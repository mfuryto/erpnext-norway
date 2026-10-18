# Standard modulvisning

Brukeren har trukket tilbake tidligere modulskjuling. Lager, Produksjon,
Prosjekter og Kvalitet skal følge ERPNext sitt ordinære moduloppsett.
Prosjektet oppretter eller tildeler ikke lenger en skjulende modulprofil.
Vanlige roller og tilgangsrettigheter avgjør fortsatt hva hver bruker får se.

`deploy/module-visibility.py` tilbakefører den tidligere profilen **Norsk standard**
én gang. De fire modulene fjernes fra profilens blokkliste. Brukere med denne
profilen frikobles fra den, og de fire modulene fjernes fra deres kopierte
blokkliste. De fire fjernes også fra personlige blokklister uten annen modulprofil
ved denne overgangen. Den tilhørende standardverdien for nye brukere fjernes. Andre profiler
og eventuelle andre blokkerte moduler bevares. Senere personlige valg overtas ikke
ved neste oppdatering.

Tilbakeføringen inngår nå i `scripts/update-runtime.py`, etter backup og migrering,
før tjenestene åpnes. Bare kjøring ved klargjøring var ikke tilstrekkelig for en
allerede startet server. Ingen ny installasjon eller endring av roller inngår.
Etter serveroppdateringen må åpne nettleserfaner lastes inn på nytt.

`tests/runtime-module-visibility.py` prøver synlige native moduler, overgang fra
profilen som skjulte alle fire, standardverdier for nye brukere og bevaring av
senere valg. Eksportert backup/restore kontrollerer modulvalgene videre.
