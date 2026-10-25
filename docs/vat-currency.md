# Valuta ved omvendt MVA

## Krav, prøvd kjerne og dokumentert gap

Avgiftsgrunnlaget for tjenestekjøp i utenlandsk valuta omregnes etter kursen på
leveringstidspunktet, jf. [Skatteetatens omtale av § 4-12 annet ledd](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-4/M-4-12/M-4-12.3/).
Bokføringskurs og avgiftskurs kan derfor ikke uten videre behandles som samme
parameter. Prøvetallene under er syntetiske, ikke publiserte valutakurser.

En faktisk, rollbacket prøve på ERPNext 16.52.1 med registrert norsk foretak,
100 EUR og bokføringskurs 10 viste:

| Native radvalg | Rapportert NOK-grunnlag | Utgående/inngående MVA | Leverandørgjeld NOK |
| --- | ---: | ---: | ---: |
| On Net Total, 25 % | 1 000 | 250 / 250 | 1 000 |
| Actual, 27,50 EUR | 1 000 | 275 / 275 | 1 000 |
| Actual, 27,53425 EUR ved standardpresisjon 2 | 1 000 | 275,30 / 275,30 | 1 000 |

Med en dokumentert avgiftskurs 11 ville grunnlaget være 1 100 og MVA 275.
Fast avgiftsbeløp løser altså ikke grunnlagsrapporteringen. Den siste prøven
viser også at et finere beløp avrundes i fakturavaluta før NOK-omregningen.
Ikke erstatt avgiftskursen med en justert prosentsats; det ville feilmerke satsen.

Kjernen har allerede `erpnext_taxable_base_resolvers` på serveren og
`erpnext.taxable_base_resolvers` i nettleseren. Begge beregningsfilene ble
sammenlignet med det låste offisielle imaget og hadde identiske SHA256-hasher.
App 0.4.12 bruker disse eksisterende krokene. Tilpasningen leverer bare
linjegrunnlaget; kjernen beregner avgift, varefordeling, avrunding og hovedbok.

## Minste retting av eksisterende omgåelse

Appens vareavgiftsmaler avviste allerede fremmed valuta, men manuelt opprettede
rader på 2704/2714 kunne lagres og bokføres uten den samme avgrensningen. Da kunne
rapporten vise et tilsynelatende avstemt, men feil omregnet avgiftsgrunnlag.

Minste retting er samme avgrensning for aktive 2704/2714-rader i ordinære
leverandørfakturaer, kreditnotaer og innkjøpsordrer. Rapporten skal også avvise
eldre slike fakturaer i den valgte perioden fremfor å vise grunnlaget som
kvalifisert. Ingen bokførte dokumenter, beløp eller originaler skal omskrives.
NOK-flyten og ordinære valutabilag uten denne omvendte behandlingen beholdes.
Andre utenlands-/importbehandlinger er fortsatt egne åpne punkter i vat-plan.md.

## Prøvd avgrensning i app 0.4.11

Den kjørbare prøven bruker kjernens kalkulator direkte for tabellen ovenfor.
Deretter prøver en vanlig eier uten System Manager reell ordinær lagring av de
samme dokumentene. Manuelle prosent-/beløpsrader, innkjøpsordre og endret valuta
på kreditnota avvises. Native sperre mot endret tallkurs på kreditnota beholdes.
En vanlig EUR-faktura med ordinær inngående MVA og en NOK-faktura med omvendt
MVA bokføres fortsatt og avstemmes mot hovedbok gjennom eksisterende rapport.
Alle prøvebilag rulles tilbake. Dette var avgrensningen i 0.4.11; det kvalifiserte linjevalget i 0.4.12 er beskrevet nedenfor.

## App 0.4.12: dokumentert kurs på den ordinære linjen

Kjerneprøven med faktisk `erpnext_taxable_base_resolvers` og native Property
Setter for transaksjonsfeltenes presisjon ga 1 101,37 NOK i grunnlag og 275,34
NOK i MVA for 100 EUR, bokføringskurs 10 og avgiftskurs 11,0137. Leverandørgjelden
forble 1 000 NOK. Det trengs ingen ny MVA-beregning eller ekstra journal.

