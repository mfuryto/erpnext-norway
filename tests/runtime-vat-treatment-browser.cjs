// Ordinary owner, native form events and totals; synthetic localhost only.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const base = process.env.ERP_LANGUAGE_TEST_URL;
    assert.match(base || '', /^http:\/\/127\.0\.0\.1:\d+$/);
    const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
    try {
        const context = await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
        const login = await context.request.post('/api/method/login',{form:{
            usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}});
        assert.equal(login.status(),200);
        const filters=encodeURIComponent(JSON.stringify({company:'Runtime VAT Example',docstatus:1,is_return:0}));
        const response=await context.request.get(`/api/resource/Purchase%20Invoice?filters=${filters}&fields=${encodeURIComponent(JSON.stringify(['supplier']))}`);
        const supplier=(await response.json()).data[0].supplier;
        const page=await context.newPage();
        page.setDefaultTimeout(60000);
        await page.goto('/app/purchase-invoice/new-purchase-invoice');
        await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice');
        await page.evaluate(async supplier=>{
            await cur_frm.set_value('company','Runtime VAT Example');
            await cur_frm.set_value('supplier',supplier);
        },supplier);
        await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count);
        await page.evaluate(async()=>{
            await cur_frm.set_value('posting_date','2026-10-16');
            await cur_frm.set_value('bill_date','2026-10-16');
            const item=frappe.model.add_child(cur_frm.doc,'Purchase Invoice Item','items');
            await frappe.model.set_value(item.doctype,item.name,'item_code','RUNTIME-VAT-SERVICE');
            await frappe.model.set_value(item.doctype,item.name,'qty',1);
            await frappe.model.set_value(item.doctype,item.name,'rate',1000);
        });
        await page.waitForFunction(()=>!frappe.request.ajax_count);
        await page.evaluate(async()=>{
            const item=cur_frm.doc.items.find(row=>row.item_code==='RUNTIME-VAT-SERVICE');
            await frappe.model.set_value(item.doctype,item.name,'item_tax_template','MVA 25 % – varelinjer - RVE');
        });
        await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===1250);
        await page.evaluate(async()=>{
            const item=cur_frm.doc.items.find(row=>row.item_code==='RUNTIME-VAT-SERVICE');
            await frappe.model.set_value(item.doctype,item.name,'custom_norway_deduction_percent',60);
        });
        await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.items.some(row=>row.item_tax_template?.includes('60 % fradrag')));
        const result=await page.evaluate(()=>({
            manager:frappe.user_roles.includes('System Manager'),total:cur_frm.doc.grand_total,
            taxes:cur_frm.doc.taxes.map(row=>({account:row.account_head,amount:row.tax_amount_after_discount_amount})),
            label:__('Input VAT deduction percent',null,'Purchase Invoice Item'),
        }));
        assert.equal(result.manager,false);
        assert.equal(result.total,1250);
        assert.equal(result.label,'MVA-fradrag i prosent');
        assert.equal(result.taxes.find(row=>row.account.startsWith('2710 ')).amount,150);
        assert.equal(result.taxes.find(row=>row.account.startsWith('4500 ')).amount,100);
        await page.screenshot({path:'/tmp/erpnext-language-browser/vat-native-line-deduction-nb.png',fullPage:true});
        console.log('PASS ordinary owner native item-tax choice and 60% deduction preview: 150 input VAT, 100 non-deductible cost, 1250 payable');
        await page.evaluate(async()=>{
            const item=cur_frm.doc.items.find(row=>row.item_code==='RUNTIME-VAT-SERVICE');
            await frappe.model.set_value(item.doctype,item.name,'custom_norway_deduction_percent',100);
        });
        await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&
            cur_frm.doc.items.some(row=>row.item_tax_template==='MVA 25 % – varelinjer - RVE'));
        const restored=await page.evaluate(()=>({total:cur_frm.doc.grand_total,
            taxes:cur_frm.doc.taxes.map(row=>({account:row.account_head,amount:row.tax_amount_after_discount_amount}))}));
        assert.equal(restored.total,1250);
        assert.equal(restored.taxes.find(row=>row.account.startsWith('2710 ')).amount,250);
        assert.equal(restored.taxes.find(row=>row.account.startsWith('4500 ')).amount,0);
        console.log('PASS explicit return to full deduction uses native template and reverses the cost allocation in preview');
        await page.evaluate(()=>{
            const cost=cur_frm.doc.taxes.find(row=>row.account_head.startsWith('4500 ')).account_head;
            cur_frm.doc.taxes=cur_frm.doc.taxes.filter(row=>row.account_head!==cost);
            cur_frm.add_child('taxes',{charge_type:'Actual',account_head:cost,tax_amount:100,
                description:'Synthetic separate charge',category:'Total',add_deduct_tax:'Add',
                cost_center:cur_frm.doc.cost_center});
            cur_frm.refresh_field('taxes');cur_frm.cscript.calculate_taxes_and_totals();
        });
        await page.waitForFunction(()=>cur_frm.doc.grand_total===1350&&!frappe.request.ajax_count);
        await page.evaluate(async()=>{
            const item=cur_frm.doc.items.find(row=>row.item_code==='RUNTIME-VAT-SERVICE');
            await frappe.model.set_value(item.doctype,item.name,'custom_norway_deduction_percent',60);
        });
        await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&
            cur_frm.doc.taxes.filter(row=>row.account_head.startsWith('4500 ')).length===2);
        const charged=await page.evaluate(()=>({total:cur_frm.doc.grand_total,
            taxes:cur_frm.doc.taxes.map(row=>({account:row.account_head,type:row.charge_type,
                amount:row.tax_amount_after_discount_amount}))}));
        assert.equal(charged.total,1350);
        assert.equal(charged.taxes.find(row=>row.account.startsWith('2710 ')).amount,150);
        assert.equal(charged.taxes.find(row=>row.account.startsWith('4500 ')&&row.type==='Actual').amount,100);
        assert.equal(charged.taxes.find(row=>row.account.startsWith('4500 ')&&row.type==='On Net Total').amount,100);
        console.log('PASS native browser retains separate charge and non-deductible VAT on the same account: 1350 payable');
        await page.goto('/app/query-report/Norsk%20MVA-spesifikasjon?company=Runtime%20VAT%20Example&from_date=2026-10-15&to_date=2026-10-31');
        await page.waitForFunction(()=>window.frappe?.query_report?.report_name==='Norsk MVA-spesifikasjon'&&
            frappe.query_report.data?.length&&!frappe.request.ajax_count);
        const report=await page.evaluate(()=>({
            codes:frappe.query_report.data.map(row=>row.vat_code),
            labels:frappe.query_report.columns.map(row=>row.label),
            company:frappe.query_report.get_filter_value('company'),
        }));
        assert.equal(report.company,'Runtime VAT Example');
        assert(report.codes.includes('3')&&report.codes.includes('1'));
        assert(report.labels.includes('Utgående MVA')&&report.labels.includes('Inngående MVA'));
        await page.getByRole('button',{name:'Bevar MVA-grunnlag',exact:true}).click();
        await page.waitForFunction(()=>window.cur_frm?.doctype==='File'&&
            cur_frm.doc.custom_norway_retained_vat_evidence===1&&!frappe.request.ajax_count);
        const evidence=await page.evaluate(()=>({private:cur_frm.doc.is_private,
            company:cur_frm.doc.attached_to_name,kind:cur_frm.doc.custom_norway_vat_evidence_kind}));
        assert.equal(evidence.private,1);assert.equal(evidence.company,'Runtime VAT Example');
        assert.equal(evidence.kind,'VAT basis');
        console.log('PASS native Norwegian VAT report opens for ordinary owner and preserves private basis through the report button');
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
