// Native workspace widgets, desktop tiles and date controls on synthetic data.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
(async () => {
    const base = process.env.ERP_LANGUAGE_TEST_URL;
    assert.match(base || '', /^http:\/\/127\.0\.0\.1:\d+$/);
    const output = process.env.ERP_LANGUAGE_TEST_OUTPUT || '/tmp/erpnext-language-surfaces';
    await fs.mkdir(output, {recursive:true});
    const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
    try {
        const context = await browser.newContext({baseURL:base, viewport:{width:1440,height:1080}});
        const login = await context.request.post('/api/method/login', {form:{
            usr:'runtime-ui-manager@example.invalid', pwd:'Synthetic-ui-manager-only-2026!'
        }});
        assert.equal(login.status(),200);
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto('/desk');
        await page.waitForSelector('.desktop-icon');
        const mode = await page.evaluate(() => frappe.boot.desktop_page);
        assert.equal(mode,'Desktop Icons');
        const invitation = page.getByRole('button',{name:'Nei takk',exact:true});
        if (await page.evaluate(() => !!frappe.boot.show_new_navigation_prompt)) {
            await invitation.waitFor();
            await invitation.click();
        }
        await page.locator('.desktop-icon[data-id="ERPNext"]').first().click();
        await page.getByText('ERPNext-innstillinger',{exact:true}).last().waitFor();
        assert(!(await page.locator('body').innerText()).split('\n').includes('ERPNext Settings'));
        await page.screenshot({path:`${output}/all-apps-nb.png`,fullPage:true});
        await page.keyboard.press('Escape');
        console.log('PASS native All apps icon grid and ERPNext-folder buttons in NB; stored module identities retained');

        await page.goto('/app/accounting');
        const dock = page.locator('#desk-dock .dock-items');
        for (const text of ['Oppsett','Regnskap','Salg','Kjøp','Lager','Produksjon','Prosjekter','Eiendeler','Kvalitet']) {
            await dock.locator('.dock-item-label').filter({hasText:new RegExp('^'+text+'$')}).waitFor({state:'attached'});
        }
        await dock.getByRole('button',{name:'Oppsett',exact:true}).hover();
        await page.locator('.es-tooltip--plain').filter({hasText:/^Oppsett$/}).waitFor();
        const dockLabels = await dock.locator('.dock-item-label').allTextContents();
        for (const text of ['Setup','Accounts','Selling','Buying']) assert(!dockLabels.includes(text),dockLabels);
        const customEntry = await page.evaluate(() => {
            const sidebar = frappe.app.sidebar;
            const app = sidebar.get_sidebar_app();
            const row = app.dock.find(row => sidebar.dock_entry(row));
            const custom = {...row,title:'Min egen meny'};
            const entry = sidebar.dock_entry(custom);
            return {label:entry.label,link:entry.link_to,source:row.link_to,title:custom.title};
        });
        assert.equal(customEntry.label,'Min egen meny');
        assert.equal(customEntry.link,customEntry.source);
        assert.equal(customEntry.title,'Min egen meny');
        await dock.getByRole('button',{name:'Salg',exact:true}).click();
        await page.waitForFunction(() => frappe.app.sidebar.current_module === 'Selling');
        await page.screenshot({path:`${output}/dock-nb.png`,fullPage:true});
        console.log('PASS actual left dock: Oppsett/Regnskap/Salg/Kjøp and native Selling navigation');

        for (const [route,expected,english] of [
            ['home',['Bli kjent med ERPNext','Inviter medarbeidere'],['Get to know ERPNext','Invite your team']],
            ['accounting',['Gjør regnskapet klart','Registre og lønnsomhet','Fordringer og gjeld'],['Get your books ready','Registers & Profitability','Receivables & Payables']],
            ['selling',['Årets salg','Salgsrapporter','Kunderapporter'],['Annual Sales','Sales Reports','Customer Reports']],
            ['buying',['Årets innkjøp','Innkjøpsrapporter','Leverandørrapporter'],['Annual Purchase','Purchase Reports','Supplier Reports']],
            ['stock',['Hold oversikt over lageret','Lagerrapporter','Samlet lagerverdi'],['Keep track of your stock','Stock Reports','Total Stock Value']],
            ['assets',['Hold oversikt over foretakets eiendeler','Eiendelsrapporter'],['Track what your business owns','Asset Reports']],
            ['projects',['Planlegg og gjennomfør prosjekter','Ufullførte oppgaver'],['Plan and deliver projects','Non Completed Tasks']],
            ['manufacturing',['Planlegg og gjennomfør produksjon','Produksjonsrapporter'],['Plan and run production','Production Reports']],
            ['quality',['Hold oversikt over kvaliteten','Kvalitetsrapporter'],['Keep quality in check','Quality Reports']],
        ]) {
            await page.goto(`/app/${route}`);
            await page.waitForFunction(() => window.frappe?.boot?.lang === 'nb');
            for (const text of expected) {
                await page.waitForFunction(value => document.body.innerText.includes(value),text);
            }
            const body = await page.locator('body').innerText();
            for (const text of english) assert(!body.split('\n').includes(text),`${route}: ${text}`);
            if (route === 'home') assert.match(body,/God (morgen|ettermiddag|kveld),/);
            await page.waitForFunction(() => !document.getAnimations().some(animation =>
                animation.playState === 'running' && animation.effect.getTiming().iterations !== Infinity));
            await page.screenshot({path:`${output}/${route}-nb.png`,fullPage:true});
        }
        console.log('PASS actual NB home and eight module workspaces: onboarding titles, progress, report groups, charts and number cards');
        await page.goto('/app/bank-reconciliation-tool');
        await page.waitForFunction(() => window.cur_frm?.doctype === 'Bank Reconciliation Tool');
        for (const text of ['Last opp kontoutskrift','Avstem automatisk','Hent uavstemte poster']) {
            await page.getByText(text,{exact:true}).first().waitFor();
        }
        await page.getByRole('link',{name:'den nye bankmodulen',exact:true}).waitFor();
        await page.screenshot({path:`${output}/bank-reconciliation-nb.png`,fullPage:true});
        await page.goto('/app/payment-reconciliation');
        await page.waitForFunction(() => window.cur_frm?.doctype === 'Payment Reconciliation');
        assert((await page.locator('body').innerText()).includes('Betalingsavstemming'));
        console.log('PASS actual native bank/payment reconciliation actions and translated intro link');
        await page.goto('/app/sales-invoice/new-sales-invoice-language-calendar');
        await page.waitForFunction(() => window.cur_frm?.doctype === 'Sales Invoice' && cur_frm.doc.__islocal);
        await page.evaluate(async () => {
            await frappe.after_ajax();
            await cur_frm.set_value('set_posting_time',1);
            await cur_frm.set_value('posting_date','2026-10-24');
        });
        // Wait for the rendered, editable control and use a real click. A
        // synthetic focus event during setup does not prove it is interactive.
        await page.locator('.frappe-control[data-fieldname="posting_date"] input:visible').first().click();
        const calendar = page.locator('.datepicker.active');
        await calendar.waitFor();
        const calendarText = await calendar.innerText();
        assert(calendarText.includes('oktober'),calendarText);
        assert(calendarText.includes('I dag'),calendarText);
        const locale = await page.evaluate(() => cur_frm.fields_dict.posting_date.datepicker.opts.language);
        assert.equal(locale,'nb');
        await page.screenshot({path:`${output}/calendar-nb.png`,fullPage:true});
        const previousLanguage = await page.evaluate(() => frappe.boot.user.language);
        try {
            await page.evaluate(() => frappe.db.set_value('User',frappe.session.user,'language','en'));
            await page.goto('/app/sales-invoice/new-sales-invoice-language-english');
            await page.waitForFunction(() => window.cur_frm?.doctype === 'Sales Invoice' && cur_frm.doc.__islocal);
            assert.equal(await page.evaluate(() => frappe.boot.lang),'en');
            assert.equal(await page.evaluate(() => !!$.fn.datepicker.language.nb),false);
            assert.equal(await page.evaluate(() => __('Annual Sales')),'Annual Sales');
            await page.goto('/app/accounting');
            for (const text of ['Setup','Accounts','Selling','Buying']) {
                await page.locator('#desk-dock .dock-item-label').filter({hasText:new RegExp('^'+text+'$')}).waitFor({state:'attached'});
            }

        } finally {
            await page.evaluate(language => frappe.db.set_value('User',frappe.session.user,'language',language),previousLanguage);
        }
        console.log('PASS native NB calendar uses Norwegian CLDR names and Today; English session retains native locale and text');
        assert.deepEqual(errors,[]);
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error);process.exit(1);});
