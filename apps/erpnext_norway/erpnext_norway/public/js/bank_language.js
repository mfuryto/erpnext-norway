// Core's intro inserts an English link label without translating the parameter.
// Use the native form-intro API and keep the same destination and action.
frappe.ui.form.on('Bank Reconciliation Tool', {
    refresh(frm) {
        if (frappe.boot.lang !== 'nb') return;
        const link = `<a href="/banking">${__('new Banking module')}</a>`;
        frm.set_intro(__('Try the {0} for a better experience.', [link]), 'info');
    },
});
