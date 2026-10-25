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
Dette er førstevalget for videre grunnlagstilpasning. Det er ikke tillatelse
til å åpne flyten før NOK-presisjon, kildedato, original kurs, delvis fradrag,
kreditnota, betaling og rapport er prøvd samlet. Ingen ny avgiftsmotor eller
grunnlagsadapter er levert i denne avgrensningen.

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
Alle prøvebilag rulles tilbake. Det er ingen ny valutakurskilde, nye felt eller
endret presisjonsinnstilling. Den generelle valutabehandlingen er ikke fullført.
