# Diary: Seed meta-data for 15 pure incremental DB2/Ø90 tables (DataEstate2026 NEW meta)

Goal: replicate the 28-SYNC_META seeding precedent for 15 *pure* incremental Ø90
tables in the NEW meta DB (sqldb-dlbr-dataestate-dev), but drop the
DB2SyncMetaTables layer so the tables report IsSyncMetaTable=0. Produce a
reproducible, idempotent seed artefact under the DLBR-DataEstate2026 repo, run
the seeding, and verify via meta.SourceObjectDefinitions / meta.IngestDefinitions.

## Step 1: Build the artefact; blocked on DB execution

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Opgave: seed meta-data for 15 rene inkrementelle DB2/Ø90-tabeller i den NYE meta-DB (DLBR-DataEstate2026), efter præcis samme mønster som de allerede seedede 28 SYNC_META-tabeller, men UDEN DB2SyncMetaTables-laget og med IsSyncMetaTable=0. Producér et reproducerbart seed-artefakt. Skriv på dansk i din rapport." (followed by detailed read-first context, the 15-table list with watermarks/keys, the 6-layer method minus DB2SyncMetaTables, idempotency + artefact + run + verify requirements, and constraints).

**Interpretation:** Write an idempotent SQL seed artefact matching the existing
`meta/Scripts/` convention, then execute it against NEW meta and verify the 15
tables come out correct in the definition views. Drop layer 5 (KeyColumns) and
the DB2SyncMetaTables layer; keys flow from EIS KeySequenceNumber.

**Inferred intent:** Move the next batch of Ø90 ingestion config into the 2026
estate the same disciplined way the 28 were done, with a re-runnable artefact so
it can later be promoted to test/prod.

### What I did
Read the full migration status (command-deck status.md, ~581 lines, the key
sections on the 28-table seeding and the view chain) and the actual NEW-meta DDL
+ views in `repos/DLBR-DataEstate2026/solutions/sql_database`:
`SourceObjectDefinitions.sql`, `IngestDefinitions.sql`, `SourceObjects.sql`,
`SourceObjectIncrementalSetup.sql`, `SourceObjectIngestSetup.sql`,
`utility/Tables/ExtractInformationSchema.sql`,
`utility/Views/ExtractInformationSchemaDefinitions.sql`. Confirmed the existing
seed-script convention is the single file
`meta/Scripts/set_o90_full_tables_writepattern_scd2.sql` (guarded transaction,
row-count guard, idempotent, STEP 1/2/3 inspect-apply-verify) and matched its
style.

Wrote two artefacts under `repos/DLBR-DataEstate2026/solutions/sql_database/meta/Scripts/`:
- `seed_o90_incremental_15_tables.sql` — the WRITE script for NEW meta. Resolves
  ConnID by name (O90→7), drives off a 15-row table variable carrying watermark
  column + IsDateFlag + baseline, then idempotently seeds SourceObjects
  (insert-if-missing on natural key + realign-to-contract update),
  SourceObjectIngestSetup (insert-if-missing + force WritePattern=stream_scd2),
  SourceObjectIncrementalSetup (DELETE-by-SOID then INSERT). All inside one
  guarded transaction with guards: every table must resolve to a SourceObjectID,
  every table must have >=1 EIS row, every table must have >=1 EIS key column
  (KeySequenceNumber>0), and final counts must be 15/15/15 or it rolls back.
  STEP 2 holds a paste-slot for the generated EIS block.
- `generate_eis_inserts_from_gl_meta.sql` — GENERATOR, read-only against GL meta.
  Reads GL `utility.ExtractInformationSchema` for the 15 tables (GL ConnIDs 5/7),
  emits idempotent DELETE+INSERT blocks rewritten to the NEW convention
  (ConnID=7, SourceConnectionName='O90', SourceSystemTypeName='DB2',
  TableCatalogName='BLUDB'), and a coverage check (15 rows, ColumnCount>0,
  KeyColumnCount>0). This is the exact generate-on-GL / run-on-NEW pattern used
  for the 28.

### Why
The view `meta.SourceObjectDefinitions` derives `IsSyncMetaTable` as
`CAST(ISNULL(sm.SourceObjectID,0) AS BIT)` from a LEFT JOIN to
`meta.DB2SyncMetaTables`. So simply *not* creating a DB2SyncMetaTables row makes
IsSyncMetaTable=0 automatically — that is precisely how the task says to drop the
layer, no extra work needed. KeyColumns in the same view come from
`ExtractInformationSchemaDefinitions WHERE KeySequenceNumber <> ''`, which is why
EIS is a hard prereq and why layer 5 (SourceObjectKeyColumns) is correctly
skipped. Generating EIS from GL (rather than hard-coding columns) keeps the
column set + key sequence byte-faithful to source and re-runnable.

