# Diary: datavilla metadata-driven ingestion framework

Building a simple, metadata-driven, Databricks-native data ingestion framework in Benny's
`datavilla` learning/build project. North star: "as automated and simplified as possible" —
the least framework that is still metadata-driven and easy to extend. Adding a new source table
should cost as close to a single metadata entry as possible; everything else automatic.

The existing datavilla platform is already deployed via IaC: three environments (dev/test/prod)
on Azure, a 6-layer medallion as Unity Catalog catalogs (`datavilla_<env>_{landing,raw,base,
enriched,curated,integration}`), managed storage per env, VNet-injected workspaces, a shared
regional metastore, and a per-env service principal (`datavilla-<env>-sp`) with write on all
layers. `src/` was empty — a fresh start. twoday Kapacity's proprietary `lighthouse` framework
was read for *patterns only* (metadata-driven ingestion, medallion flow, incremental load,
generic write patterns) — never copied. We deliberately move away from lighthouse's two pillars:
its SQL meta-database and its ADF orchestration.

## Step 1: Design, refinement, and kickoff of Blok 0 + Blok 1

**Author:** main (lead agent)

### Prompt Context

**Verbatim prompt:** "Alle fem afklaret + én designændring. Gå videre: start diary og spawn
builder på Blok 0 + Blok 1. DESIGNÆNDRING — base-laget skippes som fysisk lag: Merge (SCD1/SCD2)
og rensning sker i ét hop raw → enriched. MEN merge og cleanse skal være to separate,
genanvendelige kode-moduler der begge anvendes i det hop — behold modulariteten/testbarheden på
kode-niveau, spar den redundante fysiske base-kopi. Lagene bliver: raw → enriched (merge+cleanse)
→ curated (dim/fact) → integration. base-catalogen bliver liggende tom/reserveret. Revidér
byggeplanen: Blok 2 bliver 'merge-motor + cleanse-moduler → enriched' i stedet for →base."
(plus resolved questions 1–5: demo source Azure SQL `sql-sic-dev-01`/DB `DSA`; JDBC access via
dev-SP Entra token with an external SQL-admin prerequisite; run-log `_ops` schema with explicit
source/adapter/runtime fields; landing skipped; change-simulator as a dev Delta table.)

**Interpretation:** Requirements are settled. Start the feature diary and spawn a builder to
implement the first two build blocks: the framework skeleton + logging spine (Blok 0) and the
JDBC→raw ingest (Blok 1). Apply the design change that drops `base` as a physical layer while
keeping merge and cleanse as two separate, independently testable code modules.

**Inferred intent:** Benny wants to watch the framework grow incrementally, block by block,
starting from the spine everything hangs on (logging) plus the first real data path (JDBC→raw).
No monolith dump. Modularity and testability are first-class because this is a learning project
he wants to understand.

### What I did

Read the deployed datavilla platform (`infra/` Terraform: the 6 UC catalogs in
`infra/modules/unity_catalog/main.tf`, the per-env SPs in `platform/main.tf`) and distilled
patterns from lighthouse (metadata field shape in `adapters/metadata/sql.py` +
`config/base_configuration.yml`, generic write patterns in `write.py`, workflow autogeneration).
Produced a design and refined it across two coordinator rounds into confirmed decisions:

- **Engine:** plain PySpark Jobs + Auto Loader, no DLT.
- **Metadata:** YAML in the repo (kills the SQL meta-database).
- **DB sources:** JDBC → raw directly (skip landing; landing/Auto Loader is a later file adapter).
- **Layers (revised):** raw → enriched (merge + cleanse, two separate code modules in one hop)
  → curated (dim/fact star schema) → integration. `base` catalog stays empty/reserved.
- **Merge:** generic config-driven SCD1 + SCD2 write patterns, unit-tested like lighthouse.
- **Cleanse:** generic rule-driven module (invalid/empty dates → '1900-01-01', trim,
  empty-string→null, type standardization, dedup).
- **Dimensional templates (new beyond lighthouse):** dimension (SCD2 + surrogate key) and fact
  (FK lookup to dims + measures) templates, defined in metadata.
- **Logging:** structured Delta run-log via a shared context manager; must carry source,
  adapter type, and runtime (start_ts + end_ts + duration).
- **Orchestration:** Databricks Workflows generated from metadata. **Deploy:** Asset Bundles per
  env, `run_as` = env SP.
- **Demo source:** stale Azure SQL DB `DSA` on `sql-sic-dev-01` — ingestion proven live once;
  merge/SCD/dim/fact mechanics proven via unit tests + a seeded change-simulator Delta table
  in dev, because the source never changes.

Layered build plan agreed: Blok 0 (skeleton + logging spine), Blok 1 (JDBC→raw) = MVP; then
Blok 2 (merge + cleanse → enriched), Blok 3 folded into Blok 2 by the design change, Blok 4
(dim/fact → curated), Blok 5 (orchestration + multi-env). Then started this diary and spawned a
builder on Blok 0 + Blok 1.

### Why

The logging spine is built first because every routine hangs on it — it is what makes each later
block observable and demonstrable. JDBC→raw is the first real data path and the smallest thing
that proves the metadata→job→data loop end to end. Dropping the physical `base` layer removes a
redundant full copy of the data while the design change preserves the thing that actually
mattered (merge and cleanse as separate, testable modules).

### What worked

