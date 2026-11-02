"""Complete native chart: unused/groups/historical, permissions and restored XML."""
import os,sys,json,hashlib
from pathlib import Path
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import saft,saft_builder as xml,vat
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Account Catalog';OWNER='runtime-saft-accounts@example.invalid';NS={'s':xml.NS}
def export():
    data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);return data,etree.fromstring(data)
def check(root,e):
    nodes=root.xpath('.//s:GeneralLedgerAccounts/s:Account',namespaces=NS)
    rows=frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])
    assert {n.findtext('{'+xml.NS+'}AccountID') for n in nodes}=={r.account_number or r.name for r in rows}
    for key in ('unused','group','disabled','no_number'):
        n=root.xpath('.//s:Account[s:AccountID="'+e[key]+'"]',namespaces=NS)[0]
        assert n.xpath('s:GroupingCategory/text()|s:GroupingCode/text()',namespaces=NS)==['NA','NA']
        assert n.xpath('s:OpeningDebitBalance/text()|s:ClosingDebitBalance/text()',namespaces=NS)==['0.00','0.00']
    assert root.xpath('.//s:Account[s:AccountID="9871"]/s:GroupingCode/text()',namespaces=NS)==['4500']
    assert root.xpath('.//s:Account[s:AccountID="4500"]/s:GroupingCode/text()',namespaces=NS)==['4500']
    native=frappe.get_all('GL Entry',filters={'company':C},fields=['name','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in native}
    for side in ('debit','credit'):
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in native),Decimal())
    assert frappe.db.get_value('Account',{'company':C,'account_number':'9871'},'disabled')
def rejected(action,part,kind=frappe.ValidationError):
    frappe.db.savepoint('catalog_reject')
    try:action()
    except kind as error:assert part in str(error),str(error)
    else:raise AssertionError('Incomplete or ambiguous account catalog accepted')
    finally:frappe.db.rollback(save_point='catalog_reject')
try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.db.get_default('runtime_saft_accounts'));frappe.set_user(OWNER)
        _,root=export();check(root,e)
        proof=frappe.get_doc('File',e['file']);assert proof.is_private
        assert hashlib.sha256(Path(proof.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored complete native account catalog, groups/unused/disabled/history, NA only unused, exact GL totals/IDs and private XML')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SAC','country':'Norway','default_currency':'NOK',
            'tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,
            'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        parent=frappe.db.get_value('Account',a['4500'],'parent_account')
        history=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic historical expense','account_number':'9871','parent_account':parent}).insert()
        unnamed=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic unused without account number','parent_account':parent}).insert()
        for name,category,code in [(a['1920'],'balanseverdiForOmloepsmiddel','1920'),(a['2070'],'egenkapital','2050'),
                                  (a['4500'],'varekostnad','4500'),(history.name,'varekostnad','4500')]:
            acc=frappe.get_doc('Account',name);acc.append(saft.MAPPING,{'year':2026,'category':category,'code':code});acc.save()
        inactive=frappe.get_doc('Account',a['6551']);inactive.disabled=1;inactive.save()
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic account catalog owner','send_welcome_email':0,
            'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        from frappe.core.doctype.data_export.exporter import DataExporter
        frappe.local.response=frappe._dict()
        native=DataExporter(doctype='Account',all_doctypes=False,with_data=True,
            select_columns={'Account':['name','account_number','is_group','disabled']},file_type='CSV',
            filters={'company':C},export_without_column_meta=True)
        native.build_response()
        assert {r.name for r in native.data}==set(frappe.get_all('Account',filters={'company':C},pluck='name'))
        assert any(r.is_group for r in native.data) and any(r.disabled for r in native.data)
        print('PASS native owner Account Data Export already contains the complete chart, groups and disabled accounts')
        empty,_=export();assert b'GeneralLedgerAccounts' in empty and b'GeneralLedgerEntries' not in empty
        doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-09-20','accounts':[
            {'account':a['1920'],'debit_in_account_currency':100},{'account':a['2070'],'credit_in_account_currency':100},
            {'account':history.name,'debit_in_account_currency':25,'cost_center':c.cost_center},
            {'account':history.name,'credit_in_account_currency':25,'cost_center':c.cost_center}]}).insert();doc.submit()
        historic=frappe.get_doc('Account',history.name);historic.disabled=1;historic.save()
        group=frappe.db.get_value('Account',{'company':C,'is_group':1,'account_number':['is','not set']},'name')
        e={'unused':'6500','disabled':'6551','group':group,'no_number':unnamed.name}
        data,root=export();check(root,e)
        def duplicate_id():frappe.db.set_value('Account',unnamed.name,'account_number','1920');export()
        rejected(duplicate_id,'unik',xml.SaftExportError)
        def missing_used_mapping():frappe.db.delete('Norwegian SAF-T Mapping',{'parent':history.name});export()
        rejected(missing_used_mapping,'kontokobling')
        def bad_unused_mapping():
            acc=frappe.get_doc('Account',a['6500']);acc.append(saft.MAPPING,{'year':2026,'category':'unknown','code':'unknown'});acc.save();export()
        rejected(bad_unused_mapping,'kontokobling')
        def partial_permission():
            frappe.set_user('Administrator');frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Account','for_value':a['1920'],'apply_to_all_doctypes':1}).insert()
            frappe.set_user(OWNER);saft.account_catalog(C,2026,set(),saft.groups(2026))
        rejected(partial_permission,'kontoplanen',frappe.PermissionError)
        frappe.clear_cache(user=OWNER);frappe.set_user(OWNER)
        proof=save_file('synthetic-saft-accounts.xml',data,'Company',C,is_private=1)
        e.update(file=proof.name,sha256=hashlib.sha256(data).hexdigest());frappe.db.set_default('runtime_saft_accounts',json.dumps(e));frappe.db.commit()
        print('PASS complete native account catalog including unused/groups/disabled/history, no guessed grouping, source GL unchanged, duplicate/missing mapping and partial permission rejected')
finally:frappe.destroy()
