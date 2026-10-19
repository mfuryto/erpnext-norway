"""Private native File evidence, including nil returns without fictitious journals."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate

RETAIN = 'custom_norway_retained_vat_evidence'
KIND = 'custom_norway_vat_evidence_kind'
FROM = 'custom_norway_vat_period_from'
TO = 'custom_norway_vat_period_to'
FIELDS = (RETAIN, KIND, FROM, TO)
KINDS = ('VAT basis', 'Submitted VAT return', 'VAT receipt')


def configure_fields():
    create_custom_fields({'File': [
        {'fieldname': RETAIN, 'label': 'Retained VAT evidence', 'fieldtype': 'Check',
         'insert_after': 'attached_to_name', 'read_only': 1, 'no_copy': 1},
        {'fieldname': KIND, 'label': 'VAT evidence type', 'fieldtype': 'Select',
         'insert_after': RETAIN, 'options': '\n' + '\n'.join(KINDS), 'read_only': 1, 'no_copy': 1},
        {'fieldname': FROM, 'label': 'VAT period from', 'fieldtype': 'Date',
         'insert_after': KIND, 'read_only': 1, 'no_copy': 1},
        {'fieldname': TO, 'label': 'VAT period to', 'fieldtype': 'Date',
         'insert_after': FROM, 'read_only': 1, 'no_copy': 1},
    ]})


def authorize(company, from_date, to_date):
    company = frappe.get_doc('Company', company)
    company.check_permission('write')
    if company.country != 'Norway' or getdate(from_date) > getdate(to_date):
        frappe.throw(frappe._('Select a Norwegian company and a valid VAT period.'))
    return company


def retain(file, kind, from_date, to_date):
    if not file.is_private or not (file.file_url or '').startswith('/private/files/') or file.attached_to_doctype != 'Company':
        frappe.throw(frappe._('VAT evidence must be a private attachment on the Company.'))
    file.set(RETAIN, 1)
    file.set(KIND, kind)
    file.set(FROM, getdate(from_date))
    file.set(TO, getdate(to_date))
    file.save()
    return {'name': file.name, 'file_url': file.file_url}


@frappe.whitelist()
def preserve_basis(company, from_date, to_date):
    from frappe.utils.file_manager import save_file
    from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
    authorize(company, from_date, to_date)
    rows = collect({'company': company, 'from_date': from_date, 'to_date': to_date})
    content = frappe.as_json({'format': 'erpnext-norway-vat-basis-1', 'company': company,
        'from_date': str(getdate(from_date)), 'to_date': str(getdate(to_date)), 'rows': rows})
    file = save_file(f'MVA-grunnlag-{from_date}-{to_date}.json', content.encode(),
                     'Company', company, is_private=1)
    return retain(file, 'VAT basis', from_date, to_date)


@frappe.whitelist()
def preserve_uploaded(file_name, company, from_date, to_date, kind):
    authorize(company, from_date, to_date)
    if kind not in ('Submitted VAT return', 'VAT receipt'):
        frappe.throw(frappe._('Select a submitted VAT return or a VAT receipt.'))
    file = frappe.get_doc('File', file_name)
    file.check_permission('write')
    if file.attached_to_doctype != 'Company' or file.attached_to_name != company:
        frappe.throw(frappe._('Upload VAT evidence as a private Company attachment first.'))
    return retain(file, kind, from_date, to_date)
