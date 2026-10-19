"""Synthetic ordinary-owner VAT report/settlement/payment/refund/evidence cycle."""
import os, json, hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites'); frappe.connect()
frappe.set_user('Administrator'); frappe.local.lang='nb'; frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat, vat_catalog as catalog
from erpnext_norway.vat_journal import BASE, SETTLEMENT
from erpnext_norway.vat_settlement import make_settlement, make_payment
from erpnext_norway.vat_evidence import preserve_basis, preserve_uploaded, RETAIN
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect, execute
from frappe.utils.file_manager import save_file
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import reconcile_vouchers
C='Runtime VAT Matrix'; owner='runtime-vat-owner@example.invalid'

def equal(actual,expected): assert round(float(actual or 0),2)==expected,(actual,expected)
def rejected(action):
    frappe.db.savepoint('matrix_rejection')
    try: action()
    except frappe.ValidationError: frappe.db.rollback(save_point='matrix_rejection')
    else: raise AssertionError('Invalid operation accepted')
def journal(date,rows,remark):
    return frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':date,
        'voucher_type':'Journal Entry','user_remark':remark,
        'accounts':[{'account':A[code],'debit_in_account_currency':max(amount,0),
            'credit_in_account_currency':max(-amount,0),'cost_center':cc,**extra}
            for code,amount,extra in rows]}).insert()
def invoice(kind,date,items,**extra):
    return frappe.get_doc({'doctype':kind,'company':C,'posting_date':date,'set_posting_time':1,
        'due_date':'2026-06-30','currency':'NOK','conversion_rate':1,'disable_rounded_total':1,
        'cost_center':cc,**({'customer':customer} if kind=='Sales Invoice' else
        {'supplier':supplier,'bill_date':date,'bill_no':'SYNTHETIC-MATRIX-'+date}),
        'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,'cost_center':cc,
                  'income_account':A['3020'],'expense_account':A['4500'],**row} for row in items],**extra})
def purchase_original(doc):
    save_file('synthetic-matrix-supplier.pdf',frappe.get_print(doc.doctype,doc.name,as_pdf=True),
        doc.doctype,doc.name,is_private=1)
def reconcile(voucher,date,amount,deposit=False):
    transaction=frappe.get_doc({'doctype':'Bank Transaction','company':C,'date':date,
        'bank_account':bank_account.name,'currency':'NOK','deposit':amount if deposit else 0,
        'withdrawal':0 if deposit else amount,'transaction_id':'SYNTHETIC-'+voucher.name,
        'description':'Synthetic VAT matrix bank movement'}).insert()
    transaction.submit()
    reconcile_vouchers(transaction.name,json.dumps([{'payment_doctype':voucher.doctype,
        'payment_name':voucher.name,'amount':amount}]))
    transaction.reload(); equal(transaction.unallocated_amount,0)
def payment(invoice,date,amount,deposit=False):
    doc=get_payment_entry(invoice.doctype,invoice.name,bank_account=A['1920'])
    doc.posting_date=date; doc.reference_no='SYNTHETIC-'+date; doc.reference_date=date
    doc.insert();doc.submit();reconcile(doc,date,amount,deposit)
    return doc
