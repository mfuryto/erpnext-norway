"""Native goods/fees/declaration/LCV, zero import, payment and exported recovery."""
import os,sys,json,hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE,RATE
from erpnext_norway.vat_journal import BASE
from erpnext_norway.vat_import import DATE,REFERENCE
from erpnext_norway.vat_quarterly import ORDINARY,RETURN_TYPE
from erpnext_norway.vat_settlement import make_settlement,make_payment
from erpnext_norway.vat_evidence import preserve_basis
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
from frappe.utils.file_manager import save_file
C='Runtime Import Flow';OWNER='runtime-vat-owner@example.invalid'
F={'company':C,'from_date':'2026-09-01','to_date':'2026-09-30','return_type':ORDINARY}
def ledger():
    return sorted((r.account,float(r.debit),float(r.credit),r.voucher_type,r.voucher_no) for r in frappe.get_all('GL Entry',filters={'company':C,'is_cancelled':0},fields=['account','debit','credit','voucher_type','voucher_no']))
def portal():
    rows=[r for r in collect(F) if r['portal']]
    return tuple(round(sum(r[key] for r in rows),2) for key in ('base_amount','output_vat','input_vat'))
def rejected(action,text=None,kind=None):
    frappe.db.savepoint('import_reject')
    try:action()
    except frappe.ValidationError as error:
        if text:assert text in str(error),str(error)
        if kind:assert type(error).__name__==kind,type(error).__name__
        frappe.db.rollback(save_point='import_reject')
    else:raise AssertionError('Invalid import accepted')
