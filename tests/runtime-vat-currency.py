"""Registered service FX: native basis, GL, credit, bank payment and restore."""
import os,sys,json,hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE,DEDUCTION
from erpnext_norway.vat_currency import DATE,EXCHANGE,KIND
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice
from frappe.utils.file_manager import save_file
C='Runtime Currency Services';OWNER='runtime-vat-owner@example.invalid'
def equal(actual,expected):assert round(float(actual or 0),2)==expected,(actual,expected)
def ledger(doc):
    result={}
    for row in frappe.get_all('GL Entry',filters={'voucher_type':doc.doctype,'voucher_no':doc.name,'is_cancelled':0},fields=['account','debit','credit']):
        result[row.account]=round(result.get(row.account,0)+row.debit-row.credit,2)
    return {key:value for key,value in result.items() if value}
def totals():
    result={}
    for row in frappe.get_all('GL Entry',filters={'company':C,'is_cancelled':0},fields=['account','debit','credit']):
        result[row.account]=round(result.get(row.account,0)+row.debit-row.credit,2)
    return result
def report(start='2026-09-01',end='2026-10-31'):
    return collect({'company':C,'from_date':start,'to_date':end})
def rejected(action,message=None,exception=None):
    frappe.db.savepoint('fx_reject')
    try:action()
    except frappe.ValidationError as error:
        if message:assert message in str(error),str(error)
        if exception:assert type(error).__name__==exception,(type(error).__name__,str(error))
        frappe.db.rollback(save_point='fx_reject')
    else:raise AssertionError('Invalid currency treatment was accepted')
def snapshot(doc):
    return {'doctype':doc.doctype,'name':doc.name,'total':doc.get('grand_total'),
        'items':[{key:str(row.get(key)) if key==DATE else row.get(key)
            for key in (DATE,EXCHANGE,CODE,DEDUCTION,'purchase_order','po_detail','purchase_invoice_item')}
            for row in (doc.get('items') or [])], 'ledger':ledger(doc)}
