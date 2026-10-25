"""Ordinary native registered service import, deduction, returns and settlement."""
import os, sys, json, hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect()
frappe.set_user('Administrator');frappe.local.lang='en';frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat, reverse_charge
from erpnext_norway.vat_catalog import CODE, DEDUCTION
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect,execute
from erpnext_norway.vat_settlement import make_settlement
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils.file_manager import save_file
C='Runtime Reverse Services';OWNER='runtime-vat-owner@example.invalid'


def equal(a,b):assert round(float(a or 0),2)==b,(a,b)
def ledger(doc):
    result={}
    for r in frappe.get_all('GL Entry',filters={'voucher_type':doc.doctype,'voucher_no':doc.name,'is_cancelled':0},fields=['account','debit','credit']):
        number=frappe.get_cached_value('Account',r.account,'account_number')
        result[number]=round(result.get(number,0)+float(r.debit)-float(r.credit),2)
    return {k:v for k,v in result.items() if v}
def submit(doc):
    doc.insert()
    file=save_file('synthetic-reverse-supplier.pdf',frappe.get_print(doc.doctype,doc.name,as_pdf=True),doc.doctype,doc.name,is_private=1)
    doc.submit()
    return file

def rejected(action, message=None):
    frappe.db.savepoint('reverse_reject')
    try:action()
    except frappe.ValidationError as error:
        if message:assert message in str(error),str(error)
        frappe.db.rollback(save_point='reverse_reject')
    else:raise AssertionError('Invalid treatment accepted')

