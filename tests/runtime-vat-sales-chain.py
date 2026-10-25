"""Native mixed-rate quotation/order/partial delivery/invoice/credit/payment."""
import os, sys, json, hashlib
from pathlib import Path
import frappe

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites'); frappe.connect()
frappe.set_user('Administrator'); frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect

C='Runtime Sales VAT Chain'; OWNER='runtime-vat-owner@example.invalid'

def equal(actual, expected): assert round(float(actual or 0),2)==expected,(actual,expected)
def rejected(action, message):
    frappe.db.savepoint('sales_chain_rejection')
    try: action()
    except frappe.ValidationError as error:
        assert message in str(error),str(error)
        frappe.db.rollback(save_point='sales_chain_rejection')
    else: raise AssertionError('Invalid configuration accepted')
def ledger(doc):
    result={}
    for row in frappe.get_all('GL Entry',filters={'voucher_type':doc.doctype,
            'voucher_no':doc.name,'is_cancelled':0},fields=['account','debit','credit']):
        number=frappe.get_cached_value('Account',row.account,'account_number')
        result[number]=round(result.get(number,0)+float(row.debit)-float(row.credit),2)
    return {key:value for key,value in result.items() if value}
def basis(start='2026-08-01',end='2026-09-30'):
    return collect({'company':C,'from_date':start,'to_date':end})

