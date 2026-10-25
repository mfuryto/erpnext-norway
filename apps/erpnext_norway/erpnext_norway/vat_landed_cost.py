"""Retain native LCV valuation for real returns and manual Asset creation.

No amount, valuation, GL or lifecycle method is overridden. Core's Asset
quantity/status check remains in place for ordinary vouchers and existing Assets.
"""
import frappe


class NorwegianLandedCostMixin:
    def validate_asset_qty_and_status(self, receipt_document_type, receipt_document):
        from erpnext_norway.vat_valuation import ALLOCATION
        if (not self.get(ALLOCATION) or len(self.purchase_receipts) != 1 or
                frappe.get_cached_value('Company', self.company, 'country') != 'Norway' or
                receipt_document_type not in ('Purchase Invoice', 'Purchase Receipt') or
                receipt_document.company != self.company or receipt_document.docstatus != 1):
            return super().validate_asset_qty_and_status(receipt_document_type, receipt_document)
        link = 'purchase_invoice' if receipt_document_type == 'Purchase Invoice' else 'purchase_receipt'
        exceptions = []
        for row in self.items:
            if (not row.is_fixed_asset or row.receipt_document_type != receipt_document_type or
                    row.receipt_document != receipt_document.name):
                continue
            returning = receipt_document.is_return and receipt_document.return_against and row.qty < 0
            manual = (not receipt_document.is_return and row.qty > 0 and
                not frappe.get_cached_value('Item', row.item_code, 'auto_create_assets') and
                not frappe.db.exists('Asset', {link: receipt_document.name, 'item_code': row.item_code}))
            if returning or manual:
                exceptions.append(row)
        if not exceptions:
            return super().validate_asset_qty_and_status(receipt_document_type, receipt_document)
        original = self.items
        try:
            self.items = [row for row in original if row not in exceptions]
            return super().validate_asset_qty_and_status(receipt_document_type, receipt_document)
        finally:
            self.items = original


def refresh_zero_asset_values(voucher, method=None):
    """Core skips its own Asset updater when the last landed cost becomes zero."""
    from erpnext_norway.vat_valuation import ALLOCATION
    if (not voucher.get(ALLOCATION) or
            frappe.get_cached_value('Company', voucher.company, 'country') != 'Norway'):
        return
    for row in voucher.purchase_receipts:
        if row.receipt_document_type not in ('Purchase Receipt', 'Purchase Invoice'):
            continue
        source = frappe.get_doc(row.receipt_document_type, row.receipt_document)
        for item in source.items:
            if item.is_fixed_asset and not item.landed_cost_voucher_amount:
                if source.doctype == 'Purchase Receipt':
                    source.update_assets(item, item.valuation_rate)
                else:
                    source.update_net_purchase_amount_for_linked_assets(item)
