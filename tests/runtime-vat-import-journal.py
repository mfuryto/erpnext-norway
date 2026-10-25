"""Native documented import journals: correct copied basis, never calculate VAT."""
import os,sys,json,hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect()
frappe.set_user('Administrator')
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE,RATE
from erpnext_norway.vat_journal import BASE
from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from frappe.utils.file_manager import save_file
C='Runtime Import Journals';OWNER='runtime-vat-owner@example.invalid'
def report(start,end):
    return collect({'company':C,'from_date':start,'to_date':end})
def totals(rows):
    return tuple(round(sum(r[k] for r in rows),2) for k in ('base_amount','output_vat','input_vat'))
def ledger(name):
    return sorted((r.account,float(r.debit),float(r.credit)) for r in frappe.get_all('GL Entry',
        filters={'company':C,'voucher_no':name,'is_cancelled':0},fields=['account','debit','credit']))
try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_import_journals'))
        for saved in evidence:
            source=frappe.get_doc('Journal Entry',saved['source'])
            reverse=frappe.get_doc('Journal Entry',saved['reverse'])
            assert source.docstatus==reverse.docstatus==1 and reverse.reversal_of==source.name
            assert next(r.get(BASE) for r in source.accounts if r.get(BASE))==saved['base']
            assert next(r.get(BASE) for r in reverse.accounts if r.get(BASE))==-saved['base']
            assert ledger(source.name)==[tuple(r) for r in saved['ledger']]
            assert ledger(reverse.name)==[tuple(r) for r in saved['reverse_ledger']]
            path=Path(frappe.get_doc('File',saved['file']).get_full_path())
            assert hashlib.sha256(path.read_bytes()).hexdigest()==saved['sha256']
        assert totals(report('2026-09-01','2026-09-30'))==(18100,4125,2180)
        assert totals(report('2026-10-01','2026-10-31'))==(-18100,-4125,-2180)
        assert totals(report('2026-09-01','2026-10-31'))==(0,0,0)
        print('PASS restored native import journal reversal links, signed bases, ledger and private declaration bytes')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'IMJ','country':'Norway',
            'default_currency':'NOK','tax_id':'999999987','enable_perpetual_inventory':0,
            'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        evidence=[]
        for code,rate,base,output,input_,out_account,in_account in [
                ('81',25,4700,1175,1175,'2705','2715'),
                ('81',25,4700,1175,705,'2705','2715'),
                ('82',25,4700,1175,0,'2705','2715'),
                ('83',15,2000,300,300,'2706','2716'),
                ('84',15,2000,300,0,'2706','2716')]:
            rows=[{'account':a[out_account],'credit_in_account_currency':output,CODE:code,RATE:rate,BASE:base}]
            if input_:rows.append({'account':a[in_account],'debit_in_account_currency':input_,CODE:code,RATE:rate})
            if output!=input_:rows.append({'account':a['4300'],'debit_in_account_currency':output-input_,'cost_center':c.cost_center})
            doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-09-20',
                'voucher_type':'Journal Entry','user_remark':'Synthetic documented customs declaration','accounts':rows}).insert();doc.submit()
            native=make_reverse_journal_entry(doc.name);native.posting_date='2026-10-20'
            assert next(r.get(BASE) for r in native.accounts if r.get(BASE))==base
            native.insert();assert next(r.get(BASE) for r in native.accounts if r.get(BASE))==-base
            native.save();assert next(r.get(BASE) for r in native.accounts if r.get(BASE))==-base
            native.submit()
            file=save_file('synthetic-customs-declaration.json',json.dumps({'synthetic':True,'basis':base,'code':code,'source':doc.name}).encode(),doc.doctype,doc.name,is_private=1)
            evidence.append({'source':doc.name,'reverse':native.name,'base':base,'ledger':ledger(doc.name),
                'reverse_ledger':ledger(native.name),'file':file.name,
                'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
        assert totals(report('2026-09-01','2026-09-30'))==(18100,4125,2180)
        assert totals(report('2026-10-01','2026-10-31'))==(-18100,-4125,-2180)
        assert totals(report('2026-09-01','2026-10-31'))==(0,0,0)
        # Keep the core correction route: cancel a reversal, never reverse it again.
        try:make_reverse_journal_entry(evidence[0]['reverse'])
        except frappe.ValidationError as error:assert 'Cancel it instead of reversing it' in str(error)
        else:raise AssertionError('Native reversal-of-reversal guard was bypassed')
        print('PASS native import journals81/82/83/84, 25/15 rates, full/60/zero deduction; original18100/4125/2180 and exact negative reversal next period; repeated save and native reversal-of-reversal guard')
        frappe.db.set_default('runtime_import_journals',json.dumps(evidence));frappe.db.commit()
finally:frappe.destroy()
