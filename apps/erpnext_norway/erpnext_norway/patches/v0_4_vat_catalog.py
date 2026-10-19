"""One native patch for existing explicitly registered Norwegian companies."""
import frappe


def execute():
    from erpnext_norway.vat_catalog import configure_fields, seed
    from erpnext_norway.vat import STATUS, CONFIGURED, configure
    configure()
    if not frappe.db.has_column('Company', STATUS):
        return
    for name in frappe.get_all('Company', filters={'country': 'Norway', STATUS: 'Registered'}, pluck='name'):
        seed(frappe.get_doc('Company', name), upgrade=True)
        frappe.db.set_value('Company', name, CONFIGURED, 1, update_modified=False)
