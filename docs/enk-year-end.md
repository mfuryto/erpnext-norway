# ENK: eiertransaksjoner og årsgrunnlag

Første omfang er norsk ENK uten ansatte, NOK og kalenderår. ERPNexts
bokføringsbilag, leverandørfaktura, hovedbok, saldobalanse, resultatregnskap,
balanse og periodeavslutningsbilag brukes direkte. Det opprettes ikke en
parallell eierreskontro, skattekalkulator eller ny årsavslutningsside.

## Personlig skatt og uttak

Eieruttak er ikke lønn eller fradragsberettiget driftskostnad. Foretakets
overskudd endres ikke av at eieren tar ut penger. Se
[Altinn om skatt og uttak i ENK](https://info.altinn.no/starte-og-drive/skatt-og-avgift/skatt/skatt-for-enkeltpersonforetak/).
Personlig forskuddsskatt bygger på flere personlige forhold enn foretakets
resultat. Oppdater forventet overskudd og betal de faktiske kravene fra
[Skatteetaten](https://www.skatteetaten.no/bedrift-og-organisasjon/skatt/forskuddsskatt/forskuddsskatt-for-enkeltpersonforetak).
Appen beregner ikke en personlig skatteprosent fra resultatregnskapet.

Bruk **Bokføringsbilag** for eierbevegelser. I den leverte kontoplanen:

| Hendelse | Debet | Kredit |
| --- | --- | --- |
| Eieren skyter inn penger på driftskonto | 1920 Bankinnskudd | 2062 Innskudd kontanter |
| Overføring fra driftskonto til privat | 2060 Uttak kontanter | 1920 Bankinnskudd |
| Personlig forskuddsskatt betalt fra driftskonto | 2070 Forskuddsskatt | 1920 Bankinnskudd |
| Personlig restskatt/tilleggsforskudd betalt fra driftskonto | 2072 Tilleggsforskudd/restskatt | 1920 Bankinnskudd |
| Refusjon av slik personlig skatt til driftskonto | 1920 Bankinnskudd | Den avstemte personlige skattekontoen |

Dette er bruk av de eksisterende kontoene, ikke universelle krav til kontonumre.
Alle disse eierkontoene har hovedgruppe Egenkapital. Ikke bruk selskapsskatt,
lønn eller kostnadskonto 8980 bare fordi navnet inneholder «privatuttak».
Personlig skatt betalt helt privat føres ikke som en ekstra utgift eller en
oppdiktet bankbevegelse i foretaket. Skill MVA-oppgjør fra personlig skatt.
Legg bankunderlag og en tydelig forklaring ved det ordinære bilaget.

## Kjøp som eieren betaler privat

Registrer det faktiske næringskjøpet som vanlig **Leverandørfaktura**, med
leverandør, dokumentasjon, kostnad/eiendel og korrekt MVA-status. Et ENK som
ikke er MVA-registrert skal ikke få et ordinært inngående MVA-fradrag bare
fordi eieren har betalt fakturaen.

Gjør opp fakturaen med et ordinært bokføringsbilag: debet leverandørgjeld
på 2400 med **Leverandør**, **Referansetype = Leverandørfaktura** og riktig
**Referansenavn**; kredit 2062. Referansen lar kjernen redusere utestående
beløp. Ikke opprett en falsk betaling fra foretakets bank eller bokfør
kostnaden på nytt. Refunderer foretaket senere eieren, er betalingen en
eierbevegelse mot 2060/1920; den er ikke enda et næringskjøp.

## Finn årsgrunnlaget på de eksisterende arbeidsstedene

Velg samme foretak, inntektsår, NOK og relevante regnskapsbøker i rapportene.
Behold standardbokens poster når foretaket bruker standardboken.

| Rapport | Bruk |
| --- | --- |
| Resultatregnskap | Inntekter, kostnader og årets bokførte resultat, også etter periodestenging. |
| Balanse | Avstem bank, fordringer, gjeld, eiendeler og egenkapital ved årsslutt. |
| Saldobalanse | IB, årets debet/kredit og UB per konto. Slå av grupper ved summering av kontolinjer i eksport, så gruppesummer ikke telles på nytt. |
| Hovedbok | Kilder og bevegelser på blant annet 2060, 2062, 2070 og 2072. Bevar rapport/underlag som dokumenterer eierbevegelsene. |
| Kundereskontro/leverandørreskontro og bankavstemming | Åpne dokumenter og avstemming mot faktiske inn-/utbetalinger. |

I **Saldobalanse** gjør valget **Avslutningspostering for gjeldende periode**
at resultatkontoene viser null etter stenging. Slå dette av for å se årets
resultatkonti uten selve avslutningsposten. Behold **Ta med avslutningspostering i inngående saldo** for neste års IB. Disse er kjernens eksisterende
rapportfiltre; norsk visning kan variere med språkversjonen.
[Rapportforklaring fra Frappe](https://docs.frappe.io/erpnext/financial-statements-show-unexpected-numbers).

## Årsavslutning med kjernen

1. Fullfør og avstem vanlige fakturaer, kreditnotaer, betalinger, bank, MVA,
   lager, periodiseringer og avskrivninger. Kontroller manglende dokumentasjon
   og utkast på de ordinære arbeidsstedene. Ta og prøv gjenoppretting av backup.
2. Avstem årets eierkonti. Vil du nullstille de aktuelle 206x-/207x-kontoene,
   flytt de faktiske saldoene til 2050 med et ordinært bokføringsbilag datert
   årsslutt. En debetsaldo nullstilles med kredit på eierkontoen og debet 2050;
   en kreditsaldo motsatt. Behold kontospesifikasjonen før omføringen.
3. Opprett **Bilag for periodeavslutning** (Period Closing Voucher) for året,
   med 2050 som avslutningskonto i dette ENK-oppsettet. Kontroller og bokfør.
   Vent på **Fullført** (Completed). Kjernen disponerer årets faktiske overskudd eller tap.
   Ikke legg til en egen beregnet disponering gjennom appen.
4. Kontroller resultatrapporten, balansen og saldobalansen med riktige filtre.
   Balansekontiene videreføres av kjernen. Opprett neste regnskapsår ved behov;
   ikke lag et nytt inngående bilag som dupliserer eksisterende saldoer.
5. Den låste kjernen 16.52.1 avviser ny postering/kansellering innen en periode
   som har periodeavslutningsbilag. Bruk også vanlig **Regnskapsperiode** (Accounting Period) eller
   frysingsdato etter foretakets praksis. Ikke bygg et nytt låseregister. Ved
   korreksjon må den native gjenåpnings-/kanselleringsrekkefølgen følges.

Frappe sin løpende dokumentasjon beskriver periodeavslutningsbilag og periodelås
hver for seg. Faktisk låseatferd skal prøves på det låste imaget; den skal ikke
utledes fra en annen kjerneversjons veiledning.

## Teknisk prøve og hva som gjenstår

`tests/runtime-enk-core.py` bruker vanlig regnskapsbruker og de samme offentlige
rapport-API-ene som Desk. Den prøver privat betalt leverandørfaktura med native
oppgjørsreferanse, innskudd/uttak/refusjon, personlig skatt, kansellering,
eieromføring, overskudd i 2026 og underskudd i 2027. Rapportene og SAF-T skal
stemme med hovedboken og overleve eksportert backup/gjenoppretting.

Dette kvalifiserer bokført årsgrunnlag. Det er ikke en full næringsspesifikasjon
eller ferdig personlig skatteberegning. Skatteetaten skiller mellom personlige
opplysninger og næringsopplysninger, og det må ikke rapporteres dobbelt.
[Leveringsmåte og krav](https://www.skatteetaten.no/bedrift-og-organisasjon/skatt/skattemelding-naringsdrivende/enk/):
ENK med regnskaps-/revisjonsplikt må bruke et system som støtter innsending;
andre kan ha adgang til portalen. Denne appen har ingen skatteinnsending.

[Skattesaldo og næringsgrunnlag](enk-tax-basis.md) beskriver neste leveranse:
prøvd native manuell avskrivning og regnskapsbok, gjenbrukt a/d-saldoberegning,
årlige skattefakta og en rapport som avstemmer mot native resultatregnskap og
saldobalanse. Bokføringen håndteres fortsatt av kjernen. Gruppe a/d for 2026
er et avgrenset omfang; øvrige saldogrupper og personlige skatteopplysninger
skal ikke utgis for å være ferdig automatisert. Se veiledningens konkrete
arbeidsflyt og begrensninger. Hovedplanens punkt 7 er fortsatt åpent.
EHF via SendRegning følger etter ENK-arbeidet.
