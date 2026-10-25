# Oppdatering av ERPNext/Frappe

App 0.4.7 bruker ERPNext 16.52.1 / Frappe 16.53.0 fra det offisielle
`frappe/erpnext:v16.52.1`-imaget, låst til flerplattform-digest
`sha256:eb1c22d2bb926ed97352b63334507bf0297f1ca1244b406e3f30869ca5d0092b`.
Versjonene er kontrollert ved Python-import uten site eller nettverk.
MariaDB, Redis og appens byggavhengigheter endres ikke.

## Kjernefunksjoner først

[ERPNext 16.52.0](https://github.com/frappe/erpnext/releases/tag/v16.52.0),
[ERPNext 16.52.1](https://github.com/frappe/erpnext/releases/tag/v16.52.1) og
[Frappe 16.53.0](https://github.com/frappe/frappe/releases/tag/v16.53.0)
er gjennomgått med særlig vekt på avgiftsrader, verdsetting/retur, filtilgang,
rapportering, oversettelse og dokumentbevaring.

ERPNext AccountsController.on_trash beskytter nå kansellerte bilag når
Accounts Settings.enable_immutable_ledger er aktivert. Appen lar denne ordinære
controller-kjeden håndtere avvisningen. Appvernet behøves fortsatt når innstillingen
er av, for nummererte fakturakladder og for tilbud. Det eksisterende filvernet
dekker fortsatt frakobling, overskriving og kansellerte bilagsvedlegg.
Ingen innstillinger slås automatisk på eller av. Kjernefilene endres ikke.

## Prøver før promotering

- Eksisterende syntetisk installasjon oppdateres med update-runtime.py: full native
  backup før imagebytte, native migrate og gjenstart av samme tjenesteutvalg.
- Sammenlign hovedbok, fakturabeløp, navngivingstellere, lokale filbytes og
  krypteringsnøkkel før/etter. Kontroller de seks bevarte NB/EN PDF-originalene.
- Gjenopprett den eksporterte backupen fra gammel kjerne med native restore og
  migrer med ny kjerne. Gjenta sammenligningen og originalkontrollen.
- Hele ordinære app-/nettleserprøven kontrollerer språk, MVA, betaling, bank,
  lager-/fraktflyt og eksportert backup/restore. Slettingsvern prøves med
  Immutable Ledger både på og av, uten å endre noen driftsinnstilling.
- CI prøver også standard ERPNext uten den norske appen. Grønn teknisk prøve
  er ikke generell regnskapsmessig aksept eller kvalifisering av åpne MVA-gap.

## Eksisterende server

Bruk vanlig oppdateringsblokk som henter gjeldende main, bygger app-imaget og
kjører update-runtime.py. Ikke kjør prepare-runtime.sh, ny site eller bench update.
Skriptet bevarer data, passord, krypteringsnøkkel og Compose-prosjektnavn, tar
backup og bruker kjernens migrering. Ved feil etter migreringsstart holdes
appene stoppet; gammel kode åpnes ikke mot en muligens migrert database.
Brukeren kjører serveroppdateringen og kontrollerer ekstern proxy/innlogging.
