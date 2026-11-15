"""Ordinary native sources for remaining 2026 ENK annual basis; exported restore."""
import hashlib,json,os,sys
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.local.lang='nb';frappe.conf.host_name='http://frontend:8080'
from frappe.utils.file_manager import save_file
from erpnext_norway import enk_tax as tax,vat
from erpnext_norway.enk_journal import EFFECT,PROCEEDS
from frappe.desk.query_report import run as run_report
from erpnext.assets.doctype.asset.depreciation import scrap_asset,restore_asset
C='Runtime ENK Annual';OWNER='runtime-enk-tax@example.invalid'


def snapshot():
    b=tax.collect(C,'2026');b['pools']=[asdict(p) for p in b['pools']]
    return json.loads(frappe.as_json(b))


def rejected(action,phrase):
    frappe.db.savepoint('annual_negative')
    try:action()
    except frappe.ValidationError as error:assert phrase in str(error),str(error)
    else:raise AssertionError('Missing annual control: '+phrase)
    finally:frappe.db.rollback(save_point='annual_negative')


def exported_csv():
    import csv,io
    from frappe.desk.query_report import export_query
    previous_form,previous_response=frappe.local.form_dict,frappe.local.response
    try:
        frappe.local.form_dict=frappe._dict(report_name='Norsk ENK-grunnlag',file_format_type='CSV',
            filters=frappe.as_json({'company':C,'fiscal_year':'2026','show_accounts':1}))
        frappe.local.response=frappe._dict()
        export_query()
        content=frappe.local.response.filecontent
        text=content.decode('utf-8-sig') if isinstance(content,bytes) else content.lstrip('\ufeff')
        rows=list(csv.reader(io.StringIO(text)))
        header=rows[0];account=header.index('Konto');tax_value=header.index('Skatteverdi UB')
        fixed=next(r for r in rows[1:] if len(r)>account and r[account].startswith('1230 '))
        assert fixed[tax_value]=='',fixed
        assert any('Beregnet næringsresultat' in r for r in rows)
        return hashlib.sha256(content if isinstance(content,bytes) else content.encode()).hexdigest()
    finally:frappe.local.form_dict,frappe.local.response=previous_form,previous_response


