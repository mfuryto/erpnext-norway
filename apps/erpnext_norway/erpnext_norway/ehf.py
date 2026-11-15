"""Norwegian outgoing EHF adapter over existing native invoices and EDocument.

Only a read copy is adapted. No invoice, VAT calculation, ledger or transport
is implemented here. Generated, strictly validated XML is a native private File.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib

import frappe
from edocument.edocument.profiles.peppol.generator import PEPPOLGenerator
from lxml import etree as ET

from erpnext_norway.vat import organisation_number, is_vat_account
from erpnext_norway.vat_catalog import CODE, RATE

CHANNEL = 'custom_norway_invoice_delivery'
REFERENCE = 'custom_norway_ehf_buyer_reference'
XML = 'custom_norway_ehf_xml'
CATEGORIES = {'3':'S', '31':'S', '33':'S', '5':'Z', '6':'E', '7':'O'}
CBC = '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}'
CAC = '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}'


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({dt: [
        {'fieldname': CHANNEL, 'label': 'Invoice delivery', 'fieldtype': 'Select',
            'options': '\nStandard\nEHF', 'insert_after': 'tax_id' if dt=='Customer' else 'po_date',
            'description': 'EHF prepares validated XML on submission. Preparation does not mean the document has been sent or delivered.'},
        {'fieldname': REFERENCE, 'label': 'EHF buyer reference', 'fieldtype': 'Data',
            'insert_after': CHANNEL, 'depends_on': f'eval:doc.{CHANNEL}==="EHF"',
            'description': 'The routing reference supplied by the buyer. Keep the actual purchase order in PO No.'}
    ] for dt in ('Customer','Sales Invoice')})
    create_custom_fields({'Sales Invoice': [{'fieldname': XML, 'label': 'EHF XML',
        'fieldtype': 'Attach', 'insert_after': REFERENCE, 'read_only': 1, 'no_copy': 1,
        'print_hide': 1, 'depends_on': f'eval:doc.{CHANNEL}==="EHF"'}]})


def prepare(doc, method=None):
    if doc.docstatus not in (0, 1) or not doc.customer:
        return
    old = doc.get_doc_before_save()
    if old and old.docstatus == 1:
        return
    original = None
    if doc.is_return and doc.return_against:
        original = frappe.get_doc('Sales Invoice', doc.return_against)
        original.check_permission('read')
    if not doc.get(CHANNEL):
        doc.set(CHANNEL, (original.get(CHANNEL) if original else None)
            or frappe.get_cached_value('Customer', doc.customer, CHANNEL) or 'Standard')
    if doc.get(CHANNEL) == 'EHF':
        if not doc.get(REFERENCE):
            doc.set(REFERENCE, (original.get(REFERENCE) if original else None)
                or frappe.get_cached_value('Customer', doc.customer, REFERENCE))
        if original and not doc.po_no:
            doc.po_no = original.po_no


def source(doc):
    doc.check_permission('read')
    if doc.doctype != 'Sales Invoice' or doc.docstatus != 1 or doc.get(CHANNEL) != 'EHF':
        frappe.throw('EHF klargjøres fra en bokført faktura eller kreditnota med EHF valgt som leveringsmåte.')
    company = frappe.get_doc('Company', doc.company); company.check_permission('read')
    customer = frappe.get_doc('Customer', doc.customer); customer.check_permission('read')
    if company.country != 'Norway' or doc.currency not in {'NOK','EUR'}:
        frappe.throw('EHF er kvalifisert for norsk avsender og NOK/EUR.')
    seller = organisation_number(doc.company_tax_id)
    buyer = organisation_number(doc.tax_id or customer.tax_id)
    if not seller or not buyer:
        frappe.throw('EHF krever norsk organisasjonsnummer for både avsender og mottaker.')
    if not (doc.get(REFERENCE) or doc.po_no or '').strip():
        frappe.throw('Oppgi kjøperens EHF-mottakerreferanse eller faktiske bestillingsnummer før bokføring.')
    for field, party_type, party in [('company_address','Company',doc.company),('customer_address','Customer',doc.customer)]:
        if not doc.get(field):
            frappe.throw('Velg fakturaadresse for både avsender og mottaker før EHF klargjøres.')
        address = frappe.get_doc('Address', doc.get(field)); address.check_permission('read')
        if (address.country != 'Norway' or not address.address_line1 or not address.city or not address.pincode
                or not any(r.link_doctype == party_type and r.link_name == party for r in address.links)):
            frappe.throw('EHF krever fullstendig norsk adresse knyttet til riktig avsender og mottaker.')
    for field in ('shipping_address_name', 'contact_person'):
        if doc.get(field):
            frappe.get_doc('Address' if field=='shipping_address_name' else 'Contact',doc.get(field)).check_permission('read')
    if doc.return_against:
        original = frappe.get_doc('Sales Invoice',doc.return_against); original.check_permission('read')
        if original.company != doc.company or original.customer != doc.customer:
            frappe.throw('EHF-kreditnotaen må referere til opprinnelig faktura for samme foretak og kunde.')
    for item in doc.items:
        if item.get(CODE) not in CATEGORIES:
            frappe.throw('EHF er foreløpig kvalifisert for innenlandssalg: 25/15/12 %, nullsats, unntatt og uten MVA. Velg en kvalifisert MVA-behandling på alle linjene.')
    # The candidate treats every Actual charge as VAT. Use the existing native
    # freight/service item when a charge has no unambiguous UBL mapping yet.
    if any(not is_vat_account(r.account_head) and money(r.tax_amount_after_discount_amount) for r in doc.taxes):
        frappe.throw('EHF-tillegg i avgiftstabellen er ennå ikke kvalifisert. Bruk en ordinær frakt-/tjenestevarelinje med riktig MVA-behandling.')
    if money(sum(r.tax_amount_after_discount_amount for r in doc.taxes)) != money(doc.total_taxes_and_charges):
        frappe.throw('EHF-grunnlaget stemmer ikke med fakturaens bokførte avgifter.')
    return seller, buyer


class NorwegianGenerator(PEPPOLGenerator):
    """Extend missing Norwegian identifiers/reference/bank mapping, reuse format."""
    def __init__(self, invoice, seller, buyer):
        self.seller_org, self.buyer_org = seller, buyer
        super().__init__(invoice)

    def get_seller_electronic_address(self, company, seller_contact=None):
        return {'scheme_id':'0192','value':self.seller_org}

    def get_buyer_electronic_address(self, customer, invoice, buyer_contact=None, buyer_address=None):
        return {'scheme_id':'0192','value':self.buyer_org}

    def get_vat_category_code(self, invoice, item=None, tax=None):
        codes = {item.get(CODE)} if item else {r.get(CODE) for r in invoice.items}
        categories = {CATEGORIES.get(c) for c in codes}
        if len(categories) != 1 or None in categories:
            frappe.throw('Tilleggets MVA-behandling er ikke entydig i EHF-grunnlaget.')
        return categories.pop()

    def _get_exemption_reason_code(self, category_code):
        # EU Directive article 132 is not the basis for Norwegian exemption.
        return '' if category_code == 'E' else super()._get_exemption_reason_code(category_code)

    def _get_exemption_reason_text(self, category_code):
        return 'Unntatt merverdiavgift' if category_code == 'E' else super()._get_exemption_reason_text(category_code)

    def map_unit_code(self, unit):
        from erpnext.edi.doctype.code_list.code_list import get_codes_for
        codes = get_codes_for('urn:peppol:id:codelist:UNECERec20', 'UOM', unit)
        if len(codes) == 1:
            return codes[0]
        if not codes and unit == 'Nos':
            return 'C62'  # Exact native count unit only, never a fallback for kg/hours.
        frappe.throw('Koble måleenheten til én UNECE Rec20-kode i ERPNexts ordinære kodeliste før EHF klargjøres.')

    def _get_item_tax_rate(self, item):
        return float(item.get(RATE) or 0)

    def _set_header(self):
        super()._set_header()
        reference = self.invoice.get(REFERENCE)
        if reference:
            node = self.root.find(CBC+'BuyerReference')
            if node is None:
                node = ET.Element(CBC+'BuyerReference')
                currency = self.root.find(CBC+'DocumentCurrencyCode')
                self.root.insert(self.root.index(currency)+1,node)
            node.text = reference
        if self.invoice.currency != 'NOK' and money(self.invoice.total_taxes_and_charges):
            currency = self.root.find(CBC+'DocumentCurrencyCode')
            node = ET.Element(CBC+'TaxCurrencyCode'); node.text='NOK'
            self.root.insert(self.root.index(currency)+1,node)

    def _set_seller(self):
        super()._set_seller()
        legal = self.root.find(CAC+'AccountingSupplierParty/'+CAC+'Party/'+CAC+'PartyLegalEntity')
        ET.SubElement(legal,CBC+'CompanyID',schemeID='0192').text=self.seller_org

    def _set_buyer(self):
        super()._set_buyer()
        legal = self.root.find(CAC+'AccountingCustomerParty/'+CAC+'Party/'+CAC+'PartyLegalEntity')
        ET.SubElement(legal,CBC+'CompanyID',schemeID='0192').text=self.buyer_org

    def _add_payment_means(self):
        from erpnext.accounts.doctype.bank_account.bank_account import get_default_company_bank_account
        selected = self.invoice.get('company_bank_account') or get_default_company_bank_account(self.invoice.company,'Customer',self.invoice.customer)
        if not selected:
            frappe.throw('Velg foretakets betalingskonto i ERPNext før EHF klargjøres.')
        bank = frappe.get_doc('Bank Account',selected); bank.check_permission('read')
        if bank.company != self.invoice.company or not bank.is_company_account or bank.disabled:
            frappe.throw('EHF-betalingskontoen må være en aktiv firmabankkonto i samme foretak.')
        account = bank.iban or bank.bank_account_no
        if not account:
            frappe.throw('Oppgi IBAN eller bankkontonummer på foretakets betalingskonto.')
        means=ET.SubElement(self.root,CAC+'PaymentMeans')
        ET.SubElement(means,CBC+'PaymentMeansCode').text='30'
        ET.SubElement(means,CBC+'PaymentID').text=self.invoice.name
        payee=ET.SubElement(means,CAC+'PayeeFinancialAccount')
        ET.SubElement(payee,CBC+'ID').text=account

    def _add_tax_totals(self):
        super()._add_tax_totals()
        if self.invoice.currency != 'NOK' and money(self.invoice.total_taxes_and_charges):
            total=ET.SubElement(self.root,CAC+'TaxTotal')
            ET.SubElement(total,CBC+'TaxAmount',currencyID='NOK').text=f'{abs(money(self.invoice.base_total_taxes_and_charges)):.2f}'


def xml(doc):
    seller,buyer=source(doc)
    adapted=deepcopy(doc)
    # ERPNext has already distributed any document discount to net_amount/
    # net_rate. Serialize those native line values; do not allocate it again.
    for item in adapted.items:
        item.amount=item.net_amount; item.rate=item.net_rate
    adapted.total=doc.net_total
    adapted.discount_amount=0; adapted.additional_discount_percentage=0
    adapted.company_tax_id=('NO'+seller+'MVA') if 'MVA' in (doc.company_tax_id or '').upper() else ''
    adapted.tax_id=''  # Buyer legal/endpoint ID is separate from optional VAT ID.
    generator=NorwegianGenerator(adapted,seller,buyer); generator.create_einvoice()
    content=generator.get_xml_bytes()
    from erpnext_norway.ehf_validation import validate
    warnings=validate(content)
    return content,warnings


def file_for(doc):
    if not doc.get(XML):
        return None
    name = frappe.db.get_value('File', {'file_url': doc.get(XML), 'attached_to_doctype': doc.doctype,
        'attached_to_name': doc.name, 'attached_to_field': XML, 'is_private': 1})
    if not name:
        frappe.throw('Det opprinnelige EHF-vedlegget mangler. Undersøk dokumentasjonen før levering.')
    return frappe.get_doc('File', name)


def preserve(doc, method=None):
    if doc.get(CHANNEL) != 'EHF':
        doc.db_set(XML, None, update_modified=False)
        return
    content,warnings=xml(doc)
    from frappe.utils.file_manager import save_file
    file = save_file(doc.name+'-ehf.xml',content,doc.doctype,doc.name,is_private=1,df=XML)
    doc.db_set(XML, file.file_url, update_modified=False)
    # A real validation result belongs with the real XML, as a standard File.
    result={'xml_sha256':hashlib.sha256(content).hexdigest(),'rules':'Peppol BIS Billing 3.0.21 / May 2026',
        'warnings':warnings,'delivery':'Prepared only; not transmitted'}
    save_file(doc.name+'-ehf-validation.json',frappe.as_json(result),doc.doctype,doc.name,is_private=1)

