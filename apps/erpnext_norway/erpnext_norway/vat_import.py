"""Customs metadata on native journals/receipts; no import or valuation engine."""
import math

import frappe
from frappe.utils import flt, getdate

from erpnext_norway.vat_catalog import CODE, RATE, PURCHASE_CODE, DEDUCTION
from erpnext_norway.vat_journal import BASE

DATE = 'custom_norway_import_date'
REFERENCE = 'custom_norway_customs_reference'
IMPORT_CODES = {'81', '82', '83', '84'}


def journal_date(doc):
    from erpnext_norway.vat_quarterly import JOURNAL
    if doc.get(JOURNAL) or any(row.get(CODE) in IMPORT_CODES for row in doc.accounts):
        return getdate(doc.bill_date or doc.posting_date)
    return getdate(doc.posting_date)


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Purchase Receipt Item': [
        {'fieldname': BASE, 'label': 'Customs declaration basis (NOK)', 'fieldtype': 'Currency',
         'options': 'NOK', 'insert_after': RATE, 'allow_on_submit': 1,
         'depends_on': f'eval:["20","21","22","85"].includes(doc.{CODE}) || doc.{DATE}',
         'read_only_depends_on': 'eval:parent.is_return',
         'description': 'For code 85: documented customs value, not automatically the supplier price.'},
        {'fieldname': DATE, 'label': 'Customs expedition date', 'fieldtype': 'Date',
         'insert_after': BASE, 'allow_on_submit': 1,
         'depends_on': f'eval:["20","21","22","85"].includes(doc.{CODE}) || doc.{DATE}',
         'read_only_depends_on': 'eval:parent.is_return'},
        {'fieldname': REFERENCE, 'label': 'Customs declaration reference', 'fieldtype': 'Data',
         'insert_after': DATE, 'allow_on_submit': 1,
         'depends_on': f'eval:["20","21","22","85"].includes(doc.{CODE}) || doc.{DATE}',
         'read_only_depends_on': 'eval:parent.is_return',
         'description': 'Retain the declaration as a private receipt attachment. A goods return does not cancel the original import declaration.'},
    ]})
    for name in frappe.get_all('Company', filters={'country': 'Norway'}, pluck='name'):
        seed(frappe.get_doc('Company', name))


def seed(company):
    if company.country != 'Norway' or company.default_currency != 'NOK':
        return
    accounts = frappe.get_all('Account', filters={'company': company.name,
        'is_group': 0, 'disabled': 0}, fields=['name', 'account_number'])
    taxes = [{'tax_type': row.name, 'tax_rate': 0} for row in accounts
        if (row.account_number or '').startswith(('270', '271'))]
    if not taxes:
        return
    for code, title in (
        ('20', 'Vareimport – kostnad uten MVA-behandling'),
        ('21', 'Vareimport – leverandørfaktura, 25 % ved innførsel'),
        ('22', 'Vareimport – leverandørfaktura, 15 % ved innførsel'),
        ('85', 'Vareimport – deklarasjon uten beregning av MVA'),
    ):
        if not frappe.db.exists('Item Tax Template', {'company': company.name, 'title': title}):
            frappe.get_doc({'doctype': 'Item Tax Template', 'company': company.name,
                'title': title, PURCHASE_CODE: code, RATE: 0, DEDUCTION: 0,
                'taxes': taxes}).insert(ignore_permissions=True)


def validate_receipt(doc, method=None):
    if doc.is_return or frappe.get_cached_value('Company', doc.company, 'country') != 'Norway':
        return
    previous = doc.get_doc_before_save()
    old = {row.name: row for row in previous.items} if previous else {}
    for row in doc.items:
        original = old.get(row.name)
        if row.get(CODE) != '85' and not (original and original.get(CODE) == '85'):
            continue
        fields = (CODE, BASE, DATE, REFERENCE)
        if previous and previous.docstatus == 1 and original and all(
                (row.get(field) or None) == (original.get(field) or None) for field in fields):
            continue
        submitted = doc.docstatus == 1 or method == 'before_submit'
        if row.get(CODE) == '85':
            if not submitted and not all(row.get(field) for field in (BASE, DATE, REFERENCE)):
                continue  # An ordinary receipt draft can be completed later.
            if (not row.get(DATE) or not str(row.get(REFERENCE) or '').strip()
                    or not math.isfinite(flt(row.get(BASE))) or flt(row.get(BASE)) < 0
                    or (not (previous and previous.docstatus == 1) and not flt(row.get(BASE)))):
                frappe.throw(frappe._('Enter the documented customs basis, expedition date and declaration reference on each code 85 receipt line.'))
            if not original or original.get(CODE) != '85' or getdate(row.get(DATE)) != getdate(original.get(DATE)):
                from erpnext_norway.vat import effective
                if not effective(frappe.get_cached_doc('Company', doc.company), row.get(DATE)):
                    frappe.throw(frappe._('Use code 85 only for imports within the approved VAT registration period.'))
        if submitted:
            from erpnext_norway.vat_catalog import check_code, check_metadata_period
            check_code(doc, row)
            for date in {value for value in (row.get(DATE), original and original.get(DATE)) if value}:
                check_metadata_period(frappe._dict(doctype='Purchase Receipt', company=doc.company,
                    posting_date=getdate(date), is_opening='No'))


def receipt_rows(company, start, end):
    """Read actual zero-VAT goods receipts, including non-stock physical goods."""
    required = {row.name for row in frappe.db.sql(f"""SELECT DISTINCT p.name
        FROM `tabPurchase Receipt` p JOIN `tabPurchase Receipt Item` i ON i.parent=p.name
        WHERE p.company=%s AND p.docstatus=1 AND p.is_return=0 AND i.`{CODE}`='85'
        AND COALESCE(i.`{DATE}`,p.posting_date) BETWEEN %s AND %s""",
        (company, start, end), as_dict=True)}
    if not required:
        return  # Domestic/service-only reporting does not require stock access.
    frappe.has_permission('Purchase Receipt', 'read', throw=True)
    names = frappe.get_list('Purchase Receipt', filters={'name': ['in', sorted(required)]},
        fields=['name'], limit_page_length=0)
    if {row.name for row in names} != required:
        frappe.throw(frappe._('Read access to all code 85 import receipts in this company and period is required for a complete VAT basis.'), frappe.PermissionError)
    for entry in names:
        doc = frappe.get_doc('Purchase Receipt', entry.name)
        for row in doc.items:
            if row.get(CODE) != '85':
                continue
            if not row.get(DATE) or not row.get(REFERENCE):
                frappe.throw(frappe._('Enter the documented customs basis, expedition date and declaration reference on each code 85 receipt line.'))
            from erpnext_norway.vat_catalog import check_code
            check_code(doc, row)
            date = getdate(row.get(DATE))
            if start <= date <= end:
                yield {'posting_date': doc.posting_date, 'vat_date': date,
                    'voucher_type': doc.doctype, 'voucher': doc.name, 'line': row.idx,
                    'item_code': row.item_code, 'source_reference': row.get(REFERENCE),
                    'vat_code': '85', 'vat_rate': 0, 'vat_note': '',
                    'base_amount': flt(row.get(BASE)), 'output_vat': 0,
                    'input_vat': 0, 'net_vat': 0, 'specification': '',
                    'specification_label': '', 'vat_accounts': {}, 'portal': True}
