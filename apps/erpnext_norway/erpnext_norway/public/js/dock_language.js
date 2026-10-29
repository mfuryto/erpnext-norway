// The pinned dock resolves stored labels without calling the native translator.
// Translate only the resolved display label; keep core routes and user ordering.
if (frappe.boot.lang === 'nb' && frappe.ui.Sidebar?.prototype.dock_entry) {
    const resolve = frappe.ui.Sidebar.prototype.dock_entry;
    frappe.ui.Sidebar.prototype.dock_entry = function (row) {
        const entry = resolve.call(this, row);
        if (entry) entry.label = __(entry.label);
        return entry;
    };
}
