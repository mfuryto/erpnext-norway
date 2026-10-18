"""Native navigation defaults and explicit later opt-in, on a synthetic site."""
import os
import runpy

import frappe
from frappe.utils.modules import get_blocked_modules, is_module_visible
from frappe.desk.doctype.sidebar.sidebar import get_navigable_modules
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def verify():
    namespace = runpy.run_path("/opt/runtime/module-visibility.py")
    apply_defaults = namespace["apply_defaults"]
    profile_name = namespace["PROFILE"]
    modules = set(namespace["MODULES"])
    assert frappe.get_meta("User").get_field("module_profile").default == profile_name
    assert modules <= set(get_blocked_modules("Administrator"))
    assert all(not is_module_visible(module, "Administrator") for module in modules)
    assert not modules.intersection(get_navigable_modules())
    assert is_module_visible("Accounts", "Administrator")
    assert is_module_visible("Stock", "Administrator")
    assert frappe.has_permission("Stock Entry", "create", user="Administrator")

    # New users get the native default, including when created through get_doc.
    user = frappe.get_doc({
        "doctype": "User", "email": "runtime-modules@example.invalid",
        "first_name": "Runtime", "user_type": "System User", "send_welcome_email": 0,
        "roles": [{"role": "System Manager"}],
    }).insert()
    assert user.module_profile == profile_name
    assert modules <= set(get_blocked_modules(user.name))

    # A user can choose a personal module selection instead of the shared profile.
    user.module_profile = None
    user.set("block_modules", [{"module": name} for name in sorted(modules - {"Projects"})])
    user.save()
    assert is_module_visible("Projects", user.name)
    assert not is_module_visible("Manufacturing", user.name)
    apply_defaults()
    apply_defaults()
    user.reload()
    assert not user.module_profile
    assert is_module_visible("Projects", user.name)
    assert not is_module_visible("Manufacturing", user.name)

    # Editing the shared profile is also retained by later setup runs.
    profile = frappe.get_doc("Module Profile", profile_name)
    original = [row.module for row in profile.block_modules]
    profile.set("block_modules", [{"module": name} for name in original if name != "Projects"])
    profile.save()
    profile.update_all_users()
    apply_defaults()
    assert is_module_visible("Projects", "Administrator")
    # The exact old standard is migrated once; customised profiles are retained.
    profile.set("block_modules", [{"module": name} for name in [*original, "Stock"]])
    profile.save()
    frappe.db.set_default(namespace["STOCK_VISIBLE_MARKER"], None)
    apply_defaults()
    assert is_module_visible("Stock", "Administrator")
    profile.reload()
    profile.set("block_modules", [{"module": name} for name in [*original, "Stock"]])
    profile.save()
    apply_defaults()
    assert not is_module_visible("Stock", "Administrator")
    profile.set("block_modules", [{"module": name} for name in [*original, "Stock", "Buying"]])
    profile.save()
    frappe.db.set_default(namespace["STOCK_VISIBLE_MARKER"], None)
    apply_defaults()
    profile.reload()
    assert {row.module for row in profile.block_modules} == {*original, "Stock", "Buying"}
    profile.set("block_modules", [{"module": name} for name in original])
    profile.save()
    apply_defaults()
    # Return the synthetic default to its original state for recovery assertions.
    profile.set("block_modules", [{"module": name} for name in original])
    profile.save()
    profile.update_all_users()
    # Removing the new-user default later is an explicit choice too.
    make_property_setter("User", "module_profile", "default", "", "Data")
    frappe.clear_cache(doctype="User")
    apply_defaults()
    assert not frappe.get_meta("User").get_field("module_profile").default
    make_property_setter("User", "module_profile", "default", profile_name, "Data")
    frappe.clear_cache(doctype="User")
    frappe.db.commit()
    print("PASS native module hiding, Stock migration, new-user default and preserved later choices")


os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="accounting", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
# Native Module Profile normally queues propagation. Workers are intentionally
# stopped for recovery, so use Frappe's synchronous test mode for these edits.
frappe.flags.in_test = True
try:
    verify()
finally:
    frappe.destroy()
