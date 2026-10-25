"""Norwegian registration metadata and native tax setup; core calculates and posts VAT."""
import re

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate

STATUS = 'custom_norway_vat_status'
FROM = 'custom_norway_vat_from'
CATEGORY = 'Norge MVA 25 %'
CONFIGURED = 'custom_norway_vat_configured'


def configure():
    from erpnext_norway.vat_catalog import configure_fields
    configure_fields()
    from erpnext_norway.vat_currency import configure as configure_currency
    configure_currency()
    from erpnext_norway.vat_quarterly import configure as configure_quarterly
    configure_quarterly()
    from erpnext_norway.vat_journal import configure_fields as configure_journal_fields
    configure_journal_fields()
    from erpnext_norway.vat_evidence import configure_fields as configure_evidence_fields
    configure_evidence_fields()
    # Company has Tax ID but no Norwegian registration/approval or effective date.
    # Native Custom Field/Version and Tax Rule date ranges provide the missing data.
    create_custom_fields({doctype: [{
        'fieldname': 'custom_norway_company_tax_id', 'label': 'Company organisation number',
        'fieldtype': 'Data', 'insert_after': 'company', 'read_only': 1, 'no_copy': 1,
    }] for doctype in ('Quotation', 'Sales Order', 'Delivery Note', 'Purchase Order')})
    create_custom_fields({'Company': [
        {'fieldname': CONFIGURED, 'label': 'Norwegian VAT configuration initialized',
         'fieldtype': 'Check', 'insert_after': 'tax_id', 'hidden': 1, 'read_only': 1, 'no_copy': 1},
        {'fieldname': STATUS, 'label': 'Norwegian VAT registration', 'fieldtype': 'Select',
         'insert_after': 'tax_id', 'no_copy': 1, 'options': 'Not configured\nNot registered\nRegistered',
         'depends_on': 'eval:doc.country==="Norway"',
         'description': 'Select Registered only after registration is approved. Planned registration is not approval.'},
        {'fieldname': FROM, 'label': 'VAT registration effective from', 'fieldtype': 'Date',
         'insert_after': STATUS, 'no_copy': 1, 'depends_on': 'eval:doc.custom_norway_vat_status==="Registered"',
         'mandatory_depends_on': 'eval:doc.country==="Norway" && doc.custom_norway_vat_status==="Registered"',
         'description': 'Use the effective date in the approved registration. Existing invoices are not recalculated.'},
    ]})


def validate_company(doc, method=None):
    if doc.country != 'Norway':
        return
    state, date = doc.get(STATUS), doc.get(FROM)
    if state == 'Registered':
        if not date:
            frappe.throw(frappe._('Enter the effective date of the approved VAT registration.'))
        if not organisation_number(doc.tax_id):
            frappe.throw(frappe._('Enter the nine-digit organisation number before confirming VAT registration.'))
    elif date:
        frappe.throw(frappe._('An effective VAT registration date requires approved registration.'))


def organisation_number(value):
    match = re.fullmatch(r'(?:NO\s*)?(\d{9})(?:\s*MVA)?', (value or '').strip(), re.I)
    return match[1] if match else None


