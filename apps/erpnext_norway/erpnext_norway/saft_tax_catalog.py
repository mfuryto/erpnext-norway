"""Read stored tax definitions and source classifications; never calculate tax."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import frappe

from erpnext_norway import saft_builder as xml
from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION, SALES_CODE, PURCHASE_CODE

ZERO = {'0', '5', '6', '7', '20', '52', '85'}
IMPORT = {'81', '82', '83', '84'}


def _parents(doctype, filters, fields):
    count = frappe.db.count(doctype, filters)
    if not count:
        return []
    rows = frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=0)
    if len(rows) != count:
        frappe.throw('SAF-T krever tilgang til alle avgiftsmaler og klassifiserte kildebilag for foretaket.', frappe.PermissionError)
    return rows


def read(company, end, period_mappings, accounts):
    from erpnext_norway.saft import SALES, PURCHASES
    from erpnext_norway.vat_journal import ACCOUNTS
    known = set(SALES) | set(PURCHASES) | set(ACCOUNTS) | ZERO
    catalog = defaultdict(set)

    def decimal(value, label, source):
        try:
            result = Decimal(str(value))
            if not result.is_finite():
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            frappe.throw(f'SAF-T: {source}: {label} mangler eller er ugyldig.')
        return result

    def add(code, rate, share, source, sales=False):
        if not code:
            return
        if code not in known and not source.startswith('Item Tax Template '):
            frappe.throw(f'SAF-T: {source}: avgiftskoden {code} har ingen kvalifisert standardkobling.')
        percentage = decimal(rate, 'Nominell sats', source) if rate is not None else None
        if code in {'21', '22'}:
            percentage = Decimal(PURCHASES[code])  # Import classification; supplier VAT stays zero.
        elif code in ZERO:
            percentage = Decimal(0)  # Same no-VAT classification as the transaction adapter.
        elif code in known and percentage == 0:
            percentage = None  # Do not turn missing historical rate metadata into zero-rated VAT.
        if percentage is not None and percentage < 0:
            frappe.throw(f'SAF-T: {source}: nominell sats kan ikke være negativ.')
        base = Decimal(100) if sales else decimal(share, 'Fradragsandel', source)
        if not 0 <= base <= 100 or (code in {'81', '83'} and not base):
            frappe.throw(f'SAF-T: {source}: registrer dokumentert fradragsandel; ukjent importfradrag blir ikke antatt.')
        if code in {'82', '84'} and base:
            frappe.throw(f'SAF-T: {source}: kode 82/84 skal ha null fradragsandel.')
        catalog[code, percentage, code if code in known else 'NA'].add(base)

    templates = _parents('Item Tax Template', {'company': company},
        ['name', SALES_CODE, PURCHASE_CODE, RATE, DEDUCTION])
    for row in templates:
        add(row.get(SALES_CODE), row.get(RATE), 100, 'Item Tax Template ' + row.name, sales=True)
        add(row.get(PURCHASE_CODE), row.get(RATE), row.get(DEDUCTION), 'Item Tax Template ' + row.name)

    for doctype in ('Sales Invoice', 'Purchase Invoice', 'Purchase Receipt', 'Journal Entry'):
        parents = _parents(doctype, {'company': company, 'docstatus': ['in', [1, 2]],
            'posting_date': ['<=', end]}, ['name'])
        if not parents:
            continue
        field = 'accounts' if doctype == 'Journal Entry' else 'items'
        child = 'Journal Entry Account' if field == 'accounts' else doctype + ' Item'
        fields = ['parent', CODE, RATE] + ([DEDUCTION, 'account'] if field == 'accounts'
            else [DEDUCTION] if doctype != 'Sales Invoice' else [])
        rows = frappe.get_all(child, filters={'parent': ['in', [r.name for r in parents]],
            'parenttype': doctype, 'parentfield': field}, fields=fields, limit_page_length=0)
        imports, outputs = defaultdict(set), defaultdict(set)
        for row in rows:
            code = row.get(CODE)
            if not code:
                continue
            source = doctype + ' ' + row.parent
            if doctype == 'Journal Entry':
                if code in IMPORT:
                    imports[row.parent].add(code)
                    if row.account not in accounts or accounts[row.account].account_id not in {'2705', '2706'}:
                        continue
                    outputs[row.parent].add(code)
                    share = row.get(DEDUCTION)
                else:
                    share = 0 if code in {'87', '89'} else 100  # Explicit no-deduction codes; otherwise the recorded VAT amount itself.
            else:
                share = 100 if doctype == 'Sales Invoice' else row.get(DEDUCTION)
            add(code, row.get(RATE), share, source, sales=doctype == 'Sales Invoice')
        for parent, codes in imports.items():
            if codes != outputs[parent]:
                frappe.throw(f'SAF-T: Journal Entry {parent}: utgående innførsels-MVA-linje mangler i avgiftsregisterets kilde.')

    # Reuse the qualified period mapping; a complete register opens no new transactions.
    for mapping in period_mappings.values():
        catalog[mapping.code, mapping.percentage, mapping.standard_tax_code].update(mapping.base_rates)
    return tuple(xml.TaxMapping(code, rate, standard, tuple(sorted(shares)))
        for (code, rate, standard), shares in catalog.items())
