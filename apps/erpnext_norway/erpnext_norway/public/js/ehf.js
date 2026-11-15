frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.custom_norway_invoice_delivery === 'EHF'
                && frm.doc.custom_norway_ehf_xml) {
            frm.dashboard.set_headline_alert(__('EHF XML is prepared. Delivery has not been confirmed.'), 'blue');
        }
    }
});
