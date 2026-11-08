"""Read native ledgers; adapt qualified source data to the reused SAF-T builder."""
from collections import defaultdict
import csv
from decimal import Decimal
from pathlib import Path
import re

import frappe
from frappe.utils import getdate, now_datetime, get_link_to_form
from erpnext_norway import __version__
from erpnext_norway import saft_builder as xml

MAPPING = 'custom_norway_saft_mapping'
SALES = {'3':25, '31':15, '33':12, '5':0, '6':0, '7':0, '52':0}
PURCHASES = {'20':0, '21':25, '22':15, '1':25, '11':15, '13':12, '0':0, '86':25, '87':25, '88':12, '89':12}


def groups(year):
    with (Path(__file__).with_name('saft_data') / 'naeringsspesifikasjon-2025-2026.csv').open(encoding='utf-8-sig') as f:
        return {(r['GroupingCategory'], r['GroupingCode']) for r in csv.DictReader(f, delimiter=';')} | {('NA', 'NA')}


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Account': [{'fieldname': MAPPING, 'label': 'Norwegian SAF-T mapping',
        'fieldtype': 'Table', 'options': 'Norwegian SAF-T Mapping', 'insert_after': 'account_number',
        'description': 'Grouping applies from the selected fiscal year until a later mapping replaces it.'}]})


def unsupported(doc, reason='Spesialbehandling er ikke kvalifisert.'):
    frappe.throw('SAF-T: Eksportmappingen er ennå ikke kvalifisert for bilaget {0} {1}. '
        '{2} Bilaget er beholdt; det blir ikke utelatt fra eksporten.'.format(doc.doctype, doc.name, reason))


def receipt_source(doc, item):
    """Read the native receipt and its recorded clearing account, if posted."""
    from erpnext_norway.vat_catalog import CODE
    if not item.get('purchase_receipt'):
        return
    if doc.doctype != 'Purchase Invoice' or item.get(CODE) not in PURCHASES:
        unsupported(doc)
    receipt = frappe.get_doc('Purchase Receipt', item.purchase_receipt)
    receipt.check_permission('read')
    source = next((r for r in receipt.items if r.name == item.get('pr_detail')), None)
    if (receipt.company != doc.company or receipt.docstatus not in {1, 2} or not source
            or (receipt.docstatus == 2 and doc.docstatus != 2)
            or source.item_code != item.item_code or source.get(CODE) not in set(PURCHASES) | {'85'}):
        unsupported(doc, 'Mottakets lager-/deklarasjonsmapping er ikke kvalifisert.')
    if source.get(CODE) == '85':
        from erpnext_norway.vat_import import DATE, REFERENCE
        from erpnext_norway.vat_journal import BASE
        if not source.get(DATE) or not source.get(REFERENCE) or source.get(BASE) is None:
            unsupported(doc, 'Mottakets deklarasjonsgrunnlag mangler.')
    filters = {'company': doc.company, 'voucher_type': receipt.doctype, 'voucher_no': receipt.name}
    posted = frappe.get_list('GL Entry', filters=filters, fields=['name', 'account'], limit_page_length=0)
    if len(posted) != frappe.db.count('GL Entry', filters):
        frappe.throw('SAF-T krever tilgang til hele hovedboken for mottaket.', frappe.PermissionError)
    if posted and not source.get('is_fixed_asset'):
        stock_filters = {'company': doc.company, 'voucher_type': receipt.doctype,
            'voucher_no': receipt.name, 'voucher_detail_no': source.name}
        count = frappe.db.count('Stock Ledger Entry', stock_filters)
        stock = frappe.get_list('Stock Ledger Entry', filters=stock_filters,
            fields=['name'], limit_page_length=0) if count else []
        if len(stock) != count:
            frappe.throw('SAF-T krever tilgang til mottakslinjens lagerposter.', frappe.PermissionError)
        if not stock:
            return False  # A non-stock service can share a receipt with a posted asset.
    if posted and (item.expense_account not in {r.account for r in posted}
            or frappe.get_cached_value('Account', item.expense_account, 'account_type') not in
                {'Stock Received But Not Billed', 'Asset Received But Not Billed'}):
        unsupported(doc, 'Mottakets bokførte avregningskonto stemmer ikke med fakturalinjen.')
    return bool(posted)


