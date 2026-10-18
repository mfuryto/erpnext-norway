#!/usr/bin/env python3
"""Restore native module visibility after withdrawing the Norwegian hiding default."""
import os

import frappe

PROFILE = "Norsk standard"
MODULES = ("Stock", "Manufacturing", "Projects", "Quality Management")
RESTORED_MARKER = "erpnext_norway_native_modules_restored_v1"


def apply_defaults():
    # One transition only: subsequent personal/admin choices belong to the site.
    if frappe.db.get_default(RESTORED_MARKER):
        return 0, 0
    applied = preserved = 0
    if frappe.db.exists("Module Profile", PROFILE):
        profile = frappe.get_doc("Module Profile", PROFILE)
        profile.set("block_modules", [row for row in profile.block_modules if row.module not in MODULES])
        profile.save()
    for name in frappe.get_all("Property Setter", filters={
        "doc_type": "User", "field_name": "module_profile", "property": "default", "value": PROFILE,
    }, pluck="name"):
        frappe.delete_doc("Property Setter", name)
    frappe.clear_cache(doctype="User")
    for name in frappe.get_all("User", filters={"user_type": "System User"}, pluck="name"):
        user = frappe.get_doc("User", name)
        # Also clear copied personal blocks for these four modules on this transition.
        # A different explicitly configured profile remains under site control.
        if user.module_profile == PROFILE or (not user.module_profile and
                any(row.module in MODULES for row in user.block_modules)):
            user.module_profile = None
            user.set("block_modules", [row for row in user.block_modules if row.module not in MODULES])
            user.save()
            frappe.clear_cache(user=name)
            applied += 1
        else:
            preserved += 1
    frappe.db.set_default(RESTORED_MARKER, "1")
    return applied, preserved


def main():
    os.chdir("/home/frappe/frappe-bench/sites")
    frappe.init(site="accounting", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    frappe.set_user("Administrator")
    try:
        applied, preserved = apply_defaults()
        frappe.db.commit()
        print(f"Native module defaults restored for {applied} users; other choices retained for {preserved}.")
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == "__main__":
    main()
