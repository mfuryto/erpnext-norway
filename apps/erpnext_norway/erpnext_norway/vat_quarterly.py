"""Company-wide quarterly selection; core calculates tax and posts ordinary journals."""
import calendar
from decimal import Decimal
import math

import frappe
from frappe.utils import flt, getdate, nowdate

ITEM = 'custom_norway_quarterly_service'
JOURNAL = 'custom_norway_quarterly_vat'
RETURN_TYPE = 'custom_norway_vat_return_type'
ORDINARY = 'Ordinary VAT return'
QUARTERLY = 'Reverse-charge quarterly return'
NOTE = 'custom_norway_vat_note'
SOURCE_TITLE = 'Tjenestekjøp fra utlandet – kvartalsgrunnlag før MVA-registrering'
CALC_TITLE = 'Kvartalsberegning – tjenestekjøp fra utlandet'


def nominal(row):
    return row.get('custom_norway_vat_rate') or 25


def title(base, rate):
    return base if rate == 25 else f'{base} – {rate:g} %'


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def period(date):
    date = getdate(date)
    month = (date.month - 1) // 3 * 3 + 1
    return date.replace(month=month, day=1), date.replace(month=month + 2,
        day=calendar.monthrange(date.year, month + 2)[1])


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({**{doctype: [
        {'fieldname': ITEM, 'label': 'Foreign service purchase before VAT registration',
         'fieldtype': 'Check', 'insert_after': 'custom_norway_deduction_percent', 'read_only': 1, 'depends_on': 'eval:doc.custom_norway_quarterly_service',
         'description': 'Include this service in the company-wide quarterly reverse-charge basis. Supplier payable is unchanged.',
         'print_hide': 1},
    ] for doctype in ('Purchase Invoice Item', 'Purchase Order Item')},
        'Journal Entry': [
            {'fieldname': JOURNAL, 'label': 'VAT adjustment for pre-registration services',
             'fieldtype': 'Check', 'insert_after': 'custom_norway_vat_settlement',
             'read_only': 1, 'no_copy': 1},
            {'fieldname': RETURN_TYPE, 'label': 'VAT return type', 'fieldtype': 'Select',
             'insert_after': JOURNAL, 'options': '\n' + ORDINARY + '\n' + QUARTERLY},
        ], 'Purchase Invoice': [
            {'fieldname': RETURN_TYPE, 'label': 'VAT return type', 'fieldtype': 'Select',
             'insert_after': 'tax_category', 'read_only': 1, 'no_copy': 1,
             'depends_on': 'eval:doc.items && doc.items.some(row => row.custom_norway_quarterly_service)',
             'options': '\n' + ORDINARY + '\n' + QUARTERLY},
        ], 'Journal Entry Account': [
            {'fieldname': NOTE, 'label': 'VAT return note', 'fieldtype': 'Small Text',
             'insert_after': 'custom_norway_vat_specification', 'allow_on_submit': 1},
        ]})

    for name in frappe.get_all('Company', filters={'country': 'Norway'}, pluck='name'):
        seed(frappe.get_doc('Company', name))


def seed(company):
    if company.country != 'Norway' or company.default_currency != 'NOK':
        return
    from erpnext_norway.vat_catalog import PURCHASE_CODE, RATE, DEDUCTION
    from erpnext_norway.reverse_charge import TREATMENTS
    accounts = frappe.get_all('Account', filters={'company': company.name, 'is_group': 0}, fields=['name', 'account_number'])
    for rate, (output_number, *_) in TREATMENTS.items():
        output = next((row.name for row in accounts if row.account_number == output_number), None)
        if not output:
            continue
        calc_title = title(CALC_TITLE, rate)
        if not frappe.db.exists('Item Tax Template', {'company': company.name, 'title': calc_title}):
            frappe.get_doc({'doctype': 'Item Tax Template', 'company': company.name, 'title': calc_title,
                'taxes': [{'tax_type': output, 'tax_rate': rate}]}).insert(ignore_permissions=True)
        source_title = title(SOURCE_TITLE, rate)
        if not frappe.db.exists('Item Tax Template', {'company': company.name, 'title': source_title}):
            frappe.get_doc({'doctype': 'Item Tax Template', 'company': company.name, 'title': source_title,
                PURCHASE_CODE: '0', RATE: rate, DEDUCTION: 0,
                'taxes': [{'tax_type': row.name, 'tax_rate': 0} for row in accounts
                    if (row.account_number or '').startswith(('270', '271'))]}).insert(ignore_permissions=True)


