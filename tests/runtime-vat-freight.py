"""Native freight VAT allocation through purchasing, returns and cancellation."""
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
        evidence = json.loads(frappe.db.get_default('runtime_vat_freight_evidence'))
        invoice = frappe.get_doc('Purchase Invoice', evidence['invoice'])
        receipt = frappe.get_doc('Purchase Receipt', evidence['receipt'])
        adjustment = frappe.get_doc('Landed Cost Voucher', evidence['allocation'])
        assert adjustment.custom_norway_vat_allocation == 1 and adjustment.docstatus == 1
        assert adjustment.get(SOURCE) == invoice.name
        assert adjustment.total_taxes_and_charges == 105
        assert flt(receipt.items[0].valuation_rate * receipt.items[0].stock_qty, 2) == 1105
        original = frappe.get_doc('File', evidence['file'])
        assert hashlib.sha256(Path(original.get_full_path()).read_bytes()).hexdigest() == evidence['sha256']
        frappe.set_user('runtime-vat-owner@example.invalid')
        from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
        report = collect({'company': invoice.company, 'from_date':'2026-10-15','to_date':'2026-10-31'})
        assert flt(sum(row['input_vat'] for row in report), 2) == 315
        assert flt(sum(row['output_vat'] for row in report), 2) == 0
        print('PASS restored freight receipt/invoice/marked LCV, 1105 stock / 315 VAT report and original private PDF bytes')
    finally:
        frappe.destroy()
    raise SystemExit(0)

