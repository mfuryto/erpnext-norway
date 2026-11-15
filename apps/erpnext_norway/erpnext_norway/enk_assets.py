"""Tax-unit selection using recorded native Asset and purchase-line references."""
from collections import defaultdict
from decimal import Decimal

import frappe

INDIVIDUAL = set('efghi')


def pool_key(row):
    group = row.saldo_group
    if group in INDIVIDUAL or group == 'j':
        return group + ':' + (row.get('asset') or row.get('unit_reference') or '')
    return group


def native_asset(name, company):
    asset = frappe.get_doc('Asset', name)
    asset.check_permission('read')
    if asset.company != company or asset.asset_quantity != 1:
        frappe.throw('Individuell skattesaldo krever ett nativt driftsmiddel i samme foretak, med antall én.')
    return asset


def source_account(asset, get_source):
    """Return the recorded acquisition account, never today's category default."""
    for doctype, link, detail in [('Purchase Receipt', 'purchase_receipt', 'purchase_receipt_item'),
            ('Purchase Invoice', 'purchase_invoice', 'purchase_invoice_item')]:
        if not asset.get(link):
            continue
        doc = get_source(doctype, asset.get(link))
        rows = [r for r in doc.items if r.name == asset.get(detail)]
        if not rows:
            rows = [r for r in doc.items if r.item_code == asset.item_code]
        if len(rows) == 1 and rows[0].expense_account:
            return rows[0].expense_account
    return None


def acquisition_allocations(source, gl, pools, selected, number, money, get_source):
    """Whole recorded GL for pooled balances; native stored cost for individual assets.

    No proportional book-value guesses. A source with ambiguous/missing native
    asset allocation is rejected rather than silently dropping an acquisition.
    """
    result = defaultdict(lambda: Decimal(0))
    amounts = defaultdict(lambda: Decimal(0))
    for row in gl:
        amounts[row.account] += number(row.debit) - number(row.credit)
    for account, amount in amounts.items():
        owners = [p for p in pools if account in selected[pool_key(p)]]
        if not owners:
            continue
        if len(owners) == 1 and not owners[0].get('asset'):
            result[pool_key(owners[0])] += amount
            continue
        if source.doctype not in {'Purchase Invoice', 'Purchase Receipt'}:
            frappe.throw('Individuell saldo krever lagrede native driftsmiddelkilder for denne tilleggskostnaden.')
        original = get_source(source.doctype, source.return_against) if source.is_return else source
        link = 'purchase_invoice' if source.doctype == 'Purchase Invoice' else 'purchase_receipt'
        detail = link + '_item'
        allocation = {}
        for pool in owners:
            asset = native_asset(pool.asset, source.company)
            if asset.get(link) != original.name:
                continue
            original_rows = [r for r in original.items if r.name == asset.get(detail)]
            if not original_rows:
                original_rows = [r for r in original.items if r.item_code == asset.item_code]
            if len(original_rows) != 1 or original_rows[0].expense_account != account:
                frappe.throw('Skattesaldoen mangler entydig lagret innkjøpslinje for driftsmiddelet.')
            expected = number(original_rows[0].valuation_rate) * number(original_rows[0].conversion_factor or 1) * number(asset.asset_quantity)
            if money(asset.net_purchase_amount) != money(expected):
                frappe.throw('Driftsmiddelets lagrede anskaffelsesverdi stemmer ikke med den native innkjøpslinjen.')
            if source.is_return:
                returned = [r for r in source.items if r.item_code == asset.item_code and r.expense_account == account]
                if len(returned) != 1 or asset.docstatus != 2:
                    continue
                # Native return requires cancelling/deleting the returned assets.
                allocation[pool_key(pool)] = -number(asset.net_purchase_amount)
            else:
                allocation[pool_key(pool)] = number(asset.net_purchase_amount)
        if money(sum(allocation.values(), Decimal(0))) != money(amount):
            frappe.throw('Individuelle skattesaldoer dekker ikke den faktiske native driftsmiddelposteringen. Avstem kildelinjer og driftsmidler.')
        for key, value in allocation.items():
            result[key] += value
    return dict(result)


def sale_allocations(source, fixed_gl, pools, selected, number, get_source, eligible=None):
    """Bind each actual sale/return item to its tax unit from native source links."""
    proceeds = defaultdict(lambda: Decimal(0))
    quantities = defaultdict(lambda: Decimal(0))
    for item in source.items:
        if not item.is_fixed_asset or not item.asset or (eligible is not None and item.name not in eligible):
            continue
        explicit = [p for p in pools if p.get('asset') == item.asset]
        if explicit:
            candidates = explicit
        else:
            candidates = [p for p in pools if not p.get('asset') and
                any(r.account in selected[pool_key(p)] for r in fixed_gl)]
            if len(candidates) != 1:
                asset = frappe.get_doc('Asset', item.asset)
                asset.check_permission('read')
                account = source_account(asset, get_source)
                candidates = [p for p in pools if not p.get('asset') and account in selected[pool_key(p)]]
            if len(candidates) > 1:
                exact = {r.account for r in fixed_gl if r.voucher_detail_no in {item.name, item.asset}}
                candidates = [p for p in candidates if exact & selected[pool_key(p)]]
        if len(candidates) != 1:
            frappe.throw('Driftsmiddelsalget mangler én entydig skattesaldo fra de lagrede native kildene.')
        key = pool_key(candidates[0])
        proceeds[key] += number(item.base_net_amount)
        quantities[key] += number(item.qty)
    return dict(proceeds), dict(quantities)


def native_scrap(source, gl, pools, selected, accounts, number):
    """Recognise only the native Asset's recorded scrap journal, with zero proceeds."""
    if source.voucher_type != 'Asset Disposal':
        return None
    names = frappe.get_list('Asset', filters={'company': source.company, 'journal_entry_for_scrap': source.name,
        'docstatus': 1}, pluck='name', limit_page_length=0)
    if len(names) != 1:
        return None
    asset = frappe.get_doc('Asset', names[0]); asset.check_permission('read')
    candidates = [p for p in pools if p.get('asset') == asset.name]
    if not candidates:
        candidates = [p for p in pools if not p.get('asset') and
            any(r.account in selected[pool_key(p)] for r in gl)]
    if len(candidates) != 1:
        frappe.throw('Native utrangering krever én entydig skattesaldo.')
    key = pool_key(candidates[0])
    gains = {r.account for r in gl if r.account in accounts and accounts[r.account].root_type in {'Income','Expense'}}
    return dict(adds={}, proceeds={key: Decimal(0)}, quantities={key: Decimal(1)},
        book_result=sum((number(r.credit)-number(r.debit) for r in gl if r.account in gains), Decimal(0)), accounts=gains)