def calculation_template(company, output, rate):
    name = frappe.db.get_value('Item Tax Template', {'company': company,
        'title': title(CALC_TITLE, rate)}, 'name')
    if not name:
        frappe.throw(frappe._('Run the ordinary app migration to configure quarterly VAT calculation.'))
    template = frappe.get_cached_doc('Item Tax Template', name)
    if template.disabled or len(template.taxes) != 1 or template.taxes[0].tax_type != output or template.taxes[0].tax_rate != rate:
        frappe.throw(frappe._('Review the existing native quarterly VAT calculation template for the selected rate.'))
    return name


def prepare(doc, method=None):
    from erpnext_norway import vat
    from erpnext_norway.vat_catalog import DEDUCTION, RATE
    from erpnext_norway.vat_currency import DATE, EXCHANGE
    from erpnext_norway.reverse_charge import TREATMENTS
    source_names = {frappe.db.get_value('Item Tax Template', {'company': doc.company,
        'title': title(SOURCE_TITLE, rate)}): rate for rate in TREATMENTS}
    source_names.pop(None, None)
    if not doc.get('is_return'):
        for row in doc.items:
            if row.item_tax_template:
                row.set(ITEM, int(row.item_tax_template in source_names))
                if row.get(ITEM):
                    row.set(RATE, source_names[row.item_tax_template])
            elif row.get(ITEM):
                row.item_tax_template = next((name for name, rate in source_names.items() if rate == nominal(row)), None)
    rows = [row for row in doc.items if row.get(ITEM)]
    if doc.doctype == 'Purchase Invoice':
        doc.set(RETURN_TYPE, ORDINARY)
    if not rows:
        return
    if doc.get('is_return') and not doc.get('return_against'):
        frappe.throw(frappe._('Link the original purchase invoice before using quarterly treatment on a credit note.'))
    company = frappe.get_cached_doc('Company', doc.company)
    if doc.doctype == 'Purchase Invoice':
        doc.set(RETURN_TYPE, ORDINARY if doc.get('is_return') and vat.effective(company,
            doc.get('bill_date') or doc.posting_date) else QUARTERLY)
    if company.country != 'Norway' or company.default_currency != 'NOK':
        frappe.throw(frappe._('Quarterly reverse-charge treatment requires a Norwegian NOK accounting company.'))
    if not doc.get('is_return') and vat.effective(company,
            doc.get('bill_date') or doc.get('posting_date') or doc.get('transaction_date')):
        frappe.throw(frappe._('Use the registered reverse-charge treatment from the approved VAT registration date.'))
    from erpnext_norway.vat_catalog import PURCHASE_CODE
    for row in rows:
        if nominal(row) not in TREATMENTS:
            frappe.throw(frappe._('Select a supported reverse-charge service VAT rate.'))
        if row.item_tax_template and frappe.get_cached_value('Item Tax Template', row.item_tax_template, PURCHASE_CODE) not in (None, '', '0'):
            frappe.throw(frappe._('Use an untaxed service line for the quarterly purchase basis.'))
        if row.item_code and any(frappe.get_cached_value('Item', row.item_code, field)
                for field in ('is_stock_item', 'is_fixed_asset')):
            frappe.throw(frappe._('Select a non-stock service item for this reverse-charge treatment.'))
        row.set(DEDUCTION, 0)
        if doc.currency != 'NOK':
            if not row.get(DATE) or not math.isfinite(flt(row.get(EXCHANGE))) or flt(row.get(EXCHANGE)) <= 0:
                frappe.throw(frappe._('Enter the VAT delivery date and a positive VAT exchange rate on every service line.'))
            if doc.get('posting_date') and getdate(row.get(DATE)) > getdate(doc.posting_date):
                frappe.throw(frappe._('The VAT delivery date cannot be after the invoice posting date.'))