def invoice_taxes(doc, rows):
    """Never calculate VAT. Retain native item details and signed GL directions."""
    from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION
    from erpnext_norway.vat import is_vat_account
    from erpnext_norway.vat_valuation import COST
    from erpnext_norway.vat_quarterly import ITEM
    stock_accounts = {}
    if (doc.doctype == 'Purchase Invoice' and doc.get('update_stock')
            and {item.get(CODE) for item in doc.items} <= {'20', '21', '22'}
            and not any(item.get('is_fixed_asset') for item in doc.items)):
        from erpnext_norway.saft_stock import invoice_taxes as stock_taxes
        return stock_taxes(doc, rows)
    if doc.get('update_stock') and not all(item.get('is_fixed_asset') for item in doc.items):
        from erpnext_norway.saft_stock import invoice_accounts
        stock_accounts = invoice_accounts(doc, rows)
    taxes = {r.name: r for r in doc.taxes}
    legacy_cost = {item.expense_account for item in doc.items if item.get(CODE) == '0'} if doc.doctype == 'Purchase Invoice' else set()
    # Reuse the native per-item Actual charge amount; never allocate freight.
    freight = {r.name for r in doc.taxes if doc.currency in {'NOK', 'EUR'}
        and r.charge_type == 'Actual' and not r.get(COST) and not is_vat_account(r.account_head)
        and (doc.doctype == 'Sales Invoice' or r.category == 'Total')
        and r.get('add_deduct_tax') in (None, '', 'Add') and xml._money(r.base_tax_amount)}
    if any(not is_vat_account(r.account_head) and not r.get(COST) and xml._money(r.base_tax_amount)
            and r.name not in freight and not (r.charge_type == 'On Net Total' and r.account_head in legacy_cost
                     and all(item.get(CODE) == '0' for item in doc.items)) for r in doc.taxes):
        unsupported(doc)  # Freight mapping must be qualified, not added to an arbitrary cost line.
    details = frappe.get_all('Item Wise Tax Detail', filters={'parenttype': doc.doctype, 'parent': doc.name},
        fields=['item_row', 'tax_row', 'amount', 'taxable_amount', 'rate'])
    for name in freight:
        recorded = [r for r in details if r.tax_row == name and r.item_row in {i.name for i in doc.items}]
        if (len(recorded) != len(doc.items) or {r.item_row for r in recorded} != {i.name for i in doc.items}
                or xml._money(sum((Decimal(str(r.amount)) for r in recorded), Decimal())) != xml._money(taxes[name].base_tax_amount)):
            unsupported(doc, 'Lagret tilleggsbeløp per varelinje mangler eller avviker fra bilaget.')
    result, mappings = defaultdict(list), {}
    expected_vat = defaultdict(lambda: [Decimal(), Decimal()])
    for item in doc.items:
        code = item.get(CODE)
        expected = SALES if doc.doctype == 'Sales Invoice' else PURCHASES
        if (code not in expected or (item.get(ITEM) and (doc.doctype != 'Purchase Invoice' or code != '0' or doc.currency not in {'NOK', 'EUR'}))
                or (code in {'20', '21', '22'} and doc.currency not in {'NOK', 'EUR'})
                ):
            unsupported(doc)
        posted_receipt = receipt_source(doc, item)
        values = [r for r in details if r.item_row == item.name and r.tax_row in taxes]
        vat = [r for r in values if is_vat_account(taxes[r.tax_row].account_head)]
        if (expected[code] == 0 or code in {'20', '21', '22'}) and any(xml._money(r.amount) for r in vat):
            unsupported(doc, 'Bokført MVA mangler en kvalifisert avgiftskode.')
        vat_groups = [[r for r in vat if taxes[r.tax_row].account_head == account]
            for account in {taxes[r.tax_row].account_head for r in vat}]
        if freight and any(len({Decimal(str(r.rate or 0)) for r in group if xml._money(r.amount)}) > 1
                for group in (*vat_groups, [r for r in values if taxes[r.tax_row].get(COST)])):
            unsupported(doc, 'Tillegg med annen avgiftsbehandling enn varelinjen er ikke kvalifisert.')
        for name in freight:
            # The native previous-row link identifies VAT on this charge.
            # A shared expense account alone does not establish its VAT treatment.
            if doc.currency != 'NOK' and any(xml._money(r.amount) for r in vat):
                from erpnext_norway.vat_currency import validate_rows
                validate_rows(doc)  # Reuse the posted NOK-basis/previous-row validation.
                continue
            for group in (*vat_groups, [r for r in values if taxes[r.tax_row].get(COST)]):
                if not any(xml._money(r.amount) for r in group):
                    continue
                linked = [r for r in group if xml._money(r.amount) and (
                    (taxes[r.tax_row].charge_type == 'On Previous Row Amount'
                        and str(taxes[r.tax_row].row_id) == str(taxes[name].idx))
                    or (taxes[r.tax_row].charge_type == 'On Previous Row Total'
                        and int(taxes[r.tax_row].row_id or 0) >= taxes[name].idx))]
                if len(linked) != 1:
                    unsupported(doc, 'Avgiftsgrunnlaget for tillegget mangler eller avviker fra bilaget.')
                detail, tax = linked[0], taxes[linked[0].tax_row]
                if tax.charge_type == 'On Previous Row Amount':
                    basis = sum((xml._money(r.amount) for r in values if r.tax_row == name), Decimal())
                else:
                    previous = {r.name for r in doc.taxes if r.idx <= int(tax.row_id)}
                    if any(is_vat_account(taxes[r.tax_row].account_head) or taxes[r.tax_row].get(COST)
                            for r in values if r.tax_row in previous and xml._money(r.amount)):
                        unsupported(doc, 'Tilleggsgrunnlaget omfatter andre avgiftsbeløp.')
                    basis = xml._money(item.base_net_amount) + sum((xml._money(r.amount)
                        for r in values if r.tax_row in previous), Decimal())
                if abs(xml._money(detail.taxable_amount)) != abs(basis):
                    unsupported(doc, 'Avgiftsgrunnlaget for tillegget mangler eller avviker fra bilaget.')
        foreign_vat = doc.currency != 'NOK' and any(xml._money(r.amount) for r in vat)
        if foreign_vat:
            from erpnext_norway.vat_currency import KIND
            if doc.doctype != 'Purchase Invoice' or code not in {'86', '87', '88', '89'} or any(
                    taxes[r.tax_row].charge_type != KIND for r in vat if xml._money(r.amount)):
                unsupported(doc, 'Denne valutabehandlingens eksportmapping er ikke kvalifisert.')
        # Use the posted native expense/income account; do not consult today's Item defaults.
        account = item.income_account if doc.doctype == 'Sales Invoice' else stock_accounts.get(item.name, item.expense_account)
        if (doc.doctype == 'Purchase Invoice'
                and frappe.get_cached_value('Account', account, 'root_type') != 'Expense'
                and not posted_receipt and item.name not in stock_accounts and not (item.get('is_fixed_asset')
                    and frappe.get_cached_value('Account', account, 'account_type') == 'Fixed Asset')):
            unsupported(doc)
        candidates = [r for r in rows if r.account == account and not r.party]
        if doc.doctype == 'Sales Invoice' and item.get('is_fixed_asset'):
            asset = frappe.get_doc('Asset', item.asset)
            asset.check_permission('read')
            if asset.company != doc.company:
                unsupported(doc)
            # Disposal posts book value and gain/loss separately. Use its
            # recorded fixed-asset line, never today's category defaults.
            assets = [r for r in rows if not r.party
                and frappe.get_cached_value('Account', r.account, 'account_type') == 'Fixed Asset']
            candidates = [r for r in assets if r.voucher_detail_no == item.name]
            if not candidates and sum(bool(r.get('is_fixed_asset')) for r in doc.items) == 1:
                candidates = assets
        exact = [r for r in candidates if r.voucher_detail_no == item.name]
        candidates = exact or candidates
        if not candidates and not xml._money(item.base_net_amount) and not any(xml._money(r.amount) for r in values):
            continue  # No financial posting exists for this free/zero-value source item.
        # Original and cancellation reversal can both have this source row.
        if not candidates or len({(r.posting_date, bool(r.debit), bool(r.is_cancelled)) for r in candidates}) != len(candidates):
            unsupported(doc)
        rate = Decimal(str(item.get(RATE) or 0)) if code not in {'0', '20', '21', '22', '5', '6', '7', '52'} else Decimal(0)
        if code in {'20', '21', '22'}:
            rate = Decimal(expected[code])  # Nominal import rate, not supplier VAT charged.
        if rate != expected[code]:
            unsupported(doc, 'Avgiftskoden og den bokførte satsen stemmer ikke overens.')
        deduction = Decimal(str(item.get(DEDUCTION) if item.get(DEDUCTION) is not None else 100)) if doc.doctype == 'Purchase Invoice' else Decimal(100)
        if not Decimal(0) <= deduction <= Decimal(100):
            unsupported(doc, 'Fradragsandelen må ligge mellom 0 og 100.')
        mappings[code] = xml.TaxMapping(code, rate, code,
            tuple(sorted(set(mappings[code].base_rates if code in mappings else ()) | {deduction})))
        amount = sum((abs(xml._money(r.amount)) * (-1 if taxes[r.tax_row].get('add_deduct_tax') == 'Deduct' else 1) for r in vat), Decimal())
        # No-treatment code0 has no VAT base. With partial deduction use the native
        # expense including non-deductible VAT (Skatteetaten documentation example1).
        basis = abs(xml._money(item.base_net_amount) + sum((xml._money(r.amount) for r in values
            if taxes[r.tax_row].get(COST) or r.tax_row in freight), Decimal())) if code != '0' else Decimal(0)
        if foreign_vat:
            # Native detail values are already NOK. Output and input share the
            # same VAT base; retain the stored output base once, without FX math.
            output = [r for r in vat if xml._money(r.amount) and
                taxes[r.tax_row].get('add_deduct_tax') == 'Deduct']
            if len(output) != 1 or not xml._money(output[0].taxable_amount):
                unsupported(doc, 'Entydig bokført MVA-grunnlag mangler for valutalinjen.')
            basis = abs(xml._money(output[0].taxable_amount))
        if code in {'20', '21', '22'}:
            basis = None  # Commercial supplier cost is not the customs declaration basis.
        for row in candidates:
            direction = 1 if row.debit else -1
            result[row.name].append(xml.TaxInformation(code, basis, abs(amount),
                tax_credit=direction * amount < 0 if amount else None))
            # Reconcile input and output separately, including cancellation rows.
            # Net zero in XML must not hide omitted or wrong reverse-charge VAT.
            for value in vat:
                tax = taxes[value.tax_row]
                signed = abs(xml._money(value.amount)) * direction
                if tax.get('add_deduct_tax') == 'Deduct':
                    signed = -signed
                expected_vat[tax.account_head][0] += signed
                expected_vat[tax.account_head][1] += abs(signed)
    actual_vat = defaultdict(lambda: [Decimal(), Decimal()])
    for row in rows:
        if is_vat_account(row.account):
            amount = xml._money(row.debit) - xml._money(row.credit)
            actual_vat[row.account][0] += amount
            actual_vat[row.account][1] += abs(amount)
    for account in set(actual_vat) | set(expected_vat):
        if actual_vat[account] != expected_vat[account]:
            unsupported(doc, 'Avgiftsdetaljene stemmer ikke med hovedbokens MVA-kontoer.')
    return result, mappings


