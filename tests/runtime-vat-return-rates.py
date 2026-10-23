"""Native credit calculation must use issued rates after later template changes."""
import hashlib
import os
from pathlib import Path

import frappe

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites')
frappe.connect();frappe.set_user('runtime-vat-owner@example.invalid')
frappe.conf.host_name='http://frontend:8080'
from erpnext_norway.vat_catalog import CODE, DEDUCTION
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from frappe.utils.file_manager import save_file

try:
    company='Runtime VAT Example';c=frappe.get_doc('Company',company)
    A={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':company},
        fields=['name','account_number']) if r.account_number}
    def draft(kind,title='MVA 25 % – varelinjer - RVE'):
        source=frappe.get_doc(kind,{'company':company,'docstatus':1,'is_return':0,
            'total_taxes_and_charges':250 if kind=='Sales Invoice' else 100})
        doc=frappe.copy_doc(source);doc.posting_date='2026-10-18';doc.due_date='2026-10-31'
        doc.set_posting_time=1;doc.tax_category=None;doc.taxes_and_charges=None
        doc.set('items',[]);doc.set('taxes',[])
        doc.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':2,'rate':500,
            'income_account':A['3020'],'expense_account':A['4500'],'cost_center':c.cost_center,
            'item_tax_template':title,DEDUCTION:60 if kind=='Purchase Invoice' else None})
        if kind=='Purchase Invoice':
            doc.bill_date='2026-10-18';doc.bill_no='SYNTHETIC-ISSUED-RATES'
        return doc
    def submit(doc):
        doc.insert()
        if doc.doctype=='Purchase Invoice':
            save_file('synthetic-issued-rates.pdf',frappe.get_print(doc.doctype,doc.name,as_pdf=True),
                doc.doctype,doc.name,is_private=1)
        doc.submit()
        return doc
    def fingerprint(doc):
        name=frappe.db.get_value('File',{'attached_to_doctype':doc.doctype,'attached_to_name':doc.name,
            'is_private':1},'name')
        path=Path(frappe.get_doc('File',name).get_full_path())
        return path,hashlib.sha256(path.read_bytes()).hexdigest()
    ordinary=submit(draft('Sales Invoice'))
    count=frappe.db.count('Item Tax Template',{'company':company})
    unchanged=make_sales_return(ordinary.name);unchanged.posting_date='2026-10-19'
    submit(unchanged)
    assert unchanged.total_taxes_and_charges==-250
    assert frappe.db.count('Item Tax Template',{'company':company})==count
    print('PASS unchanged native rates create no extra item tax template on credit')
    original=submit(draft('Sales Invoice'));original_path,original_hash=fingerprint(original)
    template=frappe.get_doc('Item Tax Template','MVA 25 % – varelinjer - RVE')
    for row in template.taxes:
        if row.tax_type==A['2700']:row.tax_rate=12
    template.save();frappe.clear_document_cache('Item Tax Template',template.name)
    chosen=[]
    for _ in range(2):
        credit=make_sales_return(original.name);credit.posting_date='2026-10-19'
        credit.items[0].qty=-1
        submit(credit)
        assert credit.total_taxes_and_charges==-125,credit.total_taxes_and_charges
        assert credit.items[0].get(CODE)=='3'
        chosen.append(credit.items[0].item_tax_template)
    assert chosen[0]==chosen[1] and chosen[0]!=template.name
    assert frappe.db.count('Item Tax Template',{'company':company})==count+1
    assert next(row.tax_rate for row in frappe.get_doc('Item Tax Template',template.name).taxes
        if row.tax_type==A['2700'])==12
    assert hashlib.sha256(original_path.read_bytes()).hexdigest()==original_hash
    print('PASS two partial native credits use issued 25 percent, reuse one native snapshot template, keep later 12 percent choice and original PDF')
    purchase=submit(draft('Purchase Invoice'));purchase_path,purchase_hash=fingerprint(purchase)
    partial=frappe.get_doc('Item Tax Template',purchase.items[0].item_tax_template)
    for row in partial.taxes:
        if row.tax_type==A['2710']:row.tax_rate=10
        if row.tax_type==A['4500']:row.tax_rate=15
    partial.save();frappe.clear_document_cache('Item Tax Template',partial.name)
    credit=make_return_doc('Purchase Invoice',purchase.name)
    credit.posting_date='2026-10-19';credit.bill_date='2026-10-19'
    credit.bill_no='SYNTHETIC-ISSUED-PURCHASE-CREDIT'
    submit(credit)
    ledger=frappe.get_all('GL Entry',filters={'company':company,'voucher_no':credit.name,'is_cancelled':0},
        fields=['account','debit','credit'])
    for code,expected in [('4500',-1100),('2710',-150),('2400',1250)]:
        actual=round(sum(r.debit-r.credit for r in ledger if r.account==A[code]),2)
        assert actual==expected,(code,actual,expected)
    assert credit.items[0].get(DEDUCTION)==60 and credit.items[0].get(CODE)=='1'
    assert next(row.tax_rate for row in frappe.get_doc('Item Tax Template',partial.name).taxes
        if row.tax_type==A['2710'])==10
    assert hashlib.sha256(purchase_path.read_bytes()).hexdigest()==purchase_hash
    print('PASS native purchase credit keeps issued 150 input VAT / 100 VAT cost after later template deduction change')
finally:
    frappe.db.rollback();frappe.clear_cache();frappe.destroy()
