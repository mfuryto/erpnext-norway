# Overgang til ERPNext Norway

Beslutning 2026-10-18: ERPNext blir prosjektets videre grunnlag. Dolibarr Norway
settes på vent; repo, historikk, installasjonsfiler beholdes. Ingen ny backup av Dolibarr eller tilbakeføringsfunksjon skal lages. Dolibarr er
oppgitt ikke tatt i ordinær bruk, så ingen produksjonshistorikk skal migreres som standard.

## Førende prinsipp

Brukeren har gitt varig godkjenning til promotering: ferdige endringer skal alltid
fra staging til main gjennom PR og beståtte aktuelle CI-kontroller, uten ny
godkjenningsrunde. Synkroniser staging etter sammenslåing uten force-push. Dette
gir ikke servertilgang; brukeren kjører fortsatt serverblokkene selv.

ERPNext-kjernen er primær. Dolibarr Norway, ENK Norge og Peppol-tilleggene brukes
som referanser. Ikke installer dem automatisk, kopier tidligere kontrollag eller
bygg en ny brukerflate rundt hele ERPNext. For hvert område registreres bare:
krav → prøvd kjernefunksjon → faktisk gap → minste tilpasning → regnskapsfasit.
En slik intern arbeidsmatrise er ikke en bestilling av en ny kontrollside.

## Overført kunnskap og bevis

Referansegrunnlaget er Dolibarr Norway 0.86.0 ved commit
`cc5cb151c1bca9eb4c6b84dd69305191e2e3ef29`.
Se særlig docs/purchase-vat.md, docs/vat-period-close.md, docs/tax-accounts.md,
docs/saft-export.md, docs/year-end.md, docs/enk-tax-return.md, docs/deductions.md,
docs/paperless-accounting.md, docs/balance-overview.md og de faktiske
testene purchase-deduction.php, year-end-cycle.php og balance-overview.php.
Historiske planer er ikke fasit for nåværende dekningsgrad.

Full evaluering med PDF, testresultater og kildehenvisninger ligger lokalt i den
ignorerte mappen `local-handover/evaluation/`. Bevisarkivet inneholder ikke API-nøkler,
passord eller site-konfigurasjon. Det er testbevis, ikke et produksjonsoppsett.
Eksterne kilde- og datasetters lisens/proveniens må følge eventuell senere gjenbruk.

Utprøvd ERPNext 16.51.1/Frappe 16.52.0:

- 20 regnskapstilfeller besto samlet; ytterligere to prøver besto for blandet
  fradragsrett per linje og leverandørbetaling/avstemming etter årsskiftet.
- Fem HTTP-prøver besto: egendefinert felt gjennom standard REST, lesing,
  foretaksfiltrering, skriveavvisning og privat fil som ikke kan leses av gjest.
- Alle 745 kontonumre kunne importeres. Direkte kopiering av kildens payable-type
  ga feil standard leverandørkonto (2740); sett 2400 og øvrige defaults uttrykkelig.
- Fullt/delvis/intet MVA-fradrag og reverse charge kan føres med native avgiftsrader.
  Det tekniske maloppsettet er ikke ferdig norsk linjevalg eller norsk MVA-rapport.
- F######, K###### og T###### virket, men nummer tildeles ved lagring av kladd.
  Tidligere kladd kunne slettes mens senere nummer ble stående. Utstedelsesnummer,
  samtidighet og revisjonsspor må løses; masken alene lukker ikke gapet.
- Private filer er tilgangsstyrt, men administrator kunne slette et vedlegg fra
  en bokført kjøpsfaktura gjennom File-API. Norsk dokumentbevaring trenger vern.
- Bokmål er ufullstendig i faktiske skjermbilder. Lokaliser regnskapsflyten og malene
  målrettet; ikke anta at språkvalget gjør alt norsk.
- Period Closing Voucher og Accounting Period er native. I denne versjonen
  sperret også ferdig Period Closing Voucher postering/kansellering i perioden.
- Standardinnstillingen Enable Immutable Ledger var 0. Originaler og motrader
  ble beholdt i begge prøvde moduser, men reverseringsdato/rapportutvalg er forskjellig.
- Core-prøvene brukte administrator for bokføring. Vanlig eierbruker må kvalifiseres
  i den norske produktflyten, med rettigheter og negative prøver.

ENK Norge ved `94406e542ed991a8de237b9de44b8d1dd576b566` ble også undersøkt.
28 databasefrie prøver besto. På den nyere kjernen besto 186 av 187 integrasjonsprøver;
én timeseddeltest traff overlappende timer før den forventede satskontrollen.
Dette er et testavvik, ikke bevis på at vanlig timefakturering er feil. Appen er
referanse, ikke valgt produktavhengighet. Den bygger mye egen flate og har avgrenset
2026-omfang. EHF, flere bransjer og flere driftsmiddelsalg er ikke ferdig dekket.

