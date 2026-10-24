"""Native desktop/workspace/catalogue coverage and reversible synthetic desktop modes."""
import json
import os
from pathlib import Path
import sys

import frappe
from frappe.translate import get_all_translations

os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting', sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.local.lang = 'nb'
MODE = 'runtime_language_desktop_mode_before'
IDENTICAL = {'ERPNext', 'Frappe', 'System', 'Data', 'Bank', 'Portal', 'Google',
             'Webhook', 'IRS 1099', 'FIFO', 'API', 'SMS'}
try:
    action = sys.argv[1] if len(sys.argv) > 1 else 'catalog'
    if action in ('desktop', 'restore-desktop'):
        from frappe.desk.doctype.desktop_settings.desktop_settings import seed_desktop_icons
        if action == 'desktop':
            # This synthetic UI account opens every standard module's reports.
            # Core report permissions do not inherit Sales/Purchase roles from
            # System Manager. Production users are never changed by this test.
            manager = frappe.get_doc('User', 'runtime-ui-manager@example.invalid')
            manager.add_roles(*[role for role in ('Sales User', 'Sales Manager',
                'Purchase User', 'Purchase Manager', 'Manufacturing User',
                'Manufacturing Manager', 'Projects User', 'Projects Manager',
                'Quality Manager', 'Support Team') if frappe.db.exists('Role', role)])
            if not frappe.db.get_default(MODE):
                frappe.db.set_default(MODE, frappe.db.get_single_value('Desktop Settings', 'desktop_page', cache=False) or 'Apps')
            frappe.db.set_single_value('Desktop Settings', 'desktop_page', 'Desktop Icons')
            frappe.db.value_cache.clear()
            seed_desktop_icons()  # Native fixtures, not replacement tiles or renamed data.
        else:
            frappe.db.set_single_value('Desktop Settings', 'desktop_page', frappe.db.get_default(MODE) or 'Apps')
            frappe.db.set_default(MODE, None)
        frappe.clear_cache()
        frappe.db.commit()
        print('PASS synthetic native desktop mode:', action)
    else:
        catalog = get_all_translations('nb')
        missing = []
        checked = set()

        def check(text, place):
            if not isinstance(text, str) or not text.strip() or not any(c.isalpha() for c in text):
                return
            checked.add(text)
            translated = catalog.get(text)
            if text not in IDENTICAL and (not translated or translated == text):
                missing.append((place, text))

        def visit(value, place):
            if isinstance(value, list):
                for row in value:
                    visit(row, place)
            elif isinstance(value, dict):
                for key, text in value.items():
                    if key in ('title', 'label', 'description', 'action_label', 'subtitle',
                               'chart_name', 'empty_state_message'):
                        check(text, place + ':' + key)
                    elif isinstance(text, (dict, list)):
                        visit(text, place)
                    elif key == 'content' and isinstance(text, str):
                        try:
                            visit(json.loads(text), place)
                        except (ValueError, TypeError):
                            pass

        # Read shipped definitions too: Apps mode does not populate Desktop Icon
        # database rows, and metadata-only tests miss report links and empty charts.
        kinds = {'desktop_icon', 'sidebar', 'dock', 'workspace', 'dashboard_chart',
                 'number_card', 'onboarding_step', 'module_onboarding'}
        for app in ('frappe', 'erpnext'):
            root = Path(frappe.get_app_path(app))
            for path in root.rglob('*.json'):
                relative = path.relative_to(root)
                if 'doctype' not in relative.parts and kinds.intersection(relative.parts):
                    visit(json.loads(path.read_text()), str(relative))
        assert not missing, missing
        from frappe.desk.doctype.onboarding_step.onboarding_step import get_step_details
        step = get_step_details('Chart of Accounts')
        assert step.title == 'Kontroller kontoplanen', step
        assert step.action_label == 'Åpne kontoplan', step
        assert '[Kontoplan](' in step.description
        assert frappe._('Payment Reconciliation') == 'Betalingsavstemming'
        assert frappe._('Accounts Receivable Summary') == 'Oversikt over kundefordringer'
        print(f'PASS {len(checked)} native desktop/workspace/onboarding/chart texts and translated onboarding API; stored definitions unchanged')
finally:
    frappe.destroy()
