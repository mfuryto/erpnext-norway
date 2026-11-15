"""Native invoice/asset/credit/cancel/PCV and Norwegian tax reconciliation."""
import hashlib,json,os,sys
from dataclasses import asdict
from pathlib import Path
from decimal import Decimal
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.local.lang='en';frappe.conf.host_name='http://frontend:8080'
from frappe.utils.file_manager import save_file
from frappe.desk.query_report import run as run_report
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.assets.doctype.asset.depreciation import make_depreciation_entry
from erpnext_norway import enk_tax as tax,vat
C='Runtime ENK Tax';OWNER='runtime-enk-tax@example.invalid'


def basis():return tax.collect(C,'2026')


def snapshot():
    b=basis();b['pools']=[asdict(r) for r in b['pools']]
    return json.loads(frappe.as_json(b))


def ledger():
    return json.loads(frappe.as_json(frappe.get_all('GL Entry',filters={'company':C},
        fields=['name','account','debit','credit','posting_date','voucher_type','voucher_no','is_cancelled'],order_by='name')))


def rejected(action,phrase):
    frappe.db.savepoint('enk_tax_rejected')
    try:action()
    except frappe.ValidationError as e:assert phrase in str(e),str(e)
    else:raise AssertionError('Missing tax basis control: '+phrase)
    finally:frappe.db.rollback(save_point='enk_tax_rejected')


def report():
    return run_report('Norsk ENK-grunnlag',filters=frappe.as_json({'company':C,'fiscal_year':'2026'}),
        ignore_prepared_report=True,js_filters=[{'fieldname':'company','fieldtype':'Link','options':'Company'}])


def additional_d():
    """Qualify a second pool and multiple native leaf accounts in one selected group."""
    RC='Runtime ENK Tax Registered'
    frappe.set_user('Administrator')
    c=frappe.get_doc('Company',RC)
    a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':RC},fields=['name','account_number'])}
    group=frappe.get_doc({'doctype':'Account','company':RC,'account_name':'Synthetic pooled machine accounts','account_number':'1288',
        'is_group':1,'parent_account':frappe.db.get_value('Account',{'company':RC,'root_type':'Asset','is_group':1})}).insert()
    first=frappe.get_doc('Account',a['1200']);first.parent_account=group.name;first.save()
    second=frappe.get_doc({'doctype':'Account','company':RC,'account_name':'Synthetic second machine account','account_number':'1201',
        'account_type':'Fixed Asset','parent_account':group.name}).insert()
    items=[]
    for index,(account,amount) in enumerate([(first.name,40000),(second.name,60000)]):
        category=frappe.get_doc({'doctype':'Asset Category','asset_category_name':'Synthetic tax machines '+str(index),
            'accounts':[{'company_name':RC,'fixed_asset_account':account,'accumulated_depreciation_account':a['1299'],'depreciation_expense_account':a['6017']}]}).insert()
        item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-ENK-TAX-D-'+str(index),'item_name':'Synthetic tax machine',
            'item_group':'Products','stock_uom':'Nos','is_stock_item':0,'is_fixed_asset':1,'auto_create_assets':0,'asset_category':category.name}).insert()
        items.append({'item_code':item.name,'qty':1,'rate':amount,'expense_account':account,'cost_center':c.cost_center,
            'warehouse':'Stores - NTR','asset_location':'Synthetic tax asset location',
            'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':RC,'title':'MVA 25 % – varelinjer'})})
    frappe.set_user(OWNER)
    pi=frappe.get_doc({'doctype':'Purchase Invoice','company':RC,'supplier':frappe.db.get_value('Supplier',{'supplier_name':'Synthetic tax supplier'}),
        'currency':'NOK','conversion_rate':1,'posting_date':'2026-10-22','bill_date':'2026-10-22','bill_no':'SYNTHETIC-TAX-POOL-D',
        'set_posting_time':1,'due_date':'2026-12-31','disable_rounded_total':1,'update_stock':1,'items':items}).insert();pi.submit()
    facts=frappe.get_doc(tax.FACTS,frappe.db.get_value(tax.FACTS,{'company':RC,'fiscal_year':'2026'}))
    facts.append('pools',{'saldo_group':'d','asset_account':group.name,'opening_reference':'Synthetic new machine pool','use_maximum':1});facts.save()
    b=tax.collect(RC,'2026');d=next(p for p in b['pools'] if p.group.value=='d')
    assert (d.acquisitions,d.depreciation_deduction,d.closing_balance,b['tax_profit'])==(100000,20000,80000,-20000),b
    print('PASS native a/d combined basis and one pooled tax balance over two native fixed-asset accounts')
    return str(b['tax_profit'])


