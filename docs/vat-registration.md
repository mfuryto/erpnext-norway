# MVA-registrering og overgang

Registreringsgrunnlaget dekker et norsk NOK-foretak som går fra ikke registrert til godkjent
registrering, med innenlandsk ordinær sats 25 %. Planlagt registrering er ikke en
bekreftelse. Appen registrerer ikke virksomheten hos Skatteetaten og aktiverer ikke
MVA automatisk ved en omsetningsgrense.

## Native funksjoner og påvist gap

ERPNext 16.51.1 har Tax ID på Company, men ikke norsk registreringsstatus eller
virkningsdato. Landoppsettet oppretter tidløse 25 %-standardmaler uten å kjenne
registreringen. Tax Rule har allerede fra-/til-dato og brukes av ordinært malvalg.
Sales Invoice har allerede company_tax_id som dokumentets eget felt.

Minste tillegg er to native Custom Fields på Company, vanlige dokumenthendelser
for registreringskontroll og eksisterende Tax Category/Tax Rule/avgiftsmaler.
Kjernens beløpsberegning, avrunding, hovedbok, kreditnota, betaling, File og Version
beholdes. Rapporttillegget bruker native Script Report over disse kildene.

## Foretaksinnstilling

Velg **MVA-registrering (Norge)** i Foretak:

- **Ikke konfigurert**: Eksisterende registrering blir ikke gjettet fra kontoplan,
  kontonavn eller organisasjonsnummer. Faktura kan klargjøres, men må ha avklart
  registrering før bokføring.
- **Ikke registrert**: Vanlig salg føres uten utgående MVA. Kjøp føres med kostnaden
  inkludert MVA uten urettmessig fradrag for inngående MVA.
- **Registrert**: Brukes etter godkjenning. Angi **MVA-registrert fra** med
  virkningsdatoen i bekreftelsen og et nisifret organisasjonsnummer. En bekreftet
  framtidig virkningsdato gir ikke MVA på tidligere fakturaer.

Valg av registrering fjerner de tidløse MVA-standardene som ellers kan omgå datoen.
Ingen eksisterende fakturaer, avgiftsrader eller hovedboksposter beregnes på nytt.
Ved vanlig migrering beholdes eksisterende valg og native dokumenter.

## Vanlig registrering etter godkjenning

Med den norske kontoplanen opprettes native kategori **Norge MVA 25 %**, en
salgs- og en kjøpsmal, og daterte regler fra registreringens virkningsdato:

| Behandling | Native konto | Eksempel ekskl. MVA | MVA | Sum |
| --- | --- | ---: | ---: | ---: |
| Innenlandsk salg 25 % | 2700 utgående MVA | 1 000 | 250 | 1 250 |
| Innenlandsk kjøp med fullt fradrag 25 % | 2710 inngående MVA | 400 | 100 | 500 |

Velg aktuell avgiftskategori eller avgiftsmal i det ordinære fakturabildet.
Native skjermvalg henter avgiftsradene. Ved API-import må klienten sende native
avgiftsrader eller bruke ERPNexts eksisterende innstilling for å hente dem fra malen.
Appen endrer ikke denne globale innstillingen; en tom 25 %-mal avvises ved bokføring.
Kategorien er et uttrykkelig behandlingsvalg, ikke en automatisk slutning om at
alle norske eller utenlandske salg skal ha 25 %. Andre kontoplaner og eksplisitte
native maler beholdes; appen erstatter dem ikke med antatte norske kontoer.
Senere vanlige foretaksendringer tilbakestiller ikke redigerte native regler/maler.

Før virkningsdatoen avvises utgående MVA på salg og ordinært fradrag på kjøp.
For kjøp vurderes leverandørens fakturadato når den er angitt, ikke bare datoen
bilaget bokføres på. En gammel leverandørfaktura får derfor ikke automatisk
fradrag ved å bokføres etter registreringen.

Sales Invoice sitt eksisterende company_tax_id får organisasjonsnummer med MVA
når fakturaens registrering gjelder. Det er et felt på fakturaen; endret foretaksstatus
skal ikke endre opplysningene på tidligere bilag eller de bevarte PDF-originalene.
Appens eksakte uendrede utskriftsmal oppdateres for å vise MVA/VAT etter dokumentspråket.
Brukertilpassede maler og bevarte originalfiler overtas ikke. Native avgiftsrader,
beløpsformatering og avgiftsutskrift brukes videre.

Native kreditnota beholder originalfakturaens avgiftsbehandling og referanse, også
når kreditnotaen bokføres etter registreringen og originalen var uten MVA.
Utsteders organisasjonsnummer/MVA-merke følger derimot registreringen ved
utstedelsen av den nye kreditnotaen. Allerede utstedte originaler endres ikke.

## Satser, varelinjer og fradrag i app 0.4.0

Registrert foretak med norsk kontoplan får også daterte 15/12 %-maler og native
vareavgiftsmaler **MVA 25/15/12 % – varelinjer**. Velg mal per fakturalinje ved
blandet behandling. Koder og sats lagres på bilagslinjen; senere malendringer skal
ikke endre klassifiseringen av tidligere bilag.

På en ordinær kostnadslinje i kjøpsfakturaen angis **MVA-fradrag i prosent**.
Kjernen beregner både fradraget og den ikke-fradragsførte delen på valgt
kostnadskonto. Eksempel: 1000 ekskl. MVA, 25 % sats og 60 % fradrag gir 1250
leverandørgjeld, 150 inngående MVA og 1100 kostnad. Velg 100 % for fullt fradrag
eller 0 % for at hele avgiften inngår i kostnaden. Lagrede delvise maler beholder
sitt fradragsvalg når de velges på en ny linje. Lager/driftsmidler omfattes ennå
ikke av dette fradragsfeltets kvalifiserte normalflyt.

