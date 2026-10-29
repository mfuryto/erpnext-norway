"""Translate display-only dock titles through the ordinary session boot hook."""
from copy import deepcopy

import frappe
from frappe.translate import get_user_lang


def localize_dock(bootinfo):
    if get_user_lang() != 'nb':
        return
    # Work on the response, not the cached/stored configuration. The core still
    # resolves visibility, ordering, icons and routes from unchanged identifiers.
    apps = deepcopy(bootinfo.get('app_data') or [])
    dock = deepcopy(bootinfo.get('dock') or {})
    rows = [row for app in apps for row in app.get('dock') or []]
    rows.extend(row for entries in dock.values() for row in entries)
    for row in rows:
        if row.get('title'):
            row['title'] = frappe._(row['title'], lang='nb')
    bootinfo.app_data = apps
    bootinfo.dock = dock
