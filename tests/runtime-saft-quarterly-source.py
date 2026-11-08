"""Reuse ordinary source invoice exports; never hide unqualified quarterly VAT."""
import os,sys,json,hashlib
from pathlib import Path
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import vat,saft,saft_builder as xml
from erpnext_norway.vat_quarterly import ITEM,JOURNAL,SOURCE_TITLE
from erpnext_norway.vat_catalog import CODE
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Quarterly Source';OWNER='runtime-saft-quarter-source@example.invalid';NS={'s':xml.NS}
def export():
    data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);return data,etree.fromstring(data)
def check(root):
    gl=frappe.get_all('GL Entry',filters={'company':C},fields=['name','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in gl}
    for side in ('debit','credit'):
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in gl),Decimal())
    infos=root.xpath('.//s:Line/s:TaxInformation',namespaces=NS);assert len(infos)==2
    for info in infos:
        assert info.xpath('s:TaxCode/text()',namespaces=NS)==['0']
        assert info.xpath('s:TaxBase/text()',namespaces=NS)==['0.00']
        assert info.xpath('s:DebitTaxAmount/s:Amount/text()|s:CreditTaxAmount/s:Amount/text()',namespaces=NS)==['0.00']
    assert not frappe.db.count('Journal Entry',{'company':C,JOURNAL:1,'docstatus':1})
try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.db.get_default('runtime_saft_quarter_source'));frappe.set_user(OWNER);_,root=export();check(root)
        for name,total in e['invoices']:
            doc=frappe.get_doc('Purchase Invoice',name);assert doc.grand_total==total and doc.outstanding_amount==0
            assert all(r.get(ITEM) and r.get(CODE)=='0' for r in doc.items)
        f=frappe.get_doc('File',e['file']);assert f.is_private
        assert hashlib.sha256(Path(f.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored ordinary NOK pre-registration service invoices/credit/payment/refund, source code0 and exact GL IDs/totals/private XML; quarterly sources retain exact supplier classification')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SQS','country':'Norway','default_currency':'NOK','tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number,category,group in [('1920','balanseverdiForOmloepsmiddel','1920'),('2400','kortsiktigGjeld','2400'),('2704','kortsiktigGjeld','2740'),('4500','varekostnad','4500')]:
            acc=frappe.get_doc('Account',a[number]);acc.append(saft.MAPPING,{'year':2026,'category':category,'code':group});acc.save()
        c.default_bank_account=a['1920'];c.save()
        supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic quarterly source supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'NOK'}).insert()
        item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-SAFT-QUARTER-SERVICE','item_name':'Synthetic service source','item_group':'Services','stock_uom':'Nos','is_stock_item':0}).insert()
        template=frappe.db.get_value('Item Tax Template',{'company':C,'title':SOURCE_TITLE})
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic quarterly source owner','send_welcome_email':0,'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'},{'role':'Purchase Manager'}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert();frappe.set_user(OWNER)
        def purchase(amount,reference,quantity=1):
            doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':supplier.name,'currency':'NOK','conversion_rate':1,'posting_date':'2026-05-20','bill_date':'2026-05-20','set_posting_time':1,'bill_no':reference,'due_date':'2026-06-30','disable_rounded_total':1,'items':[{'item_code':item.name,'qty':quantity,'rate':amount/quantity,'expense_account':a['4500'],'cost_center':c.cost_center,'item_tax_template':template}]}).insert();doc.submit();return doc
        first=purchase(1500,'SYNTHETIC-QUARTER-SOURCE',quantity=3)
        pay=get_payment_entry('Purchase Invoice',first.name,bank_account=a['1920'],bank_amount=1500);pay.posting_date=pay.reference_date='2026-05-25';pay.reference_no='SYNTHETIC-SOURCE-PAYMENT';pay.insert();pay.submit()
        credit=make_return_doc('Purchase Invoice',first.name);credit.posting_date=credit.bill_date='2026-06-01';credit.set_posting_time=1;credit.bill_no='SYNTHETIC-QUARTER-SOURCE-CREDIT';credit.items[0].qty=-1;credit.update_outstanding_for_self=1;credit.insert();credit.submit()
        refund=get_payment_entry('Purchase Invoice',credit.name,bank_account=a['1920'],bank_amount=500);refund.posting_date=refund.reference_date='2026-06-02';refund.reference_no='SYNTHETIC-SOURCE-REFUND';refund.insert();refund.submit()
        assert credit.grand_total==-500 and first.reload().outstanding_amount==credit.reload().outstanding_amount==0
        data,root=export();check(root)
        frappe.db.savepoint('quarterly_vat_still_blocked')
        purchase(1100,'SYNTHETIC-QUARTER-THRESHOLD')
        journals=frappe.get_all('Journal Entry',filters={'company':C,JOURNAL:1,'docstatus':1},pluck='name');assert journals
        _,threshold_root=export()
        infos=threshold_root.xpath('.//s:TaxInformation[s:TaxCode="87"]',namespaces=NS)
        assert len(infos)==3
        assert sorted(Decimal(i.xpath('string(s:TaxBase)',namespaces=NS)) for i in infos)==[Decimal(500),Decimal(1100),Decimal(1500)]
        assert all(i.xpath('s:DebitTaxAmount/s:Amount/text()|s:CreditTaxAmount/s:Amount/text()',namespaces=NS)==['0.00'] for i in infos)
        assert not threshold_root.xpath('.//s:Line[s:AccountID="2704"]/s:TaxInformation',namespaces=NS)
        frappe.db.rollback(save_point='quarterly_vat_still_blocked')
        f=save_file('synthetic-saft-quarterly-source.xml',data,'Company',C,is_private=1)
        e={'file':f.name,'sha256':hashlib.sha256(data).hexdigest(),'invoices':[(first.name,1500),(credit.name,-500)]};frappe.db.set_default('runtime_saft_quarter_source',json.dumps(e));frappe.db.commit()
        print('PASS native NOK source invoice1500/credit500/payment/refund reuse code0 export with exact GL; crossing threshold retains actual quarterly VAT GL and source bases without allocating VAT')
finally:frappe.destroy()
