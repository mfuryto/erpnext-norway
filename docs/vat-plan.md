# Samlet MVA-plan – hovedplanens punkt 5

Bestilling 19. oktober 2026: fullfør hele MVA-planen, deretter hovedplanens punkt 6
(SAF-T) og 7 (ENK/årsavslutning). Ingen ny avgiftsmotor eller parallell hovedbok.
ERPNexts maler, vareavgifter, regler, beregning, kreditnotaer og bokføring brukes.
Krav → prøvd kjerne → faktisk gap → minste tilpasning → forventet regnskapsresultat.

| Rekkefølge | Leveranse | Status |
| --- | --- | --- |
| 1 | Ikke registrert/registrert, virkningsdato, MVA-merking og historiske bilag | Prøvd i app 0.3.0 |
| 2 | Norske navn, inngående/utgående MVA og forståelige beskrivelser | Prøvd i app 0.3.1 |
| 3 | 25/15/12 %, kontoer, gyldighet og norske behandlings-/rapporteringskoder | Ordinært blandet 25/15/12 %-salg og koder prøvd |
| 4 | Separate valg for fritatt/nullsats, unntatt og uten MVA-behandling | Separate varelinjevalg prøvd; vilkårene avgjør faktisk bruk |
| 5 | Fullt, delvis og intet fradrag; kostnad/eiendel får ikke-fradragsført MVA | Kostnad, lager og driftsmiddel prøvd; se avgrenset mottaks-/returflyt i vat-valuation.md |
| 6 | Blandet behandling/sats per linje, varestandard og overstyring | Native fakturalinjer, kjøpsskjerm og innkjøpsordre/mottak prøvd; blandet tjenestesalg gjennom tilbud/ordre/dellevering/faktura/kreditnota prøvd i 0.4.10 |
| 7 | Tilbud/ordre/faktura/kjøp/kreditnota, rabatt/frakt, pris inkl./ekskl. MVA, avrunding | Blandede satser, rabatt, lager-/tjenestefrakt med mottak/retur, delfakturering og inklusiv kjøpspris prøvd; tilbud/ordre/dellevering/delfaktura med salgsrabatt, inklusivt tilbud og frakthenvisning prøvd i 0.4.10; driftsmiddelfrakt og retur prøvd i 0.4.17; øvrige kombinasjoner avgrenses nedenfor |
| 8 | Utenlandske tjenester, omvendt avgiftsplikt, valuta og fradrag, også før registrering | Registrert 25 % NOK med fradrag, ordre, kreditnota og rapport prøvd i 0.4.8; registrert valutalinjeflyt med leveringskurs, fradrag, kreditnota og native betaling i 0.4.12; 25 % kvartalsgrense og registreringsovergang prøvd i 0.4.14; 12 % og blandet kvartal, valutatillegg/rabatt og native oppgjør er kvalifisert i 0.4.16; resterende verdsettingskombinasjoner er åpne |
| 9 | Vareimport, deklarasjonsgrunnlag/avstemming, eksport og utenlandssalg | Native mottak/deklarasjonsbilag, periode, kode 85, toll/LCV, valutabetaling og eksportkjede med EUR-kreditnota/refusjon prøvd i 0.4.15; særskilte importprosedyrer er ikke kvalifisert |
| 10 | Registreringsovergang, tidligere kjøp og kontrollerte rettelser/kreditnota | Grunnleggende overgang/kreditnota prøvd |
| 11 | Spesifikasjon per kode/periode, bilagsspor, hovedboksavstemming og portalgrunnlag | Native faktura-/journalrapport, leverandørens dokumentperiode og deklarasjonens ekspedisjonsperiode prøvd; utenlandske tjenester og kode 85 inngår i samme spor og hovedboksavstemming |
| 12 | Oppgjørsføring, betaling/refusjon, korrigert melding, vedlagt melding/kvittering | Native oppgjør/betaling/refusjon/differanse og privat dokumentbevaring prøvd; portal først |

