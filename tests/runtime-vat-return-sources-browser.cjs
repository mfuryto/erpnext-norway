// Ordinary owner chooses an existing native receipt-row reference in the credit form.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const base = process.env.ERP_LANGUAGE_TEST_URL;
    assert.match(base || '', /^http:\/\/127\.0\.0\.1:\d+$/);
    const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
    try {
        const context = await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
        assert.equal((await context.request.post('/api/method/login',{form:{
            usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}})).status(),200);
        const list = async (type, filters) => (await (await context.request.get(
            `/api/resource/${encodeURIComponent(type)}?filters=${encodeURIComponent(JSON.stringify(filters))}`)).json()).data;
        const get = async (type, name) => (await (await context.request.get(
            `/api/resource/${encodeURIComponent(type)}/${encodeURIComponent(name)}`)).json()).data;
        const invoices = await list('Purchase Invoice',{company:'Runtime VAT Valuation',
            bill_no:'SYNTHETIC-SPLIT-SOURCE',docstatus:1,is_return:0});
        const invoice = await get('Purchase Invoice',invoices[0].name);
        const returns = await list('Purchase Receipt',{return_against:invoice.items[0].purchase_receipt,
            docstatus:1,is_return:1});
        const receipt = await get('Purchase Receipt',returns[0].name);
        const page = await context.newPage();
        page.setDefaultTimeout(60000);
        await page.goto(`/app/purchase-invoice/${encodeURIComponent(invoice.name)}`);
        await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice'&&!frappe.request.ajax_count);
        const csrf = await page.evaluate(()=>frappe.csrf_token);
        const response = await context.request.post('/api/method/erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_debit_note',{
            data:{source_name:invoice.name},headers:{'X-Frappe-CSRF-Token':csrf}});
        assert.equal(response.status(),200);
        const draft = (await response.json()).message;
        draft.set_posting_time=1;draft.posting_date=draft.bill_date='2026-10-19';
        draft.bill_no='SYNTHETIC-BROWSER-RETURN-SOURCE';
        draft.items[0].qty=draft.items[0].received_qty=-1;
        draft.items[0].purchase_receipt=receipt.name;
        draft.items[0].pr_detail=receipt.items[0].name;
        await page.evaluate(doc=>{
            const [mapped]=frappe.model.sync(doc);
            frappe.set_route('Form',mapped.doctype,mapped.name);
        },draft);
        await page.waitForFunction(()=>window.cur_frm?.doc.is_return===1&&
            !cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===-312.5);
        await page.evaluate(()=>{
            const row=cur_frm.doc.items[0];
            cur_frm.fields_dict.items.grid.grid_rows_by_docname[row.name].toggle_view(true);
        });
        await page.waitForFunction(()=>{
            const grid=cur_frm.fields_dict.items.grid;
            return grid.grid_rows_by_docname[cur_frm.doc.items[0].name].grid_form
                ?.fields_dict.pr_detail?.get_data?.().length===2;
        });
        const input=page.locator('.grid-row-open [data-fieldname="pr_detail"] input').last();
        await input.fill('Kildelinje 2');
        await input.press('ArrowDown');
        await input.press('Enter');
        await input.press('Tab');
        await page.waitForFunction(name=>cur_frm.doc.items[0].pr_detail===name&&
            !cur_frm.__norway_vat_preview&&!frappe.request.ajax_count,receipt.items[1].name);
        assert.equal(await page.evaluate(()=>frappe.user_roles.includes('System Manager')),false);
        assert.equal(await page.evaluate(()=>cur_frm.doc.grand_total),-312.5);
        await page.evaluate(()=>{
            const row=cur_frm.doc.items[0];
            cur_frm.fields_dict.items.grid.grid_rows_by_docname[row.name].toggle_view(false);
        });
        await page.getByRole('button',{name:'Lagre',exact:true}).click();
        await page.waitForFunction(()=>!cur_frm.is_new()&&!frappe.request.ajax_count);
        const name=await page.evaluate(()=>cur_frm.doc.name);
        const saved=await get('Purchase Invoice',name);
        assert.equal(saved.items[0].pr_detail,receipt.items[1].name);
        assert.equal(saved.items[0].purchase_receipt,receipt.name);
        assert.equal(saved.items[0].custom_norway_deduction_percent,60);
        assert.equal((await context.request.delete(`/api/resource/Purchase%20Invoice/${encodeURIComponent(name)}`,
            {headers:{'X-Frappe-CSRF-Token':csrf}})).status(),202);
        console.log('PASS ordinary owner native credit receipt-row autocomplete: both source rows, Norwegian labels, explicit row retained through preview and draft save');
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exit(1);});
