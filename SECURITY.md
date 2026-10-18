# Sikkerhet og støtteomfang

Prosjektet er under utvikling. Teknisk driftsaksept er ikke norsk regnskapsmessig
produksjonsaksept. Frappe, ERPNext og eventuelle aksesspunkt har egne livssykluser
og sikkerhetsoppdateringer; versjonsendringer prøves og migreres bevisst.

Ikke publiser reelle bilag, personopplysninger, passord, nøkler, databaser eller
site-konfigurasjon. Bruk syntetiske data i tester. Rapporter sikkerhetsfeil privat
gjennom GitHubs sikkerhetsrapportering når dette er tilgjengelig. Ikke åpne offentlig
sak med utnyttelseskode eller sensitive data.

Main krever PR fra staging og aktuelle beståtte kilde- og driftskontroller, også
for administrator. Ingen force-push eller sletting av main/staging. Andre grener
skal ikke opprettes. Lokal hook er et supplement til GitHubs serververn.

Offentlig reverse proxy må gi HTTPS og korrekt videresending. Database og Redis
skal ikke publiseres. Private sikkerhetskopier skal inkludere hovedbok, dokumenter,
site-konfigurasjon og krypteringsnøkkel. Gjenoppretting skal prøves før regnskapsaksept.