The two-round refinement with the coordinator converged cleanly: presenting trade-offs (YAML vs
Delta metadata, DLT vs plain jobs) rather than a single recommendation let Benny decide fast and
the decisions matched the existing platform (plain PySpark mirrors lighthouse; SP already has
write on all layers so `run_as` needs no new infra).

### What didn't work

Nothing failed in this step — it is design + kickoff, no code executed yet. The one open risk is
external and already flagged, not a failure: the live JDBC run is blocked until a SQL/Entra admin
provisions the dev-SP as an EXTERNAL PROVIDER user with `db_datareader` in `DSA`.

### What I learned

datavilla's 6 catalogs already exist and are workspace-bound + ISOLATED per environment, so the
framework does not create catalogs — it writes into them. The per-env SP is explicitly intended
for automation and already has write everywhere, which is why Asset Bundles `run_as` the SP is
zero-friction. lighthouse's metadata shape (one row per source object with format/path/keys/
load_type/incremental-flag) maps almost 1:1 onto a YAML block — the SQL database around it was
incidental, not essential.

### What was tricky

The `base`-layer decision. Keeping base and enriched as two physical layers is cleaner
pedagogically (merge mechanics separated from cleanse mechanics) but writes the data twice.
Benny's resolution — collapse the physical layers but keep two separate code modules — is the
right call for the north star, but it puts the burden on the builder to keep merge and cleanse
genuinely decoupled at the code level even though they run in one hop. That is the main thing to
watch in Blok 2.

### What warrants review

Nothing to review yet in code. For the upcoming builder output on Blok 0 + Blok 1, reviewers
should check: (1) the run-log schema actually carries source, adapter, start_ts, end_ts, and
duration; (2) the JDBC adapter authenticates via Entra token (no password) and is schema-
agnostic so it works once access is granted; (3) nothing deploys or applies against Azure — the
builder delivers diffs only, main commits (identity singularity-consult), and the live JDBC run
waits on the external SQL-admin prerequisite.

### Future work

Blok 2 (merge + cleanse → enriched), Blok 4 (dim/fact templates → curated), Blok 5 (metadata-
driven Workflow generation + test/prod bundle targets). The file/Auto Loader landing adapter is
deferred until file sources become real. The change-simulator Delta table in dev is the vehicle
for demonstrating merge/SCD once Blok 2 lands.

## Step 2: Build Blok 0 (skeleton + logging spine) and Blok 1 (JDBC → raw)

**Author:** builder (outer_heaven:builder)

### Prompt Context

**Verbatim prompt:** "Build the first two blocks of a metadata-driven, Databricks-native data
ingestion framework in Benny's `datavilla` repo ... Blok 0 (skeleton + logging spine) and Blok 1
(JDBC → raw ingest). DIFFS ONLY — do NOT commit/push/deploy/apply/connect to Azure. Read
lighthouse for PATTERNS only, never copy code. Keep it the least framework that is still
metadata-driven; adding a source ≈ one YAML block; adapters, write patterns, logging as separate
concerns; offline-testable." (Full scoped brief with confirmed architecture, demo source
`DjurslandsBank_AllAccounts` on `sql-sic-dev-01`/`DSA`, run_log field list, and hard constraints.)

**Interpretation:** Implement only Blok 0 + Blok 1 under the empty `src/`, as inspectable/
offline-testable diffs. Distil lighthouse patterns into a clean original design; do not touch
Terraform, do not run anything against Azure, do not commit.

**Inferred intent:** Give Benny a genuinely modular spine (logging), a schema-agnostic JDBC→raw
path, one demo YAML, and a dev Asset Bundle — small enough to read in one sitting, structured so
Blok 2+ slot in without rework.

### What I did

