"""Native primary supplier journal and payment for documented VAT date cases."""
import os,frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('runtime-vat-owner@example.invalid');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway.vat_catalog import CODE,RATE
from erpnext_norway.vat_journal import BASE
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
C='Runtime Asset Freight'
try:
 c=frappe.get_doc('Company',C);a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number']) if r.account_number}
 frappe.set_user('Administrator');c.exchange_gain_loss_account=a['8160'];c.save();frappe.set_user('runtime-vat-owner@example.invalid')
 supplier=frappe.db.get_value('Supplier',{'supplier_name':'Synthetic capitalized currency supplier'})
 payable=frappe.db.get_value('Party Account',{'parent':supplier,'company':C},'account')
 j=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-20','bill_date':'2026-10-20','bill_no':'SYNTHETIC-REMOTE-SERVICE-SOURCE','multi_currency':1,
  'user_remark':'Synthetic remote service: delivery2026-10-10 before registration, invoice2026-10-20 in registration term; documented eligible business use60%, bookEUR10, customsFX11; ordinary native primary journal, no purchase invoice or later VAT correction.',
  'accounts':[{'account':a['4500'],'debit_in_account_currency':1110,'cost_center':c.cost_center},
   {'account':a['2714'],'debit_in_account_currency':165,'cost_center':c.cost_center,CODE:'86',RATE:25},
   {'account':a['2704'],'credit_in_account_currency':275,'cost_center':c.cost_center,CODE:'86',RATE:25,BASE:1100},
   {'account':payable,'party_type':'Supplier','party':supplier,'account_currency':'EUR','exchange_rate':10,'credit_in_account_currency':100}]}).insert();j.submit()
 rows=[r for r in collect({'company':C,'from_date':'2026-10-15','to_date':'2026-10-31'}) if r['voucher']==j.name]
 assert sum(r['base_amount'] for r in rows)==1100 and sum(r['output_vat'] for r in rows)==275 and sum(r['input_vat'] for r in rows)==165,rows
 print('PASS native primary supplier EUR journal: source delivery before registration within registration term, invoice/posted20Oct, 1100 base/output275/input165, expense1110/vendor100EUR, no parallel PI or followup tax correction',flush=True)
 p=frappe.get_doc({'doctype':'Payment Entry','payment_type':'Pay','company':C,'posting_date':'2026-10-21','party_type':'Supplier','party':supplier,
  'paid_from':a['1920'],'paid_from_account_currency':'NOK','paid_to':payable,'paid_to_account_currency':'EUR','paid_amount':1050,'received_amount':100,'source_exchange_rate':1,'target_exchange_rate':10.5,
  'reference_no':'SYNTHETIC-JOURNAL-PAYMENT','reference_date':'2026-10-21','cost_center':c.cost_center,
  'references':[{'reference_doctype':'Journal Entry','reference_name':j.name,'total_amount':100,'outstanding_amount':100,'allocated_amount':100,'exchange_rate':10}]})
 p.set_missing_values();p.set_amounts();p.insert();p.submit()
 rows=frappe.get_all('GL Entry',filters={'company':C,'against_voucher_type':'Journal Entry','against_voucher':j.name,'is_cancelled':0},fields=['account','debit','credit','debit_in_account_currency','credit_in_account_currency'])
 own=frappe.get_all('GL Entry',filters={'company':C,'voucher_type':'Journal Entry','voucher_no':j.name,'account':payable,'is_cancelled':0},fields=['debit','credit','debit_in_account_currency','credit_in_account_currency'])
 all_party=frappe.get_all('GL Entry',filters={'company':C,'account':payable,'is_cancelled':0},fields=['debit','credit','debit_in_account_currency','credit_in_account_currency'])
 assert round(sum(r.debit-r.credit for r in all_party),2)==0
 assert round(sum(r.debit_in_account_currency-r.credit_in_account_currency for r in all_party),2)==0
 assert round(sum(r.debit_in_account_currency-r.credit_in_account_currency for r in rows if r.account==payable)+sum(r.debit_in_account_currency-r.credit_in_account_currency for r in own),2)==0
 print('PASS native supplier Payment Entry references ordinary Journal Entry and clears EUR100, no new payment/ledger implementation',flush=True)
finally:frappe.db.rollback();frappe.clear_cache();frappe.destroy()
