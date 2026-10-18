"""Protect native numbers; never allocate numbers outside Frappe's own rules."""
import frappe
from frappe import _

RULES = {
    "Norway Sales Invoice": ("Sales Invoice", "F", 6, [("is_return", "0")]),
    "Norway Credit Note": ("Sales Invoice", "K", 6, [("is_return", "1")]),
    "Norway Quotation": ("Quotation", "T", 6, []),
    "Norway Customer": ("Customer", ".", 5, []),
    "Norway Supplier": ("Supplier", ".", 5, []),
}


def guard_import_name(doc, method=None):
    # Native ordinary inserts already discard a supplied name. Data Import is a
    # documented exception; do not let it bypass the configured native series.
    if frappe.flags.in_import and doc.name:
        if frappe.db.exists("Document Naming Rule", "Norway Sales Invoice"):
            frappe.throw(_("Let the existing invoice series assign the number. Importing a supplied invoice number is not supported."))


def prevent_rename(doc, method=None, *args, **kwargs):
    frappe.throw(_("The saved invoice number must be retained."))


def guard_invoice_identity(doc, method=None):
    if doc.is_new():
        if doc.amended_from:
            frappe.throw(_("Use a new invoice or credit note with the next native number. Keep the cancelled original and its reference."))
        return
    previous = frappe.db.get_value("Sales Invoice", doc.name, ["company", "is_return", "amended_from"], as_dict=True)
    if previous and any((previous.get(field) or "") != (doc.get(field) or "") for field in previous):
        frappe.throw(_("The company and document type of a numbered invoice cannot be changed. Keep the draft and create the correct document."))


def rule_is_used(doc):
    targets = {doc.document_type}
    if not doc.is_new():
        targets.add(frappe.db.get_value("Document Naming Rule", doc.name, "document_type"))
    for doctype in targets:
        if doctype and frappe.db.exists(doctype, {}):
            if any(spec[0] == doctype and frappe.db.exists("Document Naming Rule", name) for name, spec in RULES.items()):
                return True
    return False


def guard_rule_change(doc, method=None):
    if not rule_is_used(doc):
        return
    if doc.is_new():
        frappe.throw(_("Keep the native naming rules already used by existing documents."))
    previous = frappe.get_doc("Document Naming Rule", doc.name)
    fields = ("document_type", "prefix", "prefix_digits", "counter", "priority", "disabled")
    if any(previous.get(field) != doc.get(field) for field in fields) or [(row.field, row.condition, row.value) for row in previous.conditions] != [(row.field, row.condition, row.value) for row in doc.conditions]:
        frappe.throw(_("This native naming rule is in use and cannot be reset or changed."))


def guard_rule_delete(doc, method=None, *args, **kwargs):
    if rule_is_used(doc):
        frappe.throw(_("Keep the native naming rule used by existing documents."))
