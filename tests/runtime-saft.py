"""Native source/export controls, zero VAT, partial deduction and restored evidence."""
import hashlib
import json
import os
from pathlib import Path
import sys
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.conf.host_name='http://frontend:8080'
frappe.set_user('Administrator')
from erpnext_norway import saft
from erpnext_norway import saft_builder as xml
from erpnext_norway.vat_catalog import CODE

C = 'Runtime Norwegian Example'
OWNER = 'runtime-owner@example.invalid'
NS = {'s': xml.NS}
GROUPS = {'1500': ('balanseverdiForOmloepsmiddel', '1500'),
    '1920': ('balanseverdiForOmloepsmiddel', '1920'),
    '2050': ('egenkapital', '2050'), '2070': ('egenkapital', '2050'),
    '2400': ('kortsiktigGjeld', '2400'), '3020': ('salgsinntekt', '3000'),
    '4500': ('varekostnad', '4500'), '8050': ('finansinntekt', '8050'),
    '2701': ('kortsiktigGjeld', '2740'), '2703': ('kortsiktigGjeld', '2740'),
    '2711': ('kortsiktigGjeld', '2740'), '2713': ('kortsiktigGjeld', '2740'),
    '2704': ('kortsiktigGjeld', '2740'), '2700': ('kortsiktigGjeld', '2740'), '2710': ('kortsiktigGjeld', '2740')}


def configure(company):
    doc = frappe.get_doc('Company', company)
    doc.phone_no = '90000000'
    doc.tax_id = doc.tax_id or '999999999'
    doc.save()
    names = {r.account for r in frappe.get_all('GL Entry', filters={'company': company}, fields=['account'])}
    for name in names:
        acc = frappe.get_doc('Account', name)
        category, code = GROUPS[acc.account_number]
        if not acc.get(saft.MAPPING):
            acc.append(saft.MAPPING, {'year': 2026, 'category': category, 'code': code})
            acc.save()


def rejected(action, part, permission=False):
    frappe.db.savepoint('saft_negative')
    try:
        action()
    except (frappe.ValidationError, frappe.PermissionError, xml.SaftExportError) as error:
        assert part in str(error), (part, str(error))
        if permission:
            assert isinstance(error, frappe.PermissionError), type(error)
        frappe.db.rollback(save_point='saft_negative')
    else:
        raise AssertionError('Unsafe SAF-T export accepted: ' + part)


def exported(company=C, start='2026-01-01', end='2026-12-31'):
    content = saft.build(company, start, end)
    xml.validate_saf_t(content)
    return content, etree.fromstring(content)


def assert_sources(company, root):
    expected = frappe.get_all('GL Entry', filters={'company': company, 'posting_date': ['<=', '2026-12-31']}, fields=['name','debit','credit','cost_center'])
    for row in expected:
        if row.cost_center:
            assert root.xpath('.//s:Line[s:RecordID="'+row.name+'"]/s:Analysis/s:AnalysisID/text()',namespaces=NS)==[row.cost_center]
    assert set(root.xpath('.//s:Line/s:RecordID/text()', namespaces=NS)) == {r.name for r in expected}
    assert Decimal(root.xpath('string(.//s:TotalDebit)', namespaces=NS)) == sum((xml._money(r.debit) for r in expected), Decimal())
    assert Decimal(root.xpath('string(.//s:TotalCredit)', namespaces=NS)) == sum((xml._money(r.credit) for r in expected), Decimal())


