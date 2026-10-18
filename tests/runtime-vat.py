"""Native registration transition, owner invoices and historical evidence; synthetic only."""
import hashlib
import json
import os
from pathlib import Path
import sys

import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.local.lang = 'nb'
frappe.conf.host_name = 'http://frontend:8080'
from erpnext_norway import vat
from erpnext.accounts.party import set_taxes
from erpnext.controllers.accounts_controller import get_taxes_and_charges
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

COMPANY = 'Runtime VAT Example'
BEFORE, FROM, AFTER = '2026-10-14', '2026-10-15', '2026-10-16'


def equal(actual, expected):
    assert round(float(actual or 0), 2) == expected, (actual, expected)


def ledger(doc, expected, accounts):
    rows = frappe.get_all('GL Entry', filters={'voucher_type': doc.doctype, 'voucher_no': doc.name,
        'company': COMPANY, 'is_cancelled': 0}, fields=['account', 'debit', 'credit'])
    equal(sum(r.debit - r.credit for r in rows), 0)
    for code, amount in expected.items():
        equal(sum(r.debit - r.credit for r in rows if r.account == accounts[code]), amount)


def rejected(action, message):
    frappe.db.savepoint('vat_rejection')
    try:
        action()
    except (frappe.ValidationError, frappe.MandatoryError) as error:
        assert message in str(error), (message, str(error))
        frappe.db.rollback(save_point='vat_rejection')
    else:
        raise AssertionError('Invalid VAT transition/invoice was accepted')


def submit_purchase(doc):
    # Test-only stand-in for an uploaded supplier original, not a product renderer.
    from frappe.utils.file_manager import save_file
    content = frappe.get_print(doc.doctype, doc.name, as_pdf=True)
    save_file('synthetic-supplier-original.pdf', content, doc.doctype, doc.name, is_private=1)
    doc.submit()


def fingerprint(doc):
    row = frappe.get_all('File', filters={'attached_to_doctype': doc.doctype,
        'attached_to_name': doc.name, 'is_private': 1}, pluck='name')[0]
    file = frappe.get_doc('File', row)
    return {'doctype': doc.doctype, 'name': doc.name, 'file': row,
        'sha256': hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest(),
        'total': float(doc.grand_total), 'tax': float(doc.total_taxes_and_charges),
        'tax_id': doc.get('company_tax_id')}


