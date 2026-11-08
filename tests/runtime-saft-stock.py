"""Native stock cost sources, LCV/repost, credits, payments and exported restore."""
import os,sys,json,hashlib
from decimal import Decimal
from pathlib import Path
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import saft,saft_builder as xml,vat
from erpnext_norway.vat_catalog import CODE
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Stock';OWNER='runtime-saft-stock@example.invalid';NS={'s':xml.NS}
def export():
    data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);root=etree.fromstring(data)
    gl=frappe.get_all('GL Entry',filters={'company':C},fields=['*'])
    lines={r.find('s:RecordID',NS).text:r for r in root.findall('.//s:Line',NS)}
    assert set(lines)=={r.name for r in gl}
    for r in gl:
        amount=lines[r.name].find('s:'+('DebitAmount' if r.debit else 'CreditAmount'),NS)
        assert Decimal(amount.find('s:Amount',NS).text)==xml._money(r.debit or r.credit)
        foreign=r.account_currency and r.account_currency!='NOK'
        currency=r.account_currency if foreign else (r.transaction_currency if r.transaction_currency!='NOK' else None)
        if currency:
            assert amount.find('s:CurrencyCode',NS).text==currency
            assert Decimal(amount.find('s:CurrencyAmount',NS).text)==abs(Decimal(str(r.debit_in_account_currency if foreign else r.debit_in_transaction_currency))-Decimal(str(r.credit_in_account_currency if foreign else r.credit_in_transaction_currency)))
    for side in ('debit','credit'):
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in gl),Decimal())
    infos=root.xpath('.//s:TaxInformation[s:TaxCode="20" or s:TaxCode="21" or s:TaxCode="22"]',namespaces=NS)
    assert infos and all(not i.xpath('s:TaxBase',namespaces=NS) for i in infos)
    for info in infos:
        code=info.xpath('string(s:TaxCode)',namespaces=NS)
        assert info.xpath('s:TaxPercentage/text()',namespaces=NS)==[{'20':'0.00','21':'25.00','22':'15.00'}[code]]
    assert all(i.xpath('s:DebitTaxAmount/s:Amount/text()|s:CreditTaxAmount/s:Amount/text()',namespaces=NS)==['0.00'] for i in infos)
    return data,gl

def complete_repost():
    # Queues are deliberately stopped in the fixture. Use the same native job
    # function for this company only; never implement valuation in the test.
    frappe.db.commit();user=frappe.session.user;frappe.set_user('Administrator')
    for name in frappe.get_all('Repost Item Valuation',filters={'company':C,'docstatus':1,'status':'Queued'},order_by='posting_date, posting_time, creation',pluck='name'):
        job=frappe.get_doc('Repost Item Valuation',name)
        if job.status!='Queued':continue
        assert job.company==C;repost(job);frappe.db.commit();job.reload();assert job.status=='Completed'
    frappe.set_user(user)

def rejected(action,text):
    try:action()
    except frappe.ValidationError as error:assert text in str(error),str(error)
    else:raise AssertionError('Unsupported stock source accepted')
