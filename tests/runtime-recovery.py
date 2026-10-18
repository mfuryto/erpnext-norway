"""Synthetic recovery assertions, executed only inside runtime-smoke.sh's site."""
import json
import base64
import os
import sys
from pathlib import Path

import frappe
from frappe.utils.password import get_decrypted_password, set_encrypted_password


phase = sys.argv[1]
assert phase in {"seed", "damage", "verify"}
# Match bench's working directory; Frappe resolves its bench log path from here.
os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="accounting", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
public = Path(frappe.get_site_path("public", "files", "runtime-ci.txt"))
private = Path(frappe.get_site_path("private", "files", "runtime-ci.txt"))
try:
    if phase == "seed":
        from erpnext.setup.setup_wizard.setup_wizard import setup_complete
        from frappe.utils.pdf import get_pdf

        company = "Runtime Recovery Example"
        setup_complete(frappe._dict(
            country="Norway", language="en", company_name=company, company_abbr="RRE",
            currency="NOK", chart_of_accounts="Standard", fy_start_date="2026-01-01",
            fy_end_date="2026-12-31", timezone="Europe/Oslo",
        ))
        cash = frappe.db.get_value("Account", {
            "company": company, "account_type": "Cash", "is_group": 0,
        })
        equity = frappe.db.get_value("Account", {
            "company": company, "root_type": "Equity", "is_group": 0,
        })
        assert cash and equity
        journal = frappe.get_doc({
            "doctype": "Journal Entry", "company": company, "posting_date": "2026-10-18",
            "voucher_type": "Journal Entry", "accounts": [
                {"account": cash, "debit_in_account_currency": 100},
                {"account": equity, "credit_in_account_currency": 100},
            ],
        }).insert()
        journal.submit()
        frappe.db.set_default("runtime_ci_journal", journal.name)
        pdf = get_pdf("<html><body><h1>Synthetic runtime PDF</h1><p>NOK 1250</p></body></html>")
        assert pdf.startswith(b"%PDF-"), "PDF renderer did not return a PDF"
        print("PASS native PDF renderer (not invoice layout acceptance)")
        for is_private in (0, 1):
            frappe.get_doc({
                "doctype": "File", "file_name": "runtime-ci.txt",
                "content": "synthetic recovery evidence", "is_private": is_private,
                "attached_to_doctype": "Journal Entry", "attached_to_name": journal.name,
            }).insert()
        frappe.db.set_default("runtime_ci_recovery", "before-backup")
        set_encrypted_password("User", "Administrator", "synthetic-secret", "api_secret")
        frappe.db.commit()
        assert public.exists() and private.exists()
    elif phase == "damage":
        frappe.db.set_default("runtime_ci_recovery", "after-backup")
        set_encrypted_password("User", "Administrator", "changed-secret", "api_secret")
        frappe.db.commit()
        public.unlink()
        private.unlink()
        config_path = Path(frappe.get_site_path("site_config.json"))
        config = json.loads(config_path.read_text())
        config["encryption_key"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
        config_path.write_text(json.dumps(config))
        assert not public.exists() and not private.exists()
        assert frappe.db.get_default("runtime_ci_recovery") == "after-backup"
        print("PASS synthetic database and file changes made after backup")
    else:
        from frappe.utils.modules import get_blocked_modules, is_module_visible

        assert frappe.db.get_default("runtime_ci_recovery") == "before-backup"
        assert {"Manufacturing", "Projects", "Quality Management"} <= set(
            get_blocked_modules("Administrator")
        )
        assert is_module_visible("Stock", "Administrator")
        assert is_module_visible("Projects", "runtime-modules@example.invalid")
        assert is_module_visible("Stock", "runtime-modules@example.invalid")
        assert not is_module_visible("Manufacturing", "runtime-modules@example.invalid")
        norwegian_company = "Runtime Norwegian Example"
        assert frappe.db.exists("Company", norwegian_company)
        codes = frappe.get_all("Account", filters={"company": norwegian_company}, pluck="account_number")
        assert len([code for code in codes if code and len(code) == 4]) == 745
        bank = frappe.db.get_value("Account", {"company": norwegian_company, "account_number": "1920"})
        assert float(frappe.db.sql(
            "SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE company=%s AND account=%s AND is_cancelled=0",
            (norwegian_company, bank),
        )[0][0]) == 275
        for template in ("Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"):
            assert not frappe.db.exists(template, {"company": norwegian_company, "is_default": 1})
        assert get_decrypted_password("User", "Administrator", "api_secret") == "synthetic-secret"
        for path in (public, private):
            assert path.read_text() == "synthetic recovery evidence"
        assert frappe.db.exists("File", {"file_url": "/files/runtime-ci.txt", "is_private": 0})
        assert frappe.db.exists("File", {"file_url": "/private/files/runtime-ci.txt", "is_private": 1})
        journal_name = frappe.db.get_default("runtime_ci_journal")
        assert frappe.db.get_value("Journal Entry", journal_name, "docstatus") == 1
        ledger = frappe.get_all("GL Entry", filters={
            "voucher_type": "Journal Entry", "voucher_no": journal_name, "is_cancelled": 0,
        }, fields=["debit", "credit"])
        assert len(ledger) == 2
        assert sum(row.debit for row in ledger) == 100
        assert sum(row.credit for row in ledger) == 100
        assert frappe.db.count("File", {
            "attached_to_doctype": "Journal Entry", "attached_to_name": journal_name,
        }) == 2
        live = json.loads(Path(frappe.get_site_path("site_config.json")).read_text())
        saved = json.loads(Path(frappe.get_site_path("private", "runtime-backups", "restored-ci", "site_config.json")).read_text())
        assert live["encryption_key"] == saved["encryption_key"]
        assert live["db_password"] == saved["db_password"]
        print("PASS restored journal/ledger, database, attached public/private files and encrypted secret")
finally:
    frappe.destroy()
