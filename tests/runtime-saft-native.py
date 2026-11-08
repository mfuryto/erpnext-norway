"""Probe native assets, stock VAT and year closing without a second ledger."""
import os,sys,json,hashlib
from pathlib import Path
from frappe.utils.file_manager import save_file
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import saft,saft_builder as xml,vat
from erpnext_norway.vat_catalog import CODE,DEDUCTION
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.assets.doctype.asset.depreciation import make_depreciation_entry
C='Runtime SAF-T Native Completion';OWNER='runtime-saft-native@example.invalid';NS={'s':xml.NS}
GROUPS={'1250':('balanseverdiForAnleggsmiddel','1205'),'1460':('balanseverdiForOmloepsmiddel','1400'),
'1500':('balanseverdiForOmloepsmiddel','1500'),'1920':('balanseverdiForOmloepsmiddel','1920'),
'2050':('egenkapital','2050'),'2400':('kortsiktigGjeld','2400'),'2998':('kortsiktigGjeld','2990'),
'2700':('kortsiktigGjeld','2740'),'2710':('kortsiktigGjeld','2740'),'3020':('salgsinntekt','3000'),
'4300':('varekostnad','4005'),'4998':('varekostnad','4005'),'6000':('annenDriftskostnad','6000'),
'1299':('balanseverdiForAnleggsmiddel','1205'),
'6100':('annenDriftskostnad','6100'),'2713':('kortsiktigGjeld','2740'),'4500':('varekostnad','4500'),'2401':('kortsiktigGjeld','2400'),
'2718':('kortsiktigGjeld','2740'),'2709':('kortsiktigGjeld','2740'),'2719':('kortsiktigGjeld','2740'),'2704':('kortsiktigGjeld','2740'),'2714':('kortsiktigGjeld','2740'),'8160':('finanskostnad','8160'),'3800':('annenDriftsinntekt','3890')}
def export(label):
 user=frappe.session.user;frappe.set_user('Administrator')
 for name in set(frappe.get_all('GL Entry',filters={'company':C},pluck='account')):
  a=frappe.get_doc('Account',name)
  if a.get(saft.MAPPING):continue
  category,code=GROUPS[a.account_number];a.append(saft.MAPPING,{'year':2026,'category':category,'code':code});a.save()
 frappe.set_user(user)
 data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);root=etree.fromstring(data)
 rows=frappe.get_all('GL Entry',filters={'company':C},fields=['*'])
 lines={r.name:root.xpath('.//s:Line[s:RecordID="'+r.name+'"]',namespaces=NS) for r in rows}
 assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in rows}
 for r in rows:
  for side in ('debit','credit'):
   amounts=[Decimal(v) for line in lines[r.name] for v in line.xpath('s:'+side.title()+'Amount/s:Amount/text()',namespaces=NS)]
   assert sum(amounts,Decimal())==xml._money(r[side]),(r,side,amounts)
   foreign=r.account_currency and r.account_currency!='NOK'
   currency=r.account_currency if foreign else (r.transaction_currency if r.transaction_currency!='NOK' else None)
   if currency and amounts:
    values=[v for line in lines[r.name] for v in line.xpath('s:'+side.title()+'Amount/s:CurrencyAmount/text()',namespaces=NS)]
    expected=r[side+'_in_account_currency'] if foreign else r[side+'_in_transaction_currency']
    assert sum((Decimal(v) for v in values),Decimal())==xml._money(expected),(r,side,values)
    assert all(line.xpath('s:'+side.title()+'Amount/s:CurrencyCode/text()',namespaces=NS)==[currency] for line in lines[r.name] if line.find('s:'+side.title()+'Amount',NS) is not None)
 for side in ('debit','credit'):assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in rows),Decimal())
 print('PASS native SAF-T',label,'GL',len(rows),flush=True);return root
