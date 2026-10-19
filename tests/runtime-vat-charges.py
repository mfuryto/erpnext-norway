"""Native separate charge rows must retain VAT cost and report freight bases."""
import os
import frappe

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites')
frappe.connect();frappe.set_user('runtime-vat-owner@example.invalid')
frappe.conf.host_name='http://frontend:8080'
from erpnext_norway.vat_catalog import DEDUCTION
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from frappe.utils.file_manager import save_file

try:
    c=frappe.get_doc('Company','Runtime VAT Example')
    accounts={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':c.name},
        fields=['name','account_number']) if r.account_number}
    def charge(kind,account,amount=0,rate=0,**extra):
        return {'charge_type':kind,'account_head':accounts[account],'tax_amount':amount,'rate':rate,
            'description':'Synthetic separate charge','category':'Total','add_deduct_tax':'Add',
            'cost_center':c.cost_center,**extra}
    def draft(kind):
        source=frappe.get_doc(kind,{'company':c.name,'docstatus':1,'is_return':0,
            'total_taxes_and_charges':250 if kind=='Sales Invoice' else 100})
        d=frappe.copy_doc(source);d.posting_date='2026-10-18';d.due_date='2026-10-31'
        d.set_posting_time=1;d.set('items',[]);d.set('taxes',[])
        d.tax_category=None;d.taxes_and_charges=None
        d.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
            'income_account':accounts['3020'],'expense_account':accounts['4500'],
            'cost_center':c.cost_center,'item_tax_template':'MVA 25 % – varelinjer - RVE'})
        if kind=='Purchase Invoice':
            d.bill_date='2026-10-18';d.bill_no='SYNTHETIC-SEPARATE-CHARGE'
            d.items[0].set(DEDUCTION,60)
        return d
    sale=draft('Sales Invoice')
    sale.append('taxes',charge('Actual','3020',amount=100))
    sale.append('taxes',charge('On Previous Row Amount','2700',rate=25,row_id='1'))
    sale.insert();sale.submit()
    assert sale.grand_total==1375,sale.grand_total
    rows=[r for r in collect({'company':c.name,'from_date':'2026-10-18','to_date':'2026-10-18'})
        if r['voucher']==sale.name]
    assert len(rows)==1
    assert rows[0]['base_amount']==1100 and rows[0]['net_vat']==275,rows
    print('PASS native item VAT plus VAT on separate freight charge: 1100 report base / 275 VAT / 1375 receivable')
    header=draft('Sales Invoice')
    header.items[0].item_tax_template=None;header.tax_category='Norge MVA 25 %'
    header.append('taxes',charge('On Net Total','2700',rate=25))
    header.insert();header.submit()
    rows=[r for r in collect({'company':c.name,'from_date':'2026-10-18','to_date':'2026-10-18'})
        if r['voucher']==header.name]
    assert header.grand_total==1250 and rows[0]['base_amount']==1000 and rows[0]['net_vat']==250,rows
    print('PASS ordinary native header VAT without item template retains 1000 report base / 250 VAT')
    zero=draft('Sales Invoice')
    zero.items[0].item_tax_template='Fritatt MVA – nullsats - RVE'
    zero.append('taxes',charge('Actual','3020',amount=100))
    zero.insert();zero.submit()
    rows=[r for r in collect({'company':c.name,'from_date':'2026-10-18','to_date':'2026-10-18'})
        if r['voucher']==zero.name]
    assert zero.grand_total==1100 and rows[0]['base_amount']==1100 and rows[0]['net_vat']==0,rows
    print('PASS zero-rated freight remains part of the native 1100 consideration and report base')
    purchase=draft('Purchase Invoice')
    purchase.append('taxes',charge('Actual','4500',amount=100))
    purchase.insert()
    save_file('synthetic-separate-charge.pdf',frappe.get_print(purchase.doctype,purchase.name,as_pdf=True),
        purchase.doctype,purchase.name,is_private=1)
    purchase.submit()
    assert purchase.grand_total==1350,purchase.grand_total
    ledger=frappe.get_all('GL Entry',filters={'company':c.name,'voucher_no':purchase.name,'is_cancelled':0},
        fields=['account','debit','credit'])
    for code,expected in [('4500',1200),('2710',150),('2400',-1350)]:
        actual=round(sum(r.debit-r.credit for r in ledger if r.account==accounts[code]),2)
        assert actual==expected,(code,actual,expected)
    print('PASS separate Actual charge on same expense account retains 100 charge + 100 VAT cost + 150 input VAT')
    for kind in ('On Previous Row Amount','On Previous Row Total'):
        freight=draft('Purchase Invoice');freight.bill_no='SYNTHETIC-FREIGHT-'+kind
        freight.append('taxes',charge('Actual','6100',amount=100))
        freight.append('taxes',charge(kind,'2710',rate=25,row_id='1'))
        freight.insert()
        save_file('synthetic-freight.pdf',frappe.get_print(freight.doctype,freight.name,as_pdf=True),
            freight.doctype,freight.name,is_private=1)
        freight.submit()
        assert freight.grand_total==1375,(kind,freight.grand_total)
        ledger=frappe.get_all('GL Entry',filters={'company':c.name,'voucher_no':freight.name,'is_cancelled':0},
            fields=['account','debit','credit'])
        for code,expected in [('4500',1110),('6100',100),('2710',165),('2400',-1375)]:
            actual=round(sum(r.debit-r.credit for r in ledger if r.account==accounts[code]),2)
            assert actual==expected,(kind,code,actual,expected)
    print('PASS both native previous-row VAT bases preserve goods/freight VAT with partial deduction: 165 input VAT / 1210 cost / 1375 payable')
    no_deduction=draft('Purchase Invoice');no_deduction.bill_no='SYNTHETIC-FREIGHT-NO-DEDUCTION'
    no_deduction.items[0].set(DEDUCTION,0)
    no_deduction.append('taxes',charge('Actual','6100',amount=100))
    no_deduction.append('taxes',charge('On Previous Row Amount','2710',rate=25,row_id='1'))
    no_deduction.insert()
    assert no_deduction.grand_total==1375,no_deduction.grand_total
    assert sum(tax.tax_amount for tax in no_deduction.taxes if tax.account_head==accounts['2710'])==0
    assert sum(tax.tax_amount for tax in no_deduction.taxes if tax.account_head==accounts['4500'])==275
    print('PASS no deduction retains VAT on both goods and freight in cost')
    inclusive=draft('Purchase Invoice');inclusive.bill_no='SYNTHETIC-INCLUSIVE-PARTIAL'
    inclusive.items[0].rate=1250
    inclusive.append('taxes',charge('On Net Total','2710',rate=25,included_in_print_rate=1))
    inclusive.insert()
    assert inclusive.net_total==1000 and inclusive.grand_total==1250
    assert sum(tax.tax_amount for tax in inclusive.taxes if tax.account_head==accounts['2710'])==150
    assert sum(tax.tax_amount for tax in inclusive.taxes if tax.account_head==accounts['4500'])==100
    print('PASS native inclusive price: 1250 payable / 1000 base / 150 deductible VAT / 100 VAT cost')
    conflict=draft('Purchase Invoice')
    conflict.bill_no='SYNTHETIC-PERCENTAGE-CHARGE-CONFLICT'
    conflict.append('taxes',charge('On Net Total','4500',rate=10))
    frappe.db.savepoint('percentage_charge_conflict')
    try:
        conflict.insert()
    except frappe.ValidationError:
        frappe.db.rollback(save_point='percentage_charge_conflict')
    else:
        raise AssertionError('Ambiguous percentage charge overwrote VAT cost')
    print('PASS conflicting percentage charge requires its own native account instead of silently changing the amount')
finally:
    frappe.db.rollback();frappe.clear_cache();frappe.destroy()
