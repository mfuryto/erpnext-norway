"""Build ordinary native journals from reconciled VAT ledger balances."""
from decimal import Decimal

import frappe
from frappe.utils import getdate, nowdate
from erpnext_norway.vat import is_vat_account
from erpnext_norway.vat_journal import SETTLEMENT, PERIOD_FROM, PERIOD_TO
from erpnext_norway.vat_quarterly import JOURNAL, RETURN_TYPE, ORDINARY, QUARTERLY


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def balances(company, from_date, to_date, lock=False, return_type=ORDINARY):
    from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
    start, end = getdate(from_date), getdate(to_date)
    if lock:
        # Serialize settlement submissions; lock reads see the current ledger.
        frappe.db.get_value('Company', company, 'name', for_update=True)
    result = {}
    # Use the report's document dates and its reconciled native tax details.
    # A supplier bill posted in the following period still belongs to its bill date.
    for row in collect({'company': company, 'from_date': start, 'to_date': end, 'return_type': return_type}):
        for name, amount in row['vat_accounts'].items():
            result[name] = result.get(name, Decimal(0)) + money(amount)
    if return_type == QUARTERLY and lock:
        # Do not let a prior repeatable-read snapshot hide a quarter adjustment
        # committed while this transaction waited on the native Company lock.
        result = {}
        for row in frappe.db.sql(f'''SELECT g.account,g.debit,g.credit
                FROM `tabGL Entry` g JOIN `tabJournal Entry` j ON j.name=g.voucher_no
                WHERE g.company=%s AND g.voucher_type='Journal Entry' AND g.is_cancelled=0
                AND j.docstatus=1 AND j.`{RETURN_TYPE}`=%s AND j.`{SETTLEMENT}`=0
                AND CASE WHEN j.`{JOURNAL}`=1 THEN COALESCE(j.bill_date,j.posting_date)
                    ELSE j.posting_date END BETWEEN %s AND %s FOR UPDATE''',
                (company, QUARTERLY, start, end), as_dict=True):
            if is_vat_account(row.account):
                result[row.account] = result.get(row.account, Decimal(0)) + money(row.credit) - money(row.debit)
    # A locking current read is essential at submit: a prior consistent-read
    # snapshot must not hide a settlement committed while this draft waited.
    settlements = frappe.db.sql(f'''SELECT name, `{PERIOD_FROM}`, `{PERIOD_TO}`
        FROM `tabJournal Entry` WHERE company=%s AND docstatus=1 AND `{SETTLEMENT}`=1
        AND `{PERIOD_FROM}`<=%s AND `{PERIOD_TO}`>=%s
        AND COALESCE(NULLIF(`{RETURN_TYPE}`,''),%s)=%s''' + (' FOR UPDATE' if lock else ''),
        (company, end, start, ORDINARY, return_type), as_dict=True)
    for settlement in settlements:
        if getdate(settlement.get(PERIOD_FROM)) != start or getdate(settlement.get(PERIOD_TO)) != end:
            frappe.throw(frappe._('The selected VAT period overlaps another submitted settlement period.'))
        rows = frappe.db.sql('''SELECT account, debit, credit FROM `tabGL Entry`
            WHERE company=%s AND voucher_type='Journal Entry' AND voucher_no=%s
            AND is_cancelled=0''' + (' FOR UPDATE' if lock else ''),
            (company, settlement.name), as_dict=True)
        for row in rows:
            if is_vat_account(row.account):
                result[row.account] = result.get(row.account, Decimal(0)) + money(row.credit) - money(row.debit)
    return {account: amount for account, amount in result.items() if amount}


def account(company, number):
    name = frappe.db.get_value('Account', {'company': company, 'account_number': number, 'is_group': 0})
    if not name:
        frappe.throw(frappe._('Configure native account {0} before creating the VAT settlement.').format(number))
    return name


