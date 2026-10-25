# Gjennomgang av gjenbruk av ERPNext-kjernen

Gjennomgått 24. oktober 2026 mot ERPNext 16.51.1 / Frappe 16.52.0 i det
låste imaget. Omfanget er den leverte norske appen til og med 0.4.4,
kontoplandata, modulovergangen og bygge-/driftsskriptene. Korrigeringen i 0.4.5
er beskrevet nedenfor. Dette er en gjennomgang av funksjonsgjenbruk, ikke en
ny regnskapsmessig godkjenning av hele produktet eller MVA-planen.

## Konkret overlapp som er rettet

ERPNext har allerede `add_taxes_from_tax_template(child_item, parent_doc,
db_insert=False)` i `erpnext.controllers.accounts_controller`. Funksjonen
legger til en manglende avgiftskonto på et dokument uten å lagre en egen rad i
databasen. Den følger **Automatically add Taxes and Charges from Item Tax
Template** i Accounts Settings, som er på som standard. Appen opprettet også
disse ordinære radene selv. Det var unødvendig overlapp.

App 0.4.5 bruker nå denne kjernefunksjonen. Tilpasningen velger riktig side
av den delte norske vareavgiftsmalen (salg eller kjøp), og setter norske
beskrivelser, fradrags-/verdsettingsmetadata og valgt grunnlag på kjernens rad.
Satser og beløp beregnes fortsatt av kjernen fra den ordinære vareavgiftsmalen.
Ingen global innstilling slås på for å tvinge gjennom automatikk.

Kjernen finner eksisterende rader etter **konto**, mens MVA på både vare og
frakt kan kreve flere **grunnlag på samme konto**. Bare en slik ekstra rad
legges fortsatt til av appen når kontoen allerede finnes. Appen skal heller
ikke gjøre dette dersom brukeren har slått av den native automatikken. Da må
de nødvendige radene angis eksplisitt, eller standardinnstillingen aktiveres.
Manglende rader skal avvises fremfor at leverandørens fakturabeløp blir for lavt.

Prøvene dekker blandet 25/15/12 %-salg og kjøp med 60/0 % fradrag, både med
standardautomatikk og med denne avslått og eksplisitte rader. Eksisterende
frakt-, retur-, lager-, driftsmiddel- og nettleserprøver dekker adapterens
øvrige grunnlags-/fordelingskrav.

## Gjennomgått levert funksjonalitet