def sources():
 result={}
 for doctype,fields in [('GL Entry',['name','account','debit','credit','posting_date','voucher_type','voucher_no','is_cancelled','transaction_currency','debit_in_transaction_currency','credit_in_transaction_currency','account_currency','debit_in_account_currency','credit_in_account_currency','voucher_detail_no','cost_center','project']),('Stock Ledger Entry',['name','voucher_type','voucher_no','voucher_detail_no','actual_qty','stock_value_difference','is_cancelled']),('Asset',['name','purchase_invoice','purchase_receipt','net_purchase_amount','value_after_depreciation','docstatus'])]:
  result[doctype]=frappe.get_all(doctype,filters={'company':C},fields=fields,order_by='name')
 for doctype in ('Purchase Invoice','Sales Invoice','Purchase Receipt','Journal Entry','Stock Entry','Stock Reconciliation'):
  result[doctype]=[frappe.get_doc(doctype,name).as_dict() for name in frappe.get_all(doctype,filters={'company':C,'docstatus':['in',[1,2]]},pluck='name',order_by='name')]
 return json.loads(frappe.as_json(result))

if sys.argv[1]=='verify':
 try:
  e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_saft_native')).get_content())
  frappe.set_user(OWNER);export('restored native sources')
  assert sources()==e['sources']
  file=frappe.get_doc('File',e['file']);assert file.is_private
  assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()==e['sha256']
  print('PASS restored SAF-T native assets, stock, receipts, EUR primary journal, specifications, exact GL/SLE/source metadata and private XML')
 finally:frappe.destroy()
 raise SystemExit(0)

