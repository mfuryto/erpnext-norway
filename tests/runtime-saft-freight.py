"""Reuse standard freight items and native Actual charges, including exported restore."""
import os,sys,json,hashlib
from decimal import Decimal
from pathlib import Path
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import saft,saft_builder as xml,vat
from erpnext_norway.vat_catalog import DEDUCTION
from erpnext_norway.vat_valuation import COST
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Freight';OWNER='runtime-saft-freight@example.invalid';NS={'s':xml.NS}
# Documented synthetic prices: net goods1000 + freight100, 40% returned.
CASES={25:('2710','1',1375,550,{100:(1100,275,440,110),60:(1210,165,484,66),0:(0,0,0,0)}),
    15:('2711','11',1265,506,{100:(1100,165,440,66),60:(1166,99,466.4,39.6),0:(0,0,0,0)}),
    12:('2713','13',1232,492.8,{100:(1100,132,440,52.8),60:(1152.8,79.2,461.12,31.68),0:(0,0,0,0)})}

def export(records,cancelled):
    data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);root=etree.fromstring(data)
    gl=frappe.get_all('GL Entry',filters={'company':C},fields=['*'])
    lines={r.find('s:RecordID',NS).text:r for r in root.findall('.//s:Line',NS)}
    assert set(lines)=={r.name for r in gl}
    for r in gl:
        assert Decimal(lines[r.name].find('s:'+('DebitAmount' if r.debit else 'CreditAmount')+'/s:Amount',NS).text)==xml._money(r.debit or r.credit)
    for side in ('debit','credit'):assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in gl),Decimal())
    for name,total,code,basis,tax,is_credit in records:
        doc=frappe.get_doc('Purchase Invoice',name);assert doc.grand_total==total and doc.outstanding_amount==0
        infos=root.xpath('.//s:Line[s:SourceDocumentID="'+name+'"]/s:TaxInformation',namespaces=NS)
        assert {i.find('s:TaxCode',NS).text for i in infos}=={code}
        assert sum((Decimal(i.find('s:TaxBase',NS).text) for i in infos),Decimal())==Decimal(str(basis))
        side='CreditTaxAmount' if is_credit else 'DebitTaxAmount'
        assert sum((Decimal(i.find('s:'+side+'/s:Amount',NS).text) for i in infos),Decimal())==Decimal(str(tax))
    assert frappe.get_doc('Purchase Invoice',cancelled).docstatus==2
    infos=root.xpath('.//s:Line[s:SourceDocumentID="'+cancelled+'"]/s:TaxInformation',namespaces=NS)
    for side in ('DebitTaxAmount','CreditTaxAmount'):
        assert sum((Decimal(v) for i in infos for v in i.xpath('s:'+side+'/s:Amount/text()',namespaces=NS)),Decimal())==275
    return data,gl

def rejected(doc,text):
    rows=frappe.get_all('GL Entry',filters={'company':C,'voucher_type':'Purchase Invoice','voucher_no':doc.name},fields=['*'])
    try:saft.invoice_taxes(doc,rows)
    except frappe.ValidationError as error:assert text in str(error),str(error)
    else:raise AssertionError('Unsupported or incomplete freight accepted')
