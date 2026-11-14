"""Qualify existing ERPNext owner transactions and annual reports; no new engine."""
import hashlib,json,os,sys
from decimal import Decimal
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.local.lang='en'
from frappe.desk.query_report import run as run_report
from frappe.utils.file_manager import save_file
from erpnext_norway import saft,saft_builder as xml,vat
C='Runtime ENK Core';OWNER='runtime-enk-owner@example.invalid'


def amount(value):return xml._money(value)


def journal(a,day,entries,**values):
    rows=[]
    for number,debit,credit in entries:
        rows.append({'account':a[number],'debit_in_account_currency':debit,
            'credit_in_account_currency':credit,'cost_center':frappe.get_cached_value('Company',C,'cost_center')})
    doc=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':day,
        'user_remark':'Synthetic native ENK source','accounts':rows,**values}).insert();doc.submit();return doc


def report(name,year,**values):
    filters={'company':C,'fiscal_year':str(year),'filter_based_on':'Date Range',
        'period_start_date':f'{year}-01-01','period_end_date':f'{year}-12-31',
        'from_date':f'{year}-01-01','to_date':f'{year}-12-31','periodicity':'Yearly',
        'accumulated_values':1,'include_default_book_entries':1,'show_net_values':1,'show_zero_values':1,
        'with_period_closing_entry_for_opening':1,'with_period_closing_entry_for_current_period':1,**values}
    return run_report(name,filters=frappe.as_json(filters),ignore_prepared_report=True,
        js_filters=[{'fieldname':'company','fieldtype':'Link','options':'Company'}])['result']


def leaf(rows,account):return next(r for r in rows if r and r.get('account')==account)


def profit(year):
    rows=report('Profit and Loss Statement',year)
    return amount(next(r['total'] for r in rows if r and str(r.get('account_name','')).strip("'")=='Profit for the year'))


def ledger():
    return json.loads(frappe.as_json(frappe.get_all('GL Entry',filters={'company':C},
        fields=['name','account','debit','credit','posting_date','voucher_type','voucher_no','is_cancelled'],order_by='name')))


def check(a):
    assert frappe.session.user==OWNER and 'System Manager' not in frappe.get_roles()
    assert profit(2026)==8800 and profit(2027)==-600
    for year,balance in ((2026,19500),(2027,18900)):
        rows=report('Trial Balance',year)
        assert amount(leaf(rows,a['1920'])['closing_debit'])==balance
        assert amount(leaf(rows,a['2050'])['closing_credit'])==balance
        for number in ('2060','2062','2070','2072','3020','4500'):
            row=leaf(rows,a[number]);assert not amount(row['closing_debit']) and not amount(row['closing_credit'])
        balance_rows=report('Balance Sheet',year)
        assert amount(leaf(balance_rows,a['1920'])['total'])==balance
        assert amount(leaf(balance_rows,a['2050'])['total'])==balance
    # Native report option exposes the actual annual P&L without closing entries.
    before_closing=report('Trial Balance',2026,with_period_closing_entry_for_current_period=0)
    assert amount(leaf(before_closing,a['3020'])['closing_credit'])==10000
    assert amount(leaf(before_closing,a['4500'])['closing_debit'])==1200
    future=report('Trial Balance',2027)
    assert amount(leaf(future,a['1920'])['opening_debit'])==19500
    assert amount(leaf(future,a['2050'])['opening_credit'])==19500
    for number in ('2060','2062','2070','2072'):
        detail=report('General Ledger',2026,account=[a[number]],categorize_by='Categorize by Voucher (Consolidated)',show_opening_entries=1,include_period_closing_entries=1)
        assert any(r.get('voucher_no') for r in detail),number
    assert not any(frappe.get_cached_value('Account',r['account'],'root_type') in ('Income','Expense')
        for r in ledger() if r['voucher_no'] in json.loads(frappe.db.get_default('runtime_enk_tax_vouchers')))


def rejected(action,phrase):
    frappe.db.savepoint('enk_negative')
    try:action()
    except frappe.ValidationError as error:assert phrase in str(error),str(error)
    else:raise AssertionError('Native control failed: '+phrase)
    finally:frappe.db.rollback(save_point='enk_negative')