def journal_taxes(doc, rows):
    """Codes 14/15 are explicitly reported on the posted VAT account itself."""
    from erpnext_norway.vat import is_vat_account
    from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION
    from erpnext_norway.vat_journal import BASE, SPEC
    from erpnext_norway.vat_quarterly import JOURNAL
    if doc.doctype != 'Journal Entry' or doc.get(JOURNAL):
        unsupported(doc)
    if any(item.get(CODE) in {'81', '82', '83', '84'} for item in doc.accounts):
        from erpnext_norway.saft_import import journal_taxes as import_taxes
        return import_taxes(doc, rows)
    if any(is_vat_account(item.account) and item.get(CODE) not in {'14', '15'} for item in doc.accounts):
        return journal_adjustment(doc, rows)
    result, mappings = {}, {}
    details = {}
    for item in doc.accounts:
        if not is_vat_account(item.account):
            if item.get(CODE) not in (None, '', '0'):
                unsupported(doc)
            continue
        code = item.get(CODE)
        expected = {'14': ('2715', 25), '15': ('2716', 15)}.get(code)
        if (not expected or item.account in details or item.get(BASE) or item.get(SPEC) or item.get(DEDUCTION)
                or item.account_currency != 'NOK'
                or frappe.get_cached_value('Account', item.account, 'account_number') != expected[0]
                or Decimal(str(item.get(RATE) or 0)) != expected[1]):
            unsupported(doc, 'Bare entydig direkteført inngående import-MVA med kode 14/15 er kvalifisert her.')
        details[item.account] = item
        mappings[code] = xml.TaxMapping(code, Decimal(expected[1]), code)
    seen = set()
    for row in rows:
        if not is_vat_account(row.account):
            continue
        item = details.get(row.account)
        amount = xml._money(row.debit) - xml._money(row.credit)
        posted = xml._money(item.debit) - xml._money(item.credit) if item else Decimal()
        signature = (row.account, row.posting_date, amount > 0, bool(row.is_cancelled))
        if (not item or not amount or abs(amount) != abs(posted) or signature in seen
                or (not row.is_cancelled and amount != posted)):
            unsupported(doc, 'Avgiftsdetaljene stemmer ikke med hovedbokens MVA-kontoer.')
        seen.add(signature)
        result[row.name] = [xml.TaxInformation(item.get(CODE), tax_amount=abs(amount), tax_credit=amount < 0)]
    if {key[0] for key in seen} != set(details):
        unsupported(doc, 'Avgiftsdetaljene stemmer ikke med hovedbokens MVA-kontoer.')
    return result, mappings


