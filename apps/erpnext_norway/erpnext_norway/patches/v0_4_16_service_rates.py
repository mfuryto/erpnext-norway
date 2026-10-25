"""Seed the missing low-rate native choice without recreating removed 25% masters."""
import frappe
from erpnext_norway.reverse_charge import seed


def execute():
    for name in frappe.get_all('Company', filters={'country': 'Norway'}, pluck='name'):
        seed(frappe.get_doc('Company', name), nominals=(12,))
