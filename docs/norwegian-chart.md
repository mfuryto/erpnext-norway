# Norsk kontoplan gjennom ERPNext-kjernen

Med den norske appen installert finnes **Norsk kontoplan** i ERPNexts ordinære
malvalg. Den er første valg i oppstartsveiviseren for Norway, og nye selskaper med
Norway/NOK får den som standard når ingen annen mal er valgt. Eksplisitte malvalg,
kopiering fra eksisterende selskap og eksisterende selskaper beholdes.

De 745 norske kontonumrene/navnene opprettes direkte med kjernens `create_charts`.
Den generiske Standard-planen opprettes ikke først. Ingen manuell sletting eller
CSV-import skal inngå ved ny selskapsoppretting. Forhåndsvisning bruker også den
native trebyggeren. Se [proveniens og lisens](../resources/norway-chart/NOTICE.md).

ERPNext 16.51.1 søker bare etter malfiler i sitt eget kodeområde, og Company sin
hjelpemetode har ingen parameter for eksternt malinnhold. Appen leverer derfor
en referanse til appens datafil i den eksisterende malkatalogen ved imagebygging.
Ingen eksisterende ERPNext-filer endres. En smal Frappe-utvidelse sender maldata
til kjernens kontooppretting, slik at gjentatte kontonavn beholdes uendret.
Standardkontoer, lagersteder og øvrig selskapsoppsett håndteres av kjernen. Andre
maler bruker uendret native funksjon.

## Nytt selskap

Oppdater/installer den norske appen før selskapet opprettes. Velg Norway, NOK og
**Norsk kontoplan** i den ordinære oppstartsveiviseren eller Company. Bruk faktisk
foretak og regnskapsår på serveren; ingen syntetiske eksempler i drift. Malen er
foreløpig kvalifisert for NOK. Den endrer ikke registreringsstatus for MVA.

## Allerede opprettet selskap

Appen erstatter ikke kontoplanen i eksisterende selskaper. Den tidligere CSV-filen
`resources/norway-chart/norway.csv` beholdes for native Chart of Accounts Importer
ved en uttrykkelig valgt overgang på et foretak uten hovedboksposter. Kjernen
avviser erstatning når hovedbok finnes. Ikke omgå den kontrollen eller slett kontoer
enkeltvis for å fremtvinge et bytte. Senere tilpasning skjer i den native kontoplanen.

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

I den låste ERPNext-versjonen oppretter landoppsettet tidløse MVA-standardmaler
uten å kjenne registreringen. Med app 0.3.0 velges **MVA-registrering (Norge)** i
Foretak. Velg **Ikke registrert** nå; bekreftet registrering med virkningsdato kan
legges inn senere. Appen fjerner de tidløse MVA-standardene når registreringen
konfigureres. Eksisterende bilag og hovedbok beregnes ikke på nytt.

[Norsk MVA-registrering og overgang](vat-registration.md) beskriver felt, daterte
native regler, ordinær 25 %-behandling, kreditnota og avgrensningene. Fradrag for
eldre kjøp vurderes særskilt. Ikke-registrering er ikke en generell nullsats eller
et fritak for plikter ved utenlandskjøp.

Uten appen må standardvalget fortsatt fjernes manuelt på foretakets Sales Taxes
and Charges Template og Purchase Taxes and Charges Template før ikke-registrert
fakturering. Kontoens navn eller type alene er ingen MVA-regel.

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
