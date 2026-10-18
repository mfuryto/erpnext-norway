"""Native defaults and migration of the withdrawn module profile, synthetic only."""
import os
import runpy
import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils.modules import get_blocked_modules, is_module_visible
from frappe.desk.doctype.sidebar.sidebar import get_navigable_modules

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.flags.in_test = True
try:
    ns = runpy.run_path('/opt/runtime/module-visibility.py')
    restore, profile, modules = ns['apply_defaults'], ns['PROFILE'], set(ns['MODULES'])
    assert not modules.intersection(get_blocked_modules('Administrator'))
    assert modules <= set(get_navigable_modules())
    # Reproduce the old four-module profile, including its copied user rows/default.
    frappe.get_doc({'doctype': 'Module Profile', 'module_profile_name': profile,
        'block_modules': [{'module': m} for m in sorted(modules)]}).insert()
    make_property_setter('User', 'module_profile', 'default', profile, 'Data')
    frappe.clear_cache(doctype='User')
    user = frappe.get_doc({'doctype': 'User', 'email': 'runtime-modules@example.invalid',
        'first_name': 'Runtime', 'user_type': 'System User', 'send_welcome_email': 0,
        'roles': [{'role': 'System Manager'}]}).insert()
    admin = frappe.get_doc('User', 'Administrator')
    admin.module_profile = profile
    admin.save()
    assert modules <= set(get_blocked_modules(user.name))
    personal = frappe.get_doc({'doctype': 'User', 'email': 'runtime-personal-modules@example.invalid',
        'first_name': 'Personal', 'user_type': 'System User', 'send_welcome_email': 0,
        'roles': [{'role': 'System Manager'}]}).insert()
    personal.module_profile = None
    personal.set('block_modules', [{'module': 'Stock'}, {'module': 'Buying'}])
    personal.save()
    frappe.db.set_default(ns['RESTORED_MARKER'], None)
    restore()
    for name in ['Administrator', user.name]:
        assert not modules.intersection(get_blocked_modules(name)), name
        assert not frappe.get_doc('User', name).module_profile
    assert is_module_visible('Stock', personal.name)
    assert not is_module_visible('Buying', personal.name)
    assert not frappe.get_meta('User').get_field('module_profile').default
    assert modules <= set(get_navigable_modules())
    # New users retain native defaults; a subsequent personal choice survives reruns.
    later = frappe.get_doc({'doctype': 'User', 'email': 'runtime-native-modules@example.invalid',
        'first_name': 'Native', 'user_type': 'System User', 'send_welcome_email': 0,
        'roles': [{'role': 'System Manager'}]}).insert()
    assert not later.module_profile and not later.block_modules
    user.reload()
    user.set('block_modules', [{'module': 'Manufacturing'}])
    user.save()
    restore()
    assert not is_module_visible('Manufacturing', user.name)
    assert is_module_visible('Projects', user.name)
    assert is_module_visible('Stock', user.name)
    assert modules <= set(get_navigable_modules())
    frappe.db.commit()
    print('PASS all native modules visible; old profile/default removed; new users and later personal choices preserved')
finally:
    frappe.destroy()
