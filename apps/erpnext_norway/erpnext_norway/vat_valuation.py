"""Configure native valuation and adjust receipts with native landed cost vouchers.

Amounts come from Item Wise Tax Detail. ERPNext calculates VAT, stock value,
asset cost, GL entries, future reposts and cancellations; this module supplies
configuration and the existing document references only.
"""
from collections import defaultdict

import frappe
from frappe.utils import flt

COST = 'custom_norway_vat_cost'
SOURCE = 'custom_norway_vat_invoice'
ALLOCATION = 'custom_norway_vat_allocation'
VALUATION = 'Expenses Included In Valuation'


def configure_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Purchase Taxes and Charges': [
        {'fieldname': COST, 'label': 'Norwegian VAT cost allocation', 'fieldtype': 'Check',
         'read_only': 1, 'print_hide': 1, 'insert_after': 'category'},
    ], 'Landed Cost Voucher': [
        {'fieldname': SOURCE, 'label': 'Norwegian VAT source invoice', 'fieldtype': 'Link',
         'options': 'Purchase Invoice', 'read_only': 1, 'no_copy': 1, 'insert_after': 'company'},
        {'fieldname': ALLOCATION, 'label': 'Norwegian VAT allocation', 'fieldtype': 'Check',
         'read_only': 1, 'no_copy': 1, 'print_hide': 1, 'insert_after': SOURCE},
    ]})


def capitalized(item):
    return bool(item.get('is_fixed_asset') or (item.item_code and any(
        frappe.get_cached_value('Item', item.item_code, field)
        for field in ('is_stock_item', 'is_fixed_asset'))))


def allocation_account(doc, item):
    if capitalized(item):
        selected = {tax.account_head for tax in doc.taxes if tax.account_head
                    and frappe.get_cached_value('Account', tax.account_head, 'account_type') == VALUATION}
        if not selected:
            selected = set(frappe.get_all('Account', filters={'company': doc.company,
                'account_type': VALUATION, 'is_group': 0, 'disabled': 0}, pluck='name', limit_page_length=2))
        if len(selected) != 1:
            frappe.throw(frappe._('Select one existing Expenses Included In Valuation account in the purchase taxes.'))
        account = frappe.get_doc('Account', selected.pop())
        if account.company != doc.company or account.is_group or account.account_type != VALUATION or account.disabled:
            frappe.throw(frappe._('Select one existing Expenses Included In Valuation account in the purchase taxes.'))
        return account
    if not item.expense_account:
        frappe.throw(frappe._('Select a company expense account for non-deductible VAT.'))
    account = frappe.get_doc('Account', item.expense_account)
    if account.company != doc.company or account.root_type != 'Expense' or account.is_group:
        frappe.throw(frappe._('Select a company expense account for non-deductible VAT.'))
    return account


def configured(doc):
    return bool(doc.company and frappe.get_cached_value('Company', doc.company, 'country') == 'Norway')


def basis_key(tax):
    return (tax.charge_type, str(tax.get('row_id') or '')
            if (tax.charge_type or '').startswith('On Previous Row') else '')


def guard_configuration(doc, method=None):
    if not configured(doc) or doc.docstatus == 2:
        return
    valuation_rows = [tax for tax in doc.taxes if tax.get(COST) and
        frappe.get_cached_value('Account', tax.account_head, 'account_type') == VALUATION]
    if valuation_rows:
        # Net is intrinsic, including zero deduction without an input VAT row.
        bases = {('On Net Total', '')} | {basis_key(tax) for tax in doc.taxes
                 if tax.account_head and (frappe.get_cached_value('Account', tax.account_head,
                     'account_number') or '').startswith('271')}
        if any(basis_key(tax) not in bases for tax in valuation_rows):
            frappe.throw(frappe._('Keep matching native VAT bases for automatic VAT cost rows.'))
    rows = [tax for tax in doc.taxes if tax.get(COST) and tax.category == 'Valuation and Total'
            and frappe.get_cached_value('Account', tax.account_head, 'account_type') == VALUATION]
    if rows and len(doc.items) > 1 and any(tax.charge_type.startswith('On Previous Row') for tax in rows):
        for tax in rows:
            tax.category = 'Total'  # Native LCV, rather than the unsupported valuation spread.


