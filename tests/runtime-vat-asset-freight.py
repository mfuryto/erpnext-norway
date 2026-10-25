"""Native Asset/LCV VAT on freight: direct, receipt, return and manual creation."""
import os,sys,json,hashlib
from pathlib import Path
import frappe
from frappe.utils import flt
from frappe.utils.file_manager import save_file
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway.vat_catalog import CODE,DEDUCTION
from erpnext_norway.vat_valuation import SOURCE
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from erpnext_norway.vat_evidence import preserve_basis
C='Runtime Asset Freight';OWNER='runtime-vat-owner@example.invalid'
def gl():return sorted((r.account,float(r.debit),float(r.credit),r.voucher_type,r.voucher_no) for r in frappe.get_all('GL Entry',filters={'company':C,'is_cancelled':0},fields=['account','debit','credit','voucher_type','voucher_no']))
if sys.argv[1]=='verify':
    try:
        e=json.loads(frappe.db.get_default('runtime_asset_freight_evidence'))
        assert gl()==[tuple(r) for r in e['ledger']]
        for entry in e['documents']:
            doc=frappe.get_doc(entry['doctype'],entry['name']);assert doc.docstatus==entry['status']
            if doc.doctype=='Purchase Invoice':assert doc.grand_total==entry['total']
        for entry in e['assets']:assert frappe.db.get_value('Asset',entry['name'],'net_purchase_amount')==entry['value']
        for entry in e['files']:assert hashlib.sha256(Path(frappe.get_doc('File',entry['name']).get_full_path()).read_bytes()).hexdigest()==entry['sha256']
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        rows=collect({'company':C,'from_date':'2026-10-15','to_date':'2026-10-31'})
        assert round(sum(r['input_vat'] for r in rows),2)==157.5 and not sum(r['output_vat'] for r in rows)
        print('PASS restored native asset552.50, source/partial-credit/+105/-52.50 LCV links,157.50 inputVAT, ledger and private originals/basis')
    finally:frappe.destroy()
    raise SystemExit(0)