def configure_company(doc, method=None):
    from erpnext_norway.tax_names import configure as configure_names
    configure_names(doc.name)
    if doc.country != 'Norway' or doc.get(STATUS) not in ('Not registered', 'Registered'):
        return
    from erpnext_norway.vat_quarterly import seed as seed_quarterly
    seed_quarterly(doc)
    previous = doc.get_doc_before_save()
    first = not doc.get(CONFIGURED)
    if (not first and doc.get(STATUS) == 'Registered' and previous and previous.get(STATUS) == 'Registered'
            and getdate(previous.get(FROM)) == getdate(doc.get(FROM))):
        return
    # A timeless default bypasses Tax Rule.from_date, including on backdated drafts.
    # Once the user explicitly configures registration, use dated/selected treatments.
    for doctype in ('Sales Taxes and Charges Template', 'Purchase Taxes and Charges Template'):
        for name in frappe.get_all(doctype, filters={'company': doc.name, 'is_default': 1}, pluck='name'):
            template = frappe.get_doc(doctype, name)
            if any(is_vat_account(row.account_head) for row in template.taxes):
                template.is_default = 0
                template.save(ignore_permissions=True)
    if doc.get(STATUS) != 'Registered':
        return
    if not doc.cost_center:
        return  # Native Company can save itself while still creating defaults.
    accounts = {code: frappe.db.get_value('Account', {
        'company': doc.name, 'account_number': code, 'is_group': 0,
    }) for code in ('2700', '2710')}
    # Explicit alternative charts remain usable with the site's own native templates.
    if not all(accounts.values()):
        doc.db_set(CONFIGURED, 1, update_modified=False)
        return
    if not frappe.db.exists('Tax Category', CATEGORY):
        frappe.get_doc({'doctype': 'Tax Category', 'title': CATEGORY}).insert(ignore_permissions=True)
    for tax_type, code in [('Sales', '2700'), ('Purchase', '2710')]:
        doctype = f'{tax_type} Taxes and Charges Template'
        title = 'Utgående MVA 25 %' if tax_type == 'Sales' else 'Inngående MVA 25 % – fullt fradrag'
        name = frappe.db.get_value(doctype, {'company': doc.name, 'tax_category': CATEGORY, 'disabled': 0})
        if not name:
            name = frappe.get_doc({'doctype': doctype, 'title': title, 'company': doc.name,
                'is_default': 0, 'tax_category': CATEGORY,
                'taxes': [{'charge_type': 'On Net Total', 'account_head': accounts[code],
                    'description': 'MVA 25 %', 'rate': 25, 'cost_center': doc.cost_center,
                    'category': 'Total', 'add_deduct_tax': 'Add'}],
            }).insert(ignore_permissions=True).name
        filters = {'company': doc.name, 'tax_type': tax_type, 'tax_category': CATEGORY}
        rules = frappe.get_all('Tax Rule', filters=filters, pluck='name')
        template_field = 'sales_tax_template' if tax_type == 'Sales' else 'purchase_tax_template'
        if not rules and (first or not previous or previous.get(STATUS) != 'Registered'):
            frappe.get_doc({'doctype': 'Tax Rule', **filters, template_field: name,
                'from_date': doc.get(FROM), 'priority': 1}).insert(ignore_permissions=True)
        elif previous and previous.get(FROM) and previous.get(FROM) != doc.get(FROM):
            # Move only an unchanged seed range; retain later native rule customizations.
            for rule_name in rules:
                rule = frappe.get_doc('Tax Rule', rule_name)
                selectors = ('customer', 'customer_group', 'supplier', 'supplier_group', 'item', 'item_group',
                    'billing_city', 'billing_county', 'billing_state', 'billing_zipcode', 'billing_country',
                    'shipping_city', 'shipping_county', 'shipping_state', 'shipping_zipcode', 'shipping_country')
                if (rule.get(template_field) == name and not rule.to_date and rule.priority == 1
                        and str(rule.from_date) == str(previous.get(FROM))
                        and not any(rule.get(field) for field in selectors)):
                    rule.from_date = doc.get(FROM)
                    rule.save(ignore_permissions=True)

    from erpnext_norway.vat_catalog import seed, move_seed_dates
    if first or not previous or previous.get(STATUS) != 'Registered':
        seed(doc)
        doc.db_set(CONFIGURED, 1, update_modified=False)
    else:
        move_seed_dates(doc, previous)


def is_vat_account(name):
    if not name:
        return False
    row = frappe.get_cached_value('Account', name, ['account_number', 'account_name', 'account_type'], as_dict=True)
    if row and row.account_number in ('1640', '2740'):
        return False  # Settlement/bank transfers are not a new taxable transaction.
    return bool(row and ((row.account_number or '').startswith(('270', '271')) or
        (row.account_type == 'Tax' and re.search(r'\b(?:VAT|MVA|merverdiavgift)\b', row.account_name or '', re.I))))


def vat_amount(row):
    amount = row.get('base_tax_amount_after_discount_amount')
    return float(amount if amount is not None else row.get('base_tax_amount') or 0)


def effective(company, date):
    return bool(company.get(STATUS) == 'Registered' and company.get(FROM)
        and date and getdate(date) >= getdate(company.get(FROM)))


def original_invoice(doc):
    if doc.get('is_return') and doc.get('return_against'):
        return frappe.get_doc(doc.doctype, doc.return_against)


