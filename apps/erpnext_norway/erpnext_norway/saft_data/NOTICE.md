# SAF-T-kilder og endringer

XML-byggeren i `../saft_builder.py` gjenbruker den databasefrie delen av
[ENK Norge saft.py](https://github.com/Medpus/enk_norge/blob/94406e542ed991a8de237b9de44b8d1dd576b566/enk_norge/saft.py),
revisjon `94406e542ed991a8de237b9de44b8d1dd576b566`. Copyright (c) 2026 Haakon
Fornes, MIT. Uendret lisens følger i LICENSE.enk-norge. Den gamle Frappe-adapteren
og innstillingene er utelatt. Lokale endringer støtter null avgiftsbeløp, flere
BaseRate-verdier, native åpningsposter, valutabeløp, eksakte utvalgsdatoer,
native dimensjoner og entydige bilagsreferanser. Samlet debet/kredit gjengis
med samme native RecordID og faktiske brutto valutabeløp på hver bokført side; avgiftsopplysninger kan bindes
uttrykkelig til siden. Lagret kildebruker, eksportør, grunnlagsbeskrivelse og
spesifikasjon kan gjengis i formatets eksisterende felt. TaxTable kan få hele registeruttrekket med flere lagrede
satser per kode og valgfri nominell sats, uten å legge til transaksjoner. Hele det leverte kontoregisteret gjengis, også uten bevegelser.

Det offisielle XSD 1.40 og næringsspesifikasjonslisten 2025–2026 er hentet uendret
fra [Skatteetaten/saf-t](https://github.com/Skatteetaten/saf-t/tree/10c8fd82a6ff47e53385bc33c7638c5fde239a4f),
revisjon `10c8fd82a6ff47e53385bc33c7638c5fde239a4f`. Originalt copyright i skjemaet
er bevart. Ingen egen lisensfil ble funnet i dette kildearkivet; ikke tilskriv
filene en oppdiktet programvarelisens. Filene er den publiserte norske
formatspesifikasjonen og kodelisten brukt til validering, ikke ny programkode.
SHA-256 for de uendrede kildene følger i source.json.

Skjemaets opprinnelige whitespace er bevart. Git-attributtet unntar bare
denne uendrede normfilen fra kontroll av etterfølgende blanktegn.


account-mapping.csv er gjenbrukt koblingsdata (357 kontoer), ikke en offisiell
kontokodeliste, fra mfuryto/dolibarr-norway, GPL-3.0, revisjon
cc5cb151c1bca9eb4c6b84dd69305191e2e3ef29:
https://github.com/mfuryto/dolibarr-norway/blob/cc5cb151c1bca9eb4c6b84dd69305191e2e3ef29/htdocs/custom/norway/data/saft/account-mapping.csv
Original SHA-256: e25ff8e8dd9eadda2a21e61cd94fc2f615cf5333a6fc1302b00ffb46e9f93532.
Lokal endring: kolonnen root_type er lagt til fra den leverte norske kontoplanen. Kontonavn/proveniens følger også
resources/norway-chart/NOTICE. Bare data gjenbrukes, ingen Dolibarr-kode.
Standardvalget gjelder bare eksakt opprinnelig nummer, navn og hovedgruppe.
