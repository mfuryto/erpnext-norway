"""Native NB/EN sales documents, PDF evidence and exported restore; synthetic only."""
import hashlib
import io
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
from pypdf import PdfReader
from frappe.translate import print_language
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext_norway.printing import configure


def text(content):
    return '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)


def originals(doc):
    return frappe.get_all('File', filters={'attached_to_doctype': doc.doctype,
        'attached_to_name': doc.name, 'is_private': 1}, fields=['name', 'file_url', 'file_name'])


try:
    if sys.argv[1] == 'verify':
        evidence = json.loads(frappe.db.get_default('runtime_language_pdfs'))
        for row in evidence:
            file = frappe.get_doc('File', row['file'])
            content = Path(file.get_full_path()).read_bytes()
            assert hashlib.sha256(content).hexdigest() == row['sha256']
            assert row['heading'] in text(content)
            try:
                file.delete()
            except frappe.ValidationError:
                pass
            else:
                raise AssertionError('Restored original could be deleted')
        assert frappe._('Purchase Invoice', lang='nb') == 'Leverandørfaktura'
        assert frappe._('Posting Date', lang='nb', context='Sales Invoice') == 'Bokføringsdato'
        print('PASS NB catalog precedence and six protected PDF originals after exported restore/migrate')
    else:
        from frappe.utils.password import update_password
        manager = frappe.get_doc({'doctype': 'User', 'email': 'runtime-ui-manager@example.invalid',
            'first_name': 'UI', 'user_type': 'System User', 'language': 'nb', 'send_welcome_email': 0,
            'roles': [{'role': role} for role in ['System Manager', 'Accounts Manager',
                'Stock Manager', 'Item Manager', 'Sales Master Manager', 'Purchase Master Manager']]}).insert()
        update_password(manager.name, 'Synthetic-ui-manager-only-2026!')
        # CSS/assets use the synthetic Compose frontend, never a public hostname.
        frappe.conf.host_name = 'http://frontend:8080'
        company = frappe.get_doc('Company', 'Runtime Norwegian Example')
        company.tax_id = '999999999'  # Synthetic identifier, deliberately no MVA suffix.
        company.save()
        address = frappe.get_doc({'doctype': 'Address', 'address_title': 'Synthetic seller',
            'address_type': 'Billing', 'address_line1': 'Example street 1', 'city': 'Oslo',
            'pincode': '0001', 'country': 'Norway', 'is_your_company_address': 1,
            'links': [{'link_doctype': 'Company', 'link_name': company.name}]}).insert()
        bank = frappe.get_doc('Bank Account', {'company': company.name})
        bank.is_default = 1
        bank.bank_account_no = '00000000000'
        bank.iban = f"NO{98 - int('00000000000' + '232400') % 97:02d}00000000000"
        bank.save()
        customer = frappe.get_doc('Customer', {'customer_name': 'Runtime Norwegian Customer'})
        owner = frappe.get_doc('User', 'runtime-owner@example.invalid')
        owner.language = 'nb'
        owner.save()
        from frappe.utils.password import update_password
        update_password(owner.name, 'Synthetic-owner-runtime-only-2026!')
        customer.language = 'nb'
        customer.save()
        bill_to = frappe.get_doc({'doctype': 'Address', 'address_title': 'Synthetic buyer',
            'address_type': 'Billing', 'address_line1': 'Example street 2', 'city': 'Bergen',
            'pincode': '5000', 'country': 'Norway', 'is_primary_address': 1,
            'links': [{'link_doctype': 'Customer', 'link_name': customer.name}]}).insert()
        source = frappe.get_doc('Sales Invoice', {'company': company.name, 'is_return': 0, 'docstatus': 1})
        evidence = []
        frappe.set_user('runtime-owner@example.invalid')
        for language, headings in [('nb', ['Tilbud', 'Salgsfaktura', 'Kreditnota']),
                                    ('en', ['Quotation', 'Sales Invoice', 'Credit Note'])]:
            quote = frappe.get_doc({'doctype': 'Quotation', 'quotation_to': 'Customer',
                'party_name': customer.name, 'company': company.name, 'language': language,
                'transaction_date': '2026-10-18', 'valid_till': '2026-11-18',
                'company_address': address.name, 'customer_address': bill_to.name,
                'items': [{'item_code': 'RUNTIME-NO-SERVICE', 'qty': 2, 'rate': 500}]}).insert()
            assert quote.language == language, (quote.language, language)
            quote.submit()
            sale = frappe.copy_doc(source)
            sale.language = language
            sale.company_address = address.name
            sale.customer_address = bill_to.name
            sale.items[0].qty = 2
            sale.items[0].rate = 500
            sale.apply_discount_on = 'Grand Total'
            sale.discount_amount = 100
            sale.insert()
            sale.submit()
            assert float(sale.grand_total) == 900
            credit = make_sales_return(sale.name)
            credit.update_outstanding_for_self = 0
            credit.posting_date = sale.posting_date
            credit.set_posting_time = 1
            credit.language = language
            credit.insert()
            credit.submit()
            assert float(credit.grand_total) == -900
            for doc, heading in zip([quote, sale, credit], headings):
                files = originals(doc)
                assert len(files) == 1, files
                file = frappe.get_doc('File', files[0].name)
                content = Path(file.get_full_path()).read_bytes()
                extracted = text(content)
                assert heading in extracted, extracted
                assert ' '.join(doc.get_formatted('grand_total').split()) in ' '.join(extracted.split()), extracted
                assert doc.items[0].item_name in extracted, extracted
                assert doc.name in extracted and '999999999' in extracted, extracted
                assert 'Example street 1' in extracted and 'Example street 2' in extracted, extracted
                assert 'MVA' not in extracted, extracted
                assert '00000000000' in extracted, extracted
                assert ('Organisasjonsnummer' if language == 'nb' else 'Organisation number') in extracted, extracted
                assert ('Beskrivelse' if language == 'nb' else 'Description') in extracted, extracted
                if language == 'nb':
                    for unwanted in ['Description', 'Grand Total', 'Quantity', 'Sales Invoice', 'Credit Note', 'Quotation']:
                        assert unwanted not in extracted, (unwanted, extracted)
                if doc.get('is_return'):
                    assert sale.name in extracted
                    assert ('Opprinnelig faktura' if language == 'nb' else 'Original invoice') in extracted
                evidence.append({'file': file.name, 'url': file.file_url, 'doctype': doc.doctype,
                    'name': doc.name, 'heading': heading, 'sha256': hashlib.sha256(content).hexdigest()})
                # A later preview can use the other language without modifying the saved original.
                with print_language('en' if language == 'nb' else 'nb'):
                    preview = frappe.get_print(doc.doctype, doc.name)
                    assert ('Description' if language == 'nb' else 'Beskrivelse') in preview
                assert frappe.local.lang == 'nb'
                assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest() == evidence[-1]['sha256']
            from frappe.model.rename_doc import rename_doc
            try:
                rename_doc('Quotation', quote.name, 'SYNTHETIC-RENAMED-QUOTE', force=True)
            except frappe.ValidationError:
                pass
            else:
                raise AssertionError('Submitted quotation number could be changed')
            # Submitted and cancelled quotations preserve the original too.
            if language == 'nb':
                quote.cancel()
            for action in [lambda: quote.delete(), lambda: frappe.get_doc('File', originals(quote)[0].name).delete()]:
                try:
                    action()
                except frappe.ValidationError:
                    pass
                else:
                    raise AssertionError('Cancelled quotation/original could be deleted')
        # A rendering error cannot leave a posted invoice without its PDF.
        from unittest.mock import patch
        frappe.db.savepoint('pdf_failure_fixture')
        failing = frappe.copy_doc(source).insert()
        frappe.db.savepoint('before_failed_submission')
        with patch('frappe.get_print', side_effect=RuntimeError('Synthetic renderer failure')):
            try:
                failing.submit()
            except RuntimeError as error:
                assert str(error) == 'Synthetic renderer failure'
                frappe.db.rollback(save_point='before_failed_submission')
            else:
                raise AssertionError('Submission ignored PDF failure')
        assert frappe.db.get_value('Sales Invoice', failing.name, 'docstatus') == 0
        assert not frappe.db.exists('GL Entry', {'voucher_type': failing.doctype, 'voucher_no': failing.name})
        assert not originals(failing)
        frappe.db.rollback(save_point='pdf_failure_fixture')
        frappe.set_user('Administrator')
        # Native format choices and site-edited templates survive repeated setup/migration.
        format_doc = frappe.get_doc('Print Format', 'Norway Invoice')
        original_html = format_doc.html
        format_doc.html += '\n<!-- site customization -->'
        format_doc.save()
        configure()
        assert frappe.get_doc('Print Format', format_doc.name).html == original_html + '\n<!-- site customization -->'
        format_doc.html = original_html
        format_doc.save()
        from frappe.custom.doctype.property_setter.property_setter import make_property_setter
        make_property_setter('Sales Invoice', None, 'default_print_format', 'Standard', 'Data', for_doctype=True)
        configure()
        assert frappe.get_meta('Sales Invoice').default_print_format == 'Standard'
        make_property_setter('Sales Invoice', None, 'default_print_format', 'Norway Invoice', 'Data', for_doctype=True)

        company.tax_id = '888888888'
        company.save()
        for row in evidence:
            file = frappe.get_doc('File', row['file'])
            content = Path(file.get_full_path()).read_bytes()
            assert hashlib.sha256(content).hexdigest() == row['sha256']
            assert '999999999' in text(content) and '888888888' not in text(content)
        # Real UI translations, including contexts used by form metadata, are loaded after core catalogs.
        for original, translated, context in [
            ('Purchase Invoice', 'Leverandørfaktura', None), ('Journal Entry', 'Bokføringsbilag', None),
            ('Payment Entry', 'Betalingsregistrering', None), ('Banking', 'Bank', None),
            ('Posting Date', 'Bokføringsdato', 'Sales Invoice'), ('Print Language', 'Dokumentspråk', 'Quotation')]:
            assert frappe._(original, lang='nb', context=context) == translated
        frappe.db.set_default('runtime_language_pdfs', json.dumps(evidence))
        frappe.db.set_default('runtime_app_counter', frappe.db.get_value('Document Naming Rule', 'Norway Sales Invoice', 'counter'))
        frappe.db.commit()
        print('PASS ordinary owner NB/EN quotation, invoice/discount/credit PDF; native amounts, addresses, organisation ID, bank and original reference; protected originals survive later changes')
finally:
    frappe.destroy()
