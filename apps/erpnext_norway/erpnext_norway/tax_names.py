"""Localize exact Norwegian core seed names with native link-aware renaming."""
import frappe
from frappe.model.rename_doc import rename_doc


def configure(company=None):
    companies = [company] if company else frappe.get_all('Company', filters={'country': 'Norway'}, pluck='name')
    for name in companies:
        if frappe.db.get_value('Company', name, 'country') != 'Norway':
            continue
        abbr = frappe.db.get_value('Company', name, 'abbr')
        for rate in (12, 25):
            for doctype in ('Sales Taxes and Charges Template', 'Purchase Taxes and Charges Template',
                            'Item Tax Template'):
                direction = {'Sales Taxes and Charges Template': 'Utgående MVA',
                             'Purchase Taxes and Charges Template': 'Inngående MVA',
                             'Item Tax Template': 'MVA'}[doctype]
                title = f'{direction} {rate} %' + (' – ERPNext-standard' if doctype != 'Item Tax Template' else '')
                for prefix in ('Norway', 'Notway'):
                    old_title = f'{prefix} VAT {rate}%'
                    old_name, new_name = f'{old_title} - {abbr}', f'{title} - {abbr}'
                    if not frappe.db.exists(doctype, {'name': old_name, 'company': name, 'title': old_title}):
                        continue
                    if frappe.db.exists(doctype, new_name):
                        continue  # Never merge distinct tax configurations.
                    doc = frappe.get_doc(doctype, old_name)
                    doc.db_set('title', title, update_modified=False)
                    if doctype != 'Item Tax Template':
                        for row in doc.taxes:
                            if row.description in (f'VAT {rate}%', f'VAT {rate}% @ {rate}',
                                                   f'VAT {rate}% @ {rate}.0'):
                                row.db_set('description', f'MVA {rate} %', update_modified=False)
                    rename_doc(doctype, old_name, new_name, ignore_permissions=True)
            # Only the unnumbered Tax accounts created by the native country seed.
            old_name, new_name = f'VAT {rate}% - {abbr}', f'MVA {rate} % - {abbr}'
            if (frappe.db.exists('Account', {'name': old_name, 'company': name,
                    'account_name': f'VAT {rate}%', 'account_type': 'Tax'})
                    and not frappe.db.get_value('Account', old_name, 'account_number')
                    and not frappe.db.exists('Account', new_name)):
                rename_doc('Account', old_name, new_name, ignore_permissions=True)
                frappe.db.set_value('Account', new_name, 'account_name', f'MVA {rate} %', update_modified=False)
        for doctype, old_title, new_title in (
            ('Sales Taxes and Charges Template', 'Norge MVA 25 % – salg', 'Utgående MVA 25 %'),
            ('Purchase Taxes and Charges Template', 'Norge MVA 25 % – kjøp med fullt fradrag', 'Inngående MVA 25 % – fullt fradrag'),
            ('Purchase Taxes and Charges Template', 'Norge MVA 25 % – kjøp med fradrag', 'Inngående MVA 25 % – fullt fradrag'),
        ):
            old_name, new_name = f'{old_title} - {abbr}', f'{new_title} - {abbr}'
            if (frappe.db.exists(doctype, {'name': old_name, 'company': name, 'title': old_title,
                    'tax_category': 'Norge MVA 25 %'}) and not frappe.db.exists(doctype, new_name)):
                frappe.db.set_value(doctype, old_name, 'title', new_title, update_modified=False)
                rename_doc(doctype, old_name, new_name, ignore_permissions=True)
    frappe.clear_cache()
