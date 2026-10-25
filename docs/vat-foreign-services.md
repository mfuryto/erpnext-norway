# Tjenestekjøp fra utlandet

## Krav og prøvd kjerne før tilpasning

Skatteetaten krever omvendt avgiftsplikt for aktuelle fjernleverbare tjenester.
Registrerte foretak har ingen nedre beløpsgrense. Ikke-registrerte foretak må
vurdere samlet kvartalsgrunnlag; det er ikke en terskel per leverandør.
Omregning av avgiftsgrunnlaget skal bruke Tolletatens kurs ved levering.

Kilder: [Skatteetatens veiledning og satser](https://www.skatteetaten.no/satser/mva-satser-kjop-av-tjenester-fra-utlandet-svalbard-og-jan-mayen/),
[betalingsansvar og beløpsgrense](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-11/M-11-3/M-11-3.2/),
[valutaomregning](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-4/M-4-12/M-4-12.3/).

ERPNext 16.52.1 beregner allerede omvendt MVA med Add/Deduct i ordinære
avgiftsrader. Ved 1 000 i tjenestekjøp gir Add 25 % på 2714 og Deduct 25 % på
2704: kostnad 1 000, leverandørgjeld 1 000, inngående 250 og utgående 250.
Delvis fradrag kan bruke native vareavgiftsmaler og kostnadsrad som innenlands.
Native kreditnota, betaling, hovedbok og Journal Entry-oppgjør skal beholdes.

Påviste gap: våre ordinære linjevalg er hittil koblet til innenlandske kontoer,
og rapporten tolker signed Item Wise Tax Detail.amount for Deduct som om det
var positivt. Minste endring er norsk konfigurasjon av de eksisterende malene/
radene og korrekt lesing av native fortegn. Ingen ny beregnings- eller
bokføringsmotor, tabell eller arbeidsflate trengs for denne registrerte flyten.

## Avgrensning

Første kvalifisering gjelder registrert foretak og 25 % tjenestekjøp i NOK.
Ikke velg behandlingen bare fordi leverandøren har utenlandsk adresse; tjenesten
må oppfylle vilkårene. Vareimport, ikke-registrert kvartalsgrense, særskilt melding
og ulik handels-/avgiftskurs er fortsatt åpne punkter i vat-plan.md. De skal ikke
regnes som ferdige ut fra en enkelt korrekt teknisk postering.

## Registrert foretak: ordinært linjevalg i app 0.4.8

På leverandørfaktura/innkjøpsordre brukes eksisterende **Vareavgiftsmal**:
«Tjenestekjøp fra utlandet – MVA 25 % – 100 % fradrag» eller «… 0 % fradrag».
Eksisterende **MVA-fradrag i prosent** kan overstyres per tjenestelinje.
Fradragsadapteren er den samme som innenlands; bare kontoer, retning og kode
konfigureres annerledes. Kodene er 86 med fradrag og 87 uten fradrag.
Malene opprettes ved registrering eller én migreringspatch for allerede
registrerte foretak. De blir ikke standardvalg, og senere endringer overskrives ikke.

Native Add på 2714 gir inngående MVA; Deduct på 2704 gir utgående MVA uten å
øke leverandørgjelden. Ikke-fradragsført MVA går til linjens valgte kostnadskonto.
Rapporten leser native avgiftsdetaljer med riktig fortegn og avstemmer mot
hovedbok. Den beregner ikke fakturaens MVA på nytt. Leverandørens fakturadato
og kreditnotaens dokumentdato styrer hver sin rapportperiode.

Prøvd med vanlig eier uten System Manager:

| Kjøp 1 000 NOK | Leverandørgjeld | Kostnad | Utgående MVA | Inngående MVA |
| --- | ---: | ---: | ---: | ---: |
| Fullt fradrag | 1 000 | 1 000 | 250 | 250 |
| 60 % fradrag | 1 000 | 1 100 | 250 | 150 |
| Intet fradrag | 1 000 | 1 250 | 250 | 0 |

Native halv kreditnota i neste periode reverserer halvparten på alle sider.
Samlet gir disse tre kjøpene og kreditnotaene 375 utgående, 200 inngående og
175 til native oppgjørsbilag. Leverandørbetalingen følger faktisk restgjeld.
Blandet innenlands/omvendt behandling, vanlig native avgiftshode uten varemal,
ordreoverføring og kansellering inngår også i prøven. Private leverandøroriginaler
og regnskapsverdier sammenlignes igjen etter eksportert backup/restore.

De nye linjevalgene avviser dato før gyldig registrering,
lagerførte varer og driftsmidler. De avviser også manuelt feil avgiftsretning
og pris med inkludert omvendt MVA. Dette avgrenser den kvalifiserte flyten;
ikke-registrert kvartalsbehandling er fortsatt neste del av samme MVA-punkt.
Eksisterende manuelt konfigurerte avgiftsrader endres ikke ved migrering.

## Ikke-registrert foretak: terskel og gjenbruksprøve

Samlet avgiftsgrunnlag må **overstige** 2 000 NOK per kalenderkvartal.
Grensen gjelder foretakets aktuelle kjøp samlet, ikke hver leverandør. Det er
ikke et fradrag på 2 000 NOK i grunnlaget. Skattleggingsperioden er januar–mars,
april–juni, juli–september eller oktober–desember. Meldingen for omvendt
avgiftsplikt er en annen innleveringsvei enn den ordinære meldingen for
registrerte foretak. Det skal ikke leveres nullmelding for denne særskilte
meldingen. Hovedfristen er én måned og ti dager etter kvartalet, men andre
kvartal har sommerfrist 31. august. Utgangspunktet er dermed 10. mai,
31. august, 10. november og 10. februar året etter. Kalenderjusteringer og den
faktiske fristen kontrolleres i Skatteetatens innleveringsløsning.

Kilde for sommerunntaket: [gjeldende § 8-3-10 første ledd, med omtale](https://www.skatteetaten.no/rettskilder/type/handboker/skatteforvaltningshandboken/gjeldende/kapittel-8-opplysningsplikt-for-skattepliktige-trekkpliktige-mv/ID-8-3.001/ID-8-3.027/).
Eldre omtaler av 10. august skal ikke brukes som gjeldende sommerfrist.

Kilder: [betalingsansvar og beløpsgrense](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-11/M-11-3/M-11-3.2/)
og [Skatteforvaltningshåndboken § 8-3: særskilt periode og leveringsfrist](https://oppslag.rettskilder.skatteetaten.no/rettskilder2/type/handboker/skatteforvaltningshandboken/gjeldende/SKTFV2025_ID-8-0.001/SKTFV2025_ID-8-1.001).

Kjernens **Tax Withholding Category** har allerede datointervall og kumulativ
terskel. Den er derfor prøvd før eventuell tilleggskode. Den kjørbare prøven
`tests/runtime-vat-threshold-core.py` bruker vanlige bokførte leverandørfakturaer,
native historikk og samme kategori for to ulike leverandører. Ingen funksjoner
mockes, og hele prøven rulles tilbake. Prøven bruker en ordinær gjeldskonto,
ikke en MVA-konto: dette er en gjenbruksprøve, ikke anbefalt norsk behandling.

| Prøve i samme kalenderkvartal | Faktisk native resultat | Norsk krav som ikke dekkes |
| --- | --- | --- |
| Leverandør A: 1 500; leverandør B: 600 | Intet trekk, selv om foretakets sum er 2 100 | Summering på tvers av leverandører |
| Deretter A: 500; A har nå nøyaktig 2 000 | Trekk 500 på siste faktura | Grensen må overskrides, ikke bare nås |
| Samme siste faktura, leverandørbeløp 500 | Leverandørgjeld blir 0 | Norsk omvendt MVA skal ikke trekkes fra leverandørens vederlag |

Kildekontrollen av `TaxWithholdingController._base_threshold_query` viser
filtrering på part eller skatte-ID. `_check_historical_threshold_status`
beholder dessuten terskelpassering når tidligere historikk er «Settled».
Dette er nå også prøvd med en faktisk native kreditnota: full kreditering av
første A-faktura på 1 500 gir −375 i trekk og −1 125 i leverandørbeløp. Et nytt
A-kjøp på 100 får deretter 25 i trekk og 75 i leverandørgjeld, selv om de samlede
netto kjøpene hos A og B nå bare er 1 200. Originalen på 1 500 endres ikke.
Dette dokumenterer hvordan kjernen virker; prøven fastsetter ikke den norske
terskelregelen ved kreditnota eller åpner denne funksjonen som norsk MVA.
Felles, oppdiktet skatte-ID eller manuell terskeloverstyring skal ikke brukes
for å få funksjonen til å se ut som norsk kvartalsbehandling. Native avgiftsregler
velger fakturamaler; de løser heller ikke denne summeringen.

### Aksept før kvartalsbehandlingen åpnes

Følgende er åpne krav, ikke levert funksjonalitet:

| Tilfelle | Avklaring eller prøve som kreves |
| --- | --- |
| 1 999,99 / 2 000 / 2 000,01 NOK | Riktig grense og hele avgiftsgrunnlaget, med native avrunding |
| Flere leverandører, blandede tjenestelinjer | Bare aktuelle kjøp teller; vanlige innenlandskjøp og vareimport teller ikke |
| Flere fakturaer og tilbakeføring | Etterfølgende terskelpassering må følge normal registrering uten omskriving av bokførte originaler |
| Kreditnota i samme eller senere kvartal | Avklar terskelvirkning og rapportperiode; ikke anta at nettosummering alene er tilstrekkelig |
| Senere eller tilbakedatert godkjent registrering | Skille særskilt og ordinær melding; bevare original behandling og dokumentasjon |
| Låst eller allerede innlevert kvartal | Native periodelås og dokumentert korrigeringsvei, uten stille etterpostering |
| Parallelle registreringer | Samlet grunnlag må ikke avhenge av hvilken faktura som lagres først |
| Oppgjør, betaling og kvittering | Bruke eksisterende Journal Entry, bankflyt og private vedlegg; ingen parallell hovedbok |
| Utenlandsk valuta | Leveringsdato og Tolletatens avgiftskurs må skilles fra handels-/bokføringskurs |

Ingen egen terskelmotor, ny status eller ny arbeidsflate er innført gjennom
denne gjenbruksprøven. Dagens linjevalg er fortsatt avgrenset til det
registrerte NOK-/valutaomfanget beskrevet i vat-currency.md. Manuelle hovedboksbilag
alene gjør ikke normalflyten ferdig.

## Dokumentert gap: reversering av klassifiserte hovedboksbilag

ERPNexts ordinære `make_reverse_journal_entry` bytter debet/kredit, beholder
native `reversal_of` og kopierer de norske klassifiseringsfeltene. En faktisk
prøve med kode 87, grunnlag 1 000 og utgående MVA 250 viser to gap: kopiert
grunnlag blir fortsatt positivt, og appens registreringsvern avviser debet på
utgående MVA før registrering. Dette gjelder tilbakeføring av et dokumentert
hovedboksbilag, ikke beregning av kvartalsterskelen eller valg av melding.

Minste tilpasning skal bruke den eksisterende reverseringsfunksjonen, snu
grunnlagsmetadata bare ved samsvar med originalens motsatte MVA-linje og tillate
dokumentert negativ utgående kode 87 uten å åpne inngående fradrag. Beløp,
kobling, hovedbok, periodevern og kansellering skal fortsatt følge kjernen.
Ingen ny bilagstype, tabell eller reverseringsfunksjon trengs.

App 0.4.9 retter dette for **nye kode 87-reverseringer på 2704**. Ved ordinær
lagring matches konto, valuta/kurs, motsatte native beløp, kode, sats,
spesifikasjon og kopiert grunnlag mot det bokførte originalbilaget. Bare ved
samsvar snus det kopierte grunnlaget. Gjentatt lagring snur ikke fortegnet igjen.
Endrede beløp eller andre koder får ingen automatisk grunnlagsberegning.
Eksisterende bokførte metadata endres ikke automatisk.

Vanlig eier uten System Manager er prøvd med grunnlag 3 000 og utgående 750:
native reversering gir grunnlag −3 000, utgående −750 og intet inngående fradrag.
Kansellering, ny reversering etter kansellering, kjernens duplikatsperre,
godkjent registrering mellom original og reversering, fortsatt fradragssperre
før virkningsdato og native lukket regnskapsperiode inngår i prøven.
Rapporten avstemmer mot hovedbok; samme koblinger og fortegn kontrolleres etter
eksportert backup/gjenoppretting i app-CI.

Dette er retting av bilagsreversering, ikke avklaring av terskelvirkning for en
leverandørkreditnota i et senere kvartal. Kvartalsautomatikk, fordeling mellom
særskilt og ordinær melding ved registrering og ulik valutakurs er fortsatt åpne.

## Valutaavgrensning også for manuelle rader

App 0.4.11 lukker omgåelsen gjennom manuelle aktive 2704/2714-rader. Native
prosent-/beløpsprøver viste at bokføringskursen fortsatt bestemmer lagret
avgiftsgrunnlag, selv når det faste avgiftsbeløpet justeres. Se vat-currency.md
for prøvetall, eksisterende grunnlagsutvidelsespunkt og presisjonsbegrensning.
Leverandørfaktura, kreditnota, innkjøpsordre og rapport må bruke samme avgrensning.
Eksisterende bokførte data endres ikke; ordinære valutabilag og kvalifisert NOK-
behandling beholdes. App 0.4.12 åpner det avgrensede registrerte valutalinjevalget med egen
leveringsdato og avgiftskurs gjennom kjernens grunnlagskrok; se vat-currency.md.
Manuelle rader uten disse opplysningene forblir sperret. Ikke-registrert
kvartalsflyt er fortsatt åpen.

## Avklaring som kreves før automatisk kvartalsbehandling

Kildekontroll 25. oktober 2026 bekrefter grensen, kvartalet, innleveringsveien og
leveringskursen. De gjennomgåtte offentlige kildene gir ikke en uttrykkelig
løsning på disse kombinasjonene:

1. Opprinnelig kvartal har kjøp 2 100 og innrapportert MVA 525. En reell
   leverandørkreditnota på 200 utstedes i neste kvartal. Hvordan påvirkes
   terskelen, hvilken melding skal endres/leveres, og hvordan behandles et
   krediteringskvartal uten andre kjøp? Skill opprinnelig feil fra senere
   prisavslag/heving. Generell periodisering av kreditnota avklarer ikke alene
   terskelvirkningen eller innleveringsveien.
2. Foretaket har aktuelle kjøp før og etter godkjent registrering med virkning
   midt i kvartalet. Hvordan avgrenses grunnlaget i særskilt melding mot første
   ordinære melding? Hva gjelder hvis vedtaket får tilbakevirkende effekt etter
   at særskilt melding er levert? Vurder også eventuell fradragsrett særskilt.

Dette trenger dokumentert regnskapsmessig avklaring før automatikk implementeres.
Dagens bilag og rapportgrunnlag skal ikke omskrives ved endring av Company.
Kjernens kreditnota, dokumenterte korrigeringsbilag, periodelås, Journal Entry,
bankbetaling og File-vedlegg skal fortsatt brukes. Ingen egen kvartalsmotor,
innleveringsstatus eller parallell hovedbok er innført her.
