frappe.ui.form.on("Norwegian Tax Facts", {
    refresh(frm) {
        frm.set_query("asset_account", "pools", () => ({filters: {company: frm.doc.company, root_type: "Asset"}}));
        frm.set_query("account", "adjustments", () => ({filters: {company: frm.doc.company, root_type: "Expense", is_group: 0}}));
        frm.set_query("account", "tax_values", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        frm.set_query("account", "person_items", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        frm.set_query("asset", "pools", () => ({filters: {company: frm.doc.company}}));
        if (!frm.is_new()) {
            frm.add_custom_button(__("Norsk ENK-grunnlag"), () => frappe.set_route("query-report", "Norsk ENK-grunnlag", {
                company: frm.doc.company, fiscal_year: frm.doc.fiscal_year
            }));
        }
    }
});
