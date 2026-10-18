#!/usr/bin/env python3
"""Set native navigation defaults without changing roles or feature permissions.

Run inside the existing backend with: env/bin/python - < this-file
"""
import os

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


PROFILE = "Norsk standard"
MODULES = ("Stock", "Manufacturing", "Projects", "Quality Management")
MARKER = "erpnext_norway_module_visibility_initialized"
DEFAULT_MARKER = "erpnext_norway_module_default_initialized"


def apply_defaults():
    missing = [name for name in MODULES if not frappe.db.exists("Module Def", name)]
    if missing:
        raise RuntimeError(f"Expected ERPNext modules not found: {', '.join(missing)}")

    # An existing profile may have been edited deliberately. Never reset it.
    if not frappe.db.exists("Module Profile", PROFILE):
        frappe.get_doc({
            "doctype": "Module Profile", "module_profile_name": PROFILE,
            "block_modules": [{"module": name} for name in MODULES],
        }).insert()

    # Respect an administrator's existing non-empty default for new users.
    if not frappe.db.get_default(DEFAULT_MARKER):
        default = frappe.get_meta("User").get_field("module_profile").default
        if not default:
            make_property_setter("User", "module_profile", "default", PROFILE, "Data")
            frappe.clear_cache(doctype="User")
        frappe.db.set_default(DEFAULT_MARKER, "1")

    applied = preserved = 0
    for name in frappe.get_all("User", filters={"user_type": "System User"}, pluck="name"):
        if frappe.defaults.get_user_default(MARKER, user=name):
            preserved += 1
            continue
        user = frappe.get_doc("User", name)
        # Existing profiles and per-user choices belong to the user.
        if not user.module_profile and not user.block_modules:
            user.module_profile = PROFILE
            user.save()
            applied += 1
        else:
            preserved += 1
        frappe.defaults.set_user_default(MARKER, "1", user=name)
        frappe.clear_cache(user=name)
    return applied, preserved


def main():
    os.chdir("/home/frappe/frappe-bench/sites")
    frappe.init(site="accounting", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    frappe.set_user("Administrator")
    try:
        applied, preserved = apply_defaults()
        frappe.db.commit()
        print(f"Module visibility defaults applied to {applied} users; choices retained for {preserved}.")
        print("Use Module Profile / User settings to show modules later. Feature permissions are unchanged.")
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == "__main__":
    main()