def projected(doc, lock=False):
    """Read core-calculated tax details on an unsaved calculation copy only."""
    from erpnext_norway.vat import is_vat_account
    from erpnext_norway.vat_currency import KIND
    from erpnext_norway.reverse_charge import treatment
    rates = {nominal(row) for row in doc.items if row.get(ITEM)}
    outputs = {rate: frappe.db.get_value('Account', {'company': doc.company,
        'account_number': treatment(rate)[0]}) for rate in rates}
    if not all(outputs.values()):
        frappe.throw(frappe._('Configure the native output VAT account for each selected service rate.'))
    copy = frappe.get_doc(doc.as_dict())
    copy.shipping_rule = None  # Retain the issued charges, not today's Shipping Rule.
    original_taxes = list(copy.taxes)
    retained = [(index, tax) for index, tax in enumerate(original_taxes, 1) if not is_vat_account(tax.account_head)]
    positions = {old: new for new, (old, _) in enumerate(retained, 1)}
    copy.set('taxes', [tax.as_dict() for _, tax in retained])
    for row in copy.taxes:
        if (row.charge_type or '').startswith('On Previous Row'):
            reference = int(row.row_id or 0)
            if reference not in positions:
                frappe.throw(frappe._('Keep quarterly service charges referenced to native non-VAT charge rows.'))
            row.row_id = str(positions[reference])
    reference = str(len(copy.taxes)) if copy.taxes else None
    for row in copy.items:
        if row.get(ITEM):
            row.item_tax_template = calculation_template(doc.company, outputs[nominal(row)], nominal(row))
    taxes = {}
    for rate, output in sorted(outputs.items()):
        values = {'charge_type': KIND if doc.currency != 'NOK' else ('On Previous Row Total' if reference else 'On Net Total'),
            'row_id': reference, 'account_head': output, 'rate': 0, 'category': 'Total',
            'description': 'Quarterly reverse-charge calculation'}
        taxes[rate] = copy.append('taxes', {**values, 'add_deduct_tax': 'Deduct'})
        # Neutral counterpart on the unsaved copy keeps the supplier total and
        # native Grand Total discount allocation equal to the original source.
        copy.append('taxes', {**values, 'add_deduct_tax': 'Add'})
    copy.calculate_taxes_and_totals()
    if money(copy.grand_total) != money(doc.grand_total):
        frappe.throw(frappe._('The native quarterly calculation no longer preserves the issued supplier amount. Review changed item tax templates or source charges.'))
    return {detail.item.name: (money(-detail.taxable_amount), money(-detail.amount))
        for detail in copy._item_wise_tax_details if detail.item.get(ITEM) and detail.tax is taxes[nominal(detail.item)]}


def current_invoice(name, lock=True):
    return frappe.get_doc('Purchase Invoice', name, for_update=lock, check_permission='read')


def sources(company, start, end, lock=True):
    names = frappe.db.sql('''SELECT DISTINCT p.name FROM `tabPurchase Invoice` p
        JOIN `tabPurchase Invoice Item` i ON i.parent=p.name
        WHERE p.company=%s AND p.docstatus=1 AND i.custom_norway_quarterly_service=1
        AND COALESCE(p.bill_date,p.posting_date) BETWEEN %s AND %s
        ORDER BY p.name''' + (' FOR UPDATE' if lock else ''), (company, start, end), as_dict=True)
    return [current_invoice(row.name, lock) for row in names]


def source_kind(doc):
    return doc.get(RETURN_TYPE) or QUARTERLY


def original_taxed(original, lock):
    first, last = period(original.bill_date or original.posting_date)
    return sum((base for source in sources(original.company, first, last, lock)
        if source_kind(source) == QUARTERLY for base, _ in projected(source, lock).values()), Decimal(0)) > 2000


def assess(company, start, end, lock=False):
    docs = sources(company, start, end, lock)
    details = {doc.name: projected(doc, lock) for doc in docs}
    basis = sum((base for doc in docs if source_kind(doc) == QUARTERLY
        for base, _ in details[doc.name].values()), Decimal(0))
    result = []
    for doc in docs:
        qualified = basis > 2000 and source_kind(doc) == QUARTERLY
        if doc.is_return and doc.return_against:
            original = current_invoice(doc.return_against, lock)
            first, _ = period(original.bill_date or original.posting_date)
            if first != period(start)[0] or source_kind(doc) == ORDINARY:
                qualified = original_taxed(original, lock)
        result.append((doc, details[doc.name], qualified))
    return result


