"""Read native stock purchase sources; never calculate stock valuation or VAT."""
from decimal import Decimal

import frappe

from erpnext_norway import saft_builder as xml
from erpnext_norway.saft import unsupported, PURCHASES
from erpnext_norway.vat import is_vat_account
from erpnext_norway.vat_catalog import CODE, DEDUCTION


def invoice_taxes(doc, rows):
    codes = {item.get(CODE) for item in doc.items}
    if (doc.doctype != 'Purchase Invoice' or doc.currency not in {'NOK', 'EUR'}
            or len(codes) != 1 or not codes <= {'20', '21', '22'}
            or doc.get('is_internal_supplier')
            or any(item.get('is_fixed_asset') or item.get('purchase_receipt') for item in doc.items)
            or any(xml._money(t.base_tax_amount) for t in doc.taxes)
            or any(is_vat_account(r.account) and (r.debit or r.credit) for r in rows)):
        unsupported(doc, 'Denne lager-/avgiftsbehandlingens eksportmapping er ikke kvalifisert.')
    stock_filters = {'company': doc.company, 'voucher_type': doc.doctype, 'voucher_no': doc.name}
    stock = frappe.get_list('Stock Ledger Entry', filters=stock_filters,
        fields=['name', 'voucher_detail_no', 'item_code'], limit_page_length=0)
    if len(stock) != frappe.db.count('Stock Ledger Entry', stock_filters):
        frappe.throw('SAF-T krever lesetilgang til alle lagerpostene for bilaget.', frappe.PermissionError)
    items = {item.name: item.item_code for item in doc.items}
    if ({entry.voucher_detail_no for entry in stock} != set(items)
            or any(items.get(entry.voucher_detail_no) != entry.item_code for entry in stock)):
        unsupported(doc, 'Entydige bokførte lagerkilder mangler for varelinjene.')
    # A queued native repost may replace both values and GL IDs. Export only
    # completed sources; do not run jobs or reconstruct their earlier ledgers.
    pending_filters = {'company': doc.company, 'docstatus': 1,
        'posting_date': ['<=', max(r.posting_date for r in rows)],
        'status': ['not in', ['Completed', 'Skipped', 'Cancelled']]}
    pending = frappe.get_list('Repost Item Valuation', filters=pending_filters,
        fields=['name'], limit_page_length=0)
    if len(pending) != frappe.db.count('Repost Item Valuation', pending_filters):
        frappe.throw('SAF-T krever lesetilgang til foretakets lagerrepostering.', frappe.PermissionError)
    if pending:
        unsupported(doc, 'Fullfør kjernens lagerrepostering før SAF-T eksporteres.')
    assets = [r for r in rows if not r.party
        and frappe.get_cached_value('Account', r.account, 'account_type') == 'Stock']
    if not assets or len({r.account for r in assets}) != 1:
        unsupported(doc, 'Lagerkjøp med flere bokførte lagerkontoer er ikke kvalifisert.')
    code = next(iter(codes))
    shares = tuple(sorted({Decimal(str(item.get(DEDUCTION) if item.get(DEDUCTION) is not None else 100))
        for item in doc.items}))
    return ({r.name: [xml.TaxInformation(code, tax_amount=Decimal(0))] for r in assets},
        {code: xml.TaxMapping(code, Decimal(PURCHASES[code]), code, shares)})
