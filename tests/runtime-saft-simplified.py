"""Native 2027 sources, existing master data, default/history mapping and restore."""
import os,sys,json,hashlib
from pathlib import Path
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import saft,saft_builder as xml,vat
from erpnext_norway.vat_catalog import CODE,RATE
from erpnext_norway.vat_journal import BASE
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Simplified';OWNER='runtime-saft-simplified@example.invalid';NS={'s':xml.NS}

def ledger():
 return json.loads(frappe.as_json(frappe.get_all('GL Entry',filters={'company':C},fields=['name','account','debit','credit','posting_date','voucher_no'],order_by='name')))

def export():
 content=saft.build(C,'2027-01-01','2027-12-31');xml.validate_saf_t(content);root=etree.fromstring(content)
 rows=ledger();assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r['name'] for r in rows}
 for row in rows:
  for side in ('debit','credit'):
   assert sum((Decimal(v) for v in root.xpath('.//s:Line[s:RecordID="'+row['name']+'"]/s:'+side.title()+'Amount/s:Amount/text()',namespaces=NS)),Decimal())==xml._money(row[side])
 assert root.xpath('.//s:Header/s:Company/s:BankAccount/s:IBANNumber/text()',namespaces=NS)==['NO9386011117947']
 assert root.xpath('.//s:Supplier/s:BankAccount/s:BankAccountNumber/text()',namespaces=NS)==['12345678901']
 assert root.xpath('.//s:Header/s:Company/s:Contact/s:Email/text()',namespaces=NS)==['synthetic-contact@example.invalid']
 assert not root.xpath('.//s:Header/s:Company/s:Contact/s:Telephone',namespaces=NS)
 return content,root

def rejected(action,text,kind=frappe.ValidationError):
 frappe.db.savepoint('simplified_negative')
 try:action()
 except kind as error:assert text in str(error),str(error)
 else:raise AssertionError('Expected rejection: '+text)
 finally:frappe.db.rollback(save_point='simplified_negative');frappe.clear_cache(user=OWNER);frappe.set_user(OWNER)

