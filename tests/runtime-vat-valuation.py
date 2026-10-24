"""Native stock/asset VAT choices, receipt adjustments, returns and cancellation."""
import os
import sys
import json
import hashlib
from pathlib import Path

import frappe
from frappe.utils import flt
from frappe.utils.file_manager import save_file

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.conf.host_name = 'http://frontend:8080'
from erpnext_norway.vat_catalog import CODE, DEDUCTION
from erpnext_norway.vat_valuation import SOURCE
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
from erpnext.controllers.sales_and_purchase_return import make_return_doc

if len(sys.argv) > 1 and sys.argv[1] == 'verify':
    try:
        evidence = json.loads(frappe.db.get_default('runtime_vat_valuation_evidence'))
        receipt = frappe.get_doc('Purchase Receipt', evidence['receipt'])
        invoice = frappe.get_doc('Purchase Invoice', evidence['invoice'])
        adjustment = frappe.get_doc('Landed Cost Voucher', evidence['adjustment'])
        assert adjustment.docstatus == 1 and adjustment.get(SOURCE) == invoice.name
        assert receipt.items[0].get(DEDUCTION) == 100 and invoice.items[0].get(DEDUCTION) == 60
        assert flt(invoice.total_taxes_and_charges, 2) == 250
        assert flt(receipt.items[0].valuation_rate * receipt.items[0].stock_qty, 2) == 1100
        original = frappe.get_doc('File', evidence['file'])
        assert hashlib.sha256(Path(original.get_full_path()).read_bytes()).hexdigest() == evidence['sha256']
        rows = frappe.get_all('GL Entry', filters={'company': invoice.company,
            'voucher_no': ['in', [receipt.name, invoice.name]], 'is_cancelled': 0},
            fields=['account', 'debit', 'credit'])
        for number, expected in [('1460', 1100), ('2710', 150), ('2400', -1250), ('2998', 0), ('4998', 0)]:
            account = frappe.db.get_value('Account', {'company': invoice.company, 'account_number': number}, 'name')
            assert flt(sum(row.debit-row.credit for row in rows if row.account == account), 2) == expected
        print('PASS restored receipt/invoice/LCV references, 1100 stock / 150 VAT / 1250 payable and original PDF bytes')
        frappe.set_user('runtime-vat-owner@example.invalid')
        from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
        report = collect({'company': invoice.company, 'from_date': '2026-10-15', 'to_date': '2026-10-31'})
        assert flt(sum(row['input_vat'] for row in report), 2) == 262.5
        assert flt(sum(row['output_vat'] for row in report), 2) == 0
        print('PASS restored stock VAT report reconciles 262.50 input VAT for ordinary owner, including concurrent bills')
    finally:
        frappe.destroy()
    raise SystemExit(0)

