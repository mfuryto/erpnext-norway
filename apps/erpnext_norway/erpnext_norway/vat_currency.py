"""Dated NOK basis for core's taxable-base hook; core calculates/posts VAT."""
import math

import frappe
from frappe.utils import flt, getdate

KIND = 'On Norwegian VAT Base'
DATE = 'custom_norway_vat_delivery_date'
EXCHANGE = 'custom_norway_vat_exchange_rate'
PRECISION_FIELDS = ('net_amount', 'tax_amount', 'tax_amount_after_discount_amount', 'total', 'rate')


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    create_custom_fields({doctype: [
        {'fieldname': DATE, 'label': 'VAT delivery date', 'fieldtype': 'Date',
         'insert_after': 'custom_norway_deduction_percent', 'print_hide': 1,
         'depends_on': 'eval:parent.currency && parent.currency!=="NOK"',
         'description': 'For reverse-charge services: actual delivery date used for the customs exchange rate.'},
        {'fieldname': EXCHANGE, 'label': 'VAT exchange rate (NOK per currency unit)',
         'fieldtype': 'Float', 'precision': '9', 'insert_after': DATE, 'print_hide': 1,
         'depends_on': 'eval:parent.currency && parent.currency!=="NOK"',
         'description': 'Use the customs rate valid on delivery, per one currency unit. Retain its source with the invoice attachments.'},
    ] for doctype in ('Purchase Invoice Item', 'Purchase Order Item')})
    doctype = 'Purchase Taxes and Charges'
    options = frappe.get_meta(doctype).get_field('charge_type').options
    if KIND not in options.split('\n'):
        make_property_setter(doctype, 'charge_type', 'options', options + '\n' + KIND, 'Text')
    for field in PRECISION_FIELDS:
        if not frappe.db.exists('Property Setter', {'doc_type': doctype,
                'field_name': field, 'property': 'precision'}):
            make_property_setter(doctype, field, 'precision', '9', 'Int')


def foreign(doc):
    return bool(doc.get('currency') and doc.currency != 'NOK')


def issued(doc):
    return bool(doc.docstatus == 1 and doc.name and
        frappe.db.get_value(doc.doctype, doc.name, 'docstatus') == 1)


def reverse_item(doc, item, published=None):
    from erpnext_norway.vat_catalog import CODE, PURCHASE_CODE
    if doc.get('is_return') or (issued(doc) if published is None else published):
        return item.get(CODE) in ('86', '87')
    return bool(item.item_tax_template and frappe.get_cached_value(
        'Item Tax Template', item.item_tax_template, PURCHASE_CODE) in ('86', '87'))


def validate_document(doc):
    from erpnext_norway.vat import effective
    if (frappe.get_cached_value('Company', doc.company, 'default_currency') != 'NOK'
            or doc.doctype not in ('Purchase Invoice', 'Purchase Order') or not doc.items):
        frappe.throw(frappe._('Use a NOK accounting company and a service purchase invoice or order for this VAT basis.'))
    company = frappe.get_cached_doc('Company', doc.company)
    published = issued(doc)
    original_treatment = published or doc.get('is_return')
    if not original_treatment and not effective(company, doc.get('bill_date') or doc.get('posting_date') or doc.get('transaction_date')):
        frappe.throw(frappe._('This reverse-charge item treatment requires effective VAT registration. Non-registered quarterly treatment is not yet qualified.'))
    for item in doc.items:
        if not reverse_item(doc, item, published):
            frappe.throw(frappe._('Use only reverse-charge service lines on this foreign-currency invoice or order.'))
        if not item.get(DATE) or not math.isfinite(flt(item.get(EXCHANGE))) or flt(item.get(EXCHANGE)) <= 0:
            frappe.throw(frappe._('Enter the VAT delivery date and a positive VAT exchange rate on every service line.'))
        if doc.doctype == 'Purchase Invoice' and getdate(item.get(DATE)) > getdate(doc.posting_date):
            frappe.throw(frappe._('The VAT delivery date cannot be after the invoice posting date.'))
        if not original_treatment and getdate(item.get(DATE)) < getdate(company.get('custom_norway_vat_from')):
            frappe.throw(frappe._('Delivery before VAT registration is not yet supported by this currency treatment.'))
        if not original_treatment and item.item_code and any(frappe.get_cached_value('Item', item.item_code, field)
                for field in ('is_stock_item', 'is_fixed_asset')):
            frappe.throw(frappe._('Select a non-stock service item for this reverse-charge treatment.'))
    if not published and any((frappe.new_doc('Purchase Taxes and Charges').precision(field) or 0) < 6
            for field in PRECISION_FIELDS):
        frappe.throw(frappe._('This VAT basis requires at least six decimal places on the purchase tax amount and rate fields. Review the existing field precision settings.'))


def prepare(doc):
    if not foreign(doc) or not any(reverse_item(doc, item) for item in doc.items):
        return
    validate_document(doc)
    for tax in doc.taxes:
        number = frappe.get_cached_value('Account', tax.account_head, 'account_number') if tax.account_head else ''
        if number in ('2704', '2714') or tax.get('custom_norway_vat_cost'):
            if tax.charge_type == KIND:
                continue
            if tax.get('set_by_item_tax_template') and tax.charge_type == 'On Net Total':
                tax.charge_type = KIND
            else:
                frappe.throw(frappe._('Use the Norwegian VAT basis on the reverse-charge tax rows for this currency invoice.'))


def basis(calc, item, tax):
    """Return only the transaction-currency basis to the native calculator."""
    if not foreign(calc.doc):
        frappe.throw(frappe._('Use the Norwegian currency VAT basis only on foreign-currency purchases.'))
    return flt(item.net_amount) * flt(item.get(EXCHANGE)) / flt(calc.doc.conversion_rate)


def validate_rows(doc):
    from erpnext_norway.vat import vat_amount
    validate_document(doc)
    for tax in doc.taxes:
        if not abs(vat_amount(tax)) > 0.000001:
            continue
        number = frappe.get_cached_value('Account', tax.account_head, 'account_number')
        if (tax.charge_type != KIND or tax.included_in_print_rate or
                (number not in ('2704', '2714') and not tax.get('custom_norway_vat_cost'))):
            frappe.throw(frappe._('Use only the Norwegian reverse-charge VAT basis without additional charges on this currency invoice.'))
        expected = 'Deduct' if number == '2704' else 'Add'
        if tax.add_deduct_tax != expected or tax.category != 'Total':
            frappe.throw(frappe._('Keep output reverse-charge VAT as Deduct and input VAT as Add in the native tax rows.'))