def journal_adjustment(doc, rows):
    """Read recorded basis/correction lines and native VAT amounts without allocation."""
    from erpnext_norway.vat import is_vat_account
    from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION
    from erpnext_norway.vat_journal import ACCOUNTS, BASE, SPEC
    taxes = [r for r in doc.accounts if is_vat_account(r.account)]
    costs = [r for r in doc.accounts if not is_vat_account(r.account) and not r.party
        and frappe.get_cached_value('Account', r.account, 'root_type') in {'Expense', 'Income', 'Asset'}
        and frappe.get_cached_value('Account', r.account, 'account_type') not in {'Bank', 'Cash', 'Receivable'}]
    if not 1 <= len(taxes) <= 2 or not costs or len({r.get(CODE) for r in taxes}) != 1:
        unsupported(doc, 'MVA-bilaget krever en entydig bokført grunnlags-/rettingslinje.')
    code = taxes[0].get(CODE)
    rate = Decimal(str(taxes[0].get(RATE) or 0))
    nominal = {'1':25, '3':25, '11':15, '31':15, '13':12, '33':12,
        '86':25, '87':25, '88':12, '89':12}.get(code)
    if (nominal is None or rate != nominal or len({r.account for r in taxes}) != len(taxes)
            or any(c.get(CODE) not in ((code,) if len(costs) > 1 else (None, '', '0', code))
                or c.get(BASE) or c.get(SPEC) or c.get(DEDUCTION)
                or (c.get(CODE) == code and Decimal(str(c.get(RATE) or 0)) != rate)
                or c.account_currency != 'NOK' for c in costs)):
        unsupported(doc, 'MVA-bilagets kode, sats eller bokførte grunnlag er ikke kvalifisert.')
    for item in taxes:
        if (frappe.get_cached_value('Account', item.account, 'account_number') not in ACCOUNTS[code]
                or Decimal(str(item.get(RATE) or 0)) != rate
                or (item.get(SPEC) and (code not in {'1', '11', '13'} or item.get(SPEC) not in
                    frappe.get_meta('Journal Entry Account').get_field(SPEC).options.splitlines()))
                or item.account_currency != 'NOK'):
            unsupported(doc, 'MVA-bilagets koder og satser stemmer ikke med MVA-kontoene.')
    recorded = {Decimal(str(r.get(BASE))) for r in taxes if r.get(BASE)}
    if len(recorded) > 1 or any(xml._money(value) != value for value in recorded):
        unsupported(doc, 'MVA-bilaget mangler ett entydig lagret grunnlag i NOK.')
    base = abs(next(iter(recorded))) if recorded else None
    output = [r for r in taxes if (frappe.get_cached_value('Account', r.account, 'account_number') or '').startswith('270')]
    share = Decimal(0 if code in {'87', '89'} else 100)
    if code in {'86', '88'} and output:
        share = Decimal(str(output[0].get(DEDUCTION) or 0))
        if not 0 < share <= 100 or len(taxes) != 2:
            unsupported(doc, 'Registrer dokumentert fradragsandel på utgående tjeneste-MVA; eldre bilag får ingen antatt andel.')
    marker = 'On cancellation of ' + doc.name
    stages = defaultdict(list)
    for row in rows:
        stages[row.remarks == marker].append(row)
    result = {}
    for cancelled, entries in stages.items():
        if cancelled and doc.docstatus != 2:
            unsupported(doc)
        # Reconcile every source account, including supplier/bank counterparts.
        for account in {r.account for r in doc.accounts} | {r.account for r in entries}:
            expected = tuple(sum((xml._money(r.get(side)) for r in doc.accounts if r.account == account), Decimal())
                for side in ('debit', 'credit'))
            if cancelled:
                expected = expected[::-1]
            actual = tuple(sum((xml._money(r.get(side)) for r in entries if r.account == account), Decimal())
                for side in ('debit', 'credit'))
            if actual != expected:
                unsupported(doc, 'MVA-bilaget stemmer ikke med hovedboken.')
        basis = [r for r in entries if r.account in {c.account for c in costs}]
        if not basis or (len(costs) == 1 and len(basis) != 1):
            unsupported(doc, 'Entydig bokført grunnlags-/rettingslinje mangler.')
        amount = sum((xml._money(r.debit) - xml._money(r.credit) for r in entries if is_vat_account(r.account)), Decimal())
        # Input and output share this actual basis, as on a native invoice.
        # An adjustment may have no new base; never derive one from VAT/rate.
        for row in basis:
            result[row.name] = [xml.TaxInformation(code, base if len(costs) == 1 else None,
                abs(amount) if len(costs) == 1 else Decimal(0),
                tax_credit=amount < 0 if amount else None, tax_exemption_reason=taxes[0].get(SPEC))]
    return result, {code: xml.TaxMapping(code, rate, code, (share,))}


