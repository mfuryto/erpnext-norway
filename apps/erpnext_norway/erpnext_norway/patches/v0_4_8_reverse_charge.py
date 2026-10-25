import frappe
from erpnext_norway.reverse_charge import seed


def execute():
    for name in frappe.get_all('Company', filters={'country': 'Norway'}, pluck='name'):
        seed(frappe.get_doc('Company', name))
