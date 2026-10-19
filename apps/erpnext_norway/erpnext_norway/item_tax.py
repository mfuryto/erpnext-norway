"""Allow native COGS expense allocation without changing an account's type.

Core permits Expense Account but omits Cost of Goods Sold in Item Tax Template,
although native invoice tax rows and GL already accept that same expense account.
All ordinary rows still use the native validator; the exception uses the native
company/leaf validator and retains duplicate checks. No calculation/posting override.
"""
import frappe
from erpnext.controllers.accounts_controller import validate_account_head


class NorwegianItemTaxMixin:
    def validate_tax_accounts(self):
        if frappe.get_cached_value('Company', self.company, 'country') != 'Norway':
            return super().validate_tax_accounts()
        cogs = [row for row in self.taxes if row.tax_type and frappe.get_cached_value(
            'Account', row.tax_type, 'account_type') == 'Cost of Goods Sold']
        if not cogs:
            return super().validate_tax_accounts()
        original = self.taxes
        try:
            self.taxes = [row for row in original if row not in cogs]
            super().validate_tax_accounts()
        finally:
            self.taxes = original
        names = [row.tax_type for row in original if row.tax_type]
        if len(names) != len(set(names)):
            frappe.throw(frappe._('Do not repeat the same account in an item tax template.'))
        for row in cogs:
            validate_account_head(row.idx, row.tax_type, self.company, frappe._('Item Tax'))
