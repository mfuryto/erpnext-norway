// Configure native item tax templates/rows; native controller calculates all amounts.
async function norway_vat_preview(frm, options = {}) {
    if (frm.doc.docstatus || !frm.doc.company || frm.updating_party_details || frm.__norway_vat_applying) return;
    if (frm.__norway_vat_preview) {
        frm.__norway_vat_pending = options;
        return;
    }
    if (!frm.doc.items.some(row => row.item_tax_template ||
        (row.custom_norway_deduction_percent != null && row.custom_norway_deduction_percent !== 100))) return;
    frm.__norway_vat_preview = true;
    try {
        const { message } = await frappe.call({
            method: 'erpnext_norway.vat_catalog.preview_items',
            args: { document: JSON.stringify(frm.doc), deduction_row: options.deduction_row, template_row: options.template_row },
        });
        // A user edit during the request wins over the older response.
        if (frm.__norway_vat_pending) return;
        frm.__norway_vat_applying = true;
        for (const row of message.items) {
            const current = locals[frm.doc.items[0].doctype]?.[row.name];
            if (!current) continue;
            if (row.custom_norway_deduction_percent != null &&
                current.custom_norway_deduction_percent !== row.custom_norway_deduction_percent) {
                await frappe.model.set_value(current.doctype, current.name,
                    'custom_norway_deduction_percent', row.custom_norway_deduction_percent);
            }
            if (current.item_tax_template !== row.item_tax_template) {
                await frappe.model.set_value(current.doctype, current.name, 'item_tax_template', row.item_tax_template);
            }
        }
        for (const tax of message.taxes) {
            if (!frm.doc.taxes.some(row => row.account_head === tax.account_head)) {
                const { name, parent, parenttype, parentfield, idx, ...values } = tax;
                frm.add_child('taxes', values);
            }
        }
        frm.refresh_field('items');
        frm.refresh_field('taxes');
        frm.cscript.calculate_taxes_and_totals();
    } finally {
        frm.__norway_vat_applying = false;
        frm.__norway_vat_preview = false;
        if (frm.__norway_vat_pending) {
            const pending = frm.__norway_vat_pending;
            delete frm.__norway_vat_pending;
            await norway_vat_preview(frm, pending);
        }
    }
}
frappe.ui.form.on('Purchase Invoice Item', {
    custom_norway_deduction_percent: (frm, cdt, cdn) => norway_vat_preview(frm, {deduction_row: cdn}),
    item_tax_template: (frm, cdt, cdn) => norway_vat_preview(frm, {template_row: cdn}),
    expense_account: frm => norway_vat_preview(frm),
});
frappe.ui.form.on('Sales Invoice Item', { item_tax_template: frm => norway_vat_preview(frm) });
