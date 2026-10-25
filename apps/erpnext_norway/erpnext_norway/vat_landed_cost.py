"""Retain native LCV valuation for real returns and manual Asset creation.

No amount, valuation, GL or lifecycle method is overridden. Core's Asset
quantity/status check remains in place for ordinary vouchers and existing Assets.
"""
import frappe


class NorwegianLandedCostMixin:
    def validate_asset_qty_and_status(self, receipt_document_type, receipt_document):
        from erpnext_norway.vat_valuation import ALLOCATION, SOURCE
        if (not self.get(ALLOCATION) or len(self.purchase_receipts) != 1 or
                frappe.get_cached_value('Company', self.company, 'country') != 'Norway' or
                receipt_document_type not in ('Purchase Invoice', 'Purchase Receipt') or
                receipt_document.company != self.company or receipt_document.docstatus != 1):
            return super().validate_asset_qty_and_status(receipt_document_type, receipt_document)
        link = 'purchase_invoice' if receipt_document_type == 'Purchase Invoice' else 'purchase_receipt'
        exceptions = []
        adjusted = []
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
            elif not receipt_document.is_return:
                source = next((item for item in receipt_document.items if item.name == row.purchase_receipt_item), None)
                quarterly = source and source.get('custom_norway_quarterly_service')
                if source and receipt_document_type == 'Purchase Receipt' and self.get(SOURCE):
                    bill = frappe.get_doc('Purchase Invoice', self.get(SOURCE))
                    bill.check_permission('read')
                    quarterly = any(item.get('custom_norway_quarterly_service') and
                        item.purchase_receipt == receipt_document.name and item.pr_detail == source.name
                        for item in bill.items)
                if quarterly:
                    from erpnext.controllers.sales_and_purchase_return import get_returned_qty_map_for_row
                    from frappe.utils import flt
                    returned = flt(get_returned_qty_map_for_row(receipt_document.name,
                        receipt_document.supplier, source.name, receipt_document_type).get('qty'))
                    if returned:
                        remaining = max(0, flt(row.qty) - returned)
                        if not remaining and not frappe.db.exists('Asset', {link: receipt_document.name,
                                'item_code': row.item_code, 'docstatus': ['!=', 2]}):
                            exceptions.append(row)
                        else:
                            adjusted.append((row, row.qty, remaining))
        if not exceptions and not adjusted:
            return super().validate_asset_qty_and_status(receipt_document_type, receipt_document)
        original = self.items
        try:
            for row, original_qty, remaining in adjusted:
                row.qty = remaining
            self.items = [row for row in original if row not in exceptions]
            return super().validate_asset_qty_and_status(receipt_document_type, receipt_document)
        finally:
            self.items = original
            for row, qty, remaining in adjusted:
                row.qty = qty


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
