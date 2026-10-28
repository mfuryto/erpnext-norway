"""Try native ledger reports and Data Export before any Norwegian XML adapter.

Read-only on the shared synthetic company, except a rolled-back cancellation.
Run before and after backup/restore, both with and without the Norwegian app.
This is source qualification, not a SAF-T exporter or an EHF delivery test.
"""
import csv
import io
import os
from collections import defaultdict
from decimal import Decimal

import frappe

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.local.lang = 'en'

from frappe.core.doctype.data_export.exporter import DataExporter
from erpnext.accounts.report.general_ledger.general_ledger import execute, get_gl_entries

COMPANY = 'Runtime Norwegian Example'
OWNER = 'runtime-owner@example.invalid'


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def export(doctype, fields, filters):
    frappe.local.response = frappe._dict()
    exporter = DataExporter(doctype=doctype, all_doctypes=False, with_data=True,
        select_columns={doctype: fields}, file_type='CSV', filters=filters,
        export_without_column_meta=True)
    exporter.build_response()
    assert frappe.response.type == 'csv'
    rows = list(csv.reader(io.StringIO(frappe.response.result)))
    assert len(rows) == len(exporter.data) + 1, (doctype, len(rows), len(exporter.data))
    return exporter.data


def run():
    frappe.set_user(OWNER)
    assert 'System Manager' not in frappe.get_roles()
    accounts = export('Account', ['name', 'account_number', 'account_name'], {'company': COMPANY})
    assert len([r for r in accounts if r.account_number]) == 745
    fields = ['name', 'account', 'posting_date', 'creation', 'debit', 'credit',
        'debit_in_account_currency', 'credit_in_account_currency', 'account_currency',
        'voucher_type', 'voucher_no', 'party_type', 'party', 'is_cancelled', 'is_opening']
    entries = export('GL Entry', fields, {'company': COMPANY})
    active = [r for r in entries if not r.is_cancelled]
    assert active and sum(money(r.debit) - money(r.credit) for r in active) == 0
    assert all(r.name and r.voucher_type and r.voucher_no and r.creation for r in entries)
    by_voucher = defaultdict(Decimal)
    for row in active:
        by_voucher[(row.voucher_type, row.voucher_no)] += money(row.debit) - money(row.credit)
    assert set(by_voucher.values()) == {Decimal(0)}
    assert {'Sales Invoice', 'Purchase Invoice', 'Payment Entry', 'Journal Entry'} <= {r.voucher_type for r in active}
    filters = frappe._dict(company=COMPANY, from_date='2026-01-01', to_date='2026-12-31',
        include_default_book_entries=1, disable_opening_balance_calculation=1)
    native = get_gl_entries(filters, [])
    assert {r.gl_entry for r in native} == {r.name for r in active}
    assert sum(money(r.debit) for r in native) == sum(money(r.debit) for r in active)
    for party_type in ('Customer', 'Supplier'):
        ids = {r.party for r in active if r.party_type == party_type}
        assert ids
        masters = frappe.get_list(party_type, fields=['name', 'tax_id'],
            filters={'name': ['in', sorted(ids)]}, limit_page_length=0)
        assert {r.name for r in masters} == ids
        assert sum(money(r.debit) - money(r.credit) for r in active if r.party_type == party_type) == 0
    bank = next(r.name for r in accounts if r.account_number == '1920')
    result = execute(frappe._dict(company=COMPANY, from_date='2026-10-19', to_date='2026-12-31',
        account=[bank], include_default_book_entries=1))[1]
    opening = [r for r in result if str(r.get('account') or '').strip("'") == 'Opening']
    assert len(opening) == 1, result
    assert money(opening[0].debit) - money(opening[0].credit) == Decimal('275')
    # The ordinary API enforces user permissions. It is not an unrestricted SQL dump.
    assert not export('GL Entry', fields, {'company': 'Runtime Recovery Example'})
    try:
        export('Customer', ['name', 'tax_id'], {})
    except frappe.PermissionError:
        pass
    else:
        raise AssertionError('This owner unexpectedly has Customer export permission')
    print('PASS native owner account/GL CSV: 745 account numbers, balanced vouchers, readable parties and source IDs; opening bank275, Company isolation and denied Customer export')

    frappe.set_user('Administrator')
    frappe.db.savepoint('export_core_cancellation')
    account = next(r.name for r in accounts if r.account_number == '2070')
    doc = frappe.get_doc({'doctype': 'Journal Entry', 'company': COMPANY, 'posting_date': '2026-10-18',
        'voucher_type': 'Journal Entry', 'accounts': [
            {'account': bank, 'debit_in_account_currency': 17},
            {'account': account, 'credit_in_account_currency': 17}]}).insert()
    doc.submit()
    doc.cancel()
    filters = frappe._dict(company=COMPANY, from_date='2026-01-01', to_date='2026-12-31',
        voucher_no=doc.name, include_default_book_entries=1, disable_opening_balance_calculation=1)
    assert not get_gl_entries(filters, [])
    filters.show_cancelled_entries = 1
    cancelled = get_gl_entries(filters, [])
    assert len(cancelled) == 4 and sum(money(r.debit) - money(r.credit) for r in cancelled) == 0
    originals = export('GL Entry', fields, {'company': COMPANY, 'voucher_no': doc.name})
    assert len(originals) == 4 and all(r.is_cancelled for r in originals)
    frappe.db.rollback(save_point='export_core_cancellation')
    print('PASS native cancellation: CSV retains four original/reversal rows; normal GL excludes them and explicit cancellation filter includes them; no duplicate ledger')


try:
    run()
finally:
    frappe.db.rollback()
    frappe.destroy()
