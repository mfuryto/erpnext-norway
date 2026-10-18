# Compose og overgang

Dette er et vedvarende, standard ERPNext-miljø. Den [minimale norske appen](norwegian-app.md)
installeres separat gjennom den kvalifiserte oppdateringsrutinen. Bruk ikke evalueringsmiljøets syntetiske data, passord eller
site-filer. Det leveres ingen automatisk flytting av Dolibarr-databasen til ERPNext.

## Ny installasjon ved siden av eksisterende

Fra prosjektets rot, med `LEGACY_DIR` satt til den eksisterende installasjonen:

```sh
python3 scripts/init-runtime.py --from-dolibarr "$LEGACY_DIR"
bash scripts/prepare-runtime.sh
```

Dette leser bare offentlig URL fra gammel privat konfigurasjon, oppretter nye
private passord og starter ERPNext på `127.0.0.1:18088`. Andre ledige porter kan
velges med `--port`. Eksisterende `deploy/.env` overskrives ikke. Uten gammel
installasjon brukes `--url` med den faktiske offentlige URL-en.

Data ligger i `data/database`, `data/sites`, `data/logs` og `data/redis-queue`.
Site-navnet er internt `accounting`, uavhengig av offentlig vertsnavn. Frappe sitt
databasepassord og krypteringsnøkkel opprettes i site-konfigurasjonen og må bevares
sammen med databasen og dokumentene ved restore. Git inneholder ikke disse filene.
Den norske appen tilføyes gjennom et låst app-image og native migrering.

Første innlogging er `Administrator`. Passordet ligger i den lokale private
`deploy/.env` som `ADMIN_PASSWORD`. Ikke send filen eller passordet i chatten.
Et senere passordbytte i brukergrensesnittet endrer ikke automatisk verdien i filen.

## Portbytte

```sh
python3 scripts/cutover-from-dolibarr.py "$LEGACY_DIR"
```

Skriptet finner den eksisterende produksjonsinstallasjonen fra Compose-labels,
kontrollerer at ERPNext allerede svarer, stopper Dolibarr og overtar den lagrede
HTTP-IP-en og porten. Eksisterende Dolibarr-filer og eventuelle gamle backupfiler
blir liggende. Det tas ingen ny backup av Dolibarr, og det er ingen automatisk
eller separat tilbakeføringsfunksjon. Sletting av data inngår ikke i overgangen.
Ved oppstartsfeil stopper kommandoen med feil; eventuell videre håndtering tas da.
Det blir et kort driftsavbrudd mens porten byttes.

## Reverse proxy

Eksisterende offentlige URL, TLS og rute mellom proxy og backend videreføres.
Behold faktisk upstream-adresse dersom proxyen kjører på en annen server; ikke
bytt den blindt til localhost. ERPNext må også få videresendt WebSocket Upgrade
for `/socket.io`. Se `deploy/nginx-locations.conf.example` som same-host-eksempel,
og tilpass bare location-delene i eksisterende oppsett. Ikke erstatt TLS-serverblokken.
Kontroller offentlig innlogging, PDF/CSS og Socket.IO etter portbyttet. En lokal
HTTP-kontroll beviser ikke at den separate proxyen er korrekt konfigurert.

## Videre drift

### Modulvisning på eksisterende installasjon

`deploy/module-visibility.py` kan kjøres med backend-containerens Python og skriptet
på standard input. Vanlig appoppdatering kjører nå tilbakeføringen automatisk.
Det bruker det eksisterende sitet og native Module Profile /
User-innstillinger; ingen ny site-oppretting, image-oppdatering eller restart inngår.
Finn det eksisterende Compose-prosjektnavnet før kjøring. Se
[modulvisning](module-defaults.md) for hvilke brukere som endres og hvordan moduler
vises igjen. Endringer i menyer krever at brukeren laster inn skrivebordet på nytt.

### Oppdateringer og sikkerhetskopi

Ta [full native backup](backup.md) med `python3 scripts/backup-runtime.py` før
runtime-konfigurasjon/images oppdateres. Verktøyet inkluderer privat Compose-
konfigurasjon og starter de samme tjenestene igjen etter native backup.

Bruk [appens oppdateringsrutine](norwegian-app.md) for det særskilt bygde, låste
app-imaget. Den stopper skriv, tar full backup av database/site-filer/config,
installerer/migrerer med kjernen og kontrollerer helse. Ikke bytt øvrige images automatisk. En testet restore-rutine for den norske appen er et
ferdigkriterium før regnskapsmessig produksjonsaksept. Redis-kødata erstatter ikke
bilagsarkiv eller hovedbok. Den isolerte driftstesten prøver standardinstallasjon,
WebSocket Upgrade, PDF-rendering og native backup/gjenoppretting med etterfølgende
migrering. Se [driftsaksept](acceptance-runtime.md) for avgrensninger; testen
erstatter ikke backup/gjenoppretting av faktisk drift eller den kommende norske appen.