Wrote the framework under `C:\claudes_folder\repos\datavilla\src\`:

- Package `datavilla/`: `config.py` (YAML→frozen dataclasses `SourceDefinition`/`TargetConfig`/
  `ConnectionConfig`/`SourceRef`/`IncrementalConfig`, env-injected catalog resolution, validation),
  `runlog.py` (the spine: `RunContext` + pure `build_run_log_row` + `run_log()` context manager +
  `DeltaRunLogWriter` that idempotently bootstraps `_ops` schema and `run_log` table), `spark_utils.py`,
  `adapters/base.py` (ABC + decorator registry), `adapters/jdbc.py` (schema-agnostic Azure SQL reader,
  Entra token via secret scope, no password), `write/raw.py` (audit columns + full=overwrite/
  incremental=append), `ingest.py` (orchestration + `datavilla-ingest` CLI).
- Metadata `config/sources/djurslandsbank_allaccounts.yml` (one demo block, keys/watermark left
  unset with prerequisite comments); bundle `databricks.yml` (dev target, `run_as` dev SP) +
  `resources/ingest_djurslandsbank_allaccounts.job.yml` (python_wheel_task); `pyproject.toml`;
  `README.md` (shape, run_log schema, external prerequisites, secret keys); `tests/` (config +
  run-log, offline).

Validated offline: `python -m pytest` → `10 passed`. Confirmed the pure modules import with no
pyspark/azure installed (`import datavilla.config, datavilla.runlog` OK; `datavilla.adapters` with
jdbc registered OK; `datavilla.ingest` OK), and that all three YAML files parse.

### Why

The pure-core / side-effects-at-edges split is what makes the spine testable without a cluster:
`config` and the `RunContext`/row-builder in `runlog` import stdlib+yaml only; every Spark/Azure
import is lazy inside functions. The registry keeps `ingest` decoupled from concrete adapters so
Blok 2's merge/cleanse and a future file adapter register without editing the orchestrator. One
source = one YAML file with env injected at runtime, hitting the north star.

### What worked

Offline validation was fully green first-hand, not asserted: `10 passed in 0.05s`, and the
no-pyspark import probes all succeeded, proving the tested surface genuinely needs no cluster.

### What didn't work

No failures during the build. The honest gaps are unverifiable-offline, not broken: no pyspark/
azure in the local interpreter (Python 3.14, only pyyaml 6 + pytest 9), so the Spark write path,
the JDBC read, and `databricks bundle validate` could not be exercised here — flagged rather than
faked. `ModuleNotFoundError: No module named 'pyspark'` / `'azure'` confirmed the local env; the
design routes around it by keeping those imports lazy.

### What I learned

lighthouse's run-log helper (`helpers/logging/logging.py`) is a thin per-domain DataFrame
appender, not a general spine — so the reusable context-manager design here is genuinely our own,
not a copy. lighthouse's metadata (`adapters/metadata/sql.py`) is one wide row per source object;
that maps cleanly onto a YAML block, confirming the SQL DB around it was incidental.

### What was tricky

Two judgement calls. (1) The brief says raw write should "append", but a full load that blindly
appends duplicates the whole table every run — I implemented full→`overwrite` (idempotent),
incremental→`append`, and flagged the deliberate deviation rather than silently complying or
silently deviating. (2) "Entra token, no password" with only `sp-client-id`/`tenant-id` in the
scope has no pure client-credentials flow; the default uses `ManagedIdentityCredential(client_id=…)`
but whether dev job compute carries the SP as a managed identity is an environment fact I cannot
verify — made the `token_provider` injectable and flagged it as a decision for Benny.

### What warrants review

- `src/datavilla/write/raw.py`: the full→overwrite deviation from the literal "append" wording —
  confirm Benny wants idempotent overwrite for full loads.
- `src/datavilla/adapters/jdbc.py`: the token flow AND the `accessToken` option passthrough to the
  MS JDBC driver — both are live-only, flagged UNVERIFIED in comments.
- `src/databricks.yml`: `workspace_host` is a placeholder; `resources/…job.yml` cluster
  `spark_version`/`node_type_id` are conventional placeholders. main must run `databricks bundle
  validate` (I could not) and fill the host.
- External prerequisite unchanged: dev SP as EXTERNAL PROVIDER user with `db_datareader` in `DSA`,
  plus the `datavilla-dev-sql` secret scope (keys `server`/`database`/`sp-client-id`/`tenant-id`).

### Future work

Blok 2 merge+cleanse → enriched will register a second write pattern and reuse `run_log` unchanged
(rows_inserted/updated/deleted already in the schema). `_ops.watermarks` is reserved (constant +
README note) for Blok 2 incremental. Once access is live: confirm the real schema, set `keys` and
`incremental.watermark_column`, and validate the JDBC read + bundle deploy on a cluster.

## Step 3: Two Benny-decided adjustments — append-only raw + managed-identity auth

**Author:** builder (outer_heaven:builder)

### Prompt Context

**Verbatim prompt:** "Benny har besluttet to justeringer til Blok 0+1. Byg dem, opdatér diffs +
tests + diary (Step 3), og aflever tilbage. Byg IKKE Blok 2 endnu. JUSTERING 1 — raw-write =
APPEND, ikke overwrite. Raw skal være et immutabelt, append-only historisk bronze-spejl ... tilføj
en batch-identifikator (fx `_load_batch_id` = run_id fra RunContext) ... JUSTERING 2 — auth =
managed identity (a), password-fri. IKKE client-secret ... Databricks service credential
(databricks_credential, purpose SERVICE) der wrapper en access connector's managed identity ...
hvis mekanismen bruger access connector'ens managed identity, så er det DEN identitet (ikke
dev-SP) der skal have `db_datareader` på DSA ... Ændr IKKE infra/ Terraform selv — hvis der kræves
en infra- eller UC-ændring, STOP og beskriv den præcist til main." (Relayed via the lead sub-agent,
on Benny's behalf.)

**Interpretation:** Reverse Step 2's full→overwrite decision — raw is append-only with a per-run
batch id linking each snapshot to its run-log row. Replace the azure-identity managed-identity
default with the Databricks UC service-credential flow, and make crystal clear that the grant
target becomes the access connector's managed identity, not the dev SP. Do not touch infra;
describe the required UC change to main. No Blok 2.

**Inferred intent:** Benny wants a true historical bronze layer (snapshots, traceability) and the
cleanest password-free auth the platform actually supports, with an unambiguous handover of who
must be granted what.

### What I did

Adjustment 1 (`src/datavilla/write/raw.py`, `src/datavilla/ingest.py`): removed the overwrite
branch — `write_raw` now always appends with `mergeSchema`. Added `_load_batch_id` audit column
(alongside `_ingested_at`, `_source`); `write_raw`/`add_audit_columns` take a `load_batch_id`, and
`ingest_source` passes `ctx.run_id` so each raw row links to exactly one run-log row. Rewrote the
module docstring to state the immutable append-only contract and the explicit Blok 2 rule (latest
snapshot per key = greatest `_ingested_at` / newest batch by run `start_ts`). `WriteResult`
unchanged (rows_inserted = rows_in still correct for append). Added `writer` injection seam to
`ingest_source`.

Adjustment 2 (`src/datavilla/adapters/jdbc.py`): replaced the azure-identity
`ManagedIdentityCredential` default with `_service_credential_token_provider`, which mints an Azure
SQL token via the databricks-sdk UC service-credential API
(`WorkspaceClient().credentials.generate_temporary_service_credential`). Changed the
`TokenProvider` type to receive the resolved secrets mapping (generic, so a federation provider
drops in without touching the adapter). Secret keys are now `server`, `database`,
`service-credential` (dropped `sp-client-id`/`tenant-id`). Read `infra/modules/unity_catalog/
main.tf` and identified the reusable access connector `dbw-ac-datavilla-dev`; did NOT modify infra.

Docs/config/deps: rewrote the demo YAML prerequisite comments and the README into an explicit
WHO-gets-WHICH-access table, flagged the UC service-credential creation as an infra change for main,
and removed `azure-identity` from `pyproject.toml`. Added `tests/test_ingest.py` proving
`_load_batch_id == run_log.run_id` via fakes. `python -m pytest` → **11 passed**; verified offline
imports still work with no pyspark/azure/databricks-sdk installed and all YAML parses.

### Why

Append-only with a run-scoped batch id is what makes raw a real historical mirror: without the
batch id, repeated loads of the stale DSA source produce identical, unattributable rows. Tying the
batch id to `run_id` gives free lineage from any raw snapshot to its run-log row. The service-
credential flow is the password-free path that actually fits a Databricks-native platform, but it
moves the database principal from the SP to the connector's managed identity — a consequence that
had to be surfaced loudly, not buried.

### What worked

The generic `TokenProvider(Mapping) -> str` seam absorbed the whole auth change without touching
`read()` beyond one call site, and the new linkage test passes offline with everything Spark faked
(`11 passed in 0.05s`) — the batch-id↔run-id contract is proven, not asserted.

### What didn't work

No build failures. The honest gap is the exact databricks-sdk surface for minting the token
(`generate_temporary_service_credential`, `azure_options={"resources": [...]}`, `temp.azure_aad.
aad_token`): I could not verify method/field names offline (no databricks-sdk locally, no cluster),
so it is best-effort and flagged UNVERIFIED in code and README. The `accessToken` passthrough to the
MS JDBC driver remains live-only too.

### What I learned

The existing UC access connector (`dbw-ac-datavilla-dev`, SystemAssigned MI already used for managed
storage) is reusable for a SERVICE-purpose credential — one managed identity can back both storage
and the SQL service credential, so the platform needs one new UC object and one SQL grant, not a new
connector. That is the low-friction recommendation handed to main.

### What was tricky

The identity swap. Benny had already granted the dev SP `db_datareader` in DSA; with the service-
credential model that grant is on the wrong principal. Getting this wrong would look like it works
in code review yet fail at runtime with an opaque auth error. I made "move/duplicate the grant to
the connector MI" the first, boldest line of both the YAML and the README table, and kept federation
(where the SP grant would be reusable) documented as the preferred-if-verified alternative.

### What warrants review

- `src/datavilla/adapters/jdbc.py`: the databricks-sdk service-credential call — confirm method and
  response field names against the runtime's installed SDK version before relying on it.
- Whether to reuse `dbw-ac-datavilla-dev` or provision a separate connector, then create the
  `databricks_credential` (purpose SERVICE) + `ACCESS` grant in Terraform — an infra/UC change the
  builder deliberately did NOT make (flagged in README "Infra/UC change needed").
- `src/databricks.yml`: `workspace_host` + cluster placeholders still need main to run
  `databricks bundle validate`.
- Step 2's full→overwrite note is now superseded — raw is append-only per this step.

### Future work

Blok 2 must honour the append-only contract: dedup raw to the latest snapshot per business key by
`_ingested_at` before merge/cleanse. `_ops.watermarks` still reserved for incremental. Once auth is
live, confirm the service-credential token call and the `accessToken` passthrough, and if workload-
identity federation for the dev SP is confirmed, switch to it to reuse the existing SP grant.

## Step 4: Complete the auth chain — UC SERVICE credential in Terraform

**Author:** builder (outer_heaven:builder)

### Prompt Context

**Verbatim prompt:** "Blok 0+1 er committet af main. Benny har givet connector-MI'en db_datareader
på DSA. Nu skal auth-kæden gøres komplet i Terraform ... Tilføj en UC SERVICE credential over
access connector'en ... `databricks_credential` (workspace-provider), `purpose = \"SERVICE\"`, med
`azure_managed_identity { access_connector_id = azurerm_databricks_access_connector.this.id }` ...
Grant miljøets run-as SP `ACCESS` ... `databricks_grant` (ental, additiv) ... Tilføj et output med
credential-navnet ... Kør `terraform fmt` + `terraform validate` med `terraform init -backend=false`
... INGEN backend-init/plan/apply/commit." (Relayed by the coordinator on Benny's behalf.)

