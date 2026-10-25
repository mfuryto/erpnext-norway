"""Native Journal Entry reversal, signed VAT base and registration transition.

These are documented journal corrections, not quarterly threshold treatment
or an assertion about the RF-0005 period for a supplier credit note.
"""
import os
import sys
import json
import frappe

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
from erpnext_norway import vat
from erpnext_norway.vat_catalog import CODE, RATE
from erpnext_norway.vat_journal import BASE
from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
from erpnext.accounts.general_ledger import ClosedAccountingPeriod
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect

C = 'Runtime Journal Reversals'
OWNER = 'runtime-vat-owner@example.invalid'


def report(start, end):
    return collect({'company': C, 'from_date': start, 'to_date': end})


def totals(rows):
    return tuple(round(sum(row[field] for row in rows), 2)
        for field in ('base_amount', 'output_vat', 'input_vat'))


def rejected(action, error_type=frappe.ValidationError):
    frappe.db.savepoint('journal_reverse_reject')
    try:
        action()
    except error_type:
        frappe.db.rollback(save_point='journal_reverse_reject')
    else:
        raise AssertionError('Invalid VAT deduction or reversal accepted')


try:
    if sys.argv[1] == 'verify':
        names = json.loads(frappe.db.get_default('runtime_journal_reversals'))
        for source_name, target_name in names:
            source = frappe.get_doc('Journal Entry', source_name)
            target = frappe.get_doc('Journal Entry', target_name)
            assert source.docstatus == target.docstatus == 1
            assert target.reversal_of == source.name
            assert next(row.get(BASE) for row in source.accounts if row.get(CODE)) == 3000
            assert next(row.get(BASE) for row in target.accounts if row.get(CODE)) == -3000
        assert totals(report('2026-07-01', '2026-10-31')) == (0, 0, 0)
        assert totals(report('2026-10-01', '2026-10-31')) == (-3000, -750, 0)
        print('PASS restored native journal reversal links, signed bases and reconciled VAT periods')
    else:
        company = frappe.get_doc({'doctype': 'Company', 'company_name': C, 'abbr': 'JRV',
            'country': 'Norway', 'default_currency': 'NOK', 'tax_id': '999999990',
            'enable_perpetual_inventory': 0, 'create_chart_of_accounts_based_on': 'Standard Template',
            vat.STATUS: 'Not registered'}).insert()
        accounts = {row.account_number: row.name for row in frappe.get_all('Account',
            filters={'company': C}, fields=['name', 'account_number'])}
        frappe.get_doc({'doctype': 'User Permission', 'user': OWNER, 'allow': 'Company',
            'for_value': C, 'apply_to_all_doctypes': 1}).insert()
        frappe.set_user(OWNER)
        assert 'System Manager' not in frappe.get_roles()

        def original(date):
            doc = frappe.get_doc({'doctype': 'Journal Entry', 'company': C,
                'posting_date': date, 'voucher_type': 'Journal Entry',
                'user_remark': 'Synthetic documented journal reversal qualification',
                'accounts': [
                    {'account': accounts['4500'], 'debit_in_account_currency': 750,
                        'cost_center': company.cost_center},
                    {'account': accounts['2704'], 'credit_in_account_currency': 750,
                        'cost_center': company.cost_center, CODE: '87', RATE: 25, BASE: 3000},
                ]}).insert()
            doc.submit()
            return doc

        def reverse(source, date):
            doc = make_reverse_journal_entry(source.name)
            doc.posting_date = date
            # Show that native maps an unsigned copy of our custom base.
            row = next(row for row in doc.accounts if row.get(CODE))
            assert row.get(BASE) == 3000 and row.debit_in_account_currency == 750
            doc.insert()
            assert row.get(BASE) == -3000
            doc.save()
            assert row.get(BASE) == -3000  # No sign toggling on a second save.
            doc.submit()
            assert doc.reversal_of == source.name
            assert totals([row for row in report(date, date) if row['voucher'] == doc.name]) == (-3000, -750, 0)
            return doc

        first = original('2026-07-10')
        first_return = reverse(first, '2026-08-10')
        assert totals(report('2026-07-01', '2026-08-31')) == (0, 0, 0)
        rejected(lambda: make_reverse_journal_entry(first.name))  # Native duplicate guard.
        # Native cancellation removes the reversal; original financial data remain.
        first_return.cancel()
        assert totals(report('2026-07-01', '2026-08-31')) == (3000, 750, 0)
        first_return = reverse(first, '2026-08-11')
        assert totals(report('2026-07-01', '2026-08-31')) == (0, 0, 0)
        print('PASS ordinary owner native journal reverse/save/submit/cancel, signed basis and native duplicate guard before registration')

        second = original('2026-09-10')
        # Change the ordinary Company settings, without rewriting original rows.
        company.reload()
        company.set(vat.STATUS, 'Registered')
        company.set(vat.FROM, '2026-10-01')
        company.save()
        second_return = reverse(second, '2026-10-10')
        assert totals(report('2026-09-01', '2026-09-30')) == (3000, 750, 0)
        assert totals(report('2026-10-01', '2026-10-31')) == (-3000, -750, 0)
        assert totals(report('2026-07-01', '2026-10-31')) == (0, 0, 0)
        assert next(row.get(BASE) for row in second.accounts if row.get(CODE)) == 3000
        print('PASS native journal reversal after approved registration preserves original code 87 without creating input VAT')

        def invalid(account, code, base):
            doc = frappe.copy_doc(second)
            doc.posting_date = '2026-09-20'
            doc.reversal_of = None
            cost, tax = doc.accounts
            cost.debit_in_account_currency = 0
            cost.credit_in_account_currency = 750
            tax.credit_in_account_currency = 0
            tax.debit_in_account_currency = 750
            tax.account = accounts[account]
            tax.set(CODE, code)
            tax.set(BASE, base)
            return doc.insert()

        rejected(lambda: invalid('2704', '87', 3000))
        rejected(lambda: invalid('2714', '86', -3000))
        print('PASS wrong signed output basis and input VAT deduction still rejected before effective registration')
        frappe.db.savepoint('journal_period_case')
        locked_source = original('2026-07-11')
        frappe.set_user('Administrator')
        frappe.get_doc({'doctype': 'Accounting Period', 'period_name': 'Runtime journal reversal lock',
            'company': C, 'start_date': '2026-08-12', 'end_date': '2026-08-12',
            'closed_documents': [{'document_type': 'Journal Entry', 'closed': 1}]}).insert()
        frappe.set_user(OWNER)
        rejected(lambda: reverse(locked_source, '2026-08-12'), ClosedAccountingPeriod)
        frappe.db.rollback(save_point='journal_period_case')
        print('PASS native closed Accounting Period still rejects the reversal without a bypass')
        frappe.db.set_default('runtime_journal_reversals', json.dumps([
            [first.name, first_return.name], [second.name, second_return.name]]))
    frappe.db.commit()
finally:
    frappe.destroy()
