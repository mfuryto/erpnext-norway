"""Ordinary native purchase flow, company-wide quarter, credits and registration."""
import os,sys,json,hashlib
from pathlib import Path
import frappe
os.chdir('/home/frappe/frappe-bench/sites');frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE,DEDUCTION
from erpnext_norway.vat_quarterly import ITEM,JOURNAL,RETURN_TYPE,ORDINARY,QUARTERLY
from erpnext_norway.vat_journal import BASE
from erpnext_norway.vat_settlement import make_settlement,make_payment
from erpnext_norway.vat_evidence import preserve_basis
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils.file_manager import save_file
C='Runtime Quarterly Services';OWNER='runtime-vat-owner@example.invalid'
Q2={'company':C,'from_date':'2026-04-01','to_date':'2026-06-30','return_type':QUARTERLY}
Q3={'company':C,'from_date':'2026-07-01','to_date':'2026-09-30','return_type':QUARTERLY}
def totals(filters):
    rows=[row for row in collect(filters) if row['portal']]
    return tuple(round(sum(row[key] for row in rows),2) for key in ('base_amount','output_vat','input_vat'))
def ledger():
    rows=frappe.get_all('GL Entry',filters={'company':C,'is_cancelled':0},fields=['account','debit','credit','voucher_type','voucher_no'])
    return sorted((r.account,float(r.debit),float(r.credit),r.voucher_type,r.voucher_no) for r in rows)
def rejected(action,text=None):
    frappe.db.savepoint('quarter_reject')
    try:action()
    except frappe.ValidationError as error:
        if text:assert text in str(error),str(error)
        frappe.db.rollback(save_point='quarter_reject')
    else:raise AssertionError('Invalid quarterly treatment accepted')
