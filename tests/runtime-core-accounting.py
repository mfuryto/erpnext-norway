"""Qualify the native importer and owner workflow against the Norwegian dataset.

Synthetic data only. No Norwegian tax calculation or replacement ledger is used.
"""
import csv
import io
import json
import os
from pathlib import Path

import frappe
os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="accounting", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
if 'erpnext_norway' in frappe.get_installed_apps():
    frappe.conf.host_name = 'http://frontend:8080'
frappe.set_user("Administrator")
frappe.local.lang = "en"
from frappe.utils.file_manager import save_file
from erpnext.accounts.doctype.chart_of_accounts_importer.chart_of_accounts_importer import import_coa
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import reconcile_vouchers
from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import execute as profit_report


COMPANY = "Runtime Norwegian Example"
DAY = "2026-10-18"


def equal(actual, expected):
    assert round(float(actual or 0), 2) == expected, (actual, expected)


def check_ledger(document, expected, accounts):
    entries = frappe.get_all("GL Entry", filters={
        "company": COMPANY, "voucher_type": document.doctype, "voucher_no": document.name, "is_cancelled": 0,
    }, fields=["account", "debit", "credit"])
    equal(sum(row.debit - row.credit for row in entries), 0)
    for code, amount in expected.items():
        equal(sum(row.debit - row.credit for row in entries if row.account == accounts[code]), amount)


