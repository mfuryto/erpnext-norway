# Norsk språk og regnskapsbegreper

Bestilt omfang: oversett engelske elementer og rett misvisende norske begreper i
den støttede arbeidsflyten. Bokmål er første norske språk. Dette er et leveransekrav;
målrettede rettelser leveres nå i den eksterne appens `nb.csv`. Dette er ikke
en påstand om at hele ERPNext-katalogen er fullstendig oversatt.

## Omfang og gjennomføring

- Gjennomgå oppstartsoppsett, foretaksinnstillinger, kontoplan, salg, kjøp, betaling,
  bankavstemming, hovedbok og rapporter. Ta med menyer, felt, hjelpetekster,
  handlinger, statuser, valideringsfeil og vanlige varsler i den aktuelle flyten.
- Gjennomgå tilbud, faktura og kreditnota i forhåndsvisning og PDF. Norsk dokument
  skal ha norske tekster; engelsk dokument skal fortsatt fungere uavhengig av
  brukerens skjermspråk.
- Bruk eksisterende korrekte oversettelser først. Legg nødvendige tillegg og rettelser
  i den eksterne norske appens oversettelsesressurser og dokumentmaler. Ikke endre
  ERPNext/Frappe-kjernen, interne feltnavn, API-kontrakter eller lagrede statusverdier.
- Samme engelske tekst kan ha ulik betydning i ulike skjermbilder. Undersøk bruk
  og tilgjengelig oversettelseskontekst før en global oversettelse velges. Ikke bruk
  et globalt tekstbytte for å løse et lokalt fagbegrep.
- Kontonavn og konfigurerte malnavn er også brukerrettede data. Oversettelsesfiler
  alene sikrer ikke at disse blir norske. Ikke gi eksisterende kontoer eller bilag
  nye identifikatorer som del av språkarbeidet.

## Foretrukne begreper

Dette er en arbeidsordliste. Kontroller hele setningen og handlingens virkning før
implementasjon, særlig for bokføring, kansellering og retting.

| Kildetekst / betydning | Norsk i aktuell kontekst |
| --- | --- |
| Sales Invoice | Salgsfaktura |
| Purchase Invoice | Leverandørfaktura |
| Credit Note | Kreditnota |
| Quotation | Tilbud |
| Posting Date | Bokføringsdato |
| Due Date | Forfallsdato |
| Chart of Accounts | Kontoplan |
| General Ledger | Hovedbok |
| Journal Entry | Bokføringsbilag |
| Payment Entry | Betalingsregistrering |
| Bank Reconciliation | Bankavstemming |
| Accounts Receivable | Kundefordringer / kundereskontro, avhengig av visning |
| Accounts Payable | Leverandørgjeld / leverandørreskontro, avhengig av visning |
| Outstanding Amount | Utestående beløp |
| Draft | Kladd |
| Submit på et regnskapsbilag | Bokfør, når handlingen faktisk bokfører |
| Submit på andre dokumenter | Velges etter dokumentets virkning; ikke automatisk «Bokfør» |
| Cancel | Kanseller; forklar eventuell reversering i regnskapsflyten |
| Amend | Opprett korrigert versjon, når det er handlingens faktiske virkning |
| Check / validation | Kontroll / validering; ikke betalingsformen «sjekk» |
| Bank / Banking | Bank; ikke «balanse» |
| Balance Sheet | Balanse |
| Tax | Avgift eller skatt etter sammenhengen; bare merverdiavgift der det faktisk gjelder |
| Input / Output VAT | Inngående / utgående merverdiavgift |

## Aksept

1. Kjør normal salgs-, kjøps- og bankflyt med vanlig eierbruker og bokmål valgt.
   Registrer kilde, skjermsted, eksisterende tekst, rettelse og resultat for hvert funn.
2. Prøv også feiltilfeller: påkrevde felt, ugyldig dato, manglende rettighet og forsøk
   på endring av bokført dokument. Kontroller at betydningen ikke endres i oversettelsen.
3. Kontroller tilbud, faktura og kreditnota på bokmål og engelsk, inkludert PDF.
   Dokumentenes språkvalg må ikke gi blandede standardtekster.
