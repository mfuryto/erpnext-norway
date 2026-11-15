# Sluttføring av hovedplanens punkt 7

Punkt 7 gjelder ett norsk ENK uten ansatte, NOK og kalenderåret 2026, med
sporbart årsgrunnlag til næringsspesifikasjonen. Full personlig
skatteberegning og systeminnsending er uttrykkelig ikke bestilt. EHF starter
først etter at dette omfanget er sluttført og kvalifisert.

## Gjenstående krav og valg av funksjon

| Krav | Eksisterende funksjon | Konkret gap som skal lukkes |
| --- | --- | --- |
| Inntekter, kostnader, IB, bevegelse og UB | Native resultatregnskap og saldobalanse | Vis de faktiske kontolinjene og årsspesifikke næringsposter sammen med skatteavstemmingen, også etter PCV og for brukte deaktiverte konti. |
| Næringsposter for ENK uten regnskapsplikt | Skatteetatens offisielle 2026-kodeliste; eksisterende kontokoblinger | SAF-T-listen er ikke identisk. Gjenbruk kodelistedata og ordinære kontofelt; ikke bygg en ny hovedbok eller bruk SAF-T-kode ukritisk. |
| Øvrige skattesaldoer og gevinst-/tapskonto | Native Asset/Manual og ordinære bilag; eksisterende a/d-saldoberegning | Norske skatteposisjoner og årets skattemessige fradrag/inntekt må følge kildene uten ny bokføringsmotor. Samlesaldo, per-driftsmiddel-saldo og per-bygg-saldo må skilles. |
| Personinntektsgrunnlag | Native resultat og balanse, Skatteetatens foretaksmodell | Kapitalposter, foretaksgjeld, dokumentert skjerming og fremført negativ personinntekt er egne årsopplysninger. Ukjent skjerming skal ikke bli et oppdiktet nullfradrag eller en lånt aksjerente. |
| Formuesgrunnlag | Native balanse og dokumenterte skatteverdier | Skill bokverdi, skatteverdi og verdi før verdsettingsrabatt. Portalens rabatt/gjeldsreduksjon skal ikke utføres dobbelt. |
| Eierbevegelser og årsavslutning | Kvalifiserte native bilag, PCV og rapportfiltre | Samle sporbarheten i årsgrunnlaget og behold resultatet etter stenging. Ingen ny eierreskontro eller avslutningsside. |

ERPNexts **Financial Report Template** prøves før egen kategorisering velges.
Den faktiske prøven viste 200 på aktiv kostnadskonto og null etter at samme
brukte konto ble deaktivert. Rapportmalen filtrerer `disabled == 0`, og kan
derfor ikke alene brukes som fullstendig årsgrunnlag. Standardrapportene er fortsatt fasit for beløp; nye tilpasninger skal begrenses
til norske skattefakta, koblingsdata og presentasjon av de native resultatene.
Beregnede årsrapporter lagres ikke i et parallelt historikkregister.

## Faglige forutsetninger

- Inngående skattesaldo, private forhold og andre faktiske opplysninger kan
  ikke utledes sikkert fra kontonumre. De skal ha dokumentert årsunderlag.
- Skjermingsrente for ENK er forskjellig fra aksjonærrenten. Skattedirektoratet
  fastsetter årsatsen i januar etter inntektsåret. Ingen 2026-rente skal
  konstrueres før den er publisert.
- Skjermingsgrunnlag før fradrag for gjeld brukes i renteavgrensningen.
  Nettogrunnlaget for selve skjermingen er et annet beløp. Referansekode som
  bruker ett beløp til begge formål må ikke kopieres ukritisk.
- Brutto formuesgrunnlag og gjeld vises for portalbehandling. Personlige
  eiendeler og samlet personlig gjeld er ikke foretakets hovedbok.

