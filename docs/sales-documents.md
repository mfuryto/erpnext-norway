# Norsk og engelsk tilbud, faktura og kreditnota

Appen bruker Frappe sine ordinære Jinja Print Formats, ERPNext sine
avgiftsmaler, native formattering og allerede beregnede dokumentbeløp. Ingen
PDF-motor, nummerserie, avgiftsberegning eller utsendelsesfunksjon erstattes.

`Norway Invoice` dekker både salgsfaktura og kreditnota; `Norway Quotation` dekker
tilbud. De legges inn ved installasjon/migrering. Standardformatet velges bare
ved førstegangsoppsett på et tomt dokumentregister med kjernens Classic-standard.
Andre eksisterende standardvalg overtas ikke. Velg eventuelt malen gjennom native
Print Format dersom registeret allerede er i bruk. Senere malvalg,
inkludert eksplisitt Standard, og endringer i malinnhold beholdes ved migrering.
Bruk native Print Format for egne varianter. Det leveres ikke et nytt malverktøy.

## Vanlig bruk

- Velg bokmål (`nb`) som eget brukerspråk. Dokumentets **Dokumentspråk** kan være
  `nb` eller `en`, uavhengig av skjermspråket. Det eksisterende språkfeltet
  gjøres redigerbart på kladd med native Property Setter. Bruk kjernens språk fra
  kunde/systemvalg, eller velg et annet språk på dokumentet før innsending.
  Senere uttrykkelig tilpasning av feltets redigerbarhet beholdes.
- Bruk native foretaks-/kundeadresser, organisasjonsnummer, artikkelbeskrivelse,
  fakturadato, betalingsfrist, leveringsadresse og eventuelt fra-/til-dato. Beskriv
  faktisk leveringstid og leveringssted i disse feltene eller beskrivelsen.
  Brukerens fritekst og artikkelnavn maskinoversettes ikke.
- Foretakets native **Tax ID** brukes til organisasjonsnummer. Registreringsstatus
  utledes ikke av avgiftsrader eller språkvalg. For ikke-registrert foretak skal
  nummeret ikke få MVA-suffiks; for registrert foretak må korrekt MVA-ID oppgis.
  Norske avgiftsvalg og registreringsdato behandles i neste arbeidspakke.
- For betaling brukes kjernens valg av foretakets **Bank Account**: kundens
  foretrukne firmabankkonto, ellers foretakets standard. Bare aktiv firmabankkonto
  for riktig foretak vises. Oppgi bankkontonummer og eventuelt IBAN der.
  En tilfeldig konto eller en hovedbokskontos kontonummer brukes ikke som banknummer.
- Kreditnota viser native `return_against` som opprinnelig faktura. Bruk normal
  ERPNext-retur fra originalen og behold referansen.

## Bevaring

Kjernen lager PDF ved utskrift, men bevarer ikke automatisk en PDF ved innsending.
Et ordinært `on_submit`-hook lagrer derfor en privat PDF som native File-vedlegg på
norske tilbud og salgsfakturaer, inkludert kreditnota. Den bruker dokumentets språk
og gjeldende standardformat. Filnavnet inneholder dokumentnummer og språk.
PDF-feil stopper innsendingen; dokumentet skal ikke bokføres uten dette vedlegget.

Dette er **PDF ved innsending/bokføring**, ikke kvittering for e-post eller EHF.
Send den lagrede PDF-en dersom det er denne versjonen mottakeren skal få. Native
utskriftsdialog kan fortsatt lage nye visninger med annet språk eller mal; disse
overskriver ikke vedlegget. Det sendes ingen e-post automatisk av appen.

Senere endring av foretak, brevark, bank eller mal endrer ikke lagrede PDF-bytes.
Vedleggsvernet dekker også innsendte/kansellerte tilbud. Kladder får ingen slik
PDF; nye vedlegg og korreksjon av kladdvedlegg bruker vanlig File-funksjon.
Migrering etterlager ikke «originaler» for tidligere dokumenter. Bevar eksisterende
utsendte dokumenter som private vedlegg. Dette er applikasjonsvern, ikke en sperre
mot direkte database-/filsystemtilgang.

## Aksept og avgrensning

`tests/runtime-language.py` prøver vanlig eier, bokmål og engelsk for alle tre
dokumenttyper, ekte PDF-tekst, standard rabatt og kreditbeløp, adresser, nummer,
organisasjonsnummer uten MVA-suffiks og bank. Originaler sammenlignes etter senere
endringer og eksportert backup/restore/migrate. Native brukervalg beholdes.
Skjermspråk prøves med faktisk Desk, ikke bare CSV-opptelling. Etiketter og
hjelpetekster er rettet fra gjennomgang av faktiske native metadata og skjermbilder.
Historisk fritekst, lager-/malnavn og beløp som allerede er lagret med bokstaver
endres ikke av en oversettelsesressurs. Native `in_words` kan falle tilbake til
engelsk når tallbiblioteket ikke støtter språkidentifikatoren; det feltet brukes
ikke i disse PDF-malene. Det bygges ingen egen tall-til-ord-motor.

Første omfang er norske NOK-dokumenter for ENK. Utskriftsmalene fullfører ikke
MVA-registrering, ulike avgiftsbehandlinger, utenlandsk valuta, EHF eller SAF-T.
Opplysningene i det enkelte dokument må fortsatt fylles riktig. Ingen generell
norsk etterlevelse eller produksjonsaksept følger av disse tekniske prøvene.

Kravgrunnlag: [Altinn: faktura (salgsdokumentasjon), oppdatert 18.03.2026](https://info.altinn.no/starte-og-drive/regnskap-og-revisjon/regnskap/faktura-salgsdokumentasjon/).
PDF er et annet leveranseformat enn EHF. Krav til leveringsopplysninger,
MVA-identifikasjon og kreditnotareferanse skal beholdes ved egne maltilpasninger.
