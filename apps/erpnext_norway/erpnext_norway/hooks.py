app_name = "erpnext_norway"
app_title = "ERPNext Norway"
app_publisher = "ERPNext Norway contributors"
app_description = "Minimal safeguards for native accounting documents"
app_email = "maintainers@example.invalid"
app_license = "GPL-3.0-only"
required_apps = ["erpnext"]
erpnext_taxable_base_resolvers = {"On Norwegian VAT Base": "erpnext_norway.vat_currency.basis"}
app_include_js = ["/assets/erpnext_norway/js/locale.js"]

after_install = "erpnext_norway.setup.configure"
after_migrate = "erpnext_norway.setup.configure"

# Ordinary events run before validation/rename. File.on_trash hooks run AFTER
# native disk removal; a cooperative extension is needed for that specific gap.
_accounting = ["Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry", "Purchase Receipt", "Landed Cost Voucher"]
extend_doctype_class = {
    "Item Tax Template": ["erpnext_norway.item_tax.NorwegianItemTaxMixin"],
    "File": ["erpnext_norway.preservation.RetainedFileMixin"],
    "Company": ["erpnext_norway.chart.NorwegianCompanyMixin"],
    "Quotation": ["erpnext_norway.preservation.RetainedDocumentMixin"],
    **{name: ["erpnext_norway.preservation.RetainedDocumentMixin"] for name in _accounting},
    "Landed Cost Voucher": ["erpnext_norway.preservation.RetainedDocumentMixin",
        "erpnext_norway.vat_landed_cost.NorwegianLandedCostMixin"],
}
doc_events = {
    "Landed Cost Voucher": {
        "on_submit": "erpnext_norway.vat_landed_cost.refresh_zero_asset_values",
        "on_cancel": "erpnext_norway.vat_landed_cost.refresh_zero_asset_values"},
    "Sales Order": {"before_validate": ["erpnext_norway.vat.stamp_commercial_document",
        "erpnext_norway.vat_catalog.prepare_items"]},
    "Delivery Note": {"before_validate": ["erpnext_norway.vat.stamp_commercial_document",
        "erpnext_norway.vat_catalog.prepare_items"]},
    "Purchase Order": {"before_validate": ["erpnext_norway.vat.stamp_commercial_document",
        "erpnext_norway.vat_catalog.prepare_items", "erpnext_norway.vat_catalog.stamp_codes",
        "erpnext_norway.vat_valuation.guard_configuration"],
        "validate": "erpnext_norway.reverse_charge.guard_currency"},
    "Purchase Receipt": {"before_validate": ["erpnext_norway.vat_valuation.prepare_receipt_return",
        "erpnext_norway.vat_catalog.prepare_items", "erpnext_norway.vat_catalog.stamp_codes",
        "erpnext_norway.vat_valuation.guard_configuration"],
        "validate": "erpnext_norway.vat_import.validate_receipt",
        "before_submit": "erpnext_norway.vat_import.validate_receipt",
        "on_update_after_submit": ["erpnext_norway.vat_catalog.validate_code_changes", "erpnext_norway.vat_import.validate_receipt"],
        "on_submit": "erpnext_norway.vat_valuation.allocate_direct",
        "before_cancel": "erpnext_norway.vat_valuation.cancel_adjustments"},
    "Journal Entry": {"validate": "erpnext_norway.vat_journal.validate",
        "before_submit": "erpnext_norway.vat_journal.validate",
        "on_update_after_submit": "erpnext_norway.vat_journal.validate",
        "before_cancel": "erpnext_norway.vat_quarterly.guard_cancel"},
    "Company": {
        "before_validate": ["erpnext_norway.chart.select_default", "erpnext_norway.vat.validate_company"],
        "on_update": "erpnext_norway.vat.configure_company",
    },
    "File": {"before_validate": "erpnext_norway.preservation.guard_file_change"},
    "Purchase Invoice": {"before_validate": ["erpnext_norway.vat_returns.prepare", "erpnext_norway.vat_valuation.link_credit_receipts", "erpnext_norway.vat_catalog.prepare_items", "erpnext_norway.vat_catalog.stamp_codes", "erpnext_norway.vat_valuation.guard_configuration"],
        "validate": "erpnext_norway.vat.validate_invoice",
        "before_submit": ["erpnext_norway.vat.validate_invoice", "erpnext_norway.vat_catalog.validate_invoice_codes", "erpnext_norway.vat_valuation.lock_receipts"],
        "on_submit": ["erpnext_norway.vat_valuation.adjust_receipts", "erpnext_norway.vat_quarterly.update"],
        "on_cancel": "erpnext_norway.vat_quarterly.update",
        "before_cancel": "erpnext_norway.vat_valuation.cancel_adjustments",
        "on_update_after_submit": "erpnext_norway.vat_catalog.validate_code_changes"},
    "Sales Invoice": {
        "validate": "erpnext_norway.vat.validate_invoice",
        "before_submit": ["erpnext_norway.vat.validate_invoice", "erpnext_norway.vat_catalog.validate_invoice_codes"],
        "on_submit": "erpnext_norway.printing.preserve_submission",
        "on_update_after_submit": "erpnext_norway.vat_catalog.validate_code_changes",
        "before_naming": "erpnext_norway.numbering.guard_import_name",
        "before_validate": ["erpnext_norway.numbering.guard_invoice_identity", "erpnext_norway.vat.stamp_invoice", "erpnext_norway.vat_returns.prepare", "erpnext_norway.vat_catalog.prepare_items", "erpnext_norway.vat_catalog.stamp_codes"],
        "before_rename": "erpnext_norway.numbering.prevent_rename",
    },
    "Quotation": {"before_validate": ["erpnext_norway.vat.stamp_commercial_document",
        "erpnext_norway.vat_catalog.prepare_items"],
        "on_submit": "erpnext_norway.printing.preserve_submission",
        "before_rename": "erpnext_norway.printing.guard_quotation_rename"},
    "Document Naming Rule": {
        "validate": "erpnext_norway.numbering.guard_rule_change",
        "on_trash": "erpnext_norway.numbering.guard_rule_delete",
        "before_rename": "erpnext_norway.numbering.guard_rule_delete",
    },
}

# Only the additional template is supplied here. Other templates use native code.
_chart_api = "erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts."
override_whitelisted_methods = {
    _chart_api + name: "erpnext_norway.chart." + name
    for name in ("build_tree_from_json", "validate_bank_account")
}
doctype_js = {"Company": "public/js/company.js",
    "Bank Reconciliation Tool": "public/js/bank_language.js",
    "Sales Invoice": "public/js/vat.js", "Purchase Invoice": "public/js/vat.js",
    "Quotation": "public/js/vat.js", "Sales Order": "public/js/vat.js", "Delivery Note": "public/js/vat.js",
    "Purchase Order": "public/js/vat.js", "Purchase Receipt": "public/js/vat.js",
    "Journal Entry": "public/js/vat_journal.js"}

jinja = {"methods": ["erpnext_norway.printing.bank_details", "erpnext_norway.printing.translated_taxes"]}