try:
    if sys.argv[1] == 'verify':
        e = json.loads(frappe.db.get_default('runtime_saft_evidence'))
        frappe.set_user(OWNER)
        content, root = exported()
        assert_sources(C, root)
        proof = frappe.get_doc('File', e['file'])
        assert proof.is_private and hashlib.sha256(Path(proof.get_full_path()).read_bytes()).hexdigest() == e['sha256']
        for name in e['accounts']:
            assert frappe.get_doc('Account', name).get(saft.MAPPING)
        print('PASS restored SAF-T native GL IDs/totals, year-specific Account configuration and private XML proof')
    else:
        configure(C)
        frappe.set_user(OWNER)
        assert 'System Manager' not in frappe.get_roles()
        content, root = exported()
        assert_sources(C, root)
        assert root.xpath('.//s:TaxInformation[s:TaxCode="0"]/s:DebitTaxAmount/s:Amount/text()', namespaces=NS)
        assert all(Decimal(v) == 0 for v in root.xpath('.//s:TaxInformation/*[local-name()="DebitTaxAmount" or local-name()="CreditTaxAmount"]/s:Amount/text()', namespaces=NS))
        _, partial = exported(start='2026-10-19')
        assert not partial.xpath('.//s:GeneralLedgerEntries', namespaces=NS)
        assert partial.xpath('string(.//s:SelectionStartDate)',namespaces=NS)=='2026-10-19'
        assert Decimal(partial.xpath("string(.//s:Account[s:AccountID='1920']/s:OpeningDebitBalance)", namespaces=NS)) == 275
        rejected(lambda: saft.build('Runtime Recovery Example', '2026-01-01', '2026-12-31'), '', permission=True)
        rejected(lambda: saft.build(C, '2027-01-01', '2027-12-31'), '2026')
        account = frappe.get_doc('Account', frappe.db.get_value('Account', {'company': C, 'account_number': '1920'}))
        before = list(account.get(saft.MAPPING))
        frappe.db.savepoint('saft_mapping')
        account.set(saft.MAPPING, []);account.save()
        rejected(lambda: exported(), 'kontokobling')
        frappe.db.rollback(save_point='saft_mapping')
        # Opening and native cancellation stay in the ledger; only opening is
        # excluded from period movements. Roll back to preserve bank275 elsewhere.
        frappe.db.savepoint('saft_opening_cancel')
        bank=account.name
        equity=frappe.db.get_value('Account', {'company': C, 'account_number': '2070'})
        opening=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-01-01',
            'voucher_type':'Opening Entry','is_opening':'Yes','accounts':[
                {'account':bank,'debit_in_account_currency':100},
                {'account':equity,'credit_in_account_currency':100}]}).insert();opening.submit()
        cancelled=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-18','accounts':[
                {'account':bank,'debit_in_account_currency':17},
                {'account':equity,'credit_in_account_currency':17}]}).insert();cancelled.submit();cancelled.cancel()
        euro=frappe.get_doc({'doctype':'Account','company':C,'account_name':'Synthetic SAF-T EUR bank',
            'account_number':'1921','parent_account':frappe.db.get_value('Account',bank,'parent_account'),
            'account_type':'Bank','account_currency':'EUR',saft.MAPPING:[{'year':2026,
                'category':'balanseverdiForOmloepsmiddel','code':'1920'}]}).insert()
        foreign=frappe.get_doc({'doctype':'Journal Entry','company':C,'posting_date':'2026-10-18','multi_currency':1,
            'accounts':[{'account':euro.name,'account_currency':'EUR','exchange_rate':10,'debit_in_account_currency':100},
                        {'account':equity,'credit_in_account_currency':1000}]}).insert();foreign.submit()
        for kind, name, country in [('Company', C, 'Norway'), ('Customer',
                frappe.db.get_value('Customer',{'customer_name':'Runtime Norwegian Customer'}),'Sweden')]:
            frappe.get_doc({'doctype':'Address','address_title':'AAA Synthetic SAF-T '+kind,'address_type':'Billing',
                'address_line1':'Example street 10','address_line2':'Unit 2','city':'Oslo','pincode':'0001',
                'country':country,'is_primary_address':1,'links':[{'link_doctype':kind,'link_name':name}]}).insert()
        _, probe=exported()
        assert probe.xpath('string(.//s:Header/s:Company/s:Address/s:StreetName)',namespaces=NS)=='Example street 10'
        assert probe.xpath('string(.//s:Customers/s:Customer/s:Address/s:Country)',namespaces=NS)=='SE'
        foreign_line=probe.xpath('.//s:Line[s:SourceDocumentID="'+foreign.name+'" and s:AccountID="1921"]',namespaces=NS)[0]
        assert foreign_line.xpath('string(s:DebitAmount/s:CurrencyCode)',namespaces=NS)=='EUR'
        assert Decimal(foreign_line.xpath('string(s:DebitAmount/s:CurrencyAmount)',namespaces=NS))==100
        assert Decimal(foreign_line.xpath('string(s:DebitAmount/s:Amount)',namespaces=NS))==1000
        assert len(probe.xpath('.//s:Line[s:SourceDocumentID="'+cancelled.name+'"]',namespaces=NS))==4
        assert not probe.xpath('.//s:Line[s:SourceDocumentID="'+opening.name+'"]',namespaces=NS)
        assert Decimal(probe.xpath("string(.//s:Account[s:AccountID='1920']/s:OpeningDebitBalance)",namespaces=NS))==100
        assert Decimal(probe.xpath("string(.//s:Account[s:AccountID='1920']/s:ClosingDebitBalance)",namespaces=NS))==375
        frappe.db.rollback(save_point='saft_opening_cancel')
        frappe.set_user('Administrator')
        configure('Runtime VAT Example')
        frappe.set_user('runtime-vat-owner@example.invalid')
        _, registered = exported('Runtime VAT Example', start='2026-10-16')
        assert not registered.xpath('.//s:Line[s:AccountID="2700" or s:AccountID="2710"]/s:TaxInformation', namespaces=NS)
        assert registered.xpath('.//s:TaxInformation[s:TaxCode="3"]/s:CreditTaxAmount', namespaces=NS)
        assert registered.xpath('.//s:TaxInformation[s:TaxCode="1"]/s:DebitTaxAmount', namespaces=NS)
        rejected(lambda: exported('Runtime VAT Example'), 'ikke kvalifisert')
        frappe.db.savepoint('saft_partial_source')
        original = frappe.get_doc('Purchase Invoice', {'company':'Runtime VAT Example', 'docstatus':1, 'is_return':0, 'total_taxes_and_charges':100})
        partial_bill = frappe.copy_doc(original)
        partial_bill.bill_no='SYNTHETIC-SAFT-PARTIAL'
        partial_bill.bill_date='2026-10-16'
        partial_bill.set('items',[]);partial_bill.set('taxes',[])
        expense=frappe.db.get_value('Account',{'company':'Runtime VAT Example','account_number':'4500'})
        cc=frappe.get_cached_value('Company','Runtime VAT Example','cost_center')
        for rate in (25,15,12):
            for percent in (60,0):
                partial_bill.append('items', {'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
                    'expense_account':expense,'cost_center':cc,'item_tax_template':f'MVA {rate} % – varelinjer - RVE',
                    'custom_norway_deduction_percent':percent})
        partial_bill.insert()
        from frappe.utils.file_manager import save_file
        save_file('synthetic-saft-supplier.pdf',frappe.get_print(partial_bill.doctype,partial_bill.name,as_pdf=True),
            partial_bill.doctype,partial_bill.name,is_private=1)
        partial_bill.submit()
        assert partial_bill.grand_total==7040
        sale = frappe.copy_doc(frappe.get_doc('Sales Invoice', {'company':'Runtime VAT Example','docstatus':1,'is_return':0,'total_taxes_and_charges':['>',0]}))
        sale.set('items',[]);sale.set('taxes',[])
        income=frappe.db.get_value('Account',{'company':'Runtime VAT Example','account_number':'3020'})
        for rate in (25,15,12):
            sale.append('items',{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':1000,
                'income_account':income,'cost_center':cc,'item_tax_template':f'MVA {rate} % – varelinjer - RVE'})
        sale.insert();sale.submit();assert sale.grand_total==3520
        frappe.set_user('Administrator');configure('Runtime VAT Example');frappe.set_user('runtime-vat-owner@example.invalid')
        _, partial_xml=exported('Runtime VAT Example',start='2026-10-16')
        assert '60.00' in partial_xml.xpath('.//s:TaxCodeDetails[s:TaxCode="1"]/s:BaseRate/text()',namespaces=NS)
        specific=partial_xml.xpath('.//s:Line[s:SourceDocumentID="'+partial_bill.name+'"]',namespaces=NS)
        infos=[v for r in specific for v in r.xpath('./s:TaxInformation[s:TaxCode="1"]',namespaces=NS)]
        assert len(infos)==1 and Decimal(infos[0].xpath('string(s:TaxBase)',namespaces=NS))==1100
        assert Decimal(infos[0].xpath('string(s:DebitTaxAmount/s:Amount)',namespaces=NS))==150
        for code, amount in [('11','90.00'),('13','72.00')]:
            assert partial_xml.xpath('.//s:Line[s:SourceDocumentID="'+partial_bill.name+'"]/s:TaxInformation[s:TaxCode="'+code+'"]/s:DebitTaxAmount/s:Amount/text()',namespaces=NS)==[amount]
        from erpnext.controllers.sales_and_purchase_return import make_return_doc
        credit=make_return_doc('Purchase Invoice',partial_bill.name)
        credit.posting_date='2026-10-17';credit.set_posting_time=1;credit.bill_no='SYNTHETIC-SAFT-PARTIAL-CREDIT'
        credit.insert()
        save_file('synthetic-saft-credit.pdf',frappe.get_print(credit.doctype,credit.name,as_pdf=True),
            credit.doctype,credit.name,is_private=1)
        credit.submit()
        _, credit_xml=exported('Runtime VAT Example',start='2026-10-16')
        assert credit_xml.xpath('.//s:Line[s:SourceDocumentID="'+credit.name+'"]'
            '/s:TaxInformation[s:TaxCode="1"]/s:CreditTaxAmount/s:Amount/text()',namespaces=NS)==['150.00']
        credit.cancel()
        _, cancelled_xml=exported('Runtime VAT Example',start='2026-10-16')
        assert len(cancelled_xml.xpath('.//s:Line[s:SourceDocumentID="'+credit.name+'"]'
            '/s:TaxInformation[s:TaxCode="1"]',namespaces=NS))==2
        frappe.db.rollback(save_point='saft_partial_source')
        print('PASS actual mixed25/15/12 sales and partial60/zero purchase deduction, native basis1100/input150, issued credit and cancellation history')
        frappe.set_user('Administrator')
        # Persist only configuration and a private synthetic proof, not probes.
        from frappe.utils.file_manager import save_file
        proof=save_file('synthetic-saft-proof.xml',content,'Company',C,is_private=1)
        frappe.db.set_default('runtime_saft_evidence',json.dumps({'file':proof.name,
            'sha256':hashlib.sha256(content).hexdigest(),'accounts':list({r.account for r in frappe.get_all('GL Entry',filters={'company':C},fields=['account'])})}))
        frappe.db.commit()
        print('PASS owner XSD1.40 download source IDs/totals, zero VAT, whole-year/delår, native opening/cancellation, Company/year/mapping rejection and registered VAT on basis lines')
finally:
    frappe.db.rollback()
    frappe.destroy()