try:
    from erpnext_norway import vat
    company = frappe.get_doc({'doctype': 'Company', 'company_name': 'Runtime Asset Freight',
        'abbr': 'AVF', 'country': 'Norway', 'default_currency': 'NOK', 'tax_id': '999999993',
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
    stock = frappe.get_doc({'doctype': 'Item', 'item_code': 'SYNTHETIC-VAT-STOCK-AVF',
        'item_name': 'Synthetic stock VAT', 'item_group': 'Products', 'stock_uom': 'Nos',
        'is_stock_item': 1, 'item_defaults': [{'company': company.name,
            'expense_account': accounts['4300'], 'default_warehouse': 'Stores - AVF'}]}).insert()
    category = frappe.get_doc({'doctype': 'Asset Category',
        'asset_category_name': 'Synthetic VAT equipment asset freight',
        'accounts': [{'company_name': company.name, 'fixed_asset_account': accounts['1250']}]}).insert()
    location = frappe.get_doc({'doctype': 'Location', 'location_name': 'Synthetic VAT location asset freight'}).insert()
    asset = frappe.get_doc({'doctype': 'Item', 'item_code': 'SYNTHETIC-VAT-ASSET-AVF',
        'item_name': 'Synthetic VAT asset', 'item_group': 'Products', 'stock_uom': 'Nos',
        'is_stock_item': 0, 'is_fixed_asset': 1, 'auto_create_assets': 1,
        'asset_category': category.name, 'asset_naming_series': 'ACC-ASS-.YYYY.-',
        'item_defaults': [{'company': company.name, 'expense_account': accounts['1250']}]}).insert()
    supplier = frappe.get_all('Supplier', pluck='name')[0]
    frappe.get_doc('User','runtime-vat-owner@example.invalid').add_roles('Accounts User')
    frappe.set_user('runtime-vat-owner@example.invalid')

    def item(percent, code=stock.name, qty=2):
        return {'item_code': code, 'qty': qty, 'rate': 1000 / qty,
            'warehouse': 'Stores - AVF', 'expense_account': accounts['1250'] if code == asset.name else accounts['4300'],
            'cost_center': company.cost_center, 'item_tax_template': 'MVA 25 % – varelinjer - AVF',
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

    def mixed_asset(kind='Purchase Invoice',percent=60,qty=2):
        doc=draft(kind,percent,code=asset.name,qty=qty);doc.disable_rounded_total=1
        doc.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':qty,'rate':1000/qty,
            'expense_account':accounts['4500'],'cost_center':company.cost_center,
            'item_tax_template':'MVA 25 % – varelinjer - AVF',DEDUCTION:percent})
        doc.append('taxes',{'charge_type':'Actual','account_head':accounts['6100'],'tax_amount':100,
            'description':'Synthetic freight','category':'Total','add_deduct_tax':'Add','cost_center':company.cost_center})
        doc.append('taxes',{'charge_type':'On Previous Row Total','row_id':'1','account_head':accounts['2710'],'rate':25,
            'description':'Synthetic VAT','category':'Total','add_deduct_tax':'Add','cost_center':company.cost_center})
        return doc
    def assets_for(doc):
        field='purchase_invoice' if doc.doctype=='Purchase Invoice' else 'purchase_receipt'
        return frappe.get_list('Asset',filters={field:doc.name,'docstatus':0},fields=['name','net_purchase_amount'])
    def remove_assets(doc,qty):
        for row in assets_for(doc)[:qty]:frappe.delete_doc('Asset',row.name)
    def values(names,ratio=1,percent=60):
        cost=1000+262.5*(100-percent)/100
        ledger(names,{accounts['1250']:cost*ratio,accounts['4500']:cost*ratio,accounts['6100']:100*ratio,
            accounts['2710']:525*percent/100*ratio,accounts['2400']:-2625*ratio,
            valuation.name:0,unbilled.name:0,asset_unbilled.name:0,company.round_off_account:0})
    frappe.db.savepoint('valuation_case')
    # Native direct full and partial return, then ordinary credit cancellation.
    for returned_qty in (2,1):
        doc=submit(mixed_asset());values([doc.name])
        assert [r.net_purchase_amount for r in assets_for(doc)]==[552.5,552.5]
        positive=frappe.get_doc('Landed Cost Voucher',frappe.db.get_value('Landed Cost Voucher',{SOURCE:doc.name,'docstatus':1}))
        remove_assets(doc,returned_qty)
        credit=make_return_doc('Purchase Invoice',doc.name);credit.posting_date=credit.bill_date='2026-10-19';credit.bill_no='SYNTHETIC-ASSET-FREIGHT-CREDIT'
        for row in credit.items:row.qty=row.received_qty=-returned_qty
        credit.taxes[0].tax_amount=-100*returned_qty/2;submit(credit)
        values([doc.name,credit.name],1-returned_qty/2)
        negative=frappe.get_doc('Landed Cost Voucher',frappe.db.get_value('Landed Cost Voucher',{SOURCE:credit.name,'docstatus':1}))
        assert negative.total_taxes_and_charges==-105*returned_qty/2 and positive.reload().docstatus==1
        credit.cancel();assert negative.reload().docstatus==2 and positive.reload().docstatus==1
        values([doc.name,credit.name]);reset()
    print('PASS native 60% line choice auto-LCV: full/half asset+service+freight return, ordinary Asset lifecycle and credit cancellation; original LCV retained')
    # Native manual LCVs and submitted Assets keep their ordinary controls.
    doc=submit(mixed_asset());own=frappe.db.get_value('Landed Cost Voucher',{SOURCE:doc.name,'docstatus':1})
    manual_lcv=frappe.get_doc({'doctype':'Landed Cost Voucher','company':C,'posting_date':doc.posting_date,
        'distribute_charges_based_on':'Distribute Manually',
        'purchase_receipts':[{'receipt_document_type':'Purchase Invoice','receipt_document':doc.name}],
        'taxes':[{'expense_account':accounts['6100'],'description':'Synthetic manual native cost','amount':10}]})
    manual_lcv.get_items_from_purchase_receipts()
    for row in manual_lcv.items:row.applicable_charges=10
    manual_lcv.insert();manual_lcv.submit();doc.reload()
    frappe.db.savepoint('manual_asset_lcv')
    from erpnext_norway.vat_valuation import cancel_adjustments
    cancel_adjustments(doc)
    assert frappe.db.get_value('Landed Cost Voucher',own,'docstatus')==2
    assert manual_lcv.reload().docstatus==1
    frappe.db.rollback(save_point='manual_asset_lcv')
    assert frappe.db.get_value('Landed Cost Voucher',own,'docstatus')==1
    assert manual_lcv.reload().docstatus==1
    manual_lcv.cancel();values([doc.name]);reset()
    doc=submit(mixed_asset());record=frappe.get_doc('Asset',assets_for(doc)[0].name)
    record.available_for_use_date=doc.posting_date;record.save();record.submit()
    invalid=frappe.get_doc({'doctype':'Landed Cost Voucher','company':C,'posting_date':doc.posting_date,
        'custom_norway_vat_allocation':1,SOURCE:doc.name,'distribute_charges_based_on':'Distribute Manually',
        'purchase_receipts':[{'receipt_document_type':'Purchase Invoice','receipt_document':doc.name}],
        'taxes':[{'expense_account':valuation.name,'description':'Synthetic submitted-Asset validation','amount':10}]})
    invalid.get_items_from_purchase_receipts()
    for row in invalid.items:row.applicable_charges=10
    try:invalid.insert();invalid.submit()
    except frappe.ValidationError as error:assert 'submitted Assets' in str(error),str(error)
    else:raise AssertionError('Submitted Asset core guard was bypassed')
    reset()
    print('PASS app cancels only its own LCV, preserves manual allocation; native submitted-Asset validation remains authoritative')
    # Normal purchase order/receipt/invoice chain, including changed deduction.
    for received,billed in ((60,60),(100,60),(60,100),(60,30)):
        order=submit(mixed_asset('Purchase Order',received,qty=1))
        receipt=make_purchase_receipt(order.name);receipt.posting_date='2026-10-18';receipt.set_posting_time=1;receipt.items[0].asset_location=location.name;submit(receipt)
        invoice=make_purchase_invoice(receipt.name);invoice.posting_date=invoice.bill_date='2026-10-18';invoice.bill_no='SYNTHETIC-ASSET-FREIGHT-CHAIN'
        for row in invoice.items:
            row.set(DEDUCTION,billed)
            if billed==100:row.item_tax_template='MVA 25 % – varelinjer - AVF'
        submit(invoice);values([receipt.name,invoice.name],percent=billed)
        records=assets_for(receipt);assert len(records)==1 and records[0].net_purchase_amount==1000+262.5*(100-billed)/100,(received,billed,records)
        remove_assets(receipt,1)
        returned=make_return_doc('Purchase Receipt',receipt.name);returned.posting_date='2026-10-19';returned.set_posting_time=1;submit(returned)
        credit=make_return_doc('Purchase Invoice',invoice.name);credit.posting_date=credit.bill_date='2026-10-19';credit.bill_no='SYNTHETIC-ASSET-FREIGHT-CHAIN-CREDIT';submit(credit)
        values([receipt.name,invoice.name,returned.name,credit.name],0,percent=billed);reset()
    print('PASS native Asset purchase/receipt/invoice freight 60->60,100->60,60->100,60->30 and submitted receipt-return/credit clear all GL')
    # Preserve manual Asset creation, and use the resulting native source value.
    frappe.set_user('Administrator');manual_item=frappe.get_doc('Item',asset.name);manual_item.auto_create_assets=0;manual_item.save();frappe.set_user(OWNER)
    doc=submit(mixed_asset());values([doc.name]);assert not assets_for(doc)
    manual=frappe.get_doc({'doctype':'Asset','company':C,'item_code':asset.name,'asset_name':'Synthetic manual asset',
        'asset_category':category.name,'location':location.name,'naming_series':'ACC-ASS-.YYYY.-','asset_quantity':1,'calculate_depreciation':0,
        'purchase_date':doc.posting_date,'purchase_invoice':doc.name,'purchase_invoice_item':doc.items[0].name,
        'purchase_amount':doc.items[0].valuation_rate,'net_purchase_amount':doc.items[0].valuation_rate}).insert()
    assert manual.net_purchase_amount==552.5 and frappe.db.get_value('Item',asset.name,'auto_create_assets')==0
    values([doc.name]);reset();frappe.set_user(OWNER)
    print('PASS explicit manual Asset creation retained; native form uses552.50 source valuation without ignore flags or duplicate GL')
    # Existing NOK reverse-charge templates also work for capitalized services.
    for percent,cost,input_ in ((100,1000,250),(60,1100,150),(0,1250,0)):
        doc=draft(percent=percent,code=asset.name,qty=2);doc.disable_rounded_total=1
        doc.items[0].item_tax_template='Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag - AVF'
        submit(doc)
        assert doc.grand_total==1000 and doc.items[0].get(CODE)==('86' if percent else '87')
        ledger([doc.name],{accounts['1250']:cost,accounts['2704']:-250,accounts['2714']:input_,accounts['2400']:-1000,valuation.name:0})
        records=assets_for(doc);assert len(records)==2 and all(r.net_purchase_amount==cost/2 for r in records)
        remove_assets(doc,1)
        credit=make_return_doc('Purchase Invoice',doc.name);credit.posting_date=credit.bill_date='2026-10-19';credit.bill_no='SYNTHETIC-CAPITALIZED-SERVICE-CREDIT'
        credit.items[0].qty=credit.items[0].received_qty=-1;submit(credit)
        ledger([doc.name,credit.name],{accounts['1250']:cost/2,accounts['2704']:-125,accounts['2714']:input_/2,accounts['2400']:-500,valuation.name:0})
        rows=[r for r in collect({'company':C,'from_date':'2026-10-15','to_date':'2026-10-31'}) if r['voucher'] in (doc.name,credit.name)]
        assert sum(r['output_vat'] for r in rows)==125 and sum(r['input_vat'] for r in rows)==input_/2
        reset()
    print('PASS ordinary NOK capitalized remote service100/60/0% deduction: native Asset1000/1100/1250, output250/input250/150/0, halfcredit, GL/report')
    # Persist a genuine received-asset chain and partial return for UI/restore.
    order=submit(mixed_asset('Purchase Order'))
    receipt=make_purchase_receipt(order.name);receipt.posting_date='2026-10-18';receipt.set_posting_time=1;receipt.items[0].asset_location=location.name;submit(receipt)
    invoice=make_purchase_invoice(receipt.name);invoice.posting_date=invoice.bill_date='2026-10-18';invoice.bill_no='SYNTHETIC-ASSET-FREIGHT-RESTORE';invoice.disable_rounded_total=1;submit(invoice)
    remove_assets(receipt,1)
    returned=make_return_doc('Purchase Receipt',receipt.name);returned.posting_date='2026-10-19';returned.set_posting_time=1
    for row in returned.items:row.qty=row.received_qty=-1
    returned.taxes[0].tax_amount=-50;submit(returned)
    credit=make_return_doc('Purchase Invoice',invoice.name);credit.posting_date=credit.bill_date='2026-10-19';credit.bill_no='SYNTHETIC-ASSET-FREIGHT-RESTORE-CREDIT'
    for row in credit.items:row.qty=row.received_qty=-1
    credit.taxes[0].tax_amount=-50;submit(credit);values([receipt.name,invoice.name,returned.name,credit.name],.5)
    e={'documents':[],'assets':[],'files':[],'ledger':gl()}
    seen=set()
    for source in (order,receipt,invoice,returned,credit):
        source.reload();e['documents'].append({'doctype':source.doctype,'name':source.name,'status':1,'total':source.grand_total})
        for lcv in frappe.get_all('Landed Cost Purchase Receipt',filters={'receipt_document':source.name,'docstatus':1},pluck='parent'):
            if lcv not in seen:e['documents'].append({'doctype':'Landed Cost Voucher','name':lcv,'status':1});seen.add(lcv)
        for name in frappe.get_all('File',filters={'attached_to_doctype':source.doctype,'attached_to_name':source.name,'is_private':1},pluck='name'):
            file=frappe.get_doc('File',name);e['files'].append({'name':name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
    for record in assets_for(receipt):e['assets'].append({'name':record.name,'value':record.net_purchase_amount})
    file=frappe.get_doc('File',preserve_basis(company=C,from_date='2026-10-15',to_date='2026-10-31')['name'])
    e['files'].append({'name':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
    frappe.db.set_default('runtime_asset_freight_evidence',json.dumps(e));frappe.db.commit()
    print('PASS native asset freight source, partial credit, positive/negative LCV, remaining Asset and private originals/basis committed')
finally:frappe.db.rollback();frappe.clear_cache();frappe.destroy()
