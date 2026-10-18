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
