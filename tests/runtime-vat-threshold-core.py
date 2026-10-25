"""Qualify native withholding reuse; this is not Norwegian VAT treatment.

Actual submitted invoices and native history, with no mocks or forced entries.
Everything is rolled back: the withholding configuration must never be seeded.
"""
import os
import frappe
from erpnext_norway.vat_catalog import CODE

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')

try:
    company = frappe.get_doc('Company', 'Runtime Reverse Services')
    accounts = {r.account_number: r.name for r in frappe.get_all('Account',
        filters={'company': company.name}, fields=['name', 'account_number'])}
    category = frappe.get_doc({'doctype': 'Tax Withholding Category',
        'name': 'Runtime native threshold qualification',
        'category_name': 'Runtime native threshold qualification',
        'tax_deduction_basis': 'Net Total', 'disable_transaction_threshold': 1,
        'rates': [{'from_date': '2026-07-01', 'to_date': '2026-09-30',
            'tax_withholding_rate': 25, 'cumulative_threshold': 2000}],
        'accounts': [{'company': company.name, 'account': accounts['2960']}],
    }).insert()
    # A neutral category satisfies the app's explicit-treatment guard without
    # classifying withholding as Norwegian VAT or touching an output VAT account.
    treatment = frappe.get_doc({'doctype': 'Tax Category',
        'title': 'Runtime withholding qualification only'}).insert()
    suppliers = [frappe.get_doc({'doctype': 'Supplier',
        'supplier_name': f'Runtime threshold supplier {suffix}',
        'supplier_group': frappe.get_all('Supplier Group', filters={'is_group': 0}, pluck='name')[0],
        'supplier_type': 'Company', 'tax_withholding_category': category.name,
    }).insert().name for suffix in ('A', 'B')]

    def invoice(supplier, amount):
        doc = frappe.get_doc({'doctype': 'Purchase Invoice', 'company': company.name,
            'supplier': supplier, 'posting_date': '2026-08-10', 'set_posting_time': 1,
            'bill_date': '2026-08-10', 'bill_no': 'SYNTHETIC-THRESHOLD',
            'due_date': '2026-09-30', 'currency': 'NOK', 'conversion_rate': 1,
            'disable_rounded_total': 1, 'apply_tds': 1, 'tax_category': treatment.name,
            'items': [{'item_code': 'RUNTIME-VAT-SERVICE', 'qty': 1, 'rate': amount,
                'expense_account': accounts['4500'], 'cost_center': company.cost_center,
                CODE: '0',
                'apply_tds': 1, 'tax_withholding_category': category.name}],
        }).insert()
        doc.submit()
        return doc

    def withheld(doc):
        return round(sum(row.base_tax_amount for row in doc.taxes
            if row.is_tax_withholding_account), 2)

    first = invoice(suppliers[0], 1500)
    other = invoice(suppliers[1], 600)
    assert withheld(first) == withheld(other) == 0
    assert first.base_net_total + other.base_net_total == 2100
    print('PASS native withholding remains zero across distinct suppliers at company total 2100: not company-wide Norwegian VAT')
    boundary = invoice(suppliers[0], 500)
    assert withheld(boundary) == 500, withheld(boundary)
    assert boundary.grand_total == 0, boundary.grand_total
    print('PASS native withholding triggers at exactly 2000 for one supplier and deducts from supplier payable: not Norwegian reverse VAT')
    # Actual native credit after threshold passage: history remains settled,
    # so it cannot be reused as a company-wide quarterly VAT decision.
    from erpnext.controllers.sales_and_purchase_return import make_return_doc
    credit = make_return_doc('Purchase Invoice', first.name)
    credit.posting_date = '2026-08-11'; credit.set_posting_time = 1
    credit.bill_date = '2026-08-11'; credit.bill_no = 'SYNTHETIC-THRESHOLD-CREDIT'
    credit.insert(); credit.submit()
    assert withheld(credit) == -375 and credit.grand_total == -1125
    later = invoice(suppliers[0], 100)
    assert withheld(later) == 25 and later.grand_total == 75
    # Native source base after the full first-invoice credit: A600 + B600.
    assert sum(doc.base_net_total for doc in (first, other, boundary, credit, later)) == 1200
    assert first.reload().grand_total == 1500  # No rewrite of original.
    print('PASS native full credit leaves company base1200, but settled withholding history still deducts25 from next100: not a Norwegian quarterly decision')
finally:
    frappe.db.rollback()
    frappe.destroy()
