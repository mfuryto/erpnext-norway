"""Close tested native attachment gaps without replacing the File store."""
import frappe
from frappe import _

ACCOUNTING = ("Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry", "Purchase Receipt", "Landed Cost Voucher")
RETAINED = (*ACCOUNTING, "Quotation")
NATIVE_IDENTITY_FIELDS = ("attached_to_doctype", "attached_to_name", "attached_to_field", "file_url",
                   "file_name", "content_hash", "is_private", "is_folder", "thumbnail_url")



def identity_fields():
    from erpnext_norway.vat_evidence import RETAIN, FIELDS
    return (*NATIVE_IDENTITY_FIELDS, *FIELDS) if frappe.db.has_column('File', RETAIN) else NATIVE_IDENTITY_FIELDS


def is_retained(file, cancelled_only=False):
    from erpnext_norway.vat_evidence import RETAIN
    if file.get(RETAIN):
        return True
    doctype, name = file.get("attached_to_doctype"), file.get("attached_to_name")
    return bool(doctype in RETAINED and name and
                frappe.db.get_value(doctype, name, "docstatus", for_update=True) in ((2,) if cancelled_only else (1, 2)))


def stored_file(file):
    return frappe.db.get_value("File", file.name, ["name", *identity_fields()], as_dict=True) if file.name else None


def refuse(file=None):
    from erpnext_norway.vat_evidence import RETAIN
    if file and file.get(RETAIN):
        frappe.throw(_("VAT return evidence must be retained. Add a new file for a correction."))
    frappe.throw(_("Attachments on posted or cancelled accounting documents must be retained. Add a new attachment to document a correction."))


def guard_file_change(doc, method=None):
    if doc.is_new():
        return
    previous = stored_file(doc)
    if previous and is_retained(previous):
        if any((previous.get(field) or "") != (doc.get(field) or "") for field in identity_fields()):
            refuse(previous)


class RetainedFileMixin:
    def on_trash(self):
        previous = stored_file(self)
        if is_retained(self, cancelled_only=True) or (previous and is_retained(previous, cancelled_only=True)):
            refuse(previous or self)
        # Submitted files are already protected by the native DocType setting.
        parent = getattr(super(), "on_trash", None)
        return parent() if parent else None

    def save_file(self, *args, **kwargs):
        # Native upload/overwrite can write bytes before validate. Check first,
        # including a draft attachment sharing the same native file URL.
        previous = stored_file(self) if not self.is_new() else None
        if previous and is_retained(previous):
            refuse(previous)
        urls = {value for value in (self.file_url, previous and previous.file_url) if value}
        overwrite = kwargs.get("overwrite", args[3] if len(args) > 3 else False)
        if self.file_name and overwrite:
            from frappe.core.doctype.file.utils import get_safe_file_name
            prefix = "/private/files/" if self.is_private else "/files/"
            urls.add(prefix + get_safe_file_name(self.file_name))
        for url in urls:
            for other in frappe.get_all("File", filters={"file_url": url}, fields=list(identity_fields())):
                if is_retained(other):
                    refuse(other)
        return super().save_file(*args, **kwargs)


class RetainedDocumentMixin:
    def on_trash(self):
        if self.docstatus in (1, 2) or self.doctype == "Sales Invoice":
            frappe.throw(_("Keep this accounting document to preserve its number and documentation. Use the standard cancellation or credit note when applicable."))
        parent = getattr(super(), "on_trash", None)
        return parent() if parent else None
