"""Stored tax definitions/history, independent of period transactions, restored."""
import os,sys,json,hashlib
from pathlib import Path
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import saft,saft_builder as xml,vat
from erpnext_norway.saft_tax_catalog import read
from erpnext_norway.vat_catalog import CODE,RATE,DEDUCTION,SALES_CODE,PURCHASE_CODE
from erpnext_norway.vat_journal import BASE
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Tax Catalog';OWNER='runtime-saft-tax-catalog@example.invalid';NS={'s':xml.NS}
def export():
    data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);return data,etree.fromstring(data)
def check(root,e):
    codes=set(root.xpath('.//s:TaxCodeDetails/s:TaxCode/text()',namespaces=NS))
    templates=frappe.get_all('Item Tax Template',filters={'company':C},fields=[SALES_CODE,PURCHASE_CODE])
    stored={r.get(f) for r in templates for f in (SALES_CODE,PURCHASE_CODE) if r.get(f)}
    assert stored<=codes and {'33','31','LOCAL'}<=codes
    assert root.xpath('.//s:TaxCodeDetails[s:TaxCode="33"]/s:TaxPercentage/text()',namespaces=NS)==['6.00','12.00']
    assert root.xpath('.//s:TaxCodeDetails[s:TaxCode="31" and not(s:TaxPercentage)]',namespaces=NS)
    local=root.xpath('.//s:TaxCodeDetails[s:TaxCode="LOCAL"]',namespaces=NS)[0]
    assert local.xpath('s:StandardTaxCode/text()',namespaces=NS)==['NA']
    assert local.xpath('s:TaxPercentage/text()',namespaces=NS)==['7.50']
    assert local.xpath('s:BaseRate/text()',namespaces=NS)==['37.123456']
    assert root.xpath('.//s:TaxCodeDetails[s:TaxCode="87"]/s:BaseRate/text()',namespaces=NS)==['0.00']
    assert root.xpath('.//s:TaxCodeDetails[s:TaxCode="89"]/s:BaseRate/text()',namespaces=NS)==['0.00']
    assert not root.xpath('.//s:Line/s:TaxInformation',namespaces=NS)
    native=frappe.get_all('GL Entry',filters={'company':C,'posting_date':['between',['2026-01-01','2026-12-31']]},fields=['name','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in native}
    for side in ('debit','credit'):
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in native),Decimal())
    assert frappe.db.get_value('Item Tax Template',e['template'],'disabled')
def rejected(action,part,kind=frappe.ValidationError):
    frappe.db.savepoint('tax_catalog_reject')
    try:action()
    except kind as error:assert part in str(error),str(error)
    else:raise AssertionError('Incomplete or inferred tax catalog accepted')
    finally:frappe.db.rollback(save_point='tax_catalog_reject');frappe.clear_cache(user=OWNER);frappe.set_user(OWNER)
