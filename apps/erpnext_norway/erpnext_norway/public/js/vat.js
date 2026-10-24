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
            for (const field of ['custom_norway_vat_code', 'custom_norway_vat_rate',
                'purchase_invoice', 'purchase_invoice_item', 'purchase_receipt', 'pr_detail']) {
                if (Object.hasOwn(row, field) && frappe.meta.get_docfield(current.doctype, field, frm.doc.name) &&
                    (current[field] || null) !== (row[field] || null)) {
                    await frappe.model.set_value(current.doctype, current.name, field, row[field]);
                }
            }
        }
        for (const tax of message.taxes) {
            if (!frm.doc.taxes.some(row => row.account_head === tax.account_head &&
                row.charge_type === tax.charge_type &&
                (!tax.charge_type.startsWith('On Previous Row') ||
                    String(row.row_id || '') === String(tax.row_id || '')))) {
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
for (const child of ['Purchase Invoice Item', 'Purchase Order Item', 'Purchase Receipt Item']) {
frappe.ui.form.on(child, {
    custom_norway_deduction_percent: (frm, cdt, cdn) => norway_vat_preview(frm, {deduction_row: cdn}),
    item_tax_template: (frm, cdt, cdn) => norway_vat_preview(frm, {template_row: cdn}),
    expense_account: frm => norway_vat_preview(frm),
});
}
frappe.ui.form.on('Sales Invoice Item', { item_tax_template: frm => norway_vat_preview(frm) });

for (const parent of ['Sales Invoice', 'Purchase Invoice', 'Purchase Receipt']) {
    frappe.ui.form.on(parent, { refresh: frm => {
        if (!frm.doc.is_return || frm.doc.docstatus) return;
        if (parent !== 'Sales Invoice') frm.fields_dict.items.grid.update_docfield_property('custom_norway_deduction_percent', 'read_only', 1);
        const field = parent === 'Purchase Receipt' ? 'purchase_invoice' :
            parent === 'Purchase Invoice' ? 'purchase_receipt' : null;
        if (field) {
            frm.fields_dict.items.grid.update_docfield_property(field, 'read_only', 0);
            frm.set_query(field, 'items', () => ({filters: {
                company: frm.doc.company, supplier: frm.doc.supplier, docstatus: 1,
                is_return: parent === 'Purchase Invoice' ? 1 : 0,
            }}));
        }
        return norway_vat_preview(frm);
    }});
}
frappe.ui.form.on('Purchase Receipt Item', { purchase_invoice: async (frm, cdt, cdn) => {
    if (!frm.doc.is_return || frm.__norway_vat_applying) return;
    await frappe.model.set_value(cdt, cdn, 'purchase_invoice_item', null);
    return norway_vat_preview(frm);
}});
frappe.ui.form.on('Purchase Invoice Item', { purchase_receipt: async (frm, cdt, cdn) => {
    if (!frm.doc.is_return || frm.__norway_vat_applying) return;
    await frappe.model.set_value(cdt, cdn, 'pr_detail', null);
    return norway_vat_preview(frm);
}});

for (const child of ['Purchase Receipt Item', 'Purchase Invoice Item']) {
    frappe.ui.form.on(child, { qty: frm => {
        if (frm.doc.is_return) return norway_vat_preview(frm);
    }});
}
