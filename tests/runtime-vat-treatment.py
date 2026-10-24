"""Native mixed-rate invoices and per-line deduction; synthetic runtime only."""
import os, sys, types, json
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites')
frappe.connect(); frappe.set_user('Administrator')
frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat_catalog as module
from erpnext_norway import vat
from pathlib import Path
import hashlib
try:
    company=frappe.get_doc('Company','Runtime VAT Example')
    accounts={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':company.name},fields=['name','account_number']) if r.account_number}
    frappe.set_user('runtime-vat-owner@example.invalid')
    original=frappe.get_doc('Sales Invoice',{'company':company.name,'docstatus':1,'is_return':0,'total_taxes_and_charges':250})
    doc=frappe.copy_doc(original)
    doc.posting_date='2026-10-16'; doc.due_date='2026-10-31'; doc.set_posting_time=1
    doc.set('items',[]); doc.set('taxes',[])
    for rate, output, input_, sale_code, purchase_code in module.ORDINARY:
        doc.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
            'income_account':accounts['3020'],'cost_center':company.cost_center,
            'item_tax_template':f'MVA {rate} % – varelinjer - RVE'})

    doc.tax_category=None; doc.taxes_and_charges=None
    doc.insert(); doc.submit()
    assert float(doc.net_total)==3000
    assert float(doc.total_taxes_and_charges)==520,doc.as_dict()
    assert [r.get(module.CODE) for r in doc.items]==['3','31','33']
    rows=frappe.get_all('GL Entry',filters={'voucher_no':doc.name,'company':company.name,'is_cancelled':0},fields=['account','debit','credit'])
    for code,amount in [('2700',250),('2701',150),('2703',120)]:
        assert round(sum(r.credit-r.debit for r in rows if r.account==accounts[code]),2)==amount
    print('PASS native mixed 25/15/12 percent invoice, Norwegian codes per line, output accounts and balanced native ledger')
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
    credit=make_sales_return(doc.name)
    credit.posting_date='2026-10-17';credit.set_posting_time=1
    credit.update_outstanding_for_self=0
    credit.insert();credit.submit()
    assert float(credit.total_taxes_and_charges)==-520
    assert [r.get(module.CODE) for r in credit.items]==['3','31','33']
    discounted=frappe.copy_doc(doc)
    discounted.apply_discount_on='Net Total';discounted.additional_discount_percentage=10
    discounted.insert();discounted.submit()
    assert float(discounted.net_total)==2700
    assert float(discounted.total_taxes_and_charges)==468
    assert float(discounted.grand_total)==3168
    print('PASS native mixed-rate credit note and 10 percent net discount preserve per-line VAT treatment')
    exempt=frappe.copy_doc(doc);exempt.set('items',[])
    for title in ('Fritatt MVA – nullsats','Unntatt MVA','Uten MVA-behandling','Eksport – fritatt MVA'):
        exempt.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
            'income_account':accounts['3020'],'cost_center':company.cost_center,
            'item_tax_template':f'{title} - RVE'})
    exempt.insert();exempt.submit()
    assert float(exempt.grand_total)==4000 and float(exempt.total_taxes_and_charges)==0
    assert [r.get(module.CODE) for r in exempt.items]==['5','6','7','52']
    print('PASS distinct zero-rated, exempt, outside-VAT and export line classifications override native taxable header rows')
    purchase=frappe.copy_doc(frappe.get_doc('Purchase Invoice',{'company':company.name,'docstatus':1,'is_return':0,'total_taxes_and_charges':100}))
    purchase.posting_date='2026-10-16'; purchase.bill_date='2026-10-16'; purchase.due_date='2026-10-31'; purchase.bill_no='SYNTHETIC-MIXED-DEDUCTION'
    purchase.set('items',[]); purchase.set('taxes',[])
    for expense,percent in [('4500',60),('6540',0)]:
        purchase.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
            'expense_account':accounts[expense],'cost_center':company.cost_center,
            'item_tax_template':'MVA 25 % – varelinjer - RVE',module.DEDUCTION:percent})
    purchase.append('taxes',{'charge_type':'On Net Total','account_head':accounts['2710'],
        'rate':25,'description':'MVA 25 %','cost_center':company.cost_center,
        'category':'Total','add_deduct_tax':'Add'})
    purchase.insert()
    from frappe.utils.file_manager import save_file
    save_file('synthetic-mixed-purchase.pdf',frappe.get_print(purchase.doctype,purchase.name,as_pdf=True),purchase.doctype,purchase.name,is_private=1)
    purchase.submit()
    assert float(purchase.grand_total)==2500,purchase.grand_total
    ledger=frappe.get_all('GL Entry',filters={'voucher_no':purchase.name,'company':company.name,'is_cancelled':0},fields=['account','debit','credit'])
    for account,expected in [('4500',1100),('6540',1250),('2710',150),('2400',-2500)]:
        actual=round(sum(r.debit-r.credit for r in ledger if r.account==accounts[account]),2)
        assert actual==expected,(account,actual,expected)
    assert [r.get(module.CODE) for r in purchase.items]==['1','0']
    print('PASS native 60/0 percent deduction in one purchase; 150 input VAT, 2350 cost, 2500 payable')
    selected=frappe.copy_doc(purchase);selected.bill_no='SYNTHETIC-SAVED-PARTIAL-TEMPLATE'
    selected.set('items',[]);selected.set('taxes',[])
    selected.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
        'expense_account':accounts['4500'],'cost_center':company.cost_center,
        'item_tax_template':purchase.items[0].item_tax_template})
    selected.insert()
    assert float(selected.items[0].get(module.DEDUCTION))==60
    assert float(selected.total_taxes_and_charges)==250
    assert float(next(tax for tax in selected.taxes if tax.account_head==accounts['2710']).tax_amount)==150
    print('PASS selected saved partial template retains 60 percent deduction instead of the new-row default 100')
    from erpnext.controllers.sales_and_purchase_return import make_return_doc
    purchase_credit=make_return_doc('Purchase Invoice',purchase.name)
    purchase_credit.posting_date='2026-10-17';purchase_credit.bill_date='2026-10-17'
    purchase_credit.bill_no='SYNTHETIC-PARTIAL-DEDUCTION-CREDIT'
    purchase_credit.update_outstanding_for_self=0
    purchase_credit.insert()
    save_file('synthetic-partial-credit.pdf',frappe.get_print(purchase_credit.doctype,
        purchase_credit.name,as_pdf=True),purchase_credit.doctype,purchase_credit.name,is_private=1)
    purchase_credit.submit()
    assert float(purchase_credit.grand_total)==-2500
    assert [r.get(module.CODE) for r in purchase_credit.items]==['1','0']
    ledger=frappe.get_all('GL Entry',filters={'voucher_no':purchase_credit.name,'company':company.name,
        'is_cancelled':0},fields=['account','debit','credit'])
    for account,expected in [('4500',-1100),('6540',-1250),('2710',-150),('2400',2500)]:
        actual=round(sum(r.debit-r.credit for r in ledger if r.account==accounts[account]),2)
        assert actual==expected,(account,actual,expected)
    print('PASS native purchase credit reverses both deductible VAT and non-deductible costs')

    # The native chart's COGS type must survive partial deduction. Both the
    # template validator and invoice ledger use the actual installed extension.
    cogs_type=frappe.db.get_value('Account',accounts['4300'],'account_type')
    assert cogs_type=='Cost of Goods Sold'
    cogs=frappe.copy_doc(purchase)
    cogs.bill_no='SYNTHETIC-COGS-DEDUCTION'
    cogs.set('items',[]); cogs.set('taxes',[])
    cogs.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
        'expense_account':accounts['4300'],'cost_center':company.cost_center,
        'item_tax_template':'MVA 25 % – varelinjer - RVE',module.DEDUCTION:60})
    cogs.insert()
    save_file('synthetic-cogs-purchase.pdf',frappe.get_print(cogs.doctype,cogs.name,as_pdf=True),
        cogs.doctype,cogs.name,is_private=1)
    cogs.submit()
    assert frappe.db.get_value('Account',accounts['4300'],'account_type')==cogs_type
    ledger=frappe.get_all('GL Entry',filters={'voucher_no':cogs.name,'company':company.name,
        'is_cancelled':0},fields=['account','debit','credit'])
    for account,expected in [('4300',1100),('2710',150),('2400',-1250)]:
        actual=round(sum(r.debit-r.credit for r in ledger if r.account==accounts[account]),2)
        assert actual==expected,(account,actual,expected)
    print('PASS partial deduction keeps native Cost of Goods Sold account type and posts 1100 cost / 150 input VAT')

    # A user's native opt-out must not be bypassed by the Norwegian adapter.
    # Explicit rows still work, including the VAT cost, so an omitted cost row
    # cannot silently reduce the amount owed to the supplier.
    frappe.db.savepoint('native_auto_tax_choice')
    frappe.set_user('Administrator')
    frappe.db.set_single_value('Accounts Settings','add_taxes_from_item_tax_template',0)
    frappe.clear_cache()
    frappe.set_user('runtime-vat-owner@example.invalid')
    for source, total in ((doc,3520),(purchase,2500)):
        explicit=frappe.copy_doc(source)
        explicit.insert(); explicit.submit()
        assert float(explicit.grand_total)==total
        missing=frappe.copy_doc(source); missing.set('taxes',[])
        try:
            module.prepare_items(missing)
        except frappe.ValidationError as error:
            assert 'Accounts Settings' in str(error)
        else:
            raise AssertionError('Native automatic-tax opt-out was bypassed')
        assert not missing.taxes
    frappe.db.rollback(save_point='native_auto_tax_choice')
    frappe.clear_cache()
    print('PASS native automatic-tax opt-out preserved; explicit mixed sales and partial-deduction purchase still post correct totals')

finally:
    frappe.db.rollback(); frappe.clear_cache(); frappe.destroy()