**Interpretation:** Make exactly the infra change I flagged and stopped on in Step 3, now authorized:
a SERVICE credential over the existing access connector, an additive `ACCESS` grant to the run-as SP,
and a module output for the name. fmt + validate only; deliver a diff.

**Inferred intent:** Close the last gap so the JDBC job can mint Azure SQL tokens password-free, and
confirm the provider attribute form so main hits no surprises at apply.

### What I did

Touched only `infra/modules/unity_catalog/`: added `databricks_credential.sql` in `main.tf`
(`purpose = "SERVICE"`, `azure_managed_identity { access_connector_id =
azurerm_databricks_access_connector.this.id }`, workspace provider, named `${replace(var.name,"-",
"_")}_sql_cred` → dev `datavilla_dev_sql_cred`); an additive `databricks_grant.sql_credential_access`
in `grants.tf` (`credential`, `principal = var.service_principal_application_id`, `privileges =
["ACCESS"]`) with a comment on why singular/additive vs the authoritative catalog `databricks_grants`;
and output `sql_service_credential_name` in `outputs.tf`. Ran `terraform fmt -recursive` (no changes),
`terraform init -backend=false` (reused vendored providers), `terraform validate` → **Success! The
configuration is valid.** `git diff --stat`: 3 files, +41, additions only.