try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_saft_freight')).get_content());frappe.set_user(OWNER);_,gl=export(e['records'],e['cancelled'])
        keys=('name','account','debit','credit','voucher_type','voucher_no','is_cancelled')
        assert sorted(tuple(str(r[k]) for k in keys) for r in gl)==sorted(tuple(str(r[k]) for k in keys) for r in e['gl'])
        detail=frappe.get_all('Item Wise Tax Detail',filters={'parent':['in',e['parents']]},fields=['name','parent','item_row','tax_row','amount','taxable_amount','rate'])
        assert sorted(frappe.as_json(r) for r in detail)==sorted(frappe.as_json(r) for r in e['detail'])
        f=frappe.get_doc('File',e['file']);assert f.is_private and hashlib.sha256(Path(f.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored SAF-T freight: standard item and native Actual charges, 25/15/12%, full/partial/no deduction, credits/payment/refund/cancellation, exact GL/details/private XML')
    else:
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic freight owner','send_welcome_email':0,'roles':[{'role':r} for r in ['Accounts Manager','Accounts User','Purchase Manager','Purchase User']]}).insert()
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SFR','country':'Norway','default_currency':'NOK','tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        for code in ('GOODS','SERVICE'):
            frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-SAFT-FREIGHT-'+code,'item_name':'Synthetic freight '+code,'item_group':'Services','stock_uom':'Nos','is_stock_item':0}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic SAF-T freight supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'NOK'}).insert()
        for number,category,group in [('1920','balanseverdiForOmloepsmiddel','1920'),('2400','kortsiktigGjeld','2400'),('4300','varekostnad','4005'),('2710','kortsiktigGjeld','2740'),('2711','kortsiktigGjeld','2740'),('2713','kortsiktigGjeld','2740')]:
            account=frappe.get_doc('Account',a[number]);account.append(saft.MAPPING,{'year':2026,'category':category,'code':group});account.save()
        c.default_bank_account=a['1920'];c.save();frappe.set_user(OWNER)
        def draft(mode,rate,share,reference):
            template=frappe.db.get_value('Item Tax Template',{'company':C,'title':f'MVA {rate} % – varelinjer'})
            items=[{'item_code':'RUNTIME-SAFT-FREIGHT-'+code,'qty':10,'rate':price,'expense_account':a['4300'],'cost_center':c.cost_center,'item_tax_template':template,DEDUCTION:share} for code,price in ([('GOODS',100),('SERVICE',10)] if mode=='item' else [('GOODS',100)])]
            doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,'currency':'NOK','set_posting_time':1,'posting_date':'2026-10-15','bill_date':'2026-10-15','bill_no':reference,'due_date':'2026-10-31','disable_rounded_total':1,'items':items})
            if mode=='charge':
                for kind,account,amount,row_rate,row_id in [('Actual','4300',100,0,None),('On Previous Row Amount',CASES[rate][0],0,rate,'1')]:
                    doc.append('taxes',{'charge_type':kind,'row_id':row_id,'account_head':a[account],'tax_amount':amount,'rate':row_rate,'description':'Synthetic freight','category':'Total','add_deduct_tax':'Add','cost_center':c.cost_center})
            return doc
        records=[];parents=[];source=None
        for mode in ('item','charge'):
            for rate in ((25,) if mode=='item' else (25,15,12)):
                account,code,total,credit_total,shares=CASES[rate]
                for share in (100,60,0):
                    ref=f'{mode[0]}{rate}-{share}'
                    doc=draft(mode,rate,share,'SYN-FRT-'+ref).insert();doc.submit();assert doc.grand_total==total
                    pay=get_payment_entry('Purchase Invoice',doc.name,bank_account=a['1920']);pay.posting_date=pay.reference_date='2026-10-16';pay.reference_no='SYN-PAY-'+ref;pay.insert();pay.submit()
                    credit=make_return_doc('Purchase Invoice',doc.name);credit.posting_date=credit.bill_date='2026-10-17';credit.set_posting_time=1;credit.bill_no='SYN-CR-'+ref;credit.update_outstanding_for_self=1
                    for item in credit.items:item.qty=item.received_qty=-4
                    for tax in credit.taxes:
                        if tax.charge_type=='Actual' and not tax.get(COST):tax.tax_amount=-40
                    credit.insert();credit.submit();assert credit.grand_total==-credit_total
                    refund=get_payment_entry('Purchase Invoice',credit.name,bank_account=a['1920']);refund.posting_date=refund.reference_date='2026-10-18';refund.reference_no='SYN-REF-'+ref;refund.insert();refund.submit()
                    assert doc.reload().outstanding_amount==credit.reload().outstanding_amount==0
                    b,t,cb,ct=shares[share];actual_code=code if share else '0'
                    records.extend([(doc.name,total,actual_code,b,t,False),(credit.name,-credit_total,actual_code,cb,ct,True)]);parents.extend([doc.name,credit.name])
                    if mode=='charge' and rate==25 and share==100:source=doc
        cancelled=draft('charge',25,100,'SYN-FRT-CANCEL').insert();cancelled.submit();cancelled.cancel();parents.append(cancelled.name)
        data,gl=export(records,cancelled.name)
        # Fault injection in synthetic metadata must prevent an incomplete export.
        frappe.db.savepoint('missing_freight_detail')
        fee=next(r for r in source.taxes if r.charge_type=='Actual' and not r.get(COST))
        frappe.db.delete('Item Wise Tax Detail',{'parent':source.name,'tax_row':fee.name})
        rejected(source,'Lagret tilleggsbeløp');frappe.db.rollback(save_point='missing_freight_detail')
        for shape in ('untaxed','other_account','multiple_items'):
            frappe.db.savepoint('unsupported_freight')
            doc=draft('charge',25,100,'SYN-FRT-'+shape)
            if shape=='untaxed':doc.set('taxes',[doc.taxes[0]])
            if shape=='other_account':doc.taxes[0].account_head=a['6100']
            if shape=='multiple_items':doc.append('items',doc.items[0].as_dict() | {'name':None,'rate':10})
            doc.insert();doc.submit();rejected(doc,'Eksportmappingen');frappe.db.rollback(save_point='unsupported_freight')
        data,gl=export(records,cancelled.name)
        f=save_file('synthetic-saft-freight.xml',data,'Company',C,is_private=1)
        detail=frappe.get_all('Item Wise Tax Detail',filters={'parent':['in',parents]},fields=['name','parent','item_row','tax_row','amount','taxable_amount','rate'])
        e={'records':records,'cancelled':cancelled.name,'parents':parents,'gl':gl,'detail':detail,'file':f.name,'sha256':hashlib.sha256(data).hexdigest()}
        evidence=save_file('synthetic-saft-freight-evidence.json',frappe.as_json(e).encode(),'Company',C,is_private=1)
        frappe.db.set_default('runtime_saft_freight',evidence.name);frappe.db.commit()
        print('PASS native SAF-T freight: existing standard item route; Actual charges 25/15/12%, full/60%/no deduction, credits/pay/refund/cancellation; missing details, untaxed charge and unsupported shapes rejected; exact GL and XSD')
finally:frappe.db.rollback();frappe.destroy()