Kilder: [ENK og leveringsmåte](https://www.skatteetaten.no/bedrift-og-organisasjon/skatt/skattemelding-naringsdrivende/enk/),
[foretaksmodellen E-5-4.2](https://www.skatteetaten.no/rettskilder/type/handboker/skatte-abc/gjeldende/e-5-enkeltpersonforetak--beregnet-personinntekt-foretaksmodellen/E-5.016/E-5.018/),
[offisiell skjermingsrente](https://www.skatteetaten.no/satser/skjermingsrente-for-aksjer-og-enkeltpersonforetak/),
[verdsettingsrabatt](https://www.skatteetaten.no/nn/person/skatt/hjelp-til-rett-skatt/verdsettingsrabatt-ved-fastsetting-av-formue/),
[gevinst- og tapskonto](https://oppslag.rettskilder.skatteetaten.no/rettskilder2/type/handboker/skatte-abc/gjeldende/skatteabc-G-4/skatteabc-G-4.001/skatteabc-G-4.002).

## Dokumentert behandling uten ny bokføringsfunksjon

- Vanlig kjøp/salg/kreditnota og native utrangering/tilbakeføring er kildene.
  For manuelle driftsmiddelbevegelser velges skattemessig betydning på det
  ordinære bilagets eksisterende kontolinjer før bokføring. Faktisk hovedbok
  avstemmes mot de merkede linjene. Ingen ny bilagsgenerator innføres.
- Tomt og tidsbegrensede rettigheter er ikke vilkårlig saldogruppe a.
  Bruk native bokføring/avskrivningsplan og dokumentert årsfradrag utenfor saldo.
  [Immaterielle rettigheter, D-4-2.2](https://www.skatteetaten.no/rettskilder/type/handboker/skatte-abc/gjeldende/d-4-driftsmiddel--immaterielt-ikke-fysisk-driftsmiddel/D-4.002/D-4.007/).
- Negativ b ved årets slutt overføres til gevinst-/tapskonto. a/c/d/j følger
  negativ-saldo-reglene; realiserte e–i overføres uten årets saldoavskrivning.
  [D-2-8.6 og D-2-10](https://oppslag.rettskilder.skatteetaten.no/rettskilder2/type/handboker/skatte-abc/gjeldende/skatteabc-D-2/skatteabc-D-2.105/skatteabc-D-2.151).
- Vurdert endring i bokført/skatteverdi på øvrige eiendeler/gjeld kan tas inn
  én gang i skattebroen. Saldoavskrivning kan ikke også tas som denne forskjellen.
  Formue vises før rabatt; privat bruk som allerede er trukket fra bokført kostnad,
  legges ikke til på nytt. Riktig fradragsrett krever de faktiske vilkårene.
- Native hovedbok/resultat/saldobalanse, ordinære vedlegg og standard
  rapporteksport beholder ansvar for beløp, historikk, tilgang og dokumentasjon.

## Kvalifisering

`tests/runtime-enk-core.py`, `runtime-enk-tax.py` og `runtime-enk-annual.py`
prøver ordinær regnskapsbruker, eieroppgjør/personlig skatt, native årsavslutning,
kjøp/kreditnota, native manuell avskrivning/kansellering, salg/utrangering/
gjenoppretting og uavhengige skattesaldoer på samme konto. Grensetilfellene
omfatter fullt bokavskrevet driftsmiddel, dokumentert lagerforskjell, tomt,
tidsbegrenset rettighet, privat telefon, endret kostpris, skattenøytral bevegelse,
uvurdert skjerming, formuesverdi før rabatt og vern mot dobbel korreksjon.

Den rene regneprøven dekker gruppesatser og grensen rett under/på 30 000,
gevinst-/tapsoverføring, valgt fradrag og fremføring av negativ personinntekt.
Alle 131 postnavn/fortegn sammenlignes mot den låste offisielle 2026-XML-kilden.
Native nettskjema og rapport vises på bokmål for vanlig eier uten System Manager.
Skjema, kildepekere, rapportgrunnlag og private rapportbytes prøves på nytt etter
migrering av eksportert backup til en tom database.

Dette er teknisk kvalifisering av avtalt årsgrunnlag, ikke en generell erklæring
om norsk etterlevelse. Årets faktiske underlag, private forhold og innlevering må
fortsatt behandles. Direkte skatteinnsending og full personlig skatteberegning er
ikke del av punkt 7. EHF er et eget neste arbeid med SendRegning.
