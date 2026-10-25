"""Native mixed service rates, dated FX/fees, supplier and VAT settlements."""
import os, sys, json, hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE,RATE,DEDUCTION
from erpnext_norway.vat_quarterly import SOURCE_TITLE,title,QUARTERLY,ORDINARY
from erpnext_norway.vat_currency import DATE,EXCHANGE
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from erpnext_norway.vat_settlement import make_settlement,make_payment
from erpnext_norway.vat_evidence import preserve_basis
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils.file_manager import save_file
C='Runtime Service Rates';OWNER='runtime-vat-owner@example.invalid'
Q1={'company':C,'from_date':'2026-01-01','to_date':'2026-03-31','return_type':QUARTERLY}
Q2={**Q1,'from_date':'2026-04-01','to_date':'2026-06-30'}
O={**Q1,'from_date':'2026-09-01','to_date':'2026-10-31','return_type':ORDINARY}
def totals(filters):
 rows=[r for r in collect(filters) if r['portal']]
 return tuple(round(sum(r[key] for r in rows),2) for key in ('base_amount','output_vat','input_vat'))
def ledger():return sorted((r.account,float(r.debit),float(r.credit),r.voucher_type,r.voucher_no) for r in frappe.get_all('GL Entry',filters={'company':C,'is_cancelled':0},fields=['account','debit','credit','voucher_type','voucher_no']))
try:
 if sys.argv[1]=='verify':
  e=json.loads(frappe.db.get_default('runtime_service_rates_evidence'))
  assert totals(Q1)==(2300,406,0) and totals(Q2)==(3089,772.25,0) and totals(O)==(605,72.6,43.56)
  assert ledger()==[tuple(r) for r in e['ledger']]
  for entry in e['sources']:
   doc=frappe.get_doc('Purchase Invoice',entry['name']);assert doc.docstatus==1 and doc.grand_total==entry['total']
   assert [(r.get(CODE),r.get(RATE)) for r in doc.items]==[tuple(r) for r in entry['classifications']]
  for entry in e['files']:assert hashlib.sha256(Path(frappe.get_doc('File',entry['name']).get_full_path()).read_bytes()).hexdigest()==entry['sha256']
  print('PASS restored mixed25/12 quarter406/772.25, EURfee/deliveryFX ordinary72.60/43.56, native payments/settlements and private original bytes')
 else:
  c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'R12','country':'Norway','default_currency':'NOK','tax_id':'999999987','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
  a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
  payable=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic service EUR payable','parent_account':frappe.db.get_value('Account',a['2400'],'parent_account'),'account_type':'Payable','account_currency':'EUR'}).insert()
  c.default_bank_account=a['1920'];c.exchange_gain_loss_account=a['8160'];c.save()
  supplier=frappe.get_all('Supplier',pluck='name')[0]
  eur=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic mixed service EUR supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'EUR','accounts':[{'company':C,'account':payable.name}]}).insert()
  frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
  frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
  sources=[]
  def invoice(amount,rate,date,foreign=False,fee=0,discount=0,percent=60):
   registered=date>='2026-08-15'
   template=frappe.db.get_value('Item Tax Template',{'company':C,'title':f'Tjenestekjøp fra utlandet – MVA {rate} % – 100 % fradrag' if registered else title(SOURCE_TITLE,rate)})
   doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':eur.name if foreign else supplier,'credit_to':payable.name if foreign else a['2400'],
    'posting_date':date,'set_posting_time':1,'bill_date':date,'bill_no':'SYNTHETIC-SERVICE-RATES','due_date':'2026-10-31','currency':'EUR' if foreign else 'NOK','conversion_rate':10 if foreign else 1,'disable_rounded_total':1,
    'apply_discount_on':'Grand Total','additional_discount_percentage':discount,
    'items':[{'item_code':'RUNTIME-VAT-SERVICE','description':'Synthetic foreign service; low rate only for qualifying intermediary service','qty':2,'rate':amount/2,'expense_account':a['4500'],'cost_center':c.cost_center,'item_tax_template':template,DEDUCTION:percent if registered else 0,DATE:date if foreign else None,EXCHANGE:11 if foreign else None}]})
   if fee:doc.append('taxes',{'charge_type':'Actual','account_head':a['6100'],'tax_amount':fee,'description':'Synthetic service fee','category':'Total','add_deduct_tax':'Add','cost_center':c.cost_center})
   if registered and foreign and fee:
    for number,direction in [('2709','Deduct'),('2718','Add')]:doc.append('taxes',{'charge_type':'On Previous Row Total','row_id':'1','account_head':a[number],'rate':rate,'description':'Synthetic native VAT basis','category':'Total','add_deduct_tax':direction,'cost_center':c.cost_center})
   doc.insert();doc.submit();sources.append(doc);return doc
  invoice(1000,25,'2026-01-10');invoice(1000,12,'2026-01-11');assert totals(Q1)==(0,0,0)
  crossing=invoice(100,12,'2026-01-12');assert totals(Q1)==(2100,382,0)
  credit=make_return_doc('Purchase Invoice',crossing.name);credit.posting_date=credit.bill_date='2026-01-13';credit.set_posting_time=1;credit.bill_no='SYNTHETIC-THRESHOLD-CREDIT';credit.insert();credit.submit();sources.append(credit);assert totals(Q1)==(0,0,0)
  invoice(300,12,'2026-01-14');assert totals(Q1)==(2300,406,0)
  invoice(2000,25,'2026-04-10');fxquarter=invoice(100,25,'2026-04-20',True,10,10);assert fxquarter.grand_total==99 and totals(Q2)==(3089,772.25,0)
  print('PASS native mixed25/12 shared strict2000 threshold, credit reversal, both rates; foreign fee/GrandTotaldiscount preserves99EUR and1089NOK basis')
  frappe.set_user('Administrator');c.reload();c.set(vat.STATUS,'Registered');c.set(vat.FROM,'2026-08-15');c.save()
  frappe.db.savepoint('low_rate_migration')
  full25=frappe.db.get_value('Item Tax Template',{'company':C,'title':'Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag'})
  zero12=frappe.db.get_value('Item Tax Template',{'company':C,'title':'Tjenestekjøp fra utlandet – MVA 12 % – 0 % fradrag'})
  frappe.delete_doc('Item Tax Template',full25);frappe.delete_doc('Item Tax Template',zero12)
  from erpnext_norway.patches.v0_4_16_service_rates import execute as upgrade_rates
  upgrade_rates();upgrade_rates()
  assert not frappe.db.exists('Item Tax Template',full25)
  assert frappe.db.exists('Item Tax Template',{'company':C,'title':'Tjenestekjøp fra utlandet – MVA 12 % – 0 % fradrag'})
  frappe.db.rollback(save_point='low_rate_migration');frappe.clear_cache()
  print('PASS native low-rate migration is idempotent and preserves deliberately removed25% choice')
  frappe.set_user(OWNER)
  # NOK and mixed document rate choices use the same native adapter; these
  # cases roll back so the persisted ordinary period has a clear FX result.
  for percent,input_,code in ((100,120,'88'),(60,72,'88'),(0,0,'89')):
   frappe.db.savepoint('native_low_rate_nok')
   nok=invoice(1000,12,'2026-09-15',percent=percent);assert nok.grand_total==1000 and nok.items[0].get(CODE)==code
   rows=[r for r in collect(O) if r['voucher']==nok.name];assert (rows[0]['output_vat'],rows[0]['input_vat'])==(120,input_)
   half=make_return_doc('Purchase Invoice',nok.name);half.posting_date=half.bill_date='2026-10-15';half.set_posting_time=1;half.bill_no='SYNTHETIC-LOW-RATE-PARTIAL-CREDIT';half.items[0].qty=-1;half.insert();half.submit()
   rows=[r for r in collect(O) if r['voucher']==half.name];assert half.grand_total==-500 and (rows[0]['output_vat'],rows[0]['input_vat'])==(-60,-input_/2)
   frappe.db.rollback(save_point='native_low_rate_nok');sources.pop()
  foreign=invoice(100,12,'2026-09-20',True,10);assert foreign.grand_total==110 and totals(O)==(1210,145.2,87.12)
  frappe.db.savepoint('native_zero_before_fee')
  copy=frappe.copy_doc(foreign);copy.bill_no='SYNTHETIC-ZERO-ROW-BEFORE-FEE';original_rows=[r.as_dict() for r in copy.taxes];copy.set('taxes',[])
  copy.append('taxes',{'charge_type':'On Net Total','account_head':a['2710'],'rate':25,'description':'Synthetic zero native VAT row','category':'Total','add_deduct_tax':'Add','cost_center':c.cost_center})
  for row in original_rows:
   for key in ('name','parent','parenttype','parentfield','idx'):row.pop(key,None)
   if row.get('charge_type')=='On Norwegian VAT Base':row['row_id']='2'
   copy.append('taxes',row)
  copy.insert();copy.submit();assert copy.grand_total==110
  rows=[r for r in collect(O) if r['voucher']==copy.name];assert (rows[0]['base_amount'],rows[0]['output_vat'],rows[0]['input_vat'])==(1210,145.2,87.12)
  bad=frappe.copy_doc(copy);bad.bill_no='SYNTHETIC-NONZERO-VAT-IN-BASE'
  next(r for r in bad.taxes if r.account_head==a['2718']).row_id='3'
  try:bad.insert()
  except frappe.ValidationError as error:assert 'precede VAT' in str(error),str(error)
  else:raise AssertionError('VAT was included in its own service basis')
  frappe.db.rollback(save_point='native_zero_before_fee')
  payment=get_payment_entry('Purchase Invoice',foreign.name,bank_account=a['1920'],bank_amount=1155)
  payment.posting_date=payment.reference_date='2026-09-25';payment.reference_no='SYNTHETIC-SERVICE-EUR-PAYMENT';payment.target_exchange_rate=10.5;payment.paid_amount=1155;payment.set_amounts();payment.insert();payment.submit();assert foreign.reload().outstanding_amount==0
  credit=make_return_doc('Purchase Invoice',foreign.name);credit.posting_date=credit.bill_date='2026-10-20';credit.set_posting_time=1;credit.bill_no='SYNTHETIC-SERVICE-EUR-CREDIT';credit.items[0].qty=-1;credit.taxes[0].tax_amount=-5;credit.update_outstanding_for_self=1;credit.insert();credit.submit();sources.append(credit);assert credit.grand_total==-55
  refund=get_payment_entry('Purchase Invoice',credit.name,bank_account=a['1920'],bank_amount=577.5)
  refund.posting_date=refund.reference_date='2026-10-21';refund.reference_no='SYNTHETIC-SERVICE-EUR-REFUND';refund.source_exchange_rate=10.5;refund.received_amount=577.5;refund.set_amounts();refund.insert();refund.submit();assert credit.reload().outstanding_amount==0
  assert totals(O)==(605,72.6,43.56)
  for filters in (Q1,Q2,O):
   settlement=frappe.get_doc('Journal Entry',make_settlement(**filters)['name']);settlement.submit()
   payment=make_payment(settlement.name);payment.posting_date=payment.cheque_date='2026-10-25';payment.cheque_no='SYNTHETIC-SERVICE-VAT-PAYMENT';payment.insert();payment.submit()
  assert totals(Q1)==(2300,406,0) and totals(Q2)==(3089,772.25,0) and totals(O)==(605,72.6,43.56)
  e={'sources':[],'files':[],'ledger':ledger()}
  for doc in sources:
   doc.reload();e['sources'].append({'name':doc.name,'total':doc.grand_total,'classifications':[(r.get(CODE),r.get(RATE)) for r in doc.items]})
  for doc in (fxquarter,foreign,credit):
   f=save_file('synthetic-service-rates.pdf',frappe.get_print(doc.doctype,doc.name,as_pdf=True),doc.doctype,doc.name,is_private=1);e['files'].append({'name':f.name,'sha256':hashlib.sha256(Path(f.get_full_path()).read_bytes()).hexdigest()})
  for filters in (Q1,Q2,O):
   f=frappe.get_doc('File',preserve_basis(**filters)['name']);e['files'].append({'name':f.name,'sha256':hashlib.sha256(Path(f.get_full_path()).read_bytes()).hexdigest()})
  frappe.db.set_default('runtime_service_rates_evidence',json.dumps(e));frappe.db.commit()
  print('PASS normal12% NOK/FX fees, source-rate partialcredit, EUR supplier payment/refund, quarterly/ordinary VAT settlement/payment and private originals/bases')
finally:frappe.destroy()
