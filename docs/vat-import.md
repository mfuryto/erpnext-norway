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

Automatisk deklarasjonsinnlesing, deklarasjonsdato som periode, kobling til
leverandørfaktura/mottak, varefordeling, toll/frakt, lagerverdsetting og særskilte
importprosedyrer gjenstår. Ikke bruk teknisk grønn prøve som generell påstand om
norsk importetterlevelse. Kvartalsbehandling før registrering er et separat åpent
punkt i vat-foreign-services.md.
