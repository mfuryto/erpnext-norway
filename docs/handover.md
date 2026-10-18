# Overgang til ERPNext Norway

Beslutning 2026-10-18: ERPNext blir prosjektets videre grunnlag. Dolibarr Norway
settes på vent; repo, historikk, installasjonsfiler beholdes. Ingen ny backup av Dolibarr eller tilbakeføringsfunksjon skal lages. Dolibarr er
oppgitt ikke tatt i ordinær bruk, så ingen produksjonshistorikk skal migreres som standard.

## Førende prinsipp

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
