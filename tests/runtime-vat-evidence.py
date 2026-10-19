"""Exported backup recovery must retain private VAT evidence and its protection."""
import hashlib
import json
import os
import sys
from pathlib import Path

import frappe

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('runtime-vat-owner@example.invalid')
from erpnext_norway.vat_evidence import preserve_basis, RETAIN

try:
    if sys.argv[1] == 'seed':
        # Nil evidence must not create a fictitious financial journal.
        before = frappe.db.count('Journal Entry', {'company': 'Runtime VAT Example'})
        value = preserve_basis('Runtime VAT Example', '2026-09-01', '2026-09-30')
        file = frappe.get_doc('File', value['name'])
        assert before == frappe.db.count('Journal Entry', {'company': 'Runtime VAT Example'})
        state = {'name': file.name, 'sha256': hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()}
        frappe.set_user('Administrator')
        frappe.db.set_default('runtime_vat_retained_evidence', json.dumps(state))
        frappe.db.commit()
        print('PASS nil VAT basis preserved in native private File without a zero-value journal')
    else:
        state = json.loads(frappe.db.get_default('runtime_vat_retained_evidence'))
        file = frappe.get_doc('File', state['name'])
        assert file.get(RETAIN) == 1 and file.is_private == 1
        assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest() == state['sha256']
        frappe.db.savepoint('retained_vat_restore')
        try:
            file.delete()
        except frappe.ValidationError:
            frappe.db.rollback(save_point='retained_vat_restore')
        else:
            raise AssertionError('Restored VAT evidence could be deleted')
        assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest() == state['sha256']
        print('PASS restored VAT evidence metadata, private bytes and deletion protection')
finally:
    frappe.db.rollback()
    frappe.destroy()