4. Gjenta etter omstart og appoppdatering. Kontroller at appens rettelser faktisk
   brukes når kjernen allerede har en annen oversettelse.
5. Tekniske identifikatorer, egennavn og eksterne feilsvar vurderes særskilt; ikke
   endre dem blindt for å få en telling av engelske ord til null.

Ingen påstand om full norsk dekning baseres bare på antall oversatte strenger.
Faktiske skjermbilder, feilflyt og dokumenter er akseptgrunnlaget.

## Første arbeidspakke (0.2.0)

App 0.2.0 retter de sentrale regnskapsbegrepene og feltene i salgs-, kjøps-,
betalings- og bankflyten, med egne kontekstnøkler for de aktuelle DocType-feltene.
Kjernens oversettelser beholdes der de er riktige. Intern status, API-felter og
brukerens egennavn/fritekst endres ikke. Generell Submit blir «Send inn», ikke
en global «Bokfør» på tilbud og andre dokumenter. Enhetspris har egen priskontekst;
Rate for renter/valuta byttes ikke globalt.

[Norske/engelske salgsdokumenter](sales-documents.md) beskriver maler, språkvalg,
PDF ved innsending og bevaring. Det uendrede native Company Letterhead skriver
dokumenttypen som uoversatt data; bare en eksakt kopi av den leverte malen får
en oversettbar tittel. Brukertilpassede brevark overtas ikke.

Akseptsporet er `tests/runtime-language.py` og `tests/runtime-language-browser.cjs`,
sammen med eksisterende vanlig-eier-prøver. Browserprøven krever Playwright 1.58.2
og kjøres bare mot den syntetiske localhost-instansen. Denne første pakken var
for smal til å oppfylle bestillingen om norsk skjermspråk; utvidelsen nedenfor
lukker kartlagte hull også utenfor dokumentflyten.


## Utvidet skjermspråk (0.2.1)

Kartlegging av det låste ERPNext-imaget fant manglende feltnavn, hjelpetekster og
valg også i foretak, kunder, leverandører, artikler, priser, lager, konti, bank,
eiendeler, abonnementer, brukeroppsett og systeminnstillinger. Appens native CSV
supplerer disse tekstene, inkludert tilhørende undertabeller. Kontrollen omfatter
173 dokumenttyper; den bruker kjernens eksisterende korrekte oversettelser først.

Felles Desk-tekster for navigasjon, søk, lister, filter, oppretting, påkrevde felt,
vedlegg, varsler, utskrift, tilgang, arbeidsområder og innstillinger er også utvidet.
Regnskapsrapportenes manglende filtertekster og standardmenyenes manglende titler
er oversatt, også for de gjenåpnede modulene. Warehouse rettes fra «Varehus» til
«Lager», Serial & Batch til «Serienumre og partier». Native oversettbare landnavn
viser blant annet Norge uten å endre den lagrede nøkkelen Norway. VAT vises som **MVA**,
Value Added Tax som **merverdiavgift**. Generell Tax oversettes etter sammenhengen,
uten å kalle alle skatter og avgifter for MVA. Enhetspris og avgiftssats bruker
kontekst; verken Rate, Tax eller interne statusverdier byttes globalt.

`tests/runtime-ui-language.py` kontrollerer den installerte native katalogen mot
feltnavn, hjelpetekster og valg i de 173 dokumenttypene. Tekniske nummermønstre,
strekkodestandarder og PDF-motornavn har en uttrykkelig liste med unntak.
Browserprøven åpner dessuten kunde-, leverandør- og artikkelskjemaer, foretaksoppsett,
system-, regnskaps- og lagerinnstillinger. Den kontrollerer faktiske etiketter,
valgtekst, hjelpetekst og feildialog for manglende kundenavn, i tillegg til tidligere
salgs-/kjøps-/betalingsprøver og norske/engelske dokumenter.

Dekningskontrollen er en regresjonskontroll for dette omfanget, ikke bevis for at
hver eneste skjerm i alle ERPNext-moduler er gjennomgått manuelt. Brukerlagde navn,
fritekst, tredjepartsinnhold og tekniske identifikatorer maskinoversettes ikke.
Videre funksjonsaksept skal også kontrollere faktisk skjermspråk.