def additional():
    """Qualify ordinary read-only accounting access and actual partially deductible VAT."""
    from erpnext_norway.vat_catalog import DEDUCTION
    frappe.set_user('Administrator');frappe.clear_cache()
    reader='runtime-enk-tax-reader@example.invalid'
    restricted='runtime-enk-tax-restricted@example.invalid'
    a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
    for email in (reader,restricted):
        frappe.get_doc({'doctype':'User','email':email,'first_name':'Synthetic tax reader','send_welcome_email':0,
            'roles':[{'role':'Accounts User'}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':email,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
    frappe.get_doc({'doctype':'User Permission','user':restricted,'allow':'Account','for_value':a['1250'],'apply_to_all_doctypes':1}).insert()
    frappe.set_user(reader)
    assert report()['report_summary'][1]['value']==25350
    doc=frappe.get_doc(tax.FACTS,basis()['document'])
    try:doc.notes='Synthetic forbidden edit';doc.save()
    except frappe.PermissionError:pass
    else:raise AssertionError('Read-only accounting user could change tax facts')
    frappe.set_user(restricted)
    try:basis()
    except frappe.PermissionError:pass
    else:raise AssertionError('Partial account access produced a complete tax basis')
    frappe.set_user('Guest')
    try:report()
    except (frappe.PermissionError,frappe.ValidationError) as error:
        assert 'permission' in str(error).lower(),str(error)
    else:raise AssertionError('Guest received tax basis')
    frappe.set_user('Administrator')
    RC='Runtime ENK Tax Registered'
    c=frappe.get_doc({'doctype':'Company','company_name':RC,'abbr':'NTR','country':'Norway','default_currency':'NOK',
        'tax_id':'999999983','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',
        vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
    ra={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':RC},fields=['name','account_number'])}
    contra=frappe.get_doc({'doctype':'Account','company':RC,'account_number':'1299','account_name':'Synthetic accumulated depreciation',
        'account_type':'Accumulated Depreciation','parent_account':frappe.db.get_value('Account',{'company':RC,'root_type':'Asset','is_group':1})}).insert()
    valuation=frappe.get_doc({'doctype':'Account','company':RC,'account_number':'4998','account_name':'Synthetic included valuation',
        'account_type':'Expenses Included In Valuation','parent_account':frappe.db.get_value('Account',{'company':RC,'root_type':'Expense','is_group':1})}).insert()
    for num,title,kind in [('2998','Synthetic unbilled stock','Stock Received But Not Billed'),('2997','Synthetic unbilled assets','Asset Received But Not Billed')]:
        ra[num]=frappe.get_doc({'doctype':'Account','company':RC,'account_number':num,'account_name':title,'account_type':kind,
            'parent_account':frappe.db.get_value('Account',{'company':RC,'root_type':'Liability','is_group':1})}).insert().name
    c.default_inventory_account=ra['1460'];c.stock_received_but_not_billed=ra['2998'];c.asset_received_but_not_billed=ra['2997']
    c.expenses_included_in_valuation=valuation.name
    c.accumulated_depreciation_account=contra.name;c.depreciation_expense_account=ra['6017'];c.depreciation_cost_center=c.cost_center;c.save()
    cat=frappe.get_doc('Asset Category','Synthetic tax office assets');cat.append('accounts',{'company_name':RC,
        'fixed_asset_account':ra['1250'],'accumulated_depreciation_account':contra.name,'depreciation_expense_account':ra['6017']});cat.save()
    frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':RC,'apply_to_all_doctypes':1}).insert()
    frappe.set_user(OWNER)
    def purchase_registered(kind='Purchase Invoice'):
        pi=frappe.get_doc({'doctype':kind,'company':RC,'supplier':frappe.db.get_value('Supplier',{'supplier_name':'Synthetic tax supplier'}),'currency':'NOK','conversion_rate':1,
        'posting_date':'2026-10-20','bill_date':'2026-10-20','bill_no':'SYNTHETIC-TAX-PARTIAL-VAT','set_posting_time':1,
        'due_date':'2026-12-31','disable_rounded_total':1,'update_stock':1,
        'items':[{'item_code':'RUNTIME-ENK-TAX-ASSET','qty':1,'rate':100000,'expense_account':ra['1250'],'cost_center':c.cost_center,
            'warehouse':'Stores - NTR','asset_location':'Synthetic tax asset location','asset_naming_series':'ACC-ASS-.YYYY.-',
            'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':RC,'title':'MVA 25 % – varelinjer'}),DEDUCTION:50}]}).insert();pi.submit()
        return pi
    for kind in ('Purchase Invoice','Purchase Receipt'):
        rejected(lambda:purchase_registered(kind),'Enable Perpetual Inventory')
    assert not frappe.db.count('GL Entry',{'company':RC})
    frappe.set_user('Administrator');c.enable_perpetual_inventory=1;c.save();frappe.clear_document_cache('Company',RC)
    frappe.set_user(OWNER);pi=purchase_registered()
    facts=frappe.get_doc({'doctype':tax.FACTS,'company':RC,'fiscal_year':'2026','pools':[{'saldo_group':'a',
        'asset_account':ra['1250'],'opening_balance':0,'opening_reference':'Synthetic new registered business','use_maximum':1}]}).insert()
    b=tax.collect(RC,'2026')
    assert (b['pools'][0].acquisitions,b['tax_depreciation'],b['tax_profit'])==(112500,33750,-33750),b
    # Core explicitly requires deleting surplus draft assets before purchase return.
    asset=frappe.get_doc('Asset',frappe.db.get_value('Asset',{'purchase_invoice':pi.name}));assert asset.docstatus==0
    frappe.delete_doc('Asset',asset.name)
    credit=make_return_doc('Purchase Invoice',pi.name);credit.posting_date=credit.bill_date='2026-10-21';credit.set_posting_time=1
    credit.insert();credit.submit()
    after=tax.collect(RC,'2026')
    assert (after['pools'][0].acquisitions,after['tax_depreciation'],after['tax_profit'],after['book_assets'])==(0,0,0,0),after
    print('PASS read-only accountant, Account restriction and guest denial; native 50 percent VAT capitalisation and purchase asset credit')
    frappe.set_user(OWNER)
    final_profit=additional_d()
    return {'company':RC,'final_tax_profit':final_profit,'invoice':pi.name,'credit':credit.name,'acquisition_before_return':str(b['pools'][0].acquisitions),
        'tax_depreciation_before_return':str(b['tax_depreciation']),'tax_profit_after_return':str(after['tax_profit'])}


try:
    if sys.argv[1]=='additional':
        extra=additional();frappe.db.set_default('runtime_enk_tax_additional',frappe.as_json(extra));frappe.db.commit()
    elif sys.argv[1]=='verify':
        e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_enk_tax')).get_content())
        frappe.set_user(OWNER)
        assert snapshot()==e['basis'];assert ledger()==e['ledger']
        assert report()['report_summary'][1]['value']==25350
        extra=e['additional'];assert tax.collect(extra['company'],'2026')['tax_profit']==Decimal(extra['final_tax_profit'])
        assert frappe.get_doc('Purchase Invoice',extra['credit']).docstatus==1
        file=frappe.get_doc('File',e['proof']);assert file.is_private
        assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored tax facts/schema, native sources and reports, pooled depreciation, private proof and no extra GL')
    else:
        user=frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic tax owner','send_welcome_email':0,
            'roles':[{'role':r} for r in ['Accounts Manager','Accounts User','Purchase Manager','Sales Manager','Stock Manager','Stock User']]}).insert()
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'NET','country':'Norway','default_currency':'NOK',
            'tax_id':'999999984','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',
            vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        def account(number,title,kind,root):
            doc=frappe.get_doc({'doctype':'Account','company':C,'account_number':number,'account_name':title,
                'account_type':kind,'parent_account':frappe.db.get_value('Account',{'company':C,'root_type':root,'is_group':1})}).insert()
            a[number]=doc.name;return doc.name
        c.accumulated_depreciation_account=account('1299','Synthetic accumulated depreciation','Accumulated Depreciation','Asset')
        c.depreciation_expense_account=a['6017'];c.depreciation_cost_center=c.cost_center
        c.disposal_account=account('3800','Synthetic disposal gain loss','Income Account','Income');c.save()
        cat=frappe.get_doc({'doctype':'Asset Category','asset_category_name':'Synthetic tax office assets',
            'accounts':[{'company_name':C,'fixed_asset_account':a['1250'],'accumulated_depreciation_account':a['1299'],'depreciation_expense_account':a['6017']}]}).insert()
        loc=frappe.get_doc({'doctype':'Location','location_name':'Synthetic tax asset location'}).insert()
        asset_item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-ENK-TAX-ASSET','item_name':'Synthetic office machine',
            'item_group':'Products','stock_uom':'Nos','is_stock_item':0,'is_fixed_asset':1,'auto_create_assets':1,'asset_naming_series':'ACC-ASS-.YYYY.-','asset_category':cat.name}).insert()
        service=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-ENK-TAX-SERVICE','item_name':'Synthetic tax service',
            'item_group':'Services','stock_uom':'Nos','is_stock_item':0}).insert()
        supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic tax supplier','supplier_type':'Company',
            'supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0]}).insert()
        customer=frappe.get_doc({'doctype':'Customer','customer_name':'Synthetic tax customer','customer_type':'Company',
            'customer_group':frappe.get_all('Customer Group',filters={'is_group':0},pluck='name')[0],
            'territory':frappe.get_all('Territory',filters={'is_group':0},pluck='name')[0]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        def journal(day,rows,**kw):
            d=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':day,'user_remark':'Synthetic tax source',
                'accounts':[{'account':a[n],'debit_in_account_currency':debit,'credit_in_account_currency':credit,'cost_center':c.cost_center} for n,debit,credit in rows],**kw}).insert();d.submit();return d
        journal('2026-01-01',[('1920',100000,0),('2050',0,100000)],voucher_type='Opening Entry',is_opening='Yes')
        journal('2026-02-01',[('1920',10000,0),('3020',0,10000)])
        def purchase(item,amount,day,asset=False):
            d=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,'currency':'NOK','conversion_rate':1,
                'posting_date':day,'bill_date':day,'bill_no':'SYNTHETIC-TAX-'+str(amount),'set_posting_time':1,
                'due_date':'2026-12-31','disable_rounded_total':1,'update_stock':int(asset),
                'items':[{'item_code':item.name,'qty':1 if asset else 4,'rate':amount if asset else amount/4,'warehouse':'Stores - NET',
                    'expense_account':a['1250'] if asset else a['4500'],'cost_center':c.cost_center,
                    'asset_location':loc.name,'asset_naming_series':'ACC-ASS-.YYYY.-'}]}).insert();d.submit();return d
        expense=purchase(service,2000,'2026-12-02')
        credit=make_return_doc('Purchase Invoice',expense.name);credit.posting_date=credit.bill_date='2026-12-03';credit.set_posting_time=1
        credit.items[0].qty=-1;credit.insert();credit.submit()
        facts=frappe.get_doc({'doctype':tax.FACTS,'company':C,'fiscal_year':'2026','pools':[],
            'adjustments':[{'account':a['4500'],'disallowed_percent':50,'reason':'Synthetic 50 percent non-deductible expense account',
                'reference':'Synthetic purchase and credit documentation'},
                {'amount':100,'reason':'Synthetic other documented tax difference','reference':'Synthetic annual tax evidence'}]}).insert()
        assert basis()['tax_profit']==9350
        assets=[]
        for amount,dep,day in [(100000,20000,'2026-12-01'),(50000,5000,'2026-12-02')]:
            pi=purchase(asset_item,amount,day,True)
            asset=frappe.get_doc('Asset',frappe.db.get_value('Asset',{'purchase_invoice':pi.name}))
            asset.available_for_use_date=day;asset.calculate_depreciation=1
            asset.set('finance_books',[dict(depreciation_method='Manual',total_number_of_depreciations=amount//dep,
                frequency_of_depreciation=12,depreciation_start_date='2026-12-10',expected_value_after_useful_life=0)])
            asset.save()
            schedule=frappe.get_doc('Asset Depreciation Schedule',frappe.db.get_value('Asset Depreciation Schedule',{'asset':asset.name,'status':'Draft'}))
            schedule.set('depreciation_schedule',[])
            for n in range(amount//dep):schedule.append('depreciation_schedule',{'schedule_date':f'{2026+n}-12-10',
                'depreciation_amount':dep,'accumulated_depreciation_amount':dep*(n+1)})
            schedule.save();asset.submit();make_depreciation_entry(schedule.name,date='2026-12-10');assets.append(asset)
        facts.append('pools',{'saldo_group':'a','asset_account':a['1250'],'opening_balance':0,
            'opening_reference':'Synthetic new business: no prior tax balance','use_maximum':1});facts.save()
        b=basis();assert (b['book_depreciation'],b['tax_depreciation'],b['tax_profit'])==(25000,45000,-35650),b
        # A native manual plan can be cancelled and reposted without a separate adjustment engine.
        schedule=frappe.get_doc('Asset Depreciation Schedule',frappe.db.get_value('Asset Depreciation Schedule',{'asset':assets[1].name,'status':'Active'}))
        entry=frappe.get_doc('Journal Entry',schedule.depreciation_schedule[0].journal_entry);entry.cancel();schedule.reload()
        assert not schedule.depreciation_schedule[0].journal_entry
        assert basis()['book_depreciation']==20000
        make_depreciation_entry(schedule.name,date='2026-12-10');assert basis()['book_depreciation']==25000
        sale=frappe.get_doc({'doctype':'Sales Invoice','company':C,'customer':customer.name,'currency':'NOK','conversion_rate':1,
            'posting_date':'2026-12-20','set_posting_time':1,'due_date':'2026-12-31','disable_rounded_total':1,
            'items':[{'item_code':asset_item.name,'asset':assets[0].name,'qty':1,'rate':200000,'cost_center':c.cost_center},
                {'item_code':service.name,'qty':1,'rate':1000,'income_account':a['3020'],'cost_center':c.cost_center}]}).insert();sale.submit()
        b=basis();pool=b['pools'][0]
        assert (pool.acquisitions,pool.disposal_proceeds,pool.negative_balance_income,pool.closing_balance)==(150000,200000,15000,-35000),b
        assert (b['book_profit'],b['book_assets'],b['tax_profit'])==(104500,45000,25350),b
        assert b['book_disposal']-b['book_depreciation']==95000,b
        sale_credit=make_return_doc('Sales Invoice',sale.name);sale_credit.posting_date='2026-12-21';sale_credit.set_posting_time=1
        sale_credit.insert();sale_credit.submit()
        assert basis()['tax_profit']==-35650
        sale_credit.cancel();assert basis()['tax_profit']==25350
        print('PASS native Manual posting/cancel/repost; pooled tax, invoice/credit and mixed native asset sale/return')
        def invalid_pool():
            d=frappe.get_doc(tax.FACTS,facts.name);d.append('pools',dict(d.pools[0].as_dict(),name=None));d.save()
        rejected(invalid_pool,'én samlesaldo')
        def bad_source():
            d=frappe.get_doc(tax.FACTS,facts.name);d.pools[0].asset_account=a['1920'];d.save()
        rejected(bad_source,'anleggsmiddelkontoer')
        def valuation_mismatch():
            source=frappe.get_doc('Purchase Invoice',assets[1].purchase_invoice)
            frappe.db.set_value('Purchase Invoice Item',source.items[0].name,'valuation_rate',60000)
            basis()
        rejected(valuation_mismatch,'Avstem driftsmiddelverdsetting')
        # No guessing tax treatment of an unqualified native journal movement.
        def unsupported():
            journal('2026-12-22',[('1250',100,0),('2062',0,100)]);basis()
        rejected(unsupported,'ikke er kvalifisert')
        frappe.db.savepoint('enk_native_book_probe')
        before_book=snapshot()
        book=frappe.get_doc({'doctype':'Finance Book','finance_book_name':'Synthetic alternative depreciation book'}).insert()
        asset=frappe.get_doc({'doctype':'Asset','asset_name':'Synthetic native finance book probe','company':C,
            'item_code':asset_item.name,'asset_category':cat.name,'location':loc.name,'is_existing_asset':1,
            'purchase_date':'2026-12-01','available_for_use_date':'2026-12-01','gross_purchase_amount':100000,
            'net_purchase_amount':100000,'calculate_depreciation':1,'finance_books':[{'finance_book':book.name,
                'depreciation_method':'Manual','total_number_of_depreciations':5,'frequency_of_depreciation':12,
                'depreciation_start_date':'2026-12-10','expected_value_after_useful_life':0}]}).insert()
        asset.submit()
        ads=frappe.get_doc('Asset Depreciation Schedule',frappe.db.get_value('Asset Depreciation Schedule',{'asset':asset.name,'status':'Active'}))
        make_depreciation_entry(ads.name,date='2026-12-10');ads.reload()
        entry=frappe.get_doc('Journal Entry',ads.depreciation_schedule[0].journal_entry)
        assert entry.finance_book==book.name
        assert snapshot()==before_book
        frappe.db.rollback(save_point='enk_native_book_probe')
        print('PASS native Finance Book posts separately and core default-book reports exclude it')
        current=snapshot();before=ledger()
        result=report();assert result['report_summary'][1]['value']==25350
        assert ledger()==before
        # Same native PCV; tax report stays stable after core closes P&L accounts.
        closing=frappe.get_doc({'doctype':'Period Closing Voucher','company':C,'fiscal_year':'2026','transaction_date':'2026-11-15',
            'period_start_date':'2026-01-01','period_end_date':'2026-12-31','closing_account_head':a['2050'],
            'remarks':'Synthetic tax basis native closing'}).insert();closing.submit()
        closing.reload();assert closing.gle_processing_status=='Completed'
        after_closing = snapshot()
        assert after_closing['tax_profit'] == current['tax_profit']
        assert after_closing['pools'] == current['pools']
        assert after_closing['corrections'] == current['corrections']
        # Annual balance follows the actual native closing, including transferred
        # equity. Tax/P&L bridge remains independent of the native PCV clearing.
        assert sum(row['closing'] for row in after_closing['annual_accounts']) == 0
        assert next(r for r in after_closing['annual_accounts'] if r['account']==a['2050'])['closing'] == -204500
        extra=additional()
        proof=save_file('synthetic-enk-tax-report.json',frappe.as_json(result),tax.FACTS,facts.name,is_private=1)
        data=Path(proof.get_full_path()).read_bytes()
        evidence=save_file('synthetic-enk-tax-evidence.json',frappe.as_json({'basis':snapshot(),'ledger':ledger(),
            'additional':extra,'proof':proof.name,'sha256':hashlib.sha256(data).hexdigest()}),tax.FACTS,facts.name,is_private=1)
        frappe.set_user('Administrator');frappe.db.set_default('runtime_enk_tax',evidence.name);frappe.db.commit()
        print('PASS native P&L/Trial Balance reconciliation, source controls, year closing, permissions and no tax GL writes')
finally:frappe.destroy()
