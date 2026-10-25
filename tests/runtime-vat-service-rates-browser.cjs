// Native form fields and calculator resolver, with ordinary draft save.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  const login=await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}});assert.equal(login.status(),200);
  const filters=encodeURIComponent(JSON.stringify({company:'Runtime Service Rates',docstatus:1,is_return:0,currency:'EUR'}));
  const response=await context.request.get(`/api/resource/Purchase%20Invoice?filters=${filters}&fields=${encodeURIComponent(JSON.stringify(['supplier']))}`);
  const supplier=(await response.json()).data[0].supplier;
  const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',error=>console.error('Browser error:',error.message));
  await page.goto('/desk/purchase-invoice/new-purchase-invoice');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice'&&cur_frm.fields_dict?.items&&!frappe.request.ajax_count);
  await page.evaluate(async supplier=>{
   await cur_frm.set_value('company','Runtime Service Rates');await cur_frm.set_value('supplier',supplier);
  },supplier);
  await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count&&cur_frm.doc.currency==='EUR');
  await page.evaluate(async()=>{
   await cur_frm.set_value('set_posting_time',1);await cur_frm.set_value('posting_date','2026-09-18');await cur_frm.set_value('bill_date','2026-09-18');await cur_frm.set_value('bill_no','SYNTHETIC-FX-BROWSER');await cur_frm.set_value('due_date','2026-10-31');await cur_frm.set_value('conversion_rate',10);
   const row=cur_frm.doc.items.find(row=>!row.item_code)||frappe.model.add_child(cur_frm.doc,'Purchase Invoice Item','items');
   await frappe.model.set_value(row.doctype,row.name,'item_code','RUNTIME-VAT-SERVICE');
  });
  await page.waitForFunction(()=>!frappe.request.ajax_count&&cur_frm.doc.items[0]?.item_name&&cur_frm.doc.items[0]?.uom);
  await page.evaluate(async()=>{
   const row=cur_frm.doc.items[0];await frappe.model.set_value(row.doctype,row.name,'qty',1);await frappe.model.set_value(row.doctype,row.name,'rate',100);
   const account=await frappe.db.get_value('Account',{company:'Runtime Service Rates',account_number:'4500'},'name');
   await frappe.model.set_value(row.doctype,row.name,'expense_account',account.message.name);
   await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_delivery_date','2026-09-10');
   await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_exchange_rate',11);
   await frappe.model.set_value(row.doctype,row.name,'item_tax_template','Tjenestekjøp fra utlandet – MVA 12 % – 100 % fradrag - R12');
  });
  await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===100&&cur_frm.doc.taxes.some(row=>row.account_head.startsWith('2709 ')&&row.charge_type==='On Norwegian VAT Base'&&row.base_tax_amount===132),null,{timeout:30000}).catch(async error=>{console.error(await page.evaluate(()=>({total:cur_frm.doc.grand_total,rate:cur_frm.doc.conversion_rate,items:cur_frm.doc.items.map(r=>({rate:r.rate,net:r.net_amount,fx:r.custom_norway_vat_exchange_rate,date:r.custom_norway_vat_delivery_date,template:r.item_tax_template,map:r.item_tax_rate})),taxes:cur_frm.doc.taxes.map(r=>({account:r.account_head,kind:r.charge_type,direction:r.add_deduct_tax,amount:r.tax_amount,base:r.base_tax_amount,rate:r.rate})),resolver:!!erpnext.taxable_base_resolvers['On Norwegian VAT Base'],pending:cur_frm.__norway_vat_preview,ajax:frappe.request.ajax_count})));throw error;});
  await page.evaluate(async()=>{const row=cur_frm.doc.items[0];await frappe.model.set_value(row.doctype,row.name,'custom_norway_deduction_percent',60);});
  await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===100&&cur_frm.doc.taxes.some(row=>row.account_head.startsWith('2718 ')&&row.base_tax_amount===79.2));
  const amounts=await page.evaluate(()=>({currency:cur_frm.doc.currency,book:cur_frm.doc.conversion_rate,payable:cur_frm.doc.grand_total,output:cur_frm.doc.taxes.find(row=>row.account_head.startsWith('2709 ')).base_tax_amount,input:cur_frm.doc.taxes.find(row=>row.account_head.startsWith('2718 ')).base_tax_amount,cost:cur_frm.doc.taxes.find(row=>row.custom_norway_vat_cost).base_tax_amount}));
  assert.deepEqual(amounts,{currency:'EUR',book:10,payable:100,output:132,input:79.2,cost:52.8});
  await page.evaluate(async()=>{
   const rows=cur_frm.doc.taxes.map(row=>({...row}));cur_frm.clear_table('taxes');
   const account=await frappe.db.get_value('Account',{company:'Runtime Service Rates',account_number:'6100'},'name');
   const fee=cur_frm.add_child('taxes',{charge_type:'Actual',account_head:account.message.name,tax_amount:0,description:'Synthetic native fee',category:'Total',add_deduct_tax:'Add',cost_center:rows[0].cost_center});
   for(const row of rows){const {name,parent,parenttype,parentfield,idx,...values}=row;cur_frm.add_child('taxes',{...values,row_id:'1'});}
   cur_frm.refresh_field('taxes');await frappe.model.set_value(fee.doctype,fee.name,'tax_amount',10);
  });
  await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview&&cur_frm.doc.grand_total===110&&cur_frm.doc.taxes.some(row=>row.account_head.startsWith('2709 ')&&row.base_tax_amount===145.2));
  assert.deepEqual(await page.evaluate(()=>({output:cur_frm.doc.taxes.find(r=>r.account_head.startsWith('2709 ')).base_tax_amount,input:cur_frm.doc.taxes.find(r=>r.account_head.startsWith('2718 ')).base_tax_amount,cost:cur_frm.doc.taxes.find(r=>r.custom_norway_vat_cost).base_tax_amount})),{output:145.2,input:87.12,cost:58.08});
  assert.match(await page.evaluate(()=>cur_frm.doc.taxes.find(r=>r.account_head.startsWith('2709 ')).description),/12 %/);
  await page.evaluate(()=>cur_frm.fields_dict.taxes.grid.grid_rows[1].toggle_view(true));
  assert.equal(await page.evaluate(()=>cur_frm.fields_dict.taxes.grid.grid_rows[1].grid_form.fields_dict.row_id.$wrapper.is(':visible')),true);
  await page.evaluate(()=>cur_frm.fields_dict.taxes.grid.grid_rows[1].toggle_view(false));
  assert.equal(await page.evaluate(()=>frappe.ui.form.check_mandatory(cur_frm)),true);
  await page.getByRole('button',{name:/^Lagre/}).first().click();
  await page.waitForFunction(()=>!cur_frm.doc.__islocal&&!cur_frm.is_dirty()&&!frappe.request.ajax_count);
  const saved=await page.evaluate(()=>({total:cur_frm.doc.grand_total,date:cur_frm.doc.items[0].custom_norway_vat_delivery_date,fx:cur_frm.doc.items[0].custom_norway_vat_exchange_rate,code:cur_frm.doc.items[0].custom_norway_vat_code}));
  assert.deepEqual(saved,{total:110,date:'2026-09-10',fx:11,code:'88'});
  console.log('PASS native Norwegian12% FX/fee basis: EUR110supplier,1210NOK basis,145.20output/87.12input/58.08cost,visible native row reference and ordinary draft save');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
