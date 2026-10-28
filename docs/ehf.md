# EHF: videreføring og aksept

EHF er uttrykkelig videreført i bestillingen 28. oktober 2026. Det følger etter
SAF-T og ENK/årsgrunnlag, før samlet sluttkontroll. **EHF er ikke levert eller
kvalifisert i ERPNext Norway ennå.** Bevar eksisterende faktura, kreditnota,
nummer, regnskap og private dokumentoriginaler som kilder.

## Gjeldende format og eksisterende løsninger

[DFØs EHF-veiledning](https://www.anskaffelser.no/verktoy/veiledere/ehf-fakturering)
beskriver EHF-fakturering 3.0 og fakturering til staten.
[Peppol BIS Billing, mai 2026](https://docs.peppol.eu/poacc/billing/3.0/)
er produksjonsgrunnlaget undersøkt 28. oktober; utgave 3.0.21 ble obligatorisk
17. august 2026 ifølge [utgivelsesnotatene](https://docs.peppol.eu/poacc/billing/3.0/release-notes/).
November 2026-utgaven på testområdet er ikke valgt som produksjonsstandard.
Både UBL Invoice og UBL CreditNote samt norske regler skal kvalifiseres.

Kjernen har elektronisk fakturering for andre land. Det er ikke dokumentasjon
på norsk EHF; italiensk fakturaformat skal ikke omdøpes til EHF.
Disse eksisterende tilleggene undersøkes før eventuell ny adapter:

| Kandidat | Undersøkt støtte | Åpent før valg |
| --- | --- | --- |
| [Peppol 4 ERPNext](https://github.com/Grynn-GmbH/peppol_4_erpnext/tree/9efe16be5ab5d2a338fe3612ecfc02344b45f382) | Integrasjonsflagg og eksternt opplegg for overføring. | Faktisk format, transportavhengigheter, Peppyrus-støtte og v16-prøve. Et flagg er ikke levert dokument. |
| [Peppol Connect](https://github.com/maasanto/peppol-connect/tree/3bd618b237bfad1cf659c5445eeccb34b829076c) | Generisk leverandørgrensesnitt, asynkron sending, status og webhooks; Recommand-adapter. | Ingen Peppyrus-adapter funnet i denne revisjonen. Sending importerer `get_einvoice` fra eu_einvoice; format og avhengighetsversjon må prøves samlet. |
| [European e-Invoice](https://github.com/alyf-de/eu_einvoice/tree/b4b66b468bf32371c2f5d7be9b28a738d0ba94d7) | README avgrenser til CII/Factur-X/ZUGFeRD, også XRechnung. | UBL og Peppol-transport er uttrykkelig utenfor omfanget i denne revisjonen. Det kan ikke uten videre installeres som norsk EHF-løsning. |
| [European e-Invoice Peppol-fork](https://github.com/prilk-consulting/eu_einvoice_peppol/tree/eff09ff5e4b4cb80b026a093cf42f03bfaa40276) | Oppgir UBL 2.1 for Peppol, og har UBL-skjemaer; appmetadata tillater Frappe/ERPNext 15–16. | Faktisk v16-/Python 3.14-installasjon, vedlikehold, låste avhengigheter, kreditnota og norske valideringer må prøves. Dette er en konkret gjenbrukskandidat før en ny UBL-bygger vurderes. |

Dette er kildeundersøkelse, ikke full installasjons-/nettverksprøve av tilleggene.
Ingen er innført som produktavhengighet, og det er ikke laget en ny UBL-motor.

## Peppyrus og forskjellen mellom sendt og mottatt

Peppyrus har separat [test-API og OpenAPI-beskrivelse](https://api.test.peppyrus.be/v1).
Undersøkt 28. oktober 2026, API 1.0.0:

- `POST /message` tar avsender, mottaker, prosess, dokumenttype og base64-fil.
- `GET /message/{id}` gir melding, retning, mappe og feltet `confirmed`.
- `GET /message/{id}/report` gir validerings-/overføringsopplysninger.
- Deltakeroppslag finnes i `/peppol/lookup` og `/peppol/bestMatch`.

Disse endepunktene er dokumenterte muligheter, ikke bevis på vellykket levering
eller avklart betydning av alle statusfelt. Tidligere kontoprøve ga HTTP 200,
men deltakerprøve ga HTTP 500. Den feilen og faktisk ende-til-ende-levering står
fortsatt åpne. API-nøkkel holdes privat og tas aldri inn i Git, tester eller logger.

En transportkvittering fra aksesspunktet må skilles fra mottakers eventuelle
forretningsmessige svar. Peppol-utgaven har en valgfri faktura-med-svar-profil,
med egen SMP-registrering. Et slikt svar skal ikke loves for alle mottakere;
profil og mottakers kapasitet må faktisk avklares og prøves.

## Leveranse som må bestå før EHF er ferdig

1. Prøv aktuelle eksisterende tillegg og deres XML-utdata på den låste kjernen.
   Dokumenter konkret gap før valg av minste norske tilpasning/transportadapter.
2. Knytt korrekt organisasjons-/deltaker-ID, adresser, mottaker-/ordrehenvisning,
   betalingsopplysninger og norske MVA-behandlinger til eksisterende fakturafelt.
   Normal faktura og kreditnota skal være kilden; ingen ny fakturaflate eller
   egen avgiftsberegning.
3. Prøv registrert og ikke-registrert selger, aktuelle satser, rabatter/frakt,
   avrunding og kreditnota med originalreferanse. Valider faktisk XML med UBL
   XSD, EN 16931 og gjeldende Peppol-/norske regler.
4. Send syntetisk faktura **og kreditnota** gjennom faktisk testnettverk til en
   avtalt testmottaker. Knytt meldings-ID og faktisk rapport/kvittering til
   kildebilaget ved hjelp av eksisterende integrasjons-/filfunksjoner der de passer.
5. Prøv ukjent mottaker, formatavvisning, transportfeil, timeout med ukjent utfall
   og ny forespørsel. Ikke send samme faktura to ganger ved blind gjentakelse.
   Vis norske tilstander med ærlig skille mellom kø, sending, levering og feil.
6. Prøv rettigheter, hemmelighetshåndtering, bevaring og backup/gjenoppretting
   med ordinær eier. Deretter kommer samlet sluttkontroll og driftsveiledning.

Produksjonsaktivering og faktiske serverhandlinger utføres av brukeren gjennom
leverte blokker. En testkonto eller grønn CI alene betyr ikke at EHF er ferdig.