try:
    from erpnext_norway import vat
    company = frappe.get_doc({'doctype': 'Company', 'company_name': 'Runtime VAT Valuation Mixed',
        'abbr': 'VVM', 'country': 'Norway', 'default_currency': 'NOK', 'tax_id': '999999993',
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
    stock = frappe.get_doc({'doctype': 'Item', 'item_code': 'SYNTHETIC-VAT-STOCK-M',
        'item_name': 'Synthetic stock VAT', 'item_group': 'Products', 'stock_uom': 'Nos',
        'is_stock_item': 1, 'item_defaults': [{'company': company.name,
            'expense_account': accounts['4300'], 'default_warehouse': 'Stores - VVM'}]}).insert()
    category = frappe.get_doc({'doctype': 'Asset Category',
        'asset_category_name': 'Synthetic VAT equipment mixed',
        'accounts': [{'company_name': company.name, 'fixed_asset_account': accounts['1250']}]}).insert()
    location = frappe.get_doc({'doctype': 'Location', 'location_name': 'Synthetic VAT location mixed'}).insert()
    asset = frappe.get_doc({'doctype': 'Item', 'item_code': 'SYNTHETIC-VAT-ASSET-M',
        'item_name': 'Synthetic VAT asset', 'item_group': 'Products', 'stock_uom': 'Nos',
        'is_stock_item': 0, 'is_fixed_asset': 1, 'auto_create_assets': 1,
        'asset_category': category.name, 'asset_naming_series': 'ACC-ASS-.YYYY.-',
        'item_defaults': [{'company': company.name, 'expense_account': accounts['1250']}]}).insert()
    supplier = frappe.get_all('Supplier', pluck='name')[0]
    frappe.set_user('runtime-vat-owner@example.invalid')

    def item(percent, code=stock.name, qty=2):
        return {'item_code': code, 'qty': qty, 'rate': 1000 / qty,
            'warehouse': 'Stores - VVM', 'expense_account': accounts['1250'] if code == asset.name else accounts['4300'],
            'cost_center': company.cost_center, 'item_tax_template': 'MVA 25 % – varelinjer - VVM',
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

    def mixed(kind='Purchase Invoice', percent=60, qty=2):
        doc = draft(kind, percent, qty=qty)
        doc.append('items', {'item_code':'RUNTIME-VAT-SERVICE','qty':qty,'rate':1000/qty,
            'expense_account':accounts['4500'],'cost_center':company.cost_center,
            'item_tax_template':'MVA 25 % – varelinjer - VVM',DEDUCTION:percent})
        doc.append('taxes', {'charge_type':'Actual','account_head':accounts['6100'],
            'tax_amount':100,'description':'Synthetic freight','category':'Total','add_deduct_tax':'Add',
            'cost_center':company.cost_center})
        doc.append('taxes', {'charge_type':'On Previous Row Total','row_id':'1','account_head':accounts['2710'],
            'rate':25,'description':'Synthetic VAT on freight','category':'Total','add_deduct_tax':'Add',
            'cost_center':company.cost_center})
        return doc
    def state(names, stock_amount, service_amount, vat_amount, payable=-2625, freight=100):
        ledger(names,{accounts['1460']:stock_amount,accounts['4500']:service_amount,
            accounts['6100']:freight,accounts['2710']:vat_amount,accounts['2400']:payable,
            valuation.name:0,unbilled.name:0,accounts['4300']:0,company.round_off_account:0})
    frappe.db.savepoint('valuation_case')
    doc=submit(mixed())
    state([doc.name],1105,1105,315)
    stock_value([doc.name],1105)
    returned=make_return_doc('Purchase Invoice',doc.name)
    returned.posting_date=returned.bill_date='2026-10-19';returned.bill_no='SYNTHETIC-FREIGHT-CREDIT'
    submit(returned)
    state([doc.name,returned.name],0,0,0,0,0)
    stock_value([doc.name,returned.name],0)
    reset()
    print('PASS automatic native direct freight allocation and full credit clear stock, service, freight, VAT, payable and clearing')

    for received,billed in [(60,60),(100,60),(60,100),(60,30)]:
        order=submit(mixed('Purchase Order',received))
        receipt=make_purchase_receipt(order.name)
        receipt.posting_date='2026-10-18';receipt.set_posting_time=1
        submit(receipt)
        invoice=make_purchase_invoice(receipt.name)
        invoice.posting_date=invoice.bill_date='2026-10-18';invoice.bill_no='SYNTHETIC-FREIGHT-CHAIN'
        for row in invoice.items:
            row.set(DEDUCTION,billed)
            if billed==100:row.item_tax_template='MVA 25 % – varelinjer - VVM'
        submit(invoice)
        expected=1000+262.5*(100-billed)/100
        state([receipt.name,invoice.name],expected,expected,525*billed/100)
        stock_value([receipt.name],expected)
        returned=make_return_doc('Purchase Receipt',receipt.name)
        returned.posting_date='2026-10-19';returned.set_posting_time=1
        submit(returned)
        credit=make_return_doc('Purchase Invoice',invoice.name)
        credit.posting_date=credit.bill_date='2026-10-19';credit.bill_no='SYNTHETIC-FREIGHT-CHAIN-CREDIT'
        submit(credit)
        state([receipt.name,invoice.name,returned.name,credit.name],0,0,0,0,0)
        stock_value([receipt.name,returned.name],0)
        reset()
        print(f'PASS automatic native freight PO/PR/PI {received}->{billed}, return and credit reconcile all GL/SLE')

    doc=submit(mixed())
    returned=make_return_doc('Purchase Invoice',doc.name)
    returned.posting_date=returned.bill_date='2026-10-19';returned.bill_no='SYNTHETIC-FREIGHT-PARTIAL'
    for row in returned.items:row.qty=row.received_qty=-1
    for tax in returned.taxes:
        if tax.charge_type=='Actual':tax.tax_amount=-50
    submit(returned)
    ledger([doc.name,returned.name],{accounts['1460']:552.5,accounts['4500']:552.5,
        accounts['6100']:50,accounts['2710']:157.5,accounts['2400']:-1313,
        company.round_off_account:0.5,valuation.name:0,accounts['4300']:0})
    stock_value([doc.name,returned.name],552.5)
    reset()
    print('PASS partial native freight credit preserves ordinary rounding and signed valuation')

    doc=mixed()
    doc.taxes[1].charge_type='On Previous Row Amount'
    doc.append('taxes',{'charge_type':'On Net Total','account_head':accounts['2710'],
        'rate':25,'description':'Synthetic VAT on goods','category':'Total','add_deduct_tax':'Add',
        'included_in_print_rate':1,'cost_center':company.cost_center})
    for row in doc.items:row.rate=625
    submit(doc)
    state([doc.name],1105,1105,315)
    stock_value([doc.name],1105)
    reset()
    print('PASS goods price including VAT plus exclusive freight uses distinct native tax bases and inclusion flags')

    doc=mixed()
    doc.items[1].item_tax_template='MVA 15 % – varelinjer - VVM'
    doc.items[1].set(DEDUCTION,0)
    doc.append('taxes',{'charge_type':'On Previous Row Total','row_id':'1','account_head':accounts['2711'],
        'rate':15,'description':'Synthetic 15 percent VAT basis','category':'Total',
        'add_deduct_tax':'Add','cost_center':company.cost_center})
    submit(doc)
    ledger([doc.name],{accounts['1460']:1105,accounts['4500']:1157.5,accounts['6100']:100,
        accounts['2710']:157.5,accounts['2711']:0,accounts['2400']:-2520,valuation.name:0})
    reset()
    print('PASS mixed native 25/15 rates and 60/0 deduction follow explicit native freight tax bases')

    doc=mixed()
    doc.taxes[0].tax_amount=300
    doc.append('items',item(0))
    submit(doc)
    state([doc.name],2385,1110,330,payable=-4125,freight=300)
    stock_value([doc.name],2385)
    reset()
    print('PASS multiple stock rows with different deduction retain native per-row landed cost allocation')

    doc=submit(mixed())
    doc.cancel()
    state([doc.name],0,0,0,0,0)
    stock_value([doc.name],0)
    reset()
    print('PASS direct native invoice cancel reverses its own automatic allocation')

    invalid=mixed()
    invalid.items[0].item_code=asset.name
    invalid.items[0].expense_account=accounts['1250']
    try:
        invalid.insert()
    except frappe.ValidationError as error:
        assert 'fixed assets requires a qualified native allocation' in str(error),str(error)
    else:
        raise AssertionError('Unsupported native asset return allocation was opened')
    reset()
    print('PASS unsupported asset freight chain remains blocked without changing asset creation choices')

    order=submit(mixed('Purchase Order',55.54))
    receipt=make_purchase_receipt(order.name)
    receipt.posting_date='2026-10-18';receipt.set_posting_time=1
    submit(receipt)
    invoices=[]
    for index in range(2):
        invoice=make_purchase_invoice(receipt.name)
        invoice.posting_date=invoice.bill_date='2026-10-18';invoice.bill_no=f'SYNTHETIC-FREIGHT-PARTIAL-BILL-{index}'
        for row in invoice.items:row.qty=1;row.set(DEDUCTION,60)
        for tax in invoice.taxes:
            if tax.charge_type=='Actual':tax.tax_amount=50
        submit(invoice)
        invoices.append(invoice)
    names=[receipt.name,*[doc.name for doc in invoices]]
    ledger(names,{accounts['1460']:1105,accounts['4500']:1105,accounts['6100']:100,
        accounts['2710']:315,accounts['2400']:-2624,company.round_off_account:-1,
        valuation.name:0,unbilled.name:0,accounts['4300']:0})
    stock_value([receipt.name],1105)
    returned_names=[]
    for invoice in invoices:
        returned=make_return_doc('Purchase Receipt',receipt.name)
        returned.posting_date='2026-10-19';returned.set_posting_time=1
        for row in returned.items:
            row.qty=row.received_qty=-1
            row.purchase_invoice=invoice.name
        for tax in returned.taxes:
            if tax.charge_type=='Actual':tax.tax_amount=-50
        submit(returned)
        credit=make_return_doc('Purchase Invoice',invoice.name)
        credit.posting_date=credit.bill_date='2026-10-19';credit.bill_no='SYNTHETIC-FREIGHT-PARTIAL-BILL-CREDIT'
        submit(credit)
        names.extend([returned.name,credit.name])
        returned_names.append(returned.name)
    state(names,0,0,0,0,0)
    stock_value([receipt.name,*returned_names],0)
    reset()
    print('PASS two partial freight bills absorb receipt rounding, explicit partial returns/credits clear GL and native rounding')

    receipt=make_purchase_receipt(submit(mixed('Purchase Order')).name)
    receipt.posting_date='2026-10-18';receipt.set_posting_time=1
    submit(receipt)
    receipt.cancel()
    state([receipt.name],0,0,0,0,0)
    stock_value([receipt.name],0)
    reset()
    print('PASS native receipt cancellation reverses only its marked automatic allocation')
    doc=mixed()
    doc.append('taxes',{'charge_type':'On Net Total','account_head':valuation.name,
        'rate':0,'set_by_item_tax_template':1,'description':'Synthetic separate native valuation',
        'category':'Valuation and Total','add_deduct_tax':'Add','cost_center':company.cost_center})
    submit(doc)
    state([doc.name],1205,1105,315,payable=-2725)
    stock_value([doc.name],1205)
    reset()
    print('PASS separate native valuation row is capitalized once; automatic LCV includes only tagged Total VAT amounts')

    invalid=draft(qty=1)
    invalid.items[0].rate=1250
    second=item(60,qty=1)
    second['item_tax_template']='MVA 15 % – varelinjer - VVM'
    invalid.append('items',second)
    for code,rate,included in [('2710',25,1),('2711',15,0)]:
        invalid.append('taxes',{'charge_type':'On Net Total','account_head':accounts[code],
            'rate':rate,'included_in_print_rate':included,'description':'Synthetic mixed inclusion',
            'category':'Total','add_deduct_tax':'Add','cost_center':company.cost_center})
    try:
        invalid.insert()
    except frappe.ValidationError as error:
        assert 'VAT inclusion must match' in str(error),str(error)
    else:
        raise AssertionError('One VAT cost row accepted conflicting inclusion settings')
    reset()
    print('PASS conflicting inclusion on a shared cost account/basis is rejected rather than letting the last line change all prices')

    invalid=mixed()
    invalid.insert()
    invalid.taxes[1].charge_type='On Net Total'
    invalid.taxes[1].row_id=None
    try:
        invalid.save()
    except frappe.ValidationError as error:
        assert 'Keep matching native VAT bases' in str(error),str(error)
    else:
        raise AssertionError('An orphaned automatic VAT cost basis was retained')
    reset()
    print('PASS changed native freight basis cannot retain an orphaned automatic valuation charge')

    receipt=make_purchase_receipt(submit(mixed('Purchase Order')).name)
    receipt.posting_date='2026-10-18';receipt.set_posting_time=1
    submit(receipt)
    own=frappe.db.get_value('Landed Cost Purchase Receipt',{'receipt_document':receipt.name},'parent')
    manual=frappe.get_doc({'doctype':'Landed Cost Voucher','company':company.name,'posting_date':'2026-10-18',
        'distribute_charges_based_on':'Distribute Manually',
        'purchase_receipts':[{'receipt_document_type':'Purchase Receipt','receipt_document':receipt.name}],
        'taxes':[{'expense_account':accounts['6100'],'description':'Synthetic manual cost','amount':10}]})
    manual.get_items_from_purchase_receipts()
    for row in manual.items:row.applicable_charges=10
    manual.insert();manual.submit()
    receipt.reload()
    frappe.db.savepoint('before_manual_cancel')
    try:
        receipt.cancel()
    except frappe.ValidationError:
        frappe.db.rollback(save_point='before_manual_cancel')
    else:
        raise AssertionError('A linked manual landed cost voucher did not block native receipt cancellation')
    assert frappe.db.get_value('Landed Cost Voucher',manual.name,'docstatus')==1
    assert frappe.db.get_value('Landed Cost Voucher',own,'docstatus')==1
    manual.reload();manual.cancel()
    receipt.reload();receipt.cancel()
    state([receipt.name],0,0,0,0,0)
    reset()
    print('PASS manual native allocation is preserved; failed cancellation rolls back automatic allocation and core remains authoritative')

    if len(sys.argv)>1 and sys.argv[1]=='seed':
        order=submit(mixed('Purchase Order',100))
        receipt=make_purchase_receipt(order.name)
        receipt.posting_date='2026-10-18';receipt.set_posting_time=1
        submit(receipt)
        invoice=make_purchase_invoice(receipt.name)
        invoice.posting_date=invoice.bill_date='2026-10-18';invoice.bill_no='SYNTHETIC-FREIGHT-RESTORE'
        for row in invoice.items:row.set(DEDUCTION,60)
        submit(invoice)
        state([receipt.name,invoice.name],1105,1105,315)
        file_name=frappe.db.get_value('File',{'attached_to_doctype':'Purchase Invoice',
            'attached_to_name':invoice.name,'is_private':1},'name')
        original=frappe.get_doc('File',file_name)
        evidence={'receipt':receipt.name,'invoice':invoice.name,
            'allocation':frappe.db.get_value('Landed Cost Voucher',{SOURCE:invoice.name,'docstatus':1},'name'),
            'file':file_name,'sha256':hashlib.sha256(Path(original.get_full_path()).read_bytes()).hexdigest()}
        frappe.db.set_default('runtime_vat_freight_evidence',json.dumps(evidence))
        frappe.db.commit()
        print('PASS synthetic freight chain evidence committed for browser and exported restore')
finally:
    frappe.db.rollback();frappe.clear_cache();frappe.destroy()
