# Skattesaldo og næringsgrunnlag

## Kravet og hvorfor kjernen ikke er tilstrekkelig

ERPNext 16.52.1 har driftsmidler, regnskapsbøker, redigerbar manuell
avskrivningsplan og ordinære avskrivningsbilag. Disse skal brukes til
bokføringen. Ingen av dem inneholder norske skattemessige samlesaldoer:
flere driftsmidler i gruppe a eller d skal behandles samlet, salg reduserer
saldo med vederlaget, og negativ saldo gir skattepliktig inntekt.
En regnskapsbok per driftsmiddel erstatter ikke denne skatteposisjonen.

Prøve av kjernens Written Down Value med kjøp 100 000 den 1. desember,
30 prosent og første avskrivning 31. desember gir 2 547,95 første år.
Den proraterer og avslutter dessuten planen etter valgt levetid. Norske
saldoregler har andre forutsetninger. Faktisk kjøpsdato skal beholdes.
Manuell plan skal prøves med lagring, aktivering, bokføring og kansellering
før den brukes som anbefalt bokføringsvei.

Tilleggets avgrensede gap er derfor skatteopplysninger for året og en
avstemming mot kjernens resultatrapport og saldobalanse. Skatteopplysningene
er ikke bilag, en hovedbok eller en ny årsavslutning. Beregnede tall skal
leses fra de aktuelle kildene ved rapportkjøring, ikke lagres som kopier.
Fakturaer, kreditnotaer, betalinger, avskrivningsbilag og avslutningsbilag
skal fortsatt registreres på ERPNexts vanlige arbeidssteder.

Omfanget er ett ENK uten ansatte, NOK og kalenderåret 2026. Rapporten gir
årsgrunnlag til utfylling i Skatteetatens portal. Den omfatter samlesaldo a–d,
individuelle saldoer e–i og tekniske installasjoner j per bygg, gevinst-/tapskonto,
dokumenterte øvrige forskjeller, personinntektsgrunnlag og skatte-/formuesverdier.
Ingen full personlig skatteberegning eller innsending er innført. Særnæringer,
flere virksomheter og omdanninger er ikke generelt automatisert. En programvarelisens
er ikke automatisk saldogruppe a; tidsbegrensede rettigheter kan behandles utenfor saldo.
Se [sluttføring og faglige forutsetninger](enk-completion.md).

## Kilder og gjenbruk

