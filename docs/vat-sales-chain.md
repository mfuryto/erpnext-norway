# MVA i den ordinære salgskjeden

## Prøvd kjerne og dokumentert gap

ERPNext 16.52.1 har allerede mapping fra Quotation til Sales Order, videre til
Delivery Note og Sales Invoice, samt native kreditnota og betaling. Disse
funksjonene skal brukes. Regnskapsprøven gjelder NOK og registrert foretak;
15/12/nullsats er bare aktuelle når vilkårene for den konkrete ytelsen er oppfylt.
Se [Skatteetatens satser](https://www.skatteetaten.no/satser/merverdiavgift/).

En faktisk prøve av våre delte vareavgiftsmaler ga feil tilbudsbeløp: 3 000
netto med 25/15/12 % ble 4 040. Native automatikk la inn både 270*- og
271*-kontoene fra malene. Samme prøve med bare native utgående avgiftsrader ga
3 520 i **alle fire dokumentene**, og fakturaen fikk kodene 3/31/33. Kjernens
beregning og dokumentoverføring fungerer; gapet gjelder avgiftsradkonfigurasjon.

Minste tilpasning er å bruke den eksisterende salgsavgrensningen i
`vat_catalog.prepare_items` også for tilbud, salgsordre og levering. Native
`add_taxes_from_tax_template` oppretter fortsatt radene. Automatisk opprettede
inngående rader fra de delte malene må tas bort før native omberegning; manuelt
konfigurerte inngående rader skal gi en forståelig feil. Henvisninger til andre
avgiftsrader må beholdes ved endret rekkefølge. Det trengs ingen ny beregning,
mappingfunksjon, arbeidsflate eller egne MVA-felt på de tre kommersielle dokumentene.

Nettleserens vanlige forhåndsvisning må følge samme oppsett, slik at brukeren
ser riktig tilbuds-/ordrebeløp før lagring. Bokførte dokumenter og PDF-originaler
skal bevares. Hele kjeden, kreditnota, delvis levering/fakturering, blandede
linjevalg og normal betaling må prøves før omfanget regnes som kvalifisert.

## Avgrenset regnskapsprøve i 0.4.10

En vanlig eier uten System Manager oppretter et tilbud med fire tjenestelinjer,
25/15/12/nullsats og 10 % rabatt på nettobeløpet. Kjernen overfører tilbudet til
salgsordre, to delleveringer og to delfakturaer: samlet netto 3 600, utgående MVA
468 og kundefordring 4 068. Koder 3/31/33/5 og native kildelenker følger linjene.
En delkreditnota i neste periode reverserer 117 MVA og 1 017 i kundefordring.
Native kundebetalinger på 1 017 og 2 034 gjør begge fakturaene opp; rapporten
viser 468 og −117 i hver sin periode, samlet 351, og ingen inngående MVA.

Prøven omfatter også et tilbud med 1 250 inkludert 25 % MVA (netto 1 000), samt
frakt på 100 med 25 % MVA. En native henvisning til fraktraden peker fortsatt
på samme rad etter fjerning av automatisk inngående MVA. Eksplisitt inngående
MVA og henvisning til den fjernede raden avvises. Norsk og engelsk original-PDF
bevares ved normal innsending; eksportert restore kontrollerer originalbytes,
dokumentlenker, hovedbok og rapport. Nettleserprøven dekker standard varevalg,
blandede satser, beløpet før lagring og vanlig kladdlagring i alle fire skjermene.

Dette er en tjenesteprøve i NOK for registrert foretak. Den kvalifiserer ikke
lagerverdsetting ved salg, alle kombinasjoner av frakt/rabatt/avrunding, valuta,
utland, ikke-registrert særskilt melding eller hele MVA-planen. Returnerte
leveringer følger kjernens eksisterende returflyt; ingen ny returadapter er laget.