def costs(doc, category=None):
    """Read base-currency native amounts, including their native return signs."""
    accounts = {tax.account_head for tax in doc.taxes if (tax.category == 'Valuation and Total' or tax.get(COST) and tax.category == 'Total')
                and frappe.get_cached_value('Account', tax.account_head, 'account_type') == VALUATION}
    tax_rows = {tax.name: tax.account_head for tax in doc.taxes if tax.account_head in accounts
                and (tax.category == 'Valuation and Total' or tax.get(COST) and tax.category == 'Total')
                and (not category or tax.category == category)}
    result = defaultdict(float)
    for detail in frappe.get_all('Item Wise Tax Detail', filters={'parent': doc.name,
            'parenttype': doc.doctype}, fields=['item_row', 'tax_row', 'amount']):
        if detail.tax_row in tax_rows:
            result[(detail.item_row, tax_rows[detail.tax_row])] += flt(detail.amount)
    return result


def lock_receipts(doc, method=None):
    if not configured(doc):
        return
    for name in sorted({row.purchase_receipt for row in doc.items
                        if row.get('purchase_receipt') and capitalized(row)}):
        frappe.db.get_value('Purchase Receipt', name, 'name', for_update=True)


def adjust_receipts(doc, method=None):
    if not configured(doc):
        return
    allocate_direct(doc)
    received_items = [row for row in doc.items if row.get('purchase_receipt') and capitalized(row)]
    if not received_items:
        return
    if frappe.db.exists('Landed Cost Voucher', {SOURCE: doc.name, 'docstatus': 1}):
        frappe.throw(frappe._('A native VAT valuation adjustment already exists for this invoice.'))
    actual = costs(doc)
    grouped = defaultdict(lambda: defaultdict(float))
    receipts = {}
    billed = {}
    company = frappe.get_cached_doc('Company', doc.company)
    for item in received_items:
        if item.purchase_receipt not in receipts:
            receipts[item.purchase_receipt] = frappe.get_doc('Purchase Receipt', item.purchase_receipt)
        receipt = receipts[item.purchase_receipt]
        source = next((row for row in receipt.items if row.name == item.pr_detail), None)
        if not source or receipt.company != doc.company or receipt.docstatus != 1:
            frappe.throw(frappe._('Keep the native submitted purchase receipt row reference.'))
        source_cost = costs(receipt)
        key = (receipt.name, source.name)
        if key not in billed:
            # Current read after the receipt lock. Cumulative allocation absorbs
            # the native receipt's final cent across partial supplier invoices.
            previous = frappe.db.sql('''SELECT stock_qty FROM `tabPurchase Invoice Item`
                WHERE pr_detail=%s AND parent!=%s AND docstatus=1 FOR UPDATE''',
                (source.name, doc.name))
            billed[key] = sum(flt(row[0]) for row in previous)
        before, after = billed[key], billed[key] + flt(item.stock_qty)
        accounts = {account for row, account in (*actual.keys(), *source_cost.keys())
                    if row in (item.name, source.name)}
        # Only adapt a VAT-configured chain; explicit unrelated native templates
        # and their existing landed-cost workflows are left with core.
        tagged = {tax.account_head for document in (doc, receipt) for tax in document.taxes if tax.get(COST)}
        for account in accounts & tagged:
            amount = source_cost.get((source.name, account), 0)
            allocated_before = flt(amount * before / flt(source.stock_qty), 2) if source.stock_qty else 0
            allocated_after = flt(amount * after / flt(source.stock_qty), 2) if source.stock_qty else 0
            difference = flt(actual.get((item.name, account), 0) - (allocated_after - allocated_before), 2)
            if not difference:
                continue
            # This follows core's negative_expense_booked_in_pr choice: a
            # stock receipt valuation entry uses that charge account, otherwise SRBNB.
            # Core asset invoices do not add VAT cost to SRBNB; their charge
            # account is therefore the native counterpart in both cases.
            booked = frappe.db.exists('GL Entry', {'voucher_type': 'Purchase Receipt',
                'voucher_no': receipt.name, 'account': account, 'is_cancelled': 0})
            contra = account if account in total_accounts(doc) or booked or source.is_fixed_asset else company.stock_received_but_not_billed
            grouped[(receipt.name, contra, difference > 0)][source.name] += difference
        billed[key] = after
    for (receipt, account, positive), amounts in grouped.items():
        create_allocation(doc, 'Purchase Receipt', receipt, account, amounts, doc.name)


def total_accounts(doc):
    return {tax.account_head for tax in doc.taxes if tax.get(COST) and tax.category == 'Total'
            and frappe.get_cached_value('Account', tax.account_head, 'account_type') == VALUATION}