def validate_settlement(doc):
    from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
    previous = doc.get_doc_before_save()
    if previous and previous.docstatus == 1:
        return  # Native allow-on-submit checks protect the financial rows/period.
    start, end = doc.get(PERIOD_FROM), doc.get(PERIOD_TO)
    if not start or not end or getdate(start) > getdate(end) or getdate(doc.posting_date) != getdate(end):
        frappe.throw(frappe._('The VAT settlement must use the selected period end as posting date.'))
    kind = doc.get(RETURN_TYPE) or ORDINARY
    wanted = balances(doc.company, start, end, lock=True, return_type=kind)
    collect({'company': doc.company, 'from_date': start, 'to_date': end})
    if not wanted:
        frappe.throw(frappe._('There are no VAT balances to settle. Preserve the VAT basis without a zero-value journal.'))
    net = sum(wanted.values(), Decimal(0))
    if net:
        wanted[account(doc.company, '2740' if net > 0 else '1640')] = -net
    actual = {}
    for row in doc.accounts:
        actual[row.account] = actual.get(row.account, Decimal(0)) + money(row.debit) - money(row.credit)
    actual = {key: value for key, value in actual.items() if value}
    if wanted != actual:
        frappe.throw(frappe._('The VAT settlement no longer matches the ledger. Recreate the draft from the current report.'))


@frappe.whitelist()
def make_settlement(company, from_date, to_date, return_type=ORDINARY):
    from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
    frappe.has_permission('Journal Entry', 'create', throw=True)
    if return_type not in (ORDINARY, QUARTERLY):
        frappe.throw(frappe._('Select an ordinary or quarterly VAT return before creating the settlement.'))
    if return_type == QUARTERLY:
        from erpnext_norway.vat_quarterly import period, sync
        if period(from_date) != (getdate(from_date), getdate(to_date)):
            frappe.throw(frappe._('Select the complete calendar quarter for the quarterly VAT return.'))
        sync(company, getdate(from_date), getdate(to_date))
    collect({'company': company, 'from_date': from_date, 'to_date': to_date, 'return_type': return_type})
    values = balances(company, from_date, to_date, lock=True, return_type=return_type)
    if not values:
        frappe.throw(frappe._('There are no VAT balances to settle. Preserve the VAT basis without a zero-value journal.'))
    net = sum(values.values(), Decimal(0))
    if net:
        values[account(company, '2740' if net > 0 else '1640')] = -net
    cost_center = frappe.get_cached_value('Company', company, 'cost_center')
    doc = frappe.get_doc({'doctype': 'Journal Entry', 'company': company, 'voucher_type': 'Journal Entry',
        'posting_date': getdate(to_date), SETTLEMENT: 1, RETURN_TYPE: return_type, PERIOD_FROM: getdate(from_date), PERIOD_TO: getdate(to_date),
        'user_remark': f'MVA-oppgjør {from_date} – {to_date}. Grunnlag: Norsk MVA-spesifikasjon.',
        'accounts': [{'account': name, 'debit_in_account_currency': float(max(amount, 0)),
                      'credit_in_account_currency': float(max(-amount, 0)), 'cost_center': cost_center}
                     for name, amount in sorted(values.items())]})
    return doc.insert().as_dict()  # Native draft: the user submits the ordinary journal.


@frappe.whitelist()
def make_payment(source_name, target_doc=None):
    from erpnext.accounts.doctype.journal_entry.journal_entry import get_outstanding
    source = frappe.get_doc('Journal Entry', source_name)
    source.check_permission('read')
    frappe.has_permission('Journal Entry', 'create', throw=True)
    if source.docstatus != 1 or not source.get(SETTLEMENT):
        frappe.throw(frappe._('Select a submitted native VAT settlement.'))
    contra = next((row for row in source.accounts if frappe.get_cached_value('Account',
        row.account, 'account_number') in ('1640', '2740')), None)
    if not contra:
        frappe.throw(frappe._('The VAT settlement has no payment or refund amount.'))
    # Reuse native journal reference/direction; do not create another outstanding ledger.
    amounts = get_outstanding({'doctype': 'Journal Entry', 'docname': source.name,
        'account': contra.account, 'company': source.company})
    debit = float(amounts.get('debit_in_account_currency') or 0)
    credit = float(amounts.get('credit_in_account_currency') or 0)
    bank = frappe.get_cached_value('Company', source.company, 'default_bank_account')
    if not bank:
        frappe.throw(frappe._('Set the native company default bank account first.'))
    return frappe.get_doc({'doctype': 'Journal Entry', 'company': source.company,
        'voucher_type': 'Bank Entry', 'posting_date': nowdate(),
        'user_remark': f'MVA-betaling/refusjon: {source.name}',
        'accounts': [{'account': contra.account, 'reference_type': 'Journal Entry', 'reference_name': source.name,
                      'debit_in_account_currency': debit, 'credit_in_account_currency': credit},
                     {'account': bank, 'debit_in_account_currency': credit, 'credit_in_account_currency': debit}],
    })  # Native unsaved bank journal: fill actual bank date/reference before saving.