def address(doctype, name):
    links = frappe.get_all('Dynamic Link', filters={'parenttype': 'Address',
        'link_doctype': doctype, 'link_name': name}, pluck='parent')
    if not links:
        return None
    permitted = frappe.get_list('Address', filters={'name': ['in', links], 'disabled': 0},
        fields=['name'], order_by='is_primary_address desc, name', limit_page_length=1)
    if not permitted:
        frappe.throw('SAF-T: Tilgang til adressen mangler.')
    return frappe.get_doc('Address', permitted[0].name)


def standard_account_mappings():
    """Exact shipped-chart identities; no prefix guessing or writes during export."""
    directory = Path(__file__).with_name('saft_data')
    with (directory / 'account-mapping.csv').open(encoding='utf-8-sig') as f:
        return {(r['account_number'], r['label'], r['root_type']):
            (r['GroupingCategory'], r['GroupingCode']) for r in csv.DictReader(f, delimiter=';')}


def bank_accounts(doctype, name, mapping):
    filters = ({'is_company_account': 1, 'company': name} if doctype == 'Company' else
        {'is_company_account': 0, 'party_type': doctype, 'party': name})
    # Disabled records can still describe historical transactions. Select only
    # public account details: never statement_password or integration fields.
    rows = frappe.get_list('Bank Account', filters=filters, fields=['name', 'iban',
        'bank_account_no', 'account_name', 'branch_code', 'bank', 'account'],
        order_by='name', limit_page_length=0) if frappe.db.count('Bank Account', filters) else []
    if len(rows) != frappe.db.count('Bank Account', filters):
        frappe.throw('SAF-T krever lesetilgang til de tilknyttede bankkontoene.', frappe.PermissionError)
    result = []
    for row in rows:
        bic = None
        if row.bank:
            bank = frappe.get_doc('Bank', row.bank)
            bank.check_permission('select')  # Native Bank grants Accounts Manager link/select, not full read.
            bic = bank.swift_number
        ledger = row.account if doctype == 'Company' else None
        if ledger and ledger not in mapping:
            frappe.throw('SAF-T: Bankkontoens hovedbokskonto mangler i kontoplanen.')
        result.append(xml.BankAccountData(row.bank_account_no, row.iban, row.account_name,
            row.branch_code, bic, frappe.get_cached_value('Account', ledger, 'account_currency') if ledger else None,
            mapping[ledger].account_id if ledger else None))
    return tuple(result)


