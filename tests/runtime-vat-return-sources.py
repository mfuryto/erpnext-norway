"""Native credit source selection on a receipt return with multiple rows."""
import os
import json
import sys
import frappe
from frappe.utils import flt
from frappe.utils.file_manager import save_file
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('runtime-vat-owner@example.invalid')
frappe.conf.host_name = 'http://frontend:8080'
from erpnext_norway.vat_catalog import DEDUCTION
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
from erpnext.controllers.sales_and_purchase_return import make_return_doc
try:
    company = frappe.get_doc('Company', 'Runtime VAT Valuation')
    accounts = {row.account_number: row.name for row in frappe.get_all('Account',
        filters={'company': company.name}, fields=['name', 'account_number']) if row.account_number}
    supplier = frappe.get_doc('Purchase Invoice', {'company': company.name, 'docstatus': 1, 'is_return': 0}).supplier
    def submit(doc):
        doc.insert()
        if doc.doctype == 'Purchase Invoice':
            save_file('synthetic-source-lines.pdf', frappe.get_print(doc.doctype,
                doc.name, as_pdf=True), doc.doctype, doc.name, is_private=1)
        doc.submit()
        return doc
    finishing = len(sys.argv) > 1 and sys.argv[1] == 'finish'
    if finishing:
        evidence = json.loads(frappe.db.get_default('runtime_vat_return_sources'))
        receipt = frappe.get_doc('Purchase Receipt', evidence['receipt'])
        invoice = frappe.get_doc('Purchase Invoice', evidence['invoice'])
        returned = frappe.get_doc('Purchase Receipt', evidence['returned'])
    else:
        order = submit(frappe.get_doc({'doctype': 'Purchase Order', 'company': company.name,
            'supplier': supplier, 'transaction_date': '2026-10-18', 'schedule_date': '2026-10-18',
            'currency': 'NOK', 'conversion_rate': 1, 'cost_center': company.cost_center,
            'items': [{'item_code': 'SYNTHETIC-VAT-STOCK', 'qty': 4, 'rate': 250,
                'warehouse': 'Stores - VVE', 'expense_account': accounts['4300'],
                'cost_center': company.cost_center, DEDUCTION: 100,
                'item_tax_template': 'MVA 25 % – varelinjer - VVE'}]}))
        receipt = make_purchase_receipt(order.name)
        receipt.posting_date = '2026-10-18'; receipt.set_posting_time = 1
        submit(receipt)
        invoice = make_purchase_invoice(receipt.name)
        invoice.posting_date = invoice.bill_date = '2026-10-18'
        invoice.bill_no = 'SYNTHETIC-SPLIT-SOURCE'
        invoice.items[0].set(DEDUCTION, 60)
        submit(invoice)
        assert invoice.total_taxes_and_charges == 250
        assert flt(sum(row.tax_amount for row in invoice.taxes if row.account_head == accounts['2710']), 2) == 150
        returned = make_return_doc('Purchase Receipt', receipt.name)
        returned.posting_date = '2026-10-19'; returned.set_posting_time = 1
        base = returned.items[0].as_dict()
        returned.set('items', [])
        for index in range(2):
            values = {key: value for key, value in base.items() if key not in ('name', 'idx')}
            values.update(qty=-(1, 3)[index], received_qty=-(1, 3)[index], purchase_invoice=invoice.name,
                purchase_invoice_item=invoice.items[0].name)
            returned.append('items', values)
        submit(returned)
        assert [row.get(DEDUCTION) for row in returned.items] == [60, 60]
    credit = make_return_doc('Purchase Invoice', invoice.name)
    credit.posting_date = credit.bill_date = '2026-10-19'
    credit.bill_no = 'SYNTHETIC-SPLIT-SOURCE-CREDIT'
    frappe.db.savepoint('before_source_credit')
    originals = list(credit.items)
    credit.set('items', [])
    for index in range(2):
        values = {key: value for key, value in originals[0].as_dict().items() if key not in ('name', 'idx')}
        values.update(qty=-(1, 3)[index], received_qty=-(1, 3)[index], purchase_receipt=returned.name,
            pr_detail=returned.items[index].name)
        credit.append('items', values)
    # An explicit insufficient source must not silently switch to another row.
    valid = credit.items[1].pr_detail
    credit.items[1].pr_detail = credit.items[0].pr_detail
    from erpnext_norway.vat_valuation import link_credit_receipts
    try:
        link_credit_receipts(credit)
    except frappe.ValidationError:
        pass
    else:
        raise AssertionError('An invalid explicit source was silently replaced')
    credit.items[1].pr_detail = valid
    submit(credit)
    assert credit.total_taxes_and_charges == -250
    names = [receipt.name, invoice.name, returned.name, credit.name]
    gl = frappe.get_all('GL Entry', filters={'company': company.name,
        'voucher_no': ['in', names], 'is_cancelled': 0}, fields=['account', 'debit', 'credit'])
    for code in ('1460', '2710', '2400', '2998', '4998', '4300'):
        amount = flt(sum(row.debit-row.credit for row in gl if row.account == accounts[code]), 2)
        assert amount == 0, (code, amount)
    print('PASS native split receipt return and credit source rows clear all GL accounts; invalid explicit source is rejected')
    if not finishing:
        frappe.db.rollback(save_point='before_source_credit')
        frappe.db.set_default('runtime_vat_return_sources', json.dumps({
            'receipt': receipt.name, 'invoice': invoice.name, 'returned': returned.name}))
    frappe.db.commit()
finally:
    frappe.db.rollback()
    frappe.destroy()
