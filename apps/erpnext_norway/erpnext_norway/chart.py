"""Supply one Norwegian template to native Company/create_charts and native previews.

The image registers the app-owned data in the native template catalogue. Company
creation and previews use native custom_chart/from_coa_importer so repeated labels
keep their exact names; all account creation and other templates remain native.
"""
import json
from pathlib import Path

import frappe
from erpnext.accounts.doctype.account.chart_of_accounts import chart_of_accounts as native

NAME = "Norsk kontoplan"


def tree():
    return json.loads((Path(__file__).parent / "chart_data/norway.json").read_text())["tree"]


@frappe.whitelist()
def build_tree_from_json(chart_template, chart_data=None, from_coa_importer=False):
    if chart_template == NAME and not chart_data:
        return native.build_tree_from_json(NAME, chart_data=tree(), from_coa_importer=True)
    return native.build_tree_from_json(chart_template, chart_data, from_coa_importer)


@frappe.whitelist()
def validate_bank_account(coa, bank_account):
    if coa != NAME:
        return native.validate_bank_account(coa, bank_account)
    # Match the core's name-membership check, including templates with numbered labels.
    rows = native.build_tree_from_json(NAME, chart_data=tree(), from_coa_importer=True)
    return any(bank_account in (row["value"], row["value"].split(" - ", 1)[-1]) for row in rows)


def select_default(doc, method=None):
    if (doc.is_new() and doc.country == "Norway" and doc.default_currency == "NOK" and not doc.chart_of_accounts
            and doc.create_chart_of_accounts_based_on != "Existing Company"):
        doc.chart_of_accounts = NAME


class NorwegianCompanyMixin:
    def create_default_accounts(self):
        if self.chart_of_accounts != NAME or self.existing_company:
            return super().create_default_accounts()
        if self.default_currency != "NOK":
            frappe.throw(frappe._("The Norwegian chart template currently supports NOK as company currency."))
        frappe.local.flags.ignore_root_company_validation = True
        native.create_charts(self.name, custom_chart=tree(), from_coa_importer=True)
        # Native Company expects these two bindings from create_default_accounts;
        # its remaining on_update/default/warehouse/tax lifecycle continues normally.
        for field, account_type in (("default_receivable_account", "Receivable"),
                                    ("default_payable_account", "Payable")):
            self.db_set(field, frappe.db.get_value("Account", {
                "company": self.name, "account_type": account_type, "is_group": 0,
            }))
