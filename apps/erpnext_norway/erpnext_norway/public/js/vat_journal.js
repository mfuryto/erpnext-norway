frappe.ui.form.on('Journal Entry', {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.custom_norway_vat_settlement) {
            frm.add_custom_button(__('Create VAT payment or refund'), () => {
                frappe.model.open_mapped_doc({method:'erpnext_norway.vat_settlement.make_payment',frm});
            });
        }
    },
});