try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_currency_evidence'))
        for entry in evidence['documents']:
            doc=frappe.get_doc(entry['doctype'],entry['name']);assert doc.docstatus==1
            assert snapshot(doc)==entry,(doc.doctype,doc.name)
            if doc.doctype=='Purchase Invoice' and not doc.is_return:equal(doc.outstanding_amount,0)
        for file in evidence['files']:
            assert hashlib.sha256(Path(frappe.get_doc('File',file['name']).get_full_path()).read_bytes()).hexdigest()==file['sha256']
        assert totals()==evidence['totals']
        equal(sum(row['output_vat'] for row in report()),671.76)
        equal(sum(row['input_vat'] for row in report()),479.03)
        print('PASS restored currency metadata, native order/credit metadata, payment/FX-journal GL, 671.76 output / 479.03 input, private original PDF bytes')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'FCV','country':'Norway','default_currency':'NOK','tax_id':'999999987','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        A={row.account_number:row.name for row in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        payable=frappe.get_doc({'doctype':'Account','account_name':'Runtime supplier EUR','parent_account':frappe.db.get_value('Account',A['2400'],'parent_account'),'company':C,'account_type':'Payable','account_currency':'EUR'}).insert()
        c.exchange_gain_loss_account=A['8160'];c.save()
        frappe.get_doc({'doctype':'Currency Exchange','date':frappe.utils.nowdate(),'from_currency':'EUR','to_currency':'NOK','exchange_rate':10.5,'for_buying':1,'for_selling':1}).insert()
        supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Runtime currency supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'EUR','accounts':[{'company':C,'account':payable.name}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        def invoice(percent=100,**extra):
            return frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,'credit_to':payable.name,'posting_date':'2026-09-16','set_posting_time':1,'bill_date':'2026-09-16','bill_no':f'SYNTHETIC-FX-{percent}','due_date':'2026-10-31','currency':'EUR','conversion_rate':10,'disable_rounded_total':1,'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':2,'rate':50,'expense_account':A['4500'],'cost_center':c.cost_center,'item_tax_template':'Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag - FCV',DEDUCTION:percent,DATE:'2026-09-10',EXCHANGE:11.0137}],**extra})
        evidence={'documents':[],'files':[]}
        invoices=[]
        for percent,input_,cost,rounding in [(100,275.34,1000,0),(60,165.21,1110.14,-.01),(0,0,1275.34,0)]:
            doc=invoice(percent);doc.insert();doc.submit()
            equal(doc.grand_total,100);equal(doc.base_grand_total,1000)
            rows=[row for row in report() if row['voucher']==doc.name];assert len(rows)==1
            equal(rows[0]['base_amount'],1101.37);equal(rows[0]['output_vat'],275.34);equal(rows[0]['input_vat'],input_);equal(rows[0]['vat_rate'],25)
            expected={payable.name:-1000,A['2704']:-275.34,A['4500']:cost}
            if input_:expected[A['2714']]=input_
            if rounding:expected[A['7740']]=rounding
            assert ledger(doc)==expected,ledger(doc)
            credit=make_return_doc('Purchase Invoice',doc.name);credit.posting_date='2026-10-01';credit.set_posting_time=1;credit.bill_date='2026-10-01';credit.bill_no=f'SYNTHETIC-FX-CREDIT-{percent}';credit.update_outstanding_for_self=0
            credit.items[0].qty=-1;credit.items[0].set(EXCHANGE,99);credit.items[0].set(DATE,'2026-10-01')
            credit.insert();credit.submit();equal(credit.grand_total,-50)
            assert credit.items[0].get(EXCHANGE)==11.0137;assert str(credit.items[0].get(DATE))=='2026-09-10'
            row=next(row for row in report() if row['voucher']==credit.name)
            equal(row['base_amount'],-550.68);equal(row['output_vat'],-137.67);equal(row['input_vat'],{100:-137.67,60:-82.6,0:0}[percent])
            for saved in (doc,credit):
                file=save_file('synthetic-currency-source.pdf',frappe.get_print(saved.doctype,saved.name,as_pdf=True),saved.doctype,saved.name,is_private=1)
                evidence['files'].append({'name':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
                evidence['documents'].append(snapshot(saved))
            invoices.append(doc)
        print('PASS ordinary owner native EUR 100/60/0 percent deduction, separate delivery FX base 1101.37, 275.34 VAT, native one-cent rounding; half credits retain original FX/date in next period')

        order=frappe.get_doc({'doctype':'Purchase Order','company':C,'supplier':supplier.name,'transaction_date':'2026-09-10','schedule_date':'2026-09-15','currency':'EUR','conversion_rate':10,'disable_rounded_total':1,'apply_discount_on':'Net Total','additional_discount_percentage':10,'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':50,'schedule_date':'2026-09-15','expense_account':A['4500'],'cost_center':c.cost_center,'item_tax_template':'Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag - FCV',DATE:date,EXCHANGE:exchange} for date,exchange in [('2026-09-10',11),('2026-09-11',12)]]}).insert();order.submit()
        doc=make_purchase_invoice(order.name);doc.credit_to=payable.name;doc.posting_date='2026-09-16';doc.set_posting_time=1;doc.bill_date='2026-09-16';doc.bill_no='SYNTHETIC-FX-ORDER';doc.due_date='2026-10-31'
        for row in doc.items:row.expense_account=A['4500'];row.cost_center=c.cost_center
        doc.insert();doc.submit();equal(doc.grand_total,90)
        rows=[row for row in report() if row['voucher']==doc.name]
        assert [row['base_amount'] for row in rows]==[495,540],rows
        equal(sum(row['output_vat'] for row in rows),258.75)
        assert [row.get(EXCHANGE) for row in doc.items]==[11,12]
        assert all(row.purchase_order==order.name for row in doc.items)
        evidence['documents'] += [snapshot(order),snapshot(doc)];invoices.append(doc)
        print('PASS native two-line foreign purchase order mapping preserves distinct delivery dates/rates and 10 percent net discount: 1035 NOK VAT base, 258.75 VAT, EUR90 payable')

        for doc,bank in zip(invoices,(525,525,525,945)):
            doc.reload();payment=get_payment_entry('Purchase Invoice',doc.name,bank_account=A['1920'],bank_amount=bank)
            payment.posting_date='2026-10-05';payment.reference_date='2026-10-05';payment.reference_no='SYNTHETIC-FX-PAYMENT';payment.target_exchange_rate=10.5
            payment.received_amount=doc.outstanding_amount;payment.set_amounts();payment.insert();payment.submit()
            doc.reload();equal(doc.outstanding_amount,0);evidence['documents'].append(snapshot(payment))
        net=totals();equal(net[payable.name],0);equal(net[A['1920']],-2520);equal(net[A['8160']],120)
        equal(sum(row['output_vat'] for row in report()),671.76);equal(sum(row['input_vat'] for row in report()),479.03)
        print('PASS native supplier payments settle EUR240 with NOK2520 bank and NOK120 exchange loss using standard FX journals; VAT remains 671.76 output / 479.03 input')

        frappe.db.savepoint('fractional_currency_deduction')
        fractional=invoice(33.33);fractional.items[0].rate=5000;fractional.bill_no='SYNTHETIC-FRACTIONAL-FX';fractional.insert();fractional.submit()
        row=next(row for row in report() if row['voucher']==fractional.name)
        equal(fractional.grand_total,10000);equal(row['base_amount'],110137);equal(row['output_vat'],27534.25);equal(row['input_vat'],9177.17)
        frappe.db.rollback(save_point='fractional_currency_deduction')
        print('PASS native fractional deduction precision: EUR10000 with 33.33 percent deduction gives NOK9177.17 input VAT')
        frappe.db.savepoint('fx_registration_change')
        frappe.set_user('Administrator');changed=frappe.get_doc('Company',C);changed.set(vat.FROM,'2027-01-01');changed.save()
        frappe.set_user(OWNER)
        equal(sum(row['output_vat'] for row in report()),671.76)
        late=frappe.copy_doc(invoices[0]);late.bill_no='SYNTHETIC-FX-AFTER-STATUS';rejected(late.insert,'effective VAT registration')
        correction=make_return_doc('Purchase Invoice',invoices[0].name);correction.posting_date='2026-10-06';correction.set_posting_time=1;correction.bill_date='2026-10-06';correction.bill_no='SYNTHETIC-FX-ORIGINAL-STATUS';correction.items[0].qty=-1
        correction.insert();correction.submit();assert correction.items[0].get(EXCHANGE)==11.0137
        frappe.db.rollback(save_point='fx_registration_change');frappe.clear_document_cache('Company',C)
        print('PASS later registration changes preserve issued foreign VAT/report and original credit treatment; new early purchase remains blocked')
        bad=invoice();bad.items[0].set(EXCHANGE,0);rejected(bad.insert,'positive VAT exchange rate')
        bad=invoice();bad.items[0].set(DATE,'2026-10-01');rejected(bad.insert,'cannot be after')
        bad=invoice();bad.items[0].item_tax_template='MVA 25 % – varelinjer - FCV';bad.append('items',invoice().items[0].as_dict());rejected(bad.insert,'only reverse-charge service')
        bad=invoice(taxes=[{'charge_type':'Actual','account_head':A['4500'],'tax_amount':10,'category':'Total','add_deduct_tax':'Add','description':'Extra freight'}]);rejected(bad.insert,'without additional charges')
        posted=frappe.get_doc('Purchase Invoice',invoices[0].name);posted.items[0].set(EXCHANGE,15);rejected(posted.save,exception='UpdateAfterSubmitError')
        frappe.set_user('Administrator')
        frappe.get_doc({'doctype':'Accounting Period','company':C,'period_name':'Runtime closed FX period','start_date':'2026-08-01','end_date':'2026-08-31','closed_documents':[{'document_type':'Purchase Invoice','closed':1}]}).insert()
        frappe.set_user(OWNER)
        bad=invoice(posting_date='2026-08-20',bill_date='2026-08-20');bad.items[0].set(DATE,'2026-08-10');rejected(lambda:bad.insert().submit(),exception='ClosedAccountingPeriod')
        print('PASS invalid FX/date/mixed treatment/freight rejected; native posted-metadata protection and closed-period guard retained')
        evidence['totals']=totals();frappe.db.set_default('runtime_currency_evidence',json.dumps(evidence));frappe.db.commit()
finally:frappe.destroy()
