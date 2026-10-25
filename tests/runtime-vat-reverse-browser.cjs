// Existing item-tax selector and deduction field; native form totals and save.
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
  const filters=encodeURIComponent(JSON.stringify({company:'Runtime Reverse Services',docstatus:1,is_return:0}));
  const response=await context.request.get(`/api/resource/Purchase%20Invoice?filters=${filters}&fields=${encodeURIComponent(JSON.stringify(['supplier']))}`);
  const supplier=(await response.json()).data[0].supplier;
  const page=await context.newPage();page.setDefaultTimeout(60000);
  await page.goto('/desk/purchase-invoice/new-purchase-invoice');
  // Poll readiness across native boot navigation; an evaluated after_ajax
  // promise is destroyed if Desk replaces the document while it is pending.
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice'&&
   cur_frm.fields_dict?.items&&!frappe.request.ajax_count);
  await page.evaluate(async supplier=>{
   await cur_frm.set_value('company','Runtime Reverse Services');
   await cur_frm.set_value('supplier',supplier);
  },supplier);
  await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count);
  await page.evaluate(async()=>{
   await cur_frm.set_value('set_posting_time',1);
   await cur_frm.set_value('posting_date','2026-09-18');
   await cur_frm.set_value('bill_date','2026-09-18');
   await cur_frm.set_value('bill_no','SYNTHETIC-REVERSE-BROWSER');
   await cur_frm.set_value('due_date','2026-10-31');
   const item=cur_frm.doc.items.find(row=>!row.item_code)||frappe.model.add_child(cur_frm.doc,'Purchase Invoice Item','items');
   await frappe.model.set_value(item.doctype,item.name,'item_code','RUNTIME-VAT-SERVICE');
  });
  await page.waitForFunction(()=>!frappe.request.ajax_count&&cur_frm.doc.items[0]?.item_name&&cur_frm.doc.items[0]?.uom);
  await page.evaluate(async()=>{
   const item=cur_frm.doc.items.find(r=>r.item_code==='RUNTIME-VAT-SERVICE');
   await frappe.model.set_value(item.doctype,item.name,'qty',1);
   await frappe.model.set_value(item.doctype,item.name,'rate',1000);
   await frappe.model.set_value(item.doctype,item.name,'item_tax_template','Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag - RRS');
  });
  await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===1000&&
   cur_frm.doc.taxes.some(r=>r.account_head.startsWith('2704 ')&&r.add_deduct_tax==='Deduct'));
  await page.evaluate(async()=>{
   const item=cur_frm.doc.items.find(r=>r.item_code==='RUNTIME-VAT-SERVICE');
   await frappe.model.set_value(item.doctype,item.name,'custom_norway_deduction_percent',60);
  });
  await page.waitForFunction(()=>!cur_frm.__norway_vat_preview&&!frappe.request.ajax_count&&cur_frm.doc.grand_total===1000&&
   cur_frm.doc.taxes.some(r=>r.account_head.startsWith('2714 ')&&r.tax_amount_after_discount_amount===150));
  const totals=await page.evaluate(()=>({
   payable:cur_frm.doc.grand_total,
   input:cur_frm.doc.taxes.find(r=>r.account_head.startsWith('2714 ')).tax_amount_after_discount_amount,
   output:cur_frm.doc.taxes.find(r=>r.account_head.startsWith('2704 ')).tax_amount_after_discount_amount,
   cost:cur_frm.doc.taxes.find(r=>r.custom_norway_vat_cost).tax_amount_after_discount_amount,
  }));
  assert.equal(totals.payable,1000);assert.equal(totals.input,150);assert.equal(totals.output,250);assert.equal(totals.cost,100);
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(true));
  await page.getByText('MVA-fradrag i prosent',{exact:true}).first().waitFor({state:'visible'});
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(false));
  await page.evaluate(()=>new Promise(resolve=>frappe.after_ajax(resolve)));
  const mandatory=await page.evaluate(()=>({ok:frappe.ui.form.check_mandatory(cur_frm),missing:frappe.model.get_all_docs(cur_frm.doc).flatMap(doc=>Object.values(frappe.meta.get_docfield_copy(doc.doctype,doc.name)||{}).filter(df=>df.reqd&&!frappe.model.has_value(doc.doctype,doc.name,df.fieldname)).map(df=>[doc.doctype,doc.idx,df.fieldname]))}));
  assert.equal(mandatory.ok,true,JSON.stringify(mandatory));
  const saveState=await page.evaluate(()=>({dirty:cur_frm.is_dirty(),local:cur_frm.doc.__islocal,unsaved:cur_frm.doc.__unsaved}));
  assert(saveState.dirty,JSON.stringify(saveState));
  await page.getByRole('button',{name:/^Lagre/}).first().click();
  await page.waitForFunction(()=>!cur_frm.doc.__islocal&&!frappe.request.ajax_count);
  const saved=await page.evaluate(()=>({code:cur_frm.doc.items[0].custom_norway_vat_code,percent:cur_frm.doc.items[0].custom_norway_deduction_percent,total:cur_frm.doc.grand_total}));
  assert.deepEqual(saved,{code:'86',percent:60,total:1000});
  console.log('PASS native Norwegian reverse-charge item selector and deduction field: 1000 supplier / 250 output / 150 input / 100 cost, retained on draft save');
  await page.goto('/app/query-report/Norsk%20MVA-spesifikasjon?company=Runtime%20Reverse%20Services&from_date=2026-09-01&to_date=2026-10-31');
  await page.waitForFunction(()=>window.frappe?.query_report?.report_name==='Norsk MVA-spesifikasjon'&&frappe.query_report.data?.length&&!frappe.request.ajax_count);
  const data=await page.evaluate(()=>frappe.query_report.data.map(r=>({code:r.vat_code,base:r.base_amount,output:r.output_vat,input:r.input_vat})));
  assert.deepEqual(data,[{code:'86',base:1000,output:250,input:200},{code:'87',base:500,output:125,input:0}]);
  console.log('PASS ordinary owner native Norwegian reverse-charge report: codes 86/87, correct signs, one base and separate input/output VAT');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
