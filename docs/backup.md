# Native ERPNext-backup før oppdatering

Fra den eksisterende Compose-mappen:

```sh
python3 scripts/backup-runtime.py
```

Dette gir et kort driftsavbrudd. Skriptet finner det kjørende prosjektet fra
Docker-labels og bruker native `bench backup --with-files --ignore-backup-conf`.
Det oppretter ikke et nytt site, endrer ikke passord eller Frappe-nøkkel og trekker
ikke nye images. Kjør det **før** Compose/images endres ved en oppdatering.
Hvis konfigurert og kjørende image ikke stemmer overens, avvises operasjonen før
skriving stoppes. Det gjøres ingen installasjon eller databaseoppgradering.

## Hva som bevares

- Native databasebackup, offentlige/private filer og site-konfigurasjon.
- Opprinnelig site-konfigurasjon før maintenance mode og common_site_config.json.
- Faktisk privat runtime.env fra deploy/.env og Compose-filen som var i bruk.
- Prosjektnavn, kjørende app-tjenester og image-referanser/-identiteter.
- Privat kommandologg og SHA256SUMS for den eksporterte kopien.

Resultatet ligger i `backups/<tidspunkt-id>/`. Mapper er private med modus 0700,
filer med 0600. Mappen er ignorert av Git. Den inneholder driftshemmeligheter og
skal aldri sendes i chat, inkluderes i repo eller gjøres tilgjengelig som webfiler.
Native backupfiler blir også liggende i sitets private backupmappe.

Manuelle kopier legges under `private/runtime-backups`, utenfor kjernens vanlige
`private/backups`. Dermed får den native oppryddingen fortsatt bare filene den
forventer; ingen native oppryddingsfunksjon erstattes eller overstyres.

`--name` kan angi et unikt navn; eksisterende kopier overskrives aldri. `--root`
kan peke på den eksisterende Compose-mappen dersom skriptet kjøres fra en separat
kopi av verktøyene. Ingen privat konfigurasjon genereres på nytt.

## Rekkefølge og feil

1. Lås runtime-operasjonen og kontroller eksisterende prosjekt og images.
2. Bevar privat konfigurasjon, slå på native maintenance mode og stopp kjørende
   app-tjenester. Innganger og scheduler stoppes først; backend og køarbeidere får
   tid til å fullføre arbeidet. Database og Redis beholdes. Hvis en skrivende
   tjeneste må tvangsdrepes eller en tjeneste ikke stopper, avbrytes backupen.
3. Ta full native backup med det eksisterende imaget og eksporter til privat mappe.
   Kontroller nødvendige filer, databaseidentitet og Frappe-krypteringsnøkkel.
4. Gjenopprett opprinnelig maintenance-tilstand og start de samme app-containerne
   som var i gang. Tidligere stoppede tjenester aktiveres ikke.
5. Skriv manifest og integritetskontroll. En vellykket kjøring avsluttes med
   `Native backup complete` og plasseringen av kopien.

Ved backupfeil forsøkes opprinnelig maintenance-tilstand og tjenestestatus
gjenopprettet. Hvis gjenoppretting av maintenance-tilstanden feiler, åpnes ikke
app-tjenestene automatisk med ukjent tilstand. Undersøk den private loggen lokalt.
Ingen automatisk sletting av gamle kopier, databaseendring eller tilbakeføring
utføres. En mislykket kjøring er ikke en ferdig backup.

## Gjenoppretting og aksept

Den isolerte Compose-testen bruker samme produksjonsverktøy og kontrollerer
tilgangsmodi, konfigurasjon og SHA256SUMS. Deretter endres testdata og Frappe-nøkkelen,
testvedlegg slettes og den opprinnelige native backupmappen fjernes. Gjenoppretting
kjøres med `bench restore` fra den **eksporterte** kopien, fulgt av native migrering.
Bilag, balansert hovedbok, modulvalg, private/offentlige vedlegg og dekryptering av
en syntetisk hemmelighet kontrolleres før HTTP åpnes igjen.

Dette gjelder den låste standardkjernen. Det kvalifiserer ikke en image-oppgradering,
den fremtidige norske appen eller full servergjenoppretting med ekstern proxy.
Oppgraderingsprøve skal bygge på dette og bruke samme native migreringsfunksjoner.
Kopi utenfor serveren og faktisk gjenopprettingsprøve for driftsdata må inngå før
produksjonsaksept. Dette verktøyet endrer ikke eksisterende proxy eller TLS.
