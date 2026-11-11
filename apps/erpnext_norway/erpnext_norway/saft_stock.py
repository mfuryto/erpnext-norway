"""Read native stock purchase sources; never calculate stock valuation or VAT."""
from decimal import Decimal

import frappe

from erpnext_norway import saft_builder as xml
from erpnext_norway.saft import unsupported, PURCHASES
from erpnext_norway.vat import is_vat_account
from erpnext_norway.vat_catalog import CODE, DEDUCTION


def invoice_accounts(doc, rows):
    """Resolve stock items from posted GL source links, or one unambiguous account."""
    filters = {'company': doc.company, 'voucher_type': doc.doctype, 'voucher_no': doc.name}
    stock = frappe.get_list('Stock Ledger Entry', filters=filters,
        fields=['name', 'voucher_detail_no', 'item_code'], limit_page_length=0) if frappe.db.count('Stock Ledger Entry', filters) else []
    if len(stock) != frappe.db.count('Stock Ledger Entry', filters):
        frappe.throw('SAF-T krever lesetilgang til alle lagerpostene for bilaget.', frappe.PermissionError)
    items = {item.name: item.item_code for item in doc.items}
    if any(items.get(entry.voucher_detail_no) != entry.item_code for entry in stock):
        unsupported(doc, 'Entydige bokførte lagerkilder mangler for varelinjene.')
    pending_filters = {'company': doc.company, 'docstatus': 1,
        'posting_date': ['<=', max(r.posting_date for r in rows)],
        'status': ['not in', ['Completed', 'Skipped', 'Cancelled']]}
    pending = frappe.get_list('Repost Item Valuation', filters=pending_filters,
        fields=['name'], limit_page_length=0) if frappe.db.count('Repost Item Valuation', pending_filters) else []
    if len(pending) != frappe.db.count('Repost Item Valuation', pending_filters):
        frappe.throw('SAF-T krever lesetilgang til foretakets lagerrepostering.', frappe.PermissionError)
    if pending:
        unsupported(doc, 'Fullfør kjernens lagerrepostering før SAF-T eksporteres.')
    accounts = {r.account for r in rows if not r.party
        and frappe.get_cached_value('Account', r.account, 'account_type') == 'Stock'}
    if doc.doctype == 'Sales Invoice':
        return {}  # Sales VAT belongs to the recorded income, not stock/COGS.
    result = {}
    for source in stock:
        exact = {r.account for r in rows if r.account in accounts
            and r.voucher_detail_no == source.voucher_detail_no}
        item = next(r for r in doc.items if r.name == source.voucher_detail_no)
        dimension_accounts = {r.account for r in rows if r.account in accounts
            and (r.cost_center or '') == (item.cost_center or '')
            and (r.project or '') == (item.get('project') or '')}
        candidates = exact or (dimension_accounts if len(accounts) > 1 else accounts)
        if (not accounts and any(r.account == item.expense_account for r in rows)
                and frappe.get_cached_value('Account', item.expense_account, 'root_type') == 'Expense'):
            candidates = {item.expense_account}  # Native periodic inventory expense, as stored on the invoice.
        if len(candidates) != 1:
            unsupported(doc, 'Lagerlinjen mangler en entydig bokført kontokobling.')
        result[source.voucher_detail_no] = next(iter(candidates))
    return result


def receipt_taxes(doc, rows):
    """Code85 describes a recorded declaration, not supplier consideration."""
    from erpnext_norway.vat_import import DATE, REFERENCE
    from erpnext_norway.vat_journal import BASE
    if any(is_vat_account(r.account) and (r.debit or r.credit) for r in rows):
        unsupported(doc, 'Mottak med bokført MVA krever egen kildekobling.')
    if doc.is_return:
        return {}, {}  # Returning goods does not reverse the import declaration.
    assets = [r for r in rows if not r.party
        and frappe.get_cached_value('Account', r.account, 'account_type') in {'Stock', 'Fixed Asset'}]
    result = {}
    for item in doc.items:
        if item.get(CODE) != '85':
            continue
        if not item.get(DATE) or not item.get(REFERENCE) or item.get(BASE) is None or xml._money(item.get(BASE)) < 0:
            unsupported(doc, 'Mottakets deklarasjonsgrunnlag mangler.')
        exact = [r for r in assets if r.voucher_detail_no == item.name]
        candidates = exact or (assets if len({r.account for r in assets}) == 1 else [])
        if not candidates:
            unsupported(doc, 'Deklarasjonen mangler en entydig bokført aktivakonto.')
        for row in candidates:
            result.setdefault(row.name, []).append(xml.TaxInformation('85',
                xml._money(item.get(BASE)), Decimal(0), tax_base_description=
                    'Ekspedisjonsdato: {0}'.format(item.get(DATE))))
    return result, {'85': xml.TaxMapping('85', Decimal(0), '85', (Decimal(0),))}


