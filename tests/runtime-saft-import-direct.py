"""Native direct input import VAT: official exceptions14/15, never invented bases."""
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
frappe.connect(); frappe.set_user('Administrator')
from erpnext_norway import saft, saft_builder as xml, vat
from erpnext_norway.vat_catalog import CODE, RATE
from erpnext_norway.vat_journal import BASE
from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
from frappe.utils.file_manager import save_file
C='Runtime Direct Import VAT'; OWNER='runtime-saft-import@example.invalid'; NS={'s':xml.NS}


def export(start='2026-01-01'):
    data=saft.build(C,start,'2026-12-31'); xml.validate_saf_t(data)
    return data,etree.fromstring(data)


def check(root, evidence):
    for name,code,amount,credit,count in evidence['documents']:
        infos=root.xpath('.//s:Line[s:SourceDocumentID="'+name+'"]/s:TaxInformation',namespaces=NS)
        assert len(infos)==count,(name,len(infos),count)
        for info in infos:
            assert info.xpath('string(s:TaxCode)',namespaces=NS)==code
            assert not info.xpath('s:TaxBase',namespaces=NS)
            assert info.getparent().xpath('string(s:AccountID)',namespaces=NS)==('2715' if code=='14' else '2716')
            amounts=info.xpath('s:CreditTaxAmount/s:Amount/text()|s:DebitTaxAmount/s:Amount/text()',namespaces=NS)
            assert amounts==[amount],amounts
            side='CreditTaxAmount' if info.getparent().xpath('s:CreditAmount',namespaces=NS) else 'DebitTaxAmount'
            assert info.xpath('s:'+side+'/s:Amount/text()',namespaces=NS)==[amount]
        if count==1:
            side='CreditTaxAmount' if credit else 'DebitTaxAmount'
            assert Decimal(infos[0].xpath('string(s:'+side+'/s:Amount)',namespaces=NS))==Decimal(amount)
        else:
            assert len(infos[0].xpath('../s:CreditAmount',namespaces=NS))+len(infos[1].xpath('../s:CreditAmount',namespaces=NS))==1
    native=frappe.get_all('GL Entry',filters={'company':C},fields=['name','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in native}
    for side in ('debit','credit'):
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in native),Decimal())


try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.db.get_default('runtime_saft_direct_import'))
        frappe.set_user(OWNER); _,root=export(); check(root,e)
        proof=frappe.get_doc('File',e['file'])
        assert proof.is_private and hashlib.sha256(Path(proof.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored SAF-T direct import14/15, native reversal/cancellation, exact GL IDs/totals and private XML')
    else:
        company=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SDI','country':'Norway',
            'default_currency':'NOK','tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,
            'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        accounts={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number in ('1920','2715','2716','2705','2070'):
            acc=frappe.get_doc('Account',accounts[number])
            category,group = ('balanseverdiForOmloepsmiddel','1920') if number=='1920' else (
                ('egenkapital','2050') if number=='2070' else ('kortsiktigGjeld','2740'))
            acc.append(saft.MAPPING,{'year':2026,'category':category,'code':group}); acc.save()
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic SAF-T import',
            'send_welcome_email':0,'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER); assert 'System Manager' not in frappe.get_roles()
        evidence={'documents':[]}
        for code,rate,number,amount in [('14',25,'2715',125),('15',15,'2716',90)]:
            doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-09-20',
                'bill_date':'2026-09-20','bill_no':'SYNTHETIC-DIRECT-'+code,'accounts':[
                    {'account':accounts[number],'debit_in_account_currency':amount,CODE:code,RATE:rate},
                    {'account':accounts['1920'],'credit_in_account_currency':amount}]}).insert(); doc.submit()
            evidence['documents'].append([doc.name,code,f'{amount:.2f}',False,1])
            reversal=make_reverse_journal_entry(doc.name); reversal.posting_date='2026-10-20'
            reversal.insert(); reversal.submit()
            evidence['documents'].append([reversal.name,code,f'{amount:.2f}',True,1])
            cancelled=frappe.copy_doc(doc); cancelled.bill_no='SYNTHETIC-CANCEL-'+code
            cancelled.insert(); cancelled.submit(); cancelled.cancel()
            evidence['documents'].append([cancelled.name,code,f'{amount:.2f}',False,2])
        data,root=export(); check(root,evidence)
        _,opening=export('2026-11-01')
        assert not opening.xpath('.//s:TaxInformation',namespaces=NS)
        # Reject wrong stored rate/base and unsupported self-assessed codes.
        original=frappe.get_doc('Journal Entry',evidence['documents'][0][0])
        item=original.accounts[0]
        for field,value in [(RATE,15),(BASE,500),(CODE,'81')]:
            frappe.db.savepoint('direct_import_bad_metadata')
            frappe.db.set_value('Journal Entry Account',item.name,field,value)
            try: export()
            except frappe.ValidationError as error: assert original.name in str(error)
            else: raise AssertionError('Unqualified import metadata exported')
            frappe.db.rollback(save_point='direct_import_bad_metadata')
        frappe.db.savepoint('direct_import_wrong_gl')
        row=frappe.db.get_value('GL Entry',{'voucher_no':original.name,'account':item.account},'name')
        frappe.db.set_value('GL Entry',row,'debit',126)
        try: export()
        except frappe.ValidationError as error: assert original.name in str(error)
        else: raise AssertionError('Mismatched VAT GL exported')
        frappe.db.rollback(save_point='direct_import_wrong_gl')
        # A stored VAT code must not disappear merely because its account was wrong.
        frappe.db.savepoint('direct_import_wrong_account')
        wrong=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-09-20','accounts':[
            {'account':accounts['1920'],'debit_in_account_currency':17,CODE:'14',RATE:25},
            {'account':accounts['2070'],'credit_in_account_currency':17}]}).insert(); wrong.submit()
        try: export()
        except frappe.ValidationError as error: assert wrong.name in str(error)
        else: raise AssertionError('Stored VAT code silently omitted on a non-VAT account')
        frappe.db.rollback(save_point='direct_import_wrong_account')
        proof=save_file('synthetic-saft-direct-import.xml',data,'Company',C,is_private=1)
        evidence.update(file=proof.name,sha256=hashlib.sha256(data).hexdigest())
        frappe.db.set_default('runtime_saft_direct_import',json.dumps(evidence)); frappe.db.commit()
        print('PASS SAF-T import14/15 on native VAT lines, no fabricated base, source/reversal/cancellation and unsupported metadata rejection')
finally:
    frappe.destroy()
