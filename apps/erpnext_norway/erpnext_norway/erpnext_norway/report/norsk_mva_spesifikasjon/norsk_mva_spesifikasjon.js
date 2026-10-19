frappe.query_reports['Norsk MVA-spesifikasjon'] = {
    onload(report) {
        const period = () => {
            const values = report.get_filter_values(true);
            return {company:values.company,from_date:values.from_date,to_date:values.to_date};
        };
        report.page.add_inner_button(__('Preserve VAT basis'), async () => {
            const {message} = await frappe.call({method:'erpnext_norway.vat_evidence.preserve_basis',args:period()});
            frappe.set_route('Form','File',message.name);
        });
        report.page.add_inner_button(__('Create VAT settlement'), async () => {
            const {message} = await frappe.call({method:'erpnext_norway.vat_settlement.make_settlement',args:period()});
            frappe.model.sync(message);
            frappe.set_route('Form','Journal Entry',message.name);
        });
        const upload = (kind) => {
            const values = period();
            new frappe.ui.FileUploader({doctype:'Company',docname:values.company,
                make_attachments_public:false,allow_toggle_private:false,allow_web_link:false,
                on_success:async file => {
                    const {message} = await frappe.call({method:'erpnext_norway.vat_evidence.preserve_uploaded',
                        args:{...values,file_name:file.name,kind}});
                    frappe.set_route('Form','File',message.name);
                },
            });
        };
        report.page.add_inner_button(__('Attach submitted VAT return'), () => upload('Submitted VAT return'));
        report.page.add_inner_button(__('Attach VAT receipt'), () => upload('VAT receipt'));
        report.page.add_inner_button(__('VAT documents'), () => {
            const values = period();
            frappe.set_route('List','File',{attached_to_doctype:'Company',attached_to_name:values.company,
                custom_norway_retained_vat_evidence:1,custom_norway_vat_period_from:values.from_date,
                custom_norway_vat_period_to:values.to_date});
        });
    },
    filters: [
        {fieldname:'company',label:__('Company'),fieldtype:'Link',options:'Company',reqd:1,
            default:frappe.defaults.get_user_default('Company')},
        {fieldname:'from_date',label:__('From Date'),fieldtype:'Date',reqd:1,
            default:frappe.datetime.year_start()},
        {fieldname:'to_date',label:__('To Date'),fieldtype:'Date',reqd:1,
            default:frappe.datetime.get_today()},
        {fieldname:'group_by_code',label:__('Group by Norwegian VAT code'),fieldtype:'Check',default:1},
    ],
};