try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_sales_chain_evidence'))
        for entry in evidence['documents']:
            doc=frappe.get_doc(entry['doctype'],entry['name'])
            equal(doc.grand_total,entry['total'])
            assert doc.docstatus==1
            for field,value in entry.get('links',{}).items():
                assert [row.get(field) for row in doc.items]==value
            if doc.doctype=='Sales Invoice': assert ledger(doc)==entry['ledger']
        for file in evidence['files']:
            path=frappe.get_doc('File',file['name']).get_full_path()
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==file['sha256']
        equal(sum(row['output_vat'] for row in basis()),351)
        equal(sum(row['input_vat'] for row in basis()),0)
        print('PASS restored native sales-chain links, 351 output VAT, receivables and NB/EN PDF original bytes')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SCV','country':'Norway',
            'default_currency':'NOK','tax_id':'999999989','enable_perpetual_inventory':0,
            'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',
            vat.FROM:'2026-01-01'}).insert()
        A={row.account_number:row.name for row in frappe.get_all('Account',filters={'company':C},
            fields=['name','account_number']) if row.account_number}
        customer=frappe.get_all('Customer',pluck='name')[0]
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company',
            'for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER); assert 'System Manager' not in frappe.get_roles()

        def quotation(rates=(25,15,12,0),qty=4,price=250,**extra):
            return frappe.get_doc({'doctype':'Quotation','company':C,'quotation_to':'Customer',
                'party_name':customer,'transaction_date':'2026-08-10','valid_till':'2026-12-31',
                'currency':'NOK','conversion_rate':1,'language':'nb','tax_category':'Norge MVA 25 %',
                'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':qty,'rate':price,
                    'cost_center':c.cost_center,'item_tax_template':
                        (f'MVA {rate} % – varelinjer' if rate else 'Fritatt MVA – nullsats')+' - SCV'}
                    for rate in rates],**extra})
        q=quotation(apply_discount_on='Net Total',additional_discount_percentage=10)
        q.insert();q.submit();equal(q.net_total,3600);equal(q.grand_total,4068)
        assert len(q.taxes)==3 and not any(row.account_head.startswith('271') for row in q.taxes)
        so=make_sales_order(q.name);so.transaction_date='2026-08-11';so.delivery_date='2026-08-20'
        so.insert();so.submit();equal(so.grand_total,4068)
        assert all(row.prevdoc_docname==q.name for row in so.items)
        evidence={'documents':[],'files':[]}
        def retain(doc,**links):
            entry={'doctype':doc.doctype,'name':doc.name,'total':doc.grand_total,
                'links':{field:[row.get(field) for row in doc.items] for field in links}}
            if doc.doctype=='Sales Invoice':entry['ledger']=ledger(doc)
            evidence['documents'].append(entry)
            for name in frappe.get_all('File',filters={'attached_to_doctype':doc.doctype,
                    'attached_to_name':doc.name,'is_private':1},pluck='name'):
                file=frappe.get_doc('File',name)
                evidence['files'].append({'name':name,'sha256':hashlib.sha256(
                    Path(file.get_full_path()).read_bytes()).hexdigest()})
        retain(q);retain(so,prevdoc_docname=True,quotation_item=True)
        invoices=[]
        for day in (20,22):
            dn=make_delivery_note(so.name);dn.posting_date=f'2026-08-{day}';dn.set_posting_time=1
            for row in dn.items:row.qty=2
            dn.insert();dn.submit();equal(dn.grand_total,2034)
            assert all(row.against_sales_order==so.name for row in dn.items)
            si=make_sales_invoice(dn.name);si.posting_date=f'2026-08-{day+1}'
            si.language='nb' if day==20 else 'en'
            si.set_posting_time=1;si.due_date='2026-09-30'
            for row in si.items:row.income_account=A['3020'];row.cost_center=c.cost_center
            si.insert();si.submit();equal(si.grand_total,2034)
            assert [row.get(CODE) for row in si.items]==['3','31','33','5']
            assert all(row.delivery_note==dn.name and row.sales_order==so.name for row in si.items)
            assert ledger(si)=={'1500':2034,'3020':-1800,'2700':-112.5,'2701':-67.5,'2703':-54},ledger(si)
            retain(dn,against_sales_order=True,so_detail=True)
            retain(si,sales_order=True,so_detail=True,delivery_note=True,dn_detail=True)
            invoices.append(si)
        so.reload();equal(so.per_delivered,100);equal(so.per_billed,100)
        print('PASS native mixed 25/15/12/zero sales chain with 10 percent discount, two partial deliveries/invoices: 4068 total / 468 VAT')

        credit=make_return_doc('Sales Invoice',invoices[0].name)
        credit.posting_date='2026-09-10';credit.set_posting_time=1;credit.due_date='2026-09-30'
        credit.language='en'
        credit.update_outstanding_for_self=0
        for row in credit.items:row.qty=-1
        credit.insert();credit.submit();equal(credit.grand_total,-1017)
        assert ledger(credit)=={'1500':-1017,'3020':900,'2700':56.25,'2701':33.75,'2703':27},ledger(credit)
        retain(credit,sales_invoice_item=True)
        equal(sum(row['output_vat'] for row in basis()),351)
        equal(sum(row['output_vat'] for row in basis(end='2026-08-31')),468)
        equal(sum(row['output_vat'] for row in basis(start='2026-09-01')),-117)
        for invoice,expected in zip(invoices,(1017,2034)):
            payment=get_payment_entry('Sales Invoice',invoice.name,bank_account=A['1920'])
            payment.posting_date='2026-09-15';payment.reference_no='SYNTHETIC-SALES-CHAIN'
            payment.reference_date='2026-09-15';equal(payment.paid_amount,expected)
            payment.insert();payment.submit();invoice.reload();equal(invoice.outstanding_amount,0)
        equal(sum(ledger(doc).get('1500',0) for doc in invoices+[credit])+sum(
            row.debit-row.credit for row in frappe.get_all('GL Entry',filters={'company':C,
                'voucher_type':'Payment Entry','account':A['1500'],'is_cancelled':0},fields=['debit','credit'])),0)
        print('PASS native partial sales credit reverses 117 VAT in next period; native customer payments settle 1017 and 2034')

        inclusive=quotation((25,),qty=1,price=1250,taxes=[{'charge_type':'On Net Total',
            'account_head':A['2700'],'rate':25,'description':'MVA 25 %',
            'included_in_print_rate':1,'cost_center':c.cost_center}]).insert()
        equal(inclusive.net_total,1000);equal(inclusive.grand_total,1250)
        # Reproduce native auto-input rows before a freight row. Keep the native
        # amount/total reference pointing at the same charge after removing input.
        def freight(reference='3',manual=False):
            return quotation((25,),qty=1,price=1000,taxes=[
                {'charge_type':'On Net Total','account_head':A['2700'],'rate':0,'description':'Output'},
                {'charge_type':'On Net Total','account_head':A['2710'],'rate':0,
                    'description':'Native auto input','set_by_item_tax_template':0 if manual else 1},
                {'charge_type':'Actual','account_head':A['3020'],'tax_amount':100,'description':'Freight'},
                {'charge_type':'On Previous Row Amount','account_head':A['2700'],'rate':25,
                    'row_id':reference,'description':'VAT on freight'},
            ])
        charge=freight().insert();equal(charge.grand_total,1375)
        assert charge.taxes[-1].row_id=='2'
        rejected(lambda:freight(manual=True).insert(),'Use output VAT accounts')
        rejected(lambda:freight(reference='2').insert(),'refers to an input VAT row')
        print('PASS native inclusive quotation and freight row reference survive auto-input removal; explicit input VAT and references to it are rejected')
        assert len(evidence['files'])==4,evidence['files']
        names=[frappe.db.get_value('File',row['name'],'file_name') for row in evidence['files']]
        assert any('-nb' in name for name in names) and any('-en' in name for name in names),names
        frappe.db.set_default('runtime_sales_chain_evidence',json.dumps(evidence))
    frappe.db.commit()
finally:frappe.destroy()
