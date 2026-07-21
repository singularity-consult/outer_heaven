# Diary: Datavilla Koinly file-drop source (snapshot-per-year load)

Add Koinly (crypto tax export) as a new file-drop source in the datavilla repo,
for two separate accounts (erhverv + privat), each on its own landing/raw schema
and its own ingest job (same separation model as Kraken). Unlike the existing
e-conomic file-drop source, Koinly does NOT use SCD2: each annual CSV is the full
truth for its year, so the load model is a brand-new snapshot-per-year overwrite
(Delta `replaceWhere "year = <yr>"`), not a merge. Goal: green live in dev,
verified row counts per year/account, and a snapshot re-upload test proving a
re-uploaded year REPLACES rather than duplicates. Not committed — handed back to
main for review + commit.

## Step 1: Requirements shaping, data verification, and builder kickoff

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Byg Koinly som ny file-drop-kilde i datavilla-repoet
(C:\claudes_folder\repos\datavilla) og driv builder til at gøre det grønt live i
dev. Solo-læringsprojekt, Azure 'Microsoft Partner Network', git-identitet
allerede korrekt (singularity-consult <benny@singularityconsult.dk>, INGEN
Co-Authored-By). HEAD er nu d8e0e2a." Followed by verified context (metadata-driven
YAML framework, Databricks/PySpark, DAB; e-conomic = existing file-drop pattern
using SCD2; job_group keys on landing.schema; raw schema auto-created; landing
schema via infra), the two-account data description (koinly-erhverv 6 files
2021-2026, koinly-privat 2017-2026 with a byte-identical duplicate 2024 file),
the verified CSV format (preamble skip of 2 lines before header, ASCII no BOM,
quoted, dot-decimal, "YYYY-MM-DD HH:MM:SS UTC" dates, 20 columns incl. names with
spaces/parens), and LOCKED decisions: (1) two accounts separated on both schema
AND job like Kraken; (2) load model = snapshot per year (overwrite) via a NEW
load_type, NOT SCD2, with a `year` column derived from the FILENAME and Delta
`replaceWhere`; (3) NO dedup anywhere in raw/enriched (Benny dedups in curated);
(4) duplicate 2024 file kept out of landing. Plus DoD: pytest green (124 must not
break; add tests for snapshot-load + preamble-skip + year-extract); both jobs
green live; snapshot re-upload test; existing sources untouched; NOT committed.

Mid-task decision from Benny (verbatim): "OPTION B — de 8 numeriske kolonner ...
gemmes som STRINGS i raw, eksakt kildetekst (behold tusindtals-komma som
'12,345.67' — INGEN parsing/komma-strip af dem i raw). Typning + forretningslogik
sker i curated. Faithful bronze. ... decimal_columns = [] ... date_columns =
[Date] (parse til timestamp). Tilføj year INT udledt af FILNAVNET ... Konsekvens:
... dropp csv_parse-generaliseringen for tusindtalsseparator ... Alt andet står
som i mit oprindelige brief ... Kør."

**Interpretation:** Build a third write mode into the ingestion framework
(snapshot-per-year overwrite) alongside the existing append (`write_raw`) and
`scd2` (`write_scd2`); wire Koinly as two file-drop sources; keep all 8 amount
columns as faithful source strings; parse only `Date` to a timestamp and derive a
`year` INT partition column from the filename; provision dev landing schemas
additively; upload the real files (minus the duplicate); prove it green live and
prove the snapshot semantics; hand back without committing.

**Inferred intent:** Extend the metadata-driven framework with a genuinely
different load pattern (full-snapshot-per-partition) without contaminating the
SCD2/append paths, while keeping raw a byte-faithful bronze mirror so the
messy curation (dedup, Kraken overlap, typing) stays a deliberate curated concern.

### What I did

Read the framework end to end before forming any opinion: `src/datavilla/config.py`
(SourceDefinition, FileConfig, LandingConfig, VALID_HISTORY/VALID_LOAD_TYPES,
job_group keyed on landing.schema), `src/datavilla/autoload.py` (`_read_plan`
selects reader options/transform/writer; writer choice is driven by `history`,
not `load_type`), `src/datavilla/write/{raw,scd2,csv_parse,autoloader}.py`,
`src/scripts/generate_jobs.py` (FILE_JOB_TEMPLATE, for_each over subjects, one job
per landing.schema), the e-conomic and both Kraken YAMLs, and the infra
`landing_schemas` for_each + the kraken_privat additive commit (d8e0e2a) as the
exact additive template.