try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_saft_stock')).get_content());frappe.set_user(OWNER);data,gl=export()
        keys=('name','account','debit','credit','transaction_currency','debit_in_transaction_currency','credit_in_transaction_currency','is_cancelled')
        assert sorted(tuple(str(r[k]) for k in keys) for r in gl)==sorted(tuple(str(r[k]) for k in keys) for r in e['gl'])
        stock=frappe.get_list('Stock Ledger Entry',filters={'company':C},fields=['name','voucher_no','voucher_detail_no','actual_qty','stock_value_difference','is_cancelled'],limit_page_length=0)
        assert sorted(frappe.as_json(r) for r in stock)==sorted(frappe.as_json(r) for r in e['stock'])
        for name in e['paid']:assert frappe.get_doc('Purchase Invoice',name).outstanding_amount==0
        assert frappe.get_doc('Landed Cost Voucher',e['lcv']).docstatus==2
        assert frappe.get_doc('Purchase Invoice',e['cancelled']).docstatus==2
        f=frappe.get_doc('File',e['file']);assert f.is_private and hashlib.sha256(Path(f.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored native SAF-T stock costs20/21/22 NOK/EUR, LCV/partial return/payment/refund/repost, exact GL and SLE and private XML')
    else:
        frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-SAFT-STOCK-FEE-SHORT','item_name':'Synthetic fee','item_group':'Services','stock_uom':'Nos','is_stock_item':0}).insert()
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic stock owner','send_welcome_email':0,'roles':[{'role':r} for r in ['Accounts Manager','Accounts User','Purchase Manager','Stock Manager']]}).insert()
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SST','country':'Norway','default_currency':'NOK',
            'tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',
            vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        valuation=frappe.get_doc({'doctype':'Account','company':C,'account_number':'4998','account_name':'Synthetic import valuation',
            'parent_account':frappe.db.get_value('Account',{'company':C,'root_type':'Expense','is_group':1}),
            'account_type':'Expenses Included In Valuation'}).insert();a['4998']=valuation.name
        unbilled=frappe.get_doc({'doctype':'Account','company':C,'account_number':'2998','account_name':'Synthetic import unbilled',
            'parent_account':frappe.db.get_value('Account',{'company':C,'root_type':'Liability','is_group':1}),
            'account_type':'Stock Received But Not Billed'}).insert()
        c.default_inventory_account=a['1460'];c.stock_received_but_not_billed=unbilled.name;c.enable_perpetual_inventory=1
        c.exchange_gain_loss_account=a['8160'];c.default_bank_account=a['1920'];c.save()
        stock=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-SAFT-STOCK-SHORT','item_name':'Synthetic physical import stock',
            'item_group':'Products','stock_uom':'Nos','is_stock_item':1,'valuation_method':'FIFO',
            'item_defaults':[{'company':C,'expense_account':a['4300'],'default_warehouse':'Stores - SST'}]}).insert()
        eur_account=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic import EUR payable',
            'parent_account':frappe.db.get_value('Account',a['2400'],'parent_account'),'account_type':'Payable','account_currency':'EUR'}).insert()
        group=frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0]
        eur_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic short EUR supplier','supplier_type':'Company',
            'supplier_group':group,'default_currency':'EUR','accounts':[{'company':C,'account':eur_account.name}]}).insert()
        nok_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic short NOK supplier','supplier_type':'Company',
            'supplier_group':group,'default_currency':'NOK'}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        def template(title):return frappe.db.get_value('Item Tax Template',{'company':C,'title':title})
        def purchase(amount,item,expense,title,foreign=False):
            doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':eur_supplier.name if foreign else nok_supplier.name,
                'currency':'EUR' if foreign else 'NOK','conversion_rate':10 if foreign else 1,'posting_date':'2026-09-15',
                'bill_date':'2026-09-15','set_posting_time':1,'bill_no':'SYN-GOODS' if item==stock.name else 'SYN-FEES','due_date':'2026-10-31',
                'disable_rounded_total':1,'update_stock':int(item==stock.name),
                'items':[{'item_code':item,'qty':3 if item==stock.name else 1,'rate':amount/3 if item==stock.name else amount,'warehouse':'Stores - SST','expense_account':a[expense],
                    'cost_center':c.cost_center,'item_tax_template':template(title)}]}).insert();doc.submit();return doc
        for number,category,group in [('1460','balanseverdiForOmloepsmiddel','1400'),('1920','balanseverdiForOmloepsmiddel','1920'),('2400','kortsiktigGjeld','2400'),('4300','varekostnad','4005'),('4998','varekostnad','4005'),('8160','finanskostnad','8160')]:
            acc=frappe.get_doc('Account',a[number]);acc.append(saft.MAPPING,{'year':2026,'category':category,'code':group});acc.save()
        eur_account.append(saft.MAPPING,{'year':2026,'category':'kortsiktigGjeld','code':'2400'});eur_account.save()
        unbilled.append(saft.MAPPING,{'year':2026,'category':'kortsiktigGjeld','code':'2990'});unbilled.save()
        goods=purchase(300,stock.name,'4300','Vareimport – leverandørfaktura, 25 % ved innførsel',True)
        fees=purchase(1700,'RUNTIME-SAFT-STOCK-FEE-SHORT','4998','Uten MVA-behandling')
        def landed(amount,source=None):
            doc=frappe.get_doc({'doctype':'Landed Cost Voucher','company':C,'posting_date':'2026-09-20',
                'distribute_charges_based_on':'Amount','purchase_receipts':[{'receipt_document_type':'Purchase Invoice','receipt_document':goods.name}],
                'taxes':[{'expense_account':a['4998'],'description':'Synthetic documented import cost','amount':amount}],
                'vendor_invoices':[{'vendor_invoice':source,'amount':amount}] if source else []})
            doc.get_items_from_purchase_receipts();doc.insert();doc.submit();return doc
        duty=landed(1700,fees.name)
        _,gl=export()
        assert sum(Decimal(str(r.debit))-Decimal(str(r.credit)) for r in gl if r.account==a['1460'])==4700
        created_exchange=None
        if not frappe.db.exists('Currency Exchange',{'date':frappe.utils.nowdate(),'from_currency':'EUR','to_currency':'NOK'}):
            created_exchange=frappe.get_doc({'doctype':'Currency Exchange','date':frappe.utils.nowdate(),'from_currency':'EUR','to_currency':'NOK','exchange_rate':10,'for_buying':1,'for_selling':1}).insert().name
        pay=get_payment_entry('Purchase Invoice',goods.name,bank_account=a['1920'],bank_amount=3300);pay.posting_date=pay.reference_date='2026-09-22';pay.reference_no='SYN-PAY';pay.target_exchange_rate=11;pay.received_amount=goods.outstanding_amount;pay.set_amounts();pay.insert();pay.submit()
        paid_fee=get_payment_entry('Purchase Invoice',fees.name,bank_account=a['1920'],bank_amount=1700);paid_fee.posting_date=paid_fee.reference_date='2026-09-22';paid_fee.reference_no='SYN-FEE-PAY';paid_fee.insert();paid_fee.submit()
        credit=make_return_doc('Purchase Invoice',goods.name);credit.posting_date=credit.bill_date='2026-09-25';credit.set_posting_time=1;credit.bill_no='SYN-RETURN';credit.items[0].qty=credit.items[0].received_qty=-1;credit.update_outstanding_for_self=1;credit.insert();credit.submit()
        refund=get_payment_entry('Purchase Invoice',credit.name,bank_account=a['1920'],bank_amount=1100);refund.posting_date=refund.reference_date='2026-09-26';refund.reference_no='SYN-REFUND';refund.source_exchange_rate=11;refund.paid_amount=abs(credit.outstanding_amount);refund.set_amounts();refund.insert();refund.submit()
        export()
        duty.reload();duty.cancel()
        rejected(export,'lagerrepostering')
        complete_repost()
        frappe.set_user(OWNER);_,gl=export()
        assert sum(Decimal(str(r.debit))-Decimal(str(r.credit)) for r in gl if r.account==a['1460'])==2000
        assert sum(Decimal(str(r.debit))-Decimal(str(r.credit)) for r in gl if r.account==a['8160'])==200
        titles=['Vareimport – kostnad uten MVA-behandling','Vareimport – leverandørfaktura, 25 % ved innførsel','Vareimport – leverandørfaktura, 15 % ved innførsel']
        cancelled=None
        for currency in ('NOK','EUR'):
            for code,title in zip(('20','21','22'),titles):
                doc=frappe.copy_doc(goods);doc.bill_no='SYN-'+currency+code;doc.posting_date=doc.bill_date='2026-09-28';doc.posting_time=frappe.utils.nowtime();doc.supplier=eur_supplier.name if currency=='EUR' else nok_supplier.name;doc.currency=currency;doc.conversion_rate=10 if currency=='EUR' else 1;doc.credit_to=eur_account.name if currency=='EUR' else a['2400'];doc.set('items',[]);doc.set('taxes',[])
                for rate in ((40,60) if currency=='EUR' else (400,600)):
                    doc.append('items',{'item_code':stock.name,'qty':1,'rate':rate,'warehouse':'Stores - SST','expense_account':a['4300'],'cost_center':c.cost_center,'item_tax_template':template(title)})
                doc.insert();doc.submit();assert {r.get(CODE) for r in doc.items}=={code};export()
                if currency=='NOK' and code=='20':doc.cancel();cancelled=doc.name;complete_repost();export()
        frappe.db.savepoint('mixed_stock')
        mixed=frappe.copy_doc(doc);mixed.bill_no='SYN-MIX';mixed.posting_time=frappe.utils.nowtime();mixed.items[0].item_tax_template=template(titles[1]);mixed.insert();mixed.submit()
        assert {r.get(CODE) for r in mixed.items}=={'21','22'}
        data,_=export();assert {'21','22'} <= set(etree.fromstring(data).xpath('.//s:Line[s:SourceDocumentID="'+mixed.name+'"]/s:TaxInformation/s:TaxCode/text()',namespaces=NS))
        frappe.db.rollback(save_point='mixed_stock')
        frappe.db.savepoint('two_stock_accounts');frappe.set_user('Administrator')
        extra=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic second stock','account_number':'1461','account_type':'Stock','parent_account':frappe.db.get_value('Account',a['1460'],'parent_account')}).insert()
        warehouse=frappe.get_doc({'doctype':'Warehouse','company':C,'warehouse_name':'Synthetic second stock','parent_warehouse':frappe.db.get_value('Warehouse','Stores - SST','parent_warehouse'),'account':extra.name}).insert()
        frappe.set_user(OWNER)
        split=frappe.copy_doc(doc);split.bill_no='SYN-SPLIT';split.posting_date=split.bill_date='2026-09-29';split.posting_time=frappe.utils.nowtime();split.items[0].warehouse=warehouse.name;split.insert();split.submit()
        split_gl=frappe.get_all('GL Entry',filters={'company':C,'voucher_type':'Purchase Invoice','voucher_no':split.name},fields=['*'])
        assert {r.account for r in split_gl if r.account in {a['1460'],extra.name}}=={a['1460'],extra.name}
        mapped,_=saft.invoice_taxes(split,split_gl);assert {r.name for r in split_gl if r.account in {a['1460'],extra.name}} <= set(mapped)
        mixed_split=frappe.copy_doc(split);mixed_split.bill_no='SYN-MIX-SPLIT';mixed_split.posting_date=mixed_split.bill_date='2026-09-30';mixed_split.posting_time=frappe.utils.nowtime();mixed_split.items[0].item_tax_template=template(titles[1]);mixed_split.insert();mixed_split.submit()
        mixed_gl=frappe.get_all('GL Entry',filters={'company':C,'voucher_type':'Purchase Invoice','voucher_no':mixed_split.name},fields=['*'])
        rejected(lambda:saft.invoice_taxes(mixed_split,mixed_gl),'Blandede importkoder')
        frappe.db.rollback(save_point='two_stock_accounts')
        frappe.db.savepoint('stock_permission');frappe.set_user('Administrator')
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Item','for_value':'RUNTIME-SAFT-STOCK-FEE-SHORT','apply_to_all_doctypes':0,'applicable_for':'Stock Ledger Entry'}).insert()
        frappe.clear_cache(user=OWNER);frappe.set_user(OWNER)
        assert frappe.has_permission('Stock Ledger Entry','read')
        assert not frappe.get_list('Stock Ledger Entry',filters={'company':C},pluck='name',limit_page_length=0)
        try:export()
        except frappe.PermissionError:pass
        else:raise AssertionError('Unread stock sources accepted')
        frappe.db.rollback(save_point='stock_permission');frappe.clear_cache(user=OWNER);frappe.set_user(OWNER)
        if created_exchange:frappe.set_user('Administrator');frappe.delete_doc('Currency Exchange',created_exchange);frappe.set_user(OWNER)
        data,gl=export()
        assert sum(Decimal(str(r.debit))-Decimal(str(r.credit)) for r in gl if r.account==a['1460'])==7000
        period=etree.fromstring(saft.build(C,'2026-09-28','2026-09-30'))
        assert set(period.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in gl if str(r.posting_date)>='2026-09-28'}
        f=save_file('synthetic-saft-stock.xml',data,'Company',C,is_private=1)
        stock_rows=frappe.get_list('Stock Ledger Entry',filters={'company':C},fields=['name','voucher_no','voucher_detail_no','actual_qty','stock_value_difference','is_cancelled'],limit_page_length=0)
        e={'file':f.name,'sha256':hashlib.sha256(data).hexdigest(),'gl':gl,'stock':stock_rows,'paid':[goods.name,fees.name,credit.name],'lcv':duty.name,'cancelled':cancelled}
        evidence=save_file('synthetic-saft-stock-evidence.json',frappe.as_json(e).encode(),'Company',C,is_private=1)
        frappe.db.set_default('runtime_saft_stock',evidence.name);frappe.db.commit()
        print('PASS native SAF-T stock costs20/21/22 NOK/EUR: purchases, LCV, partial return, payments/refund, FX200, cancelled LCV and core repost; mixed codes on one account and one code across accounts; ambiguous allocation and unread sources rejected; exact GL/SLE and XSD')
finally:frappe.db.rollback();frappe.destroy()