## Produktomfang som videreføres

- Generisk norsk modul for varer og tjenester, ikke en programvarebransjemodul.
- Første konkrete regnskapsaksept: ett norsk ENK uten ansatte, NOK, kalenderår,
  norske bedrifts-/offentlige kunder og uttrykkelig kvalifiserte utenlandsforhold.
- Norsk/engelsk tilbud, faktura og kreditnota. Faktura/credit F/K med seks løpesifre,
  tilbud T med seks, kunde/leverandør med fem sifre og valgfritt skille/prefiks.
  Uavhengige stigende serier og brukerens startnummer må ivaretas med kjernen først.
- NOK er første støtteomfang. Omtrentlig EUR-pris er valgfritt, ikke ny valutamotor.
- Ingen sjekkbetalinger i norsk bruk. Ikke omdøp bank til balanse; bruk native balanse.
- MVA-melding leveres i Skatteetatens portal først. Direkteinnsending er ikke bestilt.
- ENK forskuddsskatt er personlig skatt; betalingen er en eiertransaksjon i foretaket
  når den faktisk går fra foretakets bank, ikke en driftskostnad.
- Årsgrunnlag skal hjelpe utfylling av næringsspesifikasjonen og vise sporbarhet,
  men ikke utgi seg for å være en full personlig skatteberegning eller innsending.
- Oppstartsveileder: enkel status, forklaring og lenker. Vanlige oppgaver på naturlig sted.
- Uttrykkelig språkkrav: oversett engelske elementer og rett feil norske fagbegreper
  i støttet arbeidsflyt og dokumenter. Følg [språkkrav og arbeidsordliste](language.md).
  Norsk språkvalg alene lukker ikke dette gapet; rettelser leveres i ekstern app.
- Oppdatert modulvalg: Behold ERPNext sitt standardoppsett for alle moduler.
  Tidligere skjuling av Lager, Produksjon, Prosjekter og Kvalitet tilbakeføres.
  Bevar senere brukervalg. Se [moduloppsett og aksept](module-defaults.md).

Bruk faktisk registreringsstatus, virkningsdato og gjeldende regelverk. Ikke anta
MVA-registrering bare fordi det skal faktureres. Foretaksform og kontoer er konfigurasjon.
Ikke utvid automatisk til AS-årsregnskap, lønn, utenlandske forbrukerregler eller særnæringer.

## Plan: fullfør ett støttet trinn før neste

1. **Drift og repo.** Bevar to grener og sikker arbeidsflyt. Klargjør standard ERPNext
   med Compose, privat konfigurasjon og data i prosjektets data-mappe. Prøv installasjon,
   oppdatering og ERPNext backup/restore. Overtak gammel HTTP-port først etter
   klargjøring; verifiser eksisterende proxy, TLS og Socket.IO. Den norske appen er ennå
   ikke installert i dette driftsgrunnlaget. Ingen reelle bilag før regnskapsaksept.
2. **Kjerne og norsk minimum.** Opprett en liten ekstern Frappe-app bare for faktiske gap.
   Prøv kontoplan/defaults, foretaksdata, org.nr/MVA, dokumentkrav, utstedelsesnummer,
   norsk/engelsk mal og dokumentbevaring. Ingen ekstra godkjennings- eller kontrollflate.
3. **Normal kjøps-/salgs-/bankflyt og MVA.** Velg behandling ved registrering. Prøv
   full/delvis/ingen fradragsrett per linje, kreditnota, reverse charge, betaling/refusjon
   og avrunding. Bruk native journaler, Payment Entry og Bank Reconciliation. Gjør MVA
   tydelig: grunnlag → portal → oppgjør → betaling/refusjon → avstemming og kvittering.
4. **SAF-T.** Gjenbruk regler/mapping og uavhengige fasiter, bygg adapter til ERPNext.
   1.40 må avstemmes mot hovedbok, åpning, reskontro og kilder. Kvalifiser årsversjon
   og gruppeliste før bruk; tidligere 2025–2026-støtte er ikke automatisk 2027-støtte.
   SAF-T må være klart før ordinær elektronisk bokføring tas i bruk.
5. **ENK skatt og årsavslutning.** Bruk native periodisering, balanse, låsing og Period
   Closing Voucher. Gjør forskuddsskatt/betaling og årsgrunnlag lett å finne. Rapporter
   for næringsspesifikasjon/fradrag må være årsspesifikke og sporbare. Kvalifiser behov
   for skattemessige saldogrupper separat; native Asset alene er ikke norsk skatteregel.
