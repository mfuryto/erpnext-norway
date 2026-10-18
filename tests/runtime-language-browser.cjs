// Run only against runtime-smoke.sh's synthetic fixture, using Playwright 1.58.2.
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.ERP_LANGUAGE_TEST_URL;
  assert.match(base || '', /^http:\/\/127\.0\.0\.1:\d+$/);
  const output = process.env.ERP_LANGUAGE_TEST_OUTPUT || '/tmp/erpnext-language-browser';
  await fs.mkdir(output, {recursive: true});
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const context = await browser.newContext({baseURL: base, viewport: {width: 1440, height: 1080}});
    const login = await context.request.post('/api/method/login', {form: {
      usr: 'runtime-owner@example.invalid', pwd: 'Synthetic-owner-runtime-only-2026!'
    }});
    assert.equal(login.status(), 200, await login.text());
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const fields = encodeURIComponent(JSON.stringify(['name', 'is_return', 'company_address']));
    const filters = encodeURIComponent(JSON.stringify({company: 'Runtime Norwegian Example', docstatus: 1, language: 'nb', company_address: ['is', 'set']}));
    const response = await context.request.get(`/api/resource/Sales%20Invoice?fields=${fields}&filters=${filters}`);
    const sales = (await response.json()).data;
    assert(sales.some(row => row.is_return));
    for (const sale of [sales.find(row => !row.is_return), sales.find(row => row.is_return)]) {
      await page.goto(`/app/sales-invoice/${sale.name}`);
      await page.waitForFunction(name => window.cur_frm?.doc?.name === name, sale.name);
      const labels = await page.evaluate(() => ({
        time: cur_frm.fields_dict.posting_time.$wrapper.find('label').first().text().trim(),
        date: cur_frm.fields_dict.posting_date.$wrapper.find('label').first().text().trim(),
        due: cur_frm.fields_dict.due_date.$wrapper.find('label').first().text().trim(),
        language: cur_frm.fields_dict.language.df.label,
        languageReadOnly: cur_frm.fields_dict.language.df.read_only,
        translated: __('Print Language', null, 'Sales Invoice'),
        invoice: __('Sales Invoice'), purchase: __('Purchase Invoice'),
        journal: __('Journal Entry'), payment: __('Payment Entry'),
        nativeStatus: cur_frm.doc.status, systemManager: frappe.user_roles.includes('System Manager')
      }));
      assert.equal(labels.date, 'Bokføringsdato');
      assert.equal(labels.time, 'Bokføringstidspunkt');
      assert.equal(labels.due, 'Forfallsdato');
      assert.equal(labels.translated, 'Dokumentspråk');
      assert.equal(labels.languageReadOnly, 0);
      assert.equal(labels.invoice, 'Salgsfaktura');
      assert.equal(labels.purchase, 'Leverandørfaktura');
      assert.equal(labels.journal, 'Bokføringsbilag');
      assert.equal(labels.payment, 'Betalingsregistrering');
      assert.equal(labels.systemManager, false);
      // The stored API status remains English; translation does not mutate business data.
      assert(['Unpaid', 'Overdue', 'Return', 'Credit Note Issued', 'Paid', 'Submitted'].includes(labels.nativeStatus));
      await page.screenshot({path: `${output}/${sale.is_return ? 'credit' : 'invoice'}-desk-nb.png`, fullPage: true});
      const fileFilters = encodeURIComponent(JSON.stringify({attached_to_doctype: 'Sales Invoice', attached_to_name: sale.name, is_private: 1}));
      const filesResponse = await context.request.get(`/api/resource/File?fields=${encodeURIComponent('["file_url"]')}&filters=${fileFilters}`);
      const file = (await filesResponse.json()).data[0];
      assert(file?.file_url.startsWith('/private/files/'));
      const original = await context.request.get(file.file_url);
      assert.equal(original.status(), 200);
      assert((await original.body()).subarray(0, 5).equals(Buffer.from('%PDF-')));
      const guest = await browser.newContext({baseURL: base});
      assert.equal((await guest.request.get(file.file_url)).status(), 403);
      await guest.close();
      for (const language of ['nb', 'en']) {
        const query = new URLSearchParams({doctype: 'Sales Invoice', name: sale.name,
          format: 'Norway Invoice', _lang: language, no_action_banner: '1'});
        await page.goto('/printview?' + query);
        await page.locator('.print-format').waitFor();
        const body = await page.locator('.print-format').innerText();
        assert(body.includes(language === 'nb' ? 'Organisasjonsnummer' : 'Organisation number'));
        assert(body.includes(language === 'nb' ? 'Beskrivelse' : 'Description'));
        assert(body.includes(language === 'nb' ? 'Enhetspris' : 'Unit Price'));
        if (sale.is_return) assert(body.includes(language === 'nb' ? 'Kreditnota' : 'Credit Note'));
        await page.screenshot({path: `${output}/${sale.is_return ? 'credit' : 'invoice'}-print-${language}.png`, fullPage: true});
      }
    }
    for (const [doctype, route] of [['Purchase Invoice', 'purchase-invoice'], ['Journal Entry', 'journal-entry'], ['Payment Entry', 'payment-entry'], ['Quotation', 'quotation']]) {
      const filters = encodeURIComponent(JSON.stringify({company: 'Runtime Norwegian Example', docstatus: 1}));
      const response = await context.request.get(`/api/resource/${encodeURIComponent(doctype)}?fields=${encodeURIComponent('["name"]')}&filters=${filters}`);
      const row = (await response.json()).data[0];
      assert(row, doctype);
      await page.goto(`/app/${route}/${row.name}`);
      await page.waitForFunction(name => window.cur_frm?.doc?.name === name, row.name);
      const dateLabel = await page.evaluate(() => (cur_frm.fields_dict.posting_date || cur_frm.fields_dict.transaction_date).$wrapper.find('label').first().text().trim());
      assert.equal(dateLabel, doctype === 'Quotation' ? 'Dato' : 'Bokføringsdato');
      await page.screenshot({path: `${output}/${route}-desk-nb.png`, fullPage: true});
      if (doctype === 'Quotation') {
        for (const language of ['nb', 'en']) {
          await page.goto('/printview?' + new URLSearchParams({doctype, name: row.name, format: 'Norway Quotation', _lang: language}));
          const body = await page.locator('.print-format').innerText();
          assert(body.includes(language === 'nb' ? 'Tilbud' : 'Quotation'));
          assert(body.includes(language === 'nb' ? 'Beskrivelse' : 'Description'));
        assert(body.includes(language === 'nb' ? 'Enhetspris' : 'Unit Price'));
          await page.screenshot({path: `${output}/quotation-print-${language}.png`, fullPage: true});
        }
      }
    }
    assert.deepEqual(errors, []);
    console.log('PASS actual owner sales/purchase/journal/payment/quotation Desk NB labels and independent NB/EN document previews; native statuses unchanged');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
