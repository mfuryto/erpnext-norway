"""Native quarterly Asset cost, receipt/return, FX and exported evidence."""
import os, frappe
os.chdir('/home/frappe/frappe-bench/sites'); frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('runtime-vat-owner@example.invalid');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway.vat_quarterly import SOURCE_TITLE
from erpnext_norway.vat_valuation import SOURCE
from erpnext.controllers.sales_and_purchase_return import make_return_doc
C='Runtime Asset Freight'
import sys,json
if sys.argv[1]=='verify':
 try:
  from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
  from erpnext_norway.vat_quarterly import QUARTERLY,ITEM
  e=json.loads(frappe.db.get_default('runtime_quarterly_asset_evidence'))
  source=frappe.get_doc('Purchase Invoice',e['source']);expense=frappe.get_doc('Purchase Invoice',e['expense'])
  assert source.docstatus==expense.docstatus==1 and source.grand_total==1000 and expense.grand_total==1100
  assert source.items[0].get(ITEM)==1 and expense.items[0].get(ITEM)==1
  records=frappe.get_list('Asset',filters={'purchase_invoice':source.name},fields=['net_purchase_amount'])
  assert len(records)==2 and sum(r.net_purchase_amount for r in records)==1250
  assert frappe.db.get_value('Landed Cost Voucher',e['lcv'],'docstatus')==1
  rows=collect({'company':C,'from_date':'2026-07-01','to_date':'2026-09-30','return_type':QUARTERLY})
  assert sum(r['output_vat'] for r in rows)==525 and sum(r['input_vat'] for r in rows)==0
  print('PASS restored pre-registration Asset1250, quarterly output525, native source/LCV links; full GL/original hashes checked by shared Asset evidence')
 finally:frappe.destroy()
 raise SystemExit(0)
