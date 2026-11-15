"""Synthetic native EHF invoices/credits, strict official validation and restore."""
import hashlib,json,os,sys
from copy import deepcopy
from pathlib import Path
from decimal import Decimal
import frappe
from lxml import etree as ET
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect()
frappe.set_user('Administrator');frappe.local.lang='nb';frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import ehf,vat
from erpnext_norway.ehf_validation import validate
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
C='Runtime EHF Example';OWNER='runtime-ehf@example.invalid'
NS={'cbc':ehf.CBC[1:-1],'cac':ehf.CAC[1:-1]}


def parsed(doc):
    f=ehf.file_for(doc);assert f and f.is_private
    content=Path(f.get_full_path()).read_bytes();validate(content)
    return ET.fromstring(content),f,content


def value(root,path):return root.findtext(path,namespaces=NS)


def rejected(action,phrase):
    frappe.db.savepoint('ehf_rejected')
    try:action()
    except (frappe.ValidationError,frappe.PermissionError) as e:assert phrase in str(e),str(e)
    else:raise AssertionError('EHF should have been rejected: '+phrase)
    finally:frappe.db.rollback(save_point='ehf_rejected')


def ledger():
    return frappe.as_json(frappe.get_all('GL Entry',filters={'company':C},
        fields=['name','account','debit','credit','voucher_no'],order_by='name'))