6. **Ekstern integrasjon.** Lisensarbeidet skjer i det separate prosjektet. Bruk standard
   REST/rettigheter først og valgfrie generiske adaptere ved reelt behov. Ingen leverandørnavn,
   personlige referanser eller tvungen avhengighet i regnskapsmodulen. Ingen Dolibarr-endringer.
7. **EHF sluttføring.** Lag/velg minste adapter på faktura/kreditnota. Gjenbruk EHF-fasiter
   og erfaringer, ikke en antatt ferdig landsmodul. Prøv faktisk Peppol-levering, feil,
   duplikatvern, ukjent resultat, status og kvittering før steget er ferdig.
8. **Samlet sluttkontroll sist.** Hele ordinære flyten, vanlig eierbruker, backup/restore,
   oppgraderinger, dokumentasjon og norsk regnskapsmessig aksept i eksplisitt omfang.
   Dette trinnet utsettes til EHF og de øvrige avtalte gapene er lukket.

## Videreføring av driftsprøver

Oppfølgingsarbeidet utvider den syntetiske Compose-testen med faktisk WebSocket
Upgrade, native PDF-rendering og backup/gjenoppretting av et innsendt syntetisk
bilag, hovedbok, offentlige/private vedlegg og en kryptert verdi. Etter gjenoppretting
kjøres migrering, HTTP og avvisning av gjest på privat vedlegg. Se
[driftsaksept](acceptance-runtime.md) for avgrensningene og
[kjerneoppsett og gap](core-minimum.md) for neste arbeidspakke.
Dette endrer ikke en kjørende server og kvalifiserer ikke den fremtidige norske appen.

## EHF som må videreføres

Peppyrus-testkonto og API-nøkkel er opprettet av eieren. Nøkkelen skal legges privat
på serveren, aldri i chat eller Git. Tidligere prøve ga konto HTTP 200 og deltaker
HTTP 500; dette er ikke bevist vellykket levering. Faktura og kreditnota skal gjennom
faktisk testnettverk. Ingen modulavgift var valgt; tjenesteleverandørens vilkår må
likevel undersøkes. Prosess/dokumenttyper skal følge aktuell Peppol BIS Billing.

## Første beskjed i den nye samtalen

Les AGENTS.md og denne filen. Kontroller staging/main, lokale endringer og tidligere
aksept før arbeid. Fullfør først driftsgrunnlaget og trygg portovergang. Deretter
prøv ERPNext-kjernen områdevis og implementer bare de dokumenterte norske gapene.
Ikke gjenoppta utvikling i Dolibarr Norway uten ny uttrykkelig instruks.

## Videreføring: norsk kontoplan og vanlig eier

Den lisensierte kilden, konverteringen og native import er nå versjonert i
`resources/norway-chart/`. [Kontoplanoppsettet](norwegian-chart.md) beskriver
standardkontoer og at norsk kjerneoppsett setter en MVA-mal som standard uten
registreringsstatus. Det valget må fjernes for et ikke-registrert foretak.

En vanlig eierbruker uten System Manager har bestått syntetisk salg, kjøp,
kreditnotaer, betalinger og bankavstemming med den importerte norske planen.
Native resultat er 475, bank 275 etter separat eiertransaksjon. Alle 745 koder/navn,
reskontro og avgiftsstandarder kontrolleres etter eksportert backup/restore og
migrering. Dette er ikke utført på brukerens server. Nummerering, dokumentvern,
språk, norsk avgiftsvalg og rapportering gjenstår som beskrevet i planen.

## Videreføring: minimal ekstern app

`apps/erpnext_norway/` inneholder minste tillegg for de påviste hullene i
[native kontroller](native-controls.md). [Appbeskrivelsen](norwegian-app.md)
angir oppsett, avgrensninger, bygging og native oppdatering. Ingen kjernefiler,
nummermotor eller filoppbevaring erstattes. Native egenskap protect_attached_files,
Document Naming Rule og standard kansellering/kreditnota brukes.

Appen bevarer nummererte fakturakladder og bokførte/kansellerte regnskapsbilag,
beskytter vedlegg mot de prøvde endringene og lar ny dokumentasjon legges til.
Nye native regler seedes bare på tomme registre uten eksisterende regler.
Brukte tellere og eksisterende valgmuligheter tilbakestilles ikke av migrering.
Ved native samtidighetskonflikt rulles transaksjonen tilbake; et nytt lagringsforsøk
må bevare sekvensen. Det tilføyes ingen egen produkt-retry eller utstedelsesteller.

Oppdateringen tar full backup før imagevalget endres og bruker install-app/migrate.
Feil etter migreringsstart åpner ikke gammel kode mot muligens endret database.
Appen og bevaringsvern inngår i separat Compose-prøve og eksportert restore.
Faktisk oppdatering av brukerens server er fortsatt ikke verifisert her.
Språk- og dokumentpunktet videreføres i app 0.2.0, se nedenfor. Neste produktpunkt
er korrekt foretaks-/MVA-oppsett og normal avgiftsflyt.

