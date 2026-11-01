"""Actual customs bases, recorded deduction and both native VAT directions."""
import hashlib
import json
import os
from pathlib import Path
import sys
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.local.lang='en'
from erpnext_norway import saft, saft_builder as xml, vat
from erpnext_norway.vat_catalog import CODE,RATE,DEDUCTION
from erpnext_norway.vat_journal import BASE
from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Customs';OWNER='runtime-saft-customs@example.invalid';NS={'s':xml.NS}


def export(start='2026-01-01',end='2026-12-31'):
    data=saft.build(C,start,end);xml.validate_saf_t(data)
    return data,etree.fromstring(data)


def check(root,evidence):
    native=frappe.get_all('GL Entry',filters={'company':C},fields=['name','account','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in native}
    for side in ('debit','credit'):
        total=sum((xml._money(r[side]) for r in native),Decimal())
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==total
        for row in native:
            amounts=root.xpath('.//s:Line[s:RecordID="'+row.name+'"]/s:'+side.title()+'Amount/s:Amount/text()',namespaces=NS)
            assert sum(map(Decimal,amounts),Decimal())==xml._money(row[side])
    for doc in evidence['documents']:
        infos=root.xpath('.//s:Line[s:SourceDocumentID="'+doc['name']+'"]/s:TaxInformation',namespaces=NS)
        assert len(infos)==(4 if doc['cancelled'] else 2),(doc,len(infos))
        for info in infos:
            assert info.xpath('string(s:TaxCode)',namespaces=NS)==doc['code']
            assert Decimal(info.xpath('string(s:TaxBase)',namespaces=NS))==Decimal(doc['base'])
            assert info.getparent().xpath('string(s:AccountID)',namespaces=NS)=='4300'
            side='Credit' if info.getparent().xpath('s:CreditAmount',namespaces=NS) else 'Debit'
            assert info.xpath('s:'+side+'TaxAmount',namespaces=NS)
            assert Decimal(info.getparent().xpath('string(s:Analysis/s:'+side+'AnalysisAmount/s:Amount)',namespaces=NS))==Decimal(info.getparent().xpath('string(s:'+side+'Amount/s:Amount)',namespaces=NS))
        vat_accounts=[evidence['accounts'][v] for v in ('2705','2715','2706','2716')]
        posted=frappe.get_all('GL Entry',filters={'company':C,'voucher_no':doc['name'],'account':['in',vat_accounts]},fields=['debit','credit'])
        # Compare gross input/output amounts even for a cancelled net-zero voucher.
        for side in ('debit','credit'):
            amounts=root.xpath('.//s:Line[s:SourceDocumentID="'+doc['name']+'"]/s:TaxInformation/s:'+side.title()+'TaxAmount/s:Amount/text()',namespaces=NS)
            assert sum(map(Decimal,amounts),Decimal())==sum((xml._money(r[side]) for r in posted),Decimal())
    for code,rates in [('81',['60.00','100.00']),('83',['60.00','100.00']),('82',['0.00']),('84',['0.00'])]:
        assert root.xpath('.//s:TaxCodeDetails[s:TaxCode="'+code+'"]/s:BaseRate/text()',namespaces=NS)==rates
    for number in ('2705','2715','2706','2716'):
        assert not root.xpath('.//s:Line[s:AccountID="'+number+'"]/s:TaxInformation',namespaces=NS)


def rejected(action,text=None):
    frappe.db.savepoint('customs_reject')
    try:action()
    except frappe.ValidationError as error:
        if text:assert text in str(error),str(error)
        frappe.db.rollback(save_point='customs_reject')
    else:raise AssertionError('Unqualified customs treatment accepted')

try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_saft_customs'))
        frappe.set_user(OWNER);_,root=export();check(root,evidence)
        proof=frappe.get_doc('File',evidence['file']);assert proof.is_private
        assert hashlib.sha256(Path(proof.get_full_path()).read_bytes()).hexdigest()==evidence['sha256']
        print('PASS restored SAF-T customs81-84, recorded60/100/0 percent, native merged/separate bases, reversal/cancellation, exact GL IDs/gross VAT/dimensions and private XML')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SCU','country':'Norway','default_currency':'NOK',
            'tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',
            vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number in ('4300','2705','2715','2706','2716'):
            acc=frappe.get_doc('Account',a[number]);category,group=('varekostnad','4005') if number=='4300' else ('kortsiktigGjeld','2740')
            acc.append(saft.MAPPING,{'year':2026,'category':category,'code':group});acc.save()
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic customs owner','send_welcome_email':0,
            'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        merge=frappe.db.get_single_value('Accounts Settings','merge_similar_account_heads')
        evidence={'accounts':a,'documents':[]};sources=[]
        for merged in (0,1):
            frappe.set_user('Administrator');frappe.db.set_single_value('Accounts Settings','merge_similar_account_heads',merged)
            frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
            for code,rate,base,out,input_,share,on,inn in [
                    ('81',25,4700,1175,1175,100,'2705','2715'),('81',25,4700,1175,705,60,'2705','2715'),
                    ('82',25,4700,1175,0,0,'2705','2715'),('83',15,2000,300,300,100,'2706','2716'),
                    ('83',15,2000,300,180,60,'2706','2716'),('84',15,2000,300,0,0,'2706','2716')]:
                rows=[{'account':a['4300'],'debit_in_account_currency':base,'cost_center':c.cost_center,CODE:code,RATE:rate},
                    {'account':a['4300'],'credit_in_account_currency':base,'cost_center':c.cost_center,CODE:code,RATE:rate},
                    {'account':a[on],'credit_in_account_currency':out,CODE:code,RATE:rate,BASE:base,DEDUCTION:share}]
                if input_:rows.append({'account':a[inn],'debit_in_account_currency':input_,CODE:code,RATE:rate})
                if out!=input_:rows.append({'account':a['4300'],'debit_in_account_currency':out-input_,'cost_center':c.cost_center})
                doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-09-20','bill_date':'2026-09-20',
                    'bill_no':'SYNTHETIC-SAF-T-CUSTOMS-'+str(len(evidence['documents'])),'accounts':rows}).insert();doc.submit();sources.append(doc.name)
                cost_gl=frappe.get_all('GL Entry',filters={'voucher_no':doc.name,'account':a['4300']},fields=['debit','credit'])
                assert any(r.debit and r.credit for r in cost_gl)==bool(merged),(merged,cost_gl)
                reverse=make_reverse_journal_entry(doc.name);reverse.posting_date=reverse.bill_date='2026-10-20'
                reverse.bill_no='SYNTHETIC-REVERSED-DECLARATION';reverse.insert();reverse.submit()
                assert next(r.get(BASE) for r in reverse.accounts if r.account==a[on])==-base
                assert next(r.get(DEDUCTION) for r in reverse.accounts if r.account==a[on])==share
                for entry in (doc,reverse):
                    evidence['documents'].append({'name':entry.name,'code':code,'base':base,'cancelled':False})
                cancelled=frappe.copy_doc(doc);cancelled.bill_no='SYNTHETIC-CANCELLED-CUSTOMS';cancelled.insert();cancelled.submit();cancelled.cancel()
                evidence['documents'].append({'name':cancelled.name,'code':code,'base':base,'cancelled':True})
        frappe.set_user('Administrator');frappe.db.set_single_value('Accounts Settings','merge_similar_account_heads',merge);frappe.set_user(OWNER)
        data,root=export();check(root,evidence)
        _,opening=export('2026-11-01');assert not opening.xpath('.//s:TaxInformation',namespaces=NS)
        original=frappe.get_doc('Journal Entry',sources[0]);output=next(r for r in original.accounts if r.account==a['2705'])
        for field,value in ((DEDUCTION,0),(DEDUCTION,101),(RATE,15),(BASE,4701),(BASE,4700.001)):
            def corrupt(field=field,value=value):
                frappe.db.set_value('Journal Entry Account',output.name,field,value);export()
            rejected(corrupt,original.name)
        basis=next(r for r in original.accounts if r.account==a['4300'])
        def missing_basis_code():frappe.db.set_value('Journal Entry Account',basis.name,CODE,'0');export()
        rejected(missing_basis_code,original.name)
        gl=frappe.db.get_value('GL Entry',{'voucher_no':original.name,'account':a['2715'],'debit':['>',0]},'name')
        def wrong_vat_gl():frappe.db.set_value('GL Entry',gl,'debit',1176);export()
        rejected(wrong_vat_gl,original.name)
        def missing_share():
            doc=frappe.copy_doc(original);next(r for r in doc.accounts if r.account==a['2705']).set(DEDUCTION,0);doc.insert();doc.submit()
        rejected(missing_share,'documented deduction percent')
        def legacy_unknown_share():
            doc=frappe.copy_doc(original);doc.insert();doc.submit()
            old_output=next(r for r in doc.accounts if r.account==a['2705'])
            # Simulate the absent field on an older posting; never infer its share.
            frappe.db.set_value('Journal Entry Account',old_output.name,DEDUCTION,0)
            reverse=make_reverse_journal_entry(doc.name);reverse.posting_date=reverse.bill_date='2026-10-20'
            reverse.insert();reverse.save();reverse.submit()
            assert reverse.docstatus==1
            assert next(r.get(DEDUCTION) for r in reverse.accounts if r.account==a['2705'])==0
            export()
        rejected(legacy_unknown_share,'fradragsandel')
        frappe.db.savepoint('customs_closed_period');frappe.set_user('Administrator')
        frappe.get_doc({'doctype':'Accounting Period','company':C,'period_name':'Synthetic customs share lock',
            'start_date':'2026-09-01','end_date':'2026-09-30','closed_documents':[{'document_type':'Journal Entry','closed':1}]}).insert()
        frappe.set_user(OWNER)
        def edit_closed():
            doc=frappe.get_doc('Journal Entry',original.name);next(r for r in doc.accounts if r.account==a['2705']).set(DEDUCTION,60);doc.save()
        rejected(edit_closed)
        frappe.db.rollback(save_point='customs_closed_period')
        def missing_cancelled_gross():
            cancelled=next(d for d in evidence['documents'] if d['cancelled'])
            rows=frappe.get_all('GL Entry',filters={'voucher_no':cancelled['name'],'account':a['4300'],
                'remarks':'On cancellation of '+cancelled['name']},fields=['name','debit','credit'])
            assert len(rows)==2 and sum(r.debit-r.credit for r in rows)==0
            # Test-only corruption removes both gross basis sides without changing net GL.
            for row in rows:frappe.db.set_value('GL Entry',row.name,{'debit':0,'credit':0})
            export()
        rejected(missing_cancelled_gross,'brutto grunnlagsføringer mangler')
        frappe.clear_document_cache('Accounts Settings','Accounts Settings')
        proof=save_file('synthetic-saft-customs.xml',data,'Company',C,is_private=1)
        evidence.update(file=proof.name,sha256=hashlib.sha256(data).hexdigest())
        frappe.db.set_default('runtime_saft_customs',json.dumps(evidence));frappe.db.commit()
        print('PASS SAF-T customs81-84, native merge off/on and reversal, native cancellation, recorded60/100/0 percent, exact gross GL/VAT and rejects missing metadata/GL/bases/closed-period edit/missing gross cancellation bases')
finally:frappe.destroy()
