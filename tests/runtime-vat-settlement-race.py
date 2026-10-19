"""Two stale native settlement drafts must not settle the same VAT twice."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import frappe

os.chdir('/home/frappe/frappe-bench/sites')
SITE_PATH='/home/frappe/frappe-bench/sites'
frappe.init(site='accounting', sites_path=SITE_PATH)
frappe.connect()
frappe.set_user('Administrator')
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE, RATE
from erpnext_norway.vat_journal import BASE, SETTLEMENT
from erpnext_norway.vat_settlement import make_settlement

COMPANY='Runtime VAT Settlement Race'
OWNER='runtime-vat-owner@example.invalid'
barrier=Barrier(2, timeout=30)

def submit(name):
    frappe.init(site='accounting', sites_path=SITE_PATH)
    frappe.connect()
    frappe.set_user(OWNER)
    try:
        doc=frappe.get_doc('Journal Entry', name)
        # Establish a stale consistent-read snapshot before either submit wins.
        frappe.db.sql('SELECT name FROM `tabJournal Entry` WHERE company=%s', COMPANY)
        barrier.wait()
        try:
            doc.submit()
            frappe.db.commit()
            return 'submitted'
        except (frappe.ValidationError, frappe.QueryDeadlockError):
            # A native deadlock rolls back the losing transaction. As with
            # native numbering, a fresh save may be attempted by the caller;
            # the app supplies no separate retry/posting engine.
            frappe.db.rollback()
            return 'rejected'
    finally:
        frappe.destroy()

try:
    company=frappe.get_doc({'doctype':'Company','company_name':COMPANY,'abbr':'RSC',
        'country':'Norway','default_currency':'NOK','tax_id':'999999997',
        'enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',
        vat.STATUS:'Registered',vat.FROM:'2026-05-01'}).insert()
    accounts={row.account_number:row.name for row in frappe.get_all('Account',
        filters={'company':COMPANY},fields=['name','account_number']) if row.account_number}
    frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company',
        'for_value':COMPANY,'apply_to_all_doctypes':1}).insert()
    frappe.set_user(OWNER)
    source=frappe.get_doc({'doctype':'Journal Entry','company':COMPANY,
        'posting_date':'2026-05-20','voucher_type':'Journal Entry',
        'user_remark':'Synthetic VAT settlement concurrency source',
        'accounts':[{'account':accounts['1920'],'debit_in_account_currency':100},
            {'account':accounts['2700'],'credit_in_account_currency':100,
             CODE:'3',RATE:25,BASE:400}]}).insert()
    source.submit()
    drafts=[make_settlement(COMPANY,'2026-05-01','2026-06-30')['name'] for _ in range(2)]
    frappe.db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(submit,drafts))
    assert sorted(outcomes)==['rejected','submitted'],outcomes
    frappe.db.rollback()
    assert frappe.db.count('Journal Entry',{'company':COMPANY,'docstatus':1,SETTLEMENT:1})==1
    print('PASS two concurrent stale native VAT settlement drafts: exactly one submission, no duplicate settlement')
finally:
    frappe.db.rollback()
    frappe.destroy()