try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_quarterly_evidence'))
        assert ledger()==[tuple(row) for row in evidence['ledger']]
        assert totals(Q2)==(2050.02,512.5,0)
        assert totals(Q3)==(2100,525,0)
        assert totals({**Q3,'return_type':ORDINARY})==(850.01,212.5,250)
        for entry in evidence['sources']:
            doc=frappe.get_doc('Purchase Invoice',entry['name']);assert doc.docstatus==1
            assert doc.grand_total==entry['total']
            assert [row.get(ITEM) for row in doc.items]==entry['quarterly']
            assert [(str(row.get('custom_norway_vat_delivery_date') or ''),row.get('custom_norway_vat_exchange_rate')) for row in doc.items]==[tuple(row) for row in entry['fx']]
            if not doc.is_return:assert doc.outstanding_amount==0
        for entry in evidence['files']:
            path=Path(frappe.get_doc('File',entry['name']).get_full_path())
            assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
        print('PASS restored quarterly sources, registered/quarterly split, native adjustment/payment GL and private original/basis bytes')
    else:
        c=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'QVS','country':'Norway','default_currency':'NOK','tax_id':'999999987','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        c.default_bank_account=a['1920'];c.exchange_gain_loss_account=a['8160'];c.save()
        eur_account=frappe.get_doc({'doctype':'Account','account_name':'Synthetic quarterly EUR payable','parent_account':frappe.db.get_value('Account',a['2400'],'parent_account'),'company':C,'account_type':'Payable','account_currency':'EUR'}).insert()
        eur_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic quarterly EUR supplier','supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'EUR','accounts':[{'company':C,'account':eur_account.name}]}).insert()
        if not frappe.db.exists('Currency Exchange',{'date':frappe.utils.nowdate(),'from_currency':'EUR','to_currency':'NOK'}):
            frappe.get_doc({'doctype':'Currency Exchange','date':frappe.utils.nowdate(),'from_currency':'EUR','to_currency':'NOK','exchange_rate':10.5,'for_buying':1,'for_selling':1}).insert()
        suppliers=[frappe.get_doc({'doctype':'Supplier','supplier_name':'Synthetic quarterly supplier '+suffix,'supplier_type':'Company','supplier_group':frappe.get_all('Supplier Group',filters={'is_group':0},pluck='name')[0],'default_currency':'NOK'}).insert().name for suffix in ('A','B')]
        customer=frappe.get_doc({'doctype':'Customer','customer_name':'Synthetic quarterly customer','customer_type':'Company','customer_group':frappe.get_all('Customer Group',filters={'is_group':0},pluck='name')[0],'territory':'All Territories','default_currency':'NOK'}).insert().name
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        template=frappe.db.get_value('Item Tax Template',{'company':C,'title':'Tjenestekjøp fra utlandet – kvartalsgrunnlag før MVA-registrering'})
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        sources=[]
        def purchase(amount,date='2026-05-16',quantity=1,selected=None):
            doc=frappe.get_doc({'doctype':'Purchase Invoice','company':C,'supplier':suppliers[len(sources)%2],'currency':'NOK','conversion_rate':1,'posting_date':date,'bill_date':date,'set_posting_time':1,'bill_no':'SYNTHETIC-QUARTER-'+str(len(sources)),'due_date':'2026-10-31','disable_rounded_total':1,'cost_center':c.cost_center,'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':quantity,'rate':amount/quantity,'expense_account':a['4500'],'cost_center':c.cost_center,'item_tax_template':selected or template}]}).insert();doc.submit();assert doc.grand_total==amount
            sources.append(doc);return doc
        first=purchase(1500,quantity=10)
        boundary=purchase(499.99)
        assert totals(Q2)==(0,0,0)
        purchase(.01);assert totals(Q2)==(0,0,0)
        purchase(.01);assert totals(Q2)==(2000.01,500,0)
        count=frappe.db.count('Journal Entry',{'company':C,JOURNAL:1,'docstatus':1})
        purchase(.01);assert totals(Q2)==(2000.02,500,0)
        assert frappe.db.count('Journal Entry',{'company':C,JOURNAL:1,'docstatus':1})==count
        assert first.reload().grand_total==1500
        print('PASS native company-wide multiple-supplier threshold1999.99/2000/2000.01, unchanged payables and native zero-cent rounding without a zero journal')
        def credit(date):
            doc=make_return_doc('Purchase Invoice',first.name);doc.posting_date=date;doc.bill_date=date;doc.set_posting_time=1;doc.bill_no='SYNTHETIC-QUARTER-CREDIT-'+date;doc.update_outstanding_for_self=0;doc.items[0].qty=-1
            doc.insert();doc.submit();assert doc.items[0].get(ITEM)==1 and doc.grand_total==-150
            sources.append(doc);return doc
        credit('2026-06-01');assert totals(Q2)==(0,0,0)
        purchase(200,'2026-06-05');assert totals(Q2)==(2050.02,512.5,0)
        credit('2026-08-01');assert totals(Q3)==(-150,-37.5,0)
        assert any(row.get('vat_note') for row in collect(Q3) if row['base_amount']<0)
        # A real negative quarter uses the ordinary native refund/settlement path.
        frappe.db.savepoint('quarter_refund')
        refund=frappe.get_doc('Journal Entry',make_settlement(**Q3)['name']);refund.submit()
        bank=make_payment(refund.name);bank.posting_date='2026-10-05';bank.cheque_date='2026-10-05';bank.cheque_no='SYNTHETIC-QUARTER-REFUND';bank.insert();bank.submit()
        assert any(row.account==a['1640'] for row in refund.accounts)
        frappe.db.rollback(save_point='quarter_refund')
        purchase(1250,'2026-08-03');assert totals(Q3)==(-150,-37.5,0)
        frappe.set_user('Administrator');c.reload();c.set(vat.STATUS,'Registered');c.set(vat.FROM,'2026-08-15');c.save();frappe.set_user(OWNER)
        assert totals(Q2)==(2050.02,512.5,0)
        purchase(1000,'2026-08-10');assert totals(Q3)==(2100,525,0)
        registered=purchase(1000,'2026-08-20',selected='Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag - QVS')
        assert not registered.items[0].get(ITEM)
        bad=frappe.copy_doc(registered);bad.bill_no='SYNTHETIC-INVALID-QUARTER';bad.items[0].item_tax_template=template
        rejected(bad.insert,'Use the registered reverse-charge treatment')
        print('PASS native same-quarter threshold reversal, later-quarter credit/refund, historical treatment after registration and separate quarterly/ordinary bases within one quarter')
        # Correct a retroactive decision through core cancellation/amendment;
        # the original and its previous PDFs are never rewritten.
        frappe.db.savepoint('quarter_retro_registration')
        frappe.set_user('Administrator');changed=frappe.get_doc('Company',C);changed.set(vat.FROM,'2026-05-01');changed.save();frappe.set_user(OWNER)
        boundary.reload();boundary.cancel()
        amended=frappe.copy_doc(boundary);amended.amended_from=boundary.name;amended.bill_no='SYNTHETIC-RETRO-AMEND';amended.items[0].item_tax_template='Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag - QVS';amended.items[0].set(DEDUCTION,100)
        amended.insert();amended.submit()
        assert totals(Q2)==(0,0,0)
        assert totals({**Q2,'return_type':ORDINARY})==(499.99,125,125)
        assert totals(Q3)==(2250,562.5,0)  # Earlier untaxed credit does not gain tax later.
        frappe.db.rollback(save_point='quarter_retro_registration');frappe.clear_document_cache('Company',C)
        assert totals(Q2)==(2050.02,512.5,0) and totals(Q3)==(2100,525,0)
        print('PASS native cancellation/amendment after retroactive registration and dependent later-credit correction, without rewriting source invoices')
        after_registration=credit('2026-08-20')
        assert after_registration.get(RETURN_TYPE)==ORDINARY
        assert totals(Q3)==(2100,525,0)
        assert totals({**Q3,'return_type':ORDINARY})==(850,212.5,250)
        print('PASS a post-registration credit retains the originally taxed amount without deduction and goes to the ordinary return, not the quarterly return')
        from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice
        from erpnext_norway.vat_currency import DATE,EXCHANGE
        order=frappe.get_doc({'doctype':'Purchase Order','company':C,'supplier':eur_supplier.name,
            'transaction_date':'2026-01-10','schedule_date':'2026-01-15','currency':'EUR','conversion_rate':10,
            'disable_rounded_total':1,'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':2,'rate':100,
                'schedule_date':'2026-01-15','expense_account':a['4500'],'cost_center':c.cost_center,
                'item_tax_template':template,DATE:'2026-01-10',EXCHANGE:11.0137}]}).insert();order.submit()
        foreign=make_purchase_invoice(order.name);foreign.credit_to=eur_account.name;foreign.posting_date='2026-01-16';foreign.bill_date='2026-01-16';foreign.set_posting_time=1;foreign.bill_no='SYNTHETIC-QUARTER-EUR';foreign.disable_rounded_total=1
        for row in foreign.items:row.expense_account=a['4500'];row.cost_center=c.cost_center
        foreign.insert();foreign.submit();assert foreign.grand_total==200 and foreign.items[0].get(ITEM)==1
        assert foreign.items[0].purchase_order==order.name and foreign.items[0].get(EXCHANGE)==11.0137
        q1={'company':C,'from_date':'2026-01-01','to_date':'2026-03-31','return_type':QUARTERLY}
        assert totals(q1)==(2202.74,550.68,0)  # Book basis2000 is not the VAT basis.
        foreign_credit=make_return_doc('Purchase Invoice',foreign.name);foreign_credit.posting_date='2026-01-20';foreign_credit.bill_date='2026-01-20';foreign_credit.set_posting_time=1;foreign_credit.bill_no='SYNTHETIC-QUARTER-EUR-CREDIT';foreign_credit.update_outstanding_for_self=0;foreign_credit.items[0].qty=-1;foreign_credit.items[0].set(EXCHANGE,99)
        foreign_credit.insert();foreign_credit.submit();assert foreign_credit.items[0].get(EXCHANGE)==11.0137
        assert str(foreign_credit.items[0].get(DATE))=='2026-01-10' and totals(q1)==(0,0,0)
        foreign.reload();payment=get_payment_entry('Purchase Invoice',foreign.name,bank_account=a['1920'],bank_amount=1050)
        payment.posting_date='2026-10-05';payment.reference_date='2026-10-05';payment.reference_no='SYNTHETIC-QUARTER-EUR-PAYMENT';payment.target_exchange_rate=10.5;payment.received_amount=foreign.outstanding_amount;payment.set_amounts();payment.insert();payment.submit()
        assert foreign.reload().outstanding_amount==0 and totals(q1)==(0,0,0)
        sources.extend([foreign,foreign_credit])
        print('PASS native quarterly PO-to-EUR invoice preserves delivery FX, threshold uses2202.74 not book2000, half credit removes quarter liability and ordinary FX payment leaves VAT unchanged')
        tiny=frappe.get_doc({'doctype':'Sales Invoice','company':C,'customer':customer,'posting_date':'2026-08-20','set_posting_time':1,'due_date':'2026-10-31','currency':'NOK','conversion_rate':1,'disable_rounded_total':1,'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':.01,'income_account':a['3020'],'cost_center':c.cost_center,'item_tax_template':'MVA 25 % – varelinjer - QVS'}]}).insert();tiny.submit()
        assert tiny.grand_total==.01 and totals({**Q3,'return_type':ORDINARY})==(850.01,212.5,250)
        assert tiny.items[0].get(CODE)=='3'
        print('PASS core zero-cent tax retains the configured taxable classification on a one-cent sale')
        automatic=frappe.get_doc('Journal Entry',frappe.get_all('Journal Entry',filters={'company':C,JOURNAL:1,'docstatus':1},pluck='name')[0])
        rejected(automatic.cancel,'Correct the source purchase')
        forbidden=frappe.copy_doc(automatic);forbidden.set(JOURNAL,1);forbidden.set(RETURN_TYPE,QUARTERLY)
        forbidden.set('custom_norway_vat_period_from',automatic.get('custom_norway_vat_period_from'));forbidden.set('custom_norway_vat_period_to',automatic.get('custom_norway_vat_period_to'))
        rejected(forbidden.insert,'no longer matches')
        for field,value in ((CODE,'87'),('custom_norway_vat_rate',12)):
            posted=first.reload();posted.items[0].set(field,value)
            rejected(posted.save,'Correct the source purchase' if field==CODE else None)
        posted=first.reload();posted.items[0].set(ITEM,0);rejected(posted.save)
        for field in (CODE,'custom_norway_vat_rate',BASE):
            edited=frappe.get_doc('Journal Entry',automatic.name)
            row=next(row for row in edited.accounts if row.get(CODE)=='87')
            row.set(field,'89' if field==CODE else float(row.get(field) or 0)+1)
            rejected(edited.save,'Correct the source purchase')
        print('PASS submitted source classification and derived journal metadata cannot silently diverge from the native quarterly liability')
        frappe.db.savepoint('quarter_prereg_sale')
        early=frappe.copy_doc(tiny);early.posting_date='2026-05-20'
        early.items[0].rate=100;early.items[0].item_tax_template='Fritatt MVA – nullsats - QVS'
        early.insert();early.submit();assert early.items[0].get(CODE)=='7'
        assert not any(row['portal'] for row in collect({'company':C,'from_date':'2026-05-20','to_date':'2026-05-20'}) if row['voucher']==early.name)
        frappe.db.rollback(save_point='quarter_prereg_sale')
        print('PASS an explicit zero-rate sales template before registration keeps the no-VAT code outside the portal basis')
        rejected(lambda:collect({**Q3,'to_date':'2026-08-31'}),'complete calendar quarter')
        # The native calculator allocates Actual charges and header discount;
        # the quarterly adapter consumes its saved per-item amounts.
        from erpnext_norway.vat_quarterly import projected
        for mixed in (False,True):
            frappe.db.savepoint('quarter_freight_discount')
            freight=frappe.copy_doc(first.reload());freight.set('items',[]);freight.set('taxes',[])
            freight.bill_no='SYNTHETIC-QUARTER-FREIGHT';freight.posting_date=freight.bill_date='2026-05-20'
            freight.apply_discount_on='Grand Total';freight.additional_discount_percentage=10;freight.discount_amount=0
            freight.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
                'expense_account':a['4500'],'cost_center':c.cost_center,'item_tax_template':template})
            if mixed:freight.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
                'expense_account':a['4500'],'cost_center':c.cost_center})
            freight.append('taxes',{'charge_type':'Actual','account_head':a['6100'],'tax_amount':100,
                'description':'Synthetic quarterly fee','category':'Total','add_deduct_tax':'Add','cost_center':c.cost_center})
            freight.insert();freight.submit()
            expected=(945,236.25) if mixed else (990,247.5)
            assert tuple(map(float,next(iter(projected(freight).values()))))==expected
            assert freight.grand_total==(1890 if mixed else 990)
            frappe.db.rollback(save_point='quarter_freight_discount')
        print('PASS quarterly native freight and grand-total discount, including mixed taxable/untaxed source lines')
        # Ordinary native supplier payments and VAT settlements, no second payable.
        for source in sources:
            if source.is_return or source.currency!='NOK':continue
            source.reload();payment=get_payment_entry('Purchase Invoice',source.name,bank_account=a['1920'])
            payment.posting_date='2026-10-05';payment.reference_date='2026-10-05';payment.reference_no='SYNTHETIC-QUARTER-SUPPLIER';payment.insert();payment.submit();source.reload();assert source.outstanding_amount==0
        for filters in (Q2,Q3,{**Q3,'to_date':'2026-08-31','return_type':ORDINARY}):
            settlement=frappe.get_doc('Journal Entry',make_settlement(**filters)['name']);settlement.submit()
            payment=make_payment(settlement.name);payment.posting_date='2026-10-06';payment.cheque_date='2026-10-06';payment.cheque_no='SYNTHETIC-QUARTER-VAT';payment.insert();payment.submit()
        assert totals(Q2)==(2050.02,512.5,0) and totals(Q3)==(2100,525,0)
        frappe.db.savepoint('manual_quarter_period')
        manual=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-04-20',
            'bill_date':'2026-03-20','voucher_type':'Journal Entry','user_remark':'Synthetic manual quarterly document',
            'accounts':[{'account':a['2704'],'credit_in_account_currency':25,CODE:'87',
                'custom_norway_vat_rate':25,BASE:100,'cost_center':c.cost_center},
                {'account':a['4500'],'debit_in_account_currency':25,'cost_center':c.cost_center}]}).insert()
        manual.submit();assert manual.get(RETURN_TYPE)==QUARTERLY
        from erpnext_norway.vat_settlement import balances
        assert balances(C,Q2['from_date'],Q2['to_date'],return_type=QUARTERLY)==balances(
            C,Q2['from_date'],Q2['to_date'],return_type=QUARTERLY,lock=True)
        assert sum(balances(C,Q2['from_date'],Q2['to_date'],return_type=QUARTERLY).values())==25
        frappe.db.rollback(save_point='manual_quarter_period')
        print('PASS manual quarterly journals keep their native posting period in both report and locked settlement reads')
        evidence={'sources':[],'files':[]}
        for source in sources:
            source.reload();evidence['sources'].append({'name':source.name,'total':source.grand_total,'quarterly':[row.get(ITEM) for row in source.items],'fx':[(str(row.get('custom_norway_vat_delivery_date') or ''),row.get('custom_norway_vat_exchange_rate')) for row in source.items]})
        for source in (first,sources[5]):
            file=save_file('synthetic-quarterly-source.pdf',frappe.get_print(source.doctype,source.name,as_pdf=True),source.doctype,source.name,is_private=1)
            evidence['files'].append({'name':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
        for filters in (Q2,Q3):
            file=frappe.get_doc('File',preserve_basis(**filters)['name'])
            evidence['files'].append({'name':file.name,'sha256':hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()})
        evidence['ledger']=ledger();frappe.db.set_default('runtime_quarterly_evidence',json.dumps(evidence));frappe.db.commit()
        print('PASS native quarterly supplier/VAT payments, separate filing evidence and private invoice/credit PDFs')
finally:frappe.destroy()
