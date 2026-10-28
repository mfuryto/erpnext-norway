// Reuse Company's native selector and preserve explicit selections/existing companies.
function norway_default_chart(frm) {
	if (!frm.is_new() || frm.doc.create_chart_of_accounts_based_on === "Existing Company") return;
	const eligible = frm.doc.country === "Norway" && frm.doc.default_currency === "NOK";
	if (eligible && !frm.doc.chart_of_accounts) {
		frm.set_value("chart_of_accounts", "Norsk kontoplan");
	} else if (!eligible && frm.doc.chart_of_accounts === "Norsk kontoplan") {
		frm.set_value("chart_of_accounts", "");
	}
}
frappe.ui.form.on("Company", {
	onload: norway_default_chart,
	country: norway_default_chart,
	default_currency: norway_default_chart,
	create_chart_of_accounts_based_on: norway_default_chart,
});

frappe.ui.form.on("Company", {
 refresh(frm) {
  if (frm.is_new() || frm.doc.country !== "Norway" || !frappe.user.has_role("Accounts Manager")) return;
  frm.add_custom_button(__("Download SAF-T"), () => {
   const dialog = new frappe.ui.Dialog({title: __("Download SAF-T"), fields: [
    {fieldname:"from_date", label:__("From Date"), fieldtype:"Date", reqd:1},
    {fieldname:"to_date", label:__("To Date"), fieldtype:"Date", reqd:1}
   ], primary_action_label: __("Download"), primary_action(values) {
    const query = new URLSearchParams({...values, company:frm.doc.name});
    window.open("/api/method/erpnext_norway.saft.download?" + query.toString(), "_blank", "noopener");
    dialog.hide();
   }});
   dialog.show();
  });
 }
});
