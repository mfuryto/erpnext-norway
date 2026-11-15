// Native annual facts form and Script Report, ordinary accounting roles in NB.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  assert.equal((await context.request.post('/api/method/login',{form:{usr:'runtime-enk-tax@example.invalid',pwd:'Synthetic-annual-owner-only-2026!'}})).status(),200);
  const response=await context.request.get('/api/resource/Norwegian%20Tax%20Facts?filters='+encodeURIComponent(JSON.stringify({company:'Runtime ENK Annual',fiscal_year:'2026'})));
  assert.equal(response.status(),200);const facts=(await response.json()).data[0].name;
  const page=await context.newPage();page.setDefaultTimeout(60000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/desk/norwegian-tax-facts/'+encodeURIComponent(facts));
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Norwegian Tax Facts'&&!frappe.request.ajax_count);
  const labels=await page.evaluate(()=>({system:frappe.user_roles.includes('System Manager'),
   values:__(cur_frm.fields_dict.tax_values.df.label),person:__(cur_frm.fields_dict.person_enabled.df.label),
   shielding:__(cur_frm.fields_dict.shielding_choice.df.label),none:__('Not assessed')}));
  assert.deepEqual(labels,{system:false,values:'Skatte- og formuesverdier',person:'Utarbeid personinntektsgrunnlag',shielding:'Skjermingsfradrag',none:'Ikke vurdert'});
  await page.getByRole('button',{name:'Norsk ENK-grunnlag',exact:true}).click();
  await page.waitForFunction(()=>frappe.query_report?.report_name==='Norsk ENK-grunnlag'&&frappe.query_report.data?.some(r=>r.section==='Personinntekt — beregning')&&!frappe.request.ajax_count);
  const report=await page.evaluate(()=>({company:frappe.query_report.get_filter_value('company'),
   person:frappe.query_report.data.find(r=>r.description==='Beregnet personinntekt').amount,
   tax:frappe.query_report.data.find(r=>r.description==='Beregnet næringsresultat').amount,
   label:frappe.query_report.get_filter('show_accounts').$wrapper.text().trim(),
   columns:frappe.query_report.columns.map(r=>r.label),rows:frappe.query_report.data.length}));
  assert.equal(report.company,'Runtime ENK Annual');assert.equal(report.tax,85000);assert.equal(report.person,84000);
  assert.match(report.label,/Vis kontodetaljer/);assert(report.columns.includes('Formuesverdi før rabatt'));assert(report.rows>70);
  await page.screenshot({path:'/tmp/erpnext-enk-annual-nb.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS native annual facts labels and report in NB, ordinary owner without System Manager, tax85000/person84000 and distinct book/tax/wealth columns');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