def edge_cases():
    """Actual source effects, zero book value sale, and no duplicate difference."""
    frappe.set_user(OWNER)
    c=frappe.get_doc('Company',C)
    a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
    baseline=tax.collect(C,'2026')
    facts_name=baseline['document']
    def journal(lines, depreciation=False):
        d=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-10',
            'user_remark':'Synthetic annual edge source','voucher_type':'Depreciation Entry' if depreciation else 'Journal Entry',
            'accounts':[dict(account=a[code],debit_in_account_currency=debit,credit_in_account_currency=credit,
                cost_center=c.cost_center,**extras) for code,debit,credit,extras in lines]}).insert();d.submit();return d
    frappe.db.savepoint('annual_edges')
    try:
        # Ordinary invoice accounting can have different tax inventory value;
        # the documented annual difference flows to the bridge once.
        journal([('1460',10000,0,{}),('4500',0,10000,{})])
        f=frappe.get_doc(tax.FACTS,facts_name)
        f.append('tax_values',dict(account=a['1460'],tax_method='Documented values',tax_opening=0,tax_closing=9000,
            result_effect=1,wealth_method='Tax value before discount',reference='Synthetic counted stock and tax valuation'))
        f.save();b=tax.collect(C,'2026');assert b['tax_profit']==baseline['tax_profit']+9000
        assert next(r for r in b['annual_accounts'] if r['account']==a['1460'])['wealth']==9000
        # ELK is already removed from P&L by the native private-use journal.
        journal([('6900',10000,0,{}),('1920',0,10000,{})])
        journal([('2068',4392,0,{}),('6900',0,4392,{})])
        b=tax.collect(C,'2026');assert b['tax_profit']==baseline['tax_profit']+9000-5608
        assert next(r for r in b['annual_posts'] if r['code']=='6995')['book']==10000
        assert next(r for r in b['annual_posts'] if r['code']=='6998')['book']==4392
        # Land has no saldo depreciation; a documented time-limited right uses
        # the ordinary native book depreciation, with its annual tax deduction.
        journal([('1150',100000,0,{}),('1920',0,100000,{})])
        journal([('1040',10000,0,{}),('1920',0,10000,{})])
        journal([('6017',2000,0,{}),('1040',0,2000,{})],depreciation=True)
        f.reload()
        f.append('tax_values',dict(account=a['1150'],outside_saldo=1,tax_method='Book values confirmed',
            wealth_method='Documented value',wealth_value=100000,reference='Synthetic land: not depreciable'))
        f.append('tax_values',dict(account=a['1040'],outside_saldo=1,non_saldo_deduction=2000,
            tax_method='Book values confirmed',wealth_method='Tax value before discount',
            reference='Synthetic time-limited right: documented tax deduction matches ordinary native book depreciation'))
        f.save();land=tax.collect(C,'2026')
        assert land['non_saldo_deduction']==2000 and land['tax_profit']==b['tax_profit']-2000
        b=land
        # A remaining tax value can exist even when the account has zero book
        # opening/closing and no current GL. It must not disappear from export.
        frappe.set_user('Administrator')
        tax_only=frappe.get_doc({'doctype':'Account','company':C,'account_number':'1509',
            'account_name':'Synthetic remaining tax receivable','account_type':'Receivable',
            'parent_account':frappe.get_cached_value('Account',a['1500'],'parent_account')}).insert()
        frappe.set_user(OWNER)
        assert not frappe.db.exists('GL Entry',{'company':C,'account':tax_only.name})
        f.reload();f.append('tax_values',dict(account=tax_only.name,tax_method='Documented values',
            tax_opening=10000,tax_closing=8000,result_effect=1,wealth_method='Tax value before discount',
            reference='Synthetic prior book write-off with documented remaining tax value'))
        f.save();zero_book=tax.collect(C,'2026')
        assert zero_book['tax_profit']==b['tax_profit']-2000
        assert next(r for r in zero_book['annual_accounts'] if r['account']==tax_only.name)['tax_closing']==8000
        b=zero_book
        # ENK and SAF-T use separate year histories even though the native child
        # schema is reused. Future ENK choices cannot replace this year's post.
        from erpnext_norway.enk_catalog import MAPPING
        from erpnext_norway.saft import MAPPING as SAFT_MAPPING
        account=frappe.get_doc('Account',tax_only.name)
        account.append(SAFT_MAPPING,dict(year=2026,category='balanseverdiForOmloepsmiddel',code='1530'))
        for year,code in [(2025,'1570'),(2026,'1500'),(2027,'1570')]:
            account.append(MAPPING,dict(year=year,category='balanseverdiForOmloepsmiddel',code=code))
        account.save()
        mapped=tax.collect(C,'2026')
        assert next(r for r in mapped['annual_accounts'] if r['account']==tax_only.name)['code']=='1500'
        account.reload();assert account.get(SAFT_MAPPING)[0].code=='1530'
        assert mapped['tax_profit']==b['tax_profit']
        def land_pool():
            d=frappe.get_doc(tax.FACTS,facts_name);d.append('pools',dict(saldo_group='d',asset_account=a['1150'],
                opening_reference='Invalid land depreciation',use_maximum=1));d.save()
        rejected(land_pool,'Tomter')
        # Tax-neutral account movement is not another acquisition. Cost
        # correction on the ordinary source changes tax basis automatically.
        f.reload();p=next(r for r in f.pools if r.saldo_group=='c')
        old=next(r for r in b['pools'] if r.group.value=='c')
        journal([('1230',0,10000,{EFFECT:'Cost correction'}),('1920',10000,0,{})])
        changed=tax.collect(C,'2026');new=next(r for r in changed['pools'] if r.group.value=='c')
        assert new.acquisitions==old.acquisitions-10000
        assert changed['tax_profit']==b['tax_profit']+2400
        neutral=journal([('1230',1000,0,{EFFECT:'Tax-neutral transfer'}),('1920',0,1000,{})])
        assert tax.collect(C,'2026')['tax_profit']==changed['tax_profit']
        def edit_posted():
            d=frappe.get_doc('Journal Entry',neutral.name);d.accounts[0].set(EFFECT,'New tax basis');d.save()
        rejected(edit_posted,'')
        def double_difference():
            f=frappe.get_doc(tax.FACTS,facts_name)
            f.append('tax_values',dict(account=a['1080'],tax_method='Documented values',result_effect=1,
                reference='Invalid second result correction of tax pool'))
            # Existing goodwill value is deliberately replaced to isolate pool control.
            f.tax_values=[r for r in f.tax_values if r.account!=a['1080'] or r.get('result_effect')]
            f.save();tax.collect(C,'2026')
        rejected(double_difference,'skattesaldo')
    finally:frappe.db.rollback(save_point='annual_edges')
    frappe.db.savepoint('annual_zero_book')
    try:
        item=frappe.get_doc('Item','RUNTIME-ENK-ANNUAL-c')
        asset=frappe.get_doc({'doctype':'Asset','asset_name':'Synthetic fully book-depreciated asset',
            'company':C,'item_code':item.name,'asset_category':item.asset_category,'location':'Synthetic tax asset location',
            'is_existing_asset':1,'purchase_date':'2025-03-01','available_for_use_date':'2025-03-01',
            'gross_purchase_amount':100000,'net_purchase_amount':100000,'opening_accumulated_depreciation':100000,
            'calculate_depreciation':0}).insert();asset.submit()
        assert asset.value_after_depreciation==0
        sale=frappe.get_doc({'doctype':'Sales Invoice','company':C,
            'customer':frappe.db.get_value('Customer',{'customer_name':'Synthetic tax customer'}),
            'posting_date':'2026-10-11','set_posting_time':1,'currency':'NOK','conversion_rate':1,
            'due_date':'2026-12-31','disable_rounded_total':1,
            'items':[{'item_code':item.name,'asset':asset.name,'qty':1,'rate':50000,'cost_center':c.cost_center}]}).insert();sale.submit()
        assert frappe.db.exists('GL Entry',{'voucher_type':'Sales Invoice','voucher_no':sale.name,'account':a['1230'],'is_cancelled':0})
        b=tax.collect(C,'2026');p=next(r for r in b['pools'] if r.group.value=='c')
        assert p.disposal_proceeds==50000 and b['tax_profit']==baseline['tax_profit']+12000
        assert b['book_disposal']==baseline['book_disposal']+50000
    finally:frappe.db.rollback(save_point='annual_zero_book')
    frappe.db.savepoint('annual_multiple_units')
    try:
        item=frappe.get_doc('Item','RUNTIME-ENK-ANNUAL-e')
        pi=frappe.get_doc({'doctype':'Purchase Invoice','company':C,
            'supplier':frappe.db.get_value('Supplier',{'supplier_name':'Synthetic tax supplier'}),
            'currency':'NOK','conversion_rate':1,'posting_date':'2026-10-03','bill_date':'2026-10-03',
            'bill_no':'SYNTHETIC-MULTIPLE-UNITS','set_posting_time':1,'due_date':'2026-12-31','disable_rounded_total':1,
            'update_stock':1,'items':[{'item_code':item.name,'qty':2,'rate':50000,'expense_account':a['1211'],
                'cost_center':c.cost_center,'warehouse':frappe.db.get_value('Warehouse',{'company':C,'is_group':0}),
                'asset_location':'Synthetic tax asset location','asset_naming_series':'ACC-ASS-.YYYY.-'}]}).insert();pi.submit()
        units=frappe.get_list('Asset',filters={'company':C,'purchase_invoice':pi.name},pluck='name')
        assert len(units)==2
        f=frappe.get_doc(tax.FACTS,facts_name)
        for name in units:
            asset=frappe.get_doc('Asset',name);asset.available_for_use_date='2026-10-03';asset.save();asset.submit()
            f.append('pools',dict(saldo_group='e',asset_account=a['1211'],asset=name,unit_reference='Synthetic independent unit',
                opening_reference='Synthetic new asset with zero opening tax value',use_maximum=1))
        f.save()
        sale=frappe.get_doc({'doctype':'Sales Invoice','company':C,
            'customer':frappe.db.get_value('Customer',{'customer_name':'Synthetic tax customer'}),
            'posting_date':'2026-10-04','set_posting_time':1,'currency':'NOK','conversion_rate':1,
            'due_date':'2026-12-31','disable_rounded_total':1,
            'items':[{'item_code':item.name,'asset':units[0],'qty':1,'rate':70000,'cost_center':c.cost_center}]}).insert();sale.submit()
        b=tax.collect(C,'2026');values={p.unit:p for p in b['pools'] if p.group.value=='e'}
        assert values[units[0]].gain_loss_transfer==20000 and values[units[1]].depreciation_deduction==7000
        assert b['tax_profit']==baseline['tax_profit']-3000
    finally:frappe.db.rollback(save_point='annual_multiple_units')
    frappe.db.savepoint('annual_land_sale')
    try:
        frappe.set_user('Administrator')
        category=frappe.get_doc({'doctype':'Asset Category','asset_category_name':'Synthetic annual land',
            'accounts':[{'company_name':C,'fixed_asset_account':a['1150'],'accumulated_depreciation_account':a['1299'],'depreciation_expense_account':a['6017']}]}).insert()
        item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-ENK-ANNUAL-LAND','item_name':'Synthetic land',
            'item_group':'Products','stock_uom':'Nos','is_stock_item':0,'is_fixed_asset':1,'auto_create_assets':1,
            'asset_naming_series':'ACC-ASS-.YYYY.-','asset_category':category.name}).insert()
        frappe.set_user(OWNER)
        pi=frappe.get_doc({'doctype':'Purchase Invoice','company':C,
            'supplier':frappe.db.get_value('Supplier',{'supplier_name':'Synthetic tax supplier'}),
            'currency':'NOK','conversion_rate':1,'posting_date':'2026-10-03','bill_date':'2026-10-03',
            'bill_no':'SYNTHETIC-LAND-OUTSIDE-SALDO','set_posting_time':1,'due_date':'2026-12-31','disable_rounded_total':1,
            'update_stock':1,'items':[{'item_code':item.name,'qty':1,'rate':100000,'expense_account':a['1150'],
                'cost_center':c.cost_center,'warehouse':frappe.db.get_value('Warehouse',{'company':C,'is_group':0}),
                'asset_location':'Synthetic tax asset location','asset_naming_series':'ACC-ASS-.YYYY.-'}]}).insert();pi.submit()
        asset=frappe.get_doc('Asset',frappe.db.get_value('Asset',{'purchase_invoice':pi.name}));asset.available_for_use_date='2026-10-03';asset.save();asset.submit()
        f=frappe.get_doc(tax.FACTS,facts_name)
        f.append('tax_values',dict(account=a['1150'],outside_saldo=1,tax_method='Book values confirmed',
            wealth_method='Tax value before discount',reference='Synthetic land sale, same book/tax cost'))
        f.save();assert tax.collect(C,'2026')['tax_profit']==baseline['tax_profit']
        sale=frappe.get_doc({'doctype':'Sales Invoice','company':C,
            'customer':frappe.db.get_value('Customer',{'customer_name':'Synthetic tax customer'}),
            'posting_date':'2026-10-04','set_posting_time':1,'currency':'NOK','conversion_rate':1,
            'due_date':'2026-12-31','disable_rounded_total':1,
            'items':[{'item_code':item.name,'asset':asset.name,'qty':1,'rate':120000,'cost_center':c.cost_center}]}).insert();sale.submit()
        b=tax.collect(C,'2026');assert b['tax_profit']==baseline['tax_profit']+20000
        assert b['book_disposal']==baseline['book_disposal']
    finally:frappe.db.rollback(save_point='annual_land_sale')
    assert tax.collect(C,'2026')['tax_profit']==baseline['tax_profit']
    print('PASS native zero-book-value disposal, documented inventory difference, gross/private ELK, source cost correction/neutral transfer and posted metadata immutability')




