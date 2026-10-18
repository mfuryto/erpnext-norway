# Referanser – ikke automatiske avhengigheter

ERPNext-kjernen prøves før ny kode. Disse prosjektene brukes til å forstå gap og
utforme testfasiter; de installeres ikke automatisk.

- [Dolibarr Norway](https://github.com/mfuryto/dolibarr-norway/tree/cc5cb151c1bca9eb4c6b84dd69305191e2e3ef29),
  versjon 0.86.0: norske krav, kontoplan, MVA- og SAF-T-mapping, årsgrunnlag og tester.
- [ENK Norge](https://github.com/Medpus/enk_norge/tree/94406e542ed991a8de237b9de44b8d1dd576b566),
  MIT: norsk ENK-referanse. Egen flate og avgrensninger skal ikke overtas ukritisk.
- [Peppol 4 ERPNext](https://github.com/Grynn-GmbH/peppol_4_erpnext/tree/9efe16be5ab5d2a338fe3612ecfc02344b45f382),
  MIT: tjenestespesifikk kobling, ikke kvalifisert norsk EHF i dette prosjektet.
- [Peppol Connect](https://github.com/maasanto/peppol-connect/tree/3bd618b237bfad1cf659c5445eeccb34b829076c), GPL-3.0.
- [SG Peppol](https://github.com/ahmadhuss/sg_peppol/tree/3b04a8f09c55b5f19398027c7437ac4137aaf616),
  MIT: Singapore-referanse, ikke et norsk regelsett.
- [Offisielt Frappe Docker-grunnlag](https://github.com/frappe/frappe_docker/tree/11d606208c3708cf999d50b7eb798032fc469f5f),
  MIT: tjenester/kommandoer brukt som referanse for vedvarende Compose. Demoens
  testpassord og midlertidige data brukes ikke.

Norske krav verifiseres mot Skatteetaten, Lovdata og relevante primærkilder.
Arbeidsflyt sammenlignes med leverandørdokumentasjon fra etablerte norske programmer.
Bevar original lisens og datakilde ved kopiering. Ingen kontoplan kalles NS 4102-
sertifisert bare fordi kontonumrene ligner. Les docs/handover.md for prøver og begrensninger.
