# Tjenestekjøp før MVA-registrering

## Kildegrunnlag før implementasjon

Lovens § 11-3 første ledd krever at foretakets aktuelle kjøp samlet overstiger
2 000 NOK per kvartal før avgift beregnes. Nøyaktig 2 000 utløser ikke plikten.
Kilde: [Merverdiavgiftshåndboken § 11-3](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-11/M-11-3/M-11-3.2/).

Kreditnota følger som utgangspunkt dokumentets egen periode; en senere reell
prisreduksjon er forskjellig fra retting av en opprinnelig feil. Vi tolker dette
slik at en senere kreditnota ikke i seg selv flytter et opprinnelig korrekt
kjøp tilbake til en annen periode. Kilde: [tidfesting etter § 15-9](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-15/M-15-9/M-15-9.3/).

Skatteetatens [publiserte meldingsregler](https://skatteetaten.github.io/mva-meldingen/omvendt/forretningsregler/)
belyser de tidligere åpne kombinasjonene: R108 krever merknad ved negativt
grunnlag; R117 har et uttrykkelig alternativ for ikke-positivt grunnlag;
R118/R119 skiller første melding fra korrigering. R121 avviser særskilt melding
ved ordinær plikt hele perioden, mens R123 behandler delvis periode som avvik.
Dette støtter negative korreksjoner og separate meldingsgrunnlag ved overgang.
Reglenes tekniske tillatelse av 2 000 er ikke lovhjemmel for å svekke lovens
strenge grense. Portalen brukes ved levering; ingen lokal kopi av validerings-
eller innleveringssystemet bygges.

## Prøvd kjerne og dokumentert gap

Faktiske native Tax Withholding-prøver finnes i runtime-vat-threshold-core.py.
Terskelen gjelder part, utløses ved likhet og trekker fra leverandørgjelden;
full kreditnota nullstiller heller ikke historikken. Den dekker ikke norsk
kvartalsplikt. Ordinary Invoice og kjerneberegneren kan derimot bevare originalens
beløp og levere beregnede avgiftsdetaljer, og Journal Entry fører allerede
periodens øvrige MVA-justeringer. Ingen egen sats-, avrundings- eller hovedboksmotor
trengs.

Minste tillegg er et linjevalg på ordinært kjøp som bevarer kvartalsgrunnlaget,
summering på tvers av leverandører og ordinære Journal Entry-differanser når
plikten oppstår eller bortfaller. Native beregner leverer MVA-beløpene. Bokførte
leverandørfakturaer omskrives ikke. Kreditnota kopierer kildelinjens behandling,
og godkjent registrering styrer nye kjøp. Senere vedtak som endrer allerede
bokførte perioder må følge vanlig kansellering/endring og korrigert melding.
Dette er en ordinær korrigeringsflyt, ingen ny registreringshistorikk.

## Meldingskategori er forskjellig fra avgiftsbehandling

Et kjøp før registrering beholder sitt lagrede kvartalsvalg. En senere kreditnota
beholder beregnet avgift og manglende fradrag fra kilden, men dersom foretaket da
har ordinær plikt, tilhører kreditnotaen ordinær melding. Bare grunnlaget for
ikke-registrert del summeres mot kvartalsgrensen. Linjevalg og meldingstype
lagres på native faktura; en senere Company-endring omskriver dem ikke.
Meldingsregelen R121 begrunner skillet, sammen med tidfestingen etter § 15-9.

Et tilgrensende kodegap ble påvist ved gjennomgang: en eksplisitt nullsats- eller
eksportmal kunne bevare ordinær meldingskode på en salgsfaktura før registrering.
Før godkjent virkningsdato skal nye salg derfor beholde kode uten MVA-behandling;
en allerede bokført originals kreditnota beholder fortsatt originalens kode.
Kjernens avgiftsbeløp endres ikke av rapporteringsklassifiseringen.

## Kontroll mot portalens kodebruk

Skatteetatens [informasjonsmodell](https://skatteetaten.github.io/mva-meldingen/mvameldingen/informasjonsmodell/)
viser separate utgående- og fradragslinjer under samme kode 86/88 for tjenester
og 81/83 for varer. Fradraget flyttes derfor ikke til ordinær innenlandsk kode 1.
Rapportens separate kolonner for beregnet utgående og inngående fradrag følger
dette skillet. Kode 0/7/20/21/22 er regnskapsklassifisering og skal ikke overføres
til MVA-meldingen. Innlevering skjer fortsatt i Skatteetatens portal.

## Vanlig registrering og kvalifiseringsomfang

Velg «Tjenestekjøp fra utlandet – kvartalsgrunnlag før MVA-registrering» i
fakturalinjens eksisterende vareavgiftsmal. Leverandørgjelden endres ikke av
kvartalsavgiften. Ved utenlandsk valuta oppgis leveringsdato og dokumentert
MVA-kurs per linje; vanlig bokføringskurs beholdes separat. Velg registrert
omvendt behandling på nye kjøp fra godkjent virkningsdato.

Rapportens «Alle MVA-posteringer» viser regnskapsoversikten. Velg særskilt
kvartalsmelding og helt kalenderkvartal, eller ordinær melding og aktuell termin,
før grunnlag bevares og oppgjør opprettes. Standard Journal Entry, bankføring
og private File-vedlegg brukes. Melding og kvittering fra portalen legges ved
som tidligere. Første nullmelding skal ikke leveres; retting av tidligere levert
melding vurderes i portalen, uten en lokal kopi av innleveringshistorikken.

Prøvene dekker flere leverandører, grensen 1 999,99/2 000/2 000,01, avrunding,
kreditnota innenfor og over kvartaler, ordinær melding ved senere registrering,
retroaktiv datoendring gjennom native kansellering/endring, NOK-rabatt/frakt,
valutaordre/faktura/kreditnota/betaling, refusjon, periodelås, samtidig bokføring,
vanlig eier i nettleser og bevaring etter eksportert backup/gjenoppretting.
Kjernens satsvern og vanlige transaksjonelle tilbakerulling brukes uendret.

Denne leveransen gjelder 25 % tjenester før registrering. Lav sats, tillegg på
valutakjøp og de øvrige åpne delene av vat-plan.md er ikke samlet kvalifisert av
kvartalsprøvene. Ingen faktisk innlevering eller oppdatering av drift er utført.
