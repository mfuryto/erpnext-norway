"""Existing export templates/native sales chain, EUR credit/refund and originals."""
import os,sys,json,hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway.vat_catalog import CODE
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
C='Runtime Sales VAT Chain';OWNER='runtime-vat-owner@example.invalid'
def report():return collect({'company':C,'from_date':'2026-08-01','to_date':'2026-09-30'})
def ledger(doc):
    return sorted((r.account,float(r.debit),float(r.credit)) for r in frappe.get_all('GL Entry',filters={'voucher_type':doc.doctype,'voucher_no':doc.name,'is_cancelled':0},fields=['account','debit','credit']))
try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.db.get_default('runtime_export_evidence'))
        for entry in e['documents']:
            doc=frappe.get_doc(entry['doctype'],entry['name']);assert doc.docstatus==1 and doc.grand_total==entry['total']
            if doc.doctype=='Sales Invoice':assert ledger(doc)==[tuple(r) for r in entry['ledger']] and doc.outstanding_amount==0
        for entry in e['files']:
            assert hashlib.sha256(Path(frappe.get_doc('File',entry['name']).get_full_path()).read_bytes()).hexdigest()==entry['sha256']
        rows=[r for r in report() if r['voucher'] in e['invoices']]
        assert sum(r['base_amount'] for r in rows)==500 and all(r['vat_code']=='52' and r['output_vat']==0 for r in rows)
        print('PASS restored native export sales-chain links, EUR receipt/refund GL, net500 NOK code52 basis and English PDF originals')
    else:
        c=frappe.get_doc('Company',C);a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        c.exchange_gain_loss_account=a['8160'];c.default_bank_account=a['1920'];c.save()
        receivable=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic export EUR receivable',
            'parent_account':frappe.db.get_value('Account',a['1500'],'parent_account'),'account_type':'Receivable','account_currency':'EUR'}).insert()
        customer=frappe.get_doc({'doctype':'Customer','customer_name':'Synthetic export customer in Sweden','customer_type':'Company',
            'customer_group':frappe.get_all('Customer Group',filters={'is_group':0},pluck='name')[0],'territory':'All Territories',
            'default_currency':'EUR','language':'en','accounts':[{'company':C,'account':receivable.name}]}).insert()
        address=frappe.get_doc({'doctype':'Address','address_title':'Synthetic export customer address','address_type':'Billing',
            'address_line1':'Synthetic address','city':'Stockholm','pincode':'11111','country':'Sweden','is_primary_address':1,
            'links':[{'link_doctype':'Customer','link_name':customer.name}]}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        quotation=frappe.get_doc({'doctype':'Quotation','quotation_to':'Customer','party_name':customer.name,'customer_address':address.name,
            'company':C,'transaction_date':'2026-08-10','valid_till':frappe.utils.add_days(frappe.utils.nowdate(),30),'currency':'EUR','conversion_rate':10,'language':'en',
            'disable_rounded_total':1,'terms':'VAT-exempt remotely deliverable service under Norwegian VAT Act section 6-22. Delivery 20 August 2026 to recipient resident in Sweden.',
            'items':[{'item_code':'RUNTIME-VAT-SERVICE','description':'Synthetic remotely deliverable service supplied to Sweden','qty':2,'rate':50,
                'cost_center':c.cost_center,'item_tax_template':'Eksport – fritatt MVA - SCV'}]}).insert();quotation.submit()
        order=make_sales_order(quotation.name);order.transaction_date='2026-08-11';order.delivery_date='2026-08-20';order.insert();order.submit()
        delivery=make_delivery_note(order.name);delivery.posting_date='2026-08-20';delivery.set_posting_time=1;delivery.insert();delivery.submit()
        sale=make_sales_invoice(delivery.name);sale.posting_date='2026-08-21';sale.set_posting_time=1;sale.due_date='2026-10-31';sale.language='en';sale.debit_to=receivable.name
        for row in sale.items:row.income_account=a['3020'];row.cost_center=c.cost_center
        sale.insert();sale.submit()
        for doc in (quotation,order,delivery,sale):assert doc.grand_total==100 and doc.currency=='EUR'
        assert sale.items[0].get(CODE)=='52' and sale.items[0].delivery_note==delivery.name and sale.items[0].sales_order==order.name
        payment=get_payment_entry('Sales Invoice',sale.name,bank_account=a['1920'],bank_amount=1050)
        payment.posting_date='2026-09-05';payment.reference_date='2026-09-05';payment.reference_no='SYNTHETIC-EXPORT-RECEIPT'
        payment.source_exchange_rate=10.5;payment.received_amount=1050;payment.set_amounts();payment.insert();payment.submit();assert sale.reload().outstanding_amount==0
        credit=make_return_doc('Sales Invoice',sale.name);credit.posting_date='2026-09-10';credit.set_posting_time=1;credit.language='en'
        credit.items[0].qty=-1;credit.update_outstanding_for_self=1;credit.insert();credit.submit()
        assert credit.grand_total==-50 and credit.items[0].get(CODE)=='52'
        refund=get_payment_entry('Sales Invoice',credit.name,bank_account=a['1920'],bank_amount=525)
        refund.posting_date='2026-09-15';refund.reference_date='2026-09-15';refund.reference_no='SYNTHETIC-EXPORT-REFUND'
        refund.target_exchange_rate=10.5;refund.paid_amount=525;refund.set_amounts();refund.insert();refund.submit();assert credit.reload().outstanding_amount==0
        rows=[r for r in report() if r['voucher'] in (sale.name,credit.name)]
        assert sum(r['base_amount'] for r in rows)==500 and all(r['vat_code']=='52' and r['output_vat']==0 for r in rows)
        # A foreign address alone must not replace the chosen domestic treatment.
        frappe.db.savepoint('foreign_address_domestic_supply')
        domestic=frappe.copy_doc(sale);domestic.items[0].description='Synthetic work on property in Norway';domestic.items[0].item_tax_template='MVA 25 % – varelinjer - SCV'
        for row in domestic.items:
            for field in ('sales_order','so_detail','delivery_note','dn_detail'):row.set(field,None)
        domestic.insert();assert domestic.grand_total==125 and domestic.items[0].get(CODE)=='3'
        frappe.db.rollback(save_point='foreign_address_domestic_supply')
        e={'documents':[],'files':[],'invoices':[sale.name,credit.name]}
        for doc in (quotation,order,delivery,sale,credit):
            e['documents'].append({'doctype':doc.doctype,'name':doc.name,'total':doc.grand_total,'ledger':ledger(doc)})
            for name in frappe.get_all('File',filters={'attached_to_doctype':doc.doctype,'attached_to_name':doc.name,'is_private':1},pluck='name'):
                file=frappe.get_doc('File',name);e['files'].append({'name':name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
        assert len(e['files'])==3
        frappe.db.set_default('runtime_export_evidence',json.dumps(e));frappe.db.commit()
        print('PASS existing native export quote/order/delivery/EUR100 invoice,50 credit,next-period1050 receipt/525 refund,net500 NOK code52 basis,explicit domestic treatment retained and three English original PDFs; no new export engine')
finally:frappe.destroy()
