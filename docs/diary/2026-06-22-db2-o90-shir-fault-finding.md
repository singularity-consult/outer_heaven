# Diary: DB2/Ø90 SHIR connection fault-finding (SEGES DLBR DataEstate2026)

Benny is migrating the Ø90 DB2 ingestion to the new DLBR DataEstate2026 platform. The new self-hosted integration runtime (SHIR) on `vm-dlbr-shir` was failing to pull data from DB2 with `SQL1042C / SQLSTATE=58004`, blocking the pilot backfill of 28 SYNC_META tables and the broader migration. This session was a long, evidence-driven hunt for the root cause, ending in a conclusion that reframes who owns the problem.

## Step 1: Fault-finding the SHIR → DB2 `58004` failure

**Author:** main

### Prompt Context

**Verbatim prompt:** "hej singularity-drone - hvis vi skal kigge på ADF og DLBR med Ø90 integration - hvor står vi henne lige nu? Kan jeg bare trykke Debug i ADF - lige nu ser det ud til at SHIR har forbindelse"
**Interpretation:** Benny wanted the current status of the Ø90/DB2 ADF migration and whether he could just press Debug now that SHIR appeared connected.
**Inferred intent:** Get unblocked on the pilot backfill — establish whether the DB2 path was actually usable, and if not, find and fix the real blocker.

### What I did
Read the project status (`command-deck/seges/db2-adf-meta-migration/status.md` and `shir-db2-migration/status.md`) to reconstruct state, then drove an interactive diagnostic loop with Benny running commands on `vm-dlbr-shir`:

