const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const company='Runtime Asset Freight',abbr='AVF';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  assert.equal((await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}})).status(),200);
  async function record(type,filters){const r=await context.request.get(`/api/resource/${encodeURIComponent(type)}?filters=${encodeURIComponent(JSON.stringify(filters))}&fields=${encodeURIComponent(JSON.stringify(['name']))}`);assert.equal(r.status(),200);return(await r.json()).data[0];}
  const supplier=await record('Supplier',{supplier_name:'Synthetic capitalized currency supplier'});
  const sourceRef=await record('Purchase Invoice',{company,bill_no:'SYNTHETIC-ASSET-FREIGHT-RESTORE',docstatus:1,is_return:0});
  const source=(await(await context.request.get(`/api/resource/Purchase%20Invoice/${encodeURIComponent(sourceRef.name)}`)).json()).data;
  const page=await context.newPage();page.setDefaultTimeout(60000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  async function draft(foreign){
   await page.goto('/desk/purchase-invoice/new-purchase-invoice');
   await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice'&&cur_frm.is_new()&&cur_frm.fields_dict?.items&&!frappe.request.ajax_count);
   await page.evaluate(async({company,supplier})=>{await cur_frm.set_value('company',company);await cur_frm.set_value('supplier',supplier);},{company,supplier:foreign?supplier.name:source.supplier});
   await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count);
   await page.evaluate(async foreign=>{
    await cur_frm.set_value('set_posting_time',1);await cur_frm.set_value('posting_date',foreign?'2026-10-20':'2026-09-20');await cur_frm.set_value('bill_date',foreign?'2026-10-20':'2026-09-20');await cur_frm.set_value('bill_no','SYNTHETIC-ASSET-BROWSER-'+(foreign?'EUR':'QUARTER'));
    await cur_frm.set_value('due_date','2026-10-31');await cur_frm.set_value('currency',foreign?'EUR':'NOK');await cur_frm.set_value('conversion_rate',foreign?10:1);await cur_frm.set_value('update_stock',1);await cur_frm.set_value('disable_rounded_total',1);cur_frm.clear_table('items');cur_frm.clear_table('taxes');
    const row=cur_frm.add_child('items');await frappe.model.set_value(row.doctype,row.name,'item_code','SYNTHETIC-VAT-ASSET-AVF');
   },foreign);
   await page.waitForFunction(()=>!frappe.request.ajax_count&&cur_frm.doc.items[0]?.uom);
   await page.evaluate(async({foreign,source,abbr})=>{
    const row=cur_frm.doc.items[0];
    for(const [field,value] of Object.entries({qty:foreign?2:1,rate:foreign?50:1000,expense_account:source.items[0].expense_account,cost_center:source.cost_center,asset_location:source.items[0].asset_location}))if(value!=null)await frappe.model.set_value(row.doctype,row.name,field,value);
    if(foreign){await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_delivery_date','2026-10-17');await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_exchange_rate',11);}
    await frappe.model.set_value(row.doctype,row.name,'item_tax_template',(foreign?'Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag':'Tjenestekjøp fra utlandet – kvartalsgrunnlag før MVA-registrering')+' - '+abbr);
    if(foreign)await frappe.model.set_value(row.doctype,row.name,'custom_norway_deduction_percent',60);
   },{foreign,source,abbr});
   await page.waitForFunction(foreign=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview&&cur_frm.doc.grand_total===(foreign?100:1000)&&(!foreign||cur_frm.doc.taxes.some(r=>r.account_head.startsWith('2714 ')&&r.base_tax_amount===165)),foreign);
   await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(true));
   await page.getByText(foreign?'Leveringsdato for MVA':'Tjenestekjøp fra utlandet før MVA-registrering',{exact:true}).first().waitFor({state:'visible'});
   await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(false));
   await page.getByRole('button',{name:'Lagre',exact:true}).click();
   await page.waitForFunction(()=>!cur_frm.is_new()&&!cur_frm.is_dirty()&&!frappe.request.ajax_count);
   const result=await page.evaluate(()=>({system:frappe.user_roles.includes('System Manager'),asset:cur_frm.doc.items[0].is_fixed_asset,total:cur_frm.doc.grand_total,valuation:cur_frm.doc.items[0].valuation_rate,input:cur_frm.doc.taxes.find(r=>r.account_head.startsWith('2714 '))?.base_tax_amount||0,cost:cur_frm.doc.taxes.find(r=>r.custom_norway_vat_cost)?.base_tax_amount||0,category:cur_frm.doc.taxes.find(r=>r.custom_norway_vat_cost)?.category,quarter:cur_frm.doc.items[0].custom_norway_quarterly_service||0,type:cur_frm.doc.custom_norway_vat_return_type}));
   assert.equal(result.system,false);assert.equal(result.asset,1);
   if(foreign){assert.equal(result.total,100);assert.equal(result.valuation,555);assert.equal(result.input,165);assert.equal(result.cost,110);assert.equal(result.category,'Valuation and Total');}
   else{assert.equal(result.total,1000);assert.equal(result.input,0);assert.equal(result.cost,0);assert.equal(result.quarter,1);assert.equal(result.type,'Reverse-charge quarterly return');}
   const saved=await page.evaluate(()=>({name:cur_frm.doc.name,csrf:frappe.csrf_token}));
   assert.equal((await context.request.delete(`/api/resource/Purchase%20Invoice/${encodeURIComponent(saved.name)}`,{headers:{'X-Frappe-CSRF-Token':saved.csrf}})).status(),202);
  }
  await draft(true);await draft(false);
  const scope=encodeURIComponent('Reverse-charge quarterly return');
  await page.goto(`/desk/query-report/Norsk%20MVA-spesifikasjon?company=${encodeURIComponent(company)}&from_date=2026-07-01&to_date=2026-09-30&return_type=${scope}`);
  await page.waitForFunction(()=>frappe.query_report?.data?.some(r=>r.vat_code==='87')&&!frappe.request.ajax_count);
  const totals=await page.evaluate(()=>frappe.query_report.data.reduce((s,r)=>({base:s.base+(r.base_amount||0),output:s.output+(r.output_vat||0),input:s.input+(r.input_vat||0)}),{base:0,output:0,input:0}));
  assert.deepEqual(totals,{base:2100,output:525,input:0});assert.deepEqual(errors,[]);
  console.log('PASS ordinary Norwegian Asset EUR draft100/valuation555 per unit/input165/cost110; untaxed quarterly Asset draft1000, native quarter report2100/525; no SystemManager');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