try:
    if sys.argv[1]=='probe':
        edge_cases()
    elif sys.argv[1]=='verify':
        e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_enk_annual')).get_content())
        frappe.set_user(OWNER)
        assert snapshot()==e['basis']
        assert exported_csv()==e['csv_sha256']
        report=frappe.get_doc('File',e['proof']);assert report.is_private
        assert hashlib.sha256(Path(report.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored annual catalogue, native manual/asset source links, tax/formue/person-income facts and report bytes')
    else:
        from frappe.utils.password import update_password
        user=frappe.get_doc('User',OWNER);user.language='nb';user.save()
        update_password(OWNER,'Synthetic-annual-owner-only-2026!')
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'NAN','country':'Norway','default_currency':'NOK',
            'tax_id':'999999984','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        def account(code,title,kind,root):
            d=frappe.get_doc({'doctype':'Account','company':C,'account_number':code,'account_name':title,'account_type':kind,
                'parent_account':frappe.db.get_value('Account',{'company':C,'root_type':root,'is_group':1})}).insert();a[code]=d.name;return d.name
        c.accumulated_depreciation_account=account('1299','Synthetic annual accumulated depreciation','Accumulated Depreciation','Asset')
        c.depreciation_expense_account=a['6017'];c.depreciation_cost_center=c.cost_center
        c.disposal_account=account('3800','Synthetic annual asset result','Income Account','Income');c.save()
        for group,code in [('c','1230'),('e','1211'),('f','1212'),('g','1213'),('h','1214'),('i','1215'),('j','1216')]:
            if code not in a:account(code,'Synthetic annual asset '+group,'Fixed Asset','Asset')
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        supplier=frappe.db.get_value('Supplier',{'supplier_name':'Synthetic tax supplier'})
        customer=frappe.db.get_value('Customer',{'customer_name':'Synthetic tax customer'})
        facts=frappe.get_doc({'doctype':tax.FACTS,'company':C,'fiscal_year':'2026'}).insert()
        def journal(day,lines,opening=False):
            d=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':day,'user_remark':'Synthetic documented native annual source',
                'voucher_type':'Opening Entry' if opening else 'Journal Entry','is_opening':'Yes' if opening else 'No',
                'accounts':[dict(account=a[code],debit_in_account_currency=debit,credit_in_account_currency=credit,
                    cost_center=c.cost_center,**extras) for code,debit,credit,extras in lines]}).insert();d.submit();return d
        frappe.set_user(OWNER)
        journal('2026-01-01',[('1920',500000,0,{}),('2050',0,500000,{})],True)
        journal('2026-02-01',[('1920',200000,0,{}),('3020',0,200000,{})])
        journal('2026-02-02',[('7799',1000,0,{}),('1920',0,1000,{})])
        journal('2026-02-03',[('8150',30000,0,{}),('1920',0,30000,{})])
        journal('2026-02-04',[('1920',2000,0,{}),('8050',0,2000,{})])
        journal('2026-02-05',[('2070',3000,0,{}),('1920',0,3000,{})])
        journal('2026-02-06',[('1080',100000,0,{EFFECT:'New tax basis'}),('1920',0,100000,{})])
        facts.append('pools',dict(saldo_group='b',asset_account=a['1080'],opening_reference='Synthetic new goodwill balance',use_maximum=1))
        assets={}
        for group,code in [('c','1230'),('e','1211'),('f','1212'),('g','1213'),('h','1214'),('i','1215'),('j','1216')]:
            frappe.set_user('Administrator')
            cat=frappe.get_doc({'doctype':'Asset Category','asset_category_name':'Synthetic annual category '+group,
                'accounts':[{'company_name':C,'fixed_asset_account':a[code],'accumulated_depreciation_account':a['1299'],'depreciation_expense_account':a['6017']}]}).insert()
            item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-ENK-ANNUAL-'+group,'item_name':'Synthetic annual asset '+group,
                'item_group':'Products','stock_uom':'Nos','is_stock_item':0,'is_fixed_asset':1,'auto_create_assets':1,
                'asset_naming_series':'ACC-ASS-.YYYY.-','asset_category':cat.name}).insert()
            frappe.set_user(OWNER)
            pi=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier,'currency':'NOK','conversion_rate':1,
                'posting_date':'2026-03-01','bill_date':'2026-03-01','bill_no':'SYNTHETIC-ANNUAL-'+group,'set_posting_time':1,
                'due_date':'2026-12-31','disable_rounded_total':1,'update_stock':1,
                'items':[{'item_code':item.name,'qty':1,'rate':100000,'expense_account':a[code],'cost_center':c.cost_center,
                    'warehouse':frappe.db.get_value('Warehouse', {'company': C, 'is_group': 0}),'asset_location':'Synthetic tax asset location','asset_naming_series':'ACC-ASS-.YYYY.-'}]}).insert();pi.submit()
            asset=frappe.get_doc('Asset',frappe.db.get_value('Asset',{'purchase_invoice':pi.name}))
            asset.available_for_use_date='2026-03-01';asset.calculate_depreciation=0;asset.save();asset.submit()
            assets[group]=(asset,item,pi)
            facts.append('pools',dict(saldo_group=group,asset_account=a[code],asset=asset.name if group in 'efghij' else None,
                unit_reference='Synthetic native asset and building '+group,opening_reference='Synthetic new annual tax unit',use_maximum=1))
        facts.save()
        before=tax.collect(C,'2026')
        assert before['tax_depreciation']==91000,before['tax_depreciation']
        # Native sale: e realizes 40k gain; no e depreciation in realization year.
        asset,item,pi=assets['e']
        sale=frappe.get_doc({'doctype':'Sales Invoice','company':C,'customer':customer,'posting_date':'2026-10-01',
            'set_posting_time':1,'currency':'NOK','conversion_rate':1,'due_date':'2026-12-31','disable_rounded_total':1,
            'items':[{'item_code':item.name,'asset':asset.name,'qty':1,'rate':140000,'cost_center':c.cost_center}]}).insert();sale.submit()
        # Native scrap: i tax loss 100k => max 20k deduction on gain/loss pool,
        # combined with the e gain leaves 60k loss => 12k deduction.
        scrap_asset(assets['i'][0].name,'2026-10-02')
        b=tax.collect(C,'2026')
        assert b['gain_loss']['transfers']==-60000,b['gain_loss']
        assert b['gain_loss']['deduction']==12000,b['gain_loss']
        assert b['tax_depreciation']==75000,b['tax_depreciation']
        assert b['tax_profit']==85000,b['tax_profit']
        # Cancellation/restoration uses the native reversal, no tax ledger.
        restore_asset(assets['i'][0].name)
        assert tax.collect(C,'2026')['gain_loss']['transfers']==40000
        scrap_asset(assets['i'][0].name,'2026-10-02')
        facts.reload();facts.person_enabled=1;facts.capital_return_base_gross=200000;facts.shielding_base_net=100000
        facts.qualifying_business_debt=300000;facts.person_reference='Synthetic gross/net base, debt and carry: independently documented'
        facts.person_negative_carry=5000;facts.shielding_choice='Not assessed'
        facts.append('person_items',dict(role='Capital income',account=a['8050'],reference='Native posted interest income'))
        facts.append('person_items',dict(role='Qualifying business debt interest',account=a['8150'],reference='Native posted qualifying interest'))
        facts.save();assert tax.collect(C,'2026')['person_income'] is None
        facts.shielding_choice='Documented amount';facts.shielding_amount=4000
        facts.append('tax_values',dict(account=a['1920'],tax_method='Book values confirmed',wealth_method='Tax value before discount',reference='Synthetic bank reconciliation'))
        facts.append('tax_values',dict(account=a['1080'],tax_method='Documented values',tax_opening=0,tax_closing=80000,
            wealth_method='Not taxable',reference='Synthetic goodwill tax basis and wealth exemption'))
        facts.save();b=tax.collect(C,'2026')
        assert b['person_income']['interest_addback']==10000
        assert b['person_income']['person_income']==84000,b['person_income']
        byaccount={r['account']:r for r in b['annual_accounts']}
        assert byaccount[a['1920']]['wealth']==byaccount[a['1920']]['closing']
        assert byaccount[a['1080']]['tax_closing']==80000 and byaccount[a['1080']]['wealth']==0
        assert any(r['code']=='8050' and r['book']==2000 for r in b['annual_posts'])
        assert any(r['account']==a['2070'] and r['amount']==3000 for r in b['owner_movements'])
        # Disabled used accounts survive; unknown customised accounts remain visible.
        frappe.set_user('Administrator');disabled=frappe.get_doc('Account',a['7799']);disabled.disabled=1;disabled.save()
        frappe.set_user(OWNER);assert tax.collect(C,'2026')['tax_profit']==85000
        def duplicate_value():
            f=frappe.get_doc(tax.FACTS,facts.name);f.append('tax_values',dict(f.tax_values[0].as_dict(),name=None));f.save()
        rejected(duplicate_value,'hver balansekonto')
        before_gl=frappe.db.count('GL Entry',{'company':C})
        result=run_report('Norsk ENK-grunnlag',filters=frappe.as_json({'company':C,'fiscal_year':'2026','show_accounts':1}),ignore_prepared_report=True,
            js_filters=[{'fieldname':'company','fieldtype':'Link','options':'Company'}])
        assert result['report_summary'][1]['value']==85000
        assert frappe.db.count('GL Entry',{'company':C})==before_gl
        edge_cases()
        csv_sha256=exported_csv()
        proof=save_file('synthetic-enk-annual-report.json',frappe.as_json(result),tax.FACTS,facts.name,is_private=1)
        evidence=save_file('synthetic-enk-annual-evidence.json',frappe.as_json({'basis':snapshot(),'proof':proof.name,'csv_sha256':csv_sha256,
            'sha256':hashlib.sha256(Path(proof.get_full_path()).read_bytes()).hexdigest()}),tax.FACTS,facts.name,is_private=1)
        frappe.set_user('Administrator');frappe.db.set_default('runtime_enk_annual',evidence.name);frappe.db.commit()
        print('PASS native b/c/e-j acquisitions, ordinary journal metadata, sale/scrap/restore, gain/loss, account statement, wealth before discounts, person income, disabled account and no report GL writes')
finally:frappe.destroy()
