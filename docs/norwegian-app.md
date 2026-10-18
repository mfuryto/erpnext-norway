# Minimal norsk app: dokumentvern og native numre

Appen `erpnext_norway` utvider ERPNext 16.51.1 / Frappe 16.52.0. Den har ingen nye
regnskapsregistre, nummermotor, filoppbevaring eller arbeidsflater. Hovedbok,
kreditnota, kansellering, private vedlegg og nummerserier er de eksisterende.
Norsk regnskapsmessig produksjonsaksept er fortsatt avgrenset av de øvrige gapene
[minimumsplanen](core-minimum.md) beskriver.

## Dokumenterte gap og minste tilpasning

| Påvist native gap | Løsning |
| --- | --- |
| Lagret fakturakladd kan slettes etter at neste nummer finnes | Bevar Sales Invoice, også kladder. Omdøping og bytte av foretak/returtype etter lagring avvises. |
| Native amendment gir suffiks før nummereringsregelen | Ny faktura/kreditnota med eksisterende nummerserie brukes; amendment av Sales Invoice avvises. Kansellert original beholdes. |
| Beskyttet vedlegg kan frakobles, bytte URL eller gjøres offentlig | Før validering kontrolleres lagret referanse og filidentitet på bokførte/kansellerte regnskapsbilag. |
| Native sletting tillates på kansellert dokument | En kooperativ Frappe-utvidelse avviser før den native metoden kan fjerne filen. |
| Native filskriving kan skje før validering | Kontroller før native save_file, også ved delt fil-URL. Selve lagringen delegeres til kjernen. |
| Kansellert regnskapsbilag kan slettes | Bevar kansellerte salgs-/kjøpsfakturaer, bokføringsbilag og betalingsregistreringer. |
| Bokmålskatalogen mangler eller bruker misvisende regnskapsbegreper | Målrettede nb.csv-rettelser med native oversettelseskontekst; API-felt og statusverdier beholdes. |
| En senere utskrift er en ny rendering, ikke bevart PDF ved innsending | Lagre privat native File fra native get_print i on_submit; ingen egen arkivtabell eller utskrifts-API. |

Standardegenskapen `protect_attached_files` slås på for Sales Invoice,
Purchase Invoice, Journal Entry, Payment Entry og innsendte tilbud med native Property Setter.
Den brukes direkte for vern av vedlegg på bokførte dokumenter. Nye vedlegg kan
fortsatt legges til, og feil vedlegg på en kladd kan korrigeres med native File.

Vanlige hendelser brukes for validering og omdøping. `File.on_trash`-hendelsen
kommer etter kjernens fysiske sletting, så den kan ikke beskytte filen i forkant.
Derfor brukes Frappe 16 sitt `extend_doctype_class`, som kontrollerer det påviste
gapet før `super()`. Ingen `override_doctype_class`, kopiert File-kontroller eller
alternativ filmappe brukes. Den samme forsiktigheten gjelder direkte filskriving
som skjer før validering. Referansedokumentets native radlås brukes ved kontrollen.

## Native nummeroppsett

På tomme registre uten eksisterende navngivingsregler opprettes native
Document Naming Rules: F/K/T med seks sifre og separate femsifrede kunde- og
leverandørkoder. Ingen reelle foretak, kontoer eller bilag opprettes av appen.
Et brukt register eller eksisterende regel overtas ikke automatisk.

System Manager kan velge prefiks og sist brukte nummer **før registeret tas i bruk**.
For kode uten prefiks brukes native `.`. Brukte appserier kan ikke nullstilles,
endres, slettes, omdøpes eller overstyres med en ny konkurrerende regel gjennom
vanlig dokument-API. Kjernen øker telleren selv og beholder sin transaksjonelle
radlås. Samtidige transaksjoner kan få en native konflikt; et nytt lagringsforsøk
etter tilbakerulling skal bevare sekvensen. Ingen egen teller eller utstedelsesjournal legges til. Native Data Import med angitt
fakturanummer avvises når appens salgsserie finnes; et importnavn skal ikke omgå serien.