| Område / appkode | Eksisterende funksjon som brukes | Gjenværende tillegg og begrunnelse |
| --- | --- | --- |
| Kontoplan: `chart.py`, byggedata | `create_charts`, native malvalg/trevisning og Company-defaults | 745 norske kontokoder/navn er data. Kjernen søker maler i sin egen mappe og eksponerer ikke en ekstern malprovider. Referanse til datafil og smal Company-utvidelse sender data til kjernen; ingen egen kontoimportør. |
| Nummerering: `numbering.py`, `setup.py` | Document Naming Rule, native teller og transaksjonell radlås | Ingen egen teller. Vernet avviser sletting/omdøping, nullstilling og endret identitet som de dokumenterte kjerneprøvene tillater. Native amendment bruker suffiks før nummerregelen; appen krever ny ordinær faktura/kreditnota. |
| Vedlegg: `preservation.py` | File, privat tilgang og `protect_attached_files` via Property Setter | Kjernen verner innsendte vedlegg mot sletting. Tillegget dekker kansellerte bilag, frakobling og endring/overskriving som standardegenskapen ikke dekker. Utvidelsen delegerer filskriving til kjernen. |
| Språk: `translations/nb.csv`, `tax_names.py` | Native oversettelseskatalog, oversettelseskontekst og lenkeoppdaterende `rename_doc` | Oversettelsesdata og retting av eksakte seednavn. Ingen egen oversettelsesmotor eller tekstbytte i DOM. Eksplisitte brukerdefinerte navn beholdes. |
| Salgsdokumenter: `printing.py`, Jinja-mal | Print Format, `get_print`, `save_file`, native språkfelt, formatering, avgiftsutskrift og bankvalg | Norsk/engelsk malinnhold og privat PDF ved innsending. Vanlig utskrift gjengir dagens opplysninger; den er ikke en bevart original ved innsending. Ingen ny filoppbevaring eller utskriftsmotor. |
| MVA-registrering: `vat.py`, `company.js` | Company.tax_id, Custom Field/Version og daterte Tax Rules | Norsk registreringsstatus, bekreftet virkningsdato og MVA-merke mangler i Company. Appen konfigurerer ordinære maler/regler og hindrer tidlig fradrag; ingen egen avgiftsberegning. |
| Satser, koder og fradrag: `vat_catalog.py`, `vat.js` | Item Tax Template, avgiftsrader, native kalkulator og vanlig linjemapping | Norske koder og et brukerbestemt fradragsprosentvalg mangler. Appen fordeler **satser** til native maler. Ordinær radoppretting er korrigert til kjernens funksjon i 0.4.5; særskilt grunnlag/metadata er adapterkode. |
| Kostnadskonto i vareavgiftsmal: `item_tax.py` | Native konto-/foretakskontroll og ordinær malvalidering | Kjernen godtar Expense Account, men avviser Cost of Goods Sold i Item Tax Template, selv om fakturarader og hovedbok godtar kontoen. Smal utvidelse tillater denne eksisterende kontotypen uten å endre kontoen eller erstatte beregning/postering. |
| Kreditnota: `vat_returns.py` | Native kreditnota, original linjereferanse, lagrede satser og Item Tax Template | Kjernens `get_item_tax_map` leser dagens mal, også når fakturaens mal er endret. Appen konfigurerer opprinnelige satser bare ved faktisk avvik. Kjernen beregner kreditnotaen; ingen egen retur-/avgiftsmotor. |
| Mottak, lager og driftsmidler: `vat_valuation.py` | Valuation and Total, Item Wise Tax Detail, Landed Cost Voucher, native GL/SLE/Asset og kansellering | Appen automatiserer valg av konto/grunnlag og fordeling av allerede beregnede beløp ved endret fradrag/delfakturering. Dette er egen adapterkode, inkludert kumulativ ørefordeling, ikke bare statiske innstillinger. Kjernen håndterer verdsetting og postering. |
| Frakt og returkilde: `vat_valuation.py`, `vat.js` | Native Total, Landed Cost Voucher, eksisterende faktura-/mottakslenker og Autocomplete | Valuation and Total på On Previous Row gir feil fordeling i prøvd flerlinjetilfelle. Native Total + LCV gir riktig resultat; adapteren automatiserer denne standardflyten. Native prisdifferanse på mottaket gjelder varepris og erstatter ikke denne MVA-fordelingen. Eksisterende returlinjefelt vises; ingen ny kildetabell. |
| MVA-spesifikasjon: norsk Script Report, `vat_journal.py` | Item Wise Tax Detail, fakturaer, Journal Entry, GL Entry og native periodelåser | Kjernen har salgs-/kjøpsregistre og andre lands MVA-rapporter, men ingen norsk kode-/spesifikasjonsrapport med denne dokumentperioden. VAT Audit Report er uttrykkelig begrenset til Sør-Afrika. Rapporten grupperer/avstemmer eksisterende posteringer og erstatter ingen hovedbok. Utland/import er fortsatt ikke samlet ferdig. |
| Oppgjør og betaling: `vat_settlement.py`, `vat_journal.js` | Journal Entry, native `get_outstanding`, bankbilag og Bank Reconciliation | Tillegget foreslår norske oppgjørskontoer og differanse fra det avstemte grunnlaget. Betalingsforslaget er et uspart standard bankbilag. Kjernens betalingsmapper for kunde/leverandør krever part/reskontro og kan ikke brukes direkte på partsløse MVA-kontoer 1640/2740. Ingen betalings-/reskontromotor er erstattet. |
| Melding/kvittering: `vat_evidence.py` | Privat File vedlagt Company | Metadata og bevaringsmerke knytter grunnlag, melding og kvittering til perioden, også ved nullmelding uten oppgjørsbilag. Ingen ny meldings-/historikktabell. Innlevering skjer fortsatt i portalen. |
| Modulvisning: `deploy/module-visibility.py` | Module Profile, User.block_modules og Property Setter | Engangstilbakeføring av appens tidligere skjuling etter brukerens korrigerte bestilling. Senere brukervalg beholdes. Ingen ny modulmeny eller automatisk skjuling. |
| Drift: Compose, Dockerfile og skripter | Låste standardimages, Docker Compose og native bench-konfigurasjon, backup, install-app, migrate og restore | Skriptene samordner stopp av skrivere, backup av eksisterende runtime-konfigurasjon og imagebytte. De implementerer ikke databasebackup eller migreringsmotor. Oppdatering er ikke ny installasjon; eldre overgangs-/klargjøringsskripter kjøres ikke i den normale oppdateringsblokken. |
| Repovern: hooks, rulesets og CI | Git/GitHub branch protection, PR og Actions | Konfigurasjon av eksisterende vern, to grener og låste avhengigheter. Ingen egen Git- eller godkjenningsmekanisme. |