try:
    from erpnext_norway import vat
    company = frappe.get_doc({'doctype': 'Company', 'company_name': 'Runtime VAT Valuation',
        'abbr': 'VVE', 'country': 'Norway', 'default_currency': 'NOK', 'tax_id': '999999993',
        'create_chart_of_accounts_based_on': 'Standard Template',
        vat.STATUS: 'Registered', vat.FROM: '2026-10-15'}).insert()
    frappe.get_doc({'doctype': 'User Permission', 'user': 'runtime-vat-owner@example.invalid',
        'allow': 'Company', 'for_value': company.name, 'apply_to_all_doctypes': 1}).insert()
    accounts = {row.account_number: row.name for row in frappe.get_all('Account',
        filters={'company': company.name}, fields=['name', 'account_number']) if row.account_number}
    valuation = frappe.get_doc({'doctype': 'Account', 'company': company.name,
        'account_name': 'Synthetic VAT valuation', 'account_number': '4998',
        'parent_account': frappe.db.get_value('Account', {'company': company.name,
            'root_type': 'Expense', 'is_group': 1}, 'name'),
        'account_type': 'Expenses Included In Valuation'}).insert()
    unbilled = frappe.get_doc({'doctype': 'Account', 'company': company.name,
        'account_name': 'Synthetic unbilled receipts', 'account_number': '2998',
        'parent_account': frappe.db.get_value('Account', {'company': company.name,
            'root_type': 'Liability', 'is_group': 1}, 'name'),
        'account_type': 'Stock Received But Not Billed'}).insert()
    asset_unbilled = frappe.get_doc({'doctype': 'Account', 'company': company.name,
        'account_name': 'Synthetic unbilled assets', 'account_number': '2997',
        'parent_account': frappe.db.get_value('Account', {'company': company.name,
            'root_type': 'Liability', 'is_group': 1}, 'name'),
        'account_type': 'Asset Received But Not Billed'}).insert()
    company.asset_received_but_not_billed = asset_unbilled.name
    company.default_inventory_account = accounts['1460']
    company.stock_received_but_not_billed = unbilled.name
    company.enable_perpetual_inventory = 1
    company.save()
    frappe.clear_document_cache('Company', company.name)
    stock = frappe.get_doc({'doctype': 'Item', 'item_code': 'SYNTHETIC-VAT-STOCK',
        'item_name': 'Synthetic stock VAT', 'item_group': 'Products', 'stock_uom': 'Nos',
        'is_stock_item': 1, 'item_defaults': [{'company': company.name,
            'expense_account': accounts['4300'], 'default_warehouse': 'Stores - VVE'}]}).insert()
    category = frappe.get_doc({'doctype': 'Asset Category',
        'asset_category_name': 'Synthetic VAT equipment',
        'accounts': [{'company_name': company.name, 'fixed_asset_account': accounts['1250']}]}).insert()
    location = frappe.get_doc({'doctype': 'Location', 'location_name': 'Synthetic VAT location'}).insert()
    asset = frappe.get_doc({'doctype': 'Item', 'item_code': 'SYNTHETIC-VAT-ASSET',
        'item_name': 'Synthetic VAT asset', 'item_group': 'Products', 'stock_uom': 'Nos',
        'is_stock_item': 0, 'is_fixed_asset': 1, 'auto_create_assets': 1,
        'asset_category': category.name, 'asset_naming_series': 'ACC-ASS-.YYYY.-',
        'item_defaults': [{'company': company.name, 'expense_account': accounts['1250']}]}).insert()
    supplier = frappe.get_all('Supplier', pluck='name')[0]
    frappe.set_user('runtime-vat-owner@example.invalid')

    def item(percent, code=stock.name, qty=2):
        return {'item_code': code, 'qty': qty, 'rate': 1000 / qty,
            'warehouse': 'Stores - VVE', 'expense_account': accounts['1250'] if code == asset.name else accounts['4300'],
            'cost_center': company.cost_center, 'item_tax_template': 'MVA 25 % – varelinjer - VVE',
            DEDUCTION: percent, 'asset_location': location.name,
            'asset_naming_series': 'ACC-ASS-.YYYY.-'}

    def draft(kind='Purchase Invoice', percent=60, code=stock.name, qty=2):
        return frappe.get_doc({'doctype': kind, 'company': company.name, 'supplier': supplier,
            'posting_date': '2026-10-18', 'transaction_date': '2026-10-18',
            'schedule_date': '2026-10-18', 'bill_date': '2026-10-18',
            'bill_no': 'SYNTHETIC-VAT-VALUATION', 'due_date': '2026-10-31',
            'set_posting_time': 1, 'update_stock': int(kind == 'Purchase Invoice'),
            'currency': 'NOK', 'conversion_rate': 1, 'cost_center': company.cost_center,
            'items': [item(percent, code, qty)], 'taxes': []})

    def submit(doc):
        doc.insert()
        if doc.doctype == 'Purchase Invoice':
            save_file('synthetic-valuation.pdf', frappe.get_print(doc.doctype, doc.name, as_pdf=True),
                doc.doctype, doc.name, is_private=1)
        doc.submit()
        return doc

    def ledger(names, expected):
        rows = frappe.get_all('GL Entry', filters={'company': company.name,
            'voucher_no': ['in', names], 'is_cancelled': 0}, fields=['account', 'debit', 'credit'])
        for account, value in expected.items():
            actual = flt(sum(row.debit - row.credit for row in rows if row.account == account), 2)
            assert actual == value, (account, actual, value)
        assert flt(sum(row.debit - row.credit for row in rows), 2) == 0

    def stock_value(names, expected):
        rows = frappe.get_all('Stock Ledger Entry', filters={'voucher_no': ['in', names],
            'is_cancelled': 0}, fields=['stock_value_difference'])
        assert flt(sum(row.stock_value_difference for row in rows), 2) == expected

    def reset():
        frappe.db.rollback(save_point='valuation_case')
        frappe.clear_cache()
        frappe.db.savepoint('valuation_case')

    frappe.db.savepoint('valuation_case')
    for percent, value, input_vat in [(60, 1100, 150), (0, 1250, 0), (100, 1000, 250)]:
        doc = submit(draft(percent=percent))
        ledger([doc.name], {accounts['1460']: value, accounts['2710']: input_vat,
            accounts['2400']: -1250, valuation.name: 0})
        stock_value([doc.name], value)
        credit = make_return_doc('Purchase Invoice', doc.name)
        credit.posting_date = credit.bill_date = '2026-10-19'
        credit.bill_no = 'SYNTHETIC-DIRECT-STOCK-CREDIT'
        credit.items[0].qty = credit.items[0].received_qty = -1
        submit(credit)
        ledger([doc.name, credit.name], {accounts['1460']: value / 2,
            accounts['2710']: input_vat / 2, accounts['2400']: -625, valuation.name: 0})
        stock_value([doc.name, credit.name], value / 2)
        credit.cancel()
        ledger([doc.name, credit.name], {accounts['1460']: value,
            accounts['2710']: input_vat, accounts['2400']: -1250, valuation.name: 0})
        reset()
    print('PASS ordinary owner direct stock 60/0/100 percent, native stock/GL values, partial credits and cancellation')

    doc = submit(draft(code=asset.name, qty=1))
    ledger([doc.name], {accounts['1250']: 1100, accounts['2710']: 150,
        accounts['2400']: -1250, valuation.name: 0})
    assets = frappe.get_all('Asset', filters={'purchase_invoice': doc.name}, fields=['net_purchase_amount'])
    assert len(assets) == 1 and assets[0].net_purchase_amount == 1100, assets
    reset()
    print('PASS native Asset purchase cost includes non-deductible VAT: 1100 asset / 150 VAT / 1250 payable')
    frappe.set_user('Administrator')
    manual = frappe.get_doc('Item', asset.name)
    manual.auto_create_assets = 0
    manual.save()
    frappe.set_user('runtime-vat-owner@example.invalid')
    doc = submit(draft(code=asset.name, qty=1))
    ledger([doc.name], {accounts['1250']: 1100, accounts['2710']: 150,
        accounts['2400']: -1250, valuation.name: 0})
    assert not frappe.db.exists('Asset', {'purchase_invoice': doc.name})
    assert frappe.db.get_value('Item', asset.name, 'auto_create_assets') == 0
    assert doc.items[0].valuation_rate == 1100
    reset()
    print('PASS manual native asset choice retained; 1100 capitalized without forcing Asset creation')

    for received, billed in [(60, 60), (100, 60), (60, 100), (60, 30)]:
        order = submit(draft('Purchase Order', received))
        receipt = make_purchase_receipt(order.name)
        receipt.posting_date = '2026-10-18'
        receipt.set_posting_time = 1
        submit(receipt)
        assert receipt.items[0].get(DEDUCTION) == received
        invoice = make_purchase_invoice(receipt.name)
        invoice.posting_date = invoice.bill_date = '2026-10-18'
        invoice.bill_no = 'SYNTHETIC-RECEIPT-VAT-CHANGE'
        invoice.items[0].set(DEDUCTION, billed)
        # An explicit full-deduction choice selects the ordinary native template.
        if billed == 100:
            invoice.items[0].item_tax_template = 'MVA 25 % – varelinjer - VVE'
        submit(invoice)
        expected_input = 250 * billed / 100
        expected_stock = 1250 - expected_input
        ledger([receipt.name, invoice.name], {accounts['1460']: expected_stock,
            accounts['2710']: expected_input, accounts['2400']: -1250,
            unbilled.name: 0, valuation.name: 0})
        stock_value([receipt.name], expected_stock)
        adjustments = frappe.get_all('Landed Cost Voucher', filters={SOURCE: invoice.name,
            'docstatus': 1}, pluck='name')
        assert len(adjustments) == int(received != billed), adjustments
        returned = make_return_doc('Purchase Receipt', receipt.name)
        returned.posting_date = '2026-10-19'
        returned.set_posting_time = 1
        returned.items[0].qty = returned.items[0].received_qty = -1
        submit(returned)
        assert returned.items[0].purchase_invoice == invoice.name
        assert returned.items[0].get(DEDUCTION) == billed
        credit = make_return_doc('Purchase Invoice', invoice.name)
        credit.posting_date = credit.bill_date = '2026-10-19'
        credit.bill_no = 'SYNTHETIC-RECEIPT-RETURN-CREDIT'
        credit.items[0].qty = credit.items[0].received_qty = -1
        submit(credit)
        assert credit.items[0].purchase_receipt == returned.name
        ledger([receipt.name, invoice.name, returned.name, credit.name], {
            accounts['1460']: expected_stock / 2, accounts['2710']: expected_input / 2,
            accounts['2400']: -625, unbilled.name: 0, valuation.name: 0, accounts['4300']: 0})
        stock_value([receipt.name, returned.name], expected_stock / 2)
        reset()
    print('PASS native order/receipt/invoice 60->60, 100->60, 60->100, 60->30; automatic native LCV, partial receipt return and linked credit')
    order = draft('Purchase Order', 55.55, qty=9)
    order.items[0].rate = 1000
    submit(order)
    receipt = make_purchase_receipt(order.name)
    receipt.posting_date = '2026-10-18'
    receipt.set_posting_time = 1
    submit(receipt)
    invoices = []
    for number in range(3):
        invoice = make_purchase_invoice(receipt.name)
        invoice.posting_date = invoice.bill_date = '2026-10-18'
        invoice.bill_no = 'SYNTHETIC-PARTIAL-ROUNDING-' + str(number)
        invoice.items[0].qty = 3
        invoice.items[0].set(DEDUCTION, 60)
        submit(invoice)
        invoices.append(invoice)
    ledger([receipt.name, *[invoice.name for invoice in invoices]], {
        accounts['1460']: 9900, accounts['2710']: 1350, accounts['2400']: -11250,
        unbilled.name: 0, valuation.name: 0})
    stock_value([receipt.name], 9900)
    names = [receipt.name, *[invoice.name for invoice in invoices]]
    returned_names = []
    for invoice in invoices:
        returned = make_return_doc('Purchase Receipt', receipt.name)
        returned.posting_date = '2026-10-19'
        returned.set_posting_time = 1
        returned.items[0].qty = returned.items[0].received_qty = -3
        returned.items[0].purchase_invoice = invoice.name
        returned.items[0].purchase_invoice_item = invoice.items[0].name
        submit(returned)
        credit = make_return_doc('Purchase Invoice', invoice.name)
        credit.posting_date = credit.bill_date = '2026-10-19'
        credit.bill_no = 'SYNTHETIC-PARTIAL-ROUNDING-CREDIT'
        credit.items[0].received_qty = credit.items[0].qty
        submit(credit)
        names += [returned.name, credit.name]
        returned_names.append(returned.name)
    ledger(names, {accounts['1460']: 0, accounts['2710']: 0, accounts['2400']: 0,
        unbilled.name: 0, valuation.name: 0, accounts['4300']: 0})
    stock_value([receipt.name, *returned_names], 0)
    reset()
    print('PASS three partial bills absorb native receipt rounding cent; explicit source invoice returns/credits clear all accounts')

    order = submit(draft('Purchase Order', 60))
    receipt = make_purchase_receipt(order.name)
    receipt.posting_date = '2026-10-18'
    receipt.set_posting_time = 1
    submit(receipt)
    edited = frappe.get_doc('Item Tax Template', receipt.items[0].item_tax_template)
    for row in edited.taxes:
        if row.tax_type == accounts['2710']: row.tax_rate = 10
        if row.tax_type == valuation.name: row.tax_rate = 15
    edited.save()
    returned = make_return_doc('Purchase Receipt', receipt.name)
    returned.posting_date = '2026-10-19'
    returned.set_posting_time = 1
    submit(returned)
    ledger([receipt.name, returned.name], {accounts['1460']: 0, accounts['2710']: 0,
        unbilled.name: 0, valuation.name: 0, accounts['4300']: 0})
    stock_value([receipt.name, returned.name], 0)
    reset()
    print('PASS unbilled native receipt return preserves issued valuation after a template edit')

    from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_purchase_receipt as receive_invoice
    invoice = draft()
    invoice.update_stock = 0
    submit(invoice)
    receipt = receive_invoice(invoice.name)
    receipt.posting_date = '2026-10-19'
    receipt.set_posting_time = 1
    submit(receipt)
    ledger([receipt.name, invoice.name], {accounts['1460']: 1100, accounts['2710']: 150,
        accounts['2400']: -1250, unbilled.name: 0, valuation.name: 0})
    returned = make_return_doc('Purchase Receipt', receipt.name)
    returned.posting_date = '2026-10-20'
    returned.set_posting_time = 1
    submit(returned)
    credit = make_return_doc('Purchase Invoice', invoice.name)
    credit.posting_date = credit.bill_date = '2026-10-20'
    credit.bill_no = 'SYNTHETIC-INVOICE-FIRST-CREDIT'
    submit(credit)
    ledger([receipt.name, invoice.name, returned.name, credit.name], {
        accounts['1460']: 0, accounts['2710']: 0, accounts['2400']: 0,
        unbilled.name: 0, valuation.name: 0, accounts['4300']: 0})
    stock_value([receipt.name, returned.name], 0)
    reset()
    print('PASS native invoice-before-receipt flow and full return/credit')

    for received, billed in [(100, 60), (60, 100)]:
        order = submit(draft('Purchase Order', received, asset.name, 1))
        receipt = make_purchase_receipt(order.name)
        receipt.items[0].asset_location = location.name
        receipt.items[0].asset_naming_series = 'ACC-ASS-.YYYY.-'
        receipt.posting_date = '2026-10-18'
        receipt.set_posting_time = 1
        submit(receipt)
        invoice = make_purchase_invoice(receipt.name)
        invoice.posting_date = invoice.bill_date = '2026-10-18'
        invoice.bill_no = 'SYNTHETIC-ASSET-RECEIPT-CHANGE'
        invoice.items[0].set(DEDUCTION, billed)
        if billed == 100: invoice.items[0].item_tax_template = 'MVA 25 % – varelinjer - VVE'
        submit(invoice)
        amount = 1250 - 250 * billed / 100
        ledger([receipt.name, invoice.name], {accounts['1250']: amount,
            accounts['2710']: 250*billed/100, accounts['2400']: -1250,
            asset_unbilled.name: 0, valuation.name: 0})
        values = frappe.get_all('Asset', filters={'purchase_receipt': receipt.name},
            fields=['net_purchase_amount', 'purchase_amount', 'additional_asset_cost'])
        assert len(values) == 1 and flt(values[0].net_purchase_amount, 2) == amount, values
        reset()
    print('PASS native asset order/receipt/invoice adjustment and asset cost basis')

    order = submit(draft('Purchase Order', 100))
    receipt = make_purchase_receipt(order.name)
    receipt.posting_date = '2026-10-18'
    receipt.set_posting_time = 1
    submit(receipt)
    invoice = make_purchase_invoice(receipt.name)
    invoice.posting_date = invoice.bill_date = '2026-10-18'
    invoice.bill_no = 'SYNTHETIC-CANCEL-VALUATION'
    invoice.items[0].set(DEDUCTION, 60)
    submit(invoice)
    adjustment = frappe.db.get_value('Landed Cost Voucher', {SOURCE: invoice.name, 'docstatus': 1}, 'name')
    assert adjustment
    invoice.cancel()
    assert frappe.db.get_value('Landed Cost Voucher', adjustment, 'docstatus') == 2
    ledger([receipt.name, invoice.name], {accounts['1460']: 1000, accounts['2710']: 0,
        accounts['2400']: 0, unbilled.name: -1000, valuation.name: 0})
    stock_value([receipt.name], 1000)
    try:
        frappe.delete_doc('Landed Cost Voucher', adjustment)
    except frappe.ValidationError:
        assert frappe.db.exists('Landed Cost Voucher', adjustment)
    else:
        raise AssertionError('Cancelled cost voucher was deleted')
    reset()
    print('PASS native invoice cancellation cancels its VAT LCV, restores receipt value and retains adjustment evidence')
    if len(sys.argv) > 1 and sys.argv[1] == 'seed':
        order = submit(draft('Purchase Order', 100))
        receipt = make_purchase_receipt(order.name)
        receipt.posting_date = '2026-10-18'
        receipt.set_posting_time = 1
        submit(receipt)
        invoice = make_purchase_invoice(receipt.name)
        invoice.posting_date = invoice.bill_date = '2026-10-18'
        invoice.bill_no = 'SYNTHETIC-VALUATION-RESTORE'
        invoice.items[0].set(DEDUCTION, 60)
        submit(invoice)
        file_name = frappe.db.get_value('File', {'attached_to_doctype': 'Purchase Invoice',
            'attached_to_name': invoice.name, 'is_private': 1}, 'name')
        original = frappe.get_doc('File', file_name)
        evidence = {'receipt': receipt.name, 'invoice': invoice.name,
            'adjustment': frappe.db.get_value('Landed Cost Voucher', {SOURCE: invoice.name, 'docstatus': 1}, 'name'),
            'file': file_name, 'sha256': hashlib.sha256(Path(original.get_full_path()).read_bytes()).hexdigest()}
        frappe.db.set_default('runtime_vat_valuation_evidence', json.dumps(evidence))
        frappe.db.commit()
        print('PASS synthetic valuation evidence committed for browser and exported restore')
finally:
    frappe.db.rollback()
    frappe.clear_cache()
    frappe.destroy()