### Why

The credential is the object the databricks-sdk `generate_temporary_service_credential` call from
Step 3 looks up by name to mint the token; without it the JDBC adapter's default provider has nothing
to reference. Reusing the existing `dbw-ac-datavilla-dev` connector (rather than a new one) keeps it to
one managed identity and one SQL grant, matching the low-friction recommendation.

### What worked

`terraform validate` passing against the vendored databricks provider **v1.111.0** is a real
confirmation the attribute form is accepted by `~> 1.0` — `databricks_credential` with `purpose` +
`azure_managed_identity { access_connector_id }` + `comment`, and `databricks_grant` with `credential`
+ `principal` + `privileges`. No provider-mismatch guesswork left for apply.

### What didn't work

No failures. One scope gap surfaced, not an error: infra/ has no root `outputs.tf`, so the module
output is not exposed via `terraform output` at the root. I did not add a root output ("rør ikke
andet"); flagged instead. The name is deterministic (`datavilla_dev_sql_cred`) so main can set the
secret without a root output if preferred.

### What I learned

The existing UC access connector carries a SystemAssigned managed identity that can back both a
STORAGE credential (already there, for managed storage) and a SERVICE credential (new) simultaneously
— one MI, two UC credential objects, two purposes. That is why no new Azure identity or role plumbing
was needed beyond the `db_datareader` grant Benny already applied.

### What warrants review

- `terraform validate` confirms schema, not apply-time behaviour: whether `purpose = "SERVICE"` and
  the `ACCESS` privilege are accepted by the metastore is confirmed at plan/apply, which main runs.
- Decide whether to add a root `infra/outputs.tf` re-exporting `module.unity_catalog.
  sql_service_credential_name`, or just use the deterministic name in the secret scope.
- The run-as SP for the grant is `var.service_principal_application_id` (application/client id) — same
  principal the catalog grants use, so it resolves consistently.

### Future work

main: `plan` + `apply` the infra change (dev), then put `datavilla_dev_sql_cred` into the
`datavilla-dev-sql` secret scope under `service-credential`, and the live JDBC run can be attempted.

## Step N: Logical-source model + union sources + job-from-config + live schema inspection

**Author:** main

### Prompt Context

**Verbatim prompt:** "Udvid datavilla-ingestion-frameworket: revidér metadata-modellen til logiske
kilder (ikke fysiske tabeller), tilføj de resterende DSA-kilder, og byg job-generering fra config.
Bennys eget projekt. Følg `terraform`- og `python`-skills. Aflever diffs til main; main deployer/kører
live/committer. INGEN git-commits, ingen deploy/run mod Azure — men du MÅ læse skemaer via read-only
JDBC hvis du kan etablere forbindelse." (Plus the three-opgave breakdown: multi-table UNION sources
with a `_source_table` audit column, many sources per YAML in one `dsa.yml`, job generation from
config, and schema inspection to fill keys/watermark if a connection can be established.)

**Interpretation:** Reshape config from one-source-per-file physical tables to logical entities (four
logical DSA sources, one being a UNION of two physical tables), support many sources per YAML,
generate Databricks jobs from config instead of hand-writing them, and — if a read-only JDBC
connection is reachable offline — fill `keys`/`watermark` from the real schema rather than guessing.

**Inferred intent:** Make "add a source" a pure-config act (no Python, no hand-written job), and stop
guessing schema details now that the DB is reachable — ground every keys/watermark decision in real
data or leave it explicitly empty.

### What I did

Four framework changes in `C:\claudes_folder\repos\datavilla\src`, all validated offline with pytest
(24 passed):

1. **Config model** (`datavilla/config.py`): `SourceRef` gained a `tables:` list (UNION) alongside
   `table`/`query`, with `is_union` + `physical_tables()`; validation enforces exactly-one-of and
   >=2 tables for a union. Added `SourceDefinition.load_many` + `_parse_document` (accepts a single
   mapping OR a `sources:` list), `load_all_sources(config_dir)` (globs all `*.yml`, flattens,
   rejects duplicate names), and rewired `load_source` to find by `name` across the dir instead of
   reading `<name>.yml`.
2. **Union read** (`adapters/jdbc.py`): new `_read_union` reads each physical table, stamps
   `_source_table` (new constant in `write/raw.py`), and folds them with
   `unionByName(allowMissingColumns=True)`.
