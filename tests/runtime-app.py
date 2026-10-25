"""Exercise native accounting preservation after a real external-app install."""
import os
from pathlib import Path
import sys

import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
if 'erpnext_norway' in frappe.get_installed_apps():
    frappe.conf.host_name = 'http://frontend:8080'
frappe.set_user('Administrator')
frappe.local.lang = 'en'
from frappe.utils.file_manager import save_file
from erpnext_norway.setup import configure
from erpnext_norway.numbering import RULES


def rejected(action):
    frappe.db.savepoint('rejected_app_operation')
    try:
        action()
    except (frappe.ValidationError, frappe.PermissionError):
        frappe.db.rollback(save_point='rejected_app_operation')
    else:
        raise AssertionError('Expected preservation rejection')


try:
    assert 'erpnext_norway' in frappe.get_installed_apps()
    for name in RULES:
        assert frappe.db.exists('Document Naming Rule', name), name
    for doctype in ('Sales Invoice', 'Purchase Invoice', 'Journal Entry', 'Payment Entry'):
        assert frappe.get_meta(doctype).protect_attached_files
    if sys.argv[1] == 'fresh':
        assert frappe.get_meta('Sales Invoice').default_print_format == 'Norway Invoice'
        assert frappe.get_meta('Quotation').default_print_format == 'Norway Quotation'
        for name in RULES:
            assert frappe.db.get_value('Document Naming Rule', name, 'counter') == 0
        # Existing native settings permit selecting a starting number before use.
        rule = frappe.get_doc('Document Naming Rule', 'Norway Sales Invoice')
        rule.counter = 40
        rule.save()
        rule = frappe.get_doc('Document Naming Rule', 'Norway Supplier')
        rule.prefix = 'L-'
        rule.counter = 20
        rule.save()
        frappe.db.commit()
        print('PASS real app installation on empty registers; native rules and configurable starting counters')
    elif sys.argv[1] == 'snapshot':
        # Later scenarios legitimately allocate more native invoice numbers.
        # Capture the final counter immediately before backup, retaining the
        # exact equality check after restore and detecting a reset beforehand.
        counter = frappe.db.get_value('Document Naming Rule', 'Norway Sales Invoice', 'counter')
        assert counter >= int(frappe.db.get_default('runtime_app_counter'))
        frappe.db.set_default('runtime_app_counter', counter)
        frappe.db.commit()
        print('PASS final native invoice counter retained for exact exported restore comparison')
    elif sys.argv[1] == 'verify':
        name = frappe.db.get_default('runtime_app_file')
        attachment = frappe.get_doc('File', name)
        assert Path(attachment.get_full_path()).read_bytes() == b'Original synthetic supplier document'
        rejected(attachment.delete)
        assert frappe.db.exists('File', name)
        assert frappe.db.get_value('Document Naming Rule', 'Norway Sales Invoice', 'counter') == int(frappe.db.get_default('runtime_app_counter'))
        print('PASS app, private original attachment and preservation guards after exported restore/migrate')
    else:
        company = 'Runtime Norwegian Example'
        sale = frappe.get_doc('Sales Invoice', {'company': company, 'docstatus': 1, 'is_return': 0})
        assert sale.name == 'F000041', sale.name
        assert frappe.db.exists('Sales Invoice', {'company': company, 'name': 'K000001', 'is_return': 1})
        supplier = frappe.get_doc('Supplier', {'supplier_name': 'Runtime Norwegian Supplier'})
        assert supplier.name == 'L-00021', supplier.name
        assert frappe.get_doc('Customer', {'customer_name': 'Runtime Norwegian Customer'}).name == '00001'
        from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
        draft = frappe.copy_doc(sale).insert()
        later = frappe.copy_doc(sale).insert()
        assert (draft.name, later.name) == ('F000042', 'F000043')
        rejected(draft.delete)
        frappe.local.lang = 'nb'
        try:
            draft.delete()
        except frappe.ValidationError as error:
            assert 'Bevar regnskapsbilaget' in str(error), str(error)
        else:
            raise AssertionError('Expected translated preservation error')
        frappe.local.lang = 'en'
        assert frappe.db.exists('Sales Invoice', draft.name)
        from frappe.model.rename_doc import rename_doc
        rejected(lambda: rename_doc('Sales Invoice', draft.name, 'MANUAL-NUMBER', force=True))
        altered = frappe.get_doc('Sales Invoice', draft.name)
        altered.is_return = 1
        rejected(altered.save)
        rule = frappe.get_doc('Document Naming Rule', 'Norway Sales Invoice')
        rule.counter = 0
        rejected(rule.save)
        rejected(lambda: frappe.delete_doc('Document Naming Rule', rule.name))
        rejected(lambda: rename_doc('Document Naming Rule', rule.name, 'Reset-series', force=True))
        rejected(lambda: frappe.get_doc({'doctype': 'Document Naming Rule', 'document_type': 'Sales Invoice',
            'prefix': 'OVERRIDE', 'prefix_digits': 6, 'counter': 0, 'priority': 10000}).insert())
        # Frappe's own rollback and row locking remain the numbering mechanism.
        frappe.db.savepoint('rolled_back_draft')
        rolled = frappe.copy_doc(sale).insert()
        expected = rolled.name
        frappe.db.rollback(save_point='rolled_back_draft')
        assert frappe.copy_doc(sale).insert().name == expected
        manual = frappe.copy_doc(sale)
        manual.name = 'MANUALLY-IMPORTED'
        frappe.flags.in_import = True
        try:
            rejected(manual.insert)
        finally:
            frappe.flags.in_import = False
        print('PASS native F/K and party numbering; retained drafts, rename/type/counter guards and rollback')
        frappe.db.savepoint('used_legacy_register')
        frappe.delete_doc('Document Naming Rule', 'Norway Quotation')
        customer = frappe.get_doc('Customer', {'customer_name': 'Runtime Norwegian Customer'})
        frappe.get_doc({'doctype': 'Quotation', 'quotation_to': 'Customer', 'party_name': customer.name,
            'company': company, 'transaction_date': '2026-10-18', 'valid_till': '2026-11-18',
            'items': [{'item_code': 'RUNTIME-NO-SERVICE', 'qty': 1, 'rate': 100}]}).insert()
        configure()
        assert not frappe.db.exists('Document Naming Rule', 'Norway Quotation')
        frappe.db.rollback(save_point='used_legacy_register')
        frappe.clear_cache()
        print('PASS setup preserves an already used register without installing a replacement numbering rule')


        purchase = frappe.get_doc('Purchase Invoice', {'company': company, 'docstatus': 1, 'is_return': 0})
        attachment = save_file('supplier-original.txt', b'Original synthetic supplier document',
                               purchase.doctype, purchase.name, is_private=1)
        original_path = Path(attachment.get_full_path())
        original_bytes = original_path.read_bytes()
        for user in ('runtime-owner@example.invalid', 'Administrator'):
            frappe.set_user(user)
            rejected(lambda: frappe.delete_doc('File', attachment.name))
            for field, value in [('attached_to_name', draft.name), ('attached_to_doctype', 'Sales Invoice'),
                                 ('file_url', '/private/files/replaced.txt'), ('is_private', 0),
                                 ('file_name', 'replaced.txt')]:
                changed = frappe.get_doc('File', attachment.name)
                setattr(changed, field, value)
                rejected(changed.save)
            # Exercise the ordinary File API as well as direct document deletion.
            from frappe.client import set_value, delete
            rejected(lambda: set_value('File', attachment.name, {'attached_to_name': '' , 'attached_to_doctype': ''}))
            rejected(lambda: delete('File', attachment.name))
            assert original_path.read_bytes() == original_bytes
        frappe.set_user('Administrator')
        rejected(lambda: frappe.get_doc('File', attachment.name).save_file(content=b'Altered', overwrite=True))
        shared = attachment.create_attachment_copy('Sales Invoice', draft.name)
        rejected(lambda: shared.save_file(content=b'Altered through shared draft', overwrite=True))
        assert original_path.read_bytes() == original_bytes
        replacement = frappe.get_doc({'doctype': 'File', 'file_name': attachment.file_name,
            'is_private': 1, 'content': b'Overwrite without existing File ID'})
        rejected(lambda: replacement.save_file(content=b'Overwrite without existing File ID', overwrite=True))
        assert original_path.read_bytes() == original_bytes
        # New evidence can still be attached to a posted invoice.
        extra = save_file('supplier-correction.txt', b'Additional synthetic evidence', purchase.doctype, purchase.name, is_private=1)
        assert frappe.db.exists('File', extra.name)
        # Correct a mistaken attachment on a draft using the native File lifecycle.
        temporary = save_file('draft-mistake.txt', b'Draft attachment may be corrected', 'Sales Invoice', draft.name, is_private=1)
        temporary_path = Path(temporary.get_full_path())
        temporary.delete()
        assert not temporary_path.exists()
        print('PASS posted File API delete/detach/URL/privacy/overwrite rejection; shared blob safe; draft correction and added evidence allowed')

        cancellable_sale = frappe.copy_doc(sale).insert()
        cancellable_sale.submit()
        credit = make_sales_return(cancellable_sale.name)
        credit.update_outstanding_for_self = 0
        credit.posting_date = '2026-10-18'
        credit.set_posting_time = 1
        credit.insert()
        credit.submit()
        cancelled_file = save_file('cancelled-invoice.txt', b'Cancelled synthetic invoice evidence', credit.doctype, credit.name, is_private=1)
        credit.cancel()
        cancelled_path = Path(cancelled_file.get_full_path())
        rejected(lambda: frappe.delete_doc('File', cancelled_file.name))
        rejected(lambda: frappe.delete_doc('Sales Invoice', credit.name, force=True))
        amended = frappe.copy_doc(credit)
        amended.amended_from = credit.name
        rejected(amended.insert)
        assert cancelled_path.read_bytes() == b'Cancelled synthetic invoice evidence'
        # Cancelled journals/payments must also remain; core cancellation is allowed.
        journal = frappe.copy_doc(frappe.get_doc('Journal Entry', {'company': company, 'docstatus': 1})).insert()
        journal.submit()
        journal.cancel()
        from erpnext.accounts.utils import is_immutable_ledger_enabled
        original_immutable = frappe.db.get_single_value('Accounts Settings', 'enable_immutable_ledger')
        for enabled in (1, 0):
            frappe.db.set_single_value('Accounts Settings', 'enable_immutable_ledger', enabled)
            frappe.db.value_cache.clear()
            assert bool(is_immutable_ledger_enabled()) == bool(enabled)
            try:
                # Invoke the real controller chain before any delete/link checks.
                journal.run_method('on_trash')
            except frappe.ValidationError as error:
                expected = ('Cancelled transactions cannot be deleted' if enabled else
                            'Keep this accounting document')
                assert expected in str(error), str(error)
            else:
                raise AssertionError('Cancelled journal deletion was permitted')
        frappe.db.set_single_value('Accounts Settings', 'enable_immutable_ledger', original_immutable)
        frappe.db.value_cache.clear()
        rejected(lambda: frappe.delete_doc('Journal Entry', journal.name, force=True))
        journal_file = save_file('cancelled-journal.txt', b'Cancelled journal evidence', journal.doctype, journal.name, is_private=1)
        rejected(lambda: frappe.delete_doc('File', journal_file.name))
        print('PASS native cancellation preserved; cancelled document/file deletion and suffix amendment rejected')
        # Roll back accounting probes: do not alter the known profit/bank restore baseline.
        frappe.db.rollback()
        frappe.clear_cache()
        purchase = frappe.get_doc('Purchase Invoice', {'company': company, 'docstatus': 1, 'is_return': 0})
        attachment = save_file('supplier-original.txt', b'Original synthetic supplier document', purchase.doctype, purchase.name, is_private=1)
        frappe.db.set_default('runtime_app_file', attachment.name)
        configure()
        assert frappe.db.get_value('Document Naming Rule', 'Norway Sales Invoice', 'counter') == 41
        frappe.db.commit()
        print('PASS idempotent native setup preserves used counters and original evidence for restore')
        # Two independent database sessions contend on the SAME native rule.
        # Keep the resulting drafts: preserving their sequence is the intended behaviour.
        import concurrent.futures
        import json
        import subprocess
        worker = """
import json, frappe
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
if 'erpnext_norway' in frappe.get_installed_apps():
    frappe.conf.host_name = 'http://frontend:8080'
frappe.set_user('runtime-owner@example.invalid')
sale=frappe.get_doc('Sales Invoice', 'F000041')
try:
 names=[frappe.copy_doc(sale).insert().name for _ in range(3)]
 frappe.db.commit()
 print(json.dumps({'names':names, 'conflict':False}))
except frappe.QueryDeadlockError:
 frappe.db.rollback()
 print(json.dumps({'names':[], 'conflict':True}))
frappe.destroy()
"""
        def create_concurrent_drafts(_):
            result = subprocess.run([sys.executable, '-c', worker], text=True,
                                    capture_output=True, timeout=120)
            assert result.returncode == 0, result.stderr
            return json.loads(result.stdout.strip().splitlines()[-1])
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            batches = list(executor.map(create_concurrent_drafts, range(2)))
        conflicts = sum(batch['conflict'] for batch in batches)
        # Native requests may reject a contended transaction. A fresh subsequent
        # save must reuse its rolled-back numbers; no product retry engine is added.
        completed = [batch for batch in batches if not batch['conflict']]
        for _ in range(conflicts):
            batch = create_concurrent_drafts(None)
            assert not batch['conflict'], batch
            completed.append(batch)
        names = [name for batch in completed for name in batch['names']]
        frappe.db.rollback()
        assert sorted(names) == [f'F{number:06d}' for number in range(42, 48)], names
        assert frappe.db.get_value('Document Naming Rule', 'Norway Sales Invoice', 'counter') == 47
        frappe.db.set_default('runtime_app_counter', '47')
        frappe.db.commit()
        print(f'PASS native concurrent numbering and rollback/re-save: six consecutive unique drafts; conflicts={conflicts}')

finally:
    frappe.destroy()
