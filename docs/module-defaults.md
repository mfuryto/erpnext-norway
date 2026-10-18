# Valgfrie moduler

Bestilt standard for det norske oppsettet:

| Modul i kjernen | Norsk navn | Systemstandard | Meny ved standardoppsett |
| --- | --- | --- | --- |
| Stock | Lager | Deaktivert | Skjult |
| Manufacturing | Produksjon | Deaktivert | Skjult |
| Projects | Prosjekter | Deaktivert | Skjult |
| Quality Management | Kvalitet | Deaktivert | Skjult |

Brukeren skal senere kunne aktivere hver modul gjennom ordinære innstillinger,
med nødvendige administrasjonsrettigheter. Det skal ikke kreve ny installasjon
eller endringer i kildekode. Vanlige brukere skal ikke kunne omgå systemvalget
ved å redigere sin egen modulprofil.

Dette er et produktkrav som skal implementeres og prøves i den norske appen.
Det eksisterende Compose-grunnlaget har fortsatt standard ERPNext; dokumentet
endrer ingen innstillinger på en kjørende server.

## Native grunnlag og dokumentert gap

Frappe 16.52.0 har Module Profile og User.block_modules. Disse styrer navigasjon;
de deaktiverer ikke dokumenttilgang eller funksjoner. Kildens `is_module_visible`
beskriver dette uttrykkelig. Dokumenttilgang håndteres separat av DocPerm, og
Administrator har særskilt tilgang i permission-systemet.

Det er derfor ikke tilstrekkelig å skjule fire arbeidsflater eller fjerne roller
fra den første brukeren. Undersøk native innstillinger og rettigheter først,
og legg bare det manglende reversible systemvalget i ekstern app. Ikke presenter
funksjonen som ferdig før både systembruk og navigasjon er prøvd.

## Avgrensning og bevaring

- Deaktivering skal stoppe bruk av modulfunksjonene, også når de forsøkes gjennom
  direkte lenke, REST eller en vanlig integrasjon. Menyskjuling alene består ikke.
- Bevar regnskap, salg, kjøp, betaling og bank. Grunndata kan tilhøre en teknisk
  modul uten at den valgfrie funksjonen brukes: blant annet må vanlige tjenesteartikler,
  enheter og fakturalinjer fungere selv om Lager er deaktivert. Prøv koblingene før
  hele modulens DocTypes sperres. Ingen nye parallelle registre.
- Lagerbevegelser gjennom faktura og andre dokumenter utenfor lagermenyen må inngå
  i prøven. Et skjult Stock Entry-skjermbilde alene deaktiverer ikke lagerfunksjonen.
- Ingen avinstallasjon, sletting av dokumenter eller nullstilling av innstillinger.
  Aktivering og senere deaktivering skal bevare eksisterende data og brukerens valg.
- Standardene gjelder første oppsett. Oppdateringer skal ikke slå av en modul
  brukeren uttrykkelig har aktivert. Behandle avhengigheter ved aktivering og
  forklar dem; ikke aktiver andre moduler uten at dette fremgår.
- Innstillingen for å aktivere en modul må være tilgjengelig selv om modulens meny
  er skjult. Bruk ordinært innstillingssted, uten ny oppstarts- eller kontrollflate.

## Aksept før levering

1. Nytt syntetisk oppsett: alle fire er deaktivert i systemet og skjult i relevante
   menyer, arbeidsflater og snarveier for både eierbruker og Administrator.
2. Prøv direkte lenke, native REST og relevante dokumenthandlinger. Deaktiverte
   funksjoner skal avvises på serveren med forståelig forklaring. Ta også med en
   bruker som ellers har nødvendige roller, slik at rollefravær ikke skjuler et gap.
3. Opprett og bokfør vanlig tjenestesalg og -kjøp uten lageroppdatering. Prøv tilbud,
   kreditnota, betaling, bankavstemming og standardrapportene.
4. Aktiver én modul om gangen fra innstillingene. Kontroller funksjoner, nødvendig
   tilgang og meny, uten å gi tilgang til andre moduler eller andre foretak.
5. Deaktiver igjen og kontroller at systembruken stoppes og menyen skjules uten
   datatap. Prøv eksplisitt eventuelle koblinger til dokumenter som allerede finnes.
6. Gjenta etter omstart og migrering. Både standardvalg og brukerens senere
   aktiveringer skal bestå. Dokumenter faktisk støttet omfang og åpne avhengigheter.

## Kildegrunnlag

- [Frappe 16.52.0: modulnavigasjon](https://github.com/frappe/frappe/blob/v16.52.0/frappe/utils/modules.py),
  særlig `get_blocked_modules` og `is_module_visible`.
- [Frappe 16.52.0: dokumentrettigheter](https://github.com/frappe/frappe/blob/v16.52.0/frappe/permissions.py),
  særlig `has_permission`.
