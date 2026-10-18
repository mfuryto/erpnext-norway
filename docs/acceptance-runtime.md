# Aksept for driftsgrunnlaget

Baseline gjelder standard ERPNext 16.51.1 / Frappe 16.52.0. Den separate
appprøven nedenfor kvalifiserer bare den minimale appen, ikke hele norsk regnskap.
Kontrolleres før promotering til main:

- Ny installasjon med tilfeldige private passord og separate mapper for database,
  site-filer, kø og logger. Ingen gamle databaser eller evalueringsdata gjenbrukes.
- Native site og HTTP API svarer, og Socket.IO polling går gjennom frontend.
- Socket.IO WebSocket Upgrade gir HTTP 101 og korrekt handshake gjennom Compose-
  frontend. Dette gjelder ikke den eksterne reverse proxyen.
- Restart bevarer site-lagring og Frappe-krypteringsnøkkel.
- Native moduloppsett beholdes. Tidligere norsk skjuleprofil/default tilbakeføres
  for Lager, Produksjon, Prosjekter og Kvalitet; nye brukere får ingen slik profil.
  Senere personlige valg bevares. Se [modulvisning](module-defaults.md).
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
`tests/runtime-smoke.sh`. Den er ikke en gjenoppretting av serverens data eller kvalifisering av andre
kjerneversjoner. Den norske appen prøves særskilt som beskrevet nedenfor. Backup av
privat driftskonfigurasjon, separat lagring, full servergjenoppretting,
oppdateringsflyt og norsk regnskapsaksept skal fullføres videre i dette prosjektet.
Ingen automatisk skatteinnsending, SAF-T eller EHF hevdes
levert av dette driftsgrunnlaget. EHF og samlet sluttkontroll følger planen.

## Minimal norsk app

`ERP_TEST_APP=1 bash tests/runtime-smoke.sh` bygger et låst app-image og bruker
produksjonsverktøyet til backup før image-/konfigurasjonsendring, installasjon
og native migrering av den tomme testinstansen. Samme modul-, kontoplan-,
regnskaps- og eierprøver gjentas med appen aktiv.

Appprøven kontrollerer native F/K, partskoder og startnummer, avvisning av sletting,
omdøping, endret returtype og nullstilling/overstyring av brukt serie. Manuelle
importnumre skal ikke omgå appens serie. Eksisterende brukt register uten appregel
skal ikke få en ny erstatningsserie ved migrering.

Vanlig eier og Administrator prøver File-API for sletting, frakobling, URL-/navn-
og privatstatusendring. Originalbyte kontrolleres etter avvisning. Overskriving
via delt fil-URL og ny File uten opprinnelig ID prøves også. Nye vedlegg og retting
av kladdvedlegg tillates. Native kansellering fungerer; sletting av kansellert
bilag/vedlegg og faktura-amendment med suffiks avvises.

To samtidige uavhengige native sesjoner prøves med seks fakturakladder. En native
konflikt kan kreve et nytt lagringsforsøk etter rollback. Resultatet må være seks
unike, fortløpende, bevarte numre og riktig native teller; ingen egen retry eller
teller er produktkode. Etter eksportert backup, skade på syntetiske data/filer,
sletting av kildebackup, restore og native migrering prøves app, originalvedlegg,
vern, teller, hovedbok, krypteringsnøkkel, HTTP og privat gjesteavvisning igjen.

Kontraktstester prøver feil før/etter migreringsgrensen, feil ved backupforsegling,
bevaring av privat konfigurasjon og opprinnelig tjenesteutvalg. En mislykket
migrering skal aldri automatisk åpne gammel kode mot muligens endret database.
Disse feilmodellene erstatter ikke en faktisk servergjenoppretting.

## Norsk språk og PDF ved innsending

Appprøven utvider den generiske PDF-prøven med seks faktiske PDF-er: tilbud,
faktura med rabatt og kreditnota på bokmål/engelsk. Native get_print og File brukes.
Privat original bevares ved senere mal-/foretaksendringer og eksportert restore.
PDF-feil hindrer bokføring, og kansellert tilbud beholder filen. Se
[salgsdokumenter](sales-documents.md) for det begrensede dokumentomfanget.

Med `ERP_TEST_BROWSER=1` prøves vanlig eiers faktiske Desk og forhåndsvisninger,
inkludert private PDF-er som eieren får lese og gjesten nektes. CI bruker Playwright
1.58.2 fra `tests/browser/package-lock.json`, bare i testmiljøet. Dette tilføyer
ingen nettleseravhengighet til ERPNext-imaget. Ekstern proxy/ressurstilgang på
brukerens server er fortsatt ikke verifisert av Codex.
