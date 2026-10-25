"""Actual concurrent native submissions; retry only a native transaction conflict."""
import os,sys,json,subprocess,tempfile
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import vat
from erpnext_norway.vat_quarterly import JOURNAL,QUARTERLY
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
C='Runtime Quarterly Race';OWNER='runtime-vat-owner@example.invalid'
F={'company':C,'from_date':'2026-07-01','to_date':'2026-09-30','return_type':QUARTERLY}
WORKER='''
import os,sys,time
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('runtime-vat-owner@example.invalid')
try:
    frappe.db.sql('SET innodb_lock_wait_timeout=5')
    doc=frappe.get_doc('Purchase Invoice',sys.argv[1])
    print('READY',flush=True)
    while not Path(sys.argv[2]).exists():time.sleep(.01)
    try:
        doc.submit();frappe.db.commit();print('SUBMITTED',flush=True)
    except (frappe.QueryDeadlockError,frappe.QueryTimeoutError):
        frappe.db.rollback();print('NATIVE_TRANSACTION_RETRY',flush=True)
finally:frappe.destroy()
'''
def result():
    rows=[row for row in collect(F) if row['portal']]
    return tuple(round(sum(row[key] for row in rows),2) for key in ('base_amount','output_vat','input_vat'))
try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_quarterly_race'))
        assert all(frappe.db.get_value('Purchase Invoice',name,'docstatus')==1 for name in evidence['invoices'])
        assert result()==(2099.99,525,0)
        assert frappe.db.count('Journal Entry',{'company':C,JOURNAL:1,'docstatus':1})==1
        print('PASS restored concurrent quarterly sources and single native525 VAT adjustment')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'QVR','country':'Norway','default_currency':'NOK','tax_id':'999999987','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        template=frappe.db.get_value('Item Tax Template',{'company':C,'title':'Tjenestekjøp fra utlandet – kvartalsgrunnlag før MVA-registrering'})
        supplier=frappe.db.get_value('Supplier',{'supplier_name':'Synthetic quarterly supplier A'})
        assert supplier
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER)
        def invoice(amount,number,posting='2026-09-16',bill='2026-09-16'):
            return frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier,'currency':'NOK','conversion_rate':1,'posting_date':posting,'bill_date':bill,'set_posting_time':1,'bill_no':'SYNTHETIC-QUARTER-RACE-'+str(number),'due_date':'2026-10-31','disable_rounded_total':1,'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':amount,'expense_account':a['4500'],'cost_center':c.cost_center,'item_tax_template':template}]}).insert()
        first=invoice(1499.99,0);first.submit()
        drafts=[invoice(300,n) for n in (1,2)]
        frappe.db.commit()
        with tempfile.TemporaryDirectory(prefix='native-quarter-race-') as directory:
            release=Path(directory)/'release'
            workers=[subprocess.Popen([sys.executable,'-c',WORKER,doc.name,str(release)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for doc in drafts]
            for worker in workers:assert worker.stdout.readline().strip()=='READY'
            release.touch()
            conflicts=[]
            for doc,worker in zip(drafts,workers):
                out,err=worker.communicate(timeout=35)
                assert worker.returncode==0,(out,err)
                if 'NATIVE_TRANSACTION_RETRY' in out:conflicts.append(doc.name)
                else:assert 'SUBMITTED' in out,(out,err)
        # This is a fresh ordinary submit after a rejected native transaction,
        # not an application retry loop or a forced financial insert.
        frappe.db.rollback()
        for name in conflicts:
            doc=frappe.get_doc('Purchase Invoice',name);assert doc.docstatus==0
            doc.submit();frappe.db.commit()
        assert result()==(2099.99,525,0)
        assert frappe.db.count('Journal Entry',{'company':C,JOURNAL:1,'docstatus':1})==1
        print('PASS actual concurrent native submissions produce2099.99 base/525 VAT and one adjustment; native transaction conflicts leave a retryable draft without duplicate tax')
        frappe.set_user('Administrator')
        frappe.get_doc({'doctype':'Accounting Period','company':C,'period_name':'Synthetic closed quarterly period','start_date':'2026-07-01','end_date':'2026-09-30','closed_documents':[{'document_type':'Journal Entry','closed':1}]}).insert()
        frappe.set_user(OWNER);frappe.db.savepoint('quarter_closed')
        late=invoice(100,3,posting='2026-10-16')
        try:late.submit()
        except frappe.ValidationError as error:
            assert type(error).__name__=='ClosedAccountingPeriod',type(error).__name__
            frappe.db.rollback(save_point='quarter_closed')
        else:raise AssertionError('Closed VAT quarter received a silent financial adjustment')
        assert result()==(2099.99,525,0)
        frappe.db.set_default('runtime_quarterly_race',json.dumps({'invoices':[first.name,*[doc.name for doc in drafts]]}));frappe.db.commit()
        print('PASS native closed-quarter control rejects a late bill requiring VAT adjustment without rewriting the closed ledger')
finally:frappe.destroy()
