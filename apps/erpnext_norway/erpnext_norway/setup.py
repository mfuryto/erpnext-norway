"""Configure native features without importing business data or resetting choices."""
import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from erpnext_norway.numbering import RULES
from erpnext_norway.preservation import RETAINED


def configure():
    from erpnext_norway.saft import configure as configure_saft
    configure_saft()
    from erpnext_norway.vat import configure as configure_vat
    configure_vat()
    from erpnext_norway.tax_names import configure as configure_tax_names
    configure_tax_names()
    for doctype in RETAINED:
        if not frappe.get_meta(doctype).protect_attached_files:
            make_property_setter(doctype, None, "protect_attached_files", 1, "Check", for_doctype=True)
    # Never retrofit counters onto a used register or override existing native rules.
    for name, (doctype, prefix, digits, conditions) in RULES.items():
        if frappe.db.exists("Document Naming Rule", name):
            continue
        if frappe.db.exists(doctype, {}) or frappe.db.exists("Document Naming Rule", {"document_type": doctype}):
            continue
        # The sales and credit rules form one pair; install both together below.
        group = [(key, spec) for key, spec in RULES.items() if spec[0] == doctype]
        for key, (_, rule_prefix, rule_digits, rule_conditions) in group:
            frappe.get_doc({
                "doctype": "Document Naming Rule", "document_type": doctype,
                "prefix": rule_prefix, "prefix_digits": rule_digits, "counter": 0, "priority": 100,
                "conditions": [{"field": field, "condition": "=", "value": value} for field, value in rule_conditions],
            }).insert(set_name=key)
    from erpnext_norway.printing import configure as configure_printing
    configure_printing()
    frappe.clear_cache()
