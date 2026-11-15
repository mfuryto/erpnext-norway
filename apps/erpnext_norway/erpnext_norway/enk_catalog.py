"""Year-specific ENK vocabulary over native accounts; no financial calculation."""
import csv
from pathlib import Path

import frappe

DATA = Path(__file__).with_name('enk_data')
MAPPING = 'custom_norway_enk_mapping'
INCOME = {'salgsinntekt', 'annenDriftsinntekt', 'finansinntekt'}
EXPENSE = {'varekostnad', 'loennskostnad', 'annenDriftskostnad', 'finanskostnad', 'skattekostnad'}
BALANCE = {'balanseverdiForAnleggsmiddel', 'balanseverdiForOmloepsmiddel', 'langsiktigGjeld', 'kortsiktigGjeld', 'egenkapital'}


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Account': [{'fieldname': MAPPING, 'label': 'Norwegian ENK annual mapping',
        'fieldtype': 'Table', 'options': 'Norwegian SAF-T Mapping', 'insert_after': 'custom_norway_saft_mapping',
        'description': 'ENK annual-return vocabulary is separate from SAF-T. The latest applicable fiscal year is used.'}]})


def fields(year):
    if int(year) != 2026:
        frappe.throw('Næringspostlisten er kvalifisert for inntektsåret 2026.')
    with (DATA / 'fields-2026.csv').open() as stream:
        return {(r['category'], r['code']): r for r in csv.DictReader(stream, delimiter=';')}


def defaults():
    from erpnext_norway.saft import standard_account_mappings
    result = dict(standard_account_mappings())
    with (DATA / 'account-overrides.csv').open() as stream:
        for row in csv.DictReader(stream, delimiter=';'):
            for identity, target in list(result.items()):
                if identity[0] == row['account_number'] and target == (row['source_category'], row['source_code']):
                    result[identity] = (row['category'], row['code'])
    return result


def resolve(accounts, year):
    """Use the existing native child-table schema in a separate Account field."""
    valid = fields(year)
    standard = defaults()
    selected = {}
    names = list(accounts)
    if names:
        for row in frappe.get_all('Norwegian SAF-T Mapping', filters={'parenttype': 'Account',
                'parentfield': MAPPING, 'parent': ['in', names], 'year': ['<=', int(year)]},
                fields=['parent', 'year', 'category', 'code']):
            selected.setdefault(row.parent, []).append(row)
    result = {}
    for name, account in accounts.items():
        history = selected.get(name, [])
        latest = max((r.year for r in history), default=None)
        choices = [r for r in history if r.year == latest]
        identity = (account.account_number, account.account_name, account.root_type)
        target = ((choices[0].category, choices[0].code) if len(choices) == 1 else
            standard.get(identity) if not choices else None)
        category = target[0] if target else None
        correct_root = ((category in INCOME and account.root_type == 'Income')
            or (category in EXPENSE and account.root_type == 'Expense')
            or (category == 'egenkapital' and account.root_type == 'Equity')
            or (category in {'langsiktigGjeld', 'kortsiktigGjeld'} and account.root_type == 'Liability')
            or (category in {'balanseverdiForAnleggsmiddel', 'balanseverdiForOmloepsmiddel'} and account.root_type == 'Asset'))
        result[name] = (valid[target] if target in valid and correct_root else None)
    return result
