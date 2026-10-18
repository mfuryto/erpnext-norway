# Kjerneoppsett og norsk minimum

Arbeidsgrunnlag for neste trinn, ikke en ny arbeidsflate eller produksjonsaksept.
Tidligere syntetiske prøver gjelder ERPNext 16.51.1 / Frappe 16.52.0.
De må ikke forveksles med oppsett eller prøver på en bestemt server.

## Før oppsett fullføres

Bruk faktisk foretaksnavn og organisasjonsnummer privat i ERPNext. Velg Norway,
NOK, Europe/Oslo og avtalt regnskapsår. Ikke opprett et syntetisk foretak på
driftsserveren for å fullføre veiviseren. Regnskapsfører/eier må bekrefte åpningsdato,
åpningsbalanse og eventuelt tidligere brukte dokumentnumre før første reelle bilag.

Registreringsstatus for MVA og eventuell virkningsdato må være uttrykkelig valgt.
For et ikke-registrert foretak skal oppsettet ikke automatisk velge utgående MVA,
fradragsføre inngående MVA eller legge MVA-merking etter organisasjonsnummeret.
Dette er ikke det samme som å velge en generell nullsatsmal: avgiftsbehandlingen
og rapportgrunnlaget må være riktig for den konkrete transaksjonen.
Utenlandskjøp og senere registrering trenger egne kvalifiserte tilfeller.

ERPNext sitt Standard-kontovalg er bare et teknisk utgangspunkt, ikke prosjektets
ferdige norske kontoplan. Ikke registrer reelle bilag før kontoplan og standardkontoer
er kvalifisert. Ikke installer tredjepartsapper eller importer evalueringsdata.

## Krav og minste løsning

| Område | Prøvd kjernefunksjon | Gjenstående gap / neste prøve |
| --- | --- | --- |
| Foretak, valuta og år | Native Company og setup wizard i syntetisk foretak | App 0.3.0 har native Company-felt for MVA-status og bekreftet virkningsdato. Faktiske foretaksdata/åpning konfigureres på serveren. |
| Norsk kontoplan | Native import av 745 norske kontoer med låst LGPL-kilde, 1500/2400-defaults og norske grupper besto | Se [kontoplan og oppsett](norwegian-chart.md). Native import etter postering avvises. Faktisk åpning og øvrige virksomhetsspesifikke defaults gjenstår. |
| Salg, kjøp og bank | Faktura, kreditnota, Payment Entry, Bank Transaction og avstemming besto med norsk plan og vanlig eierbruker | Syntetisk ikke-registrert innenlandsflyt gir resultat 475 og bank 275 etter eiertransaksjon. Full norsk MVA-behandling og utenlandsflyt gjenstår. |
| MVA per linje | Native Item Tax Templates og avgiftsrader besto med ulik fradragsrett | Registrering og virkningsdato leveres i [første MVA-del](vat-registration.md). Forståelig linjevalg, øvrige satser/fradrag og norsk rapportering gjenstår. Ikke krev manuell konstruksjon av beregnede motrader i normal bruk. |
| Dokumentnummer | Document Naming Rule besto separate F/K/T, startteller, femsifrede partskoder og transaksjonsrollback | Bruk native tellere. Minimal app bevarer kladder og native serier og avviser suffiks-amendment. Native konflikt/rollback og nytt lagringsforsøk prøves; se [appen](norwegian-app.md). |
| Bilagsbevaring | Native protect_attached_files avviste Administrator før sletting på bokført faktura | Bruk eksisterende Property Setter og native filer. Minimal app lukker sletting/frakobling/overskriving i støttede filgrensesnitt. PDF ved innsending lagres nå som beskyttet native vedlegg; se [dokumentomfanget](sales-documents.md). |
| Norsk/engelsk dokument | PDF ble generert på begge språk | App 0.2.0 prøver tilbud/faktura/kreditnota på nb/en med native beløp, org.nr, adresser, bank og kreditreferanse. App 0.3.0 lagrer fakturaens MVA-merking etter bekreftet registrering. Øvrige MVA-tilfeller og leveranseveier gjenstår. |
| Norsk skjermspråk | Evalueringen viste engelske felt og ufullstendig bokmål | Målrettede CSV-rettelser og faktisk Desk med vanlig eier prøves etter [språkkravene](language.md). Nye språkfunn følger senere MVA-/års-/EHF-flyt. |
| Nummer på kunde/leverandør | Native navngiving er førstevalg | Prøv fem siffer og valgfritt prefiks uten å blande kode og visningsnavn. |
| Rettigheter | Begrenset REST-leser og foretaksfiltrering besto | Vanlig eier uten System Manager besto salg/kjøp/bank med foretaksavgrensning og avvisning av System Settings. Dokumentbevaring og øvrige negative rettighetsprøver gjenstår. |
| Valgfrie moduler | Native modulprofiler styrer navigasjon | Behold standardoppsettet for alle moduler og tilbakefør tidligere norsk skjuling. Følg [moduloppsettet](module-defaults.md); funksjoner og senere brukervalg skal bevares. |

## Rekkefølge og bevis

1. Fullfør isolert driftstest for WebSocket, PDF, backup/gjenoppretting og migrering.
   Offentlig proxy, faktisk PDF-utskrift og backup av ferdig norsk app gjenstår separat.
2. Prøv kontoplan og standardkontoer i et nytt syntetisk foretak. Bevar kildens lisens
   og proveniens; kontoplanimport alene beviser ikke norsk etterlevelse.
3. Prøv beskyttelse av native numre og dokumentbevaring i den låste kjernen.
   Beskriv minste nødvendige app-endring før implementasjon.
4. Kvalifiser vanlig eierbruker og dokumentmalene før serveroppsettet tas i bruk.
5. Fortsett med MVA, SAF-T og øvrige trinn i handover. Ikke merk hele produktet ferdig
   fordi oppsett, en faktura eller CI fungerer.

Resultater skal vise versjon, syntetisk input, forventet resultat, faktisk resultat
og eventuelle begrensninger. Ingen reelle foretak eller bilag i testfiksturer.

## Kilder

- Lokal, ignorert evaluering med testskript og resultater; oppsummert i
  [overleveringen](handover.md).
- [ERPNext Company](https://docs.frappe.io/erpnext/company-setup) og
  [Chart of Accounts](https://docs.frappe.io/erpnext/chart-of-accounts): native oppsett.
- [Document Naming Settings](https://docs.frappe.io/erpnext/document-naming-settings):
  native nummerserier; testene i prosjektets låste versjon avgjør faktisk oppførsel.

## Ny kjerneprøve

`tests/runtime-core-accounting.py` kjører mot det låste runtime-imaget.
Kontoplan, native hovedbok, reskontro, bank, MVA-standardvalg og resultat
kontrolleres igjen etter eksportert backup, gjenoppretting og migrering.
Ingen tilleggsapp eller kjerneendring er nødvendig for disse prøvde funksjonene.
