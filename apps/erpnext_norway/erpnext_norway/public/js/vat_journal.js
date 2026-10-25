function norway_import_reference_labels(frm) {
    if (!frm.__norway_reference_labels) {
        frm.__norway_reference_labels = Object.fromEntries(
            ['bill_date', 'bill_no'].map(field => [field, frm.fields_dict[field].df.label]));
    }
    const imported = (frm.doc.accounts || []).some(row =>
        ['81', '82', '83', '84'].includes(row.custom_norway_vat_code));
    for (const [field, label] of [['bill_date', 'Customs expedition date'], ['bill_no', 'Customs declaration reference']]) {
        frm.set_df_property(field, 'label', imported ? __(label) : frm.__norway_reference_labels[field]);
    }
}
frappe.ui.form.on('Journal Entry', {
    refresh(frm) {
        norway_import_reference_labels(frm);
        if (frm.doc.docstatus === 1 && frm.doc.custom_norway_vat_settlement) {
            frm.add_custom_button(__('Create VAT payment or refund'), () => {
                frappe.model.open_mapped_doc({method:'erpnext_norway.vat_settlement.make_payment',frm});
            });
        }
    },
});

frappe.ui.form.on('Journal Entry Account', {custom_norway_vat_code: norway_import_reference_labels});
