"""Classification on native journals for documented VAT adjustments/settlement."""
import frappe
from collections import Counter
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate

from erpnext_norway.vat_catalog import CODE, RATE
BASE = 'custom_norway_vat_base'
SPEC = 'custom_norway_vat_specification'
SETTLEMENT = 'custom_norway_vat_settlement'
PERIOD_FROM = 'custom_norway_vat_period_from'
PERIOD_TO = 'custom_norway_vat_period_to'
ACCOUNTS = {'3': ('2700',), '31': ('2701',), '33': ('2703',),
    '1': ('2710',), '11': ('2711',), '13': ('2713',),
    '81': ('2705', '2715'), '82': ('2705',), '83': ('2706', '2716'), '84': ('2706',),
    '86': ('2704', '2714'), '87': ('2704',), '88': ('2709', '2718'), '89': ('2709',),
    '14': ('2715',), '15': ('2716',)}


def configure_fields():
    create_custom_fields({'Journal Entry Account': [
        {'fieldname': CODE, 'label': 'Norwegian VAT code', 'fieldtype': 'Data',
         'insert_after': 'account', 'allow_on_submit': 1, 'print_hide': 1},
        {'fieldname': RATE, 'label': 'Norwegian VAT rate', 'fieldtype': 'Float',
         'insert_after': CODE, 'allow_on_submit': 1, 'print_hide': 1},
        {'fieldname': BASE, 'label': 'VAT base', 'fieldtype': 'Currency',
         'insert_after': RATE, 'allow_on_submit': 1, 'print_hide': 1},
        {'fieldname': SPEC, 'label': 'VAT specification', 'fieldtype': 'Select',
         'insert_after': BASE, 'allow_on_submit': 1, 'print_hide': 1,
         'options': '\nBad debt\nCapital goods adjustment\nCapital goods reversal'},
    ], 'Journal Entry': [
        {'fieldname': SETTLEMENT, 'label': 'Norwegian VAT settlement', 'fieldtype': 'Check',
         'insert_after': 'user_remark', 'read_only': 1, 'no_copy': 1},
        {'fieldname': PERIOD_FROM, 'label': 'VAT period from', 'fieldtype': 'Date',
         'insert_after': SETTLEMENT, 'read_only': 1, 'no_copy': 1},
        {'fieldname': PERIOD_TO, 'label': 'VAT period to', 'fieldtype': 'Date',
         'insert_after': PERIOD_FROM, 'read_only': 1, 'no_copy': 1},
    ]})


