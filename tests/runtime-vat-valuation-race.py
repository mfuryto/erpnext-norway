"""Concurrent partial supplier invoices must not lose native receipt valuation."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import frappe
from frappe.utils import flt
from frappe.utils.file_manager import save_file

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.conf.host_name = 'http://frontend:8080'
OWNER = 'runtime-vat-owner@example.invalid'
frappe.set_user(OWNER)
from erpnext_norway.vat_catalog import DEDUCTION
from erpnext_norway.vat_valuation import SOURCE
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
barrier = Barrier(2, timeout=30)


def submit_concurrently(name):
    frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
    frappe.connect()
    frappe.set_user(OWNER)
    try:
        frappe.db.sql('SET SESSION innodb_lock_wait_timeout=15')
        invoice = frappe.get_doc('Purchase Invoice', name)
        # Deliberately keep a consistent-read snapshot from before either LCV.
        frappe.db.sql('SELECT name FROM `tabLanded Cost Item` WHERE receipt_document=%s', receipt_name)
        barrier.wait()
        try:
            invoice.submit()
            frappe.db.commit()
            return 'submitted'
        except (frappe.ValidationError, frappe.QueryDeadlockError, frappe.QueryTimeoutError):
            frappe.db.rollback()
            return 'native conflict'
    finally:
        frappe.destroy()


try:
    company = frappe.get_doc('Company', 'Runtime VAT Valuation')
    accounts = {row.account_number: row.name for row in frappe.get_all('Account',
        filters={'company': company.name}, fields=['name', 'account_number']) if row.account_number}
    supplier = frappe.get_doc('Purchase Invoice', {'company': company.name, 'docstatus': 1, 'is_return': 0}).supplier
    order = frappe.get_doc({'doctype': 'Purchase Order', 'company': company.name, 'supplier': supplier,
        'transaction_date': '2026-10-18', 'schedule_date': '2026-10-18', 'currency': 'NOK',
        'conversion_rate': 1, 'cost_center': company.cost_center,
        'items': [{'item_code': 'SYNTHETIC-VAT-STOCK', 'qty': 2, 'rate': 500,
            'warehouse': 'Stores - VVE', 'expense_account': accounts['4300'],
            'cost_center': company.cost_center, DEDUCTION: 100,
            'item_tax_template': 'MVA 25 % – varelinjer - VVE'}]}).insert()
    order.submit()
    receipt = make_purchase_receipt(order.name)
    receipt.posting_date = '2026-10-18'
    receipt.set_posting_time = 1
    receipt.insert()
    receipt.submit()
    receipt_name = receipt.name
    names = []
    suffix = frappe.generate_hash(length=6)
    for percent in (60, 30):
        invoice = make_purchase_invoice(receipt.name)
        invoice.posting_date = invoice.bill_date = '2026-10-18'
        invoice.bill_no = f'SYNTHETIC-CONCURRENT-{suffix}-{percent}'
        invoice.items[0].qty = 1
        invoice.items[0].set(DEDUCTION, percent)
        invoice.insert()
        save_file('synthetic-concurrent-valuation.pdf', frappe.get_print(invoice.doctype,
            invoice.name, as_pdf=True), invoice.doctype, invoice.name, is_private=1)
        names.append(invoice.name)
    frappe.db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit_concurrently, names))
    frappe.db.rollback()
    # Native conflicts need a fresh ordinary save, never a second posting engine.
    for name in names:
        if frappe.db.get_value('Purchase Invoice', name, 'docstatus') == 0:
            frappe.get_doc('Purchase Invoice', name).submit()
            frappe.db.commit()
    frappe.db.rollback()
    for name in names:
        assert frappe.db.count('Landed Cost Voucher', {SOURCE: name, 'docstatus': 1}) == 1
    ledger = frappe.get_all('GL Entry', filters={'company': company.name,
        'voucher_no': ['in', [receipt.name, *names]], 'is_cancelled': 0}, fields=['account', 'debit', 'credit'])
    for code, expected in [('1460', 1137.5), ('2710', 112.5), ('2400', -1250), ('2998', 0), ('4998', 0)]:
        actual = flt(sum(row.debit-row.credit for row in ledger if row.account == accounts[code]), 2)
        assert actual == expected, (code, actual, expected, outcomes)
    stock = frappe.get_all('Stock Ledger Entry', filters={'voucher_no': receipt.name,
        'is_cancelled': 0}, fields=['stock_value_difference'])
    assert flt(sum(row.stock_value_difference for row in stock), 2) == 1137.5, outcomes
    print('PASS concurrent native partial bills: one LCV per invoice, both VAT cost adjustments retained, GL/SLE 1137.50; outcomes=' + str(outcomes))
finally:
    frappe.db.rollback()
    frappe.destroy()
