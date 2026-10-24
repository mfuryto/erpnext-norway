# MVA-fradrag for lager og driftsmidler

App 0.4.3 bruker ERPNexts ordinære innkjøpsordre, varemottak, innkjøpsfaktura,
retur, avgiftsmaler og verdsetting. Ikke-fradragsført MVA inngår i kostnaden;
appens fradragsvalg konfigurerer kjernens prosentsatser og Valuation and Total.
Kjernen beregner beløp, lagerverdi, driftsmiddelkostnad og hovedbok.

## Vanlig registrering

Velg vareavgiftsmal og **MVA-fradrag i prosent** på varelinjen. Feltet finnes nå
på innkjøpsordre og varemottak i tillegg til innkjøpsfaktura. Standardkoblingen
fører valget videre mellom dokumentene. Fullt fradrag fortsetter å bruke vanlig
vareavgiftsmal. Egen mal velges bare for delvis/intet fradrag.

Lageroppsettet må være ferdig i ERPNext: lagerkonto, mottatt-men-ikke-fakturert-
konto og eventuell løpende lagerføring. For driftsmidler brukes ordinær kategori,
anleggskonto, plassering og mottakskonto. Dette er eksisterende ERPNext-oppsett.

For ikke-fradragsført MVA på lager/driftsmidler må det finnes en egnet konto med
native type **Kostnader inkludert i verdsettelsen**. Appen bruker en entydig
slik konto fra avgiftsradene, eller fra foretakets eksisterende kontoplan. Ved
flere kandidater må riktig konto velges i avgiftsradene. Appen oppretter ingen
konto og endrer ikke eksisterende kontonumre eller kontotyper for dette valget.
Det finnes ikke et eget Company-felt for denne kontoen i den låste versjonen.

Fradragsprosenten er brukerens regnskapsmessige vurdering. Den skal ikke utledes
fra varenavn eller leverandør alene. Se [Skatteetatens regler om forholdsmessig
fradrag](https://www.skatteetaten.no/rettskilder/type/handboker/merverdiavgiftshandboken/gjeldende/M-8/M-8-2/).

## Endret fradrag etter mottak

Når fakturaens fradrag avviker fra mottaket, oppretter appen et ordinært **Bilag
for tilleggskostnader**. Beløpet er differansen mellom kjernens eksisterende
avgiftsdetaljer, ikke ny MVA-beregning. Bilaget peker på fakturaen og det native
mottaket. ERPNext korrigerer mottakets verdi, hovedbok og eventuell senere
lagerføring. Native periodestenging, rettigheter og driftsmiddelkrav gjelder.

Ved delfakturering fordeles mottakets eksisterende avgiftsbeløp kumulativt etter
native lagerantall. Siste øre blir dermed med når hele mottaket er fakturert.
Positive og negative justeringer bruker separate native bilag ved behov;
det opprettes ingen nullbilag eller egen hovedbok.

Kansellering av fakturaen kansellerer dens justeringsbilag med kjernens vanlige
kansellering. Mottakets tidligere verdi tilbakeføres. Både varemottak og
kostnadsfordelingsbilag med vedlegg bevares etter bokføring/kansellering.

## Retur og kreditnota

Bruk vanlig retur fra varemottaket. Når faktura allerede finnes, brukes dens
faktiske opprinnelige avgiftsbehandling. Ved flere mulige fakturaer velges
opprinnelig faktura i det eksisterende feltet på returlinjen. Returantallet må
passe fakturaens gjenstående antall. Returner ulike fakturabehandlinger på egne
linjer/dokumenter. En uberegnet eller blandet fordeling skal ikke gjettes.

Kreditnotaen kobles til tilhørende innsendte returmottak. Ved flere alternativer
kan riktig returmottak velges i det eksisterende mottaksfeltet. Originale satser
beholdes selv om avgiftsmalen senere er endret. Returkladden viser behandlingen
gjennom kjernens vanlige forhåndsberegning før lagring. Ingen ny returveiviser
eller etterfølgende manuell hovedboksretting innføres.

## Avgrensning og prøver

Prøvene omfatter direkte lagerkjøp med 60/0/100 % fradrag, delkreditnota,
kansellering, ordre/mottak/faktura med endret fradrag i begge retninger,
faktura før mottak, retur uten faktura, driftsmiddelkjøp og delfakturering.
Fasiten for 1 000 + 250 MVA med 60 % fradrag er 1 100 i lager-/driftsmiddelkost,
150 inngående MVA og 1 250 leverandørgjeld. Native Asset kan fortsatt opprettes
manuelt; appen slår ikke på automatisk oppretting mot brukerens valg.

Ved endring av driftsmiddelverdsetting krever native kostnadsfordeling at de
berørte Asset-dokumentene finnes og er kladder. Innsendte driftsmidler eller
låste perioder omgås ikke. Regnskapsmessig og skattemessig avskrivning er fortsatt
ulike spørsmål; dette er ikke skattemessig saldoregel eller årsgrunnlag.

Kjernen avviser flere fakturalinjer mot samme mottakslinje. Denne regelen
beholdes. Ved flere returlinjer på samme returmottak kan kildelinjen velges
i det eksisterende mottakslinjefeltet på kreditnotaen. Listen viser linjenummer,
antall og opprinnelig MVA-fradrag. En eksplisitt ugyldig linje avvises; den
skal ikke stille byttes til en annen mulig kilde.

Flere varelinjer kombinert med MVA-verdsetting på frakt via On Previous Row er
fortsatt et åpent kjerneavvik. Den kombinasjonen åpnes ikke av denne leveransen.
Utland/import og resten av [MVA-planen](vat-plan.md) er heller ikke ferdig med
lagerdelen. Nettleser, backup/restore og CI kvalifiserer de beskrevne prøvene,
ikke brukerens faktiske konto-/fradragsvalg eller generell norsk etterlevelse.

## Påvist gap og minste tilpasning

Kjernen lagrer allerede pr_detail, men skjuler det som Data-felt. Når flere
returlinjer på samme mottak er mulige kilder, er valg av foreldredokument alene
utilstrekkelig. App 0.4.3 viser det eksisterende linjefeltet som Frappe Autocomplete
på kreditkladden, med linjenummer, kildeantall og MVA-fradrag. Kilden leses med
ordinær dokumenttilgang. Kjernens antalls-, duplikat- og bokføringskontroller
beholdes. Ingen ny kildetabell, returveiviser eller avgiftsberegning trengs.

Prøven bruker ett mottak og én fakturalinje, to returlinjer med antall 1 og 3,
og en kreditnota med én linje mot hver returlinje. Alle berørte hovedbokskontoer
går i null. Et eksplisitt valgt returantall som er for lite, avvises selv om en
annen linje på samme returmottak har nok antall.
