"""Native Print Formats and a private submission PDF; no replacement print API."""
from copy import deepcopy
from pathlib import Path

import frappe
from frappe.translate import print_language
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils.file_manager import save_file

FORMATS = {"Sales Invoice": "Norway Invoice", "Quotation": "Norway Quotation"}


def configure():
    # The shipped company letterhead prints doc.doctype as raw English data.
    # Amend only an exact, unedited stock template, never a site's own content.
    originals = [path.read_text() for path in Path(frappe.get_app_path("erpnext", "accounts", "letterhead")).glob("*.html")]
    for row in frappe.get_all("Letter Head", fields=["name", "content"]):
        if any((row.content or "").strip() == native.strip() for native in originals):
            head = frappe.get_doc("Letter Head", row.name)
            head.content = row.content.replace("{{ doc.doctype }}", '{{ _("Credit Note") if doc.get("is_return") else _(doc.doctype) }}')
            head.save(ignore_permissions=True)
    html = (Path(__file__).parent / "templates/print_formats/sales_document.html").read_text()
    for doctype, name in FORMATS.items():
        # Expose the existing native language field on drafts; retain explicit customizations.
        if frappe.get_meta(doctype).get_field("language").read_only and not frappe.db.exists(
                "Property Setter", {"doc_type": doctype, "field_name": "language", "property": "read_only"}):
            make_property_setter(doctype, "language", "read_only", 0, "Check")
        # A site may customize its own copy or select a different native format.
        installing = not frappe.db.exists("Print Format", name)
        if installing:
            frappe.get_doc({"doctype": "Print Format", "name": name, "doc_type": doctype,
                "standard": "No", "custom_format": 1, "print_format_type": "Jinja",
                "pdf_generator": "wkhtmltopdf", "html": html}).insert(ignore_permissions=True)
        if not installing:
            format_doc = frappe.get_doc('Print Format', name)
            legacy = html.replace('translated_taxes(doc.taxes)', 'doc.taxes')
            if format_doc.html == legacy:
                format_doc.html = html
                format_doc.save(ignore_permissions=True)
        current = frappe.get_meta(doctype).default_print_format
        chosen = frappe.db.exists("Property Setter", {"doc_type": doctype, "property": "default_print_format"})
        native_empty_register = (installing and current == f"{doctype} Classic"
            and not frappe.db.exists(doctype, {}))
        if (not chosen and not current) or native_empty_register:
            make_property_setter(doctype, None, "default_print_format", name, "Data", for_doctype=True)


def translated_taxes(rows):
    """Localize our seeded label for printing; keep native tax rows/formatting and stored data."""
    copied = deepcopy(rows)
    for row in copied:
        if row.description == 'MVA 25 %':
            row.description = f"{frappe._('VAT')} 25 %"
    return copied


def bank_details(company, customer=None):
    """Respect the native customer's preferred company bank account and company default."""
    from erpnext.accounts.doctype.bank_account.bank_account import get_default_company_bank_account
    if customer:
        name = get_default_company_bank_account(company, "Customer", customer)
    else:
        name = frappe.db.get_value("Bank Account", {"company": company,
            "is_company_account": 1, "is_default": 1, "disabled": 0})
    if not name:
        return {}
    return frappe.db.get_value("Bank Account", {"name": name, "company": company,
        "is_company_account": 1, "disabled": 0}, ["bank_account_no", "iban"], as_dict=True) or {}


def preserve_submission(doc, method=None):
    if frappe.db.get_value("Company", doc.company, "country") != "Norway":
        return
    # The submission itself is transactional. A PDF failure prevents submission;
    # migrations never manufacture originals for previously submitted documents.
    language = doc.get("language") or "nb"
    filename = f"{doc.name}-{language}.pdf"
    selected = frappe.get_meta(doc.doctype).default_print_format or "Standard"
    with print_language(language):
        content = frappe.get_print(doc.doctype, doc.name, selected, doc=deepcopy(doc), as_pdf=True)
    save_file(filename, content, doc.doctype, doc.name, is_private=1)


def guard_quotation_rename(doc, method=None, *args, **kwargs):
    if doc.docstatus in (1, 2):
        frappe.throw(frappe._("The submitted document number must be retained."))