try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.db.get_default('runtime_saft_tax_catalog'));frappe.set_user(OWNER);_,root=export();check(root,e)
        proof=frappe.get_doc('File',e['file']);assert proof.is_private
        assert hashlib.sha256(Path(proof.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored complete stored tax catalog, unused/disabled definitions, historical6/current12, unknown nominal omitted, fractional deduction, native GL IDs/totals and private XML')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'STC','country':'Norway','default_currency':'NOK',
            'tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,
            'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2020-01-01'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number in ('1920','2070','2701','2703','2704','2709','2705','2715','4300'):
            category,group=('balanseverdiForOmloepsmiddel','1920') if number=='1920' else ('egenkapital','2050') if number=='2070' else ('varekostnad','4005') if number=='4300' else ('kortsiktigGjeld','2740')
            acc=frappe.get_doc('Account',a[number]);acc.append(saft.MAPPING,{'year':2026,'category':category,'code':group});acc.save()
        template=frappe.get_doc({'doctype':'Item Tax Template','company':C,'title':'Synthetic disabled native tax definition',
            'disabled':1,PURCHASE_CODE:'LOCAL',RATE:7.5,DEDUCTION:37.123456,
            'taxes':[{'tax_type':a['2715'],'tax_rate':7.5}]}).insert()
        if not frappe.db.exists('Fiscal Year','2020'):
            frappe.get_doc({'doctype':'Fiscal Year','year':'2020','year_start_date':'2020-01-01','year_end_date':'2020-12-31'}).insert()
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic tax catalog owner','send_welcome_email':0,
            'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        initial,empty=export();assert not empty.xpath('.//s:GeneralLedgerEntries',namespaces=NS)
        assert empty.xpath('.//s:TaxCodeDetails[s:TaxCode="LOCAL"]',namespaces=NS)
        history=[]
        for code,rate,account in [('33',6,'2703'),('31',0,'2701'),('87',25,'2704'),('89',12,'2709')]:
            doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2020-09-20','accounts':[
                {'account':a['2070'],'debit_in_account_currency':100},
                {'account':a[account],'credit_in_account_currency':100,CODE:code,RATE:rate}]}).insert();doc.submit();history.append(doc.name)
        current=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-09-20','accounts':[
            {'account':a['1920'],'debit_in_account_currency':100},{'account':a['2070'],'credit_in_account_currency':100}]}).insert();current.submit()
        e={'template':template.name,'history':history};data,root=export();check(root,e)
        def invalid_fraction():frappe.db.set_value('Item Tax Template',template.name,DEDUCTION,101);export()
        rejected(invalid_fraction,'fradragsandel')
        def catalog_does_not_open_transactions():
            doc=frappe.copy_doc(current);doc.accounts[0].set(CODE,'LOCAL');doc.accounts[0].set(RATE,7.5);doc.insert();doc.submit();export()
        rejected(catalog_does_not_open_transactions,'Eksportmappingen')
        def old_unknown_import_share():
            doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2020-09-20','bill_date':'2020-09-20','bill_no':'SYNTHETIC-LEGACY-IMPORT','accounts':[
                {'account':a['4300'],'debit_in_account_currency':1000,'cost_center':c.cost_center,CODE:'81',RATE:25},
                {'account':a['4300'],'credit_in_account_currency':1000,'cost_center':c.cost_center,CODE:'81',RATE:25},
                {'account':a['2705'],'credit_in_account_currency':250,CODE:'81',RATE:25,BASE:1000,DEDUCTION:100},
                {'account':a['2715'],'debit_in_account_currency':250,CODE:'81',RATE:25}]}).insert();doc.submit()
            out=next(r for r in doc.accounts if r.account==a['2705']);frappe.db.set_value('Journal Entry Account',out.name,DEDUCTION,0);export()
        rejected(old_unknown_import_share,'fradragsandel')
        def restricted_templates():
            frappe.set_user('Administrator');frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Item Tax Template','for_value':template.name,'apply_to_all_doctypes':1}).insert()
            frappe.set_user(OWNER);export()
        rejected(restricted_templates,'avgiftsmaler',frappe.PermissionError)
        def restricted_history():
            frappe.set_user('Administrator');frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Journal Entry','for_value':current.name,'apply_to_all_doctypes':1}).insert()
            frappe.set_user(OWNER);_,mapping=saft.account_catalog(C,2026,set(),saft.groups(2026));read(C,'2026-12-31',{},mapping)
        rejected(restricted_history,'kildebilag',frappe.PermissionError)
        proof=save_file('synthetic-saft-tax-catalog.xml',data,'Company',C,is_private=1)
        e.update(file=proof.name,sha256=hashlib.sha256(data).hexdigest());frappe.db.set_default('runtime_saft_tax_catalog',json.dumps(e));frappe.db.commit()
        print('PASS stored company tax catalog incl unused/disabled/unknown codes, historical6/current12 without retroactive rate, missing nominal omitted, exact fractional deduction, native ledger unchanged and partial access/unknown import share/new transactions rejected')
finally:frappe.destroy()
