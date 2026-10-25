# Vareimport: kjerne først

Registrerte foretak beregner innførsels-MVA med deklarasjonens grunnlag. Vanlig
hovedregel er statistisk verdi pluss toll og andre avgifter, ikke uten videre
leverandørfakturaens beløp. Ikke-registrerte foretak betaler til Tolletaten eller
speditør. Kilde: [Skatteetatens importveiledning](https://www.skatteetaten.no/bedrift-og-organisasjon/avgifter/mva/utland/import/beregne/).

ERPNext har allerede Purchase Invoice, Purchase Receipt, ordinære Journal Entry,
File-vedlegg og Landed Cost Voucher for senere lagerkostnader. Disse beholdes.
Deklarasjon og leverandørfaktura må behandles som forskjellige kilder; samme
frakt eller avgift skal ikke kapitaliseres to ganger. Se [native LCV](https://docs.frappe.io/erpnext/stock-transactions-landed-cost-voucher).

## Dokumentert gap før endring

En rollbacket faktisk prøve i det låste imaget med vanlig eier ga dette:
Journal Entry kode 81, dokumentert grunnlag 4 700, utgående 1 175 på 2705 og
inngående 1 175 på 2715. Native «Reverser bilag» ga korrekt −1 175 på begge
MVA-sider, men tilleggets kopierte grunnlag forble +4 700. Perioderapporten fikk
derfor positivt grunnlag ved en full reversering. Ingen feil i kjernens
beløpsberegning eller hovedbok er påvist.

Minste retting er å utvide den eksisterende metadatarettingen fra kode 87 til
importkodene 81/82 på 2705 og 83/84 på 2706. Bare en eksakt native reversering
med samme konto, valutakurs, sats, spesifikasjon og motsatte beløp får snudd
kopiert grunnlag. Ingen nye felt, klasseoverstyringer eller beløpsberegning.

## Avgrenset kvalifisering i app 0.4.13

Prøven gjelder dokumenterte importbilag og deres native reversering, ikke en
ferdig normalflyt fra tolldeklarasjon til varer/lager og MVA-melding.
25 % med fullt, 60 % og intet fradrag samt 15 % med fullt/intet fradrag prøves
på eksisterende koder og kontoer. Original og reversering ligger i hver sin
periode. Grunnlag, beløp, kobling og private syntetiske deklarasjonsvedlegg
kontrolleres igjen etter eksportert backup/gjenoppretting.

Ved 0.4.13 gjenstod deklarasjonsperiode og ordinær mottaks-/kostnadskjede;
videreføringen nedenfor dokumenterer løsningen i 0.4.15. Særskilte
importprosedyrer er fortsatt ikke kvalifisert. Ikke bruk teknisk grønn prøve som generell påstand om
norsk importetterlevelse. Kvartalsbehandling før registrering er et separat åpent
punkt i vat-foreign-services.md.

## Videre kjerneprøve: ordinær import og nullsats

En faktisk tilbakerullet prøve med vanlig eier skiller tre kilder: varefaktura
300 EUR, bokført til 3 000 NOK; egen toll-/kostnadsfaktura 1 700 NOK; deklarasjon
med statistisk verdi 3 300 og grunnlag 5 000. Native Journal Entry fører 1 250
utgående og 750 inngående MVA. Standard Landed Cost Voucher knytter
kostnadsfakturaen til varene og kapitaliserer 500 ikke-fradragsført MVA.
Resultatet er lager 5 200 og null på verdsettingsmotkontoen. Native betaling
3 150 NOK gjør opp EUR-leverandøren uten å endre deklarasjonens MVA-grunnlag.
Det trengs ingen ny import- eller verdsettingsmotor.

Påvist gjenværende gap: deklarasjonsbilaget ble vist i oktober selv om native
`bill_date` inneholdt ekspedisjonsdato i september. Perioden må følge denne
datoen for dokumenterte innførselskoder; vanlig bilagsdato beholdes separat.
En omberegning kan gjelde gammel periode, mens etterdeklarering kan ha ny
utstedelses-/ekspedisjonsdato. Se [gjeldende praktisk veiledning](https://www.skatteetaten.no/bedrift-og-organisasjon/avgifter/mva/utland/import/beregne/)
og [Skattedirektoratets faglige avklaringer](https://www.skatteetaten.no/rettskilder/type/uttalelser/prinsipputtalelser/faglige-avklaringer-mv.-knyttet-til-innforselsmerverdiavgiften/).
Leverandørkreditnota alene skal ikke gjette en korrigert tolldeklarasjon.

En annen faktisk prøve viser at native Purchase Receipt også tar imot fysiske
varer som ikke lagerføres, uten å opprette hovedbokslinjer. Mottaket kobles
ordinært til leverandørfakturaen. Dermed kan eksisterende mottak, private
vedlegg og noen deklarasjonsmetadata dekke kode 85 uten et fiktivt nullbilag
eller en ny dokumenttype. Kostnadsfakturaen og deklarasjonsgrunnlaget skal ikke
rapporteres dobbelt. Endring av statistiske metadata skal bruke native Version
og eksisterende periodekontroll; en vareretur opphever ikke innførselen i seg selv.

## Ordinær kildeflyt i app 0.4.15

Det dokumenterte gapet lukkes med tre metadatafelt på eksisterende Purchase
Receipt Item for deklarasjonsgrunnlag i NOK, ekspedisjonsdato og referanse.
Eksisterende vareavgiftsmal velger kode 85. Mottaket er den faktiske varen,
også når den ikke lagerføres; ingen ny deklarasjonsdokumenttype opprettes.
Leverandørfakturaen velger kode 20/21/22 og rapporteres ikke på nytt som
innførsel. Ingen summer fra leverandørfakturaen gjettes som deklarasjonsgrunnlag.

1. Registrer vanlig varekjøp og mottak med leverandørens valuta og kurs.
2. Behold deklarasjonen som privat vedlegg. For innførsel med MVA brukes
   ordinært Journal Entry: native fakturadato/-referanse merkes som
   ekspedisjonsdato/deklarasjonsreferanse når 81/82/83/84 velges. Dokumentert
   grunnlag føres på utgående linje; inngående fradrag er separat.
3. For kode 85 registreres dokumentert grunnlag, dato og referanse direkte
   på varemottaket. Kladd kan fullføres senere. Bokføring krever utfylte felt.
4. Bruk vanlig Landed Cost Voucher til toll/frakt og ikke-fradragsført MVA
   som skal inngå i lagerkost. Referer faktisk kostnadsfaktura; ikke før
   samme kostnad to ganger. Leverandørbetaling bruker ordinær valutaflyt.
5. MVA-spesifikasjonen velger deklarasjonsperioden fra ekspedisjonsdatoen,
   uavhengig av senere hovedbokspostering. Den viser deklarasjonsreferansen.
   Native periodelås kontrolleres også ved endring av deklarasjonsmetadata.

En omberegning av opprinnelig deklarasjon beholder opprinnelig periode;
etterdeklarering med ny ekspedisjonsdato behandles etter det nye dokumentet.
Native reversering kopierer opprinnelig referansedato. Ny dato skal bare velges
når dokumentasjonen faktisk begrunner dette. Vareretur/kreditnota skal ikke
på egen hånd tilbakeføre deklarasjonen. Metadatarettelser bruker native Version;
økonomiske rettelser bruker kjernens bilag. Eksisterende bokførte bilag uten
deklarasjonsdato omskrives ikke automatisk.

Ikke-registrerte foretak fører faktisk innførsels-MVA betalt til Tolletaten/
speditør som kostnad eller lagerkost, uten egenberegnet utgående innførsels-MVA.
Eventuelt senere tilbakegående fradrag må knyttes til kvalifiserte anskaffelser
og dokumentasjon, ikke antas fra registreringsdato alene. Skatteetatens
[gjeldende § 8-6-veiledning](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-8/M-8-6/M-8-6.2/)
angir krav i meldingen for registreringsterminen og oppbevaring av dokumentasjonen.

Prøvene dekker native mottak/faktura, fysisk ikke-lagerført vare, kode 85 uten
hovedbok, versjonering/periodelås, 25/15-prosentbilag, korreksjonsdato, rollekrav,
valutabetaling, LCV og oppgjør. Faktisk innsending i Skatteetatens portal og
særskilte importprosedyrer er ikke kvalifisert. Automatisk deklarasjonsinnlesing
er ikke nødvendig for denne manuelle dokumentbaserte standardflyten.
