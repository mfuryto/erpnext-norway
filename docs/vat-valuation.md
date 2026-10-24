# MVA-fradrag for lager og driftsmidler

App 0.4.4 bruker ERPNexts ordinære innkjøpsordre, varemottak, innkjøpsfaktura,
retur, avgiftsmaler og verdsetting. Ikke-fradragsført MVA inngår i kostnaden;
appens fradragsvalg konfigurerer kjernens prosentsatser. Ordinære nettogrunnlag
bruker Valuation and Total. Frakt med flere lager-/tjenestelinjer bruker Total
og ordinære kostnadsfordelingsbilag basert på kjernens avgiftsdetaljer.
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

Flere lager-/tjenestelinjer med MVA på frakt via On Previous Row er prøvd i
app 0.4.4. Kombinasjonen med driftsmidler er fortsatt sperret: native negativ
kostnadsfordeling på retur krever et Asset-dokument på returdokumentet, som
ikke opprettes i den ordinære returflyten. Dette gjelder også automatisk
opprettede driftsmidler. Manuell oppretting og beskyttelse av innsendte
driftsmidler omgås ikke.
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

## Grunnlaget for frakttilpasningen

Native Valuation and Total på On Previous Row fordeler ikke MVA-kostnaden
riktig ved flere varelinjer. Direkte kjerneprøver med Total og et ordinært
Landed Cost Voucher bruker allerede beregnede Item Wise Tax Detail-beløp og gir
riktig lagerverdi, full/delvis kreditnota og kansellering. Dette er konfigurasjon
og native bilagskoblinger; ingen ny avgifts- eller verdsettingsberegning.

Appen bruker samme native kostnadsfordeling på varemottak, fakturadifferanse
og retur. Automatisk opprettede fordelingsbilag på et mottak har et entydig
merke for ordinær kansellering; den eksisterende native
mottakslenken beholdes. Fakturajusteringer bruker den eksisterende fakturalenken.
Driftsmiddelkrav og uavklarte endringer i fraktens beregningsgrunnlag skal fortsatt
avvises inntil hele den aktuelle native kjeden er prøvd. Asset-oppretting eller
kjernens beskyttelse av innsendte Asset-dokumenter skal ikke overstyres.


## Fraktflyt i app 0.4.4

På lager-/tjenestekjøp med flere linjer fører appen den ikke-fradragsførte
lager-MVA-en som Total og bruker kjernens allerede beregnede linjebeløp i et
ordinært Bilag for tilleggskostnader. Dette gjelder direkte lagerfaktura,
varemottak og retur. Ved endret fradrag på en mottaksbasert faktura fordeles bare
differansen. Negative beløp bruker ordinære negative kostnadsfordelingsbilag.
Mottakets automatiske bilag er merket **Norsk MVA-fordeling** og bruker den
native mottakslenken; fakturajusteringer beholder den eksisterende fakturalenken.
Kansellering tilbakefører disse bilagene med kjernen og bevarer dokumentasjonen.
Manuelle kostnadsfordelingsbilag kanselleres ikke som om appen opprettet dem.

Native innkjøpsskjerm oppdaterer også forhåndsberegningen når fraktavgiftsradene
endres etter fradragsvalget. Ved flere satser angis avgiftsgrunnlagene på de
ordinære avgiftsradene. Appen skal ikke gjette at en eksplisitt konfigurert sats
har samme fraktgrunnlag som en annen. Ved pris inklusive MVA på varer og frakt
eksklusive MVA må den native innstillingen for inkludering angis per grunnlag;
MVA-kostnadsradene følger den tilsvarende avgiftsraden.

Prøvd: direkte kjøp, begge native On Previous Row-grunnlag, inklusiv varepris med
eksklusiv frakt, 25/15 % med 60/0 % fradrag, flere lagerlinjer med ulikt fradrag,
ordre/mottak/faktura med 60→60, 100→60, 60→100 og 60→30 %, full retur/kreditnota,
delfakturering med siste øre, delretur og vanlig avrunding samt kansellering.
1 000 lager + 1 000 tjeneste + 100 frakt ved 25 % og 60 % fradrag gir 1 105
lager, 1 105 tjenestekostnad, 100 fraktkostnad, 315 inngående MVA og 2 625 gjeld.
Kjernen styrer eventuell avrundet gjeld og fører avrundingsdifferansen selv.

Endring av selve avgiftsgrunnlagets struktur mellom mottak og faktura er ikke
generelt kvalifisert for retur. Eksisterende automatiske kostnadsrader må ha et
tilsvarende avgiftsgrunnlag, og referansen på returen må passe den opprinnelige
fakturaen. Tvetydige grunnlag avvises fremfor å gjette eller endre hovedboken.


En annen native verdsettingsrad som allerede kapitaliseres av kjernen, tas ikke
med en gang til i det automatiske fraktbilaget. Bare merkede Total-rader brukes
ved første fordeling. Dersom ulike satser har ulik MVA-inkludering på samme
MVA-kostnadskonto og samme grunnlag, avvises kombinasjonen: én native avgiftsrad
kan ikke ha to ulike inkluderingsinnstillinger. Innstillingen må være lik, eller
kostnadskontoene må skilles gjennom ordinært kontooppsett.