try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_enk_core')).get_content())
        frappe.set_user(OWNER);check(e['accounts']);assert ledger()==e['ledger']
        assert frappe.get_doc('Purchase Invoice',e['invoice']).outstanding_amount==0
        for item in e['proofs']:
            file=frappe.get_doc('File',item['file']);assert file.is_private
            data=Path(file.get_full_path()).read_bytes();assert hashlib.sha256(data).hexdigest()==item['sha256'];xml.validate_saf_t(data)
        print('PASS restored native ENK reports, supplier settlement, owner/tax equity, two year closings, GL and private XML')
    else:
        for year in (2026,2027):
            if not frappe.db.exists('Fiscal Year',str(year)):
                frappe.get_doc({'doctype':'Fiscal Year','year':str(year),'year_start_date':f'{year}-01-01','year_end_date':f'{year}-12-31'}).insert()
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic ENK owner','send_welcome_email':0,
            'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'}]}).insert()
        company=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'ECR','country':'Norway',
            'default_currency':'NOK','tax_id':'999999985','create_chart_of_accounts_based_on':'Standard Template',
            'enable_perpetual_inventory':0,vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number in ('2060','2062','2070','2072'):
            account=frappe.get_doc('Account',a[number]);assert account.root_type=='Equity'
            account.append(saft.MAPPING,{'year':2026,'category':'egenkapital','code':'2050'});account.save()
        supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic ENK privately paid supplier',
            'supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'supplier_type':'Company'}).insert()
        item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-ENK-SERVICE','item_name':'Synthetic ENK service',
            'item_group':'Services','stock_uom':'Nos','is_stock_item':0}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER)
        journal(a,'2026-01-01',[('1920',10000,0),('2050',0,10000)],voucher_type='Opening Entry',is_opening='Yes')
        journal(a,'2026-02-01',[('1920',3000,0),('2062',0,3000)])
        journal(a,'2026-02-02',[('1920',10000,0),('3020',0,10000)])
        invoice=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,
            'posting_date':'2026-02-03','bill_date':'2026-02-03','bill_no':'SYN-PRIVATELY-PAID','set_posting_time':1,
            'currency':'NOK','conversion_rate':1,'due_date':'2026-02-28','disable_rounded_total':1,
            'items':[{'item_code':item.name,'qty':1,'rate':1200,'expense_account':a['4500'],'cost_center':company.cost_center}]}).insert();invoice.submit()
        settlement=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-02-03','accounts':[
            {'account':a['2400'],'party_type':'Supplier','party':supplier.name,'reference_type':'Purchase Invoice',
             'reference_name':invoice.name,'debit_in_account_currency':1200},
            {'account':a['2062'],'credit_in_account_currency':1200}]}).insert();settlement.submit()
        assert invoice.reload().outstanding_amount==0
        journal(a,'2026-02-04',[('2060',2000,0),('1920',0,2000)])
        tax=journal(a,'2026-03-15',[('2070',1000,0),('1920',0,1000)])
        rest=journal(a,'2026-04-01',[('2072',300,0),('1920',0,300)])
        refund=journal(a,'2026-04-02',[('1920',100,0),('2072',0,100)])
        journal(a,'2026-04-03',[('2060',300,0),('1920',0,300)])
        cancelled=journal(a,'2026-04-04',[('2060',400,0),('1920',0,400)]);cancelled.cancel()
        frappe.db.set_default('runtime_enk_tax_vouchers',json.dumps([tax.name,rest.name,refund.name]))
        assert profit(2026)==8800
        assert amount(leaf(report('Trial Balance',2026),a['1920'])['closing_debit'])==19500
        journal(a,'2026-12-31',[('2062',4200,0),('2050',0,4200)])
        journal(a,'2026-12-31',[('2050',3500,0),('2060',0,2300),('2070',0,1000),('2072',0,200)])
        for year in (2026,2027):
            if year==2027:journal(a,'2027-01-15',[('4500',600,0),('1920',0,600)])
            closing=frappe.get_doc({'doctype':'Period Closing Voucher','company':C,'fiscal_year':str(year),
                'closing_account_head':a['2050'],'transaction_date':'2026-11-14',
                'period_start_date':f'{year}-01-01','period_end_date':f'{year}-12-31',
                'remarks':'Synthetic native ENK profit/loss closing'}).insert();closing.submit();closing.reload()
            assert closing.gle_processing_status=='Completed'
        rejected(lambda:journal(a,'2026-10-01',[('2060',1,0),('1920',0,1)]),'Books have been closed')
        rejected(lambda:tax.cancel(),'Books have been closed')
        check(a)
        try:report('Trial Balance',2026,company='Runtime Norwegian Example')
        except frappe.ValidationError as error:assert 'permission' in str(error).lower(),str(error)
        else:raise AssertionError('Another company report selection was allowed')
        # Without Desk's filter metadata, native report generation returns blank
        # chart rows, not that company's booked amounts. Do not mistake an empty
        # report for permission to read its ledger or expect a different error type.
        raw=run_report('Trial Balance',filters={'company':'Runtime Norwegian Example',
            'fiscal_year':'2026','from_date':'2026-01-01','to_date':'2026-12-31',
            'include_default_book_entries':1,'with_period_closing_entry_for_opening':1,
            'with_period_closing_entry_for_current_period':1,'show_zero_values':1},ignore_prepared_report=True)
        assert not any(amount(r.get(key)) for r in raw['result'] if r
            for key in ('opening_debit','opening_credit','debit','credit','closing_debit','closing_credit'))
        proofs=[]
        for year in (2026,2027):
            content=saft.build(C,f'{year}-01-01',f'{year}-12-31');xml.validate_saf_t(content)
            file=save_file(f'synthetic-enk-{year}.xml',content,'Company',C,is_private=1)
            proofs.append({'file':file.name,'sha256':hashlib.sha256(content).hexdigest()})
        evidence={'accounts':a,'invoice':invoice.name,'ledger':ledger(),'proofs':proofs}
        record=save_file('synthetic-enk-core-evidence.json',frappe.as_json(evidence).encode(),'Company',C,is_private=1)
        frappe.db.set_default('runtime_enk_core',record.name);frappe.db.commit()
        print('PASS native ENK deposits/withdrawals/private supplier payment/reimbursement/personal tax/refund, P&L8800/-600, bank/equity19500/18900, year close/opening, lock and report permission')
finally:frappe.db.rollback();frappe.destroy()