Navn alene betyr ikke kvalifisert behandling. En eksisterende 12 %-standardmal
beviser ikke korrekt norsk konto-/fradrags-/rapporteringsflyt. Års- og særregler
må avgrenses uttrykkelig; foretaket er ikke registrert nå, men planlegger registrering.

Hver behandling skal prøves gjennom vanlig bilagsregistrering og kreditnota til
hovedbok og rapportgrunnlag, med vanlig eierbruker. Oppgraderinger skal bevare
valg, bokførte verdier og PDF-originaler. Skjemaendringer krever backup/restore-prøve.

Kilder: [satser](https://www.skatteetaten.no/satser/merverdiavgift?pageid=1500),
[fritak/unntak](https://www.skatteetaten.no/bedrift-og-organisasjon/avgifter/mva/slik-fungerer-mva/forskjellen-pa-fritak-og-unntak-fra-merverdiavgift/),
[MVA-meldingens informasjonsmodell](https://skatteetaten.github.io/mva-meldingen/mvameldingen/informasjonsmodell/).
Eksisterende leveranse og prøver er beskrevet i [MVA-registrering](vat-registration.md).

## Kjerneprøve for satser og linjevalg

Kjernen har Item Tax Template og native avgiftsrader per konto. Prosentvalg per
varelinje er derfor konfigurasjon, ikke grunnlag for en ny beregningsmotor.
Norske kontoer er 2700/2710 (25 %), 2701/2711 (15 %) og 2703/2713 (12 %).
Standard MVA-koder er 3/1, 31/11 og 33/13 for henholdsvis salg/kjøp med fradrag.
En blandet faktura skal prøve 1 000 i grunnlag per sats: 250 + 150 + 120 = 520.
Kjernens avgiftsrader, hovedbok og kreditnota er fasit for faktisk oppførsel.

Påvist gap: den native malen har ikke norske rapporteringskoder. Minste tillegg er
kodefelt på native Item Tax Template og en kode på fakturalinjen som bevarer valget
ved bokføring. Rapportering skal lese disse native bilagene og hovedboken.
Etterfølgende endring av en mal må ikke omklassifisere et allerede bokført bilag.

## Kvalifisert delomfang i app 0.4.0

Isolerte native prøver har bestått for blandet 25/15/12 %-salg (520 MVA),
60/0 %-fradrag i ett kjøp (150 inngående MVA, 2350 kostnad, 2500 leverandørgjeld),
vanlig eier uten System Manager og faktisk standard kjøpsskjerm med fradragsvalg.
Første rapportprøve leser native Item Wise Tax Detail og avstemmer bilagene mot
GL Entry: 520 utgående minus 150 inngående gir 370. Samlet MVA er fortsatt ikke ferdig: utland/import, normal vare-/driftsmiddelkjede
og øvrige åpne kombinasjoner i tabellen gjenstår. Rapport-/oppgjørsprøvene
under kvalifiserer bare de uttrykkelig prøvde tilfellene.

Videre isolert prøve har bestått for faktisk native rapport, separat vurdert
tilbakegående fradragsbilag, oppgjør 270, betaling og bankavstemming, senere
refusjon 100 samt bevaring av privat rapportgrunnlag og kvittering. Dette er
syntetisk lokal kvalifisering, ikke innlevering eller kontroll av brukerens server.
Prøven ligger i tests/runtime-vat-portal-cycle.py og inngår i appens driftsprøve.
Delvis fradrag mot 4300 er også prøvd uten å endre Cost of Goods Sold-kontotypen.
Native blandet kreditnota og 10 % rabatt er prøvd: 520 reverseres til -520,
og rabatt gir 2700 netto + 468 MVA = 3168. Kjøpskreditnota reverserer både
150 inngående MVA og 2350 kostnad ved opprinnelig 60/0 %-fradrag.
Separate native tillegg er prøvd: vare 1000 + frakt 100 gir 1100 i grunnlag
og 275 MVA med On Previous Row/On Net Total, mens nullsats beholder 1100 i
grunnlag uten MVA. Et Actual-tillegg på samme kostnadskonto beholdes som en
egen rad ved delvis fradrag. En eksisterende prosentvis kostnadsrad må bruke
en annen konto enn MVA-kostnadsfordelingen: kjernens vareavgiftskart er per
konto og kan ikke skille to ulike prosentsatser på samme konto.
Ved delvis/intet fradrag følger MVA-kostnadsfordelingen også kjernens fraktgrunnlag:
1000 varer + 100 frakt gir 275 MVA, hvorav 165 inngående og 110 i kostnad ved
60 % fradrag. Samlet kostnad blir 1210 og leverandørgjeld 1375. Både On Previous
Row Amount og On Previous Row Total er prøvd; Total får ikke en ekstra grunnlagsrad.
Pris 1250 inkludert MVA er prøvd med 1000 netto, 150 fradrag og 100 MVA-kostnad.
Kjernefunn i den låste versjonen: Item Wise Tax Detail kan ha taxable_amount=0
for en vanlig On Net Total-rad uten vareavgiftsmal, selv om MVA-beløpet er riktig.
Rapporten må da lese varens eksisterende base_net_amount som grunnlag; den skal
ikke rapportere nullgrunnlag eller beregne fakturaens avgift på nytt.
Gjentatt bevaring av identisk grunnlag må gjenbruke det eksisterende native
File-vedlegget: kjernens blob-deduplisering møter ellers med rette skrivevernet
på den allerede beskyttede URL-en. Endret grunnlag skal opprette et nytt vedlegg
uten å endre de tidligere bytes; filvernet skal ikke svekkes for å få dette til.

Periodegap: kjernens posting_date alene dekker ikke leverandørens dokumentdato.
Rapporten viser derfor både bokføringsdato og MVA-dato og bruker native bill_date
for kjøpsfakturaer. Oppgjørsforslaget bygger på rapportens avstemte native
avgiftsdetaljer, fratrukket allerede bokførte oppgjør for samme periode. Det
skriver ikke om fakturaens bokføringsdato. Deklarasjonsdato og øvrige unntak
krever egne kvalifiserte importtilfeller før den behandlingen tilbys.
Kilde: [Skatteetatens tidfestingsregel](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-15/M-15-9/M-15-9.3/).

Opprinnelig kjerneprøve før app 0.4.2: native
Valuation and Total med 15 % fradragsført og 10 % kapitalisert ved 25 % MVA
ga 1250 leverandørgjeld, 150 inngående MVA og 1100 lagerverdi i både GL Entry
og Stock Ledger Entry. Et tilsvarende direkte driftsmiddelkjøp ga 1100 på
1250 og native Asset.net_purchase_amount/purchase_amount = 1100. Dette skal
brukes ved videreføring; ingen egen verdsettings- eller avskrivningsmotor.

Undersøkt kjernealternativ for utenlandstjenester før MVA-registrering:
Tax Withholding Category/Details er parts-/skattetrekkbasert og dekker ikke
foretakets samlede kvartalsgrunnlag på tvers av leverandører. Det skal ikke
omdøpes eller gjenbrukes som om det var norsk omvendt MVA. Vanlig registrert
omvendt avgift kan bruke native avgiftsrader, men ikke-registrert kvartalsterskel
og korrekt særskilt melding er fortsatt et dokumentert gap.

## Malendring etter fakturering: retting i app 0.4.1

Native get_item_tax_map leser dagens Item Tax Template også på en kreditnota.
Isolert prøve: faktura med 250 MVA, senere malendring fra 25 til 12, deretter
native full kreditnota ga bare -120 MVA. Kjernens varelinjehenvisning og lagrede
item_tax_rate gir allerede opprinnelig behandling; ingen ny historikk trengs.
Minste tilpasning er å konfigurere en native vareavgiftsmal med de opprinnelige
ratene bare når dagens mal avviker, og la kjernen beregne kreditnotaen som før.
Uendrede satser skal ikke opprette ekstra maler, og brukerens endrede mal beholdes.

Isolerte prøver med vanlig eier består: to delkreditnotaer gir -125 hver etter
malendring fra 25 til 12 %, og gjenbruker én native mal med opprinnelige satser.
En kjøpskreditnota beholder 150 i inngående MVA og 100 i MVA-kostnad ved
opprinnelig 60 % fradrag, selv om malen senere er endret. Begge originalenes
PDF-bytes beholdes. Uendret behandling oppretter ingen ekstra mal.

Native avgiftsmaler mangler et fradragsprosent-parameter og norske rapporteringskoder.
Tillegget konfigurerer native Item Tax Template/rader og lar kjernen beregne og føre.
Blank account_type på en valgt kostnadskonto presiseres til native Expense Account
for at kjernens vareavgiftsmal skal godta kontoen; root_type, kontonummer/navn og
bokførte verdier endres ikke. Det forutsetter brukerens ordinære kontorettigheter.
Koder på eldre bilag kan korrigeres som metadata gjennom native felt/Version;
økonomiske beløpsrettinger skal fortsatt bruke native kreditnota/journal.
Rapporten er en native Script Report, ikke egen hovedbok eller kontrollflate.


Kjernefunn: Item Tax Template tillater Expense Account, men ikke Cost of Goods Sold,
selv om den native fakturaens avgiftsrader/hovedbok godtar kostnadskontoen. Å endre
4300 fra COGS til generell kostnad ville endre eksisterende kontosemantikk. Den
smale klasseutvidelsen i item_tax.py beholder kjernens validering for alle ordinære
rader, bruker kjernens foretaks-/enkeltkontokontroll for COGS og beholder duplikatkontroll.
Ingen beregnings- eller bokføringsmetode erstattes.

## Lager, driftsmidler og mottakskjede: påvist gap før tilpasning

Fradragsfeltet finnes bare på kjøpsfaktura, og appen avviser lager/driftsmidler.
Native Valuation and Total gir riktig kapitalisering ved ordinære nettogrunnlag,
og native Landed Cost Voucher kan korrigere mottaket når fradraget endres på
fakturaen. En korrekt retur bruker den faktiske originalfakturaens behandling og
kjernens lenker mellom returmottak og kreditnota. Felt, native konfigurasjon og
ordinære hendelser mangler; ingen ny beregnings- eller bokføringsmotor trengs.

Verdsettingskonto velges fra eksisterende avgiftsrader eller en entydig konto med
native type Expenses Included In Valuation. Det finnes ikke et tilsvarende
Company-felt i denne versjonen. Ingen kontonumre eller kontooppretting skal gjettes.
Innkjøpsordre og varemottak trenger samme fradragsfelt slik at native mapping kan
føre valget videre. Ved fakturaendring skal native avgiftsdetaljer være grunnlaget
for kostnadsfordeling, ikke en ny beregning av MVA.

Påvist kjerneavvik: Valuation and Total på On Previous Row-grunnlag fordeler
verdsettingsavgiften feil ved blandede lager-/kostnadslinjer med frakt. Isolert
prøve ga 52,50 i ubalanse. Native avgiftsdetaljer og manuell fordeling i Landed Cost
Voucher kan løse dette, men ordinær flyt, driftsmidler, endringer og retur må
kvalifiseres samlet før den kombinasjonen åpnes. Ikke svekk kontrollen eller
bruk egne hovedboksposteringer for å skjule avviket.

Se [lager- og driftsmiddelflyten](vat-valuation.md) for konto-/rollekrav, native
justeringsbilag, delfakturering, retur og gjenstående fraktkombinasjoner.


App 0.4.4 viderefører fraktgapet med native Total og Landed Cost Voucher for
lager-/tjenestelinjer, inkludert mottakskjede, endret fradrag, delmengder og
retur. Ingen egen avgiftsberegning eller postering. Inklusiv pris følger den
native innstillingen per avgiftsgrunnlag. Den daværende sperren for
driftsmiddelretur er løst i 0.4.17 med originalens native Asset-/fakturakobling;
øvrig MVA-plan er fortsatt åpen. Se vat-valuation.md for prøver og presise avgrensninger.

Gjenbrukskontrollen i app 0.4.5 korrigerer ordinær radoppretting til kjernens
`add_taxes_from_tax_template`. Innstillingen for automatisk tilføying av avgifter
fra vareavgiftsmal respekteres; ved avslått automatikk må nødvendige rader finnes
eksplisitt. Flere grunnlag på samme konto krever fortsatt adapteren fordi kjernen
finner rader etter konto alene. Se [samlet gjennomgang](core-reuse-audit.md).

Registrert 25 % tjenestekjøp i NOK følger fra app 0.4.8 de eksisterende
vareavgiftsmalene og fradragsadapteren, native Add/Deduct og ordinær
kreditnota/betaling/oppgjør. Rapportens lesing av signed Deduct-detaljer er
korrigert, med enkelt grunnlag og hovedboksavstemming. Se
[tjenestekjøp fra utlandet](vat-foreign-services.md) for nøyaktig omfang.
Registrert valutalinjeflyt bruker fra 0.4.12 kjernens grunnlagsresolvers, ordinære
linjefelt og presisjonsinnstillinger; se vat-currency.md. Punkt 8 er fortsatt åpent
for ikke-registrert kvartal, registreringsovergang og øvrig utlandsomfang.

Importavklaringen har en avgrenset retting i app 0.4.13: native reversering av
klassifiserte deklarasjonsbilag får også negativt kopiert MVA-grunnlag på
81/82/83/84. Kjernen fører fortsatt alle beløp. Full vareimportflyt og valg av
deklarasjonsperiode er fortsatt åpne; se vat-import.md.


## MVA: dokumentert innførsel og kjernebasert eksport, 0.4.15

Deklarasjonsdato/-referanse bruker native Journal Entry-felt; kode 85 bruker
faktisk Purchase Receipt med tre metadatafelt og private originalvedlegg.
Varefaktura, toll-/kostnadsfaktura, Landed Cost Voucher, valutabetaling og
MVA-oppgjør bruker standard ERPNext. Ingen importmotor, egen dokumenttype eller
parallell hovedbok. Periode og rapportgrunnlag følger faktisk deklarasjon.
Se [arbeidsflyt, kilder og avgrensninger](vat-import.md).

Eksportprøven gjenbruker eksisterende avgiftsmal og native tilbud, ordre,
levering, EUR-faktura, delkreditnota, betaling/refusjon og engelske PDF-originaler.
Utenlandsk kundeadresse overstyrer ikke valgt innenlandsbehandling. Ingen ny
eksportkode er nødvendig. Tilbakegående tjenestefradrag prøves med native
bilag i registreringsterminen; tidligere faktura omskrives ikke.

Hele MVA-planen er fortsatt åpen for lav sats på utenlandske tjenester,
valutatillegg og resterende verdsettingskombinasjoner. Teknisk kvalifisering
er ikke generell norsk regnskapsaksept eller faktisk portalinnsending.

## Native driftsmiddelflyter i 0.4.17

Anleggsmiddelfrakt, delretur, fradragsendring og manuelt opprettingsvalg bruker
samme native bilag som lagerflyten. Registrert kapitalisert utenlandsk tjeneste
i NOK er også prøvd med 100/60/0 % fradrag og delkreditnota. Se
[gap og konkrete beløp](vat-valuation.md). Valuta og kvartalskapitalisering før
registrering inngår ikke i denne utvidelsen og skal ikke omtales som ferdige.