try:
 c=frappe.get_doc('Company',C);a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
 supplier=frappe.get_all('Supplier',filters={'default_currency':['in',['','NOK']]},pluck='name')[0]
 def invoice(amount,asset=False):
  d=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier,'posting_date':'2026-09-15','set_posting_time':1,'bill_date':'2026-09-15','bill_no':'SYNTHETIC-QUARTERLY-ASSET','due_date':'2026-10-31','currency':'NOK','conversion_rate':1,'update_stock':int(asset),'disable_rounded_total':1,
   'items':[{'item_code':'SYNTHETIC-VAT-ASSET-AVF' if asset else 'RUNTIME-VAT-SERVICE','qty':2,'rate':amount/2,'expense_account':a['1250'] if asset else a['4500'],'cost_center':c.cost_center,'asset_location':frappe.db.get_value('Location',{'location_name':'Synthetic VAT location asset freight'}) if asset else None,'asset_naming_series':'ACC-ASS-.YYYY.-' if asset else None,'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':SOURCE_TITLE})}]}).insert();d.submit();return d
 def assets(d):return frappe.get_list('Asset',filters={'purchase_invoice':d.name},fields=['name','net_purchase_amount'])
 def cost(d,expected):
  actual=sum(r.net_purchase_amount for r in assets(d));assert actual==expected,(actual,expected)
 frappe.db.savepoint('quarter_asset_case')
 def reset():
  frappe.db.rollback(save_point='quarter_asset_case');frappe.clear_cache();frappe.db.savepoint('quarter_asset_case')
 first=invoice(1000,True);cost(first,1000)
 other=invoice(1100);cost(first,1250)
 print('PASS below/crossing2000: native JE525, Asset1000->1250 with existing LCV',flush=True)
 credit=make_return_doc('Purchase Invoice',other.name);credit.posting_date=credit.bill_date='2026-09-16';credit.bill_no='SYNTHETIC-QUARTERLY-EXPENSE-CREDIT';credit.items[0].rate=100;credit.insert();credit.submit();cost(first,1000)
 credit.cancel();cost(first,1250)
 print('PASS expensecredit lowers threshold, native LCV Asset1250->1000, cancellation restores1250',flush=True)
 other.cancel();cost(first,1000)
 print('PASS source cancellation restores below-threshold Asset1000',flush=True)
 other=invoice(1100);cost(first,1250)
 frappe.delete_doc('Asset',assets(first)[0].name)
 credit=make_return_doc('Purchase Invoice',first.name);credit.posting_date=credit.bill_date='2026-09-16';credit.bill_no='SYNTHETIC-QUARTERLY-ASSET-CREDIT';credit.items[0].qty=credit.items[0].received_qty=-1;credit.insert();credit.submit()
 cost(first,500)
 rows=frappe.get_all('GL Entry',filters={'company':C,'posting_date':['between',['2026-09-01','2026-09-30']],'is_cancelled':0},fields=['account','debit','credit'])
 totals={n:round(sum(r.debit-r.credit for r in rows if r.account==a[n]),2) for n in ('1250','4500','4998','2704','2400')}
 assert totals=={'1250':500,'4500':1100,'4998':0,'2704':0,'2400':-1600},totals
 print('PASS partialAssetcredit lowers belowthreshold: remainingAsset500, assetGL500/expense1100/output0/clearing0/vendor1600',flush=True)
 reset()
 first=invoice(1000,True);other=invoice(1100);cost(first,1250)
 frappe.delete_doc('Asset',assets(first)[0].name)
 late=make_return_doc('Purchase Invoice',first.name);late.posting_date=late.bill_date='2026-10-19';late.bill_no='SYNTHETIC-QUARTERLY-LATE-ASSET-CREDIT';late.items[0].qty=late.items[0].received_qty=-1;late.insert();late.submit();cost(first,625)
 print('PASS native Asset partialcredit in registered later period preserves original taxed treatment and remainingAsset625',flush=True)
 correction=make_return_doc('Purchase Invoice',other.name);correction.posting_date=correction.bill_date='2026-09-16';correction.bill_no='SYNTHETIC-QUARTERLY-SOURCE-CREDIT';correction.items[0].rate=100;correction.insert();correction.submit();cost(first,500)
 rows=frappe.get_all('GL Entry',filters={'company':C,'voucher_no':['in',[first.name,late.name]],'is_cancelled':0},fields=['account','debit','credit'])
 assert round(sum(r.debit-r.credit for r in rows if r.account==a['1250']),2)==500
 correction.cancel();cost(first,625)
 print('PASS original-quarter threshold correction also reverses/reinstates later native Asset return LCV and VAT',flush=True)
 reset()
 first=invoice(1000,True);other=invoice(1100)
 for record in assets(first):frappe.delete_doc('Asset',record.name)
 returned=make_return_doc('Purchase Invoice',first.name);returned.posting_date=returned.bill_date='2026-09-16';returned.bill_no='SYNTHETIC-QUARTERLY-FULL-ASSET-RETURN';returned.insert();returned.submit()
 rows=frappe.get_all('GL Entry',filters={'company':C,'posting_date':['between',['2026-09-01','2026-09-30']],'is_cancelled':0},fields=['account','debit','credit'])
 totals={n:round(sum(r.debit-r.credit for r in rows if r.account==a[n]),2) for n in ('1250','4500','4998','2704','2400')}
 assert totals=={'1250':0,'4500':1100,'4998':0,'2704':0,'2400':-1100},totals
 print('PASS full native Asset return belowthreshold leaves no Assets, zero asset/VAT/clearing and correct expense/vendor',flush=True)

 reset()
 from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
 from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
 order=frappe.get_doc({'doctype':'Purchase Order','company':C,'supplier':supplier,'transaction_date':'2026-09-15','schedule_date':'2026-09-15','currency':'NOK','conversion_rate':1,'items':[{'item_code':'SYNTHETIC-VAT-ASSET-AVF','qty':2,'rate':500,'schedule_date':'2026-09-15','expense_account':a['1250'],'cost_center':c.cost_center,'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':SOURCE_TITLE})}]}).insert();order.submit()
 receipt=make_purchase_receipt(order.name);receipt.posting_date='2026-09-15';receipt.set_posting_time=1;receipt.items[0].asset_location=frappe.db.get_value('Location',{'location_name':'Synthetic VAT location asset freight'});receipt.insert();receipt.submit()
 first=make_purchase_invoice(receipt.name);first.posting_date=first.bill_date='2026-09-15';first.set_posting_time=1;first.bill_no='SYNTHETIC-QUARTERLY-RECEIPT';first.disable_rounded_total=1;first.insert();first.submit()
 def records():return frappe.get_list('Asset',filters={'purchase_receipt':receipt.name},fields=['name','net_purchase_amount'])
 assert sum(r.net_purchase_amount for r in records())==1000
 other=invoice(1100)
 assert sum(r.net_purchase_amount for r in records())==1250
 print('PASS native quarterly Asset PO/PR/PI preserves ordinary receipt, threshold cost1250 and native LCV',flush=True)
 frappe.delete_doc('Asset',records()[0].name)
 returned=make_return_doc('Purchase Receipt',receipt.name);returned.posting_date='2026-09-16';returned.set_posting_time=1;returned.items[0].qty=returned.items[0].received_qty=-1;returned.insert();returned.submit()
 credit=make_return_doc('Purchase Invoice',first.name);credit.posting_date=credit.bill_date='2026-09-16';credit.bill_no='SYNTHETIC-QUARTERLY-RECEIPT-CREDIT';credit.items[0].qty=credit.items[0].received_qty=-1;credit.insert();credit.submit()
 assert sum(r.net_purchase_amount for r in records())==500
 rows=frappe.get_all('GL Entry',filters={'company':C,'posting_date':['between',['2026-09-01','2026-09-30']],'is_cancelled':0},fields=['account','debit','credit'])
 totals={n:round(sum(r.debit-r.credit for r in rows if r.account==a[n]),2) for n in ('1250','4500','4998','2704','2400','2997')}
 assert totals=={'1250':500,'4500':1100,'4998':0,'2704':0,'2400':-1600,'2997':0},totals
 print('PASS native quarterly Asset receipt halfreturn+PIcredit drops threshold: Asset500/expense1100/output0/clearing0/unbilled0/vendor1600',flush=True)

 reset()
 from erpnext_norway.vat_quarterly import title
 frappe.set_user('Administrator')
 payable=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic quarterly Asset EUR payable','account_type':'Payable','account_currency':'EUR','parent_account':frappe.db.get_value('Account',a['2400'],'parent_account')}).insert()
 eur=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic quarterly Asset EUR supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'EUR','accounts':[{'company':C,'account':payable.name}]}).insert()
 frappe.set_user('runtime-vat-owner@example.invalid')
 for rate,vat in ((25,275),(12,132)):
  frappe.db.savepoint('fx_quarter_asset')
  first=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':eur.name,'credit_to':payable.name,'posting_date':'2026-09-15','set_posting_time':1,'bill_date':'2026-09-15','bill_no':'SYNTHETIC-QUARTERLY-ASSET-EUR','due_date':'2026-10-31','currency':'EUR','conversion_rate':10,'update_stock':1,'disable_rounded_total':1,
   'items':[{'item_code':'SYNTHETIC-VAT-ASSET-AVF','qty':2,'rate':50,'expense_account':a['1250'],'cost_center':c.cost_center,'asset_location':frappe.db.get_value('Location',{'location_name':'Synthetic VAT location asset freight'}),'asset_naming_series':'ACC-ASS-.YYYY.-','item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':title(SOURCE_TITLE,rate)}),'custom_norway_vat_delivery_date':'2026-09-14','custom_norway_vat_exchange_rate':11}]}).insert();first.submit();cost(first,1000)
  other=invoice(1000);cost(first,1000+vat)
  assert first.grand_total==100 and frappe.db.get_value('Purchase Invoice',first.name,'base_grand_total')==1000
  frappe.delete_doc('Asset',assets(first)[0].name)
  credit=make_return_doc('Purchase Invoice',first.name);credit.posting_date=credit.bill_date='2026-09-16';credit.bill_no='SYNTHETIC-QUARTERLY-ASSET-EUR-CREDIT';credit.items[0].qty=credit.items[0].received_qty=-1;credit.items[0].custom_norway_vat_exchange_rate=99;credit.insert();credit.submit();cost(first,500)
  assert credit.grand_total==-50 and credit.items[0].custom_norway_vat_exchange_rate==11
  print('PASS native pre-registration EUR Asset '+str(rate)+'%:1100NOK basis/100EUR supplier, threshold Asset'+str(1000+vat)+', halfcredit belowthreshold leaves500 and originalFX11',flush=True)
  frappe.db.rollback(save_point='fx_quarter_asset');frappe.clear_cache()
 frappe.db.savepoint('manual_quarter_asset')
 frappe.set_user('Administrator');item=frappe.get_doc('Item','SYNTHETIC-VAT-ASSET-AVF');item.auto_create_assets=0;item.save();frappe.set_user('runtime-vat-owner@example.invalid')
 first=invoice(2500,True);first.reload();assert not assets(first)
 record=frappe.get_doc({'doctype':'Asset','company':C,'item_code':item.name,'asset_name':'Synthetic manual quarterly asset','asset_category':item.asset_category,'location':frappe.db.get_value('Location',{'location_name':'Synthetic VAT location asset freight'}),'naming_series':'ACC-ASS-.YYYY.-','asset_quantity':1,'calculate_depreciation':0,'purchase_date':first.posting_date,'purchase_invoice':first.name,'purchase_invoice_item':first.items[0].name,'purchase_amount':first.items[0].valuation_rate,'net_purchase_amount':first.items[0].valuation_rate}).insert()
 assert record.net_purchase_amount==1562.5 and frappe.db.get_value('Item',item.name,'auto_create_assets')==0
 print('PASS explicit manual Asset creation retained after quarterly VAT: native purchase value1562.50 per unit',flush=True)
 frappe.db.rollback(save_point='manual_quarter_asset');frappe.clear_cache()
 frappe.db.savepoint('submitted_asset_case')
 first=invoice(1000,True);record=frappe.get_doc('Asset',assets(first)[0].name);record.available_for_use_date=first.posting_date;record.save();record.submit()
 frappe.db.savepoint('submitted_asset_quarter')
 try:invoice(1100)
 except frappe.ValidationError as error:
  assert 'submitted Assets' in str(error),str(error)
  frappe.db.rollback(save_point='submitted_asset_quarter')
 else:raise AssertionError('Native submitted-Asset validation bypassed')
 cost(first,1000)
 print('PASS native submitted-Asset validation blocks changed quarterly capitalization; failed invoice/VAT transaction rolled back',flush=True)

 frappe.db.rollback(save_point='submitted_asset_case');frappe.clear_cache()
 reset()

 import sys,json,hashlib
 from pathlib import Path
 from frappe.utils.file_manager import save_file
 from erpnext_norway.vat_evidence import preserve_basis
 from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
 from erpnext_norway.vat_quarterly import QUARTERLY,JOURNAL
 first=invoice(1000,True);other=invoice(1100);cost(first,1250)
 evidence=json.loads(frappe.db.get_default('runtime_asset_freight_evidence'))
 for doc in (first,other):
  file=save_file('synthetic-quarterly-asset-source.pdf',frappe.get_print(doc.doctype,doc.name,as_pdf=True),doc.doctype,doc.name,is_private=1)
  evidence['files'].append({'name':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
  evidence['documents'].append({'doctype':doc.doctype,'name':doc.name,'status':1,'total':doc.grand_total})
 lcv=frappe.db.get_value('Landed Cost Voucher',{SOURCE:first.name,'docstatus':1})
 journals=frappe.get_all('Journal Entry',filters={'company':C,JOURNAL:1,'docstatus':1},pluck='name')
 evidence['documents'] += [{'doctype':'Landed Cost Voucher','name':lcv,'status':1}] + [{'doctype':'Journal Entry','name':name,'status':1} for name in journals]
 evidence['assets'] += [{'name':r.name,'value':r.net_purchase_amount} for r in assets(first)]
 file=frappe.get_doc('File',preserve_basis(company=C,from_date='2026-07-01',to_date='2026-09-30',return_type=QUARTERLY)['name'])
 evidence['files'].append({'name':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
 evidence['ledger']=sorted((r.account,float(r.debit),float(r.credit),r.voucher_type,r.voucher_no) for r in frappe.get_all('GL Entry',filters={'company':C,'is_cancelled':0},fields=['account','debit','credit','voucher_type','voucher_no']))
 frappe.db.set_default('runtime_asset_freight_evidence',json.dumps(evidence))
 frappe.db.set_default('runtime_quarterly_asset_evidence',json.dumps({'source':first.name,'expense':other.name,'lcv':lcv}))
 frappe.db.commit()
 print('PASS quarterly Asset1250, output525, ordinary PI/JE/LCV links, native original PDF/basis and full ledger committed for exported restore',flush=True)
finally:frappe.db.rollback();frappe.clear_cache();frappe.destroy()