try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_import_flow'))
        assert ledger()==[tuple(r) for r in evidence['ledger']]
        assert portal()==(6300,1250,750)
        for entry in evidence['documents']:
            doc=frappe.get_doc(entry['doctype'],entry['name']);assert doc.docstatus==1
            assert doc.get('grand_total')==entry['total']
            if doc.doctype=='Purchase Invoice':assert doc.outstanding_amount==0
        receipt=frappe.get_doc('Purchase Receipt',evidence['receipt'])
        assert receipt.items[0].get(BASE)==1300 and str(receipt.items[0].get(DATE))=='2026-09-20'
        assert receipt.items[0].get(REFERENCE)=='SYNTHETIC-ZERO-DECLARATION'
        assert receipt.items[0].get(CODE)=='85' and receipt.grand_total==1000
        for entry in evidence['files']:
            assert hashlib.sha256(Path(frappe.get_doc('File',entry['name']).get_full_path()).read_bytes()).hexdigest()==entry['sha256']
        print('PASS restored native EUR goods/duty/declaration/LCV/payment GL, zero-import receipt metadata/Version,6300/1250/750 portal basis and private customs bytes')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'IMF','country':'Norway','default_currency':'NOK',
            'tax_id':'999999987','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',
            vat.STATUS:'Registered',vat.FROM:'2026-01-01'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        valuation=frappe.get_doc({'doctype':'Account','company':C,'account_number':'4998','account_name':'Synthetic import valuation',
            'parent_account':frappe.db.get_value('Account',{'company':C,'root_type':'Expense','is_group':1}),
            'account_type':'Expenses Included In Valuation'}).insert();a['4998']=valuation.name
        unbilled=frappe.get_doc({'doctype':'Account','company':C,'account_number':'2998','account_name':'Synthetic import unbilled',
            'parent_account':frappe.db.get_value('Account',{'company':C,'root_type':'Liability','is_group':1}),
            'account_type':'Stock Received But Not Billed'}).insert()
        c.default_inventory_account=a['1460'];c.stock_received_but_not_billed=unbilled.name;c.enable_perpetual_inventory=1
        c.exchange_gain_loss_account=a['8160'];c.default_bank_account=a['1920'];c.save()
        stock=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-IMPORT-STOCK','item_name':'Synthetic physical import stock',
            'item_group':'Products','stock_uom':'Nos','is_stock_item':1,'valuation_method':'FIFO',
            'item_defaults':[{'company':C,'expense_account':a['4300'],'default_warehouse':'Stores - IMF'}]}).insert()
        nonstock=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-IMPORT-NONSTOCK','item_name':'Synthetic non-stock physical import goods',
            'item_group':'Products','stock_uom':'Nos','is_stock_item':0}).insert()
        eur_account=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic import EUR payable',
            'parent_account':frappe.db.get_value('Account',a['2400'],'parent_account'),'account_type':'Payable','account_currency':'EUR'}).insert()
        group=frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0]
        eur_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic import EUR supplier','supplier_type':'Company',
            'supplier_group':group,'default_currency':'EUR','accounts':[{'company':C,'account':eur_account.name}]}).insert()
        nok_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic import NOK supplier','supplier_type':'Company',
            'supplier_group':group,'default_currency':'NOK'}).insert()
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        def template(title):return frappe.db.get_value('Item Tax Template',{'company':C,'title':title})
        def purchase(amount,item,expense,title,foreign=False):
            doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':eur_supplier.name if foreign else nok_supplier.name,
                'currency':'EUR' if foreign else 'NOK','conversion_rate':10 if foreign else 1,'posting_date':'2026-09-15',
                'bill_date':'2026-09-15','set_posting_time':1,'bill_no':'SYNTHETIC-IMPORT-'+item,'due_date':'2026-10-31',
                'disable_rounded_total':1,'update_stock':int(item==stock.name),
                'items':[{'item_code':item,'qty':1,'rate':amount,'warehouse':'Stores - IMF','expense_account':a[expense],
                    'cost_center':c.cost_center,'item_tax_template':template(title)}]}).insert();doc.submit();return doc
        goods=purchase(300,stock.name,'4300','Vareimport – leverandørfaktura, 25 % ved innførsel',True)
        fees=purchase(1700,'RUNTIME-VAT-SERVICE','4998','Uten MVA-behandling')
        def landed(amount,source=None):
            doc=frappe.get_doc({'doctype':'Landed Cost Voucher','company':C,'posting_date':'2026-09-20',
                'distribute_charges_based_on':'Amount','purchase_receipts':[{'receipt_document_type':'Purchase Invoice','receipt_document':goods.name}],
                'taxes':[{'expense_account':a['4998'],'description':'Synthetic documented import cost','amount':amount}],
                'vendor_invoices':[{'vendor_invoice':source,'amount':amount}] if source else []})
            doc.get_items_from_purchase_receipts();doc.insert();doc.submit();return doc
        duty=landed(1700,fees.name)
        declaration=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-20','bill_date':'2026-09-20',
            'bill_no':'SYNTHETIC-IMPORT-DECLARATION','voucher_type':'Journal Entry',
            'user_remark':'Synthetic declaration; goods '+goods.name+'; duty '+fees.name,
            'accounts':[{'account':a['2705'],'credit_in_account_currency':1250,CODE:'81',RATE:25,BASE:5000},
                {'account':a['2715'],'debit_in_account_currency':750,CODE:'81',RATE:25},
                {'account':a['4998'],'debit_in_account_currency':500,'cost_center':c.cost_center}]}).insert();declaration.submit()
        nondeductible=landed(500)
        rows=[r for r in ledger() if r[-1] in (goods.name,fees.name,declaration.name)]
        for number,wanted in [('1460',5200),('4998',0),('2705',-1250),('2715',750),('2400',-1700)]:
            assert round(sum(r[1]-r[2] for r in rows if r[0]==a[number]),2)==wanted,(number,rows)
        assert fees.reload().claimed_landed_cost_amount==1700
        assert portal()==(5000,1250,750)
        assert not any(r['voucher']==declaration.name for r in collect({**F,'from_date':'2026-10-01','to_date':'2026-10-31'}))
        print('PASS native EUR300/book3000 goods, separate customs value3300+duty1700,1250/750 VAT, native LCV500, inventory5200/valuation0 and expedition period September despite October posting')
        zero=frappe.get_doc({'doctype':'Purchase Receipt','company':C,'supplier':nok_supplier.name,'posting_date':'2026-09-25',
            'set_posting_time':1,'currency':'NOK','conversion_rate':1,'items':[{'item_code':nonstock.name,'qty':1,'rate':1000,
                'expense_account':a['4300'],'cost_center':c.cost_center,
                'item_tax_template':template('Vareimport – deklarasjon uten beregning av MVA'),
                BASE:1200,DATE:'2026-09-20',REFERENCE:'SYNTHETIC-ZERO-DECLARATION'}]}).insert();zero.submit()
        assert frappe.db.count('GL Entry',{'voucher_type':'Purchase Receipt','voucher_no':zero.name,'is_cancelled':0})==0
        invoice=make_purchase_invoice(zero.name);invoice.posting_date=invoice.bill_date='2026-09-26';invoice.set_posting_time=1;invoice.bill_no='SYNTHETIC-ZERO-IMPORT';invoice.due_date='2026-10-31'
        for row in invoice.items:row.expense_account=a['4300'];row.cost_center=c.cost_center
        invoice.insert();invoice.submit();assert invoice.grand_total==1000 and invoice.items[0].get(CODE)=='20'
        assert invoice.items[0].pr_detail==zero.items[0].name
        zero.reload();zero.items[0].set(BASE,1300);zero.save()
        assert zero.grand_total==1000 and portal()==(6300,1250,750)
        assert frappe.db.exists('Version',{'ref_doctype':'Purchase Receipt','docname':zero.name})
        frappe.db.savepoint('import_source_lock');frappe.set_user('Administrator')
        frappe.get_doc({'doctype':'Accounting Period','company':C,'period_name':'Synthetic customs source closure',
            'start_date':'2026-09-01','end_date':'2026-09-30','closed_documents':[{'document_type':'Purchase Receipt','closed':1}]}).insert()
        frappe.set_user(OWNER);closed=frappe.get_doc('Purchase Receipt',zero.name);closed.items[0].set(BASE,1400);closed.items[0].set(DATE,'2026-10-01')
        rejected(closed.save,kind='ClosedAccountingPeriod');frappe.db.rollback(save_point='import_source_lock')
        print('PASS native non-stock goods receipt1300 statistical zero-import basis, ordinary1000 supplier invoice excluded from portal, native Version correction and closed-source-period guard')
        declaration.reload();declaration.accounts[1].set(BASE,5000);declaration.save()
        assert portal()==(6300,1250,750)  # An input-row basis must not double output basis.
        frappe.db.savepoint('import_journal_lock');frappe.set_user('Administrator')
        frappe.get_doc({'doctype':'Accounting Period','company':C,'period_name':'Synthetic customs VAT closure',
            'start_date':'2026-09-01','end_date':'2026-09-30','closed_documents':[{'document_type':'Journal Entry','closed':1}]}).insert()
        frappe.set_user(OWNER);closed=frappe.get_doc('Journal Entry',declaration.name);closed.accounts[0].set(BASE,5001)
        rejected(closed.save,kind='ClosedAccountingPeriod');frappe.db.rollback(save_point='import_journal_lock')
        def missing_reference():
            draft=frappe.copy_doc(declaration);draft.bill_date=None;draft.bill_no=None;draft.insert();draft.submit()
        rejected(missing_reference,'Enter the customs expedition date')
        print('PASS copied input-row basis is not double counted; native journal metadata lock uses September expedition date instead of October posting; new declarations require their source reference/date')
        # Isolate the registration gate, then restore the approved Company and all source data.
        frappe.db.savepoint('unregistered_import');frappe.set_user('Administrator')
        unregistered=frappe.get_doc('Company',C);unregistered.set(vat.STATUS,'Not registered');unregistered.set(vat.FROM,None);unregistered.save()
        frappe.set_user(OWNER)
        rejected(lambda:frappe.copy_doc(declaration).insert(),'Import VAT before registration is paid')
        paid=purchase(1250,nonstock.name,'4300','Vareimport – kostnad uten MVA-behandling')
        paid_rows=[row for row in ledger() if row[-1]==paid.name]
        assert sum(row[1]-row[2] for row in paid_rows if row[0]==a['4300'])==1250
        assert not any(row[0] in (a['2705'],a['2715']) for row in paid_rows)
        assert paid.items[0].get(CODE)=='20'
        from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
        manual=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-05','voucher_type':'Journal Entry',
            'user_remark':'Synthetic documented low-rate reverse-charge adjustment',
            'accounts':[{'account':a['2709'],'credit_in_account_currency':360,CODE:'89',RATE:12,BASE:3000},
                {'account':a['4500'],'debit_in_account_currency':360,'cost_center':c.cost_center}]}).insert();manual.submit()
        opposite=make_reverse_journal_entry(manual.name);opposite.posting_date='2026-10-06';opposite.insert();opposite.submit()
        assert next(row.get(BASE) for row in opposite.accounts if row.get(CODE)=='89')==-3000
        assert next(row.get(BASE) for row in manual.reload().accounts if row.get(CODE)=='89')==3000
        frappe.db.rollback(save_point='unregistered_import');frappe.clear_document_cache('Company',C)
        assert portal()==(6300,1250,750)
        print('PASS before registration: actual1250 paid-import invoice stays in cost without input/output VAT, self-assessed import rejected, native12-percent code89 reversal keeps signed basis without input deduction')
        frappe.db.savepoint('import_read_roles');frappe.set_user('Administrator')
        accountant=frappe.get_doc('User',OWNER);accountant.remove_roles('Stock Manager','Accounts User')
        frappe.set_user(OWNER);assert not frappe.has_permission('Purchase Receipt','read')
        assert collect({**F,'from_date':'2026-01-01','to_date':'2026-01-31'})==[]
        try:collect(F)
        except frappe.PermissionError:pass
        else:raise AssertionError('Zero-import basis was silently omitted without source permission')
        frappe.set_user('Administrator');frappe.get_doc('User',OWNER).add_roles('Accounts User');frappe.set_user(OWNER)
        assert 'Stock Manager' not in frappe.get_roles() and portal()==(6300,1250,750)
        frappe.db.rollback(save_point='import_read_roles');frappe.clear_cache(user=OWNER);frappe.set_user(OWNER)
        print('PASS no unnecessary stock permission for periods without zero imports; ordinary Accounts User source read is sufficient, and an unread zero-import source cannot silently disappear')
        frappe.db.savepoint('other_vat_reversals')
        for code,rate,out_account,counter in [('3',25,'2700','3020'),('86',25,'2704','2714'),('88',12,'2709','2718')]:
            amount=250 if rate==25 else 120
            original=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-09-22','voucher_type':'Journal Entry',
                'user_remark':'Synthetic documented VAT basis adjustment',
                'accounts':[{'account':a[out_account],'credit_in_account_currency':amount,CODE:code,RATE:rate,BASE:1000,'cost_center':c.cost_center},
                    {'account':a[counter],'debit_in_account_currency':amount,'cost_center':c.cost_center,
                        **({CODE:code,RATE:rate} if counter.startswith('271') else {})}]}).insert();original.submit()
            reverse=make_reverse_journal_entry(original.name);reverse.posting_date='2026-10-22';reverse.insert();reverse.submit()
            assert next(row.get(BASE) for row in reverse.accounts if row.get(BASE))==-1000
            pair=[row for row in collect({**F,'to_date':'2026-10-31'}) if row['voucher'] in (original.name,reverse.name)]
            assert tuple(round(sum(row[key] for row in pair),2) for key in ('base_amount','output_vat','input_vat'))==(0,0,0)
        frappe.db.rollback(save_point='other_vat_reversals')
        print('PASS the existing native journal reversal keeps signed bases for domestic25-percent and foreign-service25/12-percent adjustments, with exact invoice-ledger/report cancellation')


        for doc,bank_amount in ((goods,3150),(fees,1700),(invoice,1000)):
            payment=get_payment_entry('Purchase Invoice',doc.name,bank_account=a['1920'],bank_amount=bank_amount)
            payment.posting_date='2026-10-25';payment.reference_date='2026-10-25';payment.reference_no='SYNTHETIC-IMPORT-PAYMENT'
            if doc.currency=='EUR':payment.target_exchange_rate=10.5;payment.received_amount=300;payment.set_amounts()
            payment.insert();payment.submit();assert doc.reload().outstanding_amount==0
        settlement=frappe.get_doc('Journal Entry',make_settlement(**F)['name']);settlement.submit()
        payment=make_payment(settlement.name);payment.posting_date='2026-10-25';payment.cheque_date='2026-10-25';payment.cheque_no='SYNTHETIC-IMPORT-VAT';payment.insert();payment.submit()
        assert portal()==(6300,1250,750)
        for number in ('2705','2715','2740'):
            assert round(sum(r[1]-r[2] for r in ledger() if r[0]==a[number]),2)==0
        evidence={'documents':[{'doctype':doc.doctype,'name':doc.name,'total':doc.get('grand_total')}
            for doc in (goods,fees,declaration,duty,nondeductible,zero,invoice,settlement)],'receipt':zero.name,'files':[]}
        for doc,content,name in ((declaration,{'synthetic':True,'statistical_value':3300,'duty':1700,'base':5000,'output':1250,'input':750,'source_invoice':goods.name},'synthetic-customs.json'),
                (zero,{'synthetic':True,'base':1200,'reference':'SYNTHETIC-ZERO-DECLARATION'},'synthetic-zero-customs-original.json'),
                (zero,{'synthetic':True,'corrected_base':1300,'reference':'SYNTHETIC-ZERO-DECLARATION'},'synthetic-zero-customs-correction.json')):
            file=save_file(name,json.dumps({'company':C,**content}).encode(),doc.doctype,doc.name,is_private=1)
            evidence['files'].append({'name':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
        basis=frappe.get_doc('File',preserve_basis(**F)['name']);evidence['files'].append({'name':basis.name,'sha256':hashlib.sha256(Path(basis.get_full_path()).read_bytes()).hexdigest()})
        evidence['ledger']=ledger();frappe.db.set_default('runtime_import_flow',json.dumps(evidence));frappe.db.commit()
        print('PASS native supplier FX payment,500 VAT settlement/payment,6300/1250/750 unchanged portal basis and private declaration/correction evidence')
finally:frappe.destroy()
