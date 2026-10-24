// Native purchase fields and receipt-return preview, ordinary owner only.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const base = process.env.ERP_LANGUAGE_TEST_URL;
    assert.match(base || '', /^http:\/\/127\.0\.0\.1:\d+$/);
    const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
    let originalTemplate;
    let context;
    let csrfHeaders;
    try {
        context = await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
        const login = await context.request.post('/api/method/login',{form:{
            usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}});
        assert.equal(login.status(),200);
        const filters=encodeURIComponent(JSON.stringify({company:'Runtime VAT Valuation',docstatus:1,is_return:0}));
        const response=await context.request.get(`/api/resource/Purchase%20Invoice?filters=${filters}&fields=${encodeURIComponent(JSON.stringify(['name','supplier']))}`);
        const reference=(await response.json()).data[0];
        const source=(await (await context.request.get(`/api/resource/Purchase%20Invoice/${encodeURIComponent(reference.name)}`)).json()).data;
        const page=await context.newPage();
        page.setDefaultTimeout(60000);
        const evaluate = (fn, argument) => {
            let timer;
            return Promise.race([page.evaluate(fn, argument), new Promise((_, reject) => {
                timer=setTimeout(()=>reject(new Error('Native form operation did not finish within 60 seconds')),60000);
            })]).finally(()=>clearTimeout(timer));
        };
        for (const type of ['Purchase Invoice','Purchase Order','Purchase Receipt']) {
            const route=type.toLowerCase().replaceAll(' ','-');
            await page.goto(`/app/${route}/new-${route}`);
            await page.waitForFunction(type=>window.cur_frm?.doctype===type,type);
            csrfHeaders={'X-Frappe-CSRF-Token':await evaluate(()=>frappe.csrf_token)};
            await evaluate(async ({type,supplier})=>{
                await cur_frm.set_value('company','Runtime VAT Valuation');
                await cur_frm.set_value('supplier',supplier);
            },{type,supplier:reference.supplier});
            await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count);
            await evaluate(async type=>{
                if (type==='Purchase Order') {
                    await cur_frm.set_value('transaction_date','2026-10-18');
                    await cur_frm.set_value('schedule_date','2026-10-18');
                } else {
                    await cur_frm.set_value('set_posting_time',1);
                    await cur_frm.set_value('posting_date','2026-10-18');
                }
                if (type==='Purchase Invoice') {
                    await cur_frm.set_value('bill_date','2026-10-18');
                    await cur_frm.set_value('bill_no','SYNTHETIC-BROWSER-VALUATION');
                    await cur_frm.set_value('update_stock',1);
                }
                const row=cur_frm.doc.items.find(row=>!row.item_code) ||
                    frappe.model.add_child(cur_frm.doc,`${type} Item`,'items');
                await frappe.model.set_value(row.doctype,row.name,'item_code','SYNTHETIC-VAT-STOCK');
                await frappe.model.set_value(row.doctype,row.name,'qty',1);
                await frappe.model.set_value(row.doctype,row.name,'rate',1000);
                if (type==='Purchase Order') await frappe.model.set_value(row.doctype,row.name,'schedule_date','2026-10-18');
                await frappe.model.set_value(row.doctype,row.name,'item_tax_template','MVA 25 % – varelinjer - VVE');
            },type);
            await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===1250);
            await evaluate(()=>{
                const row=cur_frm.doc.items.find(row=>row.item_code==='SYNTHETIC-VAT-STOCK');
                cur_frm.fields_dict.items.grid.grid_rows_by_docname[row.name].toggle_view(true);
            });
            const input=page.locator('.grid-row-open [data-fieldname="custom_norway_deduction_percent"] input').last();
            await input.fill('60');
            await input.press('Tab');
            await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&
                cur_frm.doc.items.some(row=>row.custom_norway_deduction_percent===60&&row.item_tax_template?.includes('60 % fradrag')));
            const result=await evaluate(()=>({manager:frappe.user_roles.includes('System Manager'),
                label:__('Input VAT deduction percent',null,cur_frm.doctype+' Item'),
                total:cur_frm.doc.grand_total,
                taxes:cur_frm.doc.taxes.map(row=>({account:row.account_head,category:row.category,
                    amount:row.tax_amount_after_discount_amount}))}));
            assert.equal(result.manager,false);
            assert.equal(result.label,'MVA-fradrag i prosent');
            assert.equal(result.total,1250);
            assert.equal(result.taxes.find(row=>row.account.startsWith('2710 ')).amount,150);
            const cost=result.taxes.find(row=>row.account.startsWith('4998 '));
            assert.equal(cost.amount,100);
            assert.equal(cost.category,'Valuation and Total');
            await evaluate(()=>{
                const row=cur_frm.doc.items.find(row=>row.item_code==='SYNTHETIC-VAT-STOCK');
                cur_frm.fields_dict.items.grid.grid_rows_by_docname[row.name].toggle_view(false);
            });
            await page.getByRole('button',{name:'Lagre',exact:true}).click();
            await page.waitForFunction(type=>window.cur_frm?.doctype===type&&!cur_frm.is_new()&&
                !frappe.request.ajax_count,type);
            const name=await evaluate(()=>cur_frm.doc.name);
            const deleted=await context.request.delete(`/api/resource/${encodeURIComponent(type)}/${encodeURIComponent(name)}`,{headers:csrfHeaders});
            assert.equal(deleted.status(),202);
            console.log(`PASS native ${type} visible deduction input, 150 input VAT / 100 valuation / 1250 payable and ordinary draft save`);
        }
        const templateName=source.items[0].item_tax_template;
        originalTemplate=(await (await context.request.get(`/api/resource/Item%20Tax%20Template/${encodeURIComponent(templateName)}`)).json()).data;
        const edited=originalTemplate.taxes.map(row=>({...row,
            tax_rate:row.tax_type.startsWith('2710 ')?10:row.tax_type.startsWith('4998 ')?15:row.tax_rate}));
        const changed=await context.request.put(`/api/resource/Item%20Tax%20Template/${encodeURIComponent(templateName)}`,{data:{taxes:edited},headers:csrfHeaders});
        assert.equal(changed.status(),200);
        await page.goto(`/app/purchase-receipt/${encodeURIComponent(source.items[0].purchase_receipt)}`);
        await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Receipt'&&cur_frm.doc.docstatus===1&&!frappe.request.ajax_count);
        await evaluate(()=>cur_frm.cscript.make_purchase_return());
        await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Receipt'&&cur_frm.doc.is_return===1&&
            !cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&
            cur_frm.doc.items.some(row=>row.custom_norway_deduction_percent===60));
        const returned=await evaluate(()=>({total:cur_frm.doc.grand_total,
            template:cur_frm.doc.items[0].item_tax_template,
            taxes:cur_frm.doc.taxes.map(row=>({account:row.account_head,amount:row.tax_amount_after_discount_amount}))}));
        assert.equal(returned.total,-1250);
        assert(returned.template.startsWith('Opprinnelig avgiftsbehandling '));
        assert.equal(returned.taxes.find(row=>row.account.startsWith('2710 ')).amount,-150);
        assert.equal(returned.taxes.find(row=>row.account.startsWith('4998 ')).amount,-100);
        await page.getByRole('button',{name:'Lagre',exact:true}).click();
        await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Receipt'&&!cur_frm.is_new()&&
            cur_frm.doc.is_return===1&&!frappe.request.ajax_count);
        const returnedName=await evaluate(()=>cur_frm.doc.name);
        const saved=(await (await context.request.get(`/api/resource/Purchase%20Receipt/${encodeURIComponent(returnedName)}`)).json()).data;
        assert.equal(saved.items[0].purchase_invoice,source.name);
        assert.equal(saved.items[0].purchase_invoice_item,source.items[0].name);
        const deleted=await context.request.delete(`/api/resource/Purchase%20Receipt/${encodeURIComponent(returnedName)}`,{headers:csrfHeaders});
        assert.equal(deleted.status(),202);
        console.log('PASS native receipt Return action previews issued 150/100 split before save after later template edit; native source invoice/row references retained');
    } finally {
        if (originalTemplate && context) {
            const restored=await context.request.put(`/api/resource/Item%20Tax%20Template/${encodeURIComponent(originalTemplate.name)}`,{data:{taxes:originalTemplate.taxes},headers:csrfHeaders});
            assert.equal(restored.status(),200);
        }
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exit(1);});
