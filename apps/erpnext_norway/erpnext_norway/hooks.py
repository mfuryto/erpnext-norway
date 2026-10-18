app_name = "erpnext_norway"
app_title = "ERPNext Norway"
app_publisher = "ERPNext Norway contributors"
app_description = "Minimal safeguards for native accounting documents"
app_email = "maintainers@example.invalid"
app_license = "GPL-3.0-only"
required_apps = ["erpnext"]

after_install = "erpnext_norway.setup.configure"
after_migrate = "erpnext_norway.setup.configure"

# Ordinary events run before validation/rename. File.on_trash hooks run AFTER
# native disk removal; a cooperative extension is needed for that specific gap.
_accounting = ["Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"]
extend_doctype_class = {
    "File": ["erpnext_norway.preservation.RetainedFileMixin"],
    "Company": ["erpnext_norway.chart.NorwegianCompanyMixin"],
    **{name: ["erpnext_norway.preservation.RetainedDocumentMixin"] for name in _accounting},
}
doc_events = {
    "Company": {"before_validate": "erpnext_norway.chart.select_default"},
    "File": {"before_validate": "erpnext_norway.preservation.guard_file_change"},
    "Sales Invoice": {
        "before_naming": "erpnext_norway.numbering.guard_import_name",
        "before_validate": "erpnext_norway.numbering.guard_invoice_identity",
        "before_rename": "erpnext_norway.numbering.prevent_rename",
    },
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
doctype_js = {"Company": "public/js/company.js"}
