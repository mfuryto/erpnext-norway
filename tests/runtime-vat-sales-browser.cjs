// Ordinary draft forms: core item selectors/calculator/save, no parallel UI.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;
 assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  const login=await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}});
  assert.equal(login.status(),200);
  const filters=encodeURIComponent(JSON.stringify({company:'Runtime Sales VAT Chain',docstatus:1,is_return:0}));
  const response=await context.request.get(`/api/resource/Sales%20Invoice?filters=${filters}&fields=${encodeURIComponent(JSON.stringify(['customer']))}`);
  const customer=(await response.json()).data[0].customer;
  const page=await context.newPage();page.setDefaultTimeout(60000);
  for(const doctype of ['Quotation','Sales Order','Delivery Note','Sales Invoice']) {
   const route=doctype.toLowerCase().replaceAll(' ','-');
   await page.goto(`/desk/${route}/new-${route}`);
   await page.waitForFunction(doctype=>window.cur_frm?.doctype===doctype&&cur_frm.fields_dict?.items&&!frappe.request.ajax_count,doctype);
   await page.evaluate(async({doctype,customer})=>{
    await cur_frm.set_value('company','Runtime Sales VAT Chain');
    if(doctype==='Quotation') {
     await cur_frm.set_value('quotation_to','Customer');
     await cur_frm.set_value('party_name',customer);
    } else await cur_frm.set_value('customer',customer);
   },{doctype,customer});
   await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count);
   await page.evaluate(async doctype=>{
    if(cur_frm.fields_dict.set_posting_time) await cur_frm.set_value('set_posting_time',1);
    if(cur_frm.fields_dict.posting_date) await cur_frm.set_value('posting_date','2026-09-18');
    if(cur_frm.fields_dict.transaction_date) await cur_frm.set_value('transaction_date','2026-09-18');
    if(cur_frm.fields_dict.delivery_date) await cur_frm.set_value('delivery_date','2026-12-01');
    if(cur_frm.fields_dict.valid_till) await cur_frm.set_value('valid_till','2026-12-31');
    if(cur_frm.fields_dict.due_date) await cur_frm.set_value('due_date','2026-12-31');
    const item=cur_frm.doc.items.find(row=>!row.item_code)||frappe.model.add_child(cur_frm.doc,`${doctype} Item`,'items');
    await frappe.model.set_value(item.doctype,item.name,'item_code','RUNTIME-VAT-SERVICE');
   },doctype);
   await page.waitForFunction(()=>!frappe.request.ajax_count&&cur_frm.doc.items[0]?.item_name&&cur_frm.doc.items[0]?.uom);
   await page.evaluate(async()=>{
    const item=cur_frm.doc.items[0];
    await frappe.model.set_value(item.doctype,item.name,'qty',1);
    await frappe.model.set_value(item.doctype,item.name,'rate',1000);
    await frappe.model.set_value(item.doctype,item.name,'item_tax_template','MVA 25 % – varelinjer - SCV');
   });
   await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===1250&&
    cur_frm.doc.taxes.length===1&&cur_frm.doc.taxes[0].account_head.startsWith('2700 '));
   await page.evaluate(async()=>{
    const row=frappe.model.add_child(cur_frm.doc,`${cur_frm.doctype} Item`,'items');
    await frappe.model.set_value(row.doctype,row.name,'item_code','RUNTIME-VAT-SERVICE');
   });
   await page.waitForFunction(()=>!frappe.request.ajax_count&&cur_frm.doc.items[1]?.item_name&&cur_frm.doc.items[1]?.uom);
   await page.evaluate(async()=>{
    const item=cur_frm.doc.items[1];
    await frappe.model.set_value(item.doctype,item.name,'qty',1);
    await frappe.model.set_value(item.doctype,item.name,'rate',1000);
    await frappe.model.set_value(item.doctype,item.name,'item_tax_template','MVA 15 % – varelinjer - SCV');
   });
   await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===2400&&
    cur_frm.doc.taxes.length===2&&cur_frm.doc.taxes.every(row=>row.account_head.startsWith('270')));
   const mandatory=await page.evaluate(()=>frappe.ui.form.check_mandatory(cur_frm));
   assert.equal(mandatory,true,doctype);
   await page.getByRole('button',{name:/^Lagre/}).first().click();
   await page.waitForFunction(()=>!cur_frm.doc.__islocal&&!cur_frm.is_dirty()&&!frappe.request.ajax_count);
   const saved=await page.evaluate(()=>({total:cur_frm.doc.grand_total,rates:cur_frm.doc.items.map(row=>row.item_tax_template),accounts:cur_frm.doc.taxes.map(row=>row.account_head)}));
   assert.equal(saved.total,2400);assert.equal(saved.accounts.length,2);
   assert.deepEqual(saved.rates,['MVA 25 % – varelinjer - SCV','MVA 15 % – varelinjer - SCV']);
   console.log(`PASS ordinary owner ${doctype}: mixed native item selection previews 2400 with only output VAT and survives native draft save`);
  }
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
