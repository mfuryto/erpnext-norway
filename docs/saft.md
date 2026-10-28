# SAF-T: nedlasting, gjenbruk og gjenstående omfang

App 0.4.19 inneholder første SAF-T 1.40-nedlasting fra **Foretak → Last ned
SAF-T**. Den bruker den bokførte hovedboken og eksisterende bilags-/partregistre,
uten en egen hovedbok. Omfanget under er teknisk kvalifisert mot ERPNext 16.52.1 /
Frappe 16.53.0; hele SAF-T-punktet er fortsatt ikke ferdig.

## Format og årsversjon

[Skatteetatens dokumentasjon](https://www.skatteetaten.no/bedrift-og-organisasjon/starte-og-drive/rutiner-regnskap-og-kassasystem/saf-t-regnskap/dokumentasjon/)
sier at 1.40 kan brukes nå og blir eneste gyldige format fra 1. januar 2027.
1.20/1.30 kan fortsatt brukes for regnskapsår 2026 og tidligere. Ny eksport
kvalifiseres derfor mot 1.40; det er ikke tilstrekkelig å endre versjonsteksten.

Det offisielle [skjemaet og eksemplene](https://github.com/Skatteetaten/saf-t/tree/10c8fd82a6ff47e53385bc33c7638c5fde239a4f/SAF-T_Financial_1.4)
er undersøkt ved revisjon `10c8fd82a6ff47e53385bc33c7638c5fde239a4f`.
Kontogruppering må i tillegg følge offisiell liste for aktuelt inntektsår og
foretaksform. En norsk kontokode er ikke alene bevis på gyldig gruppering.
Gjeldende kilder inkluderer egne [gruppelister for 2025–2026](https://github.com/Skatteetaten/saf-t/tree/10c8fd82a6ff47e53385bc33c7638c5fde239a4f/Grouping%20Category%20Code%202025-2026).
2027-listene skal kontrolleres før støtte for det året erklæres ferdig.

## Prøvd kjerne før tilpasning

`tests/runtime-export-core.py` kjører på syntetisk norsk kontoplan med vanlig
eierbruker, både før og etter eksportert backup/gjenoppretting. Samme prøve
kjøres i grunnimaget og med den norske appen i Compose-testen.

| Krav | Faktisk kjerneprøve | Konsekvens for eksporten |
| --- | --- | --- |
| Kontoplan og transaksjoner | Native Data Export leverer CSV med 745 kontonumre og balanserte hovedbokslinjer og bilag. | Gjenbruk Account og GL Entry. Ingen import av en ny kontoplan for å eksportere. |
| Sporbarhet | Hovedboks-ID, bilagstype/-nummer, bokføringsdato, registreringstidspunkt og part er tilgjengelige. | Bevar kjernens referanser i XML. Bilagsdato, leverandørens nummer og øvrige opplysninger må hentes fra kildebilaget der de ikke følger GL. |
| Avstemming | Native General Ledger sitt radutvalg er identisk med aktive eksporterte GL-ID-er og debetsum. | Gjenbruk kjernens utvalg og kontroller mot kjernens rapporter. |
| Inngående saldo | Native kontoutvalg fra dagen etter de syntetiske posteringene gir bankens inngående saldo 275. | Periodens bevegelser og inngående saldo må skilles; et rent datofilter på eksporten er utilstrekkelig. |
| Reskontro | Kunde-/leverandør-ID-er finnes i lesbare masterregistre; netto reskontro er null etter faktura, kreditnota og betaling. | Kunder og leverandører må refereres konsistent. Åpne poster, fremmed valuta og flere reskontrokontoer gjenstår i SAF-T-fasiten. |
| Tilgang | Eieren kan eksportere konto/hovedbok og lese aktuelle parter, men får avvist Customer-eksport. Foretaksavgrensningen skjuler annen hovedbok. | Ikke gi globale eksportrettigheter eller bruke uavgrenset get_all som snarvei. En norsk nedlasting trenger egen eksplisitt adgangskontroll og avgrensning til tillatt foretak. |
| Kansellering | Native CSV beholder fire opprinnelige/motposter for et kansellert tolinjers bilag. Normal hovedbok utelater dem; eksplisitt kanselleringsfilter tar dem med. | Ikke anta at normalrapportens standardfilter er fullstendig eksporthistorikk. Behandling av motposter og perioder må kvalifiseres før SAF-T leveres. |
| Filformat | Native Data Export bygger CSV/Excel; ingen norsk AuditFile-eksport er funnet i den låste kjernen. | Det dokumenterte gapet er norsk XML-format, mapping og eksportkontroller, ikke bokføring eller saldoberegning. |

Kanselleringsprøven rulles tilbake og endrer ikke de eksisterende prøvebilagene.
Prøven er kildekvalifisering, ikke bevis på ferdig SAF-T eller regnskapsmessig aksept.

## Eksisterende norsk eksport undersøkt

ENK Norge har allerede en [SAF-T 1.40-bygger](https://github.com/Medpus/enk_norge/blob/94406e542ed991a8de237b9de44b8d1dd576b566/enk_norge/saft.py)
med MIT-lisens. Dens fem databasefrie byggetester er kjørt i det låste
ERPNext-imaget, mot det offisielle XSD-et ved revisjonen ovenfor: alle bestod.
Det omfatter XML med saldo/referanser, avgiftsmapping og avvisning av ubalansert
bilag, manglende mapping og duplikat konto-ID. Dette er en faktisk prøve av
mulig gjenbruk; det skal ikke skrives en konkurrerende XML-bygger før denne
kandidaten er ferdig vurdert.

Byggeren er også prøvd direkte mot den eksisterende, bokførte ikke-registrerte
Compose-fasiten: 16 native hovedbokslinjer, åtte bilag, kunde/leverandør og
bankens sluttverdi 275. Sju uttrykkelig angitte prøveklassifiseringer er
kontrollert mot den offisielle næringsspesifikasjonslisten for 2025–2026, og
XML-filen bestod XSD 1.40. Dette var en lokal, lesende prototype med syntetiske
foretaksopplysninger, ikke en installert eksport eller ferdig mapping av alle
745 kontoer. Den prøver ikke den norske appens avgiftsuttrekk.

Hele appen installeres ikke av den grunn. Frappe-adapteren leser egne
`enk_norge`-innstillinger og egne avgiftsbehandlinger og filtrerer på
`is_cancelled=0`. Den er ikke dermed kvalifisert for denne appens varelinjekoder,
import, kvartalsbilag, valuta og oppgjør. Fem byggetester viser heller ikke
korrekt årsgruppering eller full transaksjonsdekning. I app 0.4.19 er bare den databasefrie byggetjenesten gjenbrukt og tilpasset,
med MIT-lisens, opphavsrett og låst proveniens i `saft_data/NOTICE.md`.
ENK Norge er ikke installert og er ikke en appavhengighet.

## Oppsett og bruk

1. Bruk eksisterende foretaksfelt for organisasjonsnummer, telefon og adresse.
2. På hver brukt **Konto**, fyll **Norsk SAF-T-kontokobling** med år 2026,
   grupperingskategori og grupperingskode fra den offisielle listen. Brukte
   kontoer og kontoer med inngående saldo må ha én gyldig kobling for året.
   Dette er engangs konfigurasjon av kontoplanen, ikke etterbehandling av bilag.
   Ingen kontogruppering gjettes fra et firesifret nummer alene.
3. Åpne foretaket som regnskapsansvarlig (**Accounts Manager**), velg
   **Last ned SAF-T** og angi datoer innenfor 2026. Feil ved kontokobling
   lenker direkte til det aktuelle kontokortet.
4. Filen XSD-valideres før nedlasting. Native Access Log registrerer eksporten.
   Eksporten endrer ikke bilag, betaling, nummerserier eller hovedbok. Den
   oppretter ikke et eget eksportarkiv eller en ny hovedbok.

Andre foretaks data og gjestetilgang avvises. Regnskapsansvarlig må ha lesetilgang
til alle valgte hovedboksposter, kildebilag og masterregistre. Eksporten bruker
ikke en tildeling av globale Customer-eksportrettigheter som snarvei.

## Prøvd funksjonsomfang i 0.4.19

- Konto-/partreferanser og alle valgte native GL-ID-er; hovedbok, reskontrosaldo,
  åpning og slutt hentes fra samme bokførte kilde. Originaler og motposter ved
  kansellering er med. Native åpningsposter er saldo, ikke periodebevegelse.
- Faktiske fra-/til-datoer, også midt i en måned, i SelectionCriteria.
- Innenlandsk salg/kostnadskjøp med 25/15/12 prosent, fullt, 60 prosent og
  intet fradrag, kreditnota og kansellering. Avgiftskode, grunnlag og faktisk
  MVA-beløp leses fra eksisterende varelinjer og Item Wise Tax Detail. Ingen
  ny avgiftsberegning. Opplysningene legges på grunnlagslinjen og avstemmes
  mot native MVA-posteringer; kode 0 får null grunnlag og null MVA.
- Norsk/utenlandsk adresse, native kostnadssteder og NOK/EUR-beløp uten
  beregnet MVA. Ingen ny valutaberegning. Postenes native prosjektfelt kan
  også gjengis som dimensjon når brukeren har tilgang til masterregisteret.
- Norsk knapp og datodialog, autentisert XML-vedlegg og avvisning av gjest.
  Kilde-ID-er, kontokoblinger og en privat syntetisk XML-fil prøves etter
  eksportert backup/gjenoppretting i Compose.

Ti databasefrie byggetester, herunder de fem opprinnelige MIT-testvektorene,
prøver også nullbeløp, flere BaseRate-verdier, åpning og valutapresisjon.
Den norske adapteren kontrollerer fullstendig radtilgang, årsliste,
kontokobling, bilagsbalanse og avgiftsopplysninger før en fil leveres.

## Gjenstår i hovedplanens SAF-T-punkt

Utvid eksportmappingen til import, omvendt avgiftsplikt, kvartalsbilag,
andre klassifiserte MVA-bilag, avgiftsført valuta, lager/driftsmidler og frakt.
Disse velprøvde bokføringsfunksjonene i MVA-modulen endres ikke av eksporten.
De trenger egne SAF-T-fasiter og eksportprøver før de kan tas med i denne filen.
Alternative regnskaps-/avskrivningsbøker og øvrige brukte dimensjoner må også
kvalifiseres, sammen med flere åpne reskontrokontoer og periodestenging.
Eksport for 2027 krever kvalifisering av riktig årsliste; 2026-listen brukes
ikke automatisk videre. Deretter følger samlet regnskapsaksept av filene.

Historiske poster før fra-dato beholdes i inngående saldo; periodens
avgiftsklassifisering brukes på periodens bevegelser. En ukvalifisert
post **innenfor den valgte perioden** avvises med bilagsreferanse. Den
utelates aldri stille for at eksporten skal se komplett ut.

Deretter følger [ENK og årsavslutning](handover.md#hovedplan-avtalt-søndag-18-oktober-kl-1844)
og [EHF med faktisk levering og kvitteringer](ehf.md).

## Implementasjonsgap før første nedlasting

Den prøvde MIT-byggeren gjenbrukes selektivt, uten ENK Norges innstillinger
eller Frappe-adapter. Nødvendige endringer er nullbeløp, flere fradragsandeler
i TaxTable, native åpningsbilag, valutabeløp og entydige transaksjonsreferanser.
Norsk adapter skal legge avgiftsopplysninger på grunnlagslinjen og kontrollere
kontokoblinger mot offisiell årsliste. Se Skatteetatens generelle dokumentasjon
1.8, side 31–34. Native bokføring og avgiftsberegning endres ikke.

Første kvalifisering av nedlastingen avgrenses til 2026, NOK-hovedbok, ordinært
salg og kostnadskjøp med innenlandske satser/fullt/delvis/intet fradrag, samt
nullavgift og valutaposter uten beregnet MVA. Spesialbehandling, avgiftsført
valuta, lager-/driftsmiddelgrunnlag, frakt og alternative avskrivningsbøker
skal avvises konkret inntil eksportmappingen er kvalifisert. Disse postene
skal aldri forsvinne stille fra filen. Hele hovedplanens SAF-T-punkt er dermed
fortsatt åpent etter en slik første funksjonsleveranse.

Kjernen bruker kostnadssted og eventuelt prosjekt på hovedbokslinjer. Den
gjenbrukte byggeren manglet dette feltet; Analysis/AnalysisTypeTable skal derfor
få de faktiske native dimensjonene og beløpene. Andre brukte dimensjoner
avvises inntil de er kvalifisert, fremfor å fjernes fra eksporten.
