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
| Foretak, valuta og år | Native Company og setup wizard i syntetisk foretak | ENK, faktisk MVA-status/virkningsdato og åpning må kvalifiseres uten private data i kode. |
| Norsk kontoplan | Chart of Accounts Importer tok imot 745 kontonumre | Gjennomgå kilde/lisens, kontogrupper og kontotyper. Angi bl.a. 1500 og 2400 uttrykkelig som reskontro-defaults; 2740 skal ikke velges som leverandørkonto. Prøv en ny normal salgs-/kjøpskjede etter import. |
| Salg, kjøp og bank | Faktura, kreditnota, Payment Entry, Bank Transaction og avstemming besto | Gjenta med norsk oppsett og vanlig eierbruker, inkludert avviste handlinger. Ikke bygg egen hovedbok. |
| MVA per linje | Native Item Tax Templates og avgiftsrader besto med ulik fradragsrett | Forståelig behandlingsvalg, lagret grunnlag, virkningsdato og norsk rapportering mangler. Ikke krev manuell konstruksjon av beregnede motrader i normal bruk. |
| Dokumentnummer | Native F/K/T-masker med seks løpesifre besto | Nummer kom ved kladdlagring, og kladd kunne slettes. Prøv native nummer ved innsending før valg av ekstern app-hook. Test samtidighet, avbrutt innsending, separate serier, valgfritt startnummer og kreditnota. |
| Bilagsbevaring | Private File-vedlegg avviste gjest | Administrator kunne slette vedlegg fra bokført kjøpsfaktura. Undersøk alle native slette-/erstatningsveier før et lite bevaringsvern gjennom dokumenthendelser. Prøv også kansellert dokument og direkte File-API. |
| Norsk/engelsk dokument | PDF ble generert på begge språk | Kvalifiser ordvalg, organisasjonsopplysninger, avgiftsstatus, datoer, nummer og originalreferanse på faktura/kreditnota. Teknisk PDF-rendering er ikke malaksept. |
| Norsk skjermspråk | Evalueringen viste engelske felt og ufullstendig bokmål | Oversett og rett fagbegreper i den støttede flyten etter [språkkravene](language.md). Prøv menyer, handlinger, statuser, hjelpetekster og feil, også med vanlig eierbruker. |
| Nummer på kunde/leverandør | Native navngiving er førstevalg | Prøv fem siffer og valgfritt prefiks uten å blande kode og visningsnavn. |
| Rettigheter | Begrenset REST-leser og foretaksfiltrering besto | Bokføring ble tidligere prøvd som Administrator. Eierbruker må kunne fullføre normalflyt og være avskåret fra uønsket endring/sletting. |

## Rekkefølge og bevis

1. Fullfør isolert driftstest for WebSocket, PDF, backup/gjenoppretting og migrering.
   Offentlig proxy, faktisk PDF-utskrift og backup av ferdig norsk app gjenstår separat.
2. Prøv kontoplan og standardkontoer i et nytt syntetisk foretak. Bevar kildens lisens
   og proveniens; kontoplanimport alene beviser ikke norsk etterlevelse.
3. Prøv native nummer ved innsending og dokumentbevaring i den låste kjernen.
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
