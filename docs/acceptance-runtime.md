# Aksept for driftsgrunnlaget

Dette gjelder standard ERPNext 16.51.1 / Frappe 16.52.0, ikke en ferdig norsk app.
Kontrolleres før promotering til main:

- Ny installasjon med tilfeldige private passord og separate mapper for database,
  site-filer, kø og logger. Ingen gamle databaser eller evalueringsdata gjenbrukes.
- Native site og HTTP API svarer, og Socket.IO polling går gjennom frontend.
- Restart bevarer site-lagring og Frappe-krypteringsnøkkel.
- Tre isolerte kontraktstester av portbytte: riktig rekkefølge og bevarte ERPNext-
  passord, avvisning før stopp når ny tjeneste ikke svarer, og oppstartsfeil uten
  ubestilt backup eller tilbakeføring.
- Ingen reell server er automatisk byttet fra utviklingsmiljøet.
- Privat URL overføres bare på serveren. Ingen driftshemmeligheter eller private
  konfigurasjonsfiler publiseres. Lokal evalueringsrapport/bevis ligger ignorert.

Kontraktstestene er ikke en faktisk prøve mot en bestemt servers gamle installasjon.
Porten oppdages der skriptet kjøres. Ekstern proxy, WebSocket Upgrade, PDF-ressursvei,
foretaksoppsett og vanlig eierbruker skal kontrolleres etter oppstart på faktisk server.
Full ERPNext backup/restore, oppdateringsflyt og norsk regnskapsaksept skal fullføres
videre i dette prosjektet. Ingen automatisk skatteinnsending, SAF-T eller EHF hevdes
levert av dette driftsgrunnlaget. EHF og samlet sluttkontroll følger planen.