def posted_update(doc):
    previous = doc.get_doc_before_save()
    return bool(previous and previous.docstatus in (1, 2))


def stamp_invoice(doc, method=None):
    if doc.doctype != 'Sales Invoice' or not doc.company or posted_update(doc):
        return
    company = frappe.get_cached_doc('Company', doc.company)
    if company.country != 'Norway' or company.get(STATUS) not in ('Registered', 'Not registered'):
        return
    number = organisation_number(company.tax_id) or company.tax_id or ''
    # The current issuer's registration mark is distinct from the original
    # transaction's VAT calculation, which native credit notes still reverse.
    doc.company_tax_id = number + (' MVA' if effective(company, doc.posting_date) else '')


def validate_invoice(doc, method=None):
    if not doc.company or posted_update(doc):
        return
    company = frappe.get_cached_doc('Company', doc.company)
    if company.country != 'Norway':
        return
    from erpnext_norway.reverse_charge import guard_currency
    guard_currency(doc)
    from erpnext_norway.vat_quarterly import prepare as prepare_quarterly
    prepare_quarterly(doc)
    state = company.get(STATUS)
    if not state or state == 'Not configured':
        if method == 'before_submit' or doc.docstatus == 1:
            frappe.throw(frappe._('Set Norwegian VAT registration on the Company before submitting the invoice.'))
        return
    original = original_invoice(doc)
    rows = [row for row in doc.taxes if is_vat_account(row.account_head) and
        abs(vat_amount(row)) > 0.000001]
    if original:
        # Native return calculation/quantity checks remain authoritative. A later
        # registration must not turn an untaxed original into a VAT credit note.
        signatures = {(row.account_head, row.charge_type, float(row.rate or 0)) for row in original.taxes
            if is_vat_account(row.account_head) and abs(vat_amount(row)) > 0.000001}
        if any((row.account_head, row.charge_type, float(row.rate or 0)) not in signatures for row in rows):
            frappe.throw(frappe._('Keep the original invoice VAT treatment on its credit note.'))
        return
    date = (doc.get('bill_date') or doc.posting_date) if doc.doctype == 'Purchase Invoice' else doc.posting_date
    if not effective(company, date):
        prohibited = rows
        if doc.doctype == 'Purchase Invoice':
            # Non-registration does not remove reverse-charge liabilities. Only a
            # positive credit to an output VAT account is exempt from this guard;
            # a negative Deduct row must not smuggle in input VAT deduction.
            prohibited = [row for row in rows if not (
                row.add_deduct_tax == 'Deduct' and vat_amount(row) > 0 and
                (frappe.get_cached_value('Account', row.account_head, 'account_number') or '').startswith('270'))]
        if prohibited:
            frappe.throw(frappe._('VAT on sales or input VAT deduction requires approved registration effective for this invoice.'))
    elif method == 'before_submit' or doc.docstatus == 1:
        from erpnext_norway.vat_catalog import CODE
        explicit_lines = bool(doc.items) and all(row.get(CODE) for row in doc.items)
        if not (doc.tax_category or doc.taxes_and_charges or doc.taxes or explicit_lines):
            frappe.throw(frappe._('Select the applicable native tax category or tax template before submitting the invoice.'))
        template_type = 'Sales' if doc.doctype == 'Sales Invoice' else 'Purchase'
        template_category = frappe.db.get_value(template_type + ' Taxes and Charges Template',
            doc.taxes_and_charges, 'tax_category') if doc.taxes_and_charges else None
        from erpnext_norway.vat_catalog import ORDINARY
        categories = {f'Norge MVA {rate} %' for rate, *_ in ORDINARY}
        if (doc.tax_category in categories or template_category in categories) and not doc.taxes:
            frappe.throw(frappe._('No active VAT template was applied. Check the native tax rule and apply the correct template.'))


def stamp_commercial_document(doc, method=None):
    if not doc.company or posted_update(doc):
        return
    company = frappe.get_cached_doc('Company', doc.company)
    if company.country != 'Norway' or company.get(STATUS) not in ('Registered', 'Not registered'):
        return
    date = doc.get('transaction_date') or doc.get('posting_date')
    number = organisation_number(company.tax_id) or company.tax_id or ''
    doc.custom_norway_company_tax_id = number + (' MVA' if effective(company, date) else '')
