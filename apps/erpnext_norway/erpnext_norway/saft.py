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
PURCHASES = {'1':25, '11':15, '13':12, '0':0}


def groups(year):
    if year != 2026:
        frappe.throw('SAF-T-eksporten er foreløpig kvalifisert for regnskapsåret 2026.')
    with (Path(__file__).with_name('saft_data') / 'naeringsspesifikasjon-2025-2026.csv').open(encoding='utf-8-sig') as f:
        return {(r['GroupingCategory'], r['GroupingCode']) for r in csv.DictReader(f, delimiter=';')}


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Account': [{'fieldname': MAPPING, 'label': 'Norwegian SAF-T mapping',
        'fieldtype': 'Table', 'options': 'Norwegian SAF-T Mapping', 'insert_after': 'account_number',
        'description': 'Year-specific grouping from the official income statement code list.'}]})


def unsupported(doc, reason='Spesialbehandling er ikke kvalifisert.'):
    frappe.throw('SAF-T: Eksportmappingen er ennå ikke kvalifisert for bilaget {0} {1}. '
        '{2} Bilaget er beholdt; det blir ikke utelatt fra eksporten.'.format(doc.doctype, doc.name, reason))


def invoice_taxes(doc, rows):
    """Never calculate VAT. Retain native item details and signed GL directions."""
    from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION
    from erpnext_norway.vat import is_vat_account
    from erpnext_norway.vat_valuation import COST
    from erpnext_norway.vat_quarterly import ITEM
    taxes = {r.name: r for r in doc.taxes}
    legacy_cost = {item.expense_account for item in doc.items if item.get(CODE) == '0'} if doc.doctype == 'Purchase Invoice' else set()
    if any(not is_vat_account(r.account_head) and not r.get(COST) and xml._money(r.base_tax_amount)
            and not (r.charge_type == 'On Net Total' and r.account_head in legacy_cost
                     and all(item.get(CODE) == '0' for item in doc.items)) for r in doc.taxes):
        unsupported(doc)  # Freight mapping must be qualified, not added to an arbitrary cost line.
    details = frappe.get_all('Item Wise Tax Detail', filters={'parenttype': doc.doctype, 'parent': doc.name},
        fields=['item_row', 'tax_row', 'amount', 'taxable_amount', 'rate'])
    result, mappings = defaultdict(list), {}
    for item in doc.items:
        code = item.get(CODE)
        expected = SALES if doc.doctype == 'Sales Invoice' else PURCHASES
        if code not in expected or item.get(ITEM) or item.get('is_fixed_asset') or item.get('purchase_receipt') or doc.get('update_stock'):
            unsupported(doc)
        values = [r for r in details if r.item_row == item.name and r.tax_row in taxes]
        vat = [r for r in values if is_vat_account(taxes[r.tax_row].account_head)]
        if doc.currency != 'NOK' and any(xml._money(r.amount) for r in vat):
            unsupported(doc, 'Avgiftsført valuta er ikke kvalifisert.')
        # Use the posted native expense/income account; do not consult today's Item defaults.
        account = item.income_account if doc.doctype == 'Sales Invoice' else item.expense_account
        if doc.doctype == 'Purchase Invoice' and frappe.get_cached_value('Account', account, 'root_type') != 'Expense':
            unsupported(doc)
        candidates = [r for r in rows if r.account == account and not r.party]
        exact = [r for r in candidates if r.voucher_detail_no == item.name]
        candidates = exact or candidates
        # Original and cancellation reversal can both have this source row.
        if not candidates or len({(r.posting_date, bool(r.debit), bool(r.is_cancelled)) for r in candidates}) != len(candidates):
            unsupported(doc)
        rate = Decimal(str(item.get(RATE) or 0)) if code not in {'0', '5', '6', '7', '52'} else Decimal(0)
        if rate != expected[code]:
            unsupported(doc, 'Avgiftskoden og den bokførte satsen stemmer ikke overens.')
        deduction = Decimal(str(item.get(DEDUCTION) if item.get(DEDUCTION) is not None else 100)) if doc.doctype == 'Purchase Invoice' else Decimal(100)
        if not Decimal(0) <= deduction <= Decimal(100):
            unsupported(doc, 'Fradragsandelen må ligge mellom 0 og 100.')
        mappings[code] = xml.TaxMapping(code, rate, code,
            tuple(sorted(set(mappings[code].base_rates if code in mappings else ()) | {deduction})))
        amount = abs(sum((xml._money(r.amount) for r in vat), Decimal()))
        # No-treatment code0 has no VAT base. With partial deduction use the native
        # expense including non-deductible VAT (Skatteetaten documentation example1).
        basis = abs(xml._money(item.base_net_amount) + sum((xml._money(r.amount) for r in values
            if taxes[r.tax_row].get(COST)), Decimal())) if code != '0' else Decimal(0)
        for row in candidates:
            result[row.name].append(xml.TaxInformation(code, basis, amount))
    actual = sum((xml._money(r.credit) - xml._money(r.debit) for r in rows if is_vat_account(r.account)), Decimal())
    represented = sum((value.tax_amount * (1 if r.credit else -1)
        for r in rows for value in result.get(r.name, ())), Decimal())
    gross_actual = sum((abs(xml._money(r.credit) - xml._money(r.debit)) for r in rows if is_vat_account(r.account)), Decimal())
    gross_represented = sum((v.tax_amount for values in result.values() for v in values), Decimal())
    if actual != represented or gross_actual != gross_represented:
        unsupported(doc)
    return result, mappings


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
    if len(org) != 9 or not doc.phone_no:
        frappe.throw('Oppgi foretakets organisasjonsnummer og telefonnummer før SAF-T-eksport.')
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
    accounts, mapping, parties, vouchers = {}, {}, {}, defaultdict(list)
    for row in rows:
        vouchers[(row.voucher_type, row.voucher_no)].append(row)
        for kind, doctype, field, description, label in dimensions:
            if row.get(field) and (kind, row[field]) not in analysis_catalog:
                entity = frappe.get_doc(doctype, row[field])
                entity.check_permission('read')
                analysis_catalog[kind, row[field]] = label, entity.get(description) or row[field]
        if row.account not in accounts:
            acc = frappe.get_doc('Account', row.account)
            acc.check_permission('read')
            selected = [r for r in acc.get(MAPPING) or [] if r.year == start.year]
            if len(selected) != 1 or (selected[0].category, selected[0].code) not in valid or not acc.account_number:
                frappe.throw('SAF-T: Velg én gyldig kontokobling for {0} i {1} på kontokortet.'.format(get_link_to_form('Account', acc.name), start.year))
            accounts[acc.name] = xml.AccountData(acc.name, acc.account_name, getdate(acc.creation))
            mapping[acc.name] = xml.AccountMapping(acc.account_number, selected[0].category, selected[0].code)
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
                    addr.city if addr else None, addr.address_line2 if addr else None)
    tax_info, tax_mapping, sources = {}, {}, {}
    from erpnext_norway.vat import is_vat_account
    from erpnext_norway.vat_journal import SETTLEMENT
    for key, entries in vouchers.items():
        source = frappe.get_doc(*key)
        source.check_permission('read')
        sources[key] = source
        if not any(start <= r.posting_date <= end and r.is_opening != 'Yes' for r in entries):
            continue  # Historical sources still contribute opening balances; not period VAT.
        if source.doctype not in ('Sales Invoice', 'Purchase Invoice', 'Journal Entry', 'Payment Entry'):
            unsupported(source, 'Bilagstypens eksportmapping er ikke kvalifisert.')
        if source.doctype in ('Sales Invoice', 'Purchase Invoice'):
            info, maps = invoice_taxes(source, entries)
            tax_info.update(info)
            for code, value in maps.items():
                previous = tax_mapping.get(code)
                if previous and previous.percentage != value.percentage:
                    unsupported(source)
                tax_mapping[code] = xml.TaxMapping(code, value.percentage, code,
                    tuple(sorted(set(previous.base_rates if previous else ()) | set(value.base_rates))))
        elif any(is_vat_account(r.account) and (r.debit or r.credit) for r in entries) and not source.get(SETTLEMENT):
            unsupported(source)
    converted = []
    for row in rows:
        source = sources[(row.voucher_type, row.voucher_no)]
        foreign = row.account_currency and row.account_currency != 'NOK'
        currency = row.account_currency if foreign else (row.transaction_currency if row.transaction_currency != 'NOK' else None)
        debit_currency = row.debit_in_account_currency if foreign else row.debit_in_transaction_currency
        credit_currency = row.credit_in_account_currency if foreign else row.credit_in_transaction_currency
        converted.append(xml.LedgerEntry(record_id=row.name, account=row.account,
            debit=Decimal(str(row.debit)), credit=Decimal(str(row.credit)), posting_date=row.posting_date,
            voucher_type=row.voucher_type, voucher_no=row.voucher_no, remarks=(row.remarks or '')[:256],
            transaction_date=getdate(source.get('bill_date') or source.get('posting_date') or row.posting_date),
            system_entry_date=getdate(row.creation), modified_date=getdate(source.modified),
            party_type=row.party_type, party=row.party, due_date=row.due_date,
            reference_number=source.get('bill_no') or row.against_voucher,
            tax_information=tuple(tax_info.get(row.name, ())), is_opening=row.is_opening == 'Yes',
            analyses=tuple((kind, row[field]) for kind, _, field, _, _ in dimensions if row.get(field)),
            currency_code=currency,
            currency_amount=abs(Decimal(str(debit_currency or 0)) - Decimal(str(credit_currency or 0))) if currency else None))
    addr = address('Company', company)
    return xml.build_saf_t(xml.SaftExportData(company=xml.CompanyData(org, doc.company_name, doc.phone_no,
        addr.address_line1 if addr else None, addr.pincode if addr else None, addr.city if addr else None,
        address_line2=addr.address_line2 if addr else None,
        vat_registration_number=org if doc.get('custom_norway_vat_status') == 'Registered' else None,
        vat_registration_date=getdate(doc.get('custom_norway_vat_from')) if doc.get('custom_norway_vat_from') else None),
        period_start=start, period_end=end, software_company_name='ERPNext Norway contributors',
        software_id='ERPNext Norway', software_version=__version__, accounts=accounts,
        account_mappings=mapping, entries=tuple(converted), parties=parties, tax_mappings=tax_mapping,
        analysis_catalog=analysis_catalog, created_date=now_datetime().date()))


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