En lagret ubrukt fakturakladd beholdes som kladd med sitt nummer. Bruk native
kommentar for å forklare hvorfor den ikke fullføres. En allerede brukt ekstern
serie må vurderes før eventuell overgang til appens standard; appen gjetter
ikke startnummer eller endrer eksisterende identifikatorer.

## Bygging og oppdatering

`bash scripts/build-app-image.sh` bygger på det låste ERPNext-imaget og skriver
ett uforanderlig lokalt image-ID på standard output. Byggeloggen går til stderr. Hver bygd versjon får også et lokalt innholdstag,
slik at vanlig opprydding av navnløse images ikke fjerner forrige appversjon.
Bare appen og et versjons-/hashlåst standard byggverktøy tilføyes; kjernens
avhengigheter oppgraderes ikke. Byggekonteksten utelukker driftsdata og hemmeligheter.

Fra eksisterende Compose-mappe:

```sh
git fetch origin main
git switch main
git merge --ff-only origin/main
app_image=$(bash scripts/build-app-image.sh)
python3 scripts/update-runtime.py --image "$app_image"
```

Verktøyet beholder Compose-prosjekt, data, passord, port og Frappe-nøkkel. Det
krever ett kjørende backend-prosjekt i arbeidsmappen og kontrollerer at konfigurert
og kjørende image stemmer før backup. Det tar privat full native backup **før**
`ERP_APP_IMAGE` skrives i eksisterende `deploy/.env`. Andre verdier bevares.

Tjenestene holdes stoppet under installasjon/migrering. Native `install-app` og
`migrate` brukes. Deretter gjenopprettes maintenance-tilstanden, de tidligere
kjørende app-tjenestene opprettes med det lokale imaget og native helsekontroller
avventes. Ingen pull, ny site, passordgenerering eller endring av proxy inngår.
Database/Redis byttes ikke. Standard Compose uten `ERP_APP_IMAGE` bruker fortsatt
den opprinnelige kjernen.

Ved feil før migrering kan opprinnelig runtime gjenopptas. Etter at migrering er
forsøkt, holdes app-tjenestene stoppet med maintenance på. En eldre versjon åpnes
aldri automatisk mot en muligens migrert database. Se den private `update.log`
og originalbackupen lokalt; ikke send dem i chat. Gjenoppretting må bruke native
restore sammen med backupens image, konfigurasjon og nøkkel, slik integrasjonsprøven
beskriver. Selve backupen har SHA256SUMS; den senere update.log inngår ikke i den
allerede forseglede filoversikten.

## Omfang og grenser

Dette er vern gjennom støttede dokument-/filgrensesnitt. Direkte database- eller
filsystemskriving, endring av appkode eller avinstallasjon utført av en teknisk
administrator ligger utenfor grensen. Historiske manglende eller allerede endrede
vedlegg gjenskapes ikke. Eksterne URL-er er ikke en bevart kopi av et originalbilag. App 0.2.0 bevarer også PDF ved innsending som et vanlig privat vedlegg;
se [dokumentmaler og avgrensninger](sales-documents.md).
Tilgangsstyring og kopi utenfor serveren må fortsatt ivaretas.

Appens vernmeldinger og målrettede rettelser i regnskapsflyten bruker native CSV.
Norske/engelske dokumentmaler og faktisk skjermprøve er beskrevet i språk- og
dokumentaksepten. Videre språkfunn følger de senere funksjonsområdene.
Ingen generell påstand om norsk etterlevelse følger av denne leveransen.

## Norsk kontoplanmal

[Norsk kontoplan](norwegian-chart.md) inngår som vanlig mal ved selskapsoppretting.
Nye Norway/NOK-selskaper får den som standard når ingen annen mal er valgt; eksisterende
selskaper og eksplisitte valg beholdes. Alle 745 kontonumre og navn kommer fra samme
lisensierte kilde som CSV-eksporten. Native create_charts og trevisning brukes direkte.
Den smale Company-utvidelsen er nødvendig fordi kjernen bare søker maler i egen
pakke og ikke tilbyr et provider-hook. Imagebyggingen legger derfor en referanse
til appens datafil i den native malkatalogen. Ingen eksisterende kjernefiler endres.
