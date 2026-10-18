# Native nummerserier og bilagsvern

Prøv eksisterende funksjoner før tilleggskode. Kilden som undersøkes er Frappe
16.52.0, med ERPNext 16.51.1. `tests/runtime-native-controls.py` er en isolert
syntetisk prøve; den er ingen migrering på driftsserveren.

## Nummerserier

**Document Naming Rule** har egen transaksjonell teller per regel, radlås,
vilkår, prioritet, prefiks, antall sifre og startteller. F/K/T og uavhengige kunde-
og leverandørkoder trenger derfor ingen ny tellertabell eller egen nummermotor.
Den vanlige eierrollen skal ikke få System Manager for å endre serieoppsettet.

Startteller er sist brukte nummer: 40 med prefiks F og seks sifre gir F000041.
Kunde og leverandør bruker separate regler, også når begge skal ha fem sifre.
Native prefikstolking ignorerer punktum; `.` kan brukes for kode uten prefiks.
Dette er en teknisk oppsettsdetalj, ikke en ekstra brukerflate.

Det gjenstår å kvalifisere samtidighet, serieendring etter bruk, kansellering,
amendment, omdøping og sletting. Native navngiving skjer ved kladdlagring, og
amendment behandles før Document Naming Rule. En maskedefinisjon alene beviser
derfor ikke at nummerserien er tilstrekkelig beskyttet.

Skatteetatens [uttalelse om nummerering av salgsdokumenter](https://www.skatteetaten.no/rettskilder/type/uttalelser/prinsipputtalelser/nummerering-av-salgsdokumenter/)
krever at fullstendighet kan etterprøves, og at den enkelte bruker ikke enkelt kan
overstyre nummereringen. Det er ikke grunnlag for å finne opp en separat teller
bare fordi kjernen navngir kladden. Først prøves beskyttelse av native nummer og
bevaring av dokumentene, med minst mulig tillegg for et påvist gap.

## Vedlegg

Native DocType-egenskap **protect_attached_files** kan settes med Property Setter.
Frappe File kontrollerer egenskapen før fysisk sletting. Et bokført dokument kan
derfor beskyttes med eksisterende funksjon uten ny filoppbevaring eller erstatning
av File-kontrolleren.

Kildegjennomgangen viser samtidig at kansellerte dokumenter tillater sletting når
brukeren kan slette referansedokumentet. Endring av `attached_to_*`, URL, innhold,
tilgangsstatus og delt filinnhold må prøves særskilt; et vern på sletting alene er
ikke et fullstendig bevaringsvern. Eventuelle tillegg skal gjenbruke native File,
vedlegg og private rettigheter, uten parallelt bilagsarkiv.

## Kilder

- [Native navngiving](https://docs.frappe.io/framework/user/en/basics/doctypes/naming).
- [Document Naming Rule i låst Frappe](https://github.com/frappe/frappe/blob/v16.52.0/frappe/core/doctype/document_naming_rule/document_naming_rule.py).
- [Native File og validate_protected_file](https://github.com/frappe/frappe/blob/v16.52.0/frappe/core/doctype/file/file.py).

## Prøvd resultat

Den isolerte native prøven har bekreftet:

| Prøve | Faktisk resultat |
| --- | --- |
| F/K/T, valgfrie prefiks og starttellere | F000041, K000008 og T000013; navn beholdes ved bokføring. |
| Kunde og leverandør | 00011 og L-00021, adskilt fra visningsnavn. |
| Tilbakerulling av ikke-committet opprettelse | Native teller rulles tilbake; neste forsøk får samme navn. |
| Vanlig eier uten System Manager | Kan ikke endre Document Naming Rule. |
| Slett tidligere lagret kladd etter at neste finnes | Tillates; F000042 forsvinner mens F000043 beholdes. Bevaringsgap. |
| Amendment av kansellert kreditnota | K000008-1, fordi amendment går foran navngivingsregelen. Må avklares mot ønsket nummerflyt. |
| Slett privat vedlegg på bokført faktura med native vern | Administrator avvises før filen fjernes fra disk. |
| Slett vedlegg på kansellert faktura | Administrator får lov; filen fjernes. Bevaringsgap. |
| Frakoble beskyttet vedlegg med ordinær File.save | Tillates. Bevaringsgap. |

Prøven ruller tilbake alle sine konfigurasjons-/bilagsendringer og rydder metadata-
cache før den ordinære backup-/restore-prøven. Samtidige opprettelser og øvrige
endringsveier er ikke ferdig kvalifisert. En forventet tillatt operasjon i denne
kartleggingen er et dokumentert gap, ikke en godkjent norsk arbeidsflyt.

Ingen generell norsk regnskapsaksept eller ferdig dokumentbevaring følger av disse
enkeltfunksjonene.