def run():
    company = frappe.get_doc({
        "doctype": "Company", "company_name": COMPANY, "abbr": "RNE", "country": "Norway",
        "default_currency": "NOK", "create_chart_of_accounts_based_on": "Standard Template",
        "chart_of_accounts": "Standard", "enable_perpetual_inventory": 0,
    }).insert()
    if 'erpnext_norway' in frappe.get_installed_apps():
        company.custom_norway_vat_status = 'Not registered'
        company.save()
    contents = Path("/opt/runtime/norway.csv").read_text()
    source = {row["Account Number"]: row for row in csv.DictReader(io.StringIO(contents)) if row["Account Number"]}
    upload = save_file("norway.csv", contents.encode(), "Company", COMPANY, is_private=1)
    import_coa(upload.file_url, COMPANY)
    rows = frappe.get_all("Account", filters={"company": COMPANY},
                          fields=["name", "account_number", "account_name", "account_type", "root_type", "is_group"])
    numbered = {row.account_number: row for row in rows if row.account_number}
    assert len(numbered) == 745
    assert set(numbered) == set(source)
    assert all(numbered[code].account_name == data["Account Name"] for code, data in source.items())
    assert numbered["2740"].account_type == "Tax"
    accounts = {code: row.name for code, row in numbered.items()}
    company.reload()
    assert company.default_receivable_account == accounts["1500"]
    assert company.default_payable_account == accounts["2400"]
    print("PASS native import: 745 preserved Norwegian codes/names; correct 1500/2400 defaults")

    # The core wizard knows country, not registration status. Configure its own templates.
    if 'erpnext_norway' not in frappe.get_installed_apps():
        assert frappe.db.exists("Sales Taxes and Charges Template", {"company": COMPANY, "is_default": 1})
    for doctype in ("Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"):
        for name in frappe.get_all(doctype, filters={"company": COMPANY}, pluck="name"):
            template = frappe.get_doc(doctype, name)
            template.is_default = 0
            template.save()
        assert not frappe.db.exists(doctype, {"company": COMPANY, "is_default": 1})
    company.reload()
    company.default_bank_account = accounts["1920"]
    company.default_cash_account = accounts["1900"]
    company.round_off_account = accounts["7740"]
    company.default_income_account = accounts["3000"]
    company.default_expense_account = accounts["4300"]
    company.save()
    cost_center = company.cost_center

    customer = frappe.get_doc({"doctype": "Customer", "customer_name": "Runtime Norwegian Customer",
                               "customer_type": "Company", "customer_group": "Commercial", "territory": "Norway"}).insert()
    supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Runtime Norwegian Supplier",
                               "supplier_type": "Company", "supplier_group": "Services"}).insert()
    item = frappe.get_doc({
        "doctype": "Item", "item_code": "RUNTIME-NO-SERVICE", "item_name": "Synthetic service or licence",
        "item_group": "Services", "stock_uom": "Nos", "is_stock_item": 0,
        "item_defaults": [{"company": COMPANY, "income_account": accounts["3020"],
                           "expense_account": accounts["4500"]}],
    }).insert()
    bank = frappe.get_doc({"doctype": "Bank", "bank_name": "Runtime Norwegian Bank"}).insert()
    bank_account = frappe.get_doc({"doctype": "Bank Account", "account_name": "Runtime current account",
                                   "bank": bank.name, "company": COMPANY, "account": accounts["1920"],
                                   "is_company_account": 1}).insert()
    owner = frappe.get_doc({
        "doctype": "User", "email": "runtime-owner@example.invalid", "first_name": "Runtime Owner",
        "send_welcome_email": 0, "user_type": "System User",
        "roles": [{"role": role} for role in ("Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager")],
    }).insert()
    frappe.get_doc({"doctype": "User Permission", "user": owner.name, "allow": "Company",
                    "for_value": COMPANY, "apply_to_all_doctypes": 1}).insert()
    frappe.clear_cache(user=owner.name)
    frappe.set_user(owner.name)
    assert not frappe.has_permission("System Settings", "write")
    assert not frappe.has_permission("Company", "read", "Runtime Recovery Example")
    assert {row.name for row in frappe.get_list("Company", fields=["name"])} == {COMPANY}

    base = {"company": COMPANY, "posting_date": DAY, "set_posting_time": 1,
            "due_date": "2026-10-31", "currency": "NOK", "conversion_rate": 1,
            "cost_center": cost_center, "disable_rounded_total": 1}
    sale = frappe.get_doc({**base, "doctype": "Sales Invoice", "customer": customer.name,
                           "items": [{"item_code": item.name, "qty": 1, "rate": 1000}]}).insert()
    sale.submit()
    equal(sale.grand_total, 1000)
    equal(sale.total_taxes_and_charges, 0)
    check_ledger(sale, {"1500": 1000, "3020": -1000, "3000": 0, "2700": 0}, accounts)
    purchase = frappe.get_doc({**base, "doctype": "Purchase Invoice", "supplier": supplier.name,
        "bill_no": "SYNTHETIC-NO-1", "bill_date": DAY,
        "items": [{"item_code": item.name, "qty": 1, "rate": 400}],
        "taxes": [{"charge_type": "On Net Total", "account_head": accounts["4500"], "rate": 25,
                   "description": "Supplier VAT included in cost, no deduction", "category": "Total",
                   "add_deduct_tax": "Add", "cost_center": cost_center}],
    }).insert()
    purchase.submit()
    equal(purchase.grand_total, 500)
    check_ledger(purchase, {"2400": -500, "4500": 500, "4300": 0, "2710": 0}, accounts)

    sale_credit = make_sales_return(sale.name)
    sale_credit.update_outstanding_for_self = 0
    sale_credit.posting_date = DAY
    sale_credit.set_posting_time = 1
    sale_credit.items[0].qty = -1
    sale_credit.items[0].rate = 200
    sale_credit.save()
    sale_credit.submit()
    check_ledger(sale_credit, {"1500": -200, "3020": 200, "2700": 0}, accounts)
    purchase_credit = make_return_doc("Purchase Invoice", purchase.name)
    purchase_credit.update_outstanding_for_self = 0
    purchase_credit.posting_date = DAY
    purchase_credit.set_posting_time = 1
    purchase_credit.bill_no = "SYNTHETIC-NO-CREDIT-1"
    purchase_credit.items[0].qty = -1
    purchase_credit.items[0].rate = 100
    purchase_credit.save()
    purchase_credit.submit()
    check_ledger(purchase_credit, {"2400": 125, "4500": -125, "2710": 0}, accounts)
    sale.reload()
    purchase.reload()
    equal(sale.outstanding_amount, 800)
    equal(purchase.outstanding_amount, 375)

    movements = []
    for invoice, amount, deposit in ((sale, 800, True), (purchase, 375, False)):
        payment = get_payment_entry(invoice.doctype, invoice.name, bank_account=accounts["1920"], bank_amount=amount)
        payment.posting_date = DAY
        payment.reference_no = "SYNTHETIC-NO-PAYMENT"
        payment.reference_date = DAY
        payment.save()
        payment.submit()
        invoice.reload()
        equal(invoice.outstanding_amount, 0)
        movements.append((payment, amount, deposit))
    for code, amount, deposit in (("8050", 50, True), ("2070", 200, False)):
        journal = frappe.get_doc({"doctype": "Journal Entry", "company": COMPANY, "posting_date": DAY,
            "voucher_type": "Journal Entry", "accounts": [
                {"account": accounts["1920"], "debit_in_account_currency": amount if deposit else 0,
                 "credit_in_account_currency": 0 if deposit else amount},
                {"account": accounts[code], "debit_in_account_currency": 0 if deposit else amount,
                 "credit_in_account_currency": amount if deposit else 0},
            ]}).insert()
        journal.submit()
        movements.append((journal, amount, deposit))
    for index, (voucher, amount, deposit) in enumerate(movements):
        transaction = frappe.get_doc({"doctype": "Bank Transaction", "company": COMPANY, "date": DAY,
            "bank_account": bank_account.name, "deposit": amount if deposit else 0,
            "withdrawal": 0 if deposit else amount, "currency": "NOK",
            "transaction_id": f"SYNTHETIC-NO-{index}", "description": "Synthetic bank movement"}).insert()
        transaction.submit()
        reconcile_vouchers(transaction.name, json.dumps([{
            "payment_doctype": voucher.doctype, "payment_name": voucher.name, "amount": amount,
        }]))
        transaction.reload()
        equal(transaction.unallocated_amount, 0)

    report = profit_report(frappe._dict(company=COMPANY, filter_based_on="Date Range",
        period_start_date="2026-01-01", period_end_date="2026-12-31", periodicity="Yearly",
        accumulated_values=1, include_default_book_entries=1))
    result = next(row for row in report[1] if row and str(row.get("account_name", "")).strip("'") == "Profit for the year")
    equal(result["total"], 475)  # Revenue 800 + interest 50 - cost 375. Owner tax is equity.
    equal(frappe.db.sql("SELECT SUM(debit-credit) FROM `tabGL Entry` WHERE company=%s AND account=%s AND is_cancelled=0",
                        (COMPANY, accounts["1920"]))[0][0], 275)
    print("PASS ordinary owner: native sale/purchase/credits, non-stock licence/service, payments, bank and profit 475")

    frappe.set_user("Administrator")
    before = {row.name for row in frappe.get_all("Account", filters={"company": COMPANY})}
    gl_count = frappe.db.count("GL Entry", {"company": COMPANY})
    try:
        import_coa(upload.file_url, COMPANY)
    except frappe.ValidationError as error:
        assert "Transactions against the Company already exist" in str(error), str(error)
    else:
        raise AssertionError("Native importer accepted a company with posted transactions")
    assert before == {row.name for row in frappe.get_all("Account", filters={"company": COMPANY})}
    assert gl_count == frappe.db.count("GL Entry", {"company": COMPANY})
    frappe.db.commit()
    print("PASS native importer rejects replacement after posting; existing accounts and ledger retained")


try:
    run()
finally:
    frappe.destroy()