try:
    company=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'MVC','country':'Norway',
        'default_currency':'NOK','tax_id':'999999998','enable_perpetual_inventory':0,
        'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Registered',
        vat.FROM:'2026-05-01'}).insert()
    assert company.get(vat.CONFIGURED)==1
    for rate in (25,15,12):
        assert frappe.db.exists('Item Tax Template',f'MVA {rate} % – varelinjer - MVC')
    # A subsequent ordinary Company save must preserve an explicitly removed rule.
    removed_rule=frappe.db.get_value('Tax Rule',{'company':C,'tax_type':'Sales',
        'tax_category':'Norge MVA 15 %'})
    assert removed_rule
    frappe.delete_doc('Tax Rule',removed_rule)
    company.save()
    assert not frappe.db.exists('Tax Rule',{'company':C,'tax_type':'Sales',
        'tax_category':'Norge MVA 15 %'})
    A={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},
        fields=['name','account_number']) if r.account_number};cc=company.cost_center
    customer=frappe.get_all('Customer',pluck='name')[0];supplier=frappe.get_all('Supplier',pluck='name')[0]
    item=frappe.get_doc('Item','RUNTIME-VAT-SERVICE')
    item.append('item_defaults',{'company':C,'income_account':A['3020'],'expense_account':A['4500']});item.save()
    bank=frappe.get_all('Bank',pluck='name')[0]
    bank_account=frappe.get_doc({'doctype':'Bank Account','account_name':'Runtime VAT matrix bank',
        'bank':bank,'company':C,'is_company_account':1,'account':A['1920'],
        'bank_account_no':'00000000000'}).insert()
    frappe.get_doc({'doctype':'User Permission','user':owner,'allow':'Company','for_value':C,
                   'apply_to_all_doctypes':1}).insert()
    frappe.set_user(owner)
    assert 'System Manager' not in frappe.get_roles()
    assert not vat.is_vat_account(A['1640']) and not vat.is_vat_account(A['2740'])
    funds=journal('2026-05-01',[('1920',10000,{}),('2050',-10000,{})],'Synthetic owner funding')
    funds.submit()
    old=invoice('Purchase Invoice','2026-04-20',[{'rate':400}],taxes=[{'account_head':A['4500'],
        'charge_type':'On Net Total','rate':25,'description':'Synthetic VAT included in cost',
        'category':'Total','add_deduct_tax':'Add','cost_center':cc}]).insert()
    purchase_original(old);old.submit();equal(old.grand_total,500)
    sale=invoice('Sales Invoice','2026-05-16',[{'item_tax_template':f'MVA {rate} % – varelinjer - MVC'}
        for rate in (25,15,12)]).insert();sale.submit();equal(sale.grand_total,3520)
    purchase=invoice('Purchase Invoice','2026-05-16',[
        {'item_tax_template':'MVA 25 % – varelinjer - MVC',catalog.DEDUCTION:60},
        {'item_tax_template':'MVA 25 % – varelinjer - MVC',catalog.DEDUCTION:0,'expense_account':A['6540']}]).insert()
    purchase_original(purchase);purchase.submit();equal(purchase.grand_total,2500)
    retro=journal('2026-05-17',[('2710',100,{catalog.CODE:'1',catalog.RATE:25}),('4500',-100,{})],
        f'Synthetic separately qualified retrospective deduction; source {old.name}')
    retro.submit()
    filters={'company':C,'from_date':'2026-05-01','to_date':'2026-06-30'}
    data=collect(filters);equal(sum(row['net_vat'] for row in data),270)
    columns,summary,*_=execute(filters);assert {row['vat_code'] for row in summary}>={'1','3','31','33','0'}
    settlement=frappe.get_doc('Journal Entry',make_settlement(**filters)['name'])
    settlement.submit()
    equal(sum(float(r.debit_in_account_currency or 0) for r in settlement.accounts),520)
    rejected(lambda:make_settlement(**filters))
    tax_payment=make_payment(settlement.name);tax_payment.posting_date='2026-07-12'
    tax_payment.cheque_no='SYNTHETIC-VAT-PAYMENT';tax_payment.cheque_date='2026-07-12'
    tax_payment.insert();tax_payment.submit();reconcile(tax_payment,'2026-07-12',270)
    payment(sale,'2026-07-09',3520,True);payment(purchase,'2026-07-10',2500);payment(old,'2026-07-11',500)
    doc=frappe.get_doc('File',preserve_basis(**filters)['name']);path=Path(doc.get_full_path())
    digest=hashlib.sha256(path.read_bytes()).hexdigest();assert doc.get(RETAIN)==1
    rejected(doc.delete)
    doc.reload();doc.is_private=0;rejected(doc.save)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    receipt=save_file('synthetic-vat-receipt.json',b'{"synthetic_receipt":true}',
        'Company',C,is_private=1)
    preserve_uploaded(receipt.name,C,filters['from_date'],filters['to_date'],'VAT receipt')
    receipt.reload();rejected(receipt.delete)
    refund_purchase=invoice('Purchase Invoice','2026-07-16',[{'rate':400,
        'item_tax_template':'MVA 25 % – varelinjer - MVC'}],due_date='2026-08-31').insert()
    purchase_original(refund_purchase);refund_purchase.submit()
    refund_filters={'company':C,'from_date':'2026-07-01','to_date':'2026-08-31'}
    equal(sum(row['net_vat'] for row in collect(refund_filters)),-100)
    refund=frappe.get_doc('Journal Entry',make_settlement(**refund_filters)['name']);refund.submit()
    assert any(r.account==A['1640'] for r in refund.accounts)
    tax_refund=make_payment(refund.name);tax_refund.posting_date='2026-09-10'
    tax_refund.cheque_no='SYNTHETIC-VAT-REFUND';tax_refund.cheque_date='2026-09-10'
    tax_refund.insert();tax_refund.submit();reconcile(tax_refund,'2026-09-10',100,True)
    payment(refund_purchase,'2026-09-05',500)
    equal(frappe.db.sql('SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE company=%s AND account=%s AND is_cancelled=0',(C,A['1920']))[0][0],9850)
    for code in ('1640','2700','2701','2703','2710','2740'):
        equal(frappe.db.sql('SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE company=%s AND account=%s AND is_cancelled=0',(C,A[code]))[0][0],0)
    # A late-entered supplier invoice belongs to the supplier document's period.
    # Its native posting date stays unchanged and the amended settlement is only
    # the difference from the settlement already submitted for that same period.
    late=invoice('Purchase Invoice','2026-07-18',[{'rate':400,
        'item_tax_template':'MVA 25 % – varelinjer - MVC'}],
        bill_date='2026-05-25',due_date='2026-08-31').insert()
    purchase_original(late);late.submit()
    equal(sum(row['net_vat'] for row in collect(filters)),170)
    equal(sum(row['net_vat'] for row in collect(refund_filters)),-100)
    timing=[row for row in collect(filters) if row['voucher']==late.name]
    assert len(timing)==1 and str(timing[0]['vat_date'])=='2026-05-25'
    assert str(timing[0]['posting_date'])=='2026-07-18'
    amendment=frappe.get_doc('Journal Entry',make_settlement(**filters)['name']);amendment.submit()
    equal(sum(float(r.debit_in_account_currency or 0) for r in amendment.accounts),100)
    assert any(r.account==A['1640'] for r in amendment.accounts)
    rejected(lambda:make_settlement(**filters))
    print('PASS ordinary owner: native mixed-rate VAT, retrospective journal, report, settlement 270, refund 100, supplier/customer payments, bank reconciliation and protected private VAT evidence')
    print('PASS supplier document period differs from native posting period; amended native settlement clears only the 100 difference')
finally:
    frappe.db.rollback();frappe.clear_cache();frappe.destroy()
