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

De nye linjevalgene avviser dato før gyldig registrering, valuta ulik NOK,
lagerførte varer og driftsmidler. De avviser også manuelt feil avgiftsretning
og pris med inkludert omvendt MVA. Dette avgrenser den kvalifiserte flyten;
ikke-registrert kvartalsbehandling er fortsatt neste del av samme MVA-punkt.
Eksisterende manuelt konfigurerte avgiftsrader endres ikke ved migrering.