- Confirmed TCP reachability to the DB2 host `192.168.214.50` on both ports (30214 Prod, 32483 ProdRos) — `TcpTestSucceeded: True`.
- Ran interactive ODBC connects via `System.Data.Odbc.OdbcConnection` against the IBM `C_DB2CLI` driver. A clean `SELECT 1 FROM SYSIBM.SYSDUMMY1` returned `1` at one point, then later failed `58004` on both ports.
- Inspected the driver install: `db2cli.exe validate` passed schema validation, `db2level` reported a proper "IBM Data Server Driver For ODBC and CLI" v11.5.9, GSKit present in `C:\DB2CLI\bin\icc` and `icc64`, ACL on the working dir healthy.
- Discovered via `db2level` that the effective config and diagnostics live at `C:\ProgramData\IBM\DB2\C_DB2CLI\` (not the `C:\DB2CLI\cfg` files we had been editing). Read the real `db2diag.log` there.
- Read the ADF ODBC linked service `ls_db2_odbc.json` (new estate repo) → it pulls a single static KV secret `ConnectionString-VM-O90` from `kv-dlbr-dataestate-dev`, passed as-is (`authenticationType: Anonymous`) over IR `id-dlbr-shir`. Read the secret value; it was well-formed (`Hostname=...;Port=30214;...`, correct format) but pointed at **Prod 30214**, not ProdRos as Benny believed.
- Captured the TLS certificate presented on `192.168.214.50:30214` using `System.Net.Security.SslStream` (the same technique used earlier for the SHIR-registration TLS-inspection proof), four times in a row.

### Why
Benny's standing rule is to never call anything "likely" — investigate until factual. SHIR showing "connected" only proves SHIR↔Azure, not SHIR↔DB2, so pressing Debug blindly was not justified. Each step was chosen to eliminate one layer (network, login, driver binary, GSKit, permissions, config, TLS) until only the true cause remained.

### What worked
- The `SslStream` cert capture was the decisive move. It returned `Subject: CN=*.db2.databases.appdomain.cloud, O=International Business Machines Corporation` / `Issuer: CN=DigiCert TLS RSA SHA256 2020 CA1`, reliably 4/4. This proved two things at once: no TLS-inspection (real DigiCert cert, not a firewall CA), and the backend is **IBM Cloud managed Db2** (`*.db2.databases.appdomain.cloud`, `bludb`), fronted by the private IP `192.168.214.50`.
- `db2level` revealing the real config/diag paths in `C:\ProgramData\IBM\DB2\C_DB2CLI` explained why an earlier CLI trace came up empty (we had configured trace in the wrong `db2cli.ini`).
- Reading the actual KV secret value caught a belief/reality gap: the ODBC path had been hitting Prod 30214 the whole time, not ProdRos.

### What didn't work
- The ADF Debug and interactive connects failed reproducibly with: `ERROR [HY000] [IBM][CLI Driver] SQL1042C  An unexpected system error occurred.  SQLSTATE=58004`.
- The real `db2diag.log` showed the underlying failure: `DIA3222E The host name "" was not found`, `sqljcCommConnect ... ZRC=0x81360012 ... "External Comm error" ... CCI Error: 97`, and `Client timeout exceeded, can not go for retry`. The empty host name is DB2's generic formatting on a **timeout**, not a literal empty host — proven because the well-formed Prod secret produced the same empty-host log.
- Several of my own hypotheses were wrong and Benny rightly pushed back on them: (1) "driver can only do one process at a time / contention" — killed by the fact that 19 full-load tables came out fine on 06-18 and the old solution runs concurrent DB2 ODBC daily; (2) "SHIR worker poisons shared driver state" — better explained by the path flapping between two interactive tries; (3) "hand-copied half install" — killed by `db2level`/`validate` showing a proper install.

### What I learned
- `58004 / SQL1042C` from the IBM CLI driver is a generic wrapper that can hide a **connection/session timeout**; always pull the real `db2diag.log` (at the Common App Data path from `db2level`) before theorizing.
- The Ø90 "DB2 server" is not on-prem — it is IBM Cloud Db2 reached through a private entry point at `192.168.214.50`. TCP and TLS to it are reliably up; the intermittent stall is in the DB2 **session layer** (post-TLS DRDA/auth/db-open).
- A passing `Test-NetConnection` and a "SHIR connected" status are the wrong layer of evidence for this class of problem and should not be accepted as proof that the path works.

### What was tricky
The error code stayed identical (`58004`) across genuinely different root states (network flap vs. config vs. nothing), and the symptom was intermittent — a clean window returned `1` and a flapping window returned `58004`, which repeatedly tempted wrong conclusions. The intermittency is what made every premature "it's X" hypothesis look briefly plausible. Discipline (eliminate by layer, demand ground truth) was the only thing that cut through it.

### What warrants review
The final conclusion: transport (TCP + TLS) is reliably up; the DB2-session layer intermittently times out. That localizes the fault to one of: IBM Cloud Db2 connection limits/throttling on the managed service, the proxy/NAT at `192.168.214.50`, or SNAT/conntrack exhaustion on the Azure hub firewall for the established session. A reviewer should validate by reading the `db2diag.log` timeout entries and confirming the cert identity, then weigh the strongest discriminator: the **same** DB2 server serves the old subnet stably and daily, while only the new subnet (`10.192.112.0/24`) flaps — a server-only fault would hit both.

### Future work
- Benny has reached a contact at **Kyndryl**, who own the infrastructure between DB2 and SEGES outbound. He is setting up a joint Teams session (Kyndryl + T&O + Benny) to fix it on the spot.
- Open discriminating test not yet run: a 10x isolation loop of the DB2 connect with SHIR stopped, to separate connection-volume/SNAT exhaustion from a genuine volume-independent path/server flap.
- When the path is fixed: resume the pilot backfill (DAPOSTEXT SOID 196 via Single Controller, then the 28 SYNC_META via Multiple Controller with `MetaWhereClause = IsSyncMetaTable = 1`, ForEach set sequential while the path is fragile). Remember the meta-reset trap: any ProdRos backfill flips `IsBackfillCompleted → 1`, which must be reset before switching to Prod.
