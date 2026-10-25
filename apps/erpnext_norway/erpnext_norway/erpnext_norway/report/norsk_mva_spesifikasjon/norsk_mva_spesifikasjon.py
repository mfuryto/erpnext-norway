"""A native Script Report over invoice/GL/Item Wise Tax Detail; no shadow ledger."""
from decimal import Decimal

import frappe
from frappe.utils import getdate
from erpnext_norway.vat_catalog import CODE, RATE, check_code
from erpnext_norway.vat import is_vat_account


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def collect(filters):
    filters = frappe._dict(filters or {})
    if not filters.company or not filters.from_date or not filters.to_date:
        frappe.throw(frappe._('Select Company, From Date and To Date.'))
    start, end = getdate(filters.from_date), getdate(filters.to_date)
    if start > end:
        frappe.throw(frappe._('From Date cannot be after To Date.'))
    company = frappe.get_doc('Company', filters.company)
    company.check_permission('read')
    if company.country != 'Norway' or company.default_currency != 'NOK':
        frappe.throw(frappe._('This Norwegian VAT report requires a Norwegian company with NOK accounting currency.'))
    result = []
    known = set()
    for doctype in ('Sales Invoice', 'Purchase Invoice'):
        frappe.has_permission(doctype, 'read', throw=True)
        dates = {'posting_date': ['between', [start, end]]}
        if doctype == 'Purchase Invoice':
            dates['bill_date'] = ['between', [start, end]]
        for invoice in frappe.get_list(doctype, filters={'company': company.name, 'docstatus': 1},
                or_filters=dates, fields=['name'], limit_page_length=0,
                order_by='posting_date, name'):
            doc = frappe.get_doc(doctype, invoice.name)
            known.add((doctype, doc.name))
            if doc.is_opening == 'Yes':
                continue
            vat_date = getdate((doc.get('bill_date') if doctype == 'Purchase Invoice' else None)
                               or doc.posting_date)
            if not start <= vat_date <= end:
                continue  # A documented timing difference, not an omitted GL source.
            if doctype == 'Purchase Invoice':
                from erpnext_norway.reverse_charge import guard_currency
                guard_currency(doc)
            tax_rows = {row.name: row for row in doc.taxes}
            details = frappe.get_all('Item Wise Tax Detail', filters={'parent': doc.name,
                'parenttype': doctype}, fields=['item_row', 'tax_row', 'amount', 'taxable_amount', 'rate'])
            vat_details = [row for row in details if row.tax_row in tax_rows
                and is_vat_account(tax_rows[row.tax_row].account_head)]
            doc_total = Decimal(0)
            for item in doc.items:
                if not item.get(CODE):
                    frappe.throw(frappe._('Norwegian VAT code is missing on invoice {0}, row {1}.').format(doc.name, item.idx))
                check_code(doc, item)
                rows = [row for row in vat_details if row.item_row == item.name]
                output, deduction = Decimal(0), Decimal(0)
                accounts = {}
                for row in rows:
                    tax = tax_rows[row.tax_row]
                    amount = money(row.amount)
                    if doctype == 'Sales Invoice':
                        output += amount
                        direction = 1
                    elif (frappe.get_cached_value('Account', tax.account_head,
                            'account_number') or '').startswith('270'):
                        # Purchase details are signed Add/Deduct amounts.
                        # Output VAT is the credit side, input VAT the debit side.
                        output -= amount
                        direction = -1
                    else:
                        deduction += amount
                        direction = -1
                    accounts[tax.account_head] = accounts.get(tax.account_head, Decimal(0)) + amount * direction
                liability = output - deduction
                doc_total += liability
                active = [row for row in rows if money(row.amount)]
                if active:
                    # Freight can have its own On Previous Row VAT in addition
                    # to the item's On Net Total VAT. Sum those native bases on
                    # one side only; reverse charge has output and input on the
                    # same base and must not double that base.
                    basis_account = next((tax_rows[row.tax_row].account_head for row in active
                        if (frappe.get_cached_value('Account', tax_rows[row.tax_row].account_head,
                            'account_number') or '').startswith('270')),
                        tax_rows[active[0].tax_row].account_head)
                    base = sum((money(item.base_net_amount) if not row.taxable_amount
                        and tax_rows[row.tax_row].charge_type == 'On Net Total'
                        else money(row.taxable_amount) * (-1 if doctype == 'Purchase Invoice' and
                            tax_rows[row.tax_row].get('add_deduct_tax') == 'Deduct' else 1) for row in active
                        if tax_rows[row.tax_row].account_head == basis_account), Decimal(0))
                else:
                    base = money(item.base_net_amount)
                    if doctype == 'Sales Invoice':
                        # Native non-VAT charges allocated to a zero-rated sale
                        # are still consideration; zero VAT is not zero freight.
                        base += sum((money(row.amount) for row in details
                            if row.item_row == item.name and row.tax_row in tax_rows
                            and not is_vat_account(tax_rows[row.tax_row].account_head)), Decimal(0))
                result.append({'posting_date': doc.posting_date, 'vat_date': vat_date, 'voucher_type': doctype,
                    'voucher': doc.name, 'line': item.idx, 'item_code': item.item_code,
                    'vat_code': item.get(CODE), 'vat_rate': item.get(RATE) or (active[0].rate if active else 0),
                    'base_amount': float(base), 'output_vat': float(output),
                    'input_vat': float(deduction), 'net_vat': float(liability),
                    'specification': '', 'specification_label': '',
                    'vat_accounts': {name: float(amount) for name, amount in accounts.items()},
                    'portal': item.get(CODE) not in {'0', '7', '20', '21', '22'}})
            ledger = frappe.get_all('GL Entry', filters={'company': company.name,
                'voucher_type': doctype, 'voucher_no': doc.name, 'is_cancelled': 0},
                fields=['account', 'debit', 'credit'])
            actual = sum((money(row.credit) - money(row.debit) for row in ledger
                          if is_vat_account(row.account)), Decimal(0))
            if actual != doc_total:
                frappe.throw(frappe._('VAT details do not reconcile with the ledger for invoice {0}.').format(doc.name))
    from erpnext_norway.vat_journal import ACCOUNTS, BASE, SPEC, SETTLEMENT
    frappe.has_permission('Journal Entry', 'read', throw=True)
    for journal in frappe.get_list('Journal Entry', filters={'company': company.name, 'docstatus': 1,
            'posting_date': ['between', [start, end]]}, fields=['name'], limit_page_length=0):
        doc = frappe.get_doc('Journal Entry', journal.name)
        known.add(('Journal Entry', doc.name))
        if doc.is_opening == 'Yes' or doc.get(SETTLEMENT):
            continue
        expected = Decimal(0)
        for item in doc.accounts:
            if not is_vat_account(item.account):
                continue
            account_number = frappe.get_cached_value('Account', item.account, 'account_number') or ''
            code = item.get(CODE)
            if account_number not in ACCOUNTS.get(code, ()):
                frappe.throw(frappe._('Select a Norwegian VAT code on each journal VAT line before submission.'))
            amount = money(item.credit) - money(item.debit)
            expected += amount
            output = amount if account_number.startswith('270') else Decimal(0)
            deduction = -amount if account_number.startswith('271') else Decimal(0)
            if output and not item.get(BASE):
                frappe.throw(frappe._('Enter the documented VAT base on journal {0}, row {1}.').format(doc.name, item.idx))
            result.append({'posting_date': doc.posting_date, 'vat_date': doc.posting_date, 'voucher_type': 'Journal Entry',
                'voucher': doc.name, 'line': item.idx, 'item_code': None,
                'vat_code': code, 'vat_rate': item.get(RATE), 'base_amount': float(money(item.get(BASE))),
                'output_vat': float(output), 'input_vat': float(deduction), 'net_vat': float(amount),
                'vat_accounts': {item.account: float(amount)},
                'portal': True, 'specification': item.get(SPEC) or '',
                'specification_label': frappe._(item.get(SPEC)) if item.get(SPEC) else ''})
        actual = sum((money(row.credit) - money(row.debit) for row in frappe.get_all('GL Entry',
            filters={'company': company.name, 'voucher_type': 'Journal Entry', 'voucher_no': doc.name,
                     'is_cancelled': 0}, fields=['account', 'debit', 'credit']) if is_vat_account(row.account)), Decimal(0))
        if actual != expected:
            frappe.throw(frappe._('VAT details do not reconcile with the ledger for invoice {0}.').format(doc.name))
    for row in frappe.get_all('GL Entry', filters={'company': company.name, 'is_cancelled': 0,
            'posting_date': ['between', [start, end]], 'is_opening': ['!=', 'Yes']},
            fields=['account', 'voucher_type', 'voucher_no', 'debit', 'credit']):
        if is_vat_account(row.account) and (money(row.debit) or money(row.credit)):
            if (row.voucher_type, row.voucher_no) not in known:
                frappe.throw(frappe._('VAT posting {0} {1} has no supported classification in the report.').format(
                    row.voucher_type, row.voucher_no))
    return result


