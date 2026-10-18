# Aksept for driftsgrunnlaget

Dette gjelder standard ERPNext 16.51.1 / Frappe 16.52.0, ikke en ferdig norsk app.
Kontrolleres før promotering til main:

- Ny installasjon med tilfeldige private passord og separate mapper for database,
  site-filer, kø og logger. Ingen gamle databaser eller evalueringsdata gjenbrukes.
- Native site og HTTP API svarer, og Socket.IO polling går gjennom frontend.
- Socket.IO WebSocket Upgrade gir HTTP 101 og korrekt handshake gjennom Compose-
  frontend. Dette gjelder ikke den eksterne reverse proxyen.
- Restart bevarer site-lagring og Frappe-krypteringsnøkkel.
- Native norsk modulprofil viser Lager og skjuler Produksjon, Prosjekter og Kvalitet som
  standard. Ny bruker arver profilen, senere personlige/delte valg bevares, og
  dokumentrettigheter endres ikke. Se [modulvisning](module-defaults.md).
- Native PDF-renderer lager en PDF fra syntetisk HTML. Dette kvalifiserer ikke
  fakturamal, språk, CSS, brevark eller dokumentkrav.
- Full native backup med database, offentlige/private filer og site-konfigurasjon
  gjenopprettes etter endring av syntetisk databaseinnhold og sletting av testfiler.
  Innsendt bilag, hovedbok og filkoblinger kontrolleres, samt dekryptering av en
  syntetisk hemmelighet med bevart nøkkel. Native migrering og HTTP prøves etterpå;
  offentlig testfil skal svare, mens privat testfil fortsatt skal avvise gjest.
- Serververktøyet for native backup brukes i samme prøve. Privat Compose-konfigurasjon,
  filmodi, SHA256SUMS og opprinnelig tjenestestatus kontrolleres. Gjenopprettingen
  bruker den eksporterte kopien etter sletting av kildebackup og endring av testnøkkel.
- Tre isolerte kontraktstester av portbytte: riktig rekkefølge og bevarte ERPNext-
  passord, avvisning før stopp når ny tjeneste ikke svarer, og oppstartsfeil uten
  ubestilt backup eller tilbakeføring.
- Ingen reell server er automatisk byttet fra utviklingsmiljøet.
- Privat URL overføres bare på serveren. Ingen driftshemmeligheter eller private
  konfigurasjonsfiler publiseres. Lokal evalueringsrapport/bevis ligger ignorert.

Kontraktstestene er ikke en faktisk prøve mot en bestemt servers gamle installasjon.
Porten oppdages der skriptet kjøres. Ekstern proxy, WebSocket Upgrade, PDF-ressursvei,
foretaksoppsett og vanlig eierbruker skal kontrolleres etter oppstart på faktisk server.
Gjenopprettingsprøven kjøres bare i en ny, isolert syntetisk fikstur gjennom
`tests/runtime-smoke.sh`. Den er ikke en gjenoppretting av serverens data, prøve av
en ny image-versjon eller kvalifisering av den fremtidige norske appen. Backup av
privat driftskonfigurasjon, separat lagring, full servergjenoppretting,
oppdateringsflyt og norsk regnskapsaksept skal fullføres videre i dette prosjektet.
Ingen automatisk skatteinnsending, SAF-T eller EHF hevdes
levert av dette driftsgrunnlaget. EHF og samlet sluttkontroll følger planen.
