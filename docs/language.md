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

## Levert arbeidspakke

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
og kjøres bare mot den syntetiske localhost-instansen. Bredere språkfunn i senere
MVA-/års-/EHF-flyt skal behandles sammen med den aktuelle funksjonstesten.
