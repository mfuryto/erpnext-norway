"""Reuse native taxable bases, valuation, LCV, credit notes and Asset records."""
import os
import frappe
from frappe.utils import flt
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.conf.host_name = 'http://frontend:8080'
from erpnext_norway.vat_catalog import DEDUCTION
from erpnext_norway.vat_currency import DATE, EXCHANGE
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
C = 'Runtime Asset Freight'
OWNER = 'runtime-vat-owner@example.invalid'
try:
    frappe.set_user('Administrator')
    company = frappe.get_doc('Company', C)
    accounts = {r.account_number: r.name for r in frappe.get_all('Account',
        filters={'company': C}, fields=['name', 'account_number']) if r.account_number}
    payable = frappe.get_doc({'doctype': 'Account', 'company': C,
        'account_name': 'Synthetic capitalized currency payable', 'account_type': 'Payable',
        'account_currency': 'EUR', 'parent_account': frappe.db.get_value('Account', accounts['2400'], 'parent_account')}).insert()
    supplier = frappe.get_doc({'doctype': 'Supplier', 'supplier_name': 'Synthetic capitalized currency supplier',
        'supplier_type': 'Company', 'supplier_group': frappe.get_all('Supplier Group', filters={'is_group':0}, pluck='name')[0],
        'default_currency': 'EUR', 'accounts': [{'company': C, 'account': payable.name}]}).insert()
    accounts['2400'] = payable.name
    asset = 'SYNTHETIC-VAT-ASSET-AVF'
    location = frappe.db.get_value('Location', {'location_name': 'Synthetic VAT location asset freight'})
    frappe.db.commit()  # Synthetic EUR supplier/account remain for the ordinary browser test.
    frappe.set_user(OWNER)
    assert 'System Manager' not in frappe.get_roles()

    def ledger(names, expected):
        rows = frappe.get_all('GL Entry', filters={'company':C, 'voucher_no':['in', names], 'is_cancelled':0}, fields=['account','debit','credit'])
        actual = {number: flt(sum(r.debit-r.credit for r in rows if r.account == accounts[number]), 2) for number in expected}
        assert actual == expected, actual
        assert flt(sum(r.debit-r.credit for r in rows),2) == 0

    def invoice(rate, percent, mixed=False):
        output, input_ = ('2704','2714') if rate == 25 else ('2709','2718')
        template = frappe.db.get_value('Item Tax Template', {'company':C, 'title':f'Tjenestekjøp fra utlandet – MVA {rate} % – 100 % fradrag'})
        doc = frappe.get_doc({'doctype':'Purchase Invoice', 'company':C, 'supplier':supplier.name, 'credit_to':payable.name,
            'posting_date':'2026-10-18', 'set_posting_time':1, 'bill_date':'2026-10-18',
            'bill_no':'SYNTHETIC-CAPITALIZED-CURRENCY', 'due_date':'2026-10-31', 'currency':'EUR',
            'conversion_rate':10, 'update_stock':1, 'disable_rounded_total':1,
            'items':[{'item_code':asset, 'qty':2, 'rate':50, 'expense_account':accounts['1250'],
                'cost_center':company.cost_center, 'asset_location':location, 'asset_naming_series':'ACC-ASS-.YYYY.-',
                'item_tax_template':template, DEDUCTION:percent, DATE:'2026-10-17', EXCHANGE:11}]})
        if mixed:
            doc.append('items', {'item_code':'RUNTIME-VAT-SERVICE', 'qty':2, 'rate':50, 'expense_account':accounts['4500'],
                'cost_center':company.cost_center, 'item_tax_template':template, DEDUCTION:percent, DATE:'2026-10-17', EXCHANGE:13})
            doc.append('taxes', {'charge_type':'Actual','account_head':accounts['6100'],'tax_amount':10,
                'category':'Total','add_deduct_tax':'Add','description':'Synthetic native fee','cost_center':company.cost_center})
            for number, direction in ((output,'Deduct'),(input_,'Add')):
                doc.append('taxes', {'charge_type':'On Previous Row Total','row_id':'1','account_head':accounts[number],
                    'rate':rate,'category':'Total','add_deduct_tax':direction,'description':'Native fee basis','cost_center':company.cost_center})
        doc.insert(); doc.submit()
        return doc

    for rate, cases in ((25, ((100,1000,275),(60,1110,165),(0,1275,0))),
                        (12, ((100,1000,132),(60,1052.8,79.2),(0,1132,0)))):
        output, input_ = ('2704','2714') if rate == 25 else ('2709','2718')
        vat = 275 if rate == 25 else 132
        for percent, cost, deduction in cases:
            frappe.db.savepoint('native_asset_currency')
            doc = invoice(rate, percent)
            assert doc.grand_total == 100 and doc.base_grand_total == 1000
            expected = {'1250':cost,output:-vat,input_:deduction,'2400':-1000,'4998':0}
            ledger([doc.name], expected)
            records = frappe.get_list('Asset', filters={'purchase_invoice':doc.name}, fields=['name','net_purchase_amount'])
            assert len(records)==2 and all(r.net_purchase_amount == cost/2 for r in records), records
            frappe.delete_doc('Asset', records[0].name)
            credit = make_return_doc('Purchase Invoice', doc.name)
            credit.posting_date = credit.bill_date = '2026-10-19'
            credit.set_posting_time = 1; credit.bill_no = 'SYNTHETIC-CAPITALIZED-CURRENCY-CREDIT'
            credit.items[0].qty = credit.items[0].received_qty = -1
            credit.items[0].set(EXCHANGE,99)
            credit.insert(); credit.submit()
            assert credit.grand_total == -50 and credit.items[0].get(EXCHANGE)==11
            ledger([doc.name,credit.name], {k:flt(v/2,2) for k,v in expected.items()})
            rows = [r for r in collect({'company':C,'from_date':'2026-10-15','to_date':'2026-10-31'}) if r['voucher'] in (doc.name,credit.name)]
            assert sum(r['output_vat'] for r in rows) == vat/2 and sum(r['input_vat'] for r in rows) == deduction/2
            frappe.db.rollback(save_point='native_asset_currency'); frappe.clear_cache()
    print('PASS native registered EUR Asset25/12%, deduction100/60/0, supplier100EUR/book1000NOK, delivery11 basis1100; halfcredits retain issued FX, Asset/GL/report', flush=True)

    frappe.db.savepoint('mixed_asset_currency')
    doc = invoice(25,60,mixed=True)
    assert doc.grand_total == 210 and doc.base_grand_total == 2100
    expected = {'1250':1115.5,'4500':1136.5,'6100':100,'2704':-630,'2714':378,'2400':-2100,'4998':0}
    ledger([doc.name],expected)
    records = frappe.get_list('Asset', filters={'purchase_invoice':doc.name}, fields=['name','net_purchase_amount'])
    assert len(records)==2 and all(r.net_purchase_amount == 557.75 for r in records)
    frappe.delete_doc('Asset',records[0].name)
    credit = make_return_doc('Purchase Invoice',doc.name)
    credit.posting_date = credit.bill_date = '2026-10-19'
    credit.set_posting_time=1; credit.bill_no='SYNTHETIC-MIXED-CURRENCY-CREDIT'
    for row in credit.items: row.qty=row.received_qty=-1
    credit.taxes[0].tax_amount=-5
    credit.insert(); credit.submit()
    assert credit.grand_total==-105
    ledger([doc.name,credit.name],{k:v/2 for k,v in expected.items()})
    rows=[r for r in collect({'company':C,'from_date':'2026-10-15','to_date':'2026-10-31'}) if r['voucher'] in (doc.name,credit.name)]
    assert sum(r['output_vat'] for r in rows)==315 and sum(r['input_vat'] for r in rows)==189
    credit.cancel()
    ledger([doc.name],expected)
    frappe.db.rollback(save_point='mixed_asset_currency')
    print('PASS native mixed EUR Asset/service delivery11/13+fee10: Asset1115.50/service1136.50/fee100/input378/output630/vendor2100; halfcredit, negativeLCV and cancellation', flush=True)
finally:
    frappe.db.rollback(); frappe.clear_cache(); frappe.destroy()