try:
 frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic SAF-T native owner','send_welcome_email':0,'roles':[{'role':r} for r in ['Accounts Manager','Accounts User','Purchase Manager','Purchase User','Sales Manager','Sales User','Stock Manager','Stock User']]}).insert()
 c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SNC','country':'Norway','default_currency':'NOK','tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
 a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
 def account(number,title,type,root):
  doc=frappe.get_doc({'doctype':'Account','company':C,'account_number':number,'account_name':title,'account_type':type,'parent_account':frappe.db.get_value('Account',{'company':C,'root_type':root,'is_group':1})}).insert();a[number]=doc.name;return doc.name
 c.default_bank_account=a['1920'];c.default_inventory_account=a['1460'];c.stock_received_but_not_billed=account('2998','Synthetic unbilled','Stock Received But Not Billed','Liability')
 c.expenses_included_in_valuation=account('4998','Synthetic valuation','Expenses Included In Valuation','Expense')
 c.accumulated_depreciation_account=account('1299','Synthetic accumulated depreciation','Accumulated Depreciation','Asset')
 c.depreciation_expense_account=a.get('6000') or account('6000','Synthetic depreciation','Depreciation','Expense')
 c.disposal_account=a.get('3800') or account('3800','Synthetic disposal','Income Account','Income')
 c.exchange_gain_loss_account=a['8160'];c.depreciation_cost_center=c.cost_center;c.enable_perpetual_inventory=1;c.save()
 cat=frappe.get_doc({'doctype':'Asset Category','asset_category_name':'Synthetic SAF-T equipment','accounts':[{'company_name':C,'fixed_asset_account':a['1250'],'accumulated_depreciation_account':a['1299'],'depreciation_expense_account':a['6000']}]}).insert()
 loc=frappe.get_doc({'doctype':'Location','location_name':'Synthetic SAF-T equipment location'}).insert()
 for kind in ('ASSET','STOCK','SERVICE'):
  frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-SAFT-NATIVE-'+kind,'item_name':'Synthetic '+kind,'item_group':'Products' if kind!='SERVICE' else 'Services','stock_uom':'Nos','is_stock_item':int(kind=='STOCK'),'is_fixed_asset':int(kind=='ASSET'),'auto_create_assets':int(kind=='ASSET'),'asset_category':cat.name if kind=='ASSET' else None,'asset_naming_series':'ACC-ASS-.YYYY.-','item_defaults':[{'company':C,'expense_account':a['1250'] if kind=='ASSET' else a['4300'],'default_warehouse':'Stores - SNC'}]}).insert()
 supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic SAF-T native supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'NOK'}).insert()
 customer=frappe.get_doc({'doctype':'Customer','customer_name':'Synthetic SAF-T native customer','customer_type':'Company','customer_group':frappe.get_all('Customer Group',filters={'is_group':0},pluck='name')[0],'territory':'All Territories','default_currency':'NOK'}).insert()
 frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert();frappe.set_user(OWNER)
 template=frappe.db.get_value('Item Tax Template',{'company':C,'title':'MVA 25 % – varelinjer'})
 def purchase(kind,share=100):
  d=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,'currency':'NOK','conversion_rate':1,'posting_date':'2026-05-15','bill_date':'2026-05-15','set_posting_time':1,'bill_no':'SYNTHETIC-NATIVE-LONG-REFERENCE-UNCHANGED-'+kind+'-'+str(share),'due_date':'2026-10-31','disable_rounded_total':1,'update_stock':int(kind!='SERVICE'),'items':[{'item_code':'RUNTIME-SAFT-NATIVE-'+kind,'qty':1 if kind=='ASSET' else 10,'rate':1000 if kind=='ASSET' else 100,'warehouse':'Stores - SNC','expense_account':a['1250'] if kind=='ASSET' else a['4300'],'cost_center':c.cost_center,'item_tax_template':template,DEDUCTION:share,'asset_location':loc.name,'asset_naming_series':'ACC-ASS-.YYYY.-'}]}).insert();d.submit();return d
 asset_pi=purchase('ASSET');root=export('direct fixed asset purchase')
 assert any(asset_pi.bill_no in value for value in root.xpath('.//s:Line/s:Description/text()',namespaces=NS))
 assert root.find('s:Header/s:UserID',NS).text==OWNER
 if len(OWNER)<=35:assert OWNER in root.xpath('.//s:Transaction/s:SourceID/text()',namespaces=NS)
 else:assert any(OWNER in value for value in root.xpath('.//s:Line/s:Description/text()',namespaces=NS))
 asset_name=frappe.get_all('Asset',filters={'purchase_invoice':asset_pi.name},pluck='name')[0]
 asset=frappe.get_doc('Asset',asset_name);asset.available_for_use_date='2026-05-15';asset.calculate_depreciation=1;asset.set('finance_books',[dict(depreciation_method='Straight Line',total_number_of_depreciations=2,frequency_of_depreciation=1,depreciation_start_date='2026-06-15',expected_value_after_useful_life=0)]);asset.save();asset.submit()
 schedule=frappe.db.get_value('Asset Depreciation Schedule',{'asset':asset.name,'status':'Active'})
 make_depreciation_entry(schedule,date='2026-06-15');export('native depreciation')
 def sale(amount):
  d=frappe.get_doc({'doctype':'Sales Invoice','company':C,'customer':customer.name,'currency':'NOK','conversion_rate':1,'posting_date':'2026-06-20','set_posting_time':1,'due_date':'2026-10-31','disable_rounded_total':1,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-ASSET','asset':asset.name,'qty':1,'rate':amount,'income_account':a['3020'],'cost_center':c.cost_center,'item_tax_template':template}]}).insert();d.submit();return d
 s=sale(1200);export('asset disposal at gain')
 credit=make_return_doc('Sales Invoice',s.name);credit.posting_date='2026-06-21';credit.set_posting_time=1;credit.insert();credit.submit();export('native asset regain credit')
 # All sales/return amounts remain exactly those posted by ERPNext.
 goods=purchase('STOCK');export('domestic stock input VAT')
 for share in (60,0):purchase('STOCK',share);export('domestic stock deduction'+str(share))
 # Native multi-warehouse posting preserves the source row/account relation.
 second=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic second stock','account_number':'1461','account_type':'Stock','parent_account':frappe.db.get_value('Account',a['1460'],'parent_account')}).insert()
 second.append(saft.MAPPING,{'year':2026,'category':'balanseverdiForOmloepsmiddel','code':'1400'});second.save()
 frappe.set_user('Administrator')
 second_center=frappe.get_doc({'doctype':'Cost Center','company':C,'cost_center_name':'Synthetic second stock center','parent_cost_center':frappe.db.get_value('Cost Center',{'company':C,'is_group':1}),'is_group':0}).insert()
 warehouse=frappe.get_doc({'doctype':'Warehouse','warehouse_name':'Synthetic second stores','company':C,'account':second.name}).insert()
 frappe.set_user(OWNER)
 mixed=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,'currency':'NOK','conversion_rate':1,'posting_date':'2026-07-01','bill_date':'2026-07-01','set_posting_time':1,'bill_no':'SYN-MULTI-STOCK','due_date':'2026-10-31','disable_rounded_total':1,'update_stock':1,'items':[
  {'item_code':'RUNTIME-SAFT-NATIVE-STOCK','qty':3,'rate':100,'warehouse':wh,'expense_account':a['4300'],'cost_center':center,'item_tax_template':template} for wh,center in (('Stores - SNC',c.cost_center),(warehouse.name,second_center.name))]}).insert();mixed.submit()
 root=export('native multiple posted stock accounts')
 assert {r.account for r in frappe.get_all('GL Entry',filters={'voucher_type':mixed.doctype,'voucher_no':mixed.name},fields=['account'])} >= {a['1460'],second.name}
 for number in ('1460','1461'):
  assert root.xpath('.//s:Line[s:SourceDocumentID="'+mixed.name+'" and s:AccountID="'+number+'"]/s:TaxInformation[s:TaxCode="1"]',namespaces=NS)
 mixed.cancel()
 # Finish this company's native queued repost before requesting another export.
 from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost
 frappe.db.commit();frappe.set_user('Administrator')
 for name in frappe.get_all('Repost Item Valuation',filters={'company':C,'docstatus':1,'status':'Queued'},order_by='posting_date, posting_time, creation',pluck='name'):
  job=frappe.get_doc('Repost Item Valuation',name)
  if job.status=='Queued':repost(job);frappe.db.commit();job.reload();assert job.status=='Completed'
 frappe.set_user(OWNER);export('native multiple stock accounts cancellation')
 # Same fixed asset: core sale without gain and with loss, followed by regain.
 from erpnext.assets.doctype.asset.depreciation import get_value_after_depreciation_on_disposal_date
 asset_name=asset.name;customer_name=customer.name
 for label,date,price in [('zero gain','2026-06-22',None),('loss','2026-06-24',100)]:
  if price is None:price=get_value_after_depreciation_on_disposal_date(asset_name,date)
  d=frappe.get_doc({'doctype':'Sales Invoice','company':C,'customer':customer_name,'currency':'NOK','conversion_rate':1,'posting_date':date,'set_posting_time':1,'due_date':'2026-10-31','disable_rounded_total':1,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-ASSET','asset':asset_name,'qty':1,'rate':price,'income_account':a['3020'],'cost_center':c.cost_center,'item_tax_template':template}]}).insert();d.submit();export('asset sale '+label)
  credit=make_return_doc('Sales Invoice',d.name);credit.posting_date=frappe.utils.add_days(date,1);credit.set_posting_time=1;credit.insert();credit.submit();export('asset credit '+label)
 for share,value in ((60,1100),(0,1250)):
  p=purchase('ASSET',share);assert sum(frappe.get_all('Asset',filters={'purchase_invoice':p.name},pluck='net_purchase_amount'))==value;export('fixed asset deduction'+str(share))
 sale_stock=frappe.get_doc({'doctype':'Sales Invoice','company':C,'customer':customer_name,'currency':'NOK','conversion_rate':1,'posting_date':'2026-07-20','set_posting_time':1,'update_stock':1,'due_date':'2026-10-31','disable_rounded_total':1,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-STOCK','warehouse':'Stores - SNC','qty':1,'rate':150,'income_account':a['3020'],'expense_account':a['4300'],'cost_center':c.cost_center,'item_tax_template':template}]}).insert();sale_stock.submit();export('stock sale with native COGS')
 stock_credit=make_return_doc('Sales Invoice',sale_stock.name);stock_credit.posting_date='2026-07-21';stock_credit.set_posting_time=1;stock_credit.insert();stock_credit.submit();export('stock sale return')
 # Desk starts a new request after asset regain. The core's request-local
 # reverse-depreciation flag must not leak into later, unrelated payments.
 frappe.flags.pop('is_reverse_depr_entry',None)
 from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
 payment=get_payment_entry('Purchase Invoice',goods.name,bank_account=a['1920']);payment.posting_date=payment.reference_date='2026-07-18';payment.reference_no='SYN-NATIVE-PAY';payment.insert();payment.submit()
 goods_credit=make_return_doc('Purchase Invoice',goods.name);goods_credit.posting_date=goods_credit.bill_date='2026-07-22';goods_credit.set_posting_time=1;goods_credit.bill_no='SYN-NATIVE-GOODS-CREDIT';goods_credit.items[0].qty=goods_credit.items[0].received_qty=-2;goods_credit.update_outstanding_for_self=1;goods_credit.insert();goods_credit.submit()
 refund=get_payment_entry('Purchase Invoice',goods_credit.name,bank_account=a['1920']);refund.posting_date=refund.reference_date='2026-07-23';refund.reference_no='SYN-NATIVE-REFUND';refund.insert();refund.submit()
 assert goods.reload().outstanding_amount==goods_credit.reload().outstanding_amount==0,(goods.outstanding_amount,goods_credit.outstanding_amount,goods.grand_total,goods_credit.grand_total,payment.paid_amount,refund.received_amount);export('stock supplier partial return, payment and refund')
 from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
 receipts=[]
 for share in (100,60,0):
  r=frappe.get_doc({'doctype':'Purchase Receipt','company':C,'supplier':supplier.name,'currency':'NOK','conversion_rate':1,'posting_date':'2026-08-15','set_posting_time':1,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-STOCK','qty':10,'rate':100,'warehouse':'Stores - SNC','expense_account':a['4300'],'cost_center':c.cost_center,'item_tax_template':template,DEDUCTION:share}]}).insert();r.submit()
  p=make_purchase_invoice(r.name);p.posting_date=p.bill_date='2026-08-15';p.set_posting_time=1;p.bill_no='SYN-NATIVE-RECEIPT-'+str(share);p.due_date='2026-10-31';p.disable_rounded_total=1;p.insert();p.submit()
  assert p.items[0].expense_account==a['2998'];receipts.append((r,p));export('stock receipt/invoice deduction'+str(share))
 from erpnext_norway.vat_import import DATE,REFERENCE,receipt_rows
 from erpnext_norway.vat_journal import BASE
 declaration_reference='SYNTHETIC-DECLARATION-REFERENCE-PRESERVED-IN-FULL'
 r=frappe.get_doc({'doctype':'Purchase Receipt','company':C,'supplier':supplier.name,'currency':'NOK','conversion_rate':1,'posting_date':'2026-08-25','set_posting_time':1,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-STOCK','qty':10,'rate':100,'warehouse':'Stores - SNC','expense_account':a['4300'],'cost_center':c.cost_center,'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':'Vareimport – deklarasjon uten beregning av MVA'}),BASE:1300,DATE:'2026-08-20',REFERENCE:declaration_reference}]}).insert();r.submit()
 p=make_purchase_invoice(r.name);p.posting_date=p.bill_date='2026-08-25';p.set_posting_time=1;p.bill_no='SYN-NATIVE-ZERO-IMPORT';p.due_date='2026-10-31';p.disable_rounded_total=1;p.insert();p.submit();assert p.items[0].get(CODE)=='20'
 root=export('posted zero-import declaration')
 infos=root.xpath('.//s:TaxInformation[s:TaxCode="85"]',namespaces=NS);assert len(infos)==1
 assert infos[0].find('s:TaxBase',NS).text=='1300.00'
 assert '2026-08-20' in infos[0].find('s:TaxBaseDescription',NS).text
 assert any(declaration_reference in value for value in root.xpath('.//s:Line[s:SourceDocumentID="'+r.name+'"]/s:Description/text()',namespaces=NS))
 returned=make_return_doc('Purchase Receipt',r.name);returned.posting_date='2026-08-26';returned.set_posting_time=1;returned.items[0].qty=returned.items[0].received_qty=-2;returned.insert();returned.submit()
 credit=make_return_doc('Purchase Invoice',p.name);credit.posting_date=credit.bill_date='2026-08-26';credit.set_posting_time=1;credit.bill_no='SYN-NATIVE-IMPORT-CREDIT';credit.items[0].qty=credit.items[0].received_qty=-2;credit.insert();credit.submit()
 root=export('physical import return preserves declaration')
 assert len(root.xpath('.//s:TaxInformation[s:TaxCode="85"]',namespaces=NS))==1
 assert sum(row['base_amount'] for row in receipt_rows(C,frappe.utils.getdate('2026-08-01'),frappe.utils.getdate('2026-08-31')))==1300
 # Pure stock movements already have native GL and need no VAT adapter.
 entry=frappe.get_doc({'doctype':'Stock Entry','company':C,'stock_entry_type':'Material Receipt','posting_date':'2026-09-01','set_posting_time':1,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-STOCK','t_warehouse':'Stores - SNC','qty':2,'basic_rate':90,'expense_account':a['4300'],'cost_center':c.cost_center}]}).insert();entry.submit();export('ordinary stock entry')
 from erpnext.stock.utils import get_stock_balance
 qty,rate=get_stock_balance('RUNTIME-SAFT-NATIVE-STOCK','Stores - SNC','2026-09-02','12:00:00',with_valuation_rate=True)
 reconciliation=frappe.get_doc({'doctype':'Stock Reconciliation','company':C,'purpose':'Stock Reconciliation','posting_date':'2026-09-02','posting_time':'12:00:00','set_posting_time':1,'expense_account':a['4300'],'cost_center':c.cost_center,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-STOCK','warehouse':'Stores - SNC','qty':qty+1,'valuation_rate':rate}]}).insert();reconciliation.submit();export('ordinary stock reconciliation')
 # Primary service journal: recorded NOK basis1100, booked expense1110,
 # output275/input165 and EUR100 payable at10; native payment at10.5.
 from erpnext_norway.vat_catalog import RATE
 from erpnext_norway.vat_journal import SPEC
 payable=account('2401','Synthetic native EUR payable','Payable','Liability')
 eur_account=frappe.get_doc('Account',payable);eur_account.account_currency='EUR';eur_account.save()
 frappe.set_user('Administrator')
 eur_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic native EUR source supplier','supplier_type':'Company','supplier_group':supplier.supplier_group,'default_currency':'EUR','accounts':[{'company':C,'account':payable}]}).insert()
 frappe.set_user(OWNER)
 journal=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-20','bill_date':'2026-10-20','bill_no':'SYNTHETIC-NATIVE-SERVICE-SOURCE-REFERENCE','multi_currency':1,'user_remark':'Synthetic documented primary service:60 percent eligible, source VAT basis1100, booked vendorEUR100 at10',
  'accounts':[{'account':a['4500'],'debit_in_account_currency':1110,'cost_center':c.cost_center},
   {'account':a['2714'],'debit_in_account_currency':165,CODE:'86',RATE:25},
   {'account':a['2704'],'credit_in_account_currency':275,CODE:'86',RATE:25,BASE:1100,DEDUCTION:60},
   {'account':payable,'party_type':'Supplier','party':eur_supplier.name,'account_currency':'EUR','exchange_rate':10,'credit_in_account_currency':100}]}).insert();journal.submit()
 root=export('primary service EUR journal with documented60 percent')
 infos=root.xpath('.//s:Line[s:SourceDocumentID="'+journal.name+'"]/s:TaxInformation',namespaces=NS)
 assert len(infos)==1 and infos[0].find('s:TaxCode',NS).text=='86' and infos[0].find('s:TaxBase',NS).text=='1100.00'
 assert infos[0].find('s:CreditTaxAmount/s:Amount',NS).text=='110.00'
 # Native period lock also covers metadata on the ordinary expense row.
 frappe.db.savepoint('native_basis_metadata_lock');frappe.set_user('Administrator')
 frappe.get_doc({'doctype':'Accounting Period','company':C,'period_name':'Synthetic source metadata lock','start_date':'2026-10-01','end_date':'2026-10-31','closed_documents':[{'document_type':'Journal Entry','closed':1}]}).insert();frappe.set_user(OWNER)
 closed=frappe.get_doc('Journal Entry',journal.name);closed.accounts[0].set(RATE,15)
 try:closed.save()
 except frappe.ValidationError as error:assert type(error).__name__=='ClosedAccountingPeriod',type(error).__name__
 else:raise AssertionError('Closed source basis metadata changed')
 frappe.db.rollback(save_point='native_basis_metadata_lock')
 from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
 frappe.db.savepoint('service_reverse')
 reverse=make_reverse_journal_entry(journal.name);reverse.posting_date=reverse.bill_date='2026-10-21';reverse.insert();reverse.submit()
 assert next(row.get(BASE) for row in reverse.accounts if row.get(BASE))==-1100
 assert next(row.get(DEDUCTION) for row in reverse.accounts if row.get(BASE))==60
 export('native EUR journal reversal');frappe.db.rollback(save_point='service_reverse')
 frappe.db.savepoint('legacy_service_share')
 output=next(row for row in journal.accounts if row.account==a['2704']);frappe.db.set_value('Journal Entry Account',output.name,DEDUCTION,0)
 reverse=make_reverse_journal_entry(journal.name);reverse.posting_date=reverse.bill_date='2026-10-21';reverse.insert();reverse.save();reverse.submit()
 assert next(row.get(DEDUCTION) for row in reverse.accounts if row.get(BASE))==0
 try:export('must reject unknown legacy share')
 except frappe.ValidationError as error:assert 'fradragsandel' in str(error)
 else:raise AssertionError('Unknown historical service deduction assumed')
 frappe.db.rollback(save_point='legacy_service_share')
 payment=frappe.get_doc({'doctype':'Payment Entry','payment_type':'Pay','company':C,'posting_date':'2026-10-21','party_type':'Supplier','party':eur_supplier.name,'paid_from':a['1920'],'paid_from_account_currency':'NOK','paid_to':payable,'paid_to_account_currency':'EUR','paid_amount':1050,'received_amount':100,'source_exchange_rate':1,'target_exchange_rate':10.5,'reference_no':'SYN-NATIVE-JOURNAL-PAY','reference_date':'2026-10-21','cost_center':c.cost_center,'references':[{'reference_doctype':'Journal Entry','reference_name':journal.name,'total_amount':100,'outstanding_amount':100,'allocated_amount':100,'exchange_rate':10}]})
 payment.set_missing_values();payment.set_amounts();payment.insert();payment.submit();export('native EUR journal payment and FX')
 for specification,base,side in [('Bad debt',200,'debit'),('Capital goods adjustment',200,'debit'),('Capital goods reversal',-200,'credit')]:
  other='credit' if side=='debit' else 'debit'
  d=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-22','accounts':[{'account':a['2710'],side+'_in_account_currency':50,CODE:'1',RATE:25,BASE:base,SPEC:specification},{'account':a['4300'],other+'_in_account_currency':50,'cost_center':c.cost_center}]}).insert();d.submit()
  root=export('recorded VAT specification '+specification)
  assert root.xpath('.//s:Line[s:SourceDocumentID="'+d.name+'"]/s:TaxInformation/s:TaxExemptionReason/text()',namespaces=NS)==[specification]
 # Native foreign assets preserve BOTH gross currency sides on valuation GL.
 from erpnext_norway.vat_currency import DATE as FX_DATE,EXCHANGE
 for rate in (25,12):
  for share in (100,60,0):
   p=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':eur_supplier.name,'credit_to':payable,'currency':'EUR','conversion_rate':10,'posting_date':'2026-10-23','bill_date':'2026-10-23','set_posting_time':1,'bill_no':'SYN-EUR-ASSET-'+str(rate)+'-'+str(share),'due_date':'2026-10-31','disable_rounded_total':1,'update_stock':1,'items':[{'item_code':'RUNTIME-SAFT-NATIVE-ASSET','qty':2,'rate':50,'expense_account':a['1250'],'cost_center':c.cost_center,'asset_location':loc.name,'asset_naming_series':'ACC-ASS-.YYYY.-','item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':f'Tjenestekjøp fra utlandet – MVA {rate} % – 100 % fradrag'}),DEDUCTION:share,FX_DATE:'2026-10-22',EXCHANGE:11}]}).insert();p.submit();export('foreign fixed asset '+str(rate)+'/'+str(share))
 # Actual freight uses stored Item Wise Tax Detail allocations across different
 # item accounts, native discount, and differing documented delivery rates.
 for foreign,discount in ((False,0),(False,50),(True,0)):
  title='Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag' if foreign else 'MVA 25 % – varelinjer'
  p=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':eur_supplier.name if foreign else supplier.name,'credit_to':payable if foreign else a['2400'],'currency':'EUR' if foreign else 'NOK','conversion_rate':10 if foreign else 1,'posting_date':'2026-10-24','bill_date':'2026-10-24','set_posting_time':1,'bill_no':'SYN-COMPLEX-FREIGHT-'+str(foreign)+'-'+str(discount),'due_date':'2026-10-31','disable_rounded_total':1,'update_stock':1,'discount_amount':discount,'apply_discount_on':'Grand Total','items':[{'item_code':'RUNTIME-SAFT-NATIVE-'+kind,'qty':2,'rate':50 if foreign else 500,'expense_account':a['1250'] if kind=='ASSET' else a['4500'],'cost_center':c.cost_center,'asset_location':loc.name if kind=='ASSET' else None,'asset_naming_series':'ACC-ASS-.YYYY.-','item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':title}),DEDUCTION:60,**({FX_DATE:'2026-10-23',EXCHANGE:fx} if foreign else {})} for kind,fx in [('ASSET',11),('SERVICE',13)]],'taxes':[{'charge_type':'Actual','account_head':a['6100'],'tax_amount':10 if foreign else 100,'description':'Synthetic native freight','category':'Total','add_deduct_tax':'Add','cost_center':c.cost_center}]})
  for number,direction in ([('2704','Deduct'),('2714','Add')] if foreign else [('2710','Add')]):p.append('taxes',{'charge_type':'On Previous Row Total','row_id':'1','account_head':a[number],'rate':25,'category':'Total','add_deduct_tax':direction,'description':'Synthetic native VAT','cost_center':c.cost_center})
  p.insert();p.submit();root=export('multi-account native freight '+str(foreign)+' discount'+str(discount))
  assert not root.xpath('.//s:Line[s:SourceDocumentID="'+p.name+'" and s:AccountID="6100"]/s:TaxInformation',namespaces=NS)
  infos=root.xpath('.//s:Line[s:SourceDocumentID="'+p.name+'"]/s:TaxInformation',namespaces=NS)
  assert {i.find('s:TaxBase',NS).text for i in infos}==({'1155.00','1365.00'} if foreign else ({'1133.00'} if discount else {'1155.00'}))
 # Field/data faults are rejected without changing any source amounts.
 frappe.db.savepoint('missing_service_share')
 bad=frappe.copy_doc(journal);next(row for row in bad.accounts if row.account==a['2704']).set(DEDUCTION,0)
 try:bad.insert();bad.submit()
 except frappe.ValidationError as error:assert 'documented deduction percent' in str(error)
 else:raise AssertionError('New primary service journal submitted without its documented share')
 frappe.db.rollback(save_point='missing_service_share')
 root=export('complete native asset/stock/source suite')
 data=saft.build(C,'2026-01-01','2026-12-31')
 file=save_file('synthetic-saft-native.xml',data,'Company',C,is_private=1)
 evidence={'sources':sources(),'file':file.name,'sha256':hashlib.sha256(data).hexdigest()}
 record=save_file('synthetic-saft-native-evidence.json',frappe.as_json(evidence).encode(),'Company',C,is_private=1)
 frappe.db.set_default('runtime_saft_native',record.name);frappe.db.commit()
 print('PASS native SAF-T fixed assets/depreciation/gain-zero-loss sales/credits, stock input/output/returns/payments, receipts/clearing/85 and native stock movements, primary EUR service journals and source specifications',flush=True)
finally:frappe.db.rollback();frappe.destroy()
