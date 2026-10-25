// Native form fields and calculator resolver, with ordinary draft save.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  const login=await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}});assert.equal(login.status(),200);
  const filters=encodeURIComponent(JSON.stringify({company:'Runtime Currency Services',docstatus:1,is_return:0}));
  const response=await context.request.get(`/api/resource/Purchase%20Invoice?filters=${filters}&fields=${encodeURIComponent(JSON.stringify(['supplier']))}`);
  const supplier=(await response.json()).data[0].supplier;
  const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',error=>console.error('Browser error:',error.message));
  await page.goto('/desk/purchase-invoice/new-purchase-invoice');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice'&&cur_frm.fields_dict?.items&&!frappe.request.ajax_count);
  await page.evaluate(async supplier=>{
   await cur_frm.set_value('company','Runtime Currency Services');await cur_frm.set_value('supplier',supplier);
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
   const account=await frappe.db.get_value('Account',{company:'Runtime Currency Services',account_number:'4500'},'name');
   await frappe.model.set_value(row.doctype,row.name,'expense_account',account.message.name);
   await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_delivery_date','2026-09-10');
   await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_exchange_rate',11.0137);
   await frappe.model.set_value(row.doctype,row.name,'item_tax_template','Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag - FCV');
  });
  await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===100&&cur_frm.doc.taxes.some(row=>row.account_head.startsWith('2704 ')&&row.charge_type==='On Norwegian VAT Base'&&row.base_tax_amount===275.34),null,{timeout:30000}).catch(async error=>{console.error(await page.evaluate(()=>({total:cur_frm.doc.grand_total,rate:cur_frm.doc.conversion_rate,items:cur_frm.doc.items.map(r=>({rate:r.rate,net:r.net_amount,fx:r.custom_norway_vat_exchange_rate,date:r.custom_norway_vat_delivery_date,template:r.item_tax_template,map:r.item_tax_rate})),taxes:cur_frm.doc.taxes.map(r=>({account:r.account_head,kind:r.charge_type,direction:r.add_deduct_tax,amount:r.tax_amount,base:r.base_tax_amount,rate:r.rate})),resolver:!!erpnext.taxable_base_resolvers['On Norwegian VAT Base'],pending:cur_frm.__norway_vat_preview,ajax:frappe.request.ajax_count})));throw error;});
  await page.evaluate(async()=>{const row=cur_frm.doc.items[0];await frappe.model.set_value(row.doctype,row.name,'custom_norway_deduction_percent',60);});
  await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===100&&cur_frm.doc.taxes.some(row=>row.account_head.startsWith('2714 ')&&row.base_tax_amount===165.21));
  const amounts=await page.evaluate(()=>({currency:cur_frm.doc.currency,book:cur_frm.doc.conversion_rate,payable:cur_frm.doc.grand_total,output:cur_frm.doc.taxes.find(row=>row.account_head.startsWith('2704 ')).base_tax_amount,input:cur_frm.doc.taxes.find(row=>row.account_head.startsWith('2714 ')).base_tax_amount,cost:cur_frm.doc.taxes.find(row=>row.custom_norway_vat_cost).base_tax_amount}));
  assert.deepEqual(amounts,{currency:'EUR',book:10,payable:100,output:275.34,input:165.21,cost:110.14});
  await page.evaluate(async()=>{const row=cur_frm.doc.items[0];await frappe.model.set_value(row.doctype,row.name,'custom_norway_deduction_percent',33.33);});
  await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===100&&cur_frm.doc.taxes.some(row=>row.account_head.startsWith('2714 ')&&row.base_tax_amount===91.77),null,{timeout:30000}).catch(async error=>{console.error(await page.evaluate(()=>({total:cur_frm.doc.grand_total,precision:cur_frm.doc.taxes.map(r=>precision('rate',r)),items:cur_frm.doc.items.map(r=>({rate:r.rate,net:r.net_amount,percent:r.custom_norway_deduction_percent,map:r.item_tax_rate})),taxes:cur_frm.doc.taxes.map(r=>({account:r.account_head,base:r.base_tax_amount,amount:r.tax_amount,kind:r.charge_type})),pending:cur_frm.__norway_vat_preview,ajax:frappe.request.ajax_count})));throw error;});
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(true));
  await page.getByText('Leveringsdato for MVA',{exact:true}).first().waitFor({state:'visible'});
  await page.getByText('MVA-kurs (NOK per valutaenhet)',{exact:true}).first().waitFor({state:'visible'});
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(false));
  assert.equal(await page.evaluate(()=>frappe.ui.form.check_mandatory(cur_frm)),true);
  await page.getByRole('button',{name:/^Lagre/}).first().click();
  await page.waitForFunction(()=>!cur_frm.doc.__islocal&&!cur_frm.is_dirty()&&!frappe.request.ajax_count);
  const saved=await page.evaluate(()=>({total:cur_frm.doc.grand_total,date:cur_frm.doc.items[0].custom_norway_vat_delivery_date,fx:cur_frm.doc.items[0].custom_norway_vat_exchange_rate,code:cur_frm.doc.items[0].custom_norway_vat_code}));
  assert.deepEqual(saved,{total:100,date:'2026-09-10',fx:11.0137,code:'86'});
  console.log('PASS native Norwegian FX fields and browser resolver: EUR100 supplier, separate 1101.37 NOK basis, 275.34 output / 165.21 input / 110.14 cost, and 33.33 percent deduction retained on ordinary draft save');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
