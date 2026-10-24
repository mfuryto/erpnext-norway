// Native purchase forms: existing valuation row changes when freight is added later.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const base=process.env.ERP_LANGUAGE_TEST_URL;
    assert.match(base || '',/^http:\/\/127\.0\.0\.1:\d+$/);
    const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    try {
        const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
        assert.equal((await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',
            pwd:'Synthetic-vat-owner-only-2026!'}})).status(),200);
        const query=encodeURIComponent(JSON.stringify({company:'Runtime VAT Valuation Mixed',
            bill_no:'SYNTHETIC-FREIGHT-RESTORE',docstatus:1,is_return:0}));
        const reference=(await (await context.request.get(`/api/resource/Purchase%20Invoice?filters=${query}`)).json()).data[0];
        const source=(await (await context.request.get(`/api/resource/Purchase%20Invoice/${encodeURIComponent(reference.name)}`)).json()).data;
        const page=await context.newPage();page.setDefaultTimeout(60000);
        for (const type of ['Purchase Invoice','Purchase Order','Purchase Receipt']) {
            const route=type.toLowerCase().replaceAll(' ','-');
            await page.goto(`/app/${route}/new-${route}`);
            await page.waitForFunction(type=>window.cur_frm?.doctype===type,type);
            const csrf=await page.evaluate(()=>frappe.csrf_token);
            await page.evaluate(async source=>{
                await cur_frm.set_value('company',source.company);
                await cur_frm.set_value('supplier',source.supplier);
            },source);
            await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count);
            await page.evaluate(async ({type,source})=>{
                if (type==='Purchase Order') {
                    await cur_frm.set_value('transaction_date','2026-10-18');
                    await cur_frm.set_value('schedule_date','2026-10-18');
                } else {
                    await cur_frm.set_value('set_posting_time',1);
                    await cur_frm.set_value('posting_date','2026-10-18');
                }
                if (type==='Purchase Invoice') {
                    await cur_frm.set_value('bill_date','2026-10-18');
                    await cur_frm.set_value('bill_no','SYNTHETIC-BROWSER-FREIGHT');
                    await cur_frm.set_value('update_stock',1);
                }
                for (const original of source.items) {
                    const row=cur_frm.doc.items.find(row=>!row.item_code) ||
                        frappe.model.add_child(cur_frm.doc,`${type} Item`,'items');
                    await frappe.model.set_value(row.doctype,row.name,'item_code',original.item_code);
                    await frappe.model.set_value(row.doctype,row.name,'qty',2);
                    await frappe.model.set_value(row.doctype,row.name,'rate',500);
                    await frappe.model.set_value(row.doctype,row.name,'expense_account',original.expense_account);
                    await frappe.model.set_value(row.doctype,row.name,'item_tax_template','MVA 25 % – varelinjer - VVM');
                    if (type==='Purchase Order') await frappe.model.set_value(row.doctype,row.name,'schedule_date','2026-10-18');
                }
            },{type,source});
            await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count);
            for (let index=0;index<2;index++) {
                await page.evaluate(index=>cur_frm.fields_dict.items.grid.grid_rows_by_docname[
                    cur_frm.doc.items[index].name].toggle_view(true),index);
                const input=page.locator('.grid-row-open [data-fieldname="custom_norway_deduction_percent"] input').last();
                await input.fill('60');await input.press('Tab');
                await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count);
                await page.evaluate(index=>cur_frm.fields_dict.items.grid.grid_rows_by_docname[
                    cur_frm.doc.items[index].name].toggle_view(false),index);
            }
            assert.equal(await page.evaluate(()=>cur_frm.doc.taxes.find(row=>row.account_head.startsWith('4998 ')).category),'Valuation and Total');
            // Add ordinary native freight fields after the item deduction was already chosen.
            await page.evaluate(async source=>{
                const freight=cur_frm.add_child('taxes',{
                    charge_type:'Actual',account_head:source.taxes.find(row=>row.charge_type==='Actual').account_head,
                    tax_amount:100,category:'Total',add_deduct_tax:'Add',description:'Synthetic freight',
                    cost_center:cur_frm.doc.cost_center});
                const vat=cur_frm.add_child('taxes',{
                    charge_type:'On Previous Row Amount',row_id:String(freight.idx),
                    category:'Total',add_deduct_tax:'Add',description:'MVA på frakt',
                    cost_center:cur_frm.doc.cost_center,rate:25});
                cur_frm.refresh_field('taxes');
                await frappe.model.set_value(vat.doctype,vat.name,'account_head',
                    source.taxes.find(row=>row.account_head.startsWith('2710 ')).account_head);
            },source);
            await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&
                cur_frm.doc.grand_total===2625&&cur_frm.doc.taxes.some(row=>row.account_head.startsWith('4998 ')&&row.category==='Total'));
            const amounts=await page.evaluate(()=>({manager:frappe.user_roles.includes('System Manager'),
                input:cur_frm.doc.taxes.filter(row=>row.account_head.startsWith('2710 ')).reduce((sum,row)=>sum+row.tax_amount_after_discount_amount,0),
                markers:cur_frm.doc.taxes.filter(row=>row.account_head.startsWith('4998 ')).map(row=>row.custom_norway_vat_cost),
                stock:cur_frm.doc.taxes.filter(row=>row.account_head.startsWith('4998 ')).reduce((sum,row)=>sum+row.tax_amount_after_discount_amount,0)}));
            assert(amounts.markers.length>0 && amounts.markers.every(value=>value===1));assert.equal(amounts.manager,false);assert.equal(amounts.input,315);assert.equal(amounts.stock,105);
            await page.getByRole('button',{name:'Lagre',exact:true}).click();
            await page.waitForFunction(()=>!cur_frm.is_new()&&!frappe.request.ajax_count);
            const name=await page.evaluate(()=>cur_frm.doc.name);
            assert.equal((await context.request.delete(`/api/resource/${encodeURIComponent(type)}/${encodeURIComponent(name)}`,
                {headers:{'X-Frappe-CSRF-Token':csrf}})).status(),202);
            console.log(`PASS ordinary owner ${type}: visible deduction and later native freight tax edit update existing cost category, 315 input / 105 stock VAT cost / 2625 payable, draft save`);
        }
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