def target(company, start, end, kind=QUARTERLY):
    result, base_total = {}, {}
    for doc, details, qualified in assess(company, start, end, lock=True):
        if not qualified or source_kind(doc) != kind:
            continue
        for row in doc.items:
            if row.name not in details:
                continue
            base, amount = details[row.name]
            key = (row.expense_account, row.cost_center or doc.cost_center, nominal(row))
            result[key] = result.get(key, Decimal(0)) + amount
            base_total[nominal(row)] = base_total.get(nominal(row), Decimal(0)) + base
    return {key: value for key, value in result.items() if value}, base_total


def difference(company, start, end, kind=QUARTERLY):
    from erpnext_norway.vat_journal import PERIOD_FROM, PERIOD_TO, BASE
    from erpnext_norway.vat_catalog import RATE
    from erpnext_norway.reverse_charge import TREATMENTS
    expected, base = target(company, start, end, kind)
    old = frappe.db.sql(f'''SELECT a.account,a.cost_center,a.debit,a.credit,a.`{BASE}`,a.`{RATE}`
        FROM `tabJournal Entry` j JOIN `tabJournal Entry Account` a ON a.parent=j.name
        WHERE j.company=%s AND j.docstatus=1 AND j.`{JOURNAL}`=1
        AND j.`{PERIOD_FROM}`=%s AND j.`{PERIOD_TO}`=%s AND j.`{RETURN_TYPE}`=%s FOR UPDATE''',
        (company, start, end, kind), as_dict=True)
    outputs = {frappe.db.get_value('Account', {'company': company, 'account_number': values[0]}): rate
        for rate, values in TREATMENTS.items()}
    for row in old:
        if row.account in outputs:
            rate = outputs[row.account]
            base[rate] = base.get(rate, Decimal(0)) - money(row.get(BASE))
        else:
            key = (row.account, row.cost_center, nominal(row))
            expected[key] = expected.get(key, Decimal(0)) - money(row.debit) + money(row.credit)
    return {key: amount for key, amount in expected.items() if amount}, base


def sync(company, start, end, posting_date=None, kind=QUARTERLY):
    from erpnext_norway.vat_journal import BASE, PERIOD_FROM, PERIOD_TO
    from erpnext_norway.vat_catalog import CODE, RATE
    frappe.get_doc('Company', company).check_permission('read')
    frappe.has_permission('Journal Entry', 'create', throw=True)
    frappe.db.get_value('Company', company, 'name', for_update=True)
    values, base = difference(company, start, end, kind)
    if not values:
        return
    from erpnext_norway.vat_catalog import check_metadata_period
    check_metadata_period(frappe._dict(doctype='Journal Entry', company=company,
        posting_date=end, is_opening='No'))
    from erpnext_norway.reverse_charge import treatment
    cc = frappe.get_cached_value('Company', company, 'cost_center')
    rows = [{'account': account, 'cost_center': cost_center, RATE: rate,
        'debit_in_account_currency': float(max(value, 0)),
        'credit_in_account_currency': float(max(-value, 0))} for (account, cost_center, rate), value in sorted(values.items())]
    for rate in sorted({key[2] for key in values}):
        amount = sum((value for key, value in values.items() if key[2] == rate), Decimal(0))
        if not amount:
            continue
        output_number, _, _, code = treatment(rate)
        output = frappe.db.get_value('Account', {'company': company, 'account_number': output_number})
        rows.append({'account': output, 'cost_center': cc, CODE: code, RATE: rate, BASE: float(base.get(rate, 0)),
            NOTE: 'Kreditnota eller korrigering av kvartalsgrunnlag' if amount < 0 else '',
            'debit_in_account_currency': float(max(-amount, 0)),
            'credit_in_account_currency': float(max(amount, 0))})
    doc = frappe.get_doc({'doctype': 'Journal Entry', 'company': company,
        'posting_date': posting_date or nowdate(), 'bill_date': end, JOURNAL: 1,
        RETURN_TYPE: kind, PERIOD_FROM: start, PERIOD_TO: end,
        'voucher_type': 'Journal Entry', 'user_remark': f'MVA på tjenestekjøp fra utlandet {start} – {end}',
        'accounts': rows}).insert()
    doc.submit()
    return doc


