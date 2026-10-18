# Modulvisning som standard

Brukeren har presisert at det primært er menyene som skal skjules. Systemblokkering
inngår ikke. Vi bruker derfor kjernens Module Profile og User-innstillinger.

| Modul i kjernen | Norsk navn | Norsk standardprofil |
| --- | --- | --- |
| Stock | Lager | Skjult |
| Manufacturing | Produksjon | Skjult |
| Projects | Prosjekter | Skjult |
| Quality Management | Kvalitet | Skjult |

## Oppsett og senere valg

`deploy/module-visibility.py` oppretter den native modulprofilen **Norsk standard**
og bruker en native Property Setter som standardverdi for User.module_profile.
Nye brukere får dermed profilen gjennom kjernens ordinære dokumentoppretting.
Eksisterende systembrukere uten egne modulvalg får profilen første gang skriptet
kjøres. Eksisterende profiler og egne modulvalg bevares.

Oppsettet kjøres ved klargjøring av nye installasjoner. På eksisterende installasjon
kan det kjøres inne i den kjørende backend-containeren, uten reinstallasjon,
image-bytte eller restart. Skriptet lagrer at standarden er vurdert per bruker og
for nye brukere; gjentatt kjøring skal bevare senere valg. En eksisterende profil
med navnet Norsk standard overskrives ikke.

En bruker med nødvendige administrasjonsrettigheter kan senere:

- Endre **Module Profile / Norsk standard** for å vise moduler for profilens brukere.
- Velge en annen modulprofil under **User**, eller tømme profilvalget og velge
  brukerens tillatte moduler individuelt.
- Endre standardverdien på User.module_profile gjennom native Customize Form.

Etter endring må berørte brukere laste inn skrivebordet på nytt, eventuelt logge
ut og inn for å fornye økten. Modulvisning gir ingen nye dokumentrettigheter;
relevante roller må fortsatt være på plass for faktisk bruk.

## Avgrensning

Dette endrer navigasjon. Lager, produksjon, prosjekter og kvalitet avinstalleres
ikke. Roller, dokumentrettigheter, transaksjoner, kontoplan og driftsinnstillinger
endres ikke. Funksjoner kan fortsatt nås via tillatte lenker, relaterte dokumenter
eller API. Felles grunndata for salg, kjøp og regnskap beholdes.

Det er bevisst ikke en sikkerhetsgrense. Se kjernens
[modulnavigasjon i Frappe 16.52.0](https://github.com/frappe/frappe/blob/v16.52.0/frappe/utils/modules.py)
og [native modulprofil](https://github.com/frappe/frappe/blob/v16.52.0/frappe/core/doctype/module_profile/module_profile.py).

## Aksept

Den isolerte driftstesten skal kontrollere at:

1. De fire modulene er skjult for Administrator gjennom den native synlighetsfunksjonen,
   mens regnskap fortsatt vises og eksisterende dokumentrettigheter er bevart.
2. En ny systembruker opprettet gjennom native dokument-API arver standardprofilen
   og har samme fire moduler skjult.
3. Brukeren kan vise en modul gjennom egne modulvalg, og endringen bevares etter
   gjentatt kjøring av oppsettet.
4. Endring av den delte profilen virker og ikke overskrives av oppsettet.
5. Eksisterende prøver for bokføring, PDF, backup/gjenoppretting og tilgang til private
   vedlegg fortsatt består. Native modulvalg bevares ved gjenoppretting.

Faktisk menyvisning på serveren kontrolleres etter at serverblokken er kjørt.