Verified the real data in C:\claudes_folder\mixed_files (personal finance — never
in git): preamble is line 1 title "Transaction report YYYY", line 2 blank, line 3
real 20-col header, data from line 4; no BOM ("Tra" as first 3 bytes); the
duplicate 2024 privat file is byte-identical (md5 bafef682... on both). Computed
exact expected raw row counts via proper CSV parsing (handles any quoted
newlines): ERHVERV 2021=91, 2022=117, 2023=152, 2024=330, 2025=201, 2026=300
(total 1191); PRIVAT (excl. dup) 2017=1250, 2018=1533, 2019=297, 2020=1096,
2021=5594, 2022=1328, 2023=526, 2024=1086, 2025=652, 2026=177 (total 13539). Both
match Benny's ballpark (~1190 / ~13,540).

Surfaced one finding that contradicted the brief and drove a real decision: the
amounts are NOT plain dot-decimal. Fiat/DKK fields carry US-style comma thousands
separators inside quotes (Net Value `"12,345.67"`, cost basis `"8,765.43"`,
negative `"-9,876.54"`), and even some crypto quantities do (`"9,999.99999999"`);
crypto quantities are dot-decimal to max 8 fractional digits across every file.
Presented Benny two options: A = typed `decimal(38,18)` (his brief's "parse
dot-decimal", but Delta `try_cast` would silently round a future >18-digit token
and the parse gate only catches NULLs, not rounding), vs B = keep the 8 as exact
source strings (100% faithful bronze, matches his "raw ingesterer alt faithfully"
rule). Benny chose B.

### Why

The whole point of this source is a different load shape from e-conomic. e-conomic
is date-filtered and can re-deliver overlapping rows, so SCD2 + content hash makes
overlap a no-op. Koinly's annual export is instead a FULL snapshot of one year, so
the correct primitive is "replace this year's partition wholesale" — which also
naturally preserves within-year identical duplicate rows (no dedup) and gives a
clean re-export. That is neither append nor SCD2, hence a new writer.

Option B keeps raw byte-faithful: the comma-thousands strings are stored verbatim,
and all typing/dedup/overlap-resolution stays a curated concern, which is exactly
Benny's stated division of labour. It also shrinks the diff — no thousands-separator
generalization of `csv_parse` is needed.

### What worked

The framework was clearly designed for exactly this extension: `_read_plan`
dispatches the batch writer off `history`, `VALID_HISTORY` is an explicit
frozenset, and the FILE_JOB_TEMPLATE + `job_group` (landing.schema) mean two new
accounts become two jobs additively with zero changes to existing job names. The
kraken_privat commit is a turn-key template for the additive `landing_schemas`
change (set-add, `moved` blocks untouched, raw schema auto-creates at run).

### What didn't work

No failures yet — this step is requirements shaping and data verification, not
implementation. The one course-correction was mine-to-Benny: the brief's
"dot-decimal, ikke komma" description missed the comma thousands separators;
flagged with concrete examples and resolved to Option B before any code.

### What I learned

Two non-obvious framework facts that will shape the build: (1) the writer is
selected by `history`, not `load_type` — `load_type` is carried for the run-log
only (see write/raw.py docstring). So although Benny called the new mode a "new
load_type", the correct seam is a new `history` value (`snapshot`), exactly
parallel to how `scd2` was added; I'll build it there and document the deviation
from his wording for review. (2) The existing `_date_expr` in csv_parse forces
`CAST(try_to_timestamp(...) AS DATE)`, which drops the time-of-day — unusable for
Koinly's `Date`, which must keep `HH:MM:SS`. So a small additive timestamp path in
csv_parse is still required even under Option B (only the thousands-separator work
is dropped), and it must leave e-conomic's generated expressions byte-identical
(its unit tests assert exact expression strings).

Also: `year` is best defined as "the export FILE's year" (from the `koinly_YYYY`
filename token via the `_source_file` audit column), not per-row transaction year.
That makes the snapshot/`replaceWhere` model robust even if a file happens to hold
a stray cross-year row, and turns Benny's "one file = only its year" question into
a verify-and-report item rather than a correctness dependency.

