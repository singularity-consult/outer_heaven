# 2026-06-28 — Ø90/DB2: to fejl adskilt, connector-regression fundet

## Hvad skete der i dag
Metodisk fejlsøgning af den intermitterende DB2-fejl der blokerer Ø90-migreringen (`dataestatedlbr` → `DLBRDataEstate2026`). Jeg cyklede gennem en række hypoteser, og dataene dræbte dem én for én — til vi landede på to **adskilte** fejl med hver sin ejer.

## Bekræftet (det varige)
- **Fejl A — netværk:** Nyt subnet (`10.192.112.4`) har intermitterende sti til `192.168.214.50:30214` (timer-skala flap; natmonitor fangede et ~2t48m udfald + ren recovery 2026-06-27 21:40:06). Gammelt subnet (`10.163.134.4`) upåvirket. Driver-frit (rå TCP+TLS), så ikke driver/ODBC/ADF. db2diag (diawp.exe) viser `errno=10060`. → **T&O/Kyndryl** (FortiGate/tunnel/SNAT).
- **Fejl B — ADF connector-regression:** ADF DB2 **Lookup** (`OdbcSource`) fejler altid `SQL1042C/58004` mens **Copy** (`OdbcSource`) over SAMME linked service/SHIR/driver/connection string virker. Manuel `System.Data.Odbc` på samme VM virker 15/15. Tidsjusteret bevis: Lookup fejlede mens rå TCP+TLS var oppe hvert 10. sek. Overlever fuld VM-reboot. **Rodårsag (config):** gl. løsnings lookups brugte native `Db2Source`; migreringen skiftede dem til generisk ODBC. CLI-trace: fejlende connect ender i tom hostname → SQL1042 (port 30214 sendes korrekt). Mekanismen er udokumenteret → **Data Estate Core / Microsoft**.

## Afkræftet undervejs (noteret så vi ikke gentager)
Netværk-som-eneste-årsag, idle/stale pool (reboot), cert-revocation (CRL fast-deny + konstant-blok vs intermitterende fejl + GSKit virker i PowerShell), queryen (triviel lookup fejler også; query 1,4s manuelt), SEGES-PATH (prepend hjalp ikke), rc=126 (benign — ses på succes-connects), "NewWatermark retry:0" (er retry:3 i JSON).

## Leverancer
- `command-deck/seges/db2-adf-meta-migration/diagnostic-report-EN.md` — T&O/Kyndryl (Fejl A, scopet).
- `command-deck/seges/db2-adf-meta-migration/connector-issue-DataEstateCore-EN.md` — Data Estate Core/MS (Fejl B + repro + native-vej).
- `status.md` ledger opdateret (punkt 15-18 + native-vej).

## Næste skridt — native-fix (i morgen)
Native Db2 er den beviste gamle-design-vej og omgår ODBC-Lookup-buggen. Status: native LS over `id-dlbr-shir` NÅR DB2 (TCP+TLS OK) men fejler DRDA-security-handshake (`DrdaException -1040`; uden SSL: `EUSRIDNWPWD`). Mest sandsynlige årsag: DigiCert CA-kæden ikke trusted på SHIR'en / cert-handshake.

**Plan i morgen:**
1. Native linked service (`type: Db2`, connectVia `id-dlbr-shir`), connection string:
   `server=192.168.214.50:30214;database=bludb;authenticationType=Basic;username=dataesta;password=<pw>;certificateCommonName=*.db2.databases.appdomain.cloud;`
2. Tjek om DigiCert-kæden er trusted på SHIR-VM'en:
   ```powershell
   Get-ChildItem Cert:\LocalMachine\Root, Cert:\LocalMachine\CA |
     Where-Object { $_.Subject -match 'DigiCert' } | Select-Object Subject,NotAfter,Thumbprint
   ```
   Kæden er: leaf `*.db2.databases.appdomain.cloud` → intermediate `DigiCert TLS RSA SHA256 2020 CA1` → DigiCert root. Mangler intermediate/root → importér dem (intermediate hentes fra cert'ens AIA: `http://cacerts.digicert.com/DigiCertTLSRSASHA2562020CA1-1.crt`).
3. Hvis -1040 stadig falder efter CA-trust: undersøg IR'ens Java-truststore (`C:\Program Files\Microsoft Integration Runtime\5.0\Shared\`) og test igen.
4. Hvis `SQL1042C/SQLSTATE=51002 SQLCODE=-805` (pakke): tilføj `packageCollection=NULLID`.
5. Connecter native → kør Sync-Meta-Lookup via `Db2Source`. Virker den → Fejl B løst med rent, licensfrit design.

**Husk:** DB2-password `dataesta` blev eksponeret i klartekst i sessionen → **rotér**. Licens for native = 0 (Db2 on Cloud = LUW; DB2 Connect kun z/OS/iSeries). ADF-ændringer rutes via lead/builder.