3. **Config** (`config/sources/dsa.yml`): the four logical sources, replacing the old single
   `djurslandsbank_allaccounts.yml` (deleted). `historic_transactions` is the union.
4. **Job generation** (`scripts/generate_jobs.py`): emits `resources/ingest_<name>.job.yml` per
   source, owns files by a `# GENERATED` marker (rewrites/deletes them; leaves hand-written ones),
   has `--check` for pre-deploy drift. Deleted the manual job spec; generated all four.

Then I **inspected the live schema**. Minted an Azure SQL token via `az account get-access-token
--resource https://database.windows.net/`, and since classic ODBC `sqlcmd -G` fell back to
ActiveDirectoryIntegrated and failed ("Failed to resolve the UPN for the current windows account"),
I pip-installed pyodbc into a throwaway `C:\claudes_folder\tmp_pyodbc` (never touching Benny's global
env) and connected with ODBC Driver 17 passing the token via `attrs_before={1256: tokstruct}`.
Queried `INFORMATION_SCHEMA` + `sys.tables` on `datavault2020.database.windows.net`/DSA, then deleted
the temp dir.

Tests: extended `test_config.py`, added `test_jdbc_union.py` (fakes Spark + injects a fake
`pyspark.sql.functions` so the union wiring runs with no cluster) and `test_generate_jobs.py`
(non-destructive drift check). Updated README + config docstrings.

### Why

The north star is "add a source = edit config." Logical grouping + union + generated jobs remove the
last two manual steps (physical-table thinking and hand-written job specs). Inspecting the real schema
turns keys/watermark from guesses into evidence-based decisions — and the evidence said "leave them
empty, here's why," which is itself the deliverable.

### What worked

The token-via-pyodbc path connected on the first server tried (`datavault2020`), using Benny's own
`benny@singularityconsult.dk` az login — so the read-only inspection the task hoped for but expected
to be impossible actually succeeded. The fake-pyspark injection (`monkeypatch.setitem(sys.modules,
"pyspark.sql.functions", ...)` plus fake parent packages) let me unit-test the union orchestration
offline without a cluster.

### What didn't work

- `sqlcmd -S ... -G -Q "..."` → `Microsoft ODBC Driver 17 ... Failed to authenticate the user '' in
  Active Directory (Authentication option is 'ActiveDirectoryIntegrated'). Error code 0xCAA50017 ...
  Failed to resolve the UPN for the current windows account.` Classic ODBC sqlcmd can't take a raw
  token, and `-G` alone means Integrated. Fix: pyodbc + `SQL_COPT_SS_ACCESS_TOKEN` (1256).
- First inspection pass filtered only on `TABLE_NAME`, not schema, so `Alternative_FearGreedIndex`
  (which exists in BOTH `dbo` and `stg`) returned a merged, duplicated column list. Re-ran with
  explicit `(TABLE_SCHEMA, TABLE_NAME)` pairs.
- `subprocess.check_output(["az", ...])` → `FileNotFoundError: [WinError 2]` — `az` is a `.cmd` shim;
  needed `shell=True` with a string command.

### What I learned

The task's stated physical mapping was wrong in two concrete ways, both caught by inspection, neither
guessed: (1) `HistoricTransactions_2017-2020` and `HistoricTransactions_2021` live in **`stg`**, not
`dbo`; (2) the two union members do **not** share a schema — 2017-2020 has a `TransactionId int NOT
NULL PRIMARY KEY` (21 cols, 4065 rows) that 2021 entirely lacks (20 cols, 0 rows). So `TransactionId`
can't be the union's natural key, and `allowMissingColumns=True` is mandatory, not optional. Also:
`dbo.Alternative_FearGreedIndex` is untyped nvarchar with no PK and 0 rows, while a typed
`timestamp`-PK version sits in `stg` — a real fork-in-the-road for main. And a server discrepancy:
repo comments say `sql-sic-dev-01` but the live tables are on `datavault2020`.

### What was tricky

Keys/watermark: the honest answer is "still empty," but for schema-grounded reasons per source
(no PK + free text; generic `Prop_*` columns; empty untyped dbo table; PK on only one union half).
Writing that up convincingly — empty-but-justified, not empty-because-lazy — was the real work of
Opgave 3. The hyphenated `stg.[HistoricTransactions_2017-2020]` needs bracket-quoting for the JDBC
`dbtable` option; encoded that literally in the YAML.

### What warrants review

- `config/sources/dsa.yml`: confirm the four target schema/table names and the dbo-vs-stg choice for
  `Alternative_FearGreedIndex`; decide keys/watermark now that the schema notes are in front of you.
- The union path (`_read_union`) is unit-tested with fakes only — the real `unionByName` +
  `_source_table` behaviour against live Spark/JDBC is unverified offline; validate on a cluster run.
- Server-name discrepancy (`sql-sic-dev-01` vs `datavault2020`): confirm which the `datavilla-dev-sql`
  secret's `server` key points at before the live run.
- Deploy flow: `python scripts/generate_jobs.py` → `databricks bundle validate` → `deploy`. The
  generated `resources/*.job.yml` are committed; `generate_jobs.py --check` guards drift.

### Future work

main: fill keys/watermark per the dsa.yml notes once decided; resolve the dbo/stg FearGreed choice and
the server discrepancy; run `generate_jobs.py` + bundle deploy; attempt the first live union load and
confirm `_source_table` + null `TransactionId` for 2021 rows land as designed.

