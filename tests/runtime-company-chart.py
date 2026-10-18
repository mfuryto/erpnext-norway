"""Create real Companies from the app's template; rollback synthetic data only."""
import csv
import os
from pathlib import Path

import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.local.lang = 'en'
from erpnext_norway import chart
from erpnext.accounts.doctype.account.chart_of_accounts import chart_of_accounts as native

try:
    path = 'erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts.'
    provider = frappe.get_attr(frappe.override_whitelisted_method(path + 'get_charts_for_country'))
    assert provider('Norway', with_standard=True)[0] == chart.NAME
    assert provider('Sweden', with_standard=True) == native.get_charts_for_country('Sweden', True)
    preview = frappe.get_attr(frappe.override_whitelisted_method(path + 'build_tree_from_json'))(chart.NAME)
    assert len(preview) == 765
    assert any(row['value'].startswith('1920 - ') for row in preview)
    assert chart.validate_bank_account(chart.NAME, '1920 - Bankinnskudd')
    assert not chart.validate_bank_account(chart.NAME, 'Missing account')
    expected = {row['Account Number']: row['Account Name'] for row in
                csv.DictReader(Path('/opt/runtime/norway.csv').open()) if row['Account Number']}
    company = frappe.get_doc({'doctype': 'Company', 'company_name': 'Runtime Template Example',
        'abbr': 'RTE', 'country': 'Norway', 'default_currency': 'NOK',
        'create_chart_of_accounts_based_on': 'Standard Template', 'enable_perpetual_inventory': 1}).insert()
    assert company.chart_of_accounts == chart.NAME
    accounts = frappe.get_all('Account', filters={'company': company.name},
        fields=['name', 'account_number', 'account_name', 'root_type', 'account_type', 'parent_account'])
    numbered = {row.account_number: row for row in accounts if row.account_number}
    assert {number: row.account_name for number, row in numbered.items()} == expected
    assert len(numbered) == 745
    assert {row.account_name for row in accounts if not row.parent_account} == {
        'Eiendeler', 'Gjeld', 'Egenkapital', 'Inntekter', 'Kostnader'}
    company.reload()
    for field, code in {'default_receivable_account': '1500', 'default_payable_account': '2400',
                        'default_bank_account': '1920', 'default_cash_account': '1900',
                        'round_off_account': '7740', 'default_income_account': '3000',
                        'default_expense_account': '4300'}.items():
        assert company.get(field) == numbered[code].name, (field, company.get(field), numbered[code].name)
    assert numbered['2740'].account_type == 'Tax'
    assert numbered['8050'].root_type == 'Income'
    names_before = {row.name for row in accounts}
    company.save()
    assert names_before == set(frappe.get_all('Account', filters={'company': company.name}, pluck='name'))
    explicit = frappe.get_doc({'doctype': 'Company', 'company_name': 'Runtime Explicit Template',
        'abbr': 'RET', 'country': 'Norway', 'default_currency': 'NOK',
        'chart_of_accounts': 'Standard', 'create_chart_of_accounts_based_on': 'Standard Template',
        'enable_perpetual_inventory': 0}).insert()
    assert explicit.chart_of_accounts == 'Standard'
    assert frappe.db.count('Account', {'company': explicit.name}) < 745
    explicit.chart_of_accounts = ''
    chart.select_default(explicit)
    assert not explicit.chart_of_accounts  # Never change existing companies.
    print('PASS native Company creation selects Norwegian template directly: 745 unchanged codes/names, native defaults, preview and preserved explicit/existing choices')
finally:
    frappe.db.rollback()
    frappe.clear_cache()
    frappe.destroy()