def update(doc, method=None):
    if not any(row.get(ITEM) for row in doc.items):
        return
    date = getdate(doc.bill_date or doc.posting_date)
    kind = source_kind(doc)
    start, end = period(date) if kind == QUARTERLY else (date, date)
    sync(doc.company, start, end, doc.posting_date, kind)
    if kind == ORDINARY:
        return
    later = frappe.db.sql(f'''SELECT DISTINCT COALESCE(p.bill_date,p.posting_date) AS date,p.`{RETURN_TYPE}` AS kind
        FROM `tabPurchase Invoice` p JOIN `tabPurchase Invoice` source ON source.name=p.return_against
        JOIN `tabPurchase Invoice Item` i ON i.parent=p.name
        WHERE p.company=%s AND p.docstatus=1 AND i.`{ITEM}`=1
        AND COALESCE(source.bill_date,source.posting_date) BETWEEN %s AND %s
        AND (COALESCE(p.bill_date,p.posting_date)>%s OR p.`{RETURN_TYPE}`=%s) FOR UPDATE''',
        (doc.company, start, end, end, ORDINARY), as_dict=True)
    scopes = set()
    for row in later:
        first, last = period(row.date) if row.kind != ORDINARY else (getdate(row.date), getdate(row.date))
        scopes.add((first, last, row.kind or QUARTERLY))
    for first, last, filing_kind in sorted(scopes):
        sync(doc.company, first, last, doc.posting_date, filing_kind)


def validate_journal(doc):
    from erpnext_norway.vat_journal import BASE, PERIOD_FROM, PERIOD_TO
    from erpnext_norway.vat_catalog import CODE, RATE
    start, end = getdate(doc.get(PERIOD_FROM)), getdate(doc.get(PERIOD_TO))
    kind = doc.get(RETURN_TYPE)
    valid_period = period(start) == (start, end) if kind == QUARTERLY else (kind == ORDINARY and start == end)
    if not valid_period or getdate(doc.bill_date) != end:
        frappe.throw(frappe._('Keep the source period and return type on this VAT adjustment.'))
    previous = doc.get_doc_before_save()
    if previous and previous.docstatus == 1:
        old = {row.name: row for row in previous.accounts}
        if any(row.name not in old or any((row.get(field) or None) != (old[row.name].get(field) or None)
                for field in (CODE, RATE, BASE)) for row in doc.accounts):
            frappe.throw(frappe._('Correct the source purchase or credit note to update its quarterly VAT adjustment.'))
        return  # Core allow-on-submit protects the ordinary financial fields.
    frappe.db.get_value('Company', doc.company, 'name', for_update=True)
    wanted, base = difference(doc.company, start, end, kind)
    from erpnext_norway.reverse_charge import TREATMENTS
    outputs = {frappe.db.get_value('Account', {'company': doc.company, 'account_number': values[0]}): (rate, values[3])
        for rate, values in TREATMENTS.items()}
    actual, tax_amounts, tax_bases = {}, {}, {}
    for row in doc.accounts:
        value = money(row.debit_in_account_currency) - money(row.credit_in_account_currency)
        if row.account in outputs:
            rate, code = outputs[row.account]
            if row.get(CODE) != code or row.get(RATE) != rate:
                frappe.throw(frappe._('Keep the original quarterly VAT adjustment classification.'))
            tax_amounts[rate] = tax_amounts.get(rate, Decimal(0)) - value
            tax_bases[rate] = tax_bases.get(rate, Decimal(0)) + money(row.get(BASE))
        else:
            key = (row.account, row.cost_center, nominal(row))
            actual[key] = actual.get(key, Decimal(0)) + value
    actual = {key: value for key, value in actual.items() if value}
    expected_taxes = {rate: sum((value for key, value in wanted.items() if key[2] == rate), Decimal(0))
        for rate in {key[2] for key in wanted}}
    expected_taxes = {rate: value for rate, value in expected_taxes.items() if value}
    if (actual != wanted or {rate: value for rate, value in tax_amounts.items() if value} != expected_taxes
            or any(tax_bases.get(rate, Decimal(0)) != base.get(rate, Decimal(0)) for rate in expected_taxes)):
        frappe.throw(frappe._('The quarterly VAT adjustment no longer matches its ordinary purchase sources.'))


def guard_cancel(doc, method=None):
    if doc.get(JOURNAL):
        frappe.throw(frappe._('Correct the source purchase or credit note to update its quarterly VAT adjustment.'))
