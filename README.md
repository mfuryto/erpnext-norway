# ERPNext Norway

Norsk tilpasning for ERPNext, med vekt på vanlig arbeidsflyt og gjenbruk av standardfunksjoner.

**Status:** Driftsgrunnlag og overgang fra en eksisterende Compose-installasjon.
Den norske modulen er ennå ikke implementert eller godkjent for ordinær norsk bokføring.
Installasjonen inneholder standard ERPNext; referansearbeidet er ikke automatisk aktivert.

- Vedvarende Docker Compose-oppsett med data under prosjektets private `data/`-mappe.
- Native ERPNext-backup med privat driftskonfigurasjon og prøvd gjenoppretting.
- [Norsk kontoplan](docs/norwegian-chart.md) for den native importeren, med kilde/lisens
  og prøvd salgs-, kjøps- og bankflyt uten en egen hovedbok.
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