### What worked
The view logic confirms the design end-to-end on paper: IsSyncMetaTable=0 falls
out for free; for non-sync-meta tables IsDateFlag is passed through unchanged
(no forced →1, unlike the 28 which get forced once IsBackfillCompleted flips);
IngestDefinitions' INNER JOIN to SourceObjectIngestSetup is satisfied because
STEP 3 always creates that row; the BusinessCentral CTE admits these rows since
BusinessCentralFlag=0. GL and NEW EIS tables are schema-identical, so the
generator's column list is exact.

### What didn't work
I could not execute the seeding or the verification. Both shell tools are denied
in this builder context:
- `Bash`: "Permission to use Bash has been denied." (tried `az account show ...`)
- `PowerShell`: "Permission to use PowerShell has been denied." (tried
  `az account show`, then a minimal `az version` probe).
Without a shell I cannot run `az account get-access-token` nor open a
`New-Object System.Data.SqlClient.SqlConnection` against either meta DB. So:
the GL EIS generator was NOT run, the EIS block was NOT pasted into STEP 2, the
seed was NOT executed against NEW meta, and the post-seed verification queries
were NOT run. The artefact is written and self-reviewed but UNEXECUTED.

### What I learned
The whole "drop the DB2SyncMetaTables layer" requirement reduces to a no-op in
the seed: the view does the right thing as long as no sync-meta row exists. The
real fragile part is EIS — without it, KeyColumns is NULL/[] (the documented
"SKATSVAR trap") and Copy Data gets 0 columns. That is why both the generator
and the WRITE script carry explicit key-column guards.

### What was tricky
The LastValueLoaded baseline convention is type-driven, not IsDateFlag-driven:
date watermarks → '18991231000000' (1899-12-31), timestamp watermarks
(AJOURTIMESTAMP) → '19000101000000' (1900-01-01). ARKIV is the edge case: its
watermark is the expression `TIMESTAMP(AJOURDATO,AJOURKLOK)` (a timestamp) yet
the task lists IsDateFlag=1. I set ARKIV to IsDateFlag=1 (per spec) with the
timestamp baseline (per type), and flagged it as an item to verify against GL
before the final run rather than guessing silently.

### What warrants review
Two things need a human/DB pass before this is "done":
1. Run `generate_eis_inserts_from_gl_meta.sql` on GL, confirm the coverage check
   returns 15 rows all with ColumnCount>0 and KeyColumnCount>0, paste the block
   into STEP 2 of the write script, run it on NEW meta, and run STEP 7
   verification (expect 15 rows, IsSyncMetaTable=0, IsDateFlag correct,
   IncrementalValueColumnDefinition = the right watermark, LastValueLoaded =
   baseline, KeyColumns not NULL/[]; IngestDefinitions returns 15).
2. ARKIV's IsDateFlag + LastValueLoaded should be checked against what GL meta
   actually holds, in case GL treats the TIMESTAMP() expression differently.

### Future work
Layer 6 (SourceObjectIncrementalBatchSize / SourceObjectColumnPruning) is left
out because none was assumed present in GL for these 15; if GL has any, add
idempotent DELETE+INSERT blocks keyed on the resolved SourceObjectID. Execution
of the seed + verification is the immediate follow-up once a session with DB
shell access (az + SqlConnection) is available.

## Step 2: Validate against GL, fix the artefact, execute, verify, commit

**Author:** main

### Prompt Context

**Verbatim prompt:** "vpn skulle være på igen nu" (the prompt that unblocked
execution; the step actually spans the builder hand-off, the GL validation done
while VPN was down, the fixes, and the later "commit og push til branch").

**Interpretation:** Main has DB shell access (unlike the builder), so pick up the
unexecuted artefact: validate its assumptions against the source of truth (GL
meta), fix what is wrong, run it against NEW meta when the VPN allows, verify,
and commit to the feature branch.

**Inferred intent:** Actually get the 15 seeded and ready in dev while the DB2
network is down for backfill — turning blocked time into finished config — with a
clean, reviewed artefact rather than running the builder's draft blind.

