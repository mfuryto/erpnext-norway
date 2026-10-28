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
   ], primary_action_label: __("Download", null, "Norway SAF-T"), async primary_action(values) {
    const button = dialog.get_primary_btn();
    button.prop("disabled", true);
    try {
     const query = new URLSearchParams({...values, company:frm.doc.name});
     const response = await fetch("/api/method/erpnext_norway.saft.download?" + query.toString());
     if (!response.ok) {
      // Render the native server messages, including links to the Account form.
      frappe.request.cleanup({}, await response.json());
      return;
     }
     const disposition = response.headers.get("Content-Disposition") || "";
     const filename = disposition.match(/filename="?([^";]+)/)?.[1] || "SAF-T.xml";
     const link = document.createElement("a");
     const url = URL.createObjectURL(await response.blob());
     link.href = url;
     link.download = filename;
     document.body.appendChild(link);
     link.click();
     link.remove();
     setTimeout(() => URL.revokeObjectURL(url), 1000);
     dialog.hide();
    } catch (error) {
     frappe.msgprint({message: __("Unable to download SAF-T."), indicator: "red"});
    } finally {
     button.prop("disabled", false);
    }
   }});
   dialog.show();
  });
 }
});
