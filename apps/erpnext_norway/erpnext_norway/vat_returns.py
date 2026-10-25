"""Keep issued item-rate treatment when native templates change later.

Core recalculates returns from today's Item Tax Template. The issued invoice
already stores item_tax_rate and Item Wise Tax Detail. Configure a native template
only when those issued rates differ; core still calculates every return amount.
"""
import hashlib
import json
import re

import frappe
from frappe.utils import flt
from erpnext.stock.get_item_details import NOT_APPLICABLE_TAX, get_item_tax_map
from erpnext.controllers.sales_and_purchase_return import get_return_against_item_fields


def rate(value):
    return value if value == NOT_APPLICABLE_TAX else flt(value)


def original_rates(original, item):
    result = {}
    for account, value in (frappe.parse_json(item.item_tax_rate) or {}).items():
        current = account if frappe.db.get_value('Account', account, 'company', cache=True) == original.company else None
        if not current:
            # Native Account rename updates Link fields, but not keys inside JSON.
            # The supported Norwegian chart retains its unique account number.
            number = re.match(r'^(\d{4})\s+-', account)
            if number:
                current = frappe.db.get_value('Account', {'company': original.company,
                    'account_number': number[1], 'is_group': 0}, cache=True)
        if current:
            result[current] = rate(value)
    taxes = {tax.name: tax for tax in original.taxes}
    for detail in frappe.get_all('Item Wise Tax Detail', filters={'parent': original.name,
            'parenttype': original.doctype, 'item_row': item.name}, fields=['tax_row', 'rate']):
        if detail.tax_row in taxes:
            result.setdefault(taxes[detail.tax_row].account_head, rate(detail.rate))
    defaults = get_item_tax_map(doc=original, as_json=False)
    for tax in original.taxes:
        result.setdefault(tax.account_head, rate(defaults.get(tax.account_head, tax.rate)))
    return result


def template_rates(template):
    return {row.tax_type: NOT_APPLICABLE_TAX if row.not_applicable else flt(row.tax_rate)
            for row in template.taxes}


def frozen_template(company, rates):
    digest = hashlib.sha256(json.dumps(rates, sort_keys=True).encode()).hexdigest()[:16]
    title = f'Opprinnelig avgiftsbehandling {digest}'
    existing = frappe.get_all('Item Tax Template', filters={'company': company,
        'title': ['like', title + '%']}, pluck='name')
    for name in existing:
        template = frappe.get_doc('Item Tax Template', name)
        if not template.disabled and template_rates(template) == rates:
            return name
    if existing:
        title += ' ' + frappe.generate_hash(length=6)  # Keep the user's edited template.
    return frappe.get_doc({'doctype': 'Item Tax Template', 'company': company, 'title': title,
        'taxes': [{'tax_type': account, 'tax_rate': 0 if value == NOT_APPLICABLE_TAX else value,
                   'not_applicable': int(value == NOT_APPLICABLE_TAX)}
                  for account, value in sorted(rates.items())]}).insert().name


def prepare(doc, method=None):
    from erpnext_norway.vat import posted_update, is_vat_account
    from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION
    if (not doc.get('is_return') or not doc.get('return_against') or posted_update(doc)
            or frappe.get_cached_value('Company', doc.company, 'country') != 'Norway'):
        return
    original = frappe.get_doc(doc.doctype, doc.return_against)
    original.check_permission('read')
    if original.company != doc.company or original.docstatus != 1:
        frappe.throw(frappe._('Select a submitted original invoice from the same Company.'))
    # Preserve the existing rejection of an added/changed VAT header row.
    # A changed item template is repaired; a newly introduced VAT charge is not.
    signatures = {(row.account_head, row.charge_type, flt(row.rate))
                  for row in original.taxes if is_vat_account(row.account_head)}
    if any(is_vat_account(row.account_head) and
            (row.account_head, row.charge_type, flt(row.rate)) not in signatures
            for row in doc.taxes):
        frappe.throw(frappe._('Keep the original invoice VAT treatment on its credit note.'))
    source_field = get_return_against_item_fields(doc.doctype)
    originals = {row.name: row for row in original.items}
    for item in doc.items:
        source = originals.get(item.get(source_field))
        if not source:
            frappe.throw(frappe._('Keep the native original invoice row reference on each credit note line.'))
        from erpnext_norway.vat_currency import DATE, EXCHANGE
        for field in (CODE, RATE, DEDUCTION, DATE, EXCHANGE):
            if source.get(field) is not None and (field != CODE or source.get(field)):
                item.set(field, source.get(field))
        apply_rates(doc, item, original, source)


def apply_rates(doc, item, original, source):
    defaults = get_item_tax_map(doc=doc, as_json=False)
    issued = original_rates(original, source)
    current = get_item_tax_map(doc=doc, tax_template=item.item_tax_template, as_json=False)
    overrides = {}
    changed = False
    for tax in doc.taxes:
        account = tax.account_head
        expected = issued.get(account, 0)
        actual = rate(current.get(account, tax.rate))
        if tax.charge_type == 'Actual' and NOT_APPLICABLE_TAX not in (expected, actual):
            continue  # Native fixed amounts do not use percentage overrides.
        changed |= actual != expected
        if rate(defaults.get(account, tax.rate)) != expected:
            overrides[account] = expected
    if changed:
        item.item_tax_template = frozen_template(doc.company, overrides) if overrides else None