def create_allocation(doc, receipt_type, receipt, account, amounts, invoice=None):
    amounts = {name: flt(amount, 2) for name, amount in amounts.items() if flt(amount, 2)}
    if not amounts:
        return
    voucher = frappe.get_doc({'doctype': 'Landed Cost Voucher', 'company': doc.company,
        'posting_date': doc.posting_date, SOURCE: invoice, ALLOCATION: 1,
        'distribute_charges_based_on': 'Distribute Manually',
        'purchase_receipts': [{'receipt_document_type': receipt_type, 'receipt_document': receipt}],
        'taxes': [{'expense_account': account, 'description': frappe._('Non-deductible VAT valuation adjustment'),
                   'amount': flt(sum(amounts.values()), 2)}]})
    voucher.get_items_from_purchase_receipts()
    voucher.set('items', [row for row in voucher.items if row.purchase_receipt_item in amounts])
    for row in voucher.items:
        row.applicable_charges = amounts[row.purchase_receipt_item]
    voucher.insert()
    voucher.submit()


def allocate_direct(doc, method=None):
    if not configured(doc) or doc.doctype == 'Purchase Invoice' and not doc.get('update_stock'):
        return
    accounts = total_accounts(doc)
    if not accounts:
        return
    # Valuation and Total has already been capitalized by core.
    native = costs(doc, category='Total')
    grouped = defaultdict(dict)
    for item in doc.items:
        if not capitalized(item):
            continue
        for account in accounts:
            amount = native.get((item.name, account), 0)
            if amount:
                grouped[(account, amount > 0)][item.name] = amount
    for (account, positive), amounts in grouped.items():
        create_allocation(doc, doc.doctype, doc.name, account, amounts,
                          doc.name if doc.doctype == 'Purchase Invoice' else None)
    if grouped:
        doc.reload()  # Core LCV updates this receipt/invoice; return its current version.


def cancel_adjustments(doc, method=None):
    if not configured(doc):
        return
    if doc.doctype == 'Purchase Invoice':
        lock_receipts(doc)
        names = frappe.get_all('Landed Cost Voucher', filters={SOURCE: doc.name, 'docstatus': 1},
                               order_by='creation desc', pluck='name')
    else:
        parents = frappe.get_all('Landed Cost Purchase Receipt', filters={
            'receipt_document_type': doc.doctype, 'receipt_document': doc.name, 'docstatus': 1}, pluck='parent')
        names = frappe.get_all('Landed Cost Voucher', filters={'name': ['in', parents],
            ALLOCATION: 1, SOURCE: ['is', 'not set'], 'docstatus': 1},
            order_by='creation desc', pluck='name') if parents else []
    for name in names:
        frappe.get_doc('Landed Cost Voucher', name).cancel()