## Step N+1: Benny's two adjustments — typed FearGreed source + discard empty 2021, exact keys/watermark

**Author:** main

### Prompt Context

**Verbatim prompt:** "Benny har besluttet to justeringer i config/sources/dsa.yml. Da du har
inspiceret de rigtige skemaer live, udfyld keys/watermark PRÆCIST fra dem — gæt ikke kolonnenavne;
re-verificér mod DSA hvis du er i tvivl. ... 1. alternative_feargreedindex → skift kilde til den
TYPEDE stg-tabel ... udfyld keys + incremental.watermark_column ... 2. historic_transactions →
DISCARD den tomme 2021-tabel: Reducér source fra union til en ENKELT tabel: kun
stg.[HistoricTransactions_2017-2020] ... keys: [TransactionId]. Sæt watermark hvis en egnet
stigende/dato-kolonne findes ... 3. Ryd op i dsa.yml-kommentarerne: ret server-referencen
sql-sic-dev-01 → datavault2020 ... 4. Regenerér jobs ... kør pytest."

**Interpretation:** Repoint FearGreed at the typed `stg` table and fill its real PK/watermark; collapse
`historic_transactions` from a union to the single 2017-2020 table with `TransactionId` as key (and
watermark if suitable); keep the union feature in the framework; fix the server comment; regenerate
and re-test. Re-verify against DSA — no guessed column names.

**Inferred intent:** Now that the schema is known, turn the two "confirm later" placeholders into
committed, evidence-grounded key/watermark decisions, and drop the dead empty table.

### What I did

Re-verified both tables live first (the coordinator said re-verify if in doubt, and I had not done a
clean schema-filtered pass on the *typed* stg FearGreed table nor checked whether `TransactionId` is an
identity). Fresh throwaway pyodbc install in `C:\claudes_folder\tmp_pyodbc2` (deleted after), same
token path. Findings:
- `stg.Alternative_FearGreedIndex`: PK = `timestamp`, type `datetime2`, NOT NULL, 1439 rows; top
  values are daily dates (2022-05-26, 25, 24). Genuine datetime → key AND watermark.
- `stg.[HistoricTransactions_2017-2020]`: PK = `TransactionId`, `int`, `is_identity=1`, min=1 max=4065
  distinct=4065 over 4065 rows → strictly increasing, gapless, unique → key AND incremental watermark.
  `Date` is varchar(50) free text (`'1999-12-31 23:59:59 UTC'`), so the identity PK is the right
  watermark, not `Date`.

Then edited `config/sources/dsa.yml`: FearGreed → `source.table: stg.Alternative_FearGreedIndex`,
`keys: [timestamp]`, `watermark_column: timestamp`; historic → single `table:
stg.[HistoricTransactions_2017-2020]` (removed the `tables:` union and the 2021 member), `keys:
[TransactionId]`, `watermark_column: TransactionId`. Rewrote the header inventory (four tables, 2021
noted as discarded, server = `datavault2020.database.windows.net`) and both source comments. Updated
`test_config.py` (the union test became a single-table+key test; added a FearGreed key/watermark test),
the README schema note, regenerated jobs, and ran the suite.

### Why

The union feature stays in `config.py`/`jdbc.py` for real multi-table entities, but this specific
source no longer needs it — a single keyed table is simpler and truthful to the data. Every
key/watermark value now traces to a `SELECT` I ran, not a guess.

### What worked

`generate_jobs.py` produced an identical job set (source names unchanged), so `--check` was clean with
no manual job edits — exactly the payoff of job-from-config. `python -m pytest` → 25 passed. The
identity-column check (`sys.columns.is_identity` + min/max/distinct/count) turned "TransactionId int PK"
into a defensible watermark claim rather than an assumption that it increases.

### What didn't work

No failures this step. The earlier `SourceDefinition.load(path)` single-source helper is now unused by
the shipped config (everything routes through `load_all_sources`), but I kept it — it is still the
backward-compatible single-file path and is covered by tests; removing it would be scope creep.

### What I learned

The typed `stg.Alternative_FearGreedIndex` is a proper modelled table (name/value/value_classification/
timestamp + DV_* lineage columns, PK on `timestamp`), whereas the `dbo` copy was an empty untyped
staging shell — so "same table name, different schema" cut across dbo/stg here too, not just across the
HistoricTransactions years. And `TransactionId` being a true IDENTITY (not merely a PK that happens to
look sequential) is what makes it watermark-safe.

### What was tricky

`timestamp` is a T-SQL reserved word but is the literal column name — recorded that in the YAML so
Blok 2 remembers to quote it. Judging watermark suitability needed more than "is it the PK": I checked
monotonicity/gaplessness for the int and the actual datetime values for FearGreed before committing
either as a watermark.

## Step N+2: Live raw-write failure on spaced column names — Delta column mapping fix

**Author:** main

### Prompt Context

**Verbatim prompt:** "Live-resultat: 2 af 3 nye kilder ingesterede rent (sparekassenkronjylland_konti_base,
alternative_feargreedindex fra stg). historic_transactions FEJLEDE — men ikke på auth/JDBC (læsningen
lykkedes). Delta-write fejlede: [DELTA_INVALID_CHARACTERS_IN_COLUMN_NAMES] Invalid column names:
Sending Wallet ... FIX (generisk, i src/datavilla/write/raw.py): Enable Delta column mapping på
raw-tabellerne ... delta.columnMapping.mode = 'name' (+ minReader/minWriter 2/5). Gør det GENERISK for
alle raw-writes ... Bevar append-only + audit-kolonner + _source_table uændret. Kør pytest. ... bekræft
hvordan mapping sættes (create-time vs alter) og hvad der sker med de allerede-skrevne raw-tabeller."