### What I did
Before running anything against the customer meta DB, validated the builder's
hard-coded values against GL `meta.SourceObjectDefinitions` /
`SourceObjectIncrementalSetup`. Then fixed the write script, generated the EIS
block from GL, and executed both against NEW meta via PowerShell + .NET
`SqlConnection` with `.AccessToken` from `az account get-access-token` (NEW tenant
ec009f06, GL tenant 52c45313). Verified the 15 in the definition views and
committed three files to `feature/o90-raw-delete-detection`
(`6671e45`, author `Benny Christiansen <bech@seges.dk>`): the generator, the EIS
INSERTs (`seed_o90_incremental_15_eis.sql`), and the write script. New SOIDs
222-236; aggregate verification 15/15 on IncrementalFlag=1, IsSyncMetaTable=0,
IsDateFlag=1, KeyColumns populated, WritePattern=stream_scd2; IngestDefinitions
returns 15.

### Why
The builder produced the artefact from the task spec but could not run it, so its
values were never checked against reality. Customer-meta writes do not get run
blind: measure against GL first. The seed needs no DB2 connection (it is
meta→meta), so it is the right thing to finish while CHA-33271 blocks the DB2
network for backfill.

### What worked
Validating before running paid off immediately — it caught real value bugs (below)
that would otherwise have seeded wrong incremental config for 12-13 of the 15
tables. The generate-on-GL / run-on-NEW EIS pattern worked cleanly; trimming
SchemaName/TableName in the generator collapsed the GL CHAR-padding so the
DISTINCT dedup across GL ConnIDs 5+7 produced exactly one clean column set per
table (verified: 0 within-table duplicate columns). The whole write script is one
idempotent guarded transaction, so the mid-run failure left nothing partial.

### What didn't work
Five concrete defects, each caught before final commit:
1. **IsDateFlag wrong for ARKIVBETALING.** Builder hard-coded `0` from the spec;
   GL has `1`. Spec-following over source-checking.
2. **RollingWindowDays hard-coded to 0 for all 15.** GL has `-1` for 12 tables and
   `0` only for ARKIVBETALING/BETALINGSOPL/KUNDESEGMENT. Wrong window would change
   incremental extract behaviour.
3. **Single-argument `PRINT CONCAT(...)`** at the end of the write script:
   `The concat function requires 2 to 254 arguments.` This is a bind-time error
   that fails the *entire* batch before execution — so the first run inserted EIS
   (separate statement) but seeded nothing else. Fixed to `PRINT '...'`.
4. **EIS paste-slot sat inside a `/* */` comment block.** Pasting the generated
   SQL there would have left it commented out; the STEP 2 guard would then roll
   back with "no EIS rows". Worked around by running the EIS block as its own
   statement against NEW meta before the write script (idempotent, so safe).
5. **CHAR-padding copied verbatim.** GL stores SchemaName as `'H8921   '`; the
   generator emitted padded literals. Functionally harmless (`=` ignores trailing
   spaces) but dirty; trimmed to match the 28's convention.
   Also a PowerShell splice attempt was blocked by the sandbox ("Remove-Item on
   system path '\*/' is blocked") — switched to the Edit tool for file changes.

### What I learned
The NEW meta is **VPN-gated, the GL meta is not.** Mid-session the NEW server
started rejecting the public IP (`Client with IP address '...' is not allowed to
access the server`) while GL still answered — a reliable signal the SEGES VPN had
dropped, distinct from the DB2/CHA-33271 network flap. Also: the definition view
applies RollingWindowDays to LastValueLoaded, so the *displayed* watermark differs
from the *stored* baseline (e.g. stored `18991231`, shown `18991230` for RWD=-1).
Verifying raw stored values, not just the view, avoids chasing a phantom bug.

### What was tricky
Establishing the right naming convention for the 15 required reading the 28's
*spine* (SourceObjects), not GL: the 28 use trimmed SchemaName ('H89XX') and
UPPERCASE trimmed ObjectName, while GL is internally inconsistent (SourceObjects
'kundesegment' lowercase vs EIS 'KUNDESEGMENT' uppercase, schema CHAR-padded).
Picking the spine convention and normalising the 15 to it (uppercase ObjectName,
trimmed everything) was the call that made the new rows consistent with what is
already there.

### What warrants review
The artefact is on `feature/o90-raw-delete-detection` (commit `6671e45`). A
reviewer should sanity-check the three `meta/Scripts/` files and, if promoting to
test/prod, run them there in order (generator on GL → EIS INSERTs → write script).
The RollingWindowDays-vs-LastValueLoaded view behaviour is worth a second pair of
eyes if backfill later behaves unexpectedly at the boundary.

### What didn't need narration
Nothing else of note — the actual seeding ran clean on the second attempt.

### Future work
Two threads stay open and are unrelated to this seed: (1) backfill of all
SYNC_META + incremental tables waits on CHA-33271 / the DB2 network; (2) the three
deliberately-excluded tables (METODETIDER, METODETIDERALLE, and the SYNC_META
control table) need a separate decision on whether/how they are ingested.