def contacts(doctype, name):
    names = frappe.get_all('Dynamic Link', filters={'parenttype': 'Contact',
        'link_doctype': doctype, 'link_name': name}, pluck='parent')
    if not names:
        return ()
    rows = frappe.get_list('Contact', filters={'name': ['in', names]}, fields=['name',
        'first_name', 'last_name', 'full_name', 'phone', 'mobile_no', 'email_id'],
        order_by='name', limit_page_length=0)
    if {r.name for r in rows} != set(names):
        frappe.throw('SAF-T krever lesetilgang til de tilknyttede kontaktene.', frappe.PermissionError)
    return tuple(xml.ContactData(r.first_name if r.last_name else 'NotUsed',
        r.last_name or r.full_name or r.first_name, r.phone, r.email_id, r.mobile_no) for r in rows)


def account_catalog(company, year, used, valid):
    """Read the complete permitted native chart, including groups/disabled accounts."""
    filters = {'company': company}
    rows = frappe.get_list('Account', filters=filters,
        fields=['name', 'account_name', 'account_number', 'creation', 'root_type', 'is_group'], limit_page_length=0)
    if len(rows) != frappe.db.count('Account', filters) or not used <= {r.name for r in rows}:
        frappe.throw('SAF-T krever tilgang til hele kontoplanen for det valgte foretaket.', frappe.PermissionError)
    names = [r.name for r in rows]
    selected = defaultdict(list)
    # Child rows are scoped to the complete, permission-checked parent selection.
    if names:
        for row in frappe.get_all('Norwegian SAF-T Mapping',
                filters={'parent': ['in', names], 'parenttype': 'Account', 'parentfield': MAPPING, 'year': ['<=', year]},
                fields=['parent', 'year', 'category', 'code'], limit_page_length=0):
            selected[row.parent].append(row)
    defaults = standard_account_mappings()
    accounts, mapping = {}, {}
    for row in rows:
        history = selected[row.name]
        latest = max((r.year for r in history), default=None)
        choices = [r for r in history if r.year == latest]
        default = defaults.get((row.account_number, row.account_name, row.root_type)) if not row.is_group else None
        if not choices and row.name not in used:
            category, code = 'NA', 'NA'
        elif not choices and default in valid:
            category, code = default
        elif len(choices) == 1 and (choices[0].category, choices[0].code) in valid:
            category, code = choices[0].category, choices[0].code
        else:
            frappe.throw('SAF-T: Velg én gyldig kontokobling for {0} i {1} på kontokortet.'.format(
                get_link_to_form('Account', row.name), year))
        accounts[row.name] = xml.AccountData(row.name, row.account_name, getdate(row.creation))
        mapping[row.name] = xml.AccountMapping(row.account_number or row.name, category, code)
    return accounts, mapping