## Kilder og etterprøving

Kildene er kode fra det låste kjørende testimaget, særlig disse oppstrømsfilene:

- ERPNext: `controllers/accounts_controller.py`, `controllers/buying_controller.py`,
  `controllers/sales_and_purchase_return.py`, `stock/get_item_details.py`,
  `accounts/doctype/item_tax_template/item_tax_template.py`,
  `stock/doctype/landed_cost_voucher/landed_cost_voucher.py`,
  `stock/doctype/purchase_receipt/purchase_receipt.py`,
  `accounts/doctype/journal_entry/journal_entry.py`,
  `accounts/doctype/payment_entry/payment_entry.py`,
  `accounts/doctype/bank_account/bank_account.py`,
  `accounts/doctype/account/chart_of_accounts/chart_of_accounts.py`,
  `setup/doctype/company/company.py` og `regional/report/vat_audit_report/`.
- Frappe: `model/naming.py`, `core/doctype/document_naming_rule/`,
  `core/doctype/file/file.py` og native dokument-/utskriftsfunksjoner.

De eksisterende isolerte prøvene er fordelt på `runtime-native-controls.py`,
`runtime-core-accounting.py`, `runtime-company-chart.py`, `runtime-app.py`,
språk-/dokumentprøvene og `runtime-vat-*.py` med tilhørende nettleserprøver.
Hele appprøven eksporterer og gjenoppretter native backup og sammenligner
posteringer, lenker og PDF-originaler etter migrering. Vertstestene dekker
oppdaterings-/backupfeil og bevaring av runtime-valg.

Se [native kontrollfunn](native-controls.md), [kontoplan](norwegian-chart.md),
[dokumenter](sales-documents.md), [MVA-planens dokumenterte gap](vat-plan.md)
og [lager-/fraktprøvene](vat-valuation.md) for regnskapsfasit og avgrensninger.
Driftsmidler i flerlinjefrakt, utenlandsflyter og resten av hovedplanen åpnes
ikke av denne gjennomgangen. Ingen funksjon skal implementeres videre før
relevant standardoppsett er prøvd og det gjenstående gapet er konkret beskrevet.

Direkte kontrollprøver under gjennomgangen bekreftet også:

- Kjernens uendrede Item Tax Template-validator avviser COGS; den smale
  utvidelsen tillater kontoen uten å endre kontotypen.
- VAT Audit Report avviser et norsk foretak med sin regionkontroll.
- Native kreditnotas avgiftskart leser den endrede satsen 12 %, som forklarer
  behovet for å bevare den opprinnelige 25 %-behandlingen.
- Direkte native Valuation and Total på det prøvde flerlinjefraktgrunnlaget
  gir 1 052,50 i lagerverdi mot forventet 1 105. Tillegget skal bruke native
  Total + LCV for dette tilfellet, ikke erstatte kjernens verdsettingsmetode.
- Sammenligning mot det låste grunnimaget viste identiske innholdshasher for
  4 856 ERPNext-filer og 3 105 Frappe-filer (Python, JavaScript, JSON, HTML,
  CSV og CSS). Appens ekstra malreferanse er en egen symlenke; ingen av
  disse eksisterende kjernefilene er endret.

Oppfølging ved ERPNext 16.52.1 / Frappe 16.53.0: native AccountsController
avviser nå sletting av kansellerte bilag med Immutable Ledger aktivert. Fra
app 0.4.7 brukes dette vernet direkte. Appvernet beholdes når innstillingen er
av og for nummererte kladder/tilbud; filgapene består. Se core-update.md.
