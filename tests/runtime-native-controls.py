"""Probe existing naming rules and attachment protection; synthetic site only."""
import os
from pathlib import Path

import frappe

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.local.lang = 'en'

from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils.file_manager import save_file

COMPANY = 'Runtime Norwegian Example'


def rule(doctype, prefix, digits, counter=0, conditions=()):
    return frappe.get_doc({
        'doctype': 'Document Naming Rule', 'document_type': doctype, 'prefix': prefix,
        'prefix_digits': digits, 'counter': counter, 'priority': 1000,
        'conditions': [dict(field=field, condition='=', value=value) for field, value in conditions],
    }).insert()


def sale_draft():
    original = frappe.get_doc('Sales Invoice', {'company': COMPANY, 'docstatus': 1, 'is_return': 0})
    draft = frappe.copy_doc(original)
    draft.posting_date = '2026-10-18'
    draft.due_date = '2026-10-31'
    return draft.insert()


try:
    sale_rule = rule('Sales Invoice', 'F', 6, 40, [('company', COMPANY), ('is_return', '0')])
    credit_rule = rule('Sales Invoice', 'K', 6, 7, [('company', COMPANY), ('is_return', '1')])
    quote_rule = rule('Quotation', 'T', 6, 12, [('company', COMPANY)])
    customer_rule = rule('Customer', '.', 5, 10)
    supplier_rule = rule('Supplier', 'L-', 5, 20)
    customer = frappe.get_doc({'doctype': 'Customer', 'customer_name': 'Native numbered customer',
                              'customer_type': 'Company', 'customer_group': 'Commercial', 'territory': 'Norway'}).insert()
    supplier = frappe.get_doc({'doctype': 'Supplier', 'supplier_name': 'Native numbered supplier',
                              'supplier_type': 'Company', 'supplier_group': 'Services'}).insert()
    assert customer.name == '00011', customer.name
    assert supplier.name == 'L-00021', supplier.name
    assert customer.customer_name == 'Native numbered customer'
    draft = sale_draft()
    assert draft.name == 'F000041', draft.name
    draft.submit()
    assert draft.name == 'F000041'
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
    credit = make_sales_return(draft.name)
    credit.update_outstanding_for_self = 0
    credit.posting_date = '2026-10-18'
    credit.set_posting_time = 1
    credit.insert()
    assert credit.name == 'K000008', credit.name
    credit.submit()
    quote = frappe.get_doc({'doctype': 'Quotation', 'quotation_to': 'Customer', 'party_name': customer.name,
        'company': COMPANY, 'transaction_date': '2026-10-18', 'valid_till': '2026-11-18',
        'items': [{'item_code': 'RUNTIME-NO-SERVICE', 'qty': 1, 'rate': 100}]}).insert()
    assert quote.name == 'T000013', quote.name
    print('PASS native rules: independent F/K/T, five-digit party codes, optional prefix and configured start')

    # Native counter is transactional: rollback reuses an uncommitted name.
    frappe.db.savepoint('native_counter_probe')
    discarded = sale_draft()
    assert discarded.name == 'F000042'
    frappe.db.rollback(save_point='native_counter_probe')
    earlier = sale_draft()
    later = sale_draft()
    assert (earlier.name, later.name) == ('F000042', 'F000043')
    earlier.delete()
    assert not frappe.db.exists('Sales Invoice', earlier.name)
    assert frappe.db.exists('Sales Invoice', later.name)
    print('PASS native counter rollback; CONFIRMED GAP: deleting a saved draft leaves a number gap')

    frappe.set_user('runtime-owner@example.invalid')
    assert not frappe.has_permission('Document Naming Rule', 'write', sale_rule.name)
    frappe.set_user('Administrator')
    make_property_setter('Sales Invoice', None, 'protect_attached_files', 1, 'Check', for_doctype=True)
    assert frappe.get_meta('Sales Invoice').protect_attached_files
    attachment = save_file('native-protection.txt', b'synthetic document preservation probe',
                           'Sales Invoice', draft.name, is_private=1)
    file_path = Path(attachment.get_full_path())
    try:
        attachment.delete()
    except frappe.ValidationError as error:
        assert 'protected document' in str(error).lower(), str(error)
    else:
        raise AssertionError('Native attachment protection allowed submitted file deletion')
    assert file_path.read_bytes() == b'synthetic document preservation probe'
    assert frappe.db.exists('File', attachment.name)
    print('PASS existing protect_attached_files blocks Administrator deletion before disk removal')
    credit.cancel()
    cancelled_file = save_file('cancelled-protection.txt', b'synthetic cancelled document',
                               'Sales Invoice', credit.name, is_private=1)
    cancelled_path = Path(cancelled_file.get_full_path())
    cancelled_file.delete()
    assert not cancelled_path.exists()
    print('CONFIRMED GAP: native protection permits Administrator deletion on cancelled document')
    amended = frappe.copy_doc(credit)
    amended.amended_from = credit.name
    amended.insert()
    assert amended.name == 'K000008-1', amended.name
    print('CONFIRMED GAP: native amendment uses suffix before naming rules, not the next six-digit number')
    # Changing attachment references is another path; record its actual native behaviour.
    attachment.attached_to_doctype = None
    attachment.attached_to_name = None
    attachment.save()
    assert not frappe.db.get_value('File', attachment.name, 'attached_to_name')
    print('CONFIRMED GAP: protected attachment can still be detached through normal File.save')
    # This probe is not a production migration and must not change restore baselines.
    frappe.db.rollback()
    frappe.clear_cache()
finally:
    frappe.destroy()