Det dokumenterte datagapet er to uavhengige opplysninger som standardlinjen ikke
har: faktisk leveringsdato for avgiftskursen og NOK per valutaenhet etter den
kursen. Native `conversion_rate` skal fortsatt være bokføringskurs. Ordinære
File-vedlegg brukes for kursgrunnlag og leverandøroriginal. Tolletatens
[daterte kurser og myntenheter](https://www.toll.no/no/verktoy/valutakurser/)
brukes ved registreringen; en kurs for 100 enheter må oppgis per én enhet.
Ingen egen kurstjeneste eller automatisk kildegjetting er innført.

Adapteren leverer `item.net_amount * MVA-kurs / conversion_rate` til
kjernens eksisterende grunnlagskrok. Native vareavgiftsmal bestemmer fortsatt
prosent og fradrag. Kjernen fører Item Wise Tax Detail, hovedbok og betaling.
Samme grunnlag leveres til nettleserens native krok. Native Property Setter
på fem felt gir ni desimalers mellomregningspresisjon; NOK-feltene og ordinære
dokumenttotaler beholder sin eksisterende presisjon. Eksplisitte brukervalg
bevares; valutaflyten krever minst seks desimaler.

Første omfang er registrert foretak, NOK-regnskap, tjenestelinjer med 25 %
omvendt MVA og uten ekstra frakt-/avgiftsgrunnlag eller blandet innenlands
behandling på samme valutabilag. Begge kursopplysningene følger native
ordreoverføring og opprinnelig linje ved kreditnota, ikke kreditnotaens nye
valutakurs. Ingen historiske bilag etterfylles automatisk. Den kjørbare appprøven dekker native lagring, bokføring, delvis fradrag, rabatt,
kreditnota, betaling, periodelås, nettleser og eksportert backup/restore.

Native satspresisjon må også dekke fradrag med desimaler: 33,33 % fradrag ved
25 % MVA gir 8,3325 % inngående sats. Standard tre satsdesimaler avrunder dette
før beregningen. Også satsfeltet konfigureres derfor med native Property Setter;
ingen egen avrundings- eller fradragsberegning skal erstatte kjernen.

Også avgiftsradens løpende `total` trenger mellomregningspresisjon. Ellers
kan separate Add/Deduct-rader gi 100,01 EUR i stedet for 100 EUR før den siste
dokumentavrundingen. Native dokumenttotal og NOK-hovedbok beholder to desimaler.

## Regnskapsfasit og bruk

Velg den eksisterende vareavgiftsmalen for tjenestekjøp fra utlandet på vanlig
innkjøpsordre eller leverandørfaktura. På hver valutalinje fylles «Leveringsdato
for MVA» og «MVA-kurs (NOK per valutaenhet)». Ordinær valutakurs beholdes som
bokføringskurs. Dokumenter kurskilden med vanlig fakturavedlegg. Feltene er
oversatt til norsk og følger kjernens ordreoverføring uten egen mapping.

| Prøve: 100 EUR, bokføringskurs 10, MVA-kurs 11,0137 | Fullt fradrag | 60 % fradrag | Intet fradrag |
| --- | ---: | ---: | ---: |
| MVA-grunnlag NOK | 1 101,37 | 1 101,37 | 1 101,37 |
| Utgående MVA NOK | 275,34 | 275,34 | 275,34 |
| Inngående MVA NOK | 275,34 | 165,21 | 0 |
| Kostnad NOK | 1 000 | 1 110,14 | 1 275,34 |
| Leverandørgjeld EUR | 100 | 100 | 100 |

Kjernen fører ett øre på ordinær avrundingskonto ved 60 %-prøven. En prøve med
10 000 EUR og 33,33 % fradrag gir 9 177,17 NOK inngående MVA uten å endre
leverandørbeløpet. To ordrelinjer med forskjellige leveringskurser og 10 % rabatt
gir 1 035 NOK i samlet grunnlag og 258,75 NOK MVA på fakturaen.

Delkreditnota i neste periode beholder opprinnelig leveringsdato og MVA-kurs.
Dette følger [GBS 1 punkt 2.4, januar 2026](https://www.regnskapsstiftelsen.no/wp-content/uploads/2026/02/2026-01-GBS-1-Kreditnota-%E2%80%93-innhold-utstedelse-bokforing-og-oppbevaring-januar-2026.pdf).
Senere endring av registreringsdato endrer verken rapporterte originaler eller
kreditnotaens opprinnelige behandling; nye kjøp må fortsatt ha gyldig registrering.
Native vern mot endring etter bokføring og lukket periode beholdes.

Native betaling av samlet restgjeld 240 EUR med 2 520 NOK gir 120 NOK kurstap
gjennom kjernens valutabilag. MVA forblir 671,76 utgående og 479,03 inngående,
netto 192,73 NOK. Ingen MVA-justering lages ved betaling. Dokumentkoblinger,
hovedbok og seks private PDF-originaler kontrolleres etter eksportert restore.

Migrering oppretter to native Custom Fields på hver av de to varelinjetypene
og Property Setters for avgiftsradene. Oppdateringsverktøyet tar backup før
migrering. Bokførte eldre valutabilag etterfylles ikke og må fortsatt oppfylle
rapportens dokumentasjonskrav. Ikke-registrert kvartal, levering før registrering,
blandet innenlandsbehandling, ekstra frakt på valutabilaget og vareimport er
fortsatt åpne omfang; dette fullfører ikke hele MVA-planen.

## Native sats og tilleggsgrunnlag i 0.4.16

Påvist gap før endring: kjernen beregnet 12 % med native Add/Deduct og delvis
fradrag korrekt, men tillegget var hardkodet til 25 %. Samme mal-/kontokonfigurasjon
utvides til 2709/2718 og kode 88/89. Satsen velges etter tjenestens art;
utenlandsk leverandør er ikke i seg selv grunnlag for lav sats. Se
[gjeldende håndbok om formidling av persontransport](https://oppslag.rettskilder.skatteetaten.no/rettskilder2/type/handboker/merverdiavgiftshandboken/gjeldende/MVA2025_M-5).
Eksisterende maler overskrives ikke. Migreringen tilføyer bare manglende
12-prosentvalg til registrerte foretak, uten å gjenopprette slettede 25-prosentmaler.

Kjernen har allerede per-varelinjegrunnlaget fra en tidligere avgiftsrad.
Valutagrunnlaget kan derfor bruke standard radhenvisning for dokumentert frakt/
tillegg før MVA. Ingen ny fordelingsmotor er nødvendig. En referanse etter en
allerede beregnet MVA-/MVA-kostnadsrad avvises; en tidligere nullrad tilfører
ikke MVA til grunnlaget. Standard radhenvisning vises også på norsk valutagrunnlag,
med bevaring av eksisterende brukerdefinert Property Setter.

Prøve: 100 EUR tjeneste + 10 EUR tillegg, bokført til kurs 10 og MVA-kurs 11,
gir 110 EUR leverandørgjeld og 1 210 NOK MVA-grunnlag. Ved 12 % og 60 % fradrag
fører kjernen 145,20 utgående, 87,12 inngående, 58,08 MVA-kostnad og 100 frakt.
Delkreditnota bruker faktisk kreditert tillegg (5 EUR i prøven); en Actual-rad
skal ikke automatisk halveres bare fordi antall varer halveres. Native betaling
1 155 NOK og refusjon 577,50 NOK til kurs 10,5 endrer ikke MVA-grunnlaget.

Kvartalsbehandling bruker begge satser med samlet terskel, se vat-quarterly.md.
Tidligere avgrensninger om driftsmidler, blanding med andre valutabehandlinger
og leveringsdato rundt registrering gjelder fortsatt inntil de er kvalifisert.
