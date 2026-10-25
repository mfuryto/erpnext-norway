"""Configure existing item templates; native Add/Deduct calculates and posts VAT."""
import frappe
from erpnext_norway.vat_catalog import PURCHASE_CODE, RATE, DEDUCTION, ORDINARY

TREATMENTS = {25: ('2704', '2714', '86', '87'), 12: ('2709', '2718', '88', '89')}
CODES = {code for values in TREATMENTS.values() for code in values[2:]}


def treatment(rate):
    if rate not in TREATMENTS:
        frappe.throw(frappe._('Select a supported reverse-charge service VAT rate.'))
    return TREATMENTS[rate]


def guard_currency(doc, method=None):
    """Keep manual headers within the same qualified scope as item templates."""
    from erpnext_norway.vat import vat_amount
    if doc.doctype not in ('Purchase Invoice', 'Purchase Order') or not doc.company:
        return
    company = frappe.get_cached_doc('Company', doc.company)
    if company.country != 'Norway' or (company.default_currency == 'NOK' and
            (doc.currency or company.default_currency) == 'NOK'):
        return
    if any(abs(vat_amount(tax)) > 0.000001 and frappe.get_cached_value(
            'Account', tax.account_head, 'account_number') in {number for values in TREATMENTS.values() for number in values[:2]}
            for tax in doc.taxes if tax.account_head):
        from erpnext_norway.vat_currency import validate_rows
        validate_rows(doc)


def seed(company, nominals=None):
    from erpnext_norway.vat import STATUS
    if company.country != 'Norway' or company.get(STATUS) != 'Registered':
        return
    numbers = {number for values in TREATMENTS.values() for number in values[:2]}
    numbers.update(code for row in ORDINARY for code in row[1:3])
    accounts = {number: frappe.db.get_value('Account', {'company': company.name,
        'account_number': number, 'is_group': 0}) for number in numbers}
    for nominal in TREATMENTS if nominals is None else nominals:
        output, input_, with_deduction, without = treatment(nominal)
        if not accounts.get(output) or not accounts.get(input_):
            continue  # Never invent accounts for an alternative chart.
        for percent in (100, 0):
            title = f'Tjenestekjøp fra utlandet – MVA {nominal} % – {percent} % fradrag'
            if not frappe.db.exists('Item Tax Template', {'company': company.name, 'title': title}):
                frappe.get_doc({'doctype': 'Item Tax Template', 'company': company.name, 'title': title,
                    PURCHASE_CODE: with_deduction if percent else without, RATE: nominal, DEDUCTION: percent,
                    'taxes': [{'tax_type': account, 'tax_rate': nominal if number == output or
                        (number == input_ and percent) else 0} for number, account in sorted(accounts.items()) if account],
                }).insert(ignore_permissions=True)


def validate(doc, item, template):
    from erpnext_norway.vat import effective
    company = frappe.get_cached_doc('Company', doc.company)
    if doc.doctype not in ('Purchase Invoice', 'Purchase Order') or company.default_currency != 'NOK':
        frappe.throw(frappe._('This reverse-charge item treatment currently requires a NOK service purchase invoice or order.'))
    if not effective(company, doc.get('bill_date') or doc.get('posting_date') or doc.get('transaction_date')):
        frappe.throw(frappe._('This reverse-charge item treatment requires effective VAT registration. Use the quarterly service purchase template before registration.'))
    if item.item_code:
        stock, asset = frappe.get_cached_value('Item', item.item_code, ['is_stock_item', 'is_fixed_asset'])
        if stock or asset:
            frappe.throw(frappe._('Select a non-stock service item for this reverse-charge treatment.'))
    nominal = template.get(RATE)
    output_number, input_number, _, _ = treatment(nominal)
    output = frappe.db.get_value('Account', {'company': doc.company, 'account_number': output_number})
    if (not output or next((row.tax_rate for row in template.taxes if row.tax_type == output), None) != nominal):
        frappe.throw(frappe._('The reverse-charge item template must use the output VAT account for its selected nominal rate.'))
    input_ = frappe.db.get_value('Account', {'company': doc.company, 'account_number': input_number})
    percent = template.get(DEDUCTION)
    if (percent is None or not 0 <= percent <= 100 or not input_ or
            next((row.tax_rate for row in template.taxes if row.tax_type == input_), None) != nominal * percent / 100):
        frappe.throw(frappe._('The reverse-charge item template deduction does not match its native input VAT rate.'))
