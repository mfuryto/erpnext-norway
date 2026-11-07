"""Native import supplier costs retain codes20/21/22 without a customs basis."""
import os,sys,json,hashlib
from pathlib import Path
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator')
from erpnext_norway import vat,saft,saft_builder as xml
from erpnext_norway.vat_quarterly import ITEM,JOURNAL
from erpnext_norway.vat_catalog import PURCHASE_CODE
from erpnext_norway.vat_catalog import CODE
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils.file_manager import save_file
C='Runtime SAF-T Import Costs';OWNER='runtime-saft-import-costs@example.invalid';NS={'s':xml.NS}
def export():
    data=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(data);return data,etree.fromstring(data)
def check(root):
    gl=frappe.get_all('GL Entry',filters={'company':C},fields=['name','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in gl}
    for side in ('debit','credit'):
        assert Decimal(root.xpath('string(.//s:Total'+side.title()+')',namespaces=NS))==sum((xml._money(r[side]) for r in gl),Decimal())
    infos=root.xpath('.//s:Line/s:TaxInformation',namespaces=NS);assert len(infos)==12
    from collections import Counter
    assert Counter(i.xpath('string(s:TaxCode)',namespaces=NS) for i in infos)=={'20':4,'21':4,'22':4}
    for info in infos:
        assert not info.xpath('s:TaxBase',namespaces=NS)
        assert info.xpath('s:TaxPercentage/text()',namespaces=NS)==['0.00']
        assert info.xpath('s:DebitTaxAmount/s:Amount/text()|s:CreditTaxAmount/s:Amount/text()',namespaces=NS)==['0.00']
    assert root.xpath('.//s:Line/*[s:CurrencyCode="EUR"]/s:CurrencyAmount',namespaces=NS)
    assert not root.xpath('.//s:TaxInformation/s:DebitNOKTaxAmount|.//s:TaxInformation/s:CreditNOKTaxAmount',namespaces=NS)
    fx=frappe.db.get_value('Account',{'company':C,'account_number':'8160'},'name')
    assert sum(Decimal(str(r.debit))-Decimal(str(r.credit)) for r in frappe.get_all('GL Entry',filters={'company':C,'account':fx},fields=['debit','credit']))==Decimal('240')
    assert not frappe.db.count('Journal Entry',{'company':C,JOURNAL:1,'docstatus':1})
try:
    if sys.argv[1]=='verify':
        e=json.loads(frappe.db.get_default('runtime_saft_import_costs'));frappe.set_user(OWNER);_,root=export();check(root)
        for name,total,code,currency in e['invoices']:
            doc=frappe.get_doc('Purchase Invoice',name);assert doc.grand_total==total and doc.outstanding_amount==0 and doc.currency==currency
            assert all(not r.get(ITEM) and r.get(CODE)==code for r in doc.items)
        f=frappe.get_doc('File',e['file']);assert f.is_private
        assert hashlib.sha256(Path(f.get_full_path()).read_bytes()).hexdigest()==e['sha256']
        print('PASS restored import cost codes20/21/22 NOK and EUR, native credits/payment/refund/FX loss240, no customs basis, exact GL IDs/gross/currency and private XML')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'SIC','country':'Norway','default_currency':'NOK','tax_id':'999999987','phone_no':'90000000','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        for number,category,group in [('1920','balanseverdiForOmloepsmiddel','1920'),('2400','kortsiktigGjeld','2400'),('2704','kortsiktigGjeld','2740'),('4500','varekostnad','4500'),('8160','finanskostnad','8160')]:
            acc=frappe.get_doc('Account',a[number]);acc.append(saft.MAPPING,{'year':2026,'category':category,'code':group});acc.save()
        c.default_bank_account=a['1920'];c.exchange_gain_loss_account=a['8160'];c.save()
        payable=frappe.get_doc({'doctype':'Account','account_name':'Synthetic import EUR payable','parent_account':frappe.db.get_value('Account',a['2400'],'parent_account'),'company':C,'account_type':'Payable','account_currency':'EUR'}).insert()
        payable.append(saft.MAPPING,{'year':2026,'category':'kortsiktigGjeld','code':'2400'});payable.save()
        if not frappe.db.exists('Currency Exchange',{'date':frappe.utils.nowdate(),'from_currency':'EUR','to_currency':'NOK'}):
            frappe.get_doc({'doctype':'Currency Exchange','date':frappe.utils.nowdate(),'from_currency':'EUR','to_currency':'NOK','exchange_rate':10,'for_buying':1,'for_selling':1}).insert()
        supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic import cost supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'NOK'}).insert()
        eur_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic EUR import cost supplier','supplier_type':'Company','supplier_group':supplier.supplier_group,'default_currency':'EUR','accounts':[{'company':C,'account':payable.name}]}).insert()
        item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-SAFT-IMPORT-COST','item_name':'Synthetic import cost','item_group':'Services','stock_uom':'Nos','is_stock_item':0}).insert()
        frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic import cost owner','send_welcome_email':0,'roles':[{'role':'Accounts Manager'},{'role':'Accounts User'},{'role':'Purchase Manager'}]}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert();frappe.set_user(OWNER)
        def purchase(amount,reference,template,currency,quantity=1):
            doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':eur_supplier.name if currency=='EUR' else supplier.name,'currency':currency,'conversion_rate':10 if currency=='EUR' else 1,'credit_to':payable.name if currency=='EUR' else a['2400'],'posting_date':'2026-05-20','bill_date':'2026-05-20','set_posting_time':1,'bill_no':reference,'due_date':'2026-06-30','disable_rounded_total':1,'items':[{'item_code':item.name,'qty':quantity,'rate':amount/quantity,'expense_account':a['4500'],'cost_center':c.cost_center,'item_tax_template':template}]}).insert();doc.submit();return doc
        records=[]
        for currency in ('NOK','EUR'):
            amount=120 if currency=='EUR' else 1200
            credit_amount=40 if currency=='EUR' else 400
            for code in ('20','21','22'):
                template=frappe.db.get_value('Item Tax Template',{'company':C,PURCHASE_CODE:code})
                assert template
                first=purchase(amount,'SYNTHETIC-IMPORT-'+currency+code,template,currency,quantity=3)
                pay=get_payment_entry('Purchase Invoice',first.name,bank_account=a['1920'],bank_amount=1320 if currency=='EUR' else 1200);pay.posting_date=pay.reference_date='2026-05-25';pay.reference_no='SYNTHETIC-IMPORT-PAYMENT-'+currency+code
                if currency=='EUR':pay.target_exchange_rate=11;pay.received_amount=first.outstanding_amount;pay.set_amounts()
                pay.insert();pay.submit()
                credit=make_return_doc('Purchase Invoice',first.name);credit.posting_date=credit.bill_date='2026-06-01';credit.set_posting_time=1;credit.bill_no='SYNTHETIC-IMPORT-CREDIT-'+currency+code;credit.items[0].qty=-1;credit.update_outstanding_for_self=1;credit.insert();credit.submit()
                refund=get_payment_entry('Purchase Invoice',credit.name,bank_account=a['1920'],bank_amount=440 if currency=='EUR' else 400);refund.posting_date=refund.reference_date='2026-06-02';refund.reference_no='SYNTHETIC-IMPORT-REFUND-'+currency+code
                if currency=='EUR':refund.source_exchange_rate=11;refund.paid_amount=abs(credit.outstanding_amount);refund.set_amounts()
                refund.insert();refund.submit()
                assert credit.grand_total==-credit_amount and first.reload().outstanding_amount==credit.reload().outstanding_amount==0
                for doc in (first,credit):
                    assert all(not r.get(ITEM) and r.get(CODE)==code for r in doc.items)
                    records.append((doc.name,doc.grand_total,code,currency))
        data,root=export();check(root)
        f=save_file('synthetic-saft-import-costs.xml',data,'Company',C,is_private=1)
        e={'file':f.name,'sha256':hashlib.sha256(data).hexdigest(),'invoices':records};frappe.db.set_default('runtime_saft_import_costs',json.dumps(e));frappe.db.commit()
        print('PASS native import cost codes20/21/22 NOK and EUR: purchases/credits/payment/refund, native FX loss240, no customs basis, exact GL IDs/gross/currency and XSD-valid XML')
finally:frappe.destroy()
