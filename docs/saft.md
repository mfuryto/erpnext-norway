# SAF-T: nedlasting, gjenbruk og gjenstående omfang

App 0.4.24 viderefører første SAF-T 1.40-nedlasting fra **Foretak → Last ned
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
   Kontonummer brukes som ID når det finnes; ellers beholdes kjernens
   entydige kontonøkkel. Ekstra valutakontoer trenger ikke et påfunnet nummer.
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

Første utgave støtter faktura/kreditnota, betalingsbilag og ordinære bilag
uten MVA. Periodens andre bilagstyper avvises frem til eksportmappingen
er kvalifisert, også når hovedboksposteringen ikke har et MVA-beløp.

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

Utvid eksportmappingen til import, kvartalsbilag,
andre klassifiserte MVA-bilag, øvrig avgiftsført valuta, lager/driftsmidler og frakt.
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

## Omvendt avgiftsplikt på tjenester i 0.4.20

Kjernen og appens eksisterende vareavgiftsmaler fører allerede utgående og
inngående MVA ved tjenestekjøp fra utlandet. Første SAF-T-adapter avviste
kode 86/87/88/89; ingen ny beregning eller bokføring trengs. Adapteren leser
de samme native Item Wise Tax Detail-radene, kontrollerer begge MVA-kontoer
og plasserer netto avgiftsbeløp på kostnadsgrunnlaget. Ved fullt fradrag er
netto null, slik [Skatteetatens eksempel på side 34](https://www.skatteetaten.no/globalassets/bedrift-og-organisasjon/starte-og-drive/rutiner-regnskap-og-kassasystem/saf-t-regnskap/august2026/norwegian-saf-t-financial-data---documentation-1.40.pdf)
viser. Ved delvis/intet fradrag kan avgiftsbeløpets kredit-/debetretning
avvike fra kostnadslinjens retning. Den gjenbrukte byggeren manglet dette
valget og har fått et valgfritt avgiftsretningsfelt. Dette er et XML-mappinggap;
kjernens beløp og avgiftsbehandling beholdes.
Native prøver dekker NOK-tjenestekjøp med 25/12 prosent, 100/60/0 % fradrag,
delkreditnota og kansellering. Begge MVA-kontoer kontrolleres hver for seg,
og feil i et avgiftsgrunnlag avvises selv om netto MVA er null. Prøvene
omfatter samme kontokoblinger, GL-ID-er og privat XML-bevis etter eksportert
gjenoppretting. Avgiftsført valuta, kvartalsbilag og kapitaliserte tjenester beholdes sperret i denne leveransen.

## Avgiftsført valuta i 0.4.22

Første adapter avviser avgiftsført valuta, men den låste kjernens
`taxes_and_totals.set_item_wise_tax` lagrer allerede `amount` og
`taxable_amount` i foretakets hovedvaluta, med kjernens kumulative avrunding.
En ny valutaberegning er derfor unødvendig. Registrerte utenlandske tjenester
eksporteres med disse NOK-verdiene, mens hovedbokens native valutabeløp
beholdes separat. Ved forskjellig bokførings- og MVA-kurs brukes lagret
`taxable_amount` på utgående side én gang, ikke fakturabeløp ganger en ny kurs.
Dette følger [TaxInformationStructure, side 57–60](https://www.skatteetaten.no/globalassets/bedrift-og-organisasjon/starte-og-drive/rutiner-regnskap-og-kassasystem/saf-t-regnskap/august2026/norwegian-saf-t-financial-data---technical-description-1.4.pdf).
TaxAmount er netto av faktisk inngående/utgående MVA, avstemt hver for seg
mot hovedboken, også ved fradrag og avrunding. TaxAmount vises i NOK, som
er eksportens hovedvaluta; ekstra NOKTaxAmount brukes bare når TaxAmount
er uttrykt i en annen hovedvaluta. Kvartalsbilag, frakt og kapitalisering
er separate, fortsatt ukvalifiserte eksportgap.

Prøvene bruker faktisk bokførte EUR-tjenestekjøp med 25/12 prosent og
100/60/0 prosent fradrag, ulike bokførings-/leveringskurser, delkreditnota,
kansellering, to linjekurser med rabatt og native betaling/valutabilag.
Regnskapskostnad 1 110,14 beholdes ved siden av faktisk avgiftsgrunnlag
1 101,37; eksporten avleder ikke grunnlaget fra kostnaden. Frakt, øvrig
MVA-valuta og kapitalisering er fortsatt sperret inntil mappingen er prøvd.

Samlet SAF-T-sluttføring må også kvalifisere fullstendige konto- og
avgiftsregistre, inklusive ubrukte/historiske konti og koder. Teknisk
beskrivelse side 9 krever dette ved utlevering til Skatteetaten; første
begrensede utgave med brukte konti er ikke tilstrekkelig for samlet aksept.

## Direkteført inngående import-MVA, 0.4.23

Kjernen har allerede ordinære Journal Entry og appen lagrer kode 14/15 på
inngående import-MVA. Eksportadapteren avviste likevel alle slike bilag.
[Skatteetatens generelle dokumentasjon, side 31](https://www.skatteetaten.no/globalassets/bedrift-og-organisasjon/starte-og-drive/rutiner-regnskap-og-kassasystem/saf-t-regnskap/august2026/norwegian-saf-t-financial-data---documentation-1.40.pdf)
gjør uttrykkelig unntak for disse to kodene: avgiftsopplysningene skal på
MVA-posteringen. Dette konkrete mappinggapet lukkes ved å lese bokført beløp
og retning fra GL, kontrollert mot bilagslinjen og kode/sats/konto. Det lages
ikke et beregnet grunnlag. Kode 14 bruker 2715/25 prosent, kode 15 bruker
2716/15 prosent. Valutabilag, andre koder og tvetydige linjer holdes sperret.
Dette endrer ikke når direkteføring er regnskapsmessig riktig å bruke.

Prøven dekker ordinær bruker, begge koder, native reversering, kansellering,
inngående saldo, XSD, eksakte GL-ID-er og summer samt privat XML etter
backup/gjenoppretting. Feil sats, feil kode, uavklart grunnlag og avvik mellom
bilagslinje og GL avvises med bilagsreferanse. Ingen bokførings-/skjemaendring.

## Påvist restgap: bokført importgrunnlag

[Skatteetatens importveiledning](https://www.skatteetaten.no/bedrift-og-organisasjon/avgifter/mva/utland/import/beregne/)
krever at også grunnlaget bokføres; balanserende grunnlagsføringer er beskrevet.
De tidligere importprøvene bokfører MVA, men lagrer selve deklarasjonsgrunnlaget
som metadata på MVA-linjen. Det kvalifiserer ikke alene grunnlagsføringen eller
SAF-T-eksemplet på side 34. Dette er et gjenåpnet kvalifiseringsgap i importflyten,
ikke grunnlag for å lage kunstige GL-poster bare i eksportfilen. Historiske
bilag endres ikke ved oppdatering. Neste importarbeid skal prøve ordinære
Journal Entry med faktiske grunnlagsføringer og native dimensjoner, og avklare
normalføringen før eksportmappingen åpnes for 81–84. Kvartalsbilagenes
avgiftsgrunnlag og avrundingskorreksjoner må kvalifiseres separat.


## Samlet debet og kredit fra kjernen, 0.4.24

Ordinær Journal Entry med kjernens innstilling for sammenslåing av like kontolinjer
kan lagre både debet og kredit på samme GL Entry. Faktisk prøve med samme konto
viste separate 4 700-posteringer når innstillingen er av, og én rad med både
4 700 debet og 4 700 kredit når den er på. Den gjenbrukte byggeren avviste slike
rader. Det er et formatgap i eksporten; regnskapet og brukerens innstilling skal
beholdes.

[Skatteetatens tekniske beskrivelse, side 32–33](https://www.skatteetaten.no/globalassets/bedrift-og-organisasjon/starte-og-drive/rutiner-regnskap-og-kassasystem/saf-t-regnskap/august2026/norwegian-saf-t-financial-data---technical-description-1.4.pdf)
definerer RecordID som spor til bilagslinje/posteringsreferanse og krever valg
mellom debet og kredit per XML-linje. Byggeren gjengir derfor hver bokført side
på egen XML-linje med samme native GL-ID. Den avregner ikke til netto og lager
ikke nye posteringer eller ID-er. Dimensjonsbeløpet følger hver sides faktisk
bokførte beløp; totalsummer og saldo bruker de opprinnelige kildedataene.

Første kvalifisering av dette formatgapet gjelder NOK-rader uten tilknyttede
avgiftsopplysninger. Samlet valuta og fordeling av TaxInformation avvises fortsatt.
Negative eller tomme kildelinjer godtas ikke. Dette åpner ikke importkodene
81–84 eller kvartalsbilag: deres grunnlags-/avgiftsmapping må kvalifiseres separat.
Native sammenslåing, reversering, kansellering, kostnadssted, bruttosummer,
saldo og referanser prøves igjen etter eksportert gjenoppretting. Brukerens
Accounts Settings endres ikke av eksport eller oppdatering.
