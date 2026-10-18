# Compose og overgang

Dette er et vedvarende, standard ERPNext-miljø. Norsk modul er ikke implementert i
første driftsleveranse. Bruk ikke evalueringsmiljøets syntetiske data, passord eller
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
Den norske modulen tilføyes senere gjennom et låst app-image og migrering.

Første innlogging er `Administrator`. Passordet ligger i den lokale private
`deploy/.env` som `ADMIN_PASSWORD`. Ikke send filen eller passordet i chatten.
Et senere passordbytte i brukergrensesnittet endrer ikke automatisk verdien i filen.

## Portbytte og tilbakeføring

```sh
python3 scripts/cutover-from-dolibarr.py "$LEGACY_DIR"
```

Skriptet finner den faktisk kjørende produksjonsinstallasjonen fra Compose-labels,
ikke fra et antatt container-navn. Det kontrollerer at ERPNext allerede svarer,
stopper gamle webskriv, tar full gammel backup, overtar faktisk publisert HTTP-IP
og port og kontrollerer nytt svar. Til sist stoppes gammel database. Gamle filer,
images og backup beholdes. Ingen `down -v`, volumpruning eller sletting brukes.
Det blir et kort driftsavbrudd mens backup og portbytte skjer.

Feil under overgangen forsøker automatisk å starte den gamle installasjonen igjen.
Ved behov kan samme overgang tilbakeføres senere:

```sh
python3 scripts/cutover-from-dolibarr.py --rollback
```

Dette starter de opprinnelige Compose-tjenestene og stopper ERPNext-frontenden;
ERPNext-data beholdes. Tilbakeføringen flytter ikke data mellom regnskapssystemene.
Den lokale `.cutover.json` er privat driftsstatus, ikke en del av Git.

## Reverse proxy

Eksisterende offentlige URL, TLS og rute mellom proxy og backend videreføres.
Behold faktisk upstream-adresse dersom proxyen kjører på en annen server; ikke
bytt den blindt til localhost. ERPNext må også få videresendt WebSocket Upgrade
for `/socket.io`. Se `deploy/nginx-locations.conf.example` som same-host-eksempel,
og tilpass bare location-delene i eksisterende oppsett. Ikke erstatt TLS-serverblokken.
Kontroller offentlig innlogging, PDF/CSS og Socket.IO etter portbyttet. En lokal
HTTP-kontroll beviser ikke at den separate proxyen er korrekt konfigurert.

## Videre drift

Ikke bytt images automatisk. Videre oppdateringsrutine skal stoppe skriv, ta
full backup av database/site-filer/config, migrere, kontrollere og bevare gammel
versjon for tilbakeføring. En testet restore-rutine for den norske appen er et
ferdigkriterium før regnskapsmessig produksjonsaksept. Redis-kødata erstatter ikke
bilagsarkiv eller hovedbok. Første leveranse har bare prøvd den avgrensede
standardinstallasjonen og portovergangen som beskrevet i testbevisene.