try:
 if sys.argv[1]=='verify':
  e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_saft_simplified')).get_content())
  frappe.set_user(OWNER);export();assert ledger()==e['gl']
  file=frappe.get_doc('File',e['file']);assert file.is_private
  assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()==e['sha256']
  print('PASS restored native2027 GL, bank/contact master data and standard/history mapping')
 else:
  if not frappe.db.exists('Fiscal Year',{'year_start_date':'2027-01-01','year_end_date':'2027-12-31'}):
   frappe.get_doc({'doctype':'Fiscal Year','year':'2027','year_start_date':'2027-01-01','year_end_date':'2027-12-31'}).insert()
  frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic simplified owner','send_welcome_email':0,'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'}]}).insert()
  c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SSF','country':'Norway','default_currency':'NOK','tax_id':'999999986','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
  a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
  supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic simplified supplier','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'supplier_type':'Company'}).insert()
  bank=frappe.get_doc({'doctype':'Bank','bank_name':'Synthetic simplified bank','swift_number':'DNBANOKK'}).insert()
  company_bank=frappe.get_doc({'doctype':'Bank Account','account_name':'Synthetic company bank','bank':bank.name,'is_company_account':1,'company':C,'account':a['1920'],'iban':'NO9386011117947','bank_account_no':'86011117947'}).insert()
  party_bank=frappe.get_doc({'doctype':'Bank Account','account_name':'Synthetic supplier bank','bank':bank.name,'company':C,'party_type':'Supplier','party':supplier.name,'bank_account_no':'12345678901'}).insert()
  contact=frappe.get_doc({'doctype':'Contact','first_name':'Synthetic','last_name':'Person','email_ids':[{'email_id':'synthetic-contact@example.invalid','is_primary':1}],'links':[{'link_doctype':'Company','link_name':C}]}).insert()
  frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert();frappe.set_user(OWNER)
  journal=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2027-02-10','accounts':[
   {'account':a['4500'],'debit_in_account_currency':500,'cost_center':c.cost_center,CODE:'1',RATE:25},
   {'account':a['6551'],'debit_in_account_currency':300,'cost_center':c.cost_center,CODE:'1',RATE:25},
   {'account':a['2710'],'debit_in_account_currency':200,CODE:'1',RATE:25,BASE:800},
   {'account':a['2400'],'party_type':'Supplier','party':supplier.name,'credit_in_account_currency':1000}]}).insert();journal.submit()
  before=ledger();content,root=export();assert ledger()==before
  infos=root.xpath('.//s:Line[s:AccountID="4500" or s:AccountID="6551"]/s:TaxInformation',namespaces=NS)
  assert len(infos)==2 and not any(i.find('s:TaxBase',NS) is not None for i in infos)
  assert all(i.xpath('*[local-name()="DebitTaxAmount" or local-name()="CreditTaxAmount"]/s:Amount/text()',namespaces=NS)==['0.00'] for i in infos)
  assert not frappe.db.count('Norwegian SAF-T Mapping',{'parent':['in',list(a.values())]})
  # Explicit effective-year choices override defaults and never change older years.
  account=frappe.get_doc('Account',a['4500']);account.append(saft.MAPPING,{'year':2026,'category':'varekostnad','code':'4500'});account.append(saft.MAPPING,{'year':2028,'category':'varekostnad','code':'4005'});account.save()
  for year,expected in ((2026,'4500'),(2027,'4500'),(2028,'4005')):
   _,mapping=saft.account_catalog(C,year,{a['4500']},saft.groups(year));assert mapping[a['4500']].grouping_code==expected
  def invalid_choice():
   doc=frappe.get_doc('Account',a['4500']);doc.append(saft.MAPPING,{'year':2027,'category':'invalid','code':'invalid'});doc.save();export()
  rejected(invalid_choice,'kontokobling')
  def hidden_bank():
   frappe.set_user('Administrator');frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Bank Account','for_value':party_bank.name,'apply_to_all_doctypes':1}).insert();frappe.set_user(OWNER);export()
  rejected(hidden_bank,'bankkontoene',frappe.PermissionError)
  content,root=export()
  # Native cancellation retains both original and reversing GL without allocation.
  journal.cancel();export()
  # Native periodic inventory uses the invoice's recorded expense account.
  frappe.set_user('Administrator')
  frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-SIMPLIFIED-PERIODIC','item_name':'Synthetic periodic stock','item_group':'Products','stock_uom':'Nos','is_stock_item':1}).insert()
  frappe.set_user(OWNER)
  template=frappe.db.get_value('Item Tax Template',{'company':C,'title':'MVA 25 % – varelinjer'})
  purchase=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,'posting_date':'2027-02-12','bill_date':'2027-02-12','set_posting_time':1,'bill_no':'SYN-PERIODIC-2027','currency':'NOK','conversion_rate':1,'due_date':'2027-03-12','disable_rounded_total':1,'update_stock':1,'items':[{'item_code':'RUNTIME-SIMPLIFIED-PERIODIC','qty':2,'rate':100,'warehouse':'Stores - SSF','expense_account':a['4500'],'cost_center':c.cost_center,'item_tax_template':template}]}).insert();purchase.submit()
  _,periodic=export()
  assert periodic.xpath('.//s:Line[s:SourceDocumentID="'+purchase.name+'" and s:AccountID="4500"]/s:TaxInformation[s:TaxCode="1"]',namespaces=NS)
  # Retain all current native sources in proof, not the earlier snapshot.
  content,root=export();file=save_file('synthetic-saft-simplified-final.xml',content,'Company',C,is_private=1)
  e={'gl':ledger(),'file':file.name,'sha256':hashlib.sha256(content).hexdigest()}
  record=save_file('synthetic-saft-simplified-evidence.json',frappe.as_json(e).encode(),'Company',C,is_private=1);frappe.db.set_default('runtime_saft_simplified',record.name);frappe.db.commit()
  print('PASS native2027 multi-basis VAT/cancellation, exact GL, no-phone bank/contact, read-only defaults, historical choices, invalid mapping and restricted banks')
finally:frappe.destroy()
