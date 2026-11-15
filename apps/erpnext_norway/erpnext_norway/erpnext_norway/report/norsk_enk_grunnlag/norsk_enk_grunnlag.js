frappe.query_reports["Norsk ENK-grunnlag"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
            default: frappe.defaults.get_user_default("Company")},
        {fieldname: "fiscal_year", label: __("Fiscal Year"), fieldtype: "Link", options: "Fiscal Year", reqd: 1,
            default: "2026"},
        {fieldname: "show_accounts", label: __("Show account detail"), fieldtype: "Check", default: 1}
    ]
};