def prepare_receipt_return(doc, method=None):
    """Use the actual bill treatment via the native invoice/row references."""
    if not configured(doc) or not doc.get('is_return') or not doc.get('return_against'):
        return
    from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION
    from erpnext_norway.vat import posted_update
    if posted_update(doc):
        return
    from erpnext_norway.vat_returns import apply_rates
    original = frappe.get_doc('Purchase Receipt', doc.return_against)
    original.check_permission('read')
    if original.company != doc.company or original.docstatus != 1:
        frappe.throw(frappe._('Keep the native submitted purchase receipt row reference.'))
    originals = {row.name: row for row in original.items}
    reserved = defaultdict(float)
    for item in doc.items:
        receipt_item = originals.get(item.purchase_receipt_item)
        if not receipt_item:
            frappe.throw(frappe._('Keep the native submitted purchase receipt row reference.'))
        item.is_fixed_asset = receipt_item.is_fixed_asset
        needed = abs(flt(item.qty) * flt(item.conversion_factor or 1))
        references = frappe.get_all('Purchase Invoice Item', filters={'pr_detail': receipt_item.name,
            'docstatus': 1}, fields=['name', 'parent'])
        if receipt_item.get('purchase_invoice') and receipt_item.get('purchase_invoice_item'):
            references.append(frappe._dict(name=receipt_item.purchase_invoice_item,
                                          parent=receipt_item.purchase_invoice))
        candidates = []
        seen = set()
        for reference in references:
            if reference.name in seen:
                continue
            seen.add(reference.name)
            invoice = frappe.get_doc('Purchase Invoice', reference.parent)
            if (invoice.is_return or invoice.docstatus != 1 or invoice.company != doc.company
                    or (item.get('purchase_invoice') and item.purchase_invoice != invoice.name)):
                continue
            source = next(row for row in invoice.items if row.name == reference.name)
            returns = frappe.get_all('Purchase Receipt Item', filters={'purchase_invoice_item': source.name,
                'docstatus': 1}, fields=['parent', 'stock_qty'])
            returned = sum(abs(flt(row.stock_qty)) for row in returns
                if frappe.db.get_value('Purchase Receipt', row.parent, 'is_return'))
            available = abs(flt(source.stock_qty)) - returned - reserved[source.name]
            if available + 0.000001 >= needed:
                candidates.append((invoice, source))
        if item.get('purchase_invoice_item'):
            candidates = [(invoice, source) for invoice, source in candidates if source.name == item.purchase_invoice_item]
        if not references:
            for field in (CODE, RATE, DEDUCTION):
                item.set(field, receipt_item.get(field))
            item.item_tax_template = receipt_item.item_tax_template
            apply_rates(doc, item, original, receipt_item)
            continue  # Unbilled return retains the issued receipt treatment.
        if len(candidates) != 1:
            frappe.throw(frappe._('Select the original purchase invoice and a quantity within its unreturned quantity.'))
        invoice, source = candidates[0]
        invoice.check_permission('read')
        if invoice.company != doc.company:
            frappe.throw(frappe._('Keep the native submitted purchase receipt row reference.'))
        reserved[source.name] += needed
        item.purchase_invoice = receipt_item.get('purchase_invoice') if item.is_fixed_asset else invoice.name
        item.purchase_invoice_item = source.name
        for field in (CODE, RATE, DEDUCTION):
            item.set(field, source.get(field))
        item.item_tax_template = source.item_tax_template
        source_keys = {basis_key(tax) for tax in invoice.taxes if tax.get(COST)}
        if any(basis_key(tax) not in source_keys
               for tax in doc.taxes if tax.get(COST)):
            frappe.throw(frappe._('Keep a matching native freight tax basis on the receipt return.'))
        for tax in invoice.taxes:
            if not tax.get(COST):
                continue
            if tax.charge_type.startswith('On Previous Row'):
                index = int(tax.row_id) - 1
                if index < 0 or index >= len(doc.taxes) or index >= len(invoice.taxes) or any(
                        doc.taxes[index].get(field) != invoice.taxes[index].get(field)
                        for field in ('account_head', 'charge_type')):
                    frappe.throw(frappe._('Keep a matching native freight tax basis on the receipt return.'))
                if tax.category != 'Total':
                    frappe.throw(frappe._('Receipt returns with VAT on freight require a qualified native allocation.'))
            if not any(row.account_head == tax.account_head and row.charge_type == tax.charge_type
                       and str(row.get('row_id') or '') == str(tax.get('row_id') or '') for row in doc.taxes):
                values = tax.as_dict()
                for field in ('name', 'parent', 'parenttype', 'parentfield', 'idx'):
                    values.pop(field, None)
                doc.append('taxes', values)
        apply_rates(doc, item, invoice, source)


def link_credit_receipts(doc, method=None):
    if not configured(doc) or not doc.get('is_return') or not doc.get('return_against'):
        return
    from erpnext_norway.vat import posted_update
    if posted_update(doc):
        return
    original = frappe.get_doc('Purchase Invoice', doc.return_against)
    originals = {row.name: row for row in original.items}
    for item in doc.items:
        source = originals.get(item.get('purchase_invoice_item'))
        if not source or not source.purchase_receipt or not capitalized(item):
            continue
        candidates = []
        for row in frappe.get_all('Purchase Receipt Item', filters={'purchase_receipt_item': source.pr_detail,
                'docstatus': 1}, fields=['name', 'parent', 'stock_qty', 'purchase_invoice_item']):
            receipt = frappe.get_doc('Purchase Receipt', row.parent)
            if not receipt.is_return or receipt.company != doc.company:
                continue
            if row.purchase_invoice_item and row.purchase_invoice_item != source.name:
                continue
            used = sum(abs(flt(value.stock_qty)) for value in frappe.get_all('Purchase Invoice Item',
                filters={'pr_detail': row.name, 'docstatus': 1}, fields=['stock_qty']))
            needed = abs(flt(item.qty) * flt(item.conversion_factor or 1))
            if abs(flt(row.stock_qty)) - used + 0.000001 >= needed:
                candidates.append(row)
        explicit_return = item.purchase_receipt and frappe.db.get_value('Purchase Receipt',
            item.purchase_receipt, 'is_return')
        if explicit_return:
            candidates = [row for row in candidates if row.parent == item.purchase_receipt]
        selected = next((row for row in candidates if row.name == item.pr_detail), None)
        if not selected and len(candidates) == 1 and (not explicit_return or not item.pr_detail):
            selected = candidates[0]
        if not selected:
            frappe.throw(frappe._('Select a matching submitted Purchase Receipt return before crediting received goods.'))
        item.purchase_receipt = selected.parent
        item.pr_detail = selected.name
