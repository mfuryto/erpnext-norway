"""Export existing mixed asset/service receipts and quarterly capitalization sources."""
import os,sys,json,hashlib
from decimal import Decimal
from pathlib import Path
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import saft,saft_builder as xml
from frappe.utils.file_manager import save_file
C='Runtime Asset Freight';OWNER='runtime-vat-owner@example.invalid';NS={'s':xml.NS}
try:
 if sys.argv[1]=='seed':
  c=frappe.get_doc('Company',C);c.phone_no='90000000';c.save()
  groups={'1250':('balanseverdiForAnleggsmiddel','1205'),'1920':('balanseverdiForOmloepsmiddel','1920'),'2400':('kortsiktigGjeld','2400'),'2997':('kortsiktigGjeld','2990'),'2998':('kortsiktigGjeld','2990'),'4500':('varekostnad','4500'),'6100':('annenDriftskostnad','6100'),'4998':('varekostnad','4005')}
  for name in set(frappe.get_all('GL Entry',filters={'company':C},pluck='account')):
   a=frappe.get_doc('Account',name)
   if a.get(saft.MAPPING):continue
   category,code=('kortsiktigGjeld','2740') if a.account_number.startswith('27') else groups[a.account_number]
   a.append(saft.MAPPING,{'year':2026,'category':category,'code':code});a.save()
 frappe.set_user(OWNER)
 gl=json.loads(frappe.as_json(frappe.get_all('GL Entry',filters={'company':C},fields=['name','account','debit','credit','posting_date','voucher_type','voucher_no','is_cancelled','account_currency','transaction_currency','debit_in_account_currency','credit_in_account_currency','debit_in_transaction_currency','credit_in_transaction_currency'],order_by='name')))
 data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);root=etree.fromstring(data)
 assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r['name'] for r in gl}
 for side in ('debit','credit'):
  assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in gl),Decimal())
 assert {'1','87'} <= set(root.xpath('.//s:TaxInformation/s:TaxCode/text()',namespaces=NS))
 for r in gl:
  for side in ('debit','credit'):
   values=root.xpath('.//s:Line[s:RecordID="'+r['name']+'"]/s:'+side.title()+'Amount/s:Amount/text()',namespaces=NS)
   assert sum((Decimal(v) for v in values),Decimal())==xml._money(r[side])
 if sys.argv[1]=='seed':
  f=save_file('synthetic-shared-asset-saft.xml',data,'Company',C,is_private=1)
  e=save_file('synthetic-shared-asset-saft.json',frappe.as_json({'gl':gl,'file':f.name,'sha256':hashlib.sha256(data).hexdigest()}).encode(),'Company',C,is_private=1)
  frappe.db.set_default('runtime_saft_shared_assets',e.name);frappe.db.commit()
 else:
  e=json.loads(frappe.get_doc('File',frappe.db.get_default('runtime_saft_shared_assets')).get_content());assert gl==e['gl']
  f=frappe.get_doc('File',e['file']);assert f.is_private and hashlib.sha256(Path(f.get_full_path()).read_bytes()).hexdigest()==e['sha256']
 print('PASS shared native asset SAF-T',sys.argv[1],len(gl),'exact GL sides, mixed asset/service receipt and quarterly capitalization/clearing')
finally:frappe.db.rollback();frappe.destroy()
