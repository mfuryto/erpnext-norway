"""Native Period Closing Voucher, opening/closing GL and exported restore."""
import os,sys,json,hashlib
from decimal import Decimal
from pathlib import Path
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import saft,saft_builder as xml,vat
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Year End';OWNER='runtime-saft-year-end@example.invalid';NS={'s':xml.NS}

def ledger():
    return json.loads(frappe.as_json(frappe.get_all('GL Entry',filters={'company':C},fields=['name','account','debit','credit','posting_date','voucher_type','voucher_no','is_cancelled','cost_center','project'],order_by='name')))

def export():
    data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);root=etree.fromstring(data)
    rows=ledger()
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r['name'] for r in rows}
    for row in rows:
        for side in ('debit','credit'):
            values=root.xpath('.//s:Line[s:RecordID="'+row['name']+'"]/s:'+side.title()+'Amount/s:Amount/text()',namespaces=NS)
            assert sum((Decimal(v) for v in values),Decimal())==xml._money(row[side])
    for side in ('debit','credit'):
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in rows),Decimal())
    return data,root

try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_saft_year_end')).get_content())
        frappe.set_user(OWNER);_,root=export();assert ledger()==e['gl']
        pcv=frappe.get_doc('Period Closing Voucher',e['pcv']);assert pcv.docstatus==1 and pcv.gle_processing_status=='Completed'
        assert root.xpath('.//s:Account[s:AccountID="2050"]/s:ClosingCreditBalance/text()',namespaces=NS)==['400.00']
        file=frappe.get_doc('File',e['file']);assert file.is_private
        assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored native SAF-T year closing, exact PCV/GL IDs and amounts, zero P&L/closing equity400 and private XML')
    else:
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic year owner','send_welcome_email':0,'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'}]}).insert()
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SYE','country':'Norway','default_currency':'NOK','tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number,category,code in [('1920','balanseverdiForOmloepsmiddel','1920'),('2050','egenkapital','2050'),('3020','salgsinntekt','3000'),('4500','varekostnad','4500')]:
            account=frappe.get_doc('Account',a[number]);account.append(saft.MAPPING,{'year':2026,'category':category,'code':code});account.save()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert();frappe.set_user(OWNER)
        for date,debit,credit,amount in [('2026-06-01','4500','1920',600),('2026-06-02','1920','3020',1000)]:
            doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':date,'accounts':[{'account':a[debit],'debit_in_account_currency':amount,'cost_center':c.cost_center},{'account':a[credit],'credit_in_account_currency':amount,'cost_center':c.cost_center}]}).insert();doc.submit()
        _,before=export();assert before.xpath('.//s:Account[s:AccountID="2050"]/s:ClosingDebitBalance/text()',namespaces=NS)==['0.00']
        fiscal=frappe.db.get_value('Fiscal Year',{'year_start_date':'2026-01-01','year_end_date':'2026-12-31'})
        pcv=frappe.get_doc({'doctype':'Period Closing Voucher','company':C,'fiscal_year':fiscal,'closing_account_head':a['2050'],'transaction_date':'2026-11-08','period_start_date':'2026-01-01','period_end_date':'2026-12-31','remarks':'Synthetic native year closing'}).insert();pcv.submit();pcv.reload()
        # This pinned core's default setting uses its synchronous standard PCV.
        assert pcv.gle_processing_status=='Completed',pcv.gle_processing_status
        assert frappe.db.count('GL Entry',{'company':C,'voucher_type':pcv.doctype,'voucher_no':pcv.name})
        data,root=export()
        assert root.xpath('.//s:Account[s:AccountID="2050"]/s:ClosingCreditBalance/text()',namespaces=NS)==['400.00']
        for number in ('4500','3020'):
            assert root.xpath('.//s:Account[s:AccountID="'+number+'"]/s:ClosingDebitBalance/text()',namespaces=NS)==['0.00']
        transaction=root.xpath('.//s:Transaction[s:VoucherType="Period Closing Voucher"]',namespaces=NS);assert len(transaction)==1
        assert transaction[0].find('s:TransactionDate',NS).text=='2026-11-08'
        assert transaction[0].find('s:GLPostingDate',NS).text=='2026-12-31'
        assert not transaction[0].findall('.//s:TaxInformation',NS)
        frappe.db.savepoint('pending_year_closing');pcv.db_set('gle_processing_status','In Progress')
        try:export()
        except frappe.ValidationError as error:assert 'periodestenging' in str(error)
        else:raise AssertionError('Unfinished native closing was exported')
        frappe.db.rollback(save_point='pending_year_closing')
        # No future year borrows the current year's grouping list.
        try:saft.build(C,'2027-01-01','2027-12-31')
        except frappe.ValidationError as error:assert '2026' in str(error)
        else:raise AssertionError('Unqualified future-year grouping was accepted')
        file=save_file('synthetic-saft-year-end.xml',data,'Company',C,is_private=1)
        e={'pcv':pcv.name,'gl':ledger(),'file':file.name,'sha256':hashlib.sha256(data).hexdigest()}
        record=save_file('synthetic-saft-year-end-evidence.json',frappe.as_json(e).encode(),'Company',C,is_private=1)
        frappe.db.set_default('runtime_saft_year_end',record.name);frappe.db.commit()
        print('PASS native SAF-T year closing, actual PCV and GL IDs/gross, source versus posting dates, equity400/P&L0, unfinished closing and unqualified2027 rejected')
finally:frappe.db.rollback();frappe.destroy()