Separate native vareavgiftsvalg skiller **Fritatt MVA – nullsats**, **Unntatt MVA**,
**Uten MVA-behandling** og **Eksport – fritatt MVA**. De gir ulike norske koder;
de rettslige vilkårene avgjør hvilket valg som faktisk gjelder for leveransen.
Ingen utenlandsbehandling utledes automatisk bare fra kundens land.

Åpne **Norsk MVA-spesifikasjon** gjennom ERPNexts rapportsøk. Velg foretak og
periode. Visning per kode gir grunnlag for portalen; detaljvisning gir native
bilagslenker, linje, bokføringsdato og dato for MVA-perioden. Kjøpsfaktura bruker
leverandørens fakturadato når den er angitt. Rapporten avstemmer avgiftsdetaljene
mot bilagets hovedbok og avviser uklassifiserte MVA-posteringer.
Eldre bilag fra før kodefeltene ble innført må klassifiseres med riktig
**Norsk MVA-kode** på den native faktura-/journallinjen. Dette er metadata med
native endringssporing og periodevern; rapporten gjetter ikke nullsats versus
unntak fra at avgiftsbeløpet er null. Beløpsrettelser krever ordinær kreditnota
eller dokumentert journal, og tidligere bevarte originaler endres ikke.

**Opprett MVA-oppgjør** lager en vanlig Journal Entry-kladd til ordinær kontroll
og bokføring. Tidligere oppgjør for samme periode trekkes fra ved en rettelse;
et oppgjør for en overlappende annen periode avvises. Fra det bokførte oppgjøret
kan **Opprett MVA-betaling eller refusjon** åpne et vanlig bankbilag med native referanse.
Fyll faktisk bankdato og bankreferanse, bokfør og bruk standard bankavstemming.
Betaling bruker 2740; beløp til gode bruker 1640 for å støtte kjernens refusjonsreferanse.

**Bevar MVA-grunnlag** lagrer et privat, beskyttet File-vedlegg på foretaket.
Innlevert melding og kvittering kan legges ved samme sted via rapportens knapper.
Nullmelding krever ikke et fiktivt nullbilag. Appen sender ikke meldingen og
produserer ikke en kvittering fra Skatteetaten. Faktisk innlevering gjøres i portalen.

## Videre MVA-arbeid og avgrensning

Dette er ikke ferdig samlet MVA-støtte. [Den samlede MVA-planen](vat-plan.md)
angir prøvd omfang og åpne gap, blant annet utland/import, ikke-registrert
kvartalsgrunnlag og ordre-/mottakskjede med kapitalisert MVA.

Ikke-registrering betyr heller ikke at alle utenlandskjøp er uten avgiftsplikt.
Kontrollen tillater en positiv native kreditpostering på utgående MVA-konto ved
omvendt avgiftsplikt, men dette er ikke en ferdig automatisk kvartalsrapport eller
terskelvurdering. Tilbakegående avgiftsoppgjør for eldre kjøp skal vurderes særskilt.
Gamle kjøp får ikke fradrag automatisk som følge av registreringen.

## Kilder kontrollert 18. oktober 2026

- [Skatteetaten: Registrere, endre eller slette i Mva-registeret](https://www.skatteetaten.no/bedrift-og-organisasjon/avgifter/mva/registrere-endre-slette/):
  godkjenning før fakturering med MVA, overgangsfaktura/kreditnota og mulig
  tilbakegående avgiftsoppgjør. Bruk den faktiske bekreftelsen for foretaket.
- [Skatteetaten: MVA-satser](https://www.skatteetaten.no/satser/merverdiavgift?pageid=1500):
  ordinær sats og bransjer med egne satser. Denne delen prøver ordinær sats.
- [Skatteetaten: Tjenestekjøp fra utlandet](https://www.skatteetaten.no/satser/mva-satser-kjop-av-tjenester-fra-utlandet-svalbard-og-jan-mayen/):
  egne plikter også for ikke-registrerte næringsdrivende.

## Aksept

`tests/runtime-vat.py` bruker ekte native Company, Tax Rule, avgiftsmaler,
fakturaer, kreditnotaer, Payment Entry og private File-originaler. Vanlig eier uten
System Manager prøver før-/etterdato, ikke konfigurert, bekreftet framtidig dato,
fullt fradrag, sperret tidlig fradrag, kreditnota og uendrede originaler.
Samme status, bilagsbeløp og PDF-bytes skal bestå eksportert backup/restore/migrering.
Nettleserprøven skal kontrollere de norske feltene og native behandlingsvalg.

## Norske standardnavn

Ved oppdatering og foretaksoppsett blir kjernens eksakte standardnavn
«Norway VAT 25%» og «Norway VAT 12%» til «Utgående MVA … – ERPNext-standard»
på salg, «Inngående MVA … – ERPNext-standard» på kjøp og «MVA …» for vareavgiftsmaler.
Appens daterte 25 %-maler heter «Utgående MVA 25 %» og
«Inngående MVA 25 % – fullt fradrag». Kategorien «Norge MVA 25 %» er felles.
Standardmalens navn dokumenterer ikke alene korrekt fradrag eller kontovalg;
registreringsflyten bruker appens daterte maler med 2700/2710.
Tilsvarende standardbeskrivelser og unummererte MVA-kontonavn får MVA.
Native navneendring oppdaterer lenker; satser, beløp og lagrede PDF-originaler
endres ikke. Egne navn og navnekollisjoner beholdes uten sammenslåing.
Kjernens standardmaler beholdes som egne maler; de skal ikke forveksles med
appens daterte norske maler og varelinjevalg.