## Presisering: norsk mal ved selskapsoppretting

Brukeren har ingen data i selskapet og vil opprette det på nytt. Norsk kontoplan
skal være en ordinær standardmal, ikke en etterfølgende manuell slette-/importoppgave.
Appen leverer nå Norsk kontoplan via native malvalg/trevisning og create_charts,
med standardvalg for nye Norway/NOK-selskaper. Eksisterende selskaper, eksplisitte
malvalg og kopiering fra selskap overtas ikke automatisk. Se norwegian-chart.md.
Endringen prøves med ekte Company-oppretting, alle 745 navn/koder, standardkontoer,
native forhåndsvisning og uendrede eksplisitte valg før push/PR.

## Videreføring: bokmål og salgsdokumenter

App 0.2.0 leverer målrettede native CSV-rettelser og Jinja Print Formats for tilbud,
faktura og kreditnota på bokmål/engelsk. Den bruker eksisterende beregning,
formatteringsfunksjoner, avgiftsmaler, språkvalg og File. Vanlig on_submit lagrer en
privat PDF ved innsending/bokføring; det er ikke en utsendelseskvittering. PDF-feil
stopper innsending. Ingen etterlagring av historiske originaler ved migrering.
Innsendte/kansellerte tilbud og vedlegg får samme bevaringsprinsipp som bilag.
Egne maler og senere standardvalg bevares. Se [salgsdokumenter](sales-documents.md)
og [språkaksept](language.md) for faktisk omfang og avgrensninger.

Oppdateringsblokker skal heretter hente gjeldende origin/main med fetch, switch og
fast-forward, uten target/revisjonslås. Bygg deretter appimage og bruk den eksisterende
backup-/migreringsoppdateringen. Brukeren kjører blokken; ingen servertilgang er gitt.
Neste arbeidspakke er korrekt registreringsstatus/defaults og native MVA-behandling
ved vanlig registrering. Brukerens foretak er ikke MVA-registrert. SAF-T og øvrige
planpunkter gjenstår før samlet regnskapsmessig produksjonsaksept.


## Korrigert bestilling: bredt skjermspråk og native modulvisning

App 0.2.1 utvider norsk skjermspråk utenfor dokumentene til grunndata, innstillinger,
felt/valg/hjelpetekster i 173 dokumenttyper, felles Desk og regnskapsrapportfiltre.
VAT = MVA. Se language.md og runtime-ui-language.py; ikke påstå at hele ERPNext er
manuelt språkgodkjent basert på katalogtelling.

Brukeren vil nå beholde ALT standard moduloppsett. Tidligere instruks om å skjule
Produksjon/Prosjekter/Kvalitet er trukket tilbake. module-visibility.py tilbakefører
vår tidligere profil én gang, inkludert Lager, og oppdateringen kjører dette etter
migrering. Ingen ny profil tildeles. Senere egne valg og andre profiler beholdes.
Se module-defaults.md. Serveren oppdateres fortsatt bare av brukerens kommandoblokk.


## MVA-del 1: registrering nå og senere overgang

Brukeren er ikke registrert nå, men planlegger senere registrering. Ikke bygg et
oppsett som permanent fjerner MVA eller aktiverer den på grunn av planen alene.
App 0.3.0 legger registreringsstatus og bekreftet virkningsdato i native Company.
Eksisterende status gjettes ikke. Native Tax Rule fra-dato, avgiftsmaler og kategori
brukes til ordinær innenlandsk 25 %-behandling med 2700/2710 i norsk kontoplan.
Ingen egen avgiftsberegning, hovedbok eller historikktabell. Company har allerede
native Version-sporing. Sales Invoice sitt company_tax_id lagrer riktig MVA-merke.
Bokførte dokumenter etterbehandles ikke når foretaksinnstillingen endres.

Se vat-registration.md og runtime-vat.py/browserprøven for før-/etterdato,
framtidig godkjent dato, sperret tidlig fradrag, originaltro kreditnota og bevarte
PDF-er. MVA er ikke samlet ferdig med dette: linjefordelt fradrag, reduserte satser,
fritak/unntak, utland, portalgrunnlag, oppgjør/avstemming og kvittering gjenstår.
Tilbakegående avgiftsoppgjør vurderes særskilt; ikke endre gamle kjøp automatisk.

MVA-navngiving: native norske standardmaler navngis med Utgående/Inngående MVA
og ERPNext-standard. Vareavgiftsmaler/kategori er nøytrale. Appmalene heter
Utgående MVA 25 % og Inngående MVA 25 % – fullt fradrag. Migrering bruker native
rename_doc for lenker, uten sammenslåing av kollisjoner eller endring av bilagsbeløp.