def build(company, from_date, to_date):
    frappe.only_for('Accounts Manager')
    for doctype in ('Company', 'Account', 'GL Entry'):
        frappe.has_permission(doctype, 'read', throw=True)
    if not frappe.permissions.can_export('GL Entry'):
        frappe.throw('Du har ikke tillatelse til å eksportere hovedboken.', frappe.PermissionError)
    doc = frappe.get_doc('Company', company)
    doc.check_permission('read')
    start, end = getdate(from_date), getdate(to_date)
    if not from_date or not to_date or start > end or start.year != end.year:
        frappe.throw('Velg fra- og til-dato innenfor samme regnskapsår.')
    valid = groups(start.year)
    if doc.country != 'Norway' or doc.default_currency != 'NOK':
        frappe.throw('SAF-T-eksporten krever norsk foretak og NOK som hovedvaluta.')
    org = re.sub(r'[^0-9]', '', doc.tax_id or '')
    if len(org) != 9:
        frappe.throw('Oppgi foretakets organisasjonsnummer før SAF-T-eksport.')
    pending_closing = {'company': company, 'docstatus': 1, 'period_end_date': ['<=', end],
        'gle_processing_status': ['!=', 'Completed']}
    if frappe.db.count('Period Closing Voucher', pending_closing):
        frappe.throw('SAF-T: Fullfør kjernens periodestenging før perioden eksporteres.')
    if frappe.db.count('Repost Item Valuation', {'company': company, 'docstatus': 1,
            'posting_date': ['<=', end], 'status': ['not in', ['Completed', 'Skipped', 'Cancelled']]}):
        frappe.throw('SAF-T: Fullfør kjernens lagerrepostering før perioden eksporteres.')
    filters = {'company': company, 'posting_date': ['<=', end]}
    rows = frappe.get_list('GL Entry', filters=filters, fields=['*'],
        order_by='posting_date, creation, name', limit_page_length=0)
    if len(rows) != frappe.db.count('GL Entry', filters):
        frappe.throw('SAF-T krever tilgang til hele hovedboken for det valgte foretaket.', frappe.PermissionError)
    # Do not combine multiple finance books into inflated totals.
    if any(r.finance_book and r.finance_book != doc.default_finance_book for r in rows):
        frappe.throw('SAF-T: Alternative regnskaps-/avskrivningsbøker er ikke kvalifisert i denne eksporten.')
    from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
    other_dimensions = get_accounting_dimensions() + frappe.get_all('Accounting Dimension', filters={'disabled': 1}, pluck='fieldname')
    if any(row.get(field) for field in other_dimensions for row in rows):
        frappe.throw('SAF-T: Egendefinerte regnskapsdimensjoner er ikke kvalifisert i denne eksporten.')
    dimensions = (('CC','Cost Center','cost_center','cost_center_name','Kostnadssted'),
                  ('PROJECT','Project','project','project_name','Prosjekt'))
    analysis_catalog = {}
    accounts, mapping = account_catalog(company, start.year, {row.account for row in rows}, valid)
    parties, vouchers = {}, defaultdict(list)
    for row in rows:
        vouchers[(row.voucher_type, row.voucher_no)].append(row)
        for kind, doctype, field, description, label in dimensions:
            if row.get(field) and (kind, row[field]) not in analysis_catalog:
                entity = frappe.get_doc(doctype, row[field])
                entity.check_permission('read')
                analysis_catalog[kind, row[field]] = label, entity.get(description) or row[field]
        if row.party:
            if row.party_type not in ('Customer', 'Supplier'):
                frappe.throw('SAF-T: Denne partstypen er ikke kvalifisert: ' + row.party_type)
            key = row.party_type, row.party
            if key not in parties:
                party = frappe.get_doc(*key)
                party.check_permission('read')
                addr = address(*key)
                country = (frappe.get_cached_value('Country', addr.country, 'code') or '').upper() if addr else None
                parties[key] = xml.PartyData(*key, party.get('customer_name') or party.get('supplier_name'), party.tax_id,
                    country, addr.address_line1 if addr else None, addr.pincode if addr else None,
                    addr.city if addr else None, addr.address_line2 if addr else None,
                    bank_accounts=bank_accounts(*key, mapping), contacts=contacts(*key))
    tax_info, tax_mapping, sources, quarter_cache = {}, {}, {}, {}
    from erpnext_norway.vat import is_vat_account
    from erpnext_norway.vat_journal import SETTLEMENT
    from erpnext_norway.vat_catalog import CODE
    from erpnext_norway import saft_quarterly
    from erpnext_norway.vat_quarterly import JOURNAL
    for key, entries in vouchers.items():
        source = frappe.get_doc(*key)
        source.check_permission('read')
        sources[key] = source
        if not any(start <= r.posting_date <= end and r.is_opening != 'Yes' for r in entries):
            continue  # Historical sources still contribute opening balances; not period VAT.
        # A native non-VAT voucher already supplies its complete GL. It needs
        # no parallel posting or invoice adapter (e.g. depreciation/year close).
        # VAT-bearing sources still require the explicit mappings below.
        info, maps = {}, {}
        if source.doctype in ('Sales Invoice', 'Purchase Invoice'):
            info, maps = invoice_taxes(source, entries)
            if source.doctype == 'Purchase Invoice':
                saft_quarterly.invoice_taxes(source, entries, info, maps, quarter_cache)
        elif source.doctype == 'Journal Entry' and source.get(JOURNAL):
            info, maps = saft_quarterly.journal_taxes(source, entries, quarter_cache)
        elif source.doctype == 'Purchase Receipt' and any(r.get(CODE) == '85' for r in source.items):
            from erpnext_norway.saft_stock import receipt_taxes
            info, maps = receipt_taxes(source, entries)
        elif not source.get(SETTLEMENT) and (
                any(is_vat_account(r.account) and (r.debit or r.credit) for r in entries)
                or (source.doctype == 'Journal Entry' and any(r.get(CODE) not in (None, '', '0') for r in source.accounts))):
            info, maps = journal_taxes(source, entries)
        if maps:
            tax_info.update(info)
            for code, value in maps.items():
                previous = tax_mapping.get(code)
                if previous and previous.percentage != value.percentage:
                    unsupported(source)
                tax_mapping[code] = xml.TaxMapping(code, value.percentage, code,
                    tuple(sorted(set(previous.base_rates if previous else ()) | set(value.base_rates))))
    converted = []
    for row in rows:
        source = sources[(row.voucher_type, row.voucher_no)]
        reference = source.get('bill_no') or row.against_voucher
        description = row.remarks or row.voucher_no
        if reference and len(reference) > 35 and reference not in description:
            description += '\nBilagsreferanse: ' + reference
        if source.doctype == 'Purchase Receipt':
            from erpnext_norway.vat_import import REFERENCE, DATE
            declarations = sorted({(r.get(REFERENCE), str(r.get(DATE) or '')) for r in source.items
                if r.get(CODE) == '85' and r.get(REFERENCE)})
            for declaration, date in declarations:
                description += '\nDeklarasjon: ' + declaration
                if date:
                    description += '; ekspedisjonsdato: ' + date
        owner = source.owner or row.owner
        if owner and len(owner) > 35:
            description += '\nSourceID: ' + owner
        foreign = row.account_currency and row.account_currency != 'NOK'
        currency = row.account_currency if foreign else (row.transaction_currency if row.transaction_currency != 'NOK' else None)
        debit_currency = row.debit_in_account_currency if foreign else row.debit_in_transaction_currency
        credit_currency = row.credit_in_account_currency if foreign else row.credit_in_transaction_currency
        converted.append(xml.LedgerEntry(record_id=row.name, account=row.account,
            debit=Decimal(str(row.debit)), credit=Decimal(str(row.credit)), posting_date=row.posting_date,
            voucher_type=row.voucher_type, voucher_no=row.voucher_no, remarks=description,
            transaction_date=getdate(source.get('bill_date') or source.get('posting_date') or source.get('transaction_date') or row.posting_date),
            system_entry_date=getdate(row.creation), modified_date=getdate(source.modified),
            party_type=row.party_type, party=row.party, due_date=row.due_date,
            reference_number=reference if reference and len(reference) <= 35 else None,
            source_id=owner if owner and len(owner) <= 35 else None,
            tax_information=tuple(tax_info.get(row.name, ())), is_opening=row.is_opening == 'Yes',
            analyses=tuple((kind, row[field]) for kind, _, field, _, _ in dimensions if row.get(field)),
            currency_code=currency,
            debit_currency_amount=abs(Decimal(str(debit_currency or 0))) if currency else None,
            credit_currency_amount=abs(Decimal(str(credit_currency or 0))) if currency else None,
            currency_amount=abs(Decimal(str(debit_currency or 0)) - Decimal(str(credit_currency or 0))) if currency else None))
    from erpnext_norway.saft_tax_catalog import read as read_tax_catalog
    catalog = read_tax_catalog(company, end, tax_mapping, mapping)
    addr = address('Company', company)
    return xml.build_saf_t(xml.SaftExportData(company=xml.CompanyData(org, doc.company_name, doc.phone_no,
        addr.address_line1 if addr else None, addr.pincode if addr else None, addr.city if addr else None,
        country=(frappe.get_cached_value('Country', addr.country, 'code') or '').upper() if addr else 'NO',
        address_line2=addr.address_line2 if addr else None,
        bank_accounts=bank_accounts('Company', company, mapping), contacts=contacts('Company', company),
        vat_registration_number=org if doc.get('custom_norway_vat_status') == 'Registered' else None,
        vat_registration_date=getdate(doc.get('custom_norway_vat_from')) if doc.get('custom_norway_vat_from') else None),
        period_start=start, period_end=end, software_company_name='ERPNext Norway contributors',
        software_id='ERPNext Norway', software_version=__version__, accounts=accounts,
        account_mappings=mapping, entries=tuple(converted), parties=parties, tax_mappings=tax_mapping, tax_catalog=catalog,
        analysis_catalog=analysis_catalog, created_date=now_datetime().date(), user_id=frappe.session.user))


@frappe.whitelist(methods=['GET'])
def download(company, from_date, to_date):
    try:
        content = build(company, from_date, to_date)
    except xml.SaftExportError as error:
        frappe.throw(str(error))
    from frappe.core.doctype.access_log.access_log import make_access_log
    make_access_log(doctype='GL Entry', file_type='XML', filters={'company': company,
        'from_date': from_date, 'to_date': to_date})
    org = re.sub(r'[^0-9]', '', frappe.db.get_value('Company', company, 'tax_id') or '')
    frappe.response.filename = f'SAF-T_Financial_{org}_{now_datetime():%Y%m%d%H%M%S}_1_1.xml'
    frappe.response.filecontent = content
    frappe.response.type = 'download'