### What was tricky

The snapshot writer must not assume one year per micro-batch: Auto Loader
`availableNow` can drain several annual files in a single batch, so the writer has
to compute the DISTINCT years present in the batch and build
`replaceWhere "year IN (...)"` over exactly those, writing the whole batch (every
row's year is in the set by construction). First full load = all years replaced;
re-upload of one year = only that year's partition replaced. This is the crux of
the design and the thing the snapshot test must prove.

The preamble skip is the biggest live unknown: vanilla Spark CSV has no
`skipRows`; Databricks' cloudFiles CSV is documented to support `skipRows`, but it
MUST be verified on the cluster early (with the blank line 2 counted), because if
it is not honoured, header inference latches onto the "Transaction report YYYY"
title line and the whole schema is wrong.

### What warrants review

The new `history: snapshot` seam (vs Benny's "load_type" wording); the
`write_snapshot` implementation (distinct-years `replaceWhere`, partition-by-year
table creation with Delta column mapping for the spaced/paren column names); the
additive timestamp path in csv_parse (must not perturb e-conomic); the `year`
derivation from filename; and the infra `landing_schemas` diff (must be 0-destroy,
moved blocks untouched). Live verification: per-year/account counts equal the
targets above, and the snapshot re-upload test leaves the re-uploaded year's
partition count unchanged (not doubled) with all other years untouched.

### Future work

test/prod `landing_schemas` for Koinly (dev only for now); curated-layer typing +
dedup + Kraken-overlap resolution (Koinly privat's "Kraken - <konto>" wallet
overlaps the Kraken source by design); and confirming decimal precision headroom
if a future Koinly export ever emits a >8-fractional-digit token.

### Builder handoff

Spawning one builder (outer_heaven:builder) with the full refined requirements
below. One builder, not several: this is a single tightly-coupled feature
(config + new writer + csv_parse timestamp path + infra + upload + live verify)
with no independent parallelizable slices.

## Step 2: Build the snapshot writer + Koinly sources, and drive green live in dev

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** "Build Koinly as a new file-drop source in the datavilla repo
and drive it green live in dev. Repo: C:\claudes_folder\repos\datavilla (you share
the lead's worktree; current HEAD d8e0e2a on master). ... DO NOT COMMIT — leave all
changes in the working tree and hand back to the lead for review + commit." Followed
by the full refined brief: study the existing pattern first; build a THIRD write
mode `snapshot` as a new `history` value (not a load_type); `write_snapshot` with
distinct-years `replaceWhere` and partition-by-year table creation; a `year` INT
from the filename token; additive csv_parse timestamp + preamble-skip support that
keeps e-conomic byte-identical; a `koinly` file adapter; koinly.yml with two
accounts; additive dev infra; upload the real files (excl. the byte-identical 2024
dup); DoD = pytest green (124 must not break, add snapshot/preamble/year/timestamp/
config tests), both jobs green live with per-year/account counts equal to the
targets, a snapshot re-upload test proving replace-not-double, existing sources
untouched, NOT committed.

**Interpretation:** Extend the metadata-driven ingestion framework with a
snapshot-per-partition writer that lives at the `history` seam alongside
write_raw/write_scd2, wire Koinly as two file-drop sources (one per account, own
schema + own job), keep raw byte-faithful (amounts as source strings, only Date
typed to timestamp), provision the two dev landing schemas additively, then prove
it end-to-end on the live dev workspace and hand back uncommitted.

**Inferred intent:** Prove the framework can absorb a genuinely different load
pattern (full-snapshot-per-partition overwrite) without contaminating the append or
SCD2 paths, and validate it against real data rather than asserting it works.

### What I did

Read the whole framework before writing a line: config.py, autoload.py,
write/{raw,scd2,csv_parse,autoloader}.py, generate_jobs.py, the economic/
kraken_privat YAMLs, the infra unity_catalog module, and every relevant test. Then
verified the real data with a proper CSV parser (handles quoted newlines): all 16
files' record counts matched the targets exactly, no BOM (first bytes "Tra"), the
2024 privat dup is byte-identical (md5 bafef682...), and — the "one file = only its
year" question — every file's Date-year equals its filename-year with ZERO
mismatches across all 16 files. Reported that; the model still keys `year` off the
filename so it does not depend on it.

Implementation, all additive:
- config.py: `snapshot` added to VALID_HISTORY (with a comment documenting why it
  is a `history` value and not a `load_type`); `koinly` added to FILE_ADAPTERS;
  FileConfig gained `timestamp_columns`, `timestamp_format`, `skip_rows`,
  `year_from_filename`, all defaulting to a no-op so e-conomic is unchanged; the
  date/decimal overlap check generalized to a 3-way check including timestamps.
- write/raw.py: `YEAR_COL = "year"` constant (the shared spelling for transform +
  writer); `ensure_raw_table` gained an optional `partition_by` (default None, so
  append/SCD2 are byte-identical).
- write/snapshot.py (new): `write_snapshot` with the BatchWriter signature —
  computes the DISTINCT years in the batch, creates the table PARTITIONED BY (year)
  with column mapping, overwrites with `replaceWhere "year IN (...)"` +
  mergeSchema, rejects a NULL year loudly (analogous to SCD2's assert_keys_not_null),
  returns rows_in==rows_out==rows_inserted. Plus a pure `replace_where_predicate`.
- write/csv_parse.py: `_timestamp_expr` (try_to_timestamp WITHOUT the CAST AS DATE);
  `_typed_expr`/`validate_columns` extended for timestamps; `add_partition_year` +
  `partition_year_expr` deriving `year` from `_source_file` via
  `regexp_extract(..., 'koinly_([0-9]{4})_', 1)` — `[0-9]` not `\d` to sidestep
  Spark SQL string-literal backslash ambiguity; wired into parse_csv_batch gated by
  `year_from_filename` so parse_expressions (and e-conomic) stay byte-identical.
- write/autoloader.py: `csv_reader_options` gained `skip_rows`, emitting `skipRows`
  ONLY when > 0 (economic unchanged).
- autoload.py `_read_plan`: `elif history == "snapshot": writer = write_snapshot`.
- config/sources/koinly.yml (new): two sources (koinly_erhverv/koinly_privat),
  adapter koinly, snapshot, keys [], skip_rows 2, timestamp_columns [Date],
  timestamp_format "yyyy-MM-dd HH:mm:ss 'UTC'", decimal_columns [],
  year_from_filename true, with a thorough header comment.
- infra: added koinly_erhverv/koinly_privat to `landing_schemas` (set-add; moved
  blocks untouched).
- Tests: new test_snapshot.py (7 cases incl. the multi-year batch and null-year),
  new test_koinly.py (config + _read_plan wiring + the three-pattern boundary),
  plus additions to test_csv_parse.py (timestamp expr, gate coverage, year
  extraction, economic-unchanged), test_autoloader.py (skipRows), test_config.py
  (snapshot history, new FileConfig fields, 3-way overlap), and the count updates in
  test_generate_jobs.py (7->9 jobs) and test_config.py (source set). 124 -> 156
  passing, the original 124 unchanged.

Live in dev (env: DATABRICKS_TF_EXEC_PATH + DATABRICKS_TF_VERSION=1.14.6 required
for `bundle deploy` — without them it tried to download terraform and failed on an
expired PGP key): terraform plan = "4 to add, 0 to change, 0 to destroy" (2 schemas
+ 2 volumes, only the koinly keys), applied; regenerated jobs (`--check` clean);
`bundle deploy -t dev --var cluster_policy_id=0016CFDC5ABE5A9C`; created the dated
landing folders and uploaded 6 erhverv + 10 privat files (dup excluded) via
`databricks fs cp`; ran both jobs with `run-now --no-wait` + polled `get-run`.

### Why

The `history` seam is the correct home for a third write mode because
`_read_plan` dispatches the writer off `definition.history` (load_type is run-log
metadata only). Keeping every new field defaulted to a no-op and adding the year
column AFTER parse_expressions (not inside it) is what lets e-conomic's exact-string
expression tests stay byte-identical while Koinly gets timestamp + year handling.

### What worked

Everything the lead predicted about the framework held: the additive infra set-add
planned 0-destroy, the two accounts became two jobs with no change to existing job
names, and the writer seam took the new writer cleanly. Live counts matched the
targets to the row: erhverv 2021=91/2022=117/2023=152/2024=330/2025=201/2026=300
(total 1191); privat 2017=1250/2018=1533/2019=297/2020=1096/2021=5594/2022=1328/
2023=526/2024=1086/2025=652/2026=177 (total 13539, dup correctly absent — 2024=1086
not 2172). The biggest live unknown, cloudFiles `skipRows`, WORKS: the raw schema
is the real 20-column header (Date..Description), not the "Transaction report YYYY"
title line; Date is TIMESTAMP, amounts are STRING with spaced/paren names preserved
("Sending Wallet", "Gain (DKK)"), year is INT; `_rescued_data` all-null and zero
date-parse failures.

The snapshot re-upload test is the clean proof: after re-uploading only the 2026
erhverv file to a new dated folder and re-running, 2026 stayed 300 (not 600) and
total stayed 1191, while `_load_batch_id`/`_ingested_at` show years 2021-2025 all
still carry the FIRST run's batch id (293dbaa7..., 08:06:55) and 2026 alone carries
a NEW batch id (4fc83efd..., 08:41:00) — exactly one partition replaced, the rest
untouched. Append would have doubled 2026; SCD2 would have needed a key.

### What didn't work

Two live snags, both mechanical: (1) `databricks bundle deploy` first failed with
"error downloading Terraform: unable to verify checksums signature: openpgp: key
expired" because I had not exported DATABRICKS_TF_EXEC_PATH/DATABRICKS_TF_VERSION —
fixed by setting them (they point the CLI at the local terraform). (2) `databricks
fs cp` failed with "no such directory: .../2026/07/21" — the dated folder must be
created with `databricks fs mkdir` first; the volume does not auto-create
intermediate dirs. Also a self-inflicted quoting failure: escaped double-quotes in
a `databricks api post --json '...'` one-liner produced empty output (JSONDecodeError
"Expecting value"), so I wrote a small dsql.py helper (Statement Execution API + az
token) for all SQL verification instead. No implementation failures — offline tests
were green on the first full run after the edits.

### What I learned

cloudFiles CSV `skipRows` IS honoured on DBR 15.4 with header=true +
inferColumnTypes=false + a persisted schemaLocation — the blank line 2 is counted,
and line 3 becomes the header. This was the one thing that could have invalidated
the whole schema and it is now verified live, not assumed. Also confirmed
`mode("overwrite") + replaceWhere("year IN (...)") + mergeSchema + partitionBy` on a
partitioned column-mapping table behaves exactly as the design needs, including a
multi-year first-load batch (all six erhverv years drained in one availableNow batch
and each partition written).

### What was tricky

The `year` derivation had to be config-gated and placed after the typing selectExpr,
or it would either perturb e-conomic's byte-identical expressions or add a null
`year` column to every e-conomic raw table. Keeping `YEAR_COL` in raw.py (imported
by both csv_parse and snapshot) avoids the transform depending on the writer module
or vice versa. And the regexp needed `[0-9]{4}` rather than `\d{4}` because Spark
SQL string literals treat backslash as an escape character — `\d` is ambiguous
across runtimes, a character class is not.

### What warrants review

The `history: snapshot` seam and write_snapshot (the distinct-years predicate is the
crux — reviewed live with a 6-year batch); the additive csv_parse timestamp/year
paths (e-conomic byte-identical is asserted by its unchanged tests, all still
green); the koinly.yml decisions (faithful-string amounts, timestamp 'UTC' literal,
skip_rows 2, year_from_filename); and the infra set-add (planned + applied
0-destroy, moved blocks untouched). Everything is in the working tree, NOT committed,
per the brief — the lead reviews and commits. Author identity for the eventual
commit stays singularity-consult <benny@singularityconsult.dk>, no Co-Authored-By.

### Future work

test/prod `landing_schemas` + bundle targets for Koinly (dev only for now); the
curated-layer typing/dedup and Kraken-overlap resolution; and a cleanup of the
throwaway landing folders if desired (the 2026/07/22 snapshot-test folder and the
2026/07/21 initial-load folder both remain in the dev landing volume by design —
Auto Loader tracks them by path).