- [Skatteetatens avskrivningssatser](https://www.skatteetaten.no/satser/avskrivningssatser/).
- [Skatte-ABC, avskrivningsgrunnlag](https://oppslag.rettskilder.skatteetaten.no/rettskilder2/type/handboker/skatte-abc/gjeldende/skatteabc-D-2/skatteabc-D-2.087).
- [Skatte-ABC, negativ saldo](https://oppslag.rettskilder.skatteetaten.no/rettskilder2/type/handboker/skatte-abc/gjeldende/skatteabc-D-2/skatteabc-D-2.105/skatteabc-D-2.151).
- [Skatteloven §§ 14-40–14-48](https://lovdata.no/lov/1999-03-26-14/§14-40).
- [Altinn om bokførte og skattemessige avskrivninger](https://info.altinn.no/starte-og-drive/regnskap-og-revisjon/regnskap/avskrivning/).

Den rene a/d-saldoberegningen gjenbrukes fra
[ENK Norge, revisjon 94406e5](https://github.com/Medpus/enk_norge/blob/94406e542ed991a8de237b9de44b8d1dd576b566/enk_norge/norway_rules.py)
med MIT-lisens og navngitt opphav. Øvrige grupper og gevinst-/tapskonto følger de dokumenterte norske reglene. Personinntektens uavhengige aritmetikk gjenbrukes fra samme revisjon; brutto renteavgrensning og dokumentert nettoskjerming holdes adskilt. Prosjektets egne årsrapporter,
historikkregistre, bokføringsgeneratorer og kontrollflater overtas ikke.

## Arbeidsflyt

1. Bruk **Driftsmiddelkategori**, vanlige **Vare**-innstillinger og
   **Leverandørfaktura/Varemottak** for kjøpet. Velg riktig balansekonto for
   driftsmiddelet. Utstyr som skal inngå i ulike skattesaldoer må kunne skilles
   med lagrede driftsmiddel-/innkjøpsreferanser eller bokførte kontoer. Ikke endre historiske vare-/kategoridata for å
   omskrive allerede bokførte kilder.
2. Bruk **Driftsmiddel → Avskrivningsplan** for bokføringen. Den manuelle
   planen kan redigeres med dato og beløp før aktivering. Behold faktiske
   kjøps-/tilgjengelighetsdatoer og en fornuftig bokført plan. Kjernen lager
   bilagene og håndterer kansellering. Skatteavskrivningen skal ikke bokføres
   en gang til bare fordi rapporten viser en forskjell.
3. Åpne **Norske skatteopplysninger** (`Norwegian Tax Facts`) i vanlig søk.
   Opprett ett dokument for foretak/år. Legg inn én samlesaldo per gruppe a–d,
   med en balansekonto eller en kontogruppe som bare inneholder aktuelle
   anleggsmiddelkontoer. Flere konti i samme saldo håndteres med kjernens
   kontotre. For e–i velges ett nativt driftsmiddel (antall én) per saldo.
   Flere individuelle saldoer kan bruke samme konto når de har ulike entydige
   driftsmiddelreferanser. For j brukes én saldo per bygg, med dokumentert
   byggidentifikasjon og egne kontoer/kontogrupper for byggets installasjoner.
   En valgfri driftsmiddelreferanse i j må representere hele den aktuelle enheten,
   ikke opprette flere saldoer for enkeltkomponenter i samme bygg.
4. Oppgi faktisk inngående **skatteverdi** fra forrige skatteoppgjør med
   dokumentasjon; ikke kopier automatisk bokført nettoverdi. Nytt foretak
   uten tidligere saldo bruker null med forklaring. Dokumenter også negativ
   inngående saldo. Bruk vanlige vedlegg på skatteopplysningsdokumentet.
5. Maksimal avskrivning er standardvalg. Et lavere beløp kan velges.
   Positiv restsaldo under 30 000 før årets avskrivning kan velges
   fradragsført helt eller delvis; dette gjelder ikke ved nøyaktig 30 000.
   Negativ a/c/d/j-saldo under 30 000 skal inntektsføres helt; ellers minst gruppens
   sats, med adgang til større inntektsføring. Ved realisasjon av e–i overføres
   gevinst/tap uten årets saldoavskrivning. Negativ b ved årsslutt overføres
   også til gevinst-/tapskonto. Gevinstkonto gir minst 20 prosent inntekt, tapskonto
   høyst 20 prosent fradrag. Under 30 000 er gevinst pliktig helt inntektsført,
   mens tap kan velges helt fradragsført. Inngående gevinst-/tapskonto og valgene
   dokumenteres i samme årsopplysninger. Direkte inntektsført
   salgsvederlag er et uttrykkelig årsvalg, ikke en ny salgsfaktura.
6. **Øvrige skattekorreksjoner** kan bruke en faktisk kostnadskonto og andel
   uten skattefradrag. Beløpet følger da kjernens resultatrapport, inkludert
   kreditnotaer. Del kontoer i kjernen når en konto blander forskjellige
   skattebehandlinger. Alternativt oppgis en dokumentert årlig forskjell med
   positivt tillegg eller negativt fradrag. Oppgi begrunnelse og underlag.
   En privatandel som allerede er ført mot egenkapital skal ikke legges til
   på nytt her. Dette er årlige skattefakta, ikke manuell etterbehandling av
   ordinære fakturaer.
7. Kjør **Norsk ENK-grunnlag** fra knappen eller rapportlisten. Avstem
   bokført resultat, avskrivninger, driftsmiddelsalg, skattefradrag,
   inntektsført saldo og øvrige forskjeller. Rapporten viser også bokført
   nettoverdi, skattesaldo og differansen. Negativ skattesaldo er en senere
   inntektsføring, ikke en negativ gjenstand i driftsmiddelregisteret.

Regnskapsbruker kan lese grunnlaget; regnskapsansvarlig kan endre skattefakta.
Foretaksbegrensninger og kildenes vanlige leserettigheter gjelder. Rapporten
oppretter ingen bilag og endrer ikke de lagrede kildene. Endringer i årets
fakturaer, kreditnotaer og kanselleringer krever ny rapportkjøring. Det finnes
ikke en egen «godkjent/levert»-status som kan skjule endringer i grunnlaget.

## Resten av næringsopplysningene

| Opplysning | Eksisterende kilde og behandling |
| --- | --- |
| Omsetning, kjøp, øvrige kostnader og renter | Kjernens resultatregnskap. Faktiske periodiseringer og korrigeringer føres som ordinære bilag. Salgsvarer/lisenser for videresalg er ikke automatisk egne avskrivbare driftsmidler. |
| Varelager og ukurans | Behold native lager, opptelling/avstemming og lagerverdirapport der varer lagerføres. En skattemessig forskjell skal dokumenteres; ikke bygg en annen lagerbok. |
| Bank, fordringer og gjeld | Native bankavstemming, kunde-/leverandørreskontro, balanse og saldobalanse. Tapsføring krever sine egne faktiske vilkår og dokumentasjon. |
| Eieruttak, innskudd og personlig skatt | Ordinære egenkapitalkonti og bilag som beskrevet i [ENK-veiledningen](enk-year-end.md). Kontantuttak endrer ikke næringsresultatet. Uttak av varer/driftsmidler krever særskilt vurdering av omsetningsverdi og skatt/MVA. |
| Private andeler, representasjon og andre begrensede fradrag | Registrer kjøpet korrekt i kjernen. Bruk bokført privat korreksjon eller en dokumentert skatteforskjell, med avstemming som hindrer dobbelt tilbakeføring. Kontonummer alene beviser ikke fradragsrett. |
| Telefon/bredbånd, hjemmekontor, privat bil og pensjon | Faktiske vilkår og årets satser må dokumenteres. Appen gjetter ikke privat bruk, tilgjengelighet hos arbeidsgiver, kontorvilkår, kjørelengde eller rett til pensjonsfradrag fra et fakturabeløp. Opplysninger utenfor næringen føres ikke som oppdiktet næringskostnad. |
| Beregnet personinntekt og skjerming | Næringsresultatet er bare utgangspunkt. Kapitalinntekter/-kostnader, gjeldsrenter, skjermingsgrunnlag og fremført negativ personinntekt må behandles etter foretaksmodellen. Bokført bankinnskudd eller årsresultat alene er ikke en personlig skatteberegning. |
| Skattemessige formuesverdier og personlige opplysninger | Avstem mot eiendeler/gjeld og gjeldende verdsettingsregler. Bokført nettoverdi og skattesaldo er ikke automatisk den personlige formuesverdien. |
| Innsending | Appen har ikke skatteinnsending. Bruk Skatteetatens tilgjengelige leveringsmåte eller et system som faktisk støtter foretakets innsendingsplikt; SAF-T er ikke skattemeldingen. |

[Skatteetatens næringsspesifikasjon og leveringsmåter](https://www.skatteetaten.no/bedrift-og-organisasjon/skatt/skattemelding-naringsdrivende/enk/)
og [foretaksmodellen](https://www.skatteetaten.no/rettskilder/type/handboker/skatte-abc/2025/e-5-enkeltpersonforetak--beregnet-personinntekt-foretaksmodellen/)
er kildene for skillet mellom næringsresultat og personlige opplysninger.
Årsrapporten bruker offisiell ENK-postliste for 2026, adskilt fra SAF-T.
Standardkoblinger gjelder bare eksakt opprinnelig kontonummer/navn/hovedgruppe.
Egne koblinger settes i **Konto → Næringspost for norsk ENK**, med inntektsår.
Brukte ukoblede kontoer vises med faktisk beløp og beskjed om vurdering; de utelates ikke.
Offisielle poster vises med postens fortegn. Kontodetaljene beholder debet minus kredit.
Næringspostene er bokførte beløp; skattekorreksjonene står separat i resultatavstemmingen.
De er ikke en ferdig XML-/API-innsending av næringsspesifikasjonen.

### Andre balanseposter, personinntekt og formue

- I **Skatte- og formuesverdier** velges vurderte bokverdier eller dokumenterte
  skatteverdier for IB/UB. Beløp følger kontodetaljenes debet minus kredit.
  For andre eiendeler/gjeld, eksempelvis dokumentert varelager-/fordringsforskjell,
  kan **Ta med endring i skatte-/bokført verdiforskjell i næringsresultatet** velges.
  Rapporten bruker årets endring i forskjellen, ikke hele utgående forskjell.
  Skattesaldoer/akkumulerte avskrivninger kan ikke få samme resultatkorreksjon igjen.
- Tomter og andre eiendeler utenfor saldogruppene velges uttrykkelig som
  **Driftsmiddel utenfor skattemessige saldogrupper**, med vurdert skatteverdi,
  dokumentasjon og årets dokumenterte skattefradrag (null for ikke-avskrivbar tomt).
  Bruk native manuell avskrivningsplan/ordinære bilag til den faktiske bokføringen;
  ikke opprett en parallell plan i appen. Dokumentert fradrag trekkes i skattebroen.
- Formuesverdi velges som vurdert skatteverdi, dokumentert verdi eller uttrykkelig
  ikke formuesskattepliktig. Verdier er **før rabatt**. Appen bruker ingen ny
  personlig formuesskatte-/gjeldsreduksjonsmotor. Tomt/formuesverdi følger sine
  faktiske verdsettingsregler og er ikke automatisk lik anskaffelseskost.
- **Utarbeid personinntektsgrunnlag** krever dokumentert brutto kapitalgrunnlag
  før all gjeld, netto skjermingsgrunnlag, kvalifiserende foretaksgjeld, kapitalposter
  og fremført negativ personinntekt. Kontovalg henter årets native resultat etter
  allerede utførte kontokorreksjoner. Dokumenterte årsbeløp brukes for forhold som
  ikke har en entydig konto. Tap på kundefordringer skal ikke tilbakeføres som
  kapitalkostnad. Renteavgrensningen gjelder bare kvalifiserende foretaksgjeld til
  finansinstitusjon/mengdegjeldsbrev, ikke automatisk all leverandørgjeld.
- Skjermingen er dokumentert årsbeløp eller et uttrykkelig valg om ikke å kreve
  fradrag. Uvurdert skjerming med positivt nettogrunnlag gir ingen ferdig
  personinntektsberegning. Ingen 2025-/aksjonærrente brukes som antatt 2026-rente.
  Negativ personinntekt og brukt/gjenstående fremføring vises separat.
- Standardkontoene 7799, 7835 og 7825 får sin uttrykkelige skattebehandling ved
  eksakt opprinnelig identitet. En egen prosentkorreksjon på kontoen har forrang.
  Privatandel som allerede reduserer bokført kostnad, legges ikke tilbake igjen.
  Native 2068 mot telefonkostnad vises som brutto 6995 og privatpost 6998 når
  årets faktiske bilagslinjer avstemmes entydig. Appen beregner ikke privatbruk
  eller rett til andre fradrag ut fra en faktura.

Rapporten viser uavklarte koblinger, skatteverdier, formuesverdier og personinntekt.
Årets faktiske opplysninger og privat underlag må fylles ut før innlevering.
Manglende fakta er ikke null. Rapporten oppretter ingen egen godkjenningsstatus.
Bruk standard rapporteksport/utskrift og vanlige private vedlegg på årsopplysningene.

## Kvalifiseringsgrense for kilder

Det nye grunnlaget leser årets faktiske standardbok. Kjøp/mottak og
landed-cost-kilder kan bare brukes når de faktisk har postert på valgte
anleggsmiddelkontoer. Fakturering av et tidligere mottak skal ikke legge til
kostnaden på nytt. Native salg og utrangering bruker kjernens faktiske kilder, også ved null
bokført nettoverdi. Ordinære manuelle driftsmiddelbilag bruker feltet
**Skattemessig driftsmiddelbevegelse** på bilagslinjen før bokføring: ny tilgang,
kostkorreksjon, skattenøytral overføring, avgang eller bokført gevinst/tap.
Angi dokumentert realisasjonsverdi uten MVA ved avgang og native driftsmiddelreferanse
for individuelle saldoer. Ingen ekstra bokføringsknapp eller bilagsgenerator innføres.
Umerkede manuelle kilder avvises i skattesaldoen. Rett gjennom ordinær native
kansellering/amendering; bokførte skattefelt er ikke redigerbare.
Grensekryssende omdanning, generelle virksomhetsoverdragelser og spesialregimer
må fortsatt vurderes særskilt. Rapporten skal stoppe ved ukjent kilde; den skal ikke
anta at enhver debet på en balansekonto er et skattemessig kjøp.

Den låste kjernen kan slå sammen salgets hovedboksposter og fjerne
fakturalinjereferansen. Flere driftsmidler i **samme skattesaldo** kan fortsatt
behandles samlet fra den faktiske kilden. Salg fra flere skattesaldoer på én
faktura knyttes gjennom valgte driftsmidler eller lagrede innkjøps-/kontoreferanser; dagens kategoristandard er ikke historisk bevis. Vanlig salg og driftsmiddelsalg
kan stå på samme faktura når de bokførte gevinst-/tapskontoene er entydig skilt
fra øvrige salgslinjer og gebyrer. Det skal ikke gjettes en gevinstfordeling.

Bruk riktige native kontotyper. MVA-grunnlagskonti er ikke avskrivbare
anleggsmidler selv om de ligger i kontoklasse 1. Kontogrupper følger kjernens
kontotre; endres treet eller kontoavgrensningen, må årets skatteopplysninger
avstemmes på nytt. Rapporten bruker ikke dagens vare-/kategoristandarder til
å skrive om bokførte kontoer eller avgangsbeløp.

Skatteavskrivning opprettes ikke som en alternativ regnskapsbok automatisk.
Native Finance Book er prøvd med egen avskrivningspostering, og native
standardbokrapporter skiller den ut. Den løser likevel ikke samlesaldo,
negativ saldo eller dokumentert inngående skatteverdi. SAF-T-kvalifiseringen
omfatter heller ikke slike alternative bokposteringer.

## Konkrete native avvik ved tilleggskostnader

Prøven av direkte driftsmiddelkjøp på 100 000 + 25 000 MVA, med 50 prosent
fradrag og løpende lagerregnskap slått av, ga driftsmiddelverdi 112 500,
men bare 100 000 på anleggsmiddelkonto og 12 500 på verdsettingskostnadskonto.
Kjernens innkjøpsfaktura bruker `auto_accounting_for_stock` også for denne
aktiveringen. Landed-cost bruker den samme reposteringen; å lage en ekstra
LCV erstatter derfor ikke den manglende native innstillingen.

Løsningen er den eksisterende innstillingen **Løpende lagerregnskap**
(Enable Perpetual Inventory) og nødvendige native verdsettings-/mottakskontoer
på foretaket. Ikke-lagerførte varer/lisenser blir fortsatt ikke lagerført av
denne innstillingen alene. Appen skal ikke endre foretakets valgte lagermetode
automatisk, opprette ekstra kostnadsbilag eller skjule forskjellen i
skatterapporten. Nye driftsmiddelkjøp/-mottak og landed-cost med slike
aktiveringsbeløp skal avvises før bokføring i den ukvalifiserte kombinasjonen.
Tidligere direkte kilder med avvik mellom lagret verdsetting og faktisk
anleggsmiddelpostering må avstemmes gjennom vanlig rettingsflyt.

For eiendeler utenfor saldo må eventuell forskjell mellom bokført og skattepliktig
gevinst/tap dokumenteres i de ordinære årsjusteringene. Native salg med samme
bokførte og skattemessige kost beholder kjernens resultat. En bokført nullverdi
utelukker ikke en gjenværende dokumentert skatte-/formuesverdi; slike årsverdier
vises også uten årets hovedboksbevegelse. Kjent standardkonto for tomt kan ikke
velges som en saldoavskrivbar konto.

Sammenligningen «bokført nettoverdi minus skattesaldo» omfatter også andre
verdiforskjeller, blant annet eiendeler utenfor saldo. Den er ikke alene
avstemmingen av alle skatte-/formuesverdier; bruk de separate kontokolonnene.