def invoice_taxes(doc, rows):
    codes = {item.get(CODE) for item in doc.items}
    if (doc.doctype != 'Purchase Invoice' or doc.currency not in {'NOK', 'EUR'}
            or not codes <= {'20', '21', '22'}
            or doc.get('is_internal_supplier')
            or any(item.get('is_fixed_asset') or item.get('purchase_receipt') for item in doc.items)
            or any(is_vat_account(t.account_head) and xml._money(t.base_tax_amount) for t in doc.taxes)
            or any(is_vat_account(r.account) and (r.debit or r.credit) for r in rows)):
        unsupported(doc, 'Denne lager-/avgiftsbehandlingens eksportmapping er ikke kvalifisert.')
    stock_filters = {'company': doc.company, 'voucher_type': doc.doctype, 'voucher_no': doc.name}
    stock = frappe.get_list('Stock Ledger Entry', filters=stock_filters,
        fields=['name', 'voucher_detail_no', 'item_code'], limit_page_length=0) if frappe.db.count('Stock Ledger Entry', stock_filters) else []
    if len(stock) != frappe.db.count('Stock Ledger Entry', stock_filters):
        frappe.throw('SAF-T krever lesetilgang til alle lagerpostene for bilaget.', frappe.PermissionError)
    items = {item.name: item.item_code for item in doc.items}
    if any(items.get(entry.voucher_detail_no) != entry.item_code for entry in stock):
        unsupported(doc, 'Entydige bokførte lagerkilder mangler for varelinjene.')
    # A queued native repost may replace both values and GL IDs. Export only
    # completed sources; do not run jobs or reconstruct their earlier ledgers.
    pending_filters = {'company': doc.company, 'docstatus': 1,
        'posting_date': ['<=', max(r.posting_date for r in rows)],
        'status': ['not in', ['Completed', 'Skipped', 'Cancelled']]}
    pending = frappe.get_list('Repost Item Valuation', filters=pending_filters,
        fields=['name'], limit_page_length=0) if frappe.db.count('Repost Item Valuation', pending_filters) else []
    if len(pending) != frappe.db.count('Repost Item Valuation', pending_filters):
        frappe.throw('SAF-T krever lesetilgang til foretakets lagerrepostering.', frappe.PermissionError)
    if pending:
        unsupported(doc, 'Fullfør kjernens lagerrepostering før SAF-T eksporteres.')
    assets = [r for r in rows if not r.party
        and frappe.get_cached_value('Account', r.account, 'account_type') == 'Stock']
    stock_items = {entry.voucher_detail_no for entry in stock}
    stock_codes = {item.get(CODE) for item in doc.items if item.name in stock_items}
    if (bool(assets) != bool(stock_items) or (len(stock_codes) > 1 and len({r.account for r in assets}) > 1)):
        unsupported(doc, 'Blandede importkoder på flere lagerkontoer mangler entydig bokført kobling.')
    result = {}
    for row in assets:
        sides = (False, True) if row.debit and row.credit else (None,)
        result[row.name] = [xml.TaxInformation(code, tax_amount=Decimal(0), line_credit=side)
            for code in sorted(stock_codes) for side in sides]
    for item in doc.items:
        if item.name in stock_items:
            continue
        if frappe.get_cached_value('Account', item.expense_account, 'root_type') != 'Expense':
            unsupported(doc)
        candidates = [r for r in rows if not r.party and r.account == item.expense_account]
        if not candidates and xml._money(item.base_net_amount):
            unsupported(doc, 'Bokført kostnadskonto mangler for den ikke-lagerførte linjen.')
        for row in candidates:
            values = result.setdefault(row.name, [])
            sides = (False, True) if row.debit and row.credit else (None,)
            for side in sides:
                value = xml.TaxInformation(item.get(CODE), tax_amount=Decimal(0), line_credit=side)
                if value not in values:
                    values.append(value)
    mappings = {code: xml.TaxMapping(code, Decimal(PURCHASES[code]), code,
        tuple(sorted({Decimal(str(item.get(DEDUCTION) if item.get(DEDUCTION) is not None else 100))
            for item in doc.items if item.get(CODE) == code}))) for code in codes}
    return result, mappings
