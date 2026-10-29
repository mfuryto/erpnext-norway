"""Native reverse-charge NOK source facts, XML directions and exported restore."""
import hashlib
import json
import os
from pathlib import Path
import sys
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import saft, vat
from erpnext_norway import saft_builder as xml
from erpnext_norway.vat_catalog import DEDUCTION, CODE
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Services'
OWNER='runtime-vat-owner@example.invalid'
NS={'s':xml.NS}


def export():
    content=saft.build(C,'2026-01-01','2026-12-31')
    xml.validate_saf_t(content)
    return content, etree.fromstring(content)


def check(root, examples):
    for e in examples:
        lines=root.xpath('.//s:Line[s:SourceDocumentID="'+e['name']+'"]',namespaces=NS)
        info=[i for line in lines for i in line.xpath('s:TaxInformation',namespaces=NS)]
        assert len(info)==e['count'],(e, len(info))
        for i in info:
            assert i.xpath('string(s:TaxCode)',namespaces=NS)==e['code']
            assert Decimal(i.xpath('string(s:TaxBase)',namespaces=NS))==Decimal(str(e['base']))
        amounts=[(i[0].tag.rsplit('}',1)[-1],Decimal(i[0][0].text)) for i in
            [v.xpath('s:DebitTaxAmount|s:CreditTaxAmount',namespaces=NS) for v in info]]
        assert sorted(amounts)==sorted((direction,Decimal(str(e['tax']))) for direction in e['directions']),(e,amounts)
        assert not any(line.xpath('s:TaxInformation',namespaces=NS) for line in lines
            if line.xpath('string(s:AccountID)',namespaces=NS) in ('2704','2714','2709','2718'))
    expected=frappe.get_all('GL Entry',filters={'company':C},fields=['name','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in expected}
    assert Decimal(root.xpath('string(.//s:TotalDebit)',namespaces=NS))==sum((xml._money(r.debit) for r in expected),Decimal())
    assert Decimal(root.xpath('string(.//s:TotalCredit)',namespaces=NS))==sum((xml._money(r.credit) for r in expected),Decimal())


def reject_mismatches(examples):
    first=frappe.get_doc('Purchase Invoice',examples[0]['name'])
    detail=frappe.db.get_value('Item Wise Tax Detail',{'parent':first.name,'amount':['>',0]},'name')
    assert detail
    for doctype, name, field, value, message in [
            ('Item Wise Tax Detail',detail,'amount',0,'MVA-kontoer'),
            ('Purchase Invoice Item',first.items[0].name,CODE,'0','avgiftskode')]:
        frappe.db.savepoint('saft_service_mismatch')
        frappe.db.set_value(doctype,name,field,value)
        try: export()
        except frappe.ValidationError as error: assert message in str(error),str(error)
        else: raise AssertionError('Incorrect reverse-charge source accepted')
        frappe.db.rollback(save_point='saft_service_mismatch')


try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_saft_services'))
        frappe.set_user(OWNER)
        content,root=export()
        check(root,evidence['examples'])
        reject_mismatches(evidence['examples'])
        proof=frappe.get_doc('File',evidence['file'])
        assert proof.is_private and hashlib.sha256(Path(proof.get_full_path()).read_bytes()).hexdigest()==evidence['sha256']
        print('PASS restored SAF-T reverse-charge25/12, full/partial/zero, native credits/cancellation and private XML proof')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'RSS','country':'Norway',
            'default_currency':'NOK','tax_id':'999999980','phone_no':'90000000','enable_perpetual_inventory':0,
            'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number in ('2400','2704','2714','2709','2718','4500'):
            account=frappe.get_doc('Account',a[number])
            account.append(saft.MAPPING,{'year':2026,'category':'varekostnad' if number=='4500' else 'kortsiktigGjeld','code':'4500' if number=='4500' else '2740' if number!='2400' else '2400'})
            account.save()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        supplier=frappe.get_all('Supplier',pluck='name')[0]
        frappe.set_user(OWNER)
        assert 'System Manager' not in frappe.get_roles()
        examples=[]
        for rate in (25,12):
            for percent in (100,60,0):
                code=('86' if percent else '87') if rate==25 else ('88' if percent else '89')
                doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier,
                    'posting_date':'2026-09-16','set_posting_time':1,'bill_date':'2026-09-16','bill_no':'SYNTHETIC-SAFT-SERVICE',
                    'due_date':'2026-10-31','currency':'NOK','conversion_rate':1,'disable_rounded_total':1,
                    'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':2,'rate':500,
                        'expense_account':a['4500'],'cost_center':c.cost_center,
                        'item_tax_template':f'Tjenestekjøp fra utlandet – MVA {rate} % – 100 % fradrag - RSS',DEDUCTION:percent}]})
                doc.insert()
                save_file('synthetic-saft-service.pdf',frappe.get_print(doc.doctype,doc.name,as_pdf=True),doc.doctype,doc.name,is_private=1)
                doc.submit()
                tax=rate*(100-percent)/10
                examples.append({'name':doc.name,'count':1,'code':code,'base':1000+tax,'tax':tax,'directions':['CreditTaxAmount' if tax else 'DebitTaxAmount']})
                credit=make_return_doc('Purchase Invoice',doc.name)
                credit.posting_date=credit.bill_date='2026-10-16'
                credit.set_posting_time=1
                credit.bill_no='SYNTHETIC-SAFT-SERVICE-CREDIT'
                credit.items[0].qty=-1
                credit.insert()
                save_file('synthetic-saft-service-credit.pdf',frappe.get_print(credit.doctype,credit.name,as_pdf=True),credit.doctype,credit.name,is_private=1)
                credit.submit()
                examples.append({'name':credit.name,'count':1,'code':code,'base':(1000+tax)/2,'tax':tax/2,'directions':['DebitTaxAmount' if tax else 'CreditTaxAmount']})
                if percent==60:
                    credit.cancel()
                    examples[-1].update(count=2,directions=['DebitTaxAmount','CreditTaxAmount'])
        content,root=export()
        check(root,examples)
        reject_mismatches(examples)
        proof=save_file('synthetic-saft-services.xml',content,'Company',C,is_private=1)
        frappe.db.set_default('runtime_saft_services',json.dumps({'examples':examples,'file':proof.name,'sha256':hashlib.sha256(content).hexdigest()}))
        frappe.db.commit()
        print('PASS native SAF-T reverse-charge25/12 full100/partial60/zero, basis/net VAT directions, half-credit, cancellation and gross-account mismatch rejection')
finally:
    frappe.db.rollback()
    frappe.destroy()
