# Norsk kontoplan gjennom ERPNext-kjernen

`resources/norway-chart/norway.csv` er en fil for den eksisterende **Chart of Accounts
Importer**. Den beholder alle 745 kontonumre og norske navn fra den låste,
LGPL-lisensierte Odoo-kilden. Ingen Odoo-app eller egen importmotor installeres.
Se [proveniens og lisens](../resources/norway-chart/NOTICE.md).

## Native oppsett

Dette er teknisk kjerneoppsett, ikke samlet norsk produksjonsaksept. Fullfør den
ordinære oppstartsveiviseren med faktisk foretak, Norway, NOK, Europe/Oslo og riktig
regnskapsår. Ikke bruk syntetiske selskaper eller bilag på driftsserveren.

Ta [backup](backup.md) før kontoplan byttes. Åpne **Chart of Accounts Importer**, velg
det aktuelle tomme foretaket og last opp CSV-filen. Kjernen validerer og erstatter
kontoplanen; den avviser import når foretaket allerede har hovedboksposter. Ikke
omgå denne kontrollen eller bruk import som løpende oppdatering av en brukt plan.
Senere kontotilpasning gjøres i den native kontoplanen.

Kontroller deretter standardkontoene i **Company**:

| Native felt | Konto / valg |
| --- | --- |
| Default Receivable Account | 1500 Kundefordringer |
| Default Payable Account | 2400 Leverandørgjeld |
| Default Bank Account | 1920 for første aktuelle NOK-bank; knytt faktisk bankkonto i Bank Account |
| Default Cash Account | 1900 dersom kontanter faktisk brukes |
| Round Off Account | 7740 Øresavrunding |
| Default Income / Expense Account | Velges etter virksomheten; bruk Item Defaults for riktig konto per artikkel |

Bank, kontantkonto, valuta og eventuelle flere bankkontoer må stemme med faktisk
bruk. Filen er et NOK-utgangspunkt. Kontonavn som nevner utenlandsk valuta setter
ikke automatisk opp en ferdig kvalifisert valutaflyt.

## Ikke MVA-registrert

I den låste ERPNext-versjonen oppretter norsk standardoppsett en 25 %-mal som
standard uten å kjenne registreringsstatusen. Dette kan også skje ved kontoplanimport.
For et ikke-registrert foretak må standardvalget fjernes på foretakets **Sales Taxes
and Charges Template** og **Purchase Taxes and Charges Template** før fakturering.
Kontroller at en vanlig ny salgsfaktura ikke automatisk får avgift. Ikke bruk dette
som en generell definisjon av fritak/nullsats eller som regel for alle utenlandskjøp.

Ved kjøp skal manglende fradragsrett gi riktig kostnad og ingen urettmessig inngående
MVA. Native avgiftsrader er teknisk prøvd, men norsk behandlingsvalg per linje og
registrering med virkningsdato må fortsatt ferdigstilles. Kontoens navn eller type
er ingen MVA-regel. Ingen faktisk registreringsstatus legges i offentlige testdata.

## Artikkel, kreditnota og betaling

Bruk native Item for både varer, tjenester og lisenser. Slå av **Maintain Stock**
for artikler som ikke skal lagerføres. Velg **Item Defaults** for det aktuelle
foretaket; disse overstyrer de generelle inntekts-/kostnadsstandardene i normalflyten.

Native kreditnota kan enten redusere originalens utestående eller stå som egen åpen
post. I prøven brukes **Update Outstanding for Self = av** på begge fakturatypene
for å redusere originalen før betaling. Dette er et eksisterende kjernevalg, ikke
en ny kreditnotaberegning. Vanlig Payment Entry og Bank Reconciliation brukes videre.

## Kilde og mapping

Koder og navn er uendret. Konverteringen til native felter er uttrykkelig:

- Bare 1500 og 2400 brukes som første native reskontrotyper. 2740 er Tax, ikke Payable.
- 1570 Reiseforskudd blir ikke en kontant- eller bankkonto.
- Finansinntekter i 80xx legges under Income; finanskostnader ligger under Expense.
- Avgiftsgrunnlagskontoer som 1470 er ikke fysiske lagerkontoer.
- Fem native røtter og ordinære native kontogrupper brukes. Ingen ny rapportmotor.

Kjernen kan tilføye sine egne unummererte avgiftskontoer og maler ved landoppsett.
De 745 nummererte kontoene og norsk avgiftsoppsett er derfor ikke det samme som
at alle automatisk opprettede landmaler er kvalifisert for norsk bruk.

`python3 scripts/build_norway_chart.py` bygger filen deterministisk fra lokale,
hashkontrollerte kilder. Det gjør ingen nettverkskall og endrer ingen foretak.

## Etterprøving

Den isolerte prøven importerer filen med native API, kontrollerer alle 745 navn/koder
og 1500/2400-defaults. En vanlig eierbruker uten System Manager, avgrenset til foretaket,
prøver normal faktura-/kreditnota-/betalingsflyt og avstemmer fire banktransaksjoner.
Native resultatrapport gir forventet 475, mens bankkontoen gir 275 etter en separat
eiertransaksjon. Forsøk på å importere planen etter bokføring avvises av kjernen.
Samme data kontrolleres etter backup/gjenoppretting og native migrering.

Dette kvalifiserer et avgrenset syntetisk grunnlag. Nummereringsvern, dokumentbevaring,
norske dokumentmaler, MVA-melding, SAF-T og årsspesifikt skattegrunnlag leveres videre
etter planen. Ingen generell norsk etterlevelse hevdes av denne kontoplanprøven.