try:
    if sys.argv[1] == 'verify':
        evidence = json.loads(frappe.db.get_default('runtime_vat_evidence'))
        for row in evidence:
            doc = frappe.get_doc(row['doctype'], row['name'])
            file = frappe.get_doc('File', row['file'])
            assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest() == row['sha256']
            equal(doc.grand_total, row['total'])
            equal(doc.total_taxes_and_charges, row['tax'])
            assert doc.get('company_tax_id') == row['tax_id']
        company = frappe.get_doc('Company', COMPANY)
        assert company.get(vat.STATUS) == 'Registered' and str(company.get(vat.FROM)) == FROM
        assert not frappe.db.exists('Sales Taxes and Charges Template', {'company': COMPANY, 'is_default': 1})
        print('PASS VAT registration, native dated rules, posted values and PDF originals after exported restore/migrate')
    else:
        from erpnext_norway.printing import configure as configure_printing
        format_doc = frappe.get_doc('Print Format', 'Norway Invoice')
        current_html = format_doc.html
        assert 'translated_taxes(doc.taxes)' in current_html
        format_doc.html = current_html.replace('translated_taxes(doc.taxes)', 'doc.taxes')
        format_doc.save()
        configure_printing()
        assert frappe.get_doc('Print Format', 'Norway Invoice').html == current_html
        make_property_setter('Sales Invoice', None, 'default_print_format', 'Norway Invoice', 'Data', for_doctype=True)
        company = frappe.get_doc({'doctype': 'Company', 'company_name': COMPANY, 'abbr': 'RVE',
            'country': 'Norway', 'default_currency': 'NOK', 'tax_id': '999999999',
            'create_chart_of_accounts_based_on': 'Standard Template',
            'enable_perpetual_inventory': 0, vat.STATUS: 'Not registered'}).insert()
        accounts = {r.account_number: r.name for r in frappe.get_all('Account',
            filters={'company': COMPANY}, fields=['name', 'account_number']) if r.account_number}
        assert company.chart_of_accounts == 'Norsk kontoplan'
        assert not frappe.db.exists('Sales Taxes and Charges Template', {'company': COMPANY, 'is_default': 1})
        assert not frappe.db.exists('Purchase Taxes and Charges Template', {'company': COMPANY, 'is_default': 1})
        customer = frappe.get_all('Customer', pluck='name')[0]
        supplier = frappe.get_all('Supplier', pluck='name')[0]
        item = frappe.get_doc({'doctype': 'Item', 'item_code': 'RUNTIME-VAT-SERVICE',
            'item_name': 'Synthetic VAT service', 'item_group': 'Services', 'stock_uom': 'Nos',
            'is_stock_item': 0, 'item_defaults': [{'company': COMPANY,
                'income_account': accounts['3020'], 'expense_account': accounts['4500']}]}).insert()
        user = frappe.get_doc({'doctype': 'User', 'email': 'runtime-vat-owner@example.invalid',
            'first_name': 'VAT owner', 'language': 'nb', 'user_type': 'System User', 'send_welcome_email': 0,
            'roles': [{'role': role} for role in ['Accounts Manager', 'Sales Manager', 'Purchase Manager', 'Stock Manager']]}).insert()
        frappe.get_doc({'doctype': 'User Permission', 'user': user.name, 'allow': 'Company',
            'for_value': COMPANY, 'apply_to_all_doctypes': 1}).insert()
        from frappe.utils.password import update_password
        update_password(user.name, 'Synthetic-vat-owner-only-2026!')
        frappe.defaults.set_user_default('company', COMPANY, user=user.name)
        frappe.set_user(user.name)
        assert not frappe.has_permission('System Settings', 'write')
        base = {'company': COMPANY, 'currency': 'NOK', 'conversion_rate': 1, 'language': 'nb',
            'set_posting_time': 1, 'disable_rounded_total': 1, 'cost_center': company.cost_center,
            'due_date': '2026-10-31'}
        def invoice(kind, date=BEFORE, amount=1000, **extra):
            # This is the same native endpoint the form calls when selecting a template.
            if extra.get('taxes_and_charges') and 'taxes' not in extra:
                master = 'Sales' if kind == 'Sales Invoice' else 'Purchase'
                extra['taxes'] = get_taxes_and_charges(master + ' Taxes and Charges Template', extra['taxes_and_charges'])
            return frappe.get_doc({**base, 'doctype': kind, 'posting_date': date,
                **({'customer': customer} if kind == 'Sales Invoice' else {
                    'supplier': supplier, 'bill_date': date, 'bill_no': 'SYNTHETIC-VAT-' + frappe.generate_hash(length=8)}),
                'items': [{'item_code': item.name, 'qty': 1, 'rate': amount}], **extra})
        def tax(code, rate=25, deduct='Add'):
            return {'charge_type': 'On Net Total', 'account_head': accounts[code], 'rate': rate,
                'description': 'Synthetic VAT', 'category': 'Total', 'add_deduct_tax': deduct,
                'cost_center': company.cost_center}
        sale_before = invoice('Sales Invoice').insert()
        sale_before.submit()
        equal(sale_before.grand_total, 1000)
        ledger(sale_before, {'1500': 1000, '3020': -1000, '2700': 0}, accounts)
        assert sale_before.company_tax_id == '999999999'
        evidence = [fingerprint(sale_before)]
        rejected(lambda: invoice('Sales Invoice', taxes=[tax('2700')]).insert(), 'godkjent registrering')
        rejected(lambda: invoice('Purchase Invoice', taxes=[tax('2710')]).insert(), 'godkjent registrering')
        # A negative Deduct row must not bypass the input-VAT guard.
        rejected(lambda: invoice('Purchase Invoice', taxes=[tax('2710', -25, 'Deduct')]).insert(), 'godkjent registrering')
        purchase_before = invoice('Purchase Invoice', amount=500).insert()
        submit_purchase(purchase_before)
        ledger(purchase_before, {'2400': -500, '4500': 500, '2710': 0}, accounts)
        evidence.append(fingerprint(purchase_before))
        reverse = invoice('Purchase Invoice', amount=3000, taxes=[tax('4500'), tax('2704', 25, 'Deduct')]).insert()
        submit_purchase(reverse)
        equal(reverse.grand_total, 3000)
        ledger(reverse, {'2400': -3000, '4500': 3750, '2704': -750, '2710': 0}, accounts)
        evidence.append(fingerprint(reverse))
        payment = get_payment_entry('Purchase Invoice', purchase_before.name, bank_account=accounts['1920'])
        payment.reference_no = 'SYNTHETIC-VAT-PAYMENT'
        payment.reference_date = payment.posting_date = AFTER
        payment.insert()
        payment.submit()
        ledger(payment, {'2400': 500, '1920': -500, '2710': 0, '2700': 0}, accounts)
        purchase_before.reload()
        equal(purchase_before.outstanding_amount, 0)

        # Unknown status never becomes approved through invoicing or migration.
        company.set(vat.STATUS, 'Not configured')
        company.save()
        unknown = invoice('Sales Invoice').insert()
        rejected(unknown.submit, 'Angi MVA-registrering')
        company.set(vat.STATUS, 'Registered')
        rejected(company.save, 'virkningsdato')
        company.reload()
        company.set(vat.STATUS, 'Registered')
        company.set(vat.FROM, '2026-12-01')
        company.save()
        assert not vat.effective(company, AFTER)
        assert not set_taxes(customer, 'Customer', AFTER, COMPANY, tax_category=vat.CATEGORY)
        rejected(lambda: invoice('Sales Invoice', date=AFTER, taxes=[tax('2700')]).insert(), 'godkjent registrering')
        # Approved registration may be entered later with the effective date from the decision.
        company.set(vat.FROM, FROM)
        company.save()
        assert vat.effective(company, AFTER)
        copied = frappe.copy_doc(company, ignore_no_copy=False)
        assert frappe.get_meta('Company').get_field(vat.STATUS).no_copy
        assert frappe.get_meta('Company').get_field(vat.FROM).no_copy
        assert not copied.get(vat.FROM) and copied.get(vat.STATUS) != 'Registered'
        # A corrected effective date must not restamp an issued untaxed invoice.
        company.set(vat.FROM, BEFORE)
        company.save()
        sale_before.reload()
        sale_before.po_no = 'SYNTHETIC-REFERENCE-ADDED'
        sale_before.save()  # Existing native allow_on_submit field; no tax reinterpretation.
        assert sale_before.company_tax_id == '999999999'
        equal(sale_before.total_taxes_and_charges, 0)
        company.set(vat.FROM, FROM)
        company.save()

        assert not set_taxes(customer, 'Customer', BEFORE, COMPANY, tax_category=vat.CATEGORY)
        sale_template = set_taxes(customer, 'Customer', AFTER, COMPANY, tax_category=vat.CATEGORY)
        purchase_template = set_taxes(supplier, 'Supplier', AFTER, COMPANY, tax_category=vat.CATEGORY)
        assert sale_template and purchase_template
        sale = invoice('Sales Invoice', date=AFTER, tax_category=vat.CATEGORY,
            taxes_and_charges=sale_template).insert()
        sale.submit()
        equal(sale.grand_total, 1250)
        ledger(sale, {'1500': 1250, '3020': -1000, '2700': -250}, accounts)
        assert sale.company_tax_id == '999999999 MVA'
        evidence.append(fingerprint(sale))
        from frappe.translate import print_language
        for language, label in [('nb', 'MVA 25 %'), ('en', 'VAT 25 %')]:
            with print_language(language):
                preview = frappe.get_print('Sales Invoice', sale.name, 'Norway Invoice')
                assert label in preview, (language, preview)
        assert sale.taxes[0].description == 'MVA 25 %'  # No persisted row rewrite.

        purchase = invoice('Purchase Invoice', date=AFTER, amount=400, tax_category=vat.CATEGORY,
            taxes_and_charges=purchase_template).insert()
        submit_purchase(purchase)
        equal(purchase.grand_total, 500)
        ledger(purchase, {'2400': -500, '4500': 400, '2710': 100}, accounts)
        evidence.append(fingerprint(purchase))
        # Posting an older supplier invoice later does not automatically authorize retrospective deduction.
        rejected(lambda: invoice('Purchase Invoice', date=AFTER, bill_date=BEFORE,
            tax_category=vat.CATEGORY, taxes_and_charges=purchase_template).insert(), 'godkjent registrering')
        if not frappe.db.get_single_value('Accounts Settings', 'add_taxes_from_taxes_and_charges_template'):
            incomplete = invoice('Sales Invoice', date=AFTER, taxes_and_charges=sale_template, taxes=[]).insert()
            rejected(incomplete.submit, 'Ingen gyldig MVA-mal')
        tampered = make_sales_return(sale_before.name)
        tampered.posting_date = AFTER
        tampered.items[0].rate = 500
        tampered.append('taxes', tax('2700'))
        rejected(tampered.save, 'Behold originalfakturaens MVA-behandling')
        for original in [sale_before, sale]:
            credit = make_sales_return(original.name)
            credit.posting_date = AFTER
            credit.update_outstanding_for_self = 0
            credit.save()
            credit.submit()
            assert credit.company_tax_id == original.company_tax_id
            equal(credit.total_taxes_and_charges, -original.total_taxes_and_charges)
            evidence.append(fingerprint(credit))
        purchase_credit = make_return_doc('Purchase Invoice', purchase.name)
        purchase_credit.posting_date = AFTER
        purchase_credit.bill_no = 'SYNTHETIC-VAT-CREDIT'
        purchase_credit.update_outstanding_for_self = 0
        purchase_credit.save()
        submit_purchase(purchase_credit)
        ledger(purchase_credit, {'2400': 500, '4500': -400, '2710': -100}, accounts)
        evidence.append(fingerprint(purchase_credit))
        # Original values/PDF bytes did not change when the company registered.
        for row in evidence[:3]:
            doc = frappe.get_doc(row['doctype'], row['name'])
            equal(doc.grand_total, row['total'])
            equal(doc.total_taxes_and_charges, row['tax'])
            file = frappe.get_doc('File', row['file'])
            assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest() == row['sha256']
        frappe.set_user('Administrator')
        frappe.db.set_default('runtime_vat_evidence', json.dumps(evidence))
        if frappe.db.exists('Document Naming Rule', 'Norway Sales Invoice'):
            frappe.db.set_default('runtime_app_counter', frappe.db.get_value('Document Naming Rule', 'Norway Sales Invoice', 'counter'))
        frappe.db.commit()
        print('PASS ordinary owner: non-registration, confirmed future/effective date, dated native sales/input VAT, credit notes, blocked early deduction and unchanged originals')
finally:
    frappe.destroy()
