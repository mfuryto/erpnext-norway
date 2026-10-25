// Core resolver: provide a basis, leave rates/rounding/totals to ERPNext.
erpnext.taxable_base_resolvers = erpnext.taxable_base_resolvers || {};
erpnext.taxable_base_resolvers['On Norwegian VAT Base'] = (calc, item) =>
    flt(item.net_amount) * flt(item.custom_norway_vat_exchange_rate) / flt(calc.frm.doc.conversion_rate);

// Configure native item tax templates/rows; native controller calculates all amounts.
async function norway_vat_preview(frm, options = {}) {
    if (frm.doc.docstatus || !frm.doc.company || frm.updating_party_details || frm.__norway_vat_applying) return;
    if (frm.__norway_vat_preview) {
        frm.__norway_vat_pending = options;
        return;
    }
    if (frm.doc.taxes?.some(row => !row.account_head || !row.charge_type ||
        (row.charge_type.startsWith('On Previous Row') && !row.row_id))) return;
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
        if (message.pending_currency) return;
        frm.__norway_vat_applying = true;
        if (message.return_type && frm.fields_dict.custom_norway_vat_return_type && frm.doc.custom_norway_vat_return_type !== message.return_type) {
            await frm.set_value('custom_norway_vat_return_type', message.return_type);
        }
        for (const name of message.removed_taxes || []) {
            const tax = frm.doc.taxes.find(row => row.name === name);
            if (tax?.set_by_item_tax_template) {
                frappe.model.clear_doc(tax.doctype, tax.name);
                frm.dirty();
            }
        }
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
            for (const field of ['custom_norway_quarterly_service', 'custom_norway_vat_delivery_date', 'custom_norway_vat_exchange_rate', 'custom_norway_vat_code', 'custom_norway_vat_rate',
                'purchase_invoice', 'purchase_invoice_item', 'purchase_receipt', 'pr_detail']) {
                if (Object.hasOwn(row, field) && frappe.meta.get_docfield(current.doctype, field, frm.doc.name) &&
                    (current[field] || null) !== (row[field] || null)) {
                    await frappe.model.set_value(current.doctype, current.name, field, row[field]);
                }
            }
        }
        for (const tax of message.taxes) {
            const current = frm.doc.taxes.find(row => row.name === tax.name || row.account_head === tax.account_head &&
                row.charge_type === tax.charge_type &&
                (!tax.charge_type.startsWith('On Previous Row') ||
                    String(row.row_id || '') === String(tax.row_id || '')));
            if (!current) {
                const { name, parent, parenttype, parentfield, idx, ...values } = tax;
                frm.add_child('taxes', values);
            } else if (tax.custom_norway_vat_cost || tax.set_by_item_tax_template || current.row_id !== tax.row_id) {
                for (const field of ['category', 'included_in_print_rate', 'add_deduct_tax', 'row_id', 'charge_type']) {
                    if (!frappe.meta.get_docfield(current.doctype, field, frm.doc.name)) continue;
                    if (current[field] !== tax[field]) {
                        await frappe.model.set_value(current.doctype, current.name, field, tax[field]);
                    }
                }
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
    custom_norway_quarterly_service: frm => norway_vat_preview(frm),
    custom_norway_import_date: frm => norway_vat_preview(frm),
    custom_norway_vat_delivery_date: frm => norway_vat_preview(frm),
    custom_norway_vat_exchange_rate: frm => norway_vat_preview(frm),
});
}
for (const child of ['Quotation Item', 'Sales Order Item', 'Delivery Note Item', 'Sales Invoice Item']) {
    frappe.ui.form.on(child, { item_tax_template: frm => norway_vat_preview(frm) });
}

for (const parent of ['Quotation', 'Sales Order', 'Delivery Note', 'Sales Invoice']) {
    frappe.ui.form.on(parent, { refresh: frm => norway_vat_preview(frm) });
}
for (const parent of ['Purchase Invoice', 'Purchase Receipt']) {
    frappe.ui.form.on(parent, { refresh: frm => {
        if (!frm.doc.is_return || frm.doc.docstatus) return;
        if (parent !== 'Sales Invoice') frm.fields_dict.items.grid.update_docfield_property('custom_norway_deduction_percent', 'read_only', 1);
        for (const field of ['custom_norway_quarterly_service', 'custom_norway_vat_delivery_date', 'custom_norway_vat_exchange_rate']) {
            if (frappe.meta.get_docfield(frm.fields_dict.items.df.options, field, frm.doc.name)) frm.fields_dict.items.grid.update_docfield_property(field, 'read_only', 1);
        }
        const field = parent === 'Purchase Receipt' ? 'purchase_invoice' :
            parent === 'Purchase Invoice' ? 'purchase_receipt' : null;
        if (field) {
            const grid = frm.fields_dict.items.grid;
            grid.update_docfield_property(field, 'read_only', 0);
            if (parent === 'Purchase Invoice') {
                for (const [property, value] of Object.entries({fieldtype: 'Autocomplete', hidden: 0, read_only: 0, options: []})) {
                    grid.update_docfield_property('pr_detail', property, value);
                }
            }
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
    await norway_return_receipt_options(frm, cdt, cdn);
    return norway_vat_preview(frm);
}});

for (const child of ['Purchase Receipt Item', 'Purchase Invoice Item']) {
    frappe.ui.form.on(child, { qty: frm => {
        if (frm.doc.is_return) return norway_vat_preview(frm);
    }});
}

// The native receipt row reference uses Frappe's standard autocomplete on credits.
async function norway_return_receipt_options(frm, cdt, cdn) {
    if (!frm.doc.is_return || frm.doc.docstatus) return;
    const item = locals[cdt][cdn];
    const name = item.purchase_receipt;
    let options = [];
    if (name) {
        await frappe.model.with_doc('Purchase Receipt', name);
        await frappe.model.with_doc('Purchase Invoice', frm.doc.return_against);
        const receipt = frappe.get_doc('Purchase Receipt', name);
        const original = frappe.get_doc('Purchase Invoice', frm.doc.return_against).items
            .find(row => row.name === item.purchase_invoice_item);
        if (original && receipt.docstatus === 1 && receipt.is_return &&
            receipt.company === frm.doc.company && receipt.supplier === frm.doc.supplier) {
            options = receipt.items.filter(row => row.purchase_receipt_item === original.pr_detail &&
                (!row.purchase_invoice_item || row.purchase_invoice_item === original.name))
                .map(row => ({value: row.name, label: __('Source row {0}', [row.idx]),
                    description: __('Quantity: {0}; input VAT deduction: {1} %',
                        [row.qty, row.custom_norway_deduction_percent ?? 100])}));
        }
    }
    if (item.purchase_receipt !== name) return;
    const gridRow = frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
    const definition = gridRow?.docfields.find(df => df.fieldname === 'pr_detail');
    if (definition) definition.options = options;
    const control = gridRow?.grid_form?.fields_dict.pr_detail;
    if (control?.set_data) {
        control.set_data(options);
        control.refresh();
    }
}
frappe.ui.form.on('Purchase Invoice Item', {
    form_render: norway_return_receipt_options,
    pr_detail: frm => {
        if (frm.doc.is_return && !frm.__norway_vat_applying) return norway_vat_preview(frm);
    },
});

for (const child of ['Sales Taxes and Charges', 'Purchase Taxes and Charges']) {
frappe.ui.form.on(child, Object.fromEntries(
    ['charge_type', 'row_id', 'account_head', 'rate', 'tax_amount', 'included_in_print_rate']
        .map(field => [field, frm => norway_vat_preview(frm)])));
}
