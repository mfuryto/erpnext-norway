# Arbeidsregler for ERPNext Norway

- ERPNext-kjernen er førstevalget. Undersøk og prøv standardfunksjonen før tilleggskode.
  Ikke erstatt eller bygg en parallell variant av funksjoner som finnes og er gode nok.
- Dolibarr Norway og åpne tillegg er referanser for krav, regler, testeksempler og mønstre.
  Ikke importer dem som standardløsning eller overta egne arbeidsflater og kontrollag.
- Ny kode skal lukke et dokumentert norsk krav eller et uttrykkelig bestilt gap.
  Beskriv gapet og hvorfor kjernen ikke dekker det før implementasjon.
- Bruk en ekstern Frappe-app når tilpasning trengs. Ikke endre ERPNext/Frappe-kjernen.
  Velg konfigurasjon og ordinære hendelser før klasseoverstyringer.
- Normal faktura-/bilagsregistrering skal velge behandlingen. Den skal følge kreditnota,
  betaling, hovedbok og rapportering. Manuell etterbehandling er ikke ferdig normalflyt.
- Ikke lag nye bekreftelsessider, historikkregistre eller parallelle hovedbøker for trygghets skyld.
- Oppstartsveileder skal være kort status, forklaring og lenker til naturlige arbeidssteder.
- Norsk standardoppsett skal vise Lager/Stock for artikkelregisteret og skjule
  Produksjon, Prosjekter og Kvalitet med native modulvalg. Brukeren kan vise dem senere. Systemblokkering er ikke
  bestilt etter presiseringen. Bevar funksjoner, felles grunndata og senere brukervalg.
- Bare grenene main og staging. Ingen feature-grener. Utvikle på staging; test før push.
- Main krever PR fra staging og beståtte aktuelle CI-resultater. Ingen direkte push,
  force-push eller sletting. Synkroniser staging etter promotering uten force-push.
- Brukeren har gitt varig godkjenning til å overføre ferdige endringer fra staging
  til main. Fullfør PR, aktuelle kontroller og sammenslåing uten ny godkjenningsrunde.
  Ikke la ferdige endringer bli liggende bare på staging. Serveroppdateringer kjøres
  fortsatt av brukeren fra leverte kommandoblokker.
- Installer lokal hook med `git config core.hooksPath .githooks`. Ikke omgå serververn.
- Bruk nøytral commit-identitet og generisk dokumentasjon. Ikke publiser private domener,
  servernavn, selskapsnavn, installasjonsstier, bilag eller hemmeligheter.
- Bevar prosjektnavn, datalagring, passord og Frappe-krypteringsnøkkel ved oppdatering.
  Ikke bruk testdata i drift. Skjemaendringer krever migrering, backup og restore-prøve.
- Bruk låste images/avhengigheter og minst mulige CI-rettigheter. Compose er driftsformen.
- Lisensintegrasjoner er valgfrie og leverandørnøytrale og utvikles i det eksterne prosjektet.
  Regnskapskjernen skal ikke avhenge av dem.
- Skill teknisk drift fra regnskapsmessig aksept. Ingen generell påstand om norsk
  etterlevelse basert bare på grønn CI eller standard ERPNext.
- Bruk «kontroll» om regnskapsvalidering. Ikke introduser sjekkbetaling i norsk arbeidsflyt.
- Lever serveroppdateringer som én kjørbar blokk som henter gjeldende origin/main
  med fetch og fast-forward, uten låst target/revisjon. Bevar eksisterende data ved overgang.
- Les docs/handover.md før videre arbeid. Utvikling i Dolibarr Norway er satt på vent.