def execute(filters=None):
    columns = [
        {'fieldname': 'posting_date', 'label': frappe._('Posting Date'), 'fieldtype': 'Date', 'width': 110},
        {'fieldname': 'vat_date', 'label': frappe._('VAT period date'), 'fieldtype': 'Date', 'width': 110},
        {'fieldname': 'voucher_type', 'label': frappe._('Voucher Type'), 'fieldtype': 'Link', 'options': 'DocType', 'width': 130},
        {'fieldname': 'voucher', 'label': frappe._('Voucher No'), 'fieldtype': 'Dynamic Link', 'options': 'voucher_type', 'width': 130},
        {'fieldname': 'line', 'label': frappe._('Row'), 'fieldtype': 'Int', 'width': 50},
        {'fieldname': 'item_code', 'label': frappe._('Item Code'), 'fieldtype': 'Link', 'options': 'Item', 'width': 140},
        {'fieldname': 'vat_code', 'label': frappe._('Norwegian VAT code'), 'fieldtype': 'Data', 'width': 90},
        {'fieldname': 'specification_label', 'label': frappe._('VAT specification'), 'fieldtype': 'Data', 'width': 160},
        {'fieldname': 'vat_rate', 'label': frappe._('Norwegian VAT rate'), 'fieldtype': 'Float', 'width': 90},
        *[{'fieldname': key, 'label': frappe._(label), 'fieldtype': 'Currency', 'options': 'NOK', 'width': 125}
          for key, label in [('base_amount', 'VAT base'), ('output_vat', 'Output VAT'),
                            ('input_vat', 'Input VAT'), ('net_vat', 'VAT payable or refundable')]],
        {'fieldname': 'portal', 'label': frappe._('Included in VAT return'), 'fieldtype': 'Check', 'width': 90},
    ]
    data = collect(filters)
    if (filters or {}).get('group_by_code', 1):
        grouped = {}
        for row in data:
            code = row['vat_code']
            key = (code, row.get('specification') or '')
            if key not in grouped:
                grouped[key] = {'vat_code': code, 'portal': row['portal'],
                    'specification': row.get('specification'), 'specification_label': row.get('specification_label'),
                    'vat_rate': row['vat_rate'] if code in {'3', '31', '33'} else None,
                    'base_amount': 0, 'output_vat': 0, 'input_vat': 0, 'net_vat': 0}
            for key in ('base_amount', 'output_vat', 'input_vat', 'net_vat'):
                grouped[(code, row.get('specification') or '')][key] = float(
                    money(grouped[(code, row.get('specification') or '')][key]) + money(row[key]))
        data = [grouped[key] for key in sorted(grouped, key=lambda value: (int(value[0]), value[1]))]
        for row in data:
            if row['vat_code'] in {'1', '11', '13', '14', '15'}:
                row['base_amount'] = None  # The VAT return has no base/rate for input VAT.
        columns = [col for col in columns if col['fieldname'] not in
                   {'posting_date', 'vat_date', 'voucher_type', 'voucher', 'line', 'item_code'}]
    summary = [{'value': float(sum((money(row[key]) for row in data), Decimal(0))),
                'label': frappe._(label), 'datatype': 'Currency', 'currency': 'NOK'}
               for key, label in [('output_vat', 'Output VAT'), ('input_vat', 'Input VAT'),
                                  ('net_vat', 'VAT payable or refundable')]]
    return columns, data, None, None, summary