**Interpretation:** The read worked; Delta refused to create the historic table because `Sending Wallet`
has a space. Fix generically in `write/raw.py` by enabling Delta column mapping (`name` mode + protocol
2/5) so bronze keeps original names verbatim, no sanitising. Keep append-only + audit columns unchanged.

**Inferred intent:** A bronze layer must be faithful to the source; renaming columns to satisfy Delta
would corrupt raw provenance. Column mapping is the mechanism that lets messy source names survive.

### What I did

Reworked `src/datavilla/write/raw.py`: added `RAW_TABLE_PROPERTIES`
(`delta.columnMapping.mode=name`, `delta.minReaderVersion=2`, `delta.minWriterVersion=5`) and a new
`_ensure_raw_table(target, schema, spark)` that does `CREATE SCHEMA IF NOT EXISTS` then builds the table
with `DeltaTable.createIfNotExists(spark).tableName(target).addColumns(df.schema).property(...).execute()`.
`write_raw` now calls it before the append. Building from the DataFrame's StructType (not a DDL string)
is deliberate: spaced/special names pass through structurally with no quoting or sanitising. The append
stayed exactly as it was (append-only, mergeSchema, audit columns, `_source_table` untouched). Exported
`RAW_TABLE_PROPERTIES`, updated the module docstring and the README ("Faithful column names" subsection).
Added `tests/test_write_raw.py` (fakes Spark + `delta.tables.DeltaTable` + `pyspark.sql.functions`) to
assert the create-with-mapping-then-append wiring. `python -m pytest` → 26 passed.

### Why

Create-time-only (`createIfNotExists`) is the whole trick for the "what about the 3 existing tables"
question: it is a no-op on a table that already exists, so it never alters or breaks the tables already
written without mapping, and it never touches the append path. New tables (historic, on main's re-run)
are born with mapping; old ones are left alone and do not need it.

### What worked

The DataFrame-schema builder path sidesteps the exact failure cleanly — no DDL string means no place for
`Sending Wallet` to blow up on a bracket/quote. The offline fake-Delta test pins the generic behaviour
(properties applied, `addColumns` fed the df schema, append with mergeSchema to the same target) without
needing a cluster, so a future refactor that drops the mapping property would fail a test, not a live run.

### What didn't work

No failures this step. The live failure being fixed was main's, verbatim:
`[DELTA_INVALID_CHARACTERS_IN_COLUMN_NAMES] Invalid column names: Sending Wallet`. I could not reproduce
the Delta write live (no cluster here); the fix is validated by the wiring test + Delta docs, and flagged
as needing main's re-run to confirm end to end.

### What I learned

Column mapping is a table-level property that must exist at creation for `addColumns`'d columns to be
mapped — setting it in the same builder before `execute()` covers all columns including the spaced ones.
Setting `columnMapping.mode=name` auto-upgrades the protocol, but pinning reader v2 / writer v5 explicitly
keeps the created table's requirements reproducible rather than implicit.

### What was tricky

The "existing tables" question was the subtle part: the pragmatic answer (create-time only) is also the
safest — an unconditional `ALTER ... SET TBLPROPERTIES` on every write would upgrade the protocol of
tables that do not need it and add per-run overhead, for no benefit. Documented the one-off ALTER escape
hatch in the README without wiring it in.

### What warrants review

- `write/raw.py` `_ensure_raw_table`: unit-tested with fakes only. The real `DeltaTable.createIfNotExists`
  + `addColumns(StructType)` + column-mapping behaviour against live UC Delta is unverified offline —
  main confirms on the historic re-run that `Sending Wallet` et al. land verbatim.
- Confirm `saveAsTable(mode=append, mergeSchema=true)` composes with a pre-created column-mapped table on
  the target DBR (expected yes; verify on the re-run).
- The 3 already-written raw tables remain unmapped by design; noted in README.

### Future work

main: re-run `historic_transactions` live and confirm the raw table is created with column mapping and
the spaced source columns (`Sending Wallet`, `Gain (DKK)`, ...) are preserved verbatim; then the four DSA
sources are all landing to raw.

### What warrants review

- `config/sources/dsa.yml`: the two bank sources still have empty keys/watermark by design (no PK,
  free text) — unchanged and correct; the two crypto/index sources now carry live-confirmed values.
- `historic_transactions` is no longer a union; the union code path is now exercised only by
  `test_jdbc_union.py` (synthetic) and remains unvalidated against live Spark until a real multi-table
  source appears.
- `TransactionId` as an *append-only-safe* watermark assumes new rows always get a higher id; true for
  IDENTITY, but confirm the upstream loader never resets/reseeds it before relying on it in Blok 2.

### Future work

main: run `generate_jobs.py` + `databricks bundle validate`/`deploy`; first live load of the four
sources; verify the run-log rows and that FearGreed lands `timestamp` and historic lands `TransactionId`
as expected. Bank-source keys remain a deliberate open item for whenever those tables gain structure.
