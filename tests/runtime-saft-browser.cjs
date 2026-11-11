const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;
 assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const context=await browser.newContext({baseURL:base});
  const login=await context.request.post('/api/method/login',{form:{usr:'runtime-owner@example.invalid',pwd:'Synthetic-owner-runtime-only-2026!'}});
  assert.equal(login.status(),200);
  const page=await context.newPage();page.setDefaultTimeout(60000);
  await page.goto('/desk/company/Runtime%20Norwegian%20Example');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Company'&&cur_frm.doc.name==='Runtime Norwegian Example'&&!frappe.request.ajax_count);
  await page.getByRole('button',{name:'Last ned SAF-T',exact:true}).click();
  await page.getByRole('dialog').getByText('Fra dato',{exact:true}).waitFor();
  await page.getByRole('dialog').getByText('Til dato',{exact:true}).waitFor();
  const query=new URLSearchParams({company:'Runtime Norwegian Example',from_date:'2026-01-01',to_date:'2026-12-31'});
  const url='/api/method/erpnext_norway.saft.download?'+query.toString();
  await page.waitForFunction(()=>window.cur_dialog?.fields_dict?.from_date);
  await page.evaluate(()=>cur_dialog.set_values({from_date:'2026-01-01',to_date:'2026-12-31'}));
  const downloading=page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button',{name:'Last ned',exact:true}).click();
  const download=await downloading;
  assert.match(download.suggestedFilename(),/^SAF-T_Financial_/);
  const body=require('node:fs').readFileSync(await download.path(),'utf8');
  assert.match(body,/<AuditFile/);assert.match(body,/<AuditFileVersion>1.40<\/AuditFileVersion>/);
  assert.match(body,/<TaxCode>0<\/TaxCode>/);
  // The following year downloads native opening balances through the same UI.
  await page.getByRole('button',{name:'Last ned SAF-T',exact:true}).click();
  await page.waitForFunction(()=>window.cur_dialog?.fields_dict?.from_date);
  await page.evaluate(()=>cur_dialog.set_values({from_date:'2027-01-01',to_date:'2027-12-31'}));
  const nextDownloading=page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button',{name:'Last ned',exact:true}).click();
  const nextDownload=await nextDownloading;
  assert.match(nextDownload.suggestedFilename(),/^SAF-T_Financial_/);
  const nextBody=require('node:fs').readFileSync(await nextDownload.path(),'utf8');
  assert.match(nextBody,/<AuditFileVersion>1.40<\/AuditFileVersion>/);
  assert.match(nextBody,/<SelectionStartDate>2027-01-01<\/SelectionStartDate>/);
  assert.match(nextBody,/<SelectionEndDate>2027-12-31<\/SelectionEndDate>/);
  assert.doesNotMatch(nextBody,/<GeneralLedgerEntries>/);
  // A selection spanning fiscal years still uses the native in-form error UI.
  await page.getByRole('button',{name:'Last ned SAF-T',exact:true}).click();
  await page.waitForFunction(()=>window.cur_dialog?.fields_dict?.from_date);
  await page.evaluate(()=>cur_dialog.set_values({from_date:'2026-01-01',to_date:'2027-12-31'}));
  await page.getByRole('dialog').getByRole('button',{name:'Last ned',exact:true}).click();
  await page.getByText('Velg fra- og til-dato innenfor samme regnskapsår.',{exact:true}).waitFor();
  const guest=await browser.newContext({baseURL:base});
  assert.equal((await guest.request.get(url)).status(),403);
  console.log('PASS ordinary owner Norwegian Company/date dialog, actual2026/2027 XML downloads, native cross-year error and guest rejection');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
