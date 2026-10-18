# ERPNext Norway

Norsk tilpasning for ERPNext, med vekt på vanlig arbeidsflyt og gjenbruk av standardfunksjoner.

**Status:** Driftsgrunnlag og første minimale norske app for dokumentvern og native
nummeroppsett. Ikke godkjent for ordinær norsk bokføring. Standard Compose bruker
fortsatt kjernen; appen aktiveres gjennom den særskilte oppdateringsrutinen.

- Vedvarende Docker Compose-oppsett med data under prosjektets private `data/`-mappe.
- Native ERPNext-backup med privat driftskonfigurasjon og prøvd gjenoppretting.
- [Minimal norsk app](docs/norwegian-app.md) med native nummerserier, dokument-/vedleggsvern
  og oppdatering gjennom full backup, native installasjon og migrering.
- [Norsk kontoplan](docs/norwegian-chart.md) som standardmal for nye Norway/NOK-selskaper,
  med kilde/lisens og native kontooppretting. CSV beholdes for eksplisitt valgt overgang.
- Native norsk modulprofil som viser Lager og skjuler Produksjon, Prosjekter og Kvalitet
  som standard, med mulighet for senere visning gjennom brukerinnstillingene.
- Klargjøring før portbytte og stopp av tidligere installasjon uten sletting.
- Plan for norsk kontoplan, MVA, dokumentkrav, SAF-T, EHF og årsgrunnlag.
- ERPNext-kjernen først; tillegg brukes som referanser, ikke som automatisk produktgrunnlag.

Se [installasjon og overgang](docs/runtime.md), [plan og overlevering](docs/handover.md)
og [kjerneoppsett og norske gap](docs/core-minimum.md), samt
[referanser](references/README.md). Hemmeligheter og driftsdata skal aldri i Git.

Utvikling skjer på `staging`. `main` er stabil kanal og mottar endringer gjennom PR
etter relevante tester. Norsk regnskapsmessig produksjonsaksept er en egen milepæl.