try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_reverse_evidence'))
        for entry in evidence:
            doc=frappe.get_doc('Purchase Invoice',entry['name'])
            assert ledger(doc)==entry['ledger']
            assert hashlib.sha256(Path(frappe.get_doc('File',entry['file']).get_full_path()).read_bytes()).hexdigest()==entry['sha256']
        rows=collect({'company':C,'from_date':'2026-09-01','to_date':'2026-10-31'})
        equal(sum(r['output_vat'] for r in rows),375);equal(sum(r['input_vat'] for r in rows),200)
        print('PASS restored reverse-charge invoice/credit ledger, 375 output / 200 input and private supplier PDF originals')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'RRS','country':'Norway',
            'default_currency':'NOK','tax_id':'999999991','enable_perpetual_inventory':0,
            'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        A={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number']) if r.account_number}
        supplier=frappe.get_all('Supplier',pluck='name')[0]
        item=frappe.get_doc('Item','RUNTIME-VAT-SERVICE');item.append('item_defaults',{'company':C,'expense_account':A['4500']});item.save()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        full=frappe.db.get_value('Item Tax Template',{'company':C,'title':'Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag'})
        zero=frappe.db.get_value('Item Tax Template',{'company':C,'title':'Tjenestekjøp fra utlandet – MVA 25 % – 0 % fradrag'})
        assert full and zero
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        def invoice(percent=100,**extra):
            return frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier,
                'posting_date':'2026-09-16','set_posting_time':1,'bill_date':'2026-09-16','bill_no':'SYNTHETIC-REVERSE',
                'due_date':'2026-10-31','currency':'NOK','conversion_rate':1,'disable_rounded_total':1,
                'cost_center':c.cost_center,'items':[{'item_code':item.name,'qty':2,'rate':500,
                    'expense_account':A['4500'],'cost_center':c.cost_center,'item_tax_template':full,DEDUCTION:percent}],**extra})
        evidence=[]
        for percent,cost,input_,code in [(100,1000,250,'86'),(60,1100,150,'86'),(0,1250,0,'87')]:
            doc=invoice(percent);file=submit(doc)
            equal(doc.grand_total,1000);assert doc.items[0].get(CODE)==code
            expected={'4500':cost,'2704':-250,'2400':-1000}
            if input_:expected['2714']=input_
            assert ledger(doc)==expected,ledger(doc)
            row=next(r for r in collect({'company':C,'from_date':'2026-09-01','to_date':'2026-10-31'}) if r['voucher']==doc.name)
            equal(row['base_amount'],1000);equal(row['output_vat'],250);equal(row['input_vat'],input_)
            equal(row['vat_rate'],25)
            evidence.append({'name':doc.name,'ledger':expected,'file':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
            credit=make_return_doc('Purchase Invoice',doc.name)
            credit.posting_date=credit.bill_date='2026-10-16';credit.set_posting_time=1;credit.bill_no='SYNTHETIC-REVERSE-CREDIT'
            for row in credit.items:row.qty=-1
            credit_file=submit(credit);equal(credit.grand_total,-500)
            inverse={k:round(-v/2,2) for k,v in expected.items()};assert ledger(credit)==inverse,ledger(credit)
            evidence.append({'name':credit.name,'ledger':inverse,'file':credit_file.name,'sha256':hashlib.sha256(Path(credit_file.get_full_path()).read_bytes()).hexdigest()})
        print('PASS ordinary owner native reverse charge 100/60/0 percent deduction: supplier 1000, output 250, input 250/150/0, cost 1000/1100/1250; native partial credits reverse all sides')
        chosen=invoice();chosen.items[0].item_tax_template=zero;file=submit(chosen)
        equal(chosen.items[0].get(DEDUCTION),0);assert chosen.items[0].get(CODE)=='87'
        chosen.cancel()
        mixed=invoice();mixed.append('items',{'item_code':item.name,'qty':1,'rate':1000,'expense_account':A['4500'],
            'cost_center':c.cost_center,'item_tax_template':'MVA 15 % – varelinjer - RRS'})
        submit(mixed);equal(mixed.grand_total,2150)
        assert ledger(mixed)=={'4500':2000,'2400':-2150,'2704':-250,'2714':250,'2711':150},ledger(mixed)
        mixed.cancel()
        print('PASS native item-level reverse/domestic mixed invoice and saved no-deduction selection; cancellation retained')
        header=invoice();header.items[0].item_tax_template=None
        for code,direction in [('2714','Add'),('2704','Deduct')]:
            header.append('taxes',{'charge_type':'On Net Total','account_head':A[code],
                'rate':25,'description':'Synthetic native reverse header','category':'Total',
                'add_deduct_tax':direction,'cost_center':c.cost_center})
        submit(header)
        header_row=next(r for r in collect({'company':C,'from_date':'2026-09-01','to_date':'2026-10-31'}) if r['voucher']==header.name)
        equal(header_row['base_amount'],1000);equal(header_row['output_vat'],250);equal(header_row['input_vat'],250)
        header.cancel()
        print('PASS existing native header reverse-charge rows without an item template retain positive report base and balanced VAT')
        invalid=invoice();invalid.items[0].item_code='RUNTIME-VAT-SERVICE';invalid.currency='EUR';invalid.conversion_rate=10
        rejected(invalid.insert, 'VAT delivery date')
        early=invoice(0,bill_date='2025-12-31')
        rejected(early.insert, 'effective VAT registration')
        wrong=invoice(taxes=[{'charge_type':'On Net Total','account_head':A['2704'],
            'rate':25,'description':'Synthetic wrong direction','category':'Total','add_deduct_tax':'Add'}])
        rejected(wrong.insert, 'output reverse-charge VAT as Deduct')
        from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice
        order=frappe.get_doc({'doctype':'Purchase Order','company':C,'supplier':supplier,
            'transaction_date':'2026-09-16','schedule_date':'2026-09-20','currency':'NOK','conversion_rate':1,
            'items':[{'item_code':item.name,'qty':2,'rate':500,'expense_account':A['4500'],
                'cost_center':c.cost_center,'item_tax_template':full,DEDUCTION:60}]})
        order.insert();order.submit();equal(order.grand_total,1000)
        mapped=make_purchase_invoice(order.name)
        mapped.posting_date=mapped.bill_date='2026-09-16';mapped.set_posting_time=1
        mapped.bill_no='SYNTHETIC-REVERSE-ORDER';mapped.due_date='2026-10-31'
        submit(mapped);equal(mapped.grand_total,1000)
        assert ledger(mapped)=={'4500':1100,'2400':-1000,'2704':-250,'2714':150},ledger(mapped)
        mapped.cancel();order.reload();order.cancel()
        print('PASS native purchase order to invoice retains reverse-charge deduction; early registration, foreign currency and wrong explicit tax direction are rejected')
        rows=collect({'company':C,'from_date':'2026-09-01','to_date':'2026-10-31'})
        equal(sum(r['output_vat'] for r in rows),375);equal(sum(r['input_vat'] for r in rows),200)
        for start,end,output,input_ in [('2026-09-01','2026-09-30',750,400),('2026-10-01','2026-10-31',-375,-200)]:
            period=collect({'company':C,'from_date':start,'to_date':end})
            equal(sum(r['output_vat'] for r in period),output);equal(sum(r['input_vat'] for r in period),input_)
        columns,grouped,*_=execute({'company':C,'from_date':'2026-09-01','to_date':'2026-10-31'})
        assert {r['vat_code'] for r in grouped}=={'86','87'}
        for code,base,output,input_ in [('86',1000,250,200),('87',500,125,0)]:
            row=next(r for r in grouped if r['vat_code']==code)
            equal(row['base_amount'],base);equal(row['output_vat'],output);equal(row['input_vat'],input_)
        settlement=frappe.get_doc('Journal Entry',make_settlement(C,'2026-09-01','2026-10-31')['name']);settlement.submit()
        assert ledger(settlement)=={'2704':375,'2714':-200,'2740':-175},ledger(settlement)
        print('PASS native reverse-charge report signs and single base, credit in later period and native settlement: 375 output / 200 input / 175 payable')
        # Do not commit settlement; preserve original invoice/credit state for browser and restore.
        settlement.cancel()
        payment=get_payment_entry('Purchase Invoice',evidence[0]['name'],bank_account=A['1920'])
        payment.posting_date='2026-10-20';payment.reference_no='SYNTHETIC-REVERSE-PAYMENT';payment.reference_date=payment.posting_date
        payment.insert();payment.submit()
        equal(frappe.get_doc('Purchase Invoice',evidence[0]['name']).outstanding_amount,0)
        print('PASS native supplier payment uses actual foreign supplier balance, without paying reverse VAT to the supplier')
        frappe.db.set_default('runtime_reverse_evidence',json.dumps(evidence));frappe.db.commit()
finally:frappe.db.rollback();frappe.destroy()
