# SAF-T: gjenbruk og gjenstående eksport

Status 28. oktober 2026: datakildene er prøvd i ERPNext 16.52.1 / Frappe
16.53.0. Norsk SAF-T-nedlasting er **ikke levert**. Eksporten skal bruke den
bokførte hovedboken og eksisterende bilags-/partregistre, uten egen hovedbok.

## Format og årsversjon

[Skatteetatens dokumentasjon](https://www.skatteetaten.no/bedrift-og-organisasjon/starte-og-drive/rutiner-regnskap-og-kassasystem/saf-t-regnskap/dokumentasjon/)
sier at 1.40 kan brukes nå og blir eneste gyldige format fra 1. januar 2027.
1.20/1.30 kan fortsatt brukes for regnskapsår 2026 og tidligere. Ny eksport
kvalifiseres derfor mot 1.40; det er ikke tilstrekkelig å endre versjonsteksten.

Det offisielle [skjemaet og eksemplene](https://github.com/Skatteetaten/saf-t/tree/10c8fd82a6ff47e53385bc33c7638c5fde239a4f/SAF-T_Financial_1.4)
er undersøkt ved revisjon `10c8fd82a6ff47e53385bc33c7638c5fde239a4f`.
Kontogruppering må i tillegg følge offisiell liste for aktuelt inntektsår og
foretaksform. En norsk kontokode er ikke alene bevis på gyldig gruppering.
Gjeldende kilder inkluderer egne [gruppelister for 2025–2026](https://github.com/Skatteetaten/saf-t/tree/10c8fd82a6ff47e53385bc33c7638c5fde239a4f/Grouping%20Category%20Code%202025-2026).
2027-listene skal kontrolleres før støtte for det året erklæres ferdig.

## Prøvd kjerne før tilpasning

`tests/runtime-export-core.py` kjører på syntetisk norsk kontoplan med vanlig
eierbruker, både før og etter eksportert backup/gjenoppretting. Samme prøve
kjøres i grunnimaget og med den norske appen i Compose-testen.

| Krav | Faktisk kjerneprøve | Konsekvens for eksporten |
| --- | --- | --- |
| Kontoplan og transaksjoner | Native Data Export leverer CSV med 745 kontonumre og balanserte hovedbokslinjer og bilag. | Gjenbruk Account og GL Entry. Ingen import av en ny kontoplan for å eksportere. |
| Sporbarhet | Hovedboks-ID, bilagstype/-nummer, bokføringsdato, registreringstidspunkt og part er tilgjengelige. | Bevar kjernens referanser i XML. Bilagsdato, leverandørens nummer og øvrige opplysninger må hentes fra kildebilaget der de ikke følger GL. |
| Avstemming | Native General Ledger sitt radutvalg er identisk med aktive eksporterte GL-ID-er og debetsum. | Gjenbruk kjernens utvalg og kontroller mot kjernens rapporter. |
| Inngående saldo | Native kontoutvalg fra dagen etter de syntetiske posteringene gir bankens inngående saldo 275. | Periodens bevegelser og inngående saldo må skilles; et rent datofilter på eksporten er utilstrekkelig. |
| Reskontro | Kunde-/leverandør-ID-er finnes i lesbare masterregistre; netto reskontro er null etter faktura, kreditnota og betaling. | Kunder og leverandører må refereres konsistent. Åpne poster, fremmed valuta og flere reskontrokontoer gjenstår i SAF-T-fasiten. |
| Tilgang | Eieren kan eksportere konto/hovedbok og lese aktuelle parter, men får avvist Customer-eksport. Foretaksavgrensningen skjuler annen hovedbok. | Ikke gi globale eksportrettigheter eller bruke uavgrenset get_all som snarvei. En norsk nedlasting trenger egen eksplisitt adgangskontroll og avgrensning til tillatt foretak. |
| Kansellering | Native CSV beholder fire opprinnelige/motposter for et kansellert tolinjers bilag. Normal hovedbok utelater dem; eksplisitt kanselleringsfilter tar dem med. | Ikke anta at normalrapportens standardfilter er fullstendig eksporthistorikk. Behandling av motposter og perioder må kvalifiseres før SAF-T leveres. |
| Filformat | Native Data Export bygger CSV/Excel; ingen norsk AuditFile-eksport er funnet i den låste kjernen. | Det dokumenterte gapet er norsk XML-format, mapping og eksportkontroller, ikke bokføring eller saldoberegning. |

Kanselleringsprøven rulles tilbake og endrer ikke de eksisterende prøvebilagene.
Prøven er kildekvalifisering, ikke bevis på ferdig SAF-T eller regnskapsmessig aksept.

## Eksisterende norsk eksport undersøkt

ENK Norge har allerede en [SAF-T 1.40-bygger](https://github.com/Medpus/enk_norge/blob/94406e542ed991a8de237b9de44b8d1dd576b566/enk_norge/saft.py)
med MIT-lisens. Dens fem databasefrie byggetester er kjørt i det låste
ERPNext-imaget, mot det offisielle XSD-et ved revisjonen ovenfor: alle bestod.
Det omfatter XML med saldo/referanser, avgiftsmapping og avvisning av ubalansert
bilag, manglende mapping og duplikat konto-ID. Dette er en faktisk prøve av
mulig gjenbruk; det skal ikke skrives en konkurrerende XML-bygger før denne
kandidaten er ferdig vurdert.

Hele appen installeres ikke av den grunn. Frappe-adapteren leser egne
`enk_norge`-innstillinger og egne avgiftsbehandlinger og filtrerer på
`is_cancelled=0`. Den er ikke dermed kvalifisert for denne appens varelinjekoder,
import, kvartalsbilag, valuta og oppgjør. Fem byggetester viser heller ikke
korrekt årsgruppering eller full transaksjonsdekning. Ingen kode fra kandidaten
er kopiert inn eller blitt en produktavhengighet i denne arbeidspakken.

## Neste implementasjon og aksept

1. Prøv eksisterende bygger mot faktiske syntetiske ERPNext-uttrekk og gjeldende
   mapping. Velg dokumentert gjenbruk og bevar lisens/proveniens der den passer.
2. Kvalifiser fullstendig hovedboksutvalg: åpning, ordinære og kansellerte bilag,
   motposter, periodestenging, standard/alternative avskrivningsbøker og delår.
3. Koble kontoer til årsspesifikk gruppering og dokumenterte MVA-koder til riktig
   TaxTable/TaxInformation. Gjenbruk den leverte MVA-kildelesingen; ikke beregn
   avgiften en gang til eller gi alle kontoer en gjettet gruppering.
4. Eksporter foretak, kontoer, kunder/leverandører, åpning/slutt og transaksjoner
   med kilde-/betalingsreferanser. Prøv åpne poster og utenlandsk faktura/oppgjør.
5. Valider med offisiell XSD og kontroller referanser, bilagsbalanse, saldoer og
   avgiftsgrunnlag mot native rapporter. Et XSD-godkjent dokument alene er ikke
   tilstrekkelig regnskapsaksept.
6. Legg nedlastingen på naturlig regnskapssted, med norsk tekst og ordinære
   rettigheter. Prøv vanlig eier, avvisning av annet foretak og gjenoppretting.

Deretter følger [ENK og årsavslutning](handover.md#hovedplan-avtalt-søndag-18-oktober-kl-1844)
og [EHF](ehf.md). Hele hovedplanen er ikke ferdig med denne kildeprøven.