def validate(doc, method=None):
    from erpnext_norway.vat import effective, STATUS, is_vat_account
    company = frappe.get_cached_doc('Company', doc.company)
    if company.country != 'Norway' or doc.is_opening == 'Yes':
        return
    from erpnext_norway.vat_quarterly import JOURNAL, RETURN_TYPE, ORDINARY, QUARTERLY, validate_journal
    from erpnext_norway.vat_import import journal_date
    tax_date = journal_date(doc)
    previous = doc.get_doc_before_save()
    if (doc.docstatus == 1 and not (previous and previous.docstatus == 1)
            and any(row.get(CODE) in {'81', '82', '83', '84'} for row in doc.accounts)
            and (not doc.bill_date or not str(doc.bill_no or '').strip())):
        frappe.throw(frappe._('Enter the customs expedition date and declaration reference in the native journal reference fields.'))
    if not doc.get(RETURN_TYPE) and not (previous and previous.docstatus == 1):
        doc.set(RETURN_TYPE, ORDINARY if effective(company, tax_date) else QUARTERLY)
    if doc.get(JOURNAL):
        validate_journal(doc)
    if doc.get(SETTLEMENT):
        # A settlement is checked against the native source ledger before posting.
        from erpnext_norway.vat_settlement import validate_settlement
        validate_settlement(doc)
        return
    previous = doc.get_doc_before_save()
    if not previous or previous.docstatus != 1:
        prepare_reversal(doc)
    old = {row.name: row for row in previous.accounts} if previous else {}
    for row in doc.accounts:
        original = old.get(row.name)
        if previous and previous.docstatus == 1 and original and all(
                (row.get(field) or None) == (original.get(field) or None) for field in (CODE, RATE, BASE, SPEC, 'custom_norway_vat_note')):
            continue
        if not is_vat_account(row.account):
            continue
        if previous and previous.docstatus == 1:
            from erpnext_norway.vat_catalog import check_metadata_period
            check_metadata_period(frappe._dict(doctype=doc.doctype, company=doc.company,
                posting_date=tax_date, is_opening=doc.is_opening))
        if not row.get(CODE):
            if doc.docstatus == 1:
                frappe.throw(frappe._('Select a Norwegian VAT code on each journal VAT line before submission.'))
            continue
        account_number = frappe.get_cached_value('Account', row.account, 'account_number')
        if account_number not in ACCOUNTS.get(row.get(CODE), ()):
            frappe.throw(frappe._('The journal VAT code does not match its VAT account.'))
        if company.get(STATUS) not in ('Registered', 'Not registered'):
            frappe.throw(frappe._('Set Norwegian VAT registration on the Company before submitting the invoice.'))
        if not effective(company, tax_date):
            if row.get(CODE) in {'81', '82', '83', '84'}:
                frappe.throw(frappe._('Import VAT before registration is paid to Customs or the forwarder. Record the actual invoice without self-assessed output VAT.'))
            allowed = (row.get(CODE) in {'87', '89'} and
                (account_number or '').startswith('270') and float(row.credit or 0) > 0 and not row.debit)
            # Output VAT reversals are not input VAT deductions. Keep this
            # extension to service-import output accounts and signed basis.
            if row.get(CODE) in {'87', '89'} and account_number in {'2704', '2709'} and row.debit > 0 and not row.credit:
                if float(row.get(BASE) or 0) >= 0 and not doc.get(JOURNAL):
                    frappe.throw(frappe._('Enter a negative VAT base for the output VAT reversal.'))
                allowed = True
            if not allowed:
                frappe.throw(frappe._('VAT on sales or input VAT deduction requires approved registration effective for this invoice.'))
        if doc.get(RETURN_TYPE) == QUARTERLY and row.get(CODE) not in {'87', '89'}:
            frappe.throw(frappe._('Use the ordinary VAT return for this VAT code.'))
        if row.get(SPEC) and row.get(CODE) not in {'1', '11', '13', '81'}:
            frappe.throw(frappe._('This VAT specification is not supported for the selected VAT code.'))


def prepare_reversal(doc):
    """Native reversal maps amounts; sign only the qualified copied VAT base."""
    if not doc.reversal_of:
        return
    source = frappe.get_doc('Journal Entry', doc.reversal_of)
    source.check_permission('read')
    from erpnext_norway.vat_quarterly import JOURNAL, RETURN_TYPE, ORDINARY, QUARTERLY
    if source.get(JOURNAL):
        frappe.throw(frappe._('Correct the source purchase or credit note to update its quarterly VAT adjustment.'))
    if source.company != doc.company or source.docstatus != 1 or source.get(SETTLEMENT):
        return
    from erpnext_norway.vat import effective
    from erpnext_norway.vat_import import journal_date
    doc.set(RETURN_TYPE, ORDINARY if effective(frappe.get_cached_doc('Company', doc.company),
        journal_date(doc)) else QUARTERLY)

    def signature(row, reverse=False):
        amounts = (row.credit_in_account_currency, row.debit_in_account_currency) if reverse else (
            row.debit_in_account_currency, row.credit_in_account_currency)
        return (row.account, row.account_currency, float(row.exchange_rate or 0),
            *map(lambda value: float(value or 0), amounts), row.get(CODE),
            float(row.get(RATE) or 0), row.get(SPEC) or '', float(row.get(BASE) or 0))

    originals = Counter(signature(row, reverse=True) for row in source.accounts
        if row.get(BASE) and frappe.get_cached_value('Account', row.account, 'account_number')
        in tuple(number for number in ACCOUNTS.get(row.get(CODE), ()) if number.startswith('270')) and
        float(row.get(BASE)) * (float(row.credit or 0) - float(row.debit or 0)) > 0)
    for row in doc.accounts:
        key = signature(row)
        if originals[key]:
            row.set(BASE, -float(row.get(BASE)))
            originals[key] -= 1
