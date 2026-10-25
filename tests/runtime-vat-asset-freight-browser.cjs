// Existing native invoice/receipt controls, no extra workspace or confirmation.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const company='Runtime Asset Freight',abbr='AVF';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  assert.equal((await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}})).status(),200);
  async function record(type,filters,fields){const r=await context.request.get(`/api/resource/${encodeURIComponent(type)}?filters=${encodeURIComponent(JSON.stringify(filters))}&fields=${encodeURIComponent(JSON.stringify(fields))}`);assert.equal(r.status(),200);return(await r.json()).data[0];}
  const ref=await record('Purchase Invoice',{company,bill_no:'SYNTHETIC-ASSET-FREIGHT-RESTORE',docstatus:1,is_return:0},['name']);
  const source=(await(await context.request.get(`/api/resource/Purchase%20Invoice/${encodeURIComponent(ref.name)}`)).json()).data;
  const page=await context.newPage();page.setDefaultTimeout(60000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/desk/purchase-invoice/new-purchase-invoice');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice'&&cur_frm.fields_dict?.items&&!frappe.request.ajax_count);
  const csrf=await page.evaluate(()=>frappe.csrf_token);
  await page.evaluate(async({company,supplier})=>{await cur_frm.set_value('company',company);await cur_frm.set_value('supplier',supplier);},{company,supplier:source.supplier});
  await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count);
  await page.evaluate(async()=>{await cur_frm.set_value('set_posting_time',1);await cur_frm.set_value('posting_date','2026-10-20');await cur_frm.set_value('bill_date','2026-10-20');await cur_frm.set_value('bill_no','SYNTHETIC-ASSET-BROWSER-DRAFT');await cur_frm.set_value('due_date','2026-10-31');await cur_frm.set_value('disable_rounded_total',1);cur_frm.clear_table('items');});
  for(const item of source.items){
   const name=await page.evaluate(async code=>{const row=cur_frm.add_child('items');await frappe.model.set_value(row.doctype,row.name,'item_code',code);return row.name;},item.item_code);
   await page.waitForFunction(name=>!frappe.request.ajax_count&&locals['Purchase Invoice Item'][name]?.uom,name);
   await page.evaluate(async({name,item,abbr})=>{const r=locals['Purchase Invoice Item'][name];for(const [field,value] of Object.entries({qty:2,rate:500,expense_account:item.expense_account,cost_center:item.cost_center,item_tax_template:'MVA 25 % – varelinjer - '+abbr,custom_norway_deduction_percent:60,asset_location:item.asset_location}))if(value!=null)await frappe.model.set_value(r.doctype,r.name,field,value);},{name,item,abbr});
   await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview);
  }
  await page.evaluate(async source=>{
   cur_frm.clear_table('taxes');cur_frm.add_child('taxes',{charge_type:'Actual',account_head:source.taxes[0].account_head,tax_amount:100,category:'Total',add_deduct_tax:'Add',description:'Synthetic native freight',cost_center:source.cost_center});
   const vat=cur_frm.add_child('taxes',{charge_type:'On Previous Row Total',row_id:'1',category:'Total',add_deduct_tax:'Add',description:'MVA på tillegg',rate:25,cost_center:source.cost_center});cur_frm.refresh_field('taxes');
   await frappe.model.set_value(vat.doctype,vat.name,'account_head',source.taxes.find(r=>r.account_head.startsWith('2710 ')).account_head);
  },source);
  await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview&&cur_frm.doc.grand_total===2625&&cur_frm.doc.taxes.some(r=>r.account_head.startsWith('4998 ')&&r.category==='Total'));
  assert.deepEqual(await page.evaluate(()=>({system:frappe.user_roles.includes('System Manager'),input:cur_frm.doc.taxes.find(r=>r.account_head.startsWith('2710 ')).tax_amount_after_discount_amount,cost:cur_frm.doc.taxes.find(r=>r.account_head.startsWith('4998 ')).tax_amount_after_discount_amount})),{system:false,input:315,cost:105});
  await page.getByRole('button',{name:'Lagre',exact:true}).click();await page.waitForFunction(()=>!cur_frm.is_new()&&!cur_frm.is_dirty()&&!frappe.request.ajax_count);
  const draft=await page.evaluate(()=>cur_frm.doc.name);
  assert.equal((await context.request.delete(`/api/resource/Purchase%20Invoice/${encodeURIComponent(draft)}`,{headers:{'X-Frappe-CSRF-Token':csrf}})).status(),202);
  await page.goto(`/desk/purchase-receipt/${encodeURIComponent(source.items[0].purchase_receipt)}`);
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Receipt'&&cur_frm.doc.docstatus===1&&!frappe.request.ajax_count);
  await page.evaluate(()=>cur_frm.cscript.make_purchase_return());
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Receipt'&&cur_frm.doc.is_return===1&&!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.items[0]?.purchase_invoice_item);
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(true));
  await page.getByText('Fakturalinje for MVA-behandling',{exact:true}).first().waitFor({state:'visible'});
  await page.waitForFunction(()=>cur_frm.fields_dict.items.grid.grid_rows[0].docfields.find(df=>df.fieldname==='purchase_invoice_item').options.length>0);
  const selection=await page.evaluate(()=>{const r=cur_frm.doc.items[0],grid=cur_frm.fields_dict.items.grid.grid_rows[0];return{invoice:r.purchase_invoice||null,row:r.purchase_invoice_item,kind:grid.grid_form.fields_dict.purchase_invoice_item.df.fieldtype,readonly:grid.grid_form.fields_dict.purchase_invoice.get_status(),options:grid.docfields.find(df=>df.fieldname==='purchase_invoice_item').options,deduction:r.custom_norway_deduction_percent};});
  assert.equal(selection.invoice,null);assert.equal(selection.row,source.items[0].name);assert.equal(selection.kind,'Autocomplete');assert.notEqual(selection.readonly,'Write');assert.equal(selection.deduction,60);assert(selection.options.some(o=>o.value===source.items[0].name&&o.label.includes(source.name)));assert.deepEqual(errors,[]);
  console.log('PASS ordinary native Asset freight60% draft2625/input315/cost105; native receipt return invoice-row autocomplete in Norwegian, original receipt-owned financial reference preserved, no SystemManager');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