try:
    if sys.argv[1]=='verify':
        evidence=json.loads(frappe.db.get_default('runtime_ehf_evidence'))
        frappe.set_user(OWNER)
        for row in evidence:
            doc=frappe.get_doc('Sales Invoice',row['name']);root,file,content=parsed(doc)
            assert hashlib.sha256(content).hexdigest()==row['sha256']
            assert value(root,'cbc:ID')==doc.name
        for row in json.loads(frappe.db.get_default('runtime_ehf_files')):
            assert hashlib.sha256(Path(frappe.get_doc('File',row['name']).get_full_path()).read_bytes()).hexdigest()==row['sha256']
        print('PASS EHF private XML originals and official validation after exported restore/migration')
    else:
        company=frappe.get_doc({'doctype':'Company','company_name':C,'abbr':'EHF','country':'Norway','default_currency':'NOK',
            'tax_id':'999999999','enable_perpetual_inventory':0,'create_chart_of_accounts_based_on':'Standard Template',
            vat.STATUS:'Not registered'}).insert()
        a={r.account_number:r.name for r in frappe.get_all('Account',filters={'company':C},fields=['name','account_number'])}
        customer=frappe.get_doc({'doctype':'Customer','customer_name':'Synthetic EHF Buyer','customer_type':'Company',
            'customer_group':frappe.db.get_value('Customer Group',{'is_group':0}),'territory':frappe.db.get_value('Territory',{'is_group':0}),'tax_id':'999999980',
            ehf.CHANNEL:'EHF',ehf.REFERENCE:'Buyer routing reference'}).insert()
        addresses=[]
        for dt,name in [('Company',C),('Customer',customer.name)]:
            addresses.append(frappe.get_doc({'doctype':'Address','address_title':'Synthetic EHF '+dt,'address_type':'Billing',
                'address_line1':'Synthetic test address 1','city':'Oslo','pincode':'0150','country':'Norway',
                'is_your_company_address':dt=='Company','links':[{'link_doctype':dt,'link_name':name}]}).insert().name)
        bank=frappe.get_doc({'doctype':'Bank','bank_name':'Synthetic EHF Bank'}).insert()
        bank_account=frappe.get_doc({'doctype':'Bank Account','account_name':'Synthetic EHF settlement','bank':bank.name,
            'is_company_account':1,'is_default':1,'company':C,'account':a['1920'],'bank_account_no':'12345678903'}).insert()
        eur_account=frappe.get_doc({'doctype':'Account','account_name':'Synthetic EHF EUR receivable',
            'parent_account':frappe.db.get_value('Account',a['1500'],'parent_account'),'company':C,
            'account_type':'Receivable','account_currency':'EUR'}).insert()
        eur_customer=frappe.get_doc({'doctype':'Customer','customer_name':'Synthetic EHF EUR buyer','customer_type':'Company',
            'customer_group':frappe.db.get_value('Customer Group',{'is_group':0}),'territory':frappe.db.get_value('Territory',{'is_group':0}),
            'tax_id':'999999980','default_currency':'EUR',ehf.CHANNEL:'EHF',ehf.REFERENCE:'Buyer routing reference',
            'accounts':[{'company':C,'account':eur_account.name}]}).insert()
        address=frappe.get_doc('Address',addresses[1]);address.append('links',{'link_doctype':'Customer','link_name':eur_customer.name});address.save()
        item=frappe.get_doc({'doctype':'Item','item_code':'RUNTIME-EHF-SERVICE','item_name':'Synthetic EHF service',
            'item_group':'Services','stock_uom':'Nos','is_stock_item':0,'item_defaults':[{'company':C,'income_account':a['3020']}]}).insert()
        user=frappe.get_doc({'doctype':'User','email':OWNER,'first_name':'Synthetic EHF owner','language':'nb','send_welcome_email':0,
            'roles':[{'role':role} for role in ['Accounts Manager','Sales Manager','Stock Manager','Sales Master Manager']]}).insert()
        from frappe.utils.password import update_password
        update_password(OWNER,'Synthetic-ehf-owner-only-2026!')
        frappe.get_doc({'doctype':'User Permission','user':OWNER,'allow':'Company','for_value':C,'apply_to_all_doctypes':1}).insert()
        frappe.defaults.set_user_default('company',C,user=OWNER)
        uri='urn:peppol:id:codelist:UNECERec20'
        if not frappe.db.exists('Code List',uri):
            frappe.get_doc({'doctype':'Code List','name':uri,'title':'UNECE Recommendation 20','canonical_uri':uri}).insert()
        if not frappe.db.exists('UOM','Kg'):frappe.get_doc({'doctype':'UOM','uom_name':'Kg'}).insert()
        from erpnext.edi.doctype.code_list.code_list import get_codes_for
        if not get_codes_for(uri,'UOM','Kg'):
            frappe.get_doc({'doctype':'Common Code','code_list':uri,'title':'Kilogram','common_code':'KGM',
                'applies_to':[{'link_doctype':'UOM','link_name':'Kg'}]}).insert()
        frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
        evidence=[]
        def invoice(titles=(None,),**extra):
            return frappe.get_doc({'doctype':'Sales Invoice','company':C,'customer':customer.name,'currency':'NOK','conversion_rate':1,
                'posting_date':'2026-10-20','set_posting_time':1,'due_date':'2026-11-20','disable_rounded_total':1,'language':'nb',
                'company_address':addresses[0],'customer_address':addresses[1],'company_bank_account':bank_account.name,
                'po_no':'ACTUAL-PURCHASE-ORDER','items':[{'item_code':item.name,'qty':1,'rate':1000,'cost_center':company.cost_center,
                    'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':t}) if t else None} for t in titles],**extra})
        def submit(doc):
            doc.insert();doc.submit();root,file,content=parsed(doc)
            assert value(root,'cbc:ID')==doc.name
            assert value(root,'cbc:BuyerReference')=='Buyer routing reference'
            assert value(root,'cac:OrderReference/cbc:ID')=='ACTUAL-PURCHASE-ORDER'
            assert value(root,'cac:AccountingSupplierParty/cac:Party/cbc:EndpointID')=='999999999'
            assert value(root,'cac:AccountingCustomerParty/cac:Party/cbc:EndpointID')=='999999980'
            assert Decimal(value(root,'cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount'))==abs(ehf.money(doc.grand_total))
            before=ledger();parsed(doc);assert ledger()==before
            evidence.append({'name':doc.name,'sha256':hashlib.sha256(content).hexdigest()})
            return doc
        nonregistered=submit(invoice())
        assert value(parsed(nonregistered)[0],'cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:ID')=='O'
        standard=invoice(**{ehf.CHANNEL:'Standard'}).insert();standard.submit();assert ehf.file_for(standard) is None
        company.reload();company.set(vat.STATUS,'Registered');company.set(vat.FROM,'2026-10-21');company.save()
        # Historical nonregistered XML is retained across registration.
        assert hashlib.sha256(parsed(nonregistered)[2]).hexdigest()==evidence[0]['sha256']
        nonregistered_credit=make_return_doc('Sales Invoice',nonregistered.name)
        nonregistered_credit.posting_date='2026-10-23';nonregistered_credit.set_posting_time=1
        nonregistered_credit.insert();nonregistered_credit.submit();nr_root,nr_file,nr_content=parsed(nonregistered_credit)
        assert value(nr_root,'cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:ID')=='O'
        evidence.append({'name':nonregistered_credit.name,'sha256':hashlib.sha256(nr_content).hexdigest()})
        single=submit(invoice(('MVA 25 % – varelinjer',),posting_date='2026-10-22'))
        weighted=submit(invoice(('MVA 25 % – varelinjer',),posting_date='2026-10-22',items=[{
            'item_code':item.name,'qty':2,'uom':'Kg','conversion_factor':1,'rate':500,'cost_center':company.cost_center,
            'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':'MVA 25 % – varelinjer'})}]))
        assert parsed(weighted)[0].xpath('cac:InvoiceLine/cbc:InvoicedQuantity/@unitCode',namespaces=NS)==['KGM']
        mixed=submit(invoice(('MVA 25 % – varelinjer','MVA 15 % – varelinjer','MVA 12 % – varelinjer'),
            posting_date='2026-10-22',apply_discount_on='Net Total',additional_discount_percentage=10))
        assert ehf.money(mixed.net_total)==2700 and ehf.money(mixed.total_taxes_and_charges)==468
        submit(invoice(('Fritatt MVA – nullsats','Unntatt MVA'),posting_date='2026-10-22'))
        rounded=submit(invoice(('MVA 25 % – varelinjer',),posting_date='2026-10-22',disable_rounded_total=0,
            items=[{'item_code':item.name,'qty':1,'rate':333.33,'cost_center':company.cost_center,
                'item_tax_template':frappe.db.get_value('Item Tax Template',{'company':C,'title':'MVA 25 % – varelinjer'})}]))
        assert Decimal(value(parsed(rounded)[0],'cac:LegalMonetaryTotal/cbc:PayableAmount'))==ehf.money(rounded.rounded_total or rounded.grand_total)
        rounded_credit=make_return_doc('Sales Invoice',rounded.name);rounded_credit.posting_date='2026-10-23';rounded_credit.set_posting_time=1
        submit(rounded_credit)
        assert Decimal(value(parsed(rounded_credit)[0],'cac:LegalMonetaryTotal/cbc:PayableAmount'))==abs(ehf.money(rounded_credit.rounded_total or rounded_credit.grand_total))
        if rounded_credit.rounding_adjustment:
            assert Decimal(value(parsed(rounded_credit)[0],'cac:LegalMonetaryTotal/cbc:PayableRoundingAmount'))==abs(ehf.money(rounded_credit.rounding_adjustment))
        eur=submit(invoice(('MVA 25 % – varelinjer',),posting_date='2026-10-22',currency='EUR',conversion_rate=12))
        assert value(parsed(eur)[0],'cac:LegalMonetaryTotal/cbc:PayableAmount')=='1250.00'
        assert not value(parsed(eur)[0],'cac:LegalMonetaryTotal/cbc:PayableRoundingAmount')
        assert value(parsed(eur)[0],'cbc:TaxCurrencyCode')=='NOK'
        assert Decimal(parsed(eur)[0].xpath('cac:TaxTotal/cbc:TaxAmount[@currencyID="NOK"]/text()',namespaces=NS)[0])==3000
        euro_party=submit(invoice(('MVA 25 % – varelinjer',),posting_date='2026-10-22',currency='EUR',conversion_rate=12,
            customer=eur_customer.name,debit_to=eur_account.name))
        assert euro_party.party_account_currency=='EUR' and euro_party.outstanding_amount==1250
        assert value(parsed(euro_party)[0],'cac:LegalMonetaryTotal/cbc:PayableAmount')=='1250.00'
        partial=get_payment_entry('Sales Invoice',eur.name,bank_account=a['1920'],party_amount=7500)
        partial.reference_no='SYNTHETIC-EHF-EUR-PARTIAL';partial.reference_date=partial.posting_date='2026-10-24'
        partial.insert();partial.submit();eur.reload();assert eur.outstanding_amount==7500
        before=ledger();part=ET.fromstring(ehf.xml(eur)[0]);assert ledger()==before
        assert value(part,'cac:LegalMonetaryTotal/cbc:PayableAmount')=='625.00'
        assert value(part,'cac:LegalMonetaryTotal/cbc:PrepaidAmount')=='625.00'
        assert hashlib.sha256(parsed(eur)[2]).hexdigest()==next(r['sha256'] for r in evidence if r['name']==eur.name)
        credit=make_return_doc('Sales Invoice',mixed.name);credit.posting_date='2026-10-23';credit.set_posting_time=1
        credit.insert();credit.submit();root,file,content=parsed(credit)
        assert root.tag.endswith('CreditNote')
        assert value(root,'cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID')==mixed.name
        assert value(root,'cbc:BuyerReference')=='Buyer routing reference'
        evidence.append({'name':credit.name,'sha256':hashlib.sha256(content).hexdigest()})
        payment=get_payment_entry('Sales Invoice',single.name,bank_account=a['1920'])
        payment.reference_no='SYNTHETIC-EHF-PAYMENT';payment.reference_date=payment.posting_date='2026-10-24';payment.insert();payment.submit()
        single.reload();assert single.outstanding_amount==0
        before=ledger();paid=ET.fromstring(ehf.xml(single)[0]);assert ledger()==before
        assert value(paid,'cac:LegalMonetaryTotal/cbc:PrepaidAmount')=='1250.00'
        assert value(paid,'cac:LegalMonetaryTotal/cbc:PayableAmount')=='0.00'
        assert hashlib.sha256(parsed(single)[2]).hexdigest()==next(r['sha256'] for r in evidence if r['name']==single.name)
        # Keep PDF, XML and its real validation result byte-for-byte as ordinary Files.
        all_files=frappe.get_all('File',filters={'attached_to_doctype':'Sales Invoice',
            'attached_to_name':['in',[r['name'] for r in evidence]],'is_private':1},pluck='name')
        fingerprints=[{'name':name,'sha256':hashlib.sha256(Path(frappe.get_doc('File',name).get_full_path()).read_bytes()).hexdigest()} for name in all_files]
        frappe.db.set_default('runtime_ehf_files',frappe.as_json(fingerprints))
        unmapped=deepcopy(single);unmapped.items[0].uom='Unmapped synthetic unit'
        rejected(lambda:ehf.xml(unmapped),'måleenheten')
        no_address=deepcopy(single);no_address.company_address=None
        rejected(lambda:ehf.xml(no_address),'fakturaadresse')
        # XML tooling must fail before any entity expansion or silent rule fallback.
        entity=b'<!DOCTYPE Invoice [<!ENTITY probe SYSTEM "file:///definitely-not-an-invoice">]>'
        content=parsed(single)[2];position=content.index(b'?>')+2
        rejected(lambda:validate(content[:position]+entity+content[position:]),'DOCTYPE')
        # Re-validation must reject altered totals and real identifier errors.
        altered=ET.fromstring(parsed(single)[2]);altered.find('cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount',NS).text='0.00'
        rejected(lambda:validate(ET.tostring(altered)),'EHF-valideringen')
        customer.tax_id='999999984';customer.save()
        bad=invoice(('MVA 25 % – varelinjer',),posting_date='2026-10-22').insert()
        rejected(bad.submit,'EHF-valideringen');bad.reload();assert bad.docstatus==0 and ehf.file_for(bad) is None
        customer.tax_id='999999980';customer.save()
        no_ref=invoice(('MVA 25 % – varelinjer',),posting_date='2026-10-22',po_no='',**{ehf.REFERENCE:' '}).insert()
        rejected(no_ref.submit,'mottakerreferanse')
        before=ledger();frappe.set_user('Guest')
        try:frappe.get_doc('Sales Invoice',single.name).check_permission('read')
        except frappe.PermissionError:pass
        else:raise AssertionError('Guest read the native EHF invoice')
        frappe.set_user(OWNER);assert ledger()==before
        frappe.db.set_default('runtime_ehf_evidence',frappe.as_json(evidence));frappe.db.commit()
        print('PASS native nonregistered/registered 25/15/12/zero/exempt, mixed discount, EUR/NOK party/base currency and partial payment, rounded credit, pre-registration credit, original XML, invalid source/total, ordinary owner and guest denial')
finally:frappe.db.rollback();frappe.destroy()
