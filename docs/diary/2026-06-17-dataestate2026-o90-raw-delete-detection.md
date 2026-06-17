# Diary: DataEstate2026 - Ø90 raw delete detection (new estate)

Building the missing Databricks delete-detection brick for Ø90 raw in the new
DLBR-DataEstate2026 platform (lighthouse framework). Raw must track deletes and
keep SCD2 history. Scope is the raw layer and the 19 full-load Ø90 tables now,
but the notebook is conditional so the incremental tables work later.

## Step 1: Build delete-detection notebook + meta SQL + wiring assessment

**Author:** builder (outer_heaven:builder sub-agent)

### Prompt Context

**Verbatim prompt:** Byg den manglende Databricks delete-detektions-brik for Ø90
raw i nyt estate. Raw skal kunne tracke deletes (og historik via SCD2). Scope:
raw-laget; de 19 full-load Ø90-tabeller nu, men notebooket skal være BETINGET så
de inkrementelle virker senere. Deliverables: (1) nyt notebook
`load_to_raw_update_deleted_flags.py` der itererer source-objects fra meta,
betinget nøglekilde pr. tabel (run_keys_flow), kalder `write.soft_delete`, med
PK-sanitizing-alignment; (2) idempotent meta SQL der sætter WritePattern=
'stream_scd2' for de 19 full Ø90-tabeller; (3) workflow-wiring beskrivelse
(delete-pas EFTER raw-load). Må ikke ændre load_to_raw_general.py, prod-workflows,
.ps1, ingen UTC/datatype-konvertering, ingen push. Commit lokalt på feature-branch,
author Benny Christiansen <bech@seges.dk>.

**Interpretation:** Create a new, generic raw delete-detection notebook in the
new estate that mirrors `load_to_raw_general.py`'s metadata-driven structure,
picks its key source conditionally per table (Keys-snapshot vs newest full
snapshot), and delegates to `write.soft_delete`. Plus an idempotent T-SQL fix
and an honest assessment of how/where to wire the pass into a workflow.

**Inferred intent:** Close the historical/delete gap that the legacy estate
solved with `load_to_raw_update_deleted_flags.py`, but on the new lighthouse
API (soft_delete/upsert_type_2), without disturbing the shared general loader or
prod. Stay faithful-to-source in raw; defer UTC/typing to the enriched rebuild.

### What I did

Read the verified facts in the new estate before writing anything: the shared
loader `solutions/databricks/01_raw/load_to_raw_general.py`, the lighthouse
`write.py` (soft_delete ~618, upsert_type_2 ~528, generic_upsert_type_2 ~655),
the `meta.IngestDefinitions` view and its base `meta.SourceObjectDefinitions`
view, the SQL metadata adapter `lighthouse/adapters/metadata/sql.py`, the config
column names in `lighthouse/config/base_configuration.yml`, the cleaners, and the
legacy reference patterns in the old `dataestatedlbr` estate (read-only).

Then I created two files in the new estate:

- `solutions/databricks/01_raw/load_to_raw_update_deleted_flags.py` - the new
  notebook. It uses the same `meta_where_clause` widget and
  `metadata.source_object_metadata(adapter='sql', source=...)` pattern as the
  general loader, the same 4-worker ThreadPoolExecutor fan-out, and the same
  raw-table naming (`config.raw_catalog`.`connection_name`.`sanitizer_source_object(...)`.lower()).
  Per source object it picks the key source conditionally: `run_keys_flow == 1`
  reads the newest `/Keys/` snapshot; otherwise (full loads, run_keys_flow == 0)
  it reads the newest full snapshot from `source_path`. Both go through a
  recursive `get_latest_file_path` (ported pattern from the legacy single-entity
  notebook) so only the newest file in the dated append folder is read, not the
  whole accumulating folder. The snapshot is passed through
  `cleaners.sanitizer_unit_labeled_columns` (exactly as the general loader does
  to the main data) before `select(*primary_key_columns).distinct()`, then
  `write.soft_delete(source_keys_df=..., destination_table=..., primary_key_columns=...)`.

- `solutions/sql_database/meta/Scripts/set_o90_full_tables_writepattern_scd2.sql`
  - idempotent T-SQL that sets `SourceObjectIngestSetup.WritePattern='stream_scd2'`
  for full-load (IncrementalFlag=0) objects on the Ø90 connection. Guarded with an
  explicit transaction, a row-count abort (>19), and before/after verification
  SELECTs. The connection name is a `@ConnectionName` variable defaulting to
  'o90' that Benny must confirm.

Validated the notebook with `python -c "import ast; ast.parse(...)"` -> SYNTAX OK.

### Why

`write.soft_delete` builds an empty target-shaped df and calls `upsert_type_2`
with `detect_deletes=True`, which in `generic_upsert_type_2` does
`target.filter(is_current=true AND is_deleted=false).join(source_keys_df,
primary_key_columns, "left_anti")` and closes+reopens those rows as deleted. So
the whole brick reduces to "build the correct full key set and call soft_delete".
The conditional key source is required because full loads (run_keys_flow=0) have
no `/Keys/` snapshot per the IngestDefinitions view (line 67-70), so keys must be
derived from the full data snapshot instead.

### What worked

The new estate's API made this small: soft_delete already encapsulates the
close+reopen MERGE that the legacy notebook hand-wrote. The metadata adapter
already exposes `run_keys_flow`, `source_path`, and `source_keys_path` in
`extra_fields`, so the conditional needed no new metadata. AST syntax check
passed first try.

### What didn't work

No failures. I could not run live Databricks (no cluster/Unity Catalog here), so
the merge behavior, the dbutils.fs snapshot resolution, and the actual PK
alignment against the deployed raw tables are unverified - this is a real,
stated limitation, not a smoothed-over claim.

### What I learned

Key-name alignment is the subtle part. The raw target columns were created by the
general loader from `sanitizer_unit_labeled_columns` output (case preserved,
special chars cleaned), while `generic_upsert_type_2` lowercases
`primary_key_columns` via `sanitize_string` before the join. These only line up
because Spark resolves column names case-insensitively by default. The safe path
is to sanitize the snapshot exactly as the general loader does and select the
metadata PKs - which are themselves already ø->oe/space->_ cleaned by the
IngestDefinitions view (line 45). Mismatch there would silently anti-join
everything as deleted, so it is the first thing to validate on a real run.

### What was tricky

The wiring question has no clean answer in the new estate. The only
`load_to_raw_general` wiring that exists is `master_oe90_dash.yml` (connection
`oe90dash`), and `ingest_o90_data_serverless.yml` is enriched-only. There is no
discoverable workflow that runs the raw load for the main Ø90 connection (the 19
full tables) - consistent with the DB2/ADF migration still being in progress, so
that raw load likely runs from ADF, not a Databricks workflow here. I did not
invent a workflow; the delete-pass placement depends on where the Ø90 raw load
actually runs, which is Benny's call.

### What warrants review

1. The PK-alignment claim above - validate on a real run that the anti-join keys
   match the deployed raw table columns (a wrong match deletes everything).
2. `@ConnectionName='o90'` in the SQL script - confirm against the real
   `meta.SourceConnections.Name` before running, and that exactly 19 rows match.
3. The full-snapshot key derivation assumes the newest full snapshot contains the
   complete current key set (true for full loads). Confirm that holds.
4. Whether `soft_delete` should run before or after the regular SCD2 upsert in a
   given run - I run it as a separate pass; ordering matters if both touch the
   same table in one job.

### Future work

Wire the delete-pass into whatever ends up driving the Ø90 raw load (ADF or a
new Databricks workflow). Once incrementals come online, validate the
`run_keys_flow == 1` branch against a real `/Keys/` snapshot. Revisit when the
enriched rebuild adds the deferred UTC-correction and datatype conversion.

## Step 3: Existence guard + load->delete workflow (the "wire it up" follow-on)

**Author:** builder (outer_heaven:builder sub-agent)

### Prompt Context

**Verbatim prompt:** (Danish, paraphrased headers verbatim) Fortsæt på den
EKSISTERENDE branch `feature/o90-raw-delete-detection`. OPGAVE 1: Tilføj
eksistens-guard til delete-notebooket — før `write.soft_delete(...)` tjek at
raw-tabellen findes; hvis ikke -> print skip-besked og `return`. Brug korrekt
UC tre-delt-navn eksistenstjek (sandsynligvis `spark.catalog.tableExists`).
OPGAVE 2: Byg Databricks-workflow (load -> delete) scopet til 19 o90-full: task 1
kører `load_to_raw_general.py` med `meta_where_clause` for de 19 full-tabeller;
task 2 kører `load_to_raw_update_deleted_flags.py` med SAMME clause og
`depends_on` task 1. Ingen schedule/trigger (manuel kørsel). Må ikke ændre
`load_to_raw_general.py`, prod-workflows eller .ps1. Ingen push. Author
`Benny Christiansen <bech@seges.dk>`.

**Interpretation:** Add a missing-table guard to the delete notebook so it skips
softly instead of crashing on `spark.table()`, and create one new manual DAB
workflow that runs the raw load then the delete pass over exactly the 19 Ø90
full tables, both keyed on the same metadata filter.

**Inferred intent:** Make the delete-detection brick from Step 1 actually runnable
end-to-end tomorrow without an orchestration foot-gun (deleting nothing, or
erroring on a table that the load has not created yet), while staying inside the
new estate and not touching the shared loader or prod schedules.

### What I did

First, a hard repo-orientation pass, because the prior session flagged repo
confusion as the main hazard. My CWD is `outer_heaven`, so bare `Glob`/`Grep`
(which default to CWD) returned nothing for the DataEstate paths and briefly
looked like "the files do not exist". Re-running every search with an explicit
`path=C:\claudes_folder\repos\DLBR-DataEstate2026` resolved it. I verified
`.git/HEAD` points at `feature/o90-raw-delete-detection` and the reflog tail
(line 422-424) shows commit 9600b37 ("Add Ø90 raw delete detection notebook and
meta WritePattern fix"). All target files sit at the repo root, none under
`.claude/worktrees/`.

Opgave 1: edited
`solutions/databricks/01_raw/load_to_raw_update_deleted_flags.py`. Added a guard
right after `raw_table` is built and after the existing no-PK skip, before any
snapshot read or `write.soft_delete`:
`if not spark.catalog.tableExists(raw_table): print(...); return`. I verified the
API choice against the framework itself - `lighthouse/helpers/table.py` uses
`spark.catalog.tableExists(table_name)` in ~15 places and
`lighthouse/helpers/common.py:163` wraps exactly that. `DeltaTable.isDeltaTable`
only appears in archived code and takes a path, not a name - so Benny's hunch was
right and the archived API would have been wrong.

Opgave 2: created
`solutions/databricks/workflows/ingest_o90_raw_full.yml`. Two tasks
(`load_to_raw_o90_full` -> `update_deleted_flags_o90_full` via `depends_on`),
both `notebook_task` with
`base_parameters.meta_where_clause: "connection_name = 'o90' AND IncrementalFlag = 0"`.
Classic `job_cluster` with `${var.DataEstateDefaultClusterDEV/TEST/PROD}` per
target, schedule PAUSED on all three targets (manual trigger this phase).

### Why

I followed `master_oe90_dash.yml` as the convention, because it is the only
workflow in the estate that wires this exact notebook (`load_to_raw_general.py`)
with a `meta_where_clause` and a `depends_on` - same `base_parameters` key, same
relative `../01_raw/...` notebook path, same classic-cluster shape. The serverless
`ingest_o90_data_serverless.yml` is enriched-only and passes no parameters, so it
was the weaker template for a parameterised raw load.

The `meta_where_clause` is the load-bearing decision. The SQL metadata adapter
(`lighthouse/adapters/metadata/sql.py:70`) injects the widget verbatim as
`WHERE {source}` against `[meta].[IngestDefinitions]`. That view (line 42)
exposes `connection_name = LOWER(ConnectionName)` - so the value must be lowercase
`'o90'`, matching the meta SQL script's `@ConnectionName='o90'` - and (line 71)
exposes `IncrementalFlag` directly. `connection_name = 'o90' AND IncrementalFlag = 0`
is therefore the stable selector for the 19 full tables, and it is exactly the
predicate the Step-1 SQL script uses to pick the same 19
(`sc.Name='o90' AND so.IncrementalFlag=0 AND so.ExcludeFlag=0`); `ExcludeFlag=0`
is already enforced inside the view, so it is not needed in the clause.

### What worked

The framework gave a clean, verifiable answer for every decision: existence-check
API (grep of `helpers/table.py`), the filter columns (the view DDL), the wiring
shape (master_oe90_dash), and the bundle include (`databricks.yml` includes
`solutions/databricks/workflows/*.yml`, so the new file is picked up). Python AST
parse of the edited notebook passed, and PyYAML parse of the new workflow
confirmed two tasks, the dependency edge, identical `meta_where_clause` on both,
and PAUSED on dev/test/prod.

### What didn't work

The shells fought me. `Bash`/`PowerShell` were denied for git the entire session
(`git config`, `git status`, `git commit` all returned "Permission to use ... has
been denied"), and `echo`-prefixed Bash was denied too. `python` ran fine, which
is how I validated. PyYAML was initially missing
(`ModuleNotFoundError: No module named 'yaml'`); `python -m pip install --quiet
pyyaml` fixed it and the YAML then parsed. Net effect: I could not stage or commit
- that is left for Benny with the exact commands handed back.

### What I learned

Two concrete things. (1) The CWD-vs-target-repo trap is real and looks exactly
like "the work was never done": always pass an explicit `path=` to Glob/Grep when
the target repo differs from CWD, and confirm via `.git/HEAD` + reflog rather than
trusting an empty search. (2) A `run_keys_flow` interaction that matters: in
`IngestDefinitions` (lines 67-70) `run_keys_flow = 0` only when
`WritePattern IN ('stream_append','stream_overwrite') AND IncrementalFlag = 0`.
Once Benny's Step-1 SQL sets these 19 tables to `WritePattern='stream_scd2'`,
their `run_keys_flow` flips to **1**, so the delete notebook's conditional takes
the `/Keys/` branch (`source_keys_path`) - but full loads have no `/Keys/`
snapshot. That is why I keyed the workflow on `IncrementalFlag = 0` (stable) and
not `run_keys_flow = 0` (would match zero rows after the SCD2 script).

### What was tricky

The `run_keys_flow` flip above is the sharp edge, and it lives in code Step 1
shipped that this task was told to leave unchanged ("Bevar resten uændret"). So I
did not rewrite it - I flagged it. As written, the delete pass for the 19 full
tables will try the `/Keys/` path at runtime and fail to find a snapshot. The
faithful fix is a one-line condition change (branch on `IncrementalFlag`/presence
of a keys path rather than `run_keys_flow`), but that is Benny's call, not a
silent builder edit.

### What warrants review

1. **`run_keys_flow` branch (highest priority).** Confirm on a real run whether
   the 19 full tables, now `stream_scd2`, resolve `run_keys_flow = 1` and wrongly
   take the `/Keys/` branch. If so, decide the fix (likely branch on full-load
   detection, e.g. `IncrementalFlag == 0`, to read the full snapshot).
2. **PK anti-join alignment** (carried from Step 1): a wrong key match deletes
   everything; validate the sanitised snapshot PKs equal the raw table PKs.
3. **Compute choice:** I used a classic job cluster (master_oe90_dash precedent).
   If Benny prefers serverless for raw, switch the job block to the
   `environments`/`environment_key` shape from `ingest_o90_data_serverless.yml`.
4. **Manual run mechanics:** verify the job appears after `databricks bundle
   deploy` and runs via `bundle run ingest_o90_raw_full` (or the Workflows UI),
   PAUSED schedule and all.

### Future work

Resolve the `run_keys_flow` branch decision, then a real dev run of the two-task
job to validate delete detection end-to-end (row counts, that only truly-absent
keys get `dw_is_deleted=true`). Then decide whether this Databricks workflow or
ADF ultimately drives the Ø90 raw load in production.

## Step 2: Lead-driven requirements refinement (preceded the build)

**Author:** main

### Prompt Context

**Verbatim prompt:** jeg kunne godt tønke mig at bruge min lead agent nu

**Interpretation:** Engage the outer_heaven:lead agent to refine the loosely-held
idea (a DB2→Databricks type mapping at raw load for the 19 Ø90 full tables) into
concrete requirements before any code is written.

**Inferred intent:** Use the lead/builder team properly — refine and challenge
first, build second — rather than jumping straight to implementation on a design
Benny was still unsure about.

### What I did

Ran several lead-refinement rounds (the lead does not implement). The lead
challenged the original premise and we converged on a clean raw-layer design:
history = SCD2 (`stream_scd2`), raw stays faithful to source, UTC-correction and
datatype conversion are deferred to the enriched rebuild (both are deterministic
and re-derivable from faithful raw, so nothing is lost by waiting), and delete
detection is a separate conditional pass via `write.soft_delete` (full-snapshot
keys when `run_keys_flow=0`, `/Keys/` snapshot when `=1`). Then handed a tight,
verified spec to the builder, which shipped Step 1.

### Why

Benny explicitly wanted the lead team. The refinement mattered: it killed two
half-formed ideas (typing in raw; replicating UTC into raw) by grounding them in
the medallion principle and the fact that both transforms are reversible from a
faithful raw. It also surfaced the real requirement — delete tracking that works
for incremental, where watermark deltas never show deletes — which is why the
conditional `/Keys/` path exists rather than just a full-snapshot diff.

### What worked

The lead's challenges were substantive and changed the design for the better
(faithful raw, deferred transforms). Driving questions one at a time kept Benny's
decisions clean. Handing the builder a spec pre-loaded with verified new-estate
facts (lighthouse, write.py line numbers, IngestDefinitions columns) let it build
without re-deriving from scratch.

### What didn't work

**The lead agent confused the two repos on one round** and it nearly poisoned the
design. It read paths under `dataestatedlbr\.claude\worktrees\agent-…\…` (the OLD
estate, in a git worktree) and reported them as the BUILD repo, concluding
"framework is lakehousebpf, no `detect_deletes`, delete-detection already exists,
~0 code" — directly contradicting its own correct findings from the prior round
(lighthouse, `upsert_type_2(detect_deletes=...)`, `soft_delete()`). I caught it
only by re-verifying against the new estate myself: `grep -nE "from lighthouse|detect_deletes|upsert_type_2" solutions/databricks/01_raw/load_to_raw_general.py`
confirmed lighthouse + `detect_deletes=False` hardcoded, and the delete consumer
does NOT exist in the new estate (it lives only in old `dataestatedlbr`). Had I
relayed the lead's round verbatim, Benny would have been told the work was
already done.

Also: `SendMessage` to continue a spawned agent is not available in this session,
so every lead round was a fresh cold-start re-briefed with accumulated context —
expensive, and part of why the repo drift crept in (the cold agent re-searched
and hit worktree paths).

### What I learned

Worktree directories (`*\.claude\worktrees\*`) under a repo pollute file searches
and are a concrete repo-confusion hazard for sub-agents — especially cold-started
ones that re-derive context. The guardrail "build = new estate, reference = old"
is necessary but not sufficient; agents also need an explicit "ignore worktree
paths; verify files sit at repo root" instruction. And the main agent should not
relay sub-agent conclusions verbatim when it holds ground truth — verify first.

### What was tricky

Holding the repo distinction across many cold-start lead spawns. Each spawn re-read
the codebase and risked drifting into the old estate or its worktrees. The fix was
heavier briefings plus my own re-verification at each suspicious turn.

### What warrants review

Nothing in code beyond Step 1's review points. The process learning (repo
confusion + worktree pollution) is a candidate for an improve-skill pass on the
lead/builder agents or a repo-discipline note.

### Future work

Tighten the lead/builder agent instructions so they ignore `.claude/worktrees/`
paths and verify repo root before reasoning about framework/architecture.

## Step 4: Option 2 - branch the delete pass on IncrementalFlag (the run_keys_flow fix)

**Author:** main

### Prompt Context

**Verbatim prompt:** (Danish, abridged) Fortsæt på branch
`feature/o90-raw-delete-detection`. OPGAVE A: additiv `IncrementalFlag` i
adapteren `lighthouse/adapters/metadata/sql.py` - tilføj `IncrementalFlag,` i
SELECT'en (efter `run_keys_flow,`) og `"IncrementalFlag": row["IncrementalFlag"]`
i den returnerede per-tabel-dict. Rent additivt. OPGAVE B: branch
delete-notebooket `load_to_raw_update_deleted_flags.py` på `IncrementalFlag` fra
`extra_fields` i stedet for `run_keys_flow`: full load (`IncrementalFlag` 0/False)
-> nyeste FULDE snapshot (`source_path`); ellers (incremental) -> `/Keys/`-snapshot
(`source_keys_path`). VIGTIGT: IncrementalFlag er en BIT via sqlserver-connectoren
-> kan være bool, ikke int -> håndtér `in (0, False)` som full. Behold
eksistens-guarden. Må ikke ændre load_to_raw_general.py, prod-workflows, .ps1,
IngestDefinitions-viewet. Ingen UTC/typekonvertering. Ingen push.

**Interpretation:** Resolve the `run_keys_flow` sharp edge that Step 3 flagged, by
the option Benny chose: surface the raw `IncrementalFlag` BIT additively through
the metadata adapter, then branch the delete notebook on it instead of on the
derived `run_keys_flow` CASE int.

**Inferred intent:** After the Step-1 SQL sets the 19 full tables to
`stream_scd2`, their `run_keys_flow` flips to 1 and the delete pass would wrongly
take the `/Keys/` branch (no snapshot there for a full load) and crash in
`get_latest_file_path`. Branching on the stable `IncrementalFlag` keeps full loads
on the full-snapshot path regardless of WritePattern.

### What I did

Verified the build context first: `git rev-parse --abbrev-ref HEAD` ->
`feature/o90-raw-delete-detection`, remote is `segesdk/DLBR-DataEstate2026` (the
new estate). Read the two target files, the `IngestDefinitions` view, and
`metadata.py` to confirm the `extra_fields` mechanism end to end.

Opgave A - `lighthouse/adapters/metadata/sql.py` (two additive edits, nothing
removed): added `IncrementalFlag,` to the SELECT after `run_keys_flow,` and before
`NULL AS json_schema`; added `"IncrementalFlag": row["IncrementalFlag"]` to the
returned per-table dict after `"run_keys_flow": row["run_keys_flow"]`.

Opgave B - `solutions/databricks/01_raw/load_to_raw_update_deleted_flags.py`:
replaced `run_keys_flow = ...extra_fields.get("run_keys_flow")` with
`incremental_flag = ...extra_fields.get("IncrementalFlag")`; replaced the
`if run_keys_flow == 1: /Keys/ else: full` branch with
`if incremental_flag in (0, False): full else: /Keys/`. Updated the markdown
comment block and the inline comments to describe IncrementalFlag (raw BIT,
bool-or-int) instead of run_keys_flow. Left the existence guard
(`spark.catalog.tableExists`) and everything else untouched.

Validated: `python -c "...ast.parse..."` on both files -> "AST OK: both files
parse". Read the diffs back with `git diff` and re-read the notebook region to
confirm the existence guard still appears exactly once.

### Why

The branch is the whole point of the fix. Step 3 had already diagnosed that
`run_keys_flow` (IngestDefinitions lines 67-70) is 0 only for
`stream_append`/`stream_overwrite` + IncrementalFlag=0; once the 19 tables become
`stream_scd2` it is 1 for all of them, so the old `== 1` condition would route
every full table to the `/Keys/` branch. `IncrementalFlag` (view line 71) is the
raw, WritePattern-independent flag, so branching on it is stable across the SCD2
change. Doing it additively in the adapter (rather than reading the view
differently) means `load_to_raw_general.py` and every other consumer keep reading
the same fields with identical behavior.

### What worked

The `extra_fields` plumbing held exactly as the prompt predicted. `metadata.py:183`
calls `SourceObjectMetadata(**value)`; that class (lines 132-148) names only
`primary_key_columns` and `json_schema`, so every other dict key - now including
`IncrementalFlag` - is swept into `**kwargs` and stored as `self.extra_fields`
(line 148). `asdict()` (line 189) then re-nests it, which is precisely how the
notebook already reads `source_path` via `["extra_fields"].get(...)`. So a single
new dict key flows to `extra_fields["IncrementalFlag"]` with zero other changes.
AST parse passed first try.

### What didn't work

No failures. Git is read-only in this sandbox per the prior sessions' pattern, so
I did not attempt to commit - the diffs are handed back for Benny to commit. That
is the stated, expected limitation, not a smoothed-over claim.

### What I learned

The bool/int robustness is real and Python makes it free here: `bool` subclasses
`int`, and `in` compares with `==`, so `0 == False` and `1 == True`. That means
`incremental_flag in (0, False)` matches whether the sqlserver connector hands
back the BIT as int `0` or bool `False` - both branch to the full-load path.
Keeping both literals in the tuple is redundant by Python semantics but makes the
intent explicit and survives a future connector that changes the type. The view
column is NOT NULL (no ISNULL wrap, line 71), so `None` is not expected; if it ever
arrived it falls to the incremental/`/Keys/` branch, which is the safe default
since incremental tables genuinely have a keys snapshot.

### What was tricky

The `git diff` hunk grouping was briefly alarming: it rendered the unchanged
existence guard as part of the same added block as my branch change, which looked
like a duplicated guard. Reading the actual file (lines 114-137) confirmed the
guard appears exactly once and untouched - the diff was just sharing context lines.
Worth re-reading the file rather than trusting the diff's block boundaries.

### What warrants review

1. **Live run is the only real proof.** AST parse and the `extra_fields` reasoning
   are verified statically, but the actual value of `IncrementalFlag` coming off
   the sqlserver connector (int vs bool), the snapshot resolution, and the
   anti-join behavior can only be confirmed on a real dev run against the 19 full
   tables now set to `stream_scd2`. The bool/int handling is built to cover both,
   but observe which type actually arrives.
2. **PK anti-join alignment** (carried from Steps 1 and 3, unchanged by this step):
   a wrong key match deletes everything; still the first thing to validate live.
3. The Step-3 workflow (`ingest_o90_raw_full.yml`) keys on
   `connection_name = 'o90' AND IncrementalFlag = 0`, which now matches the
   notebook's own branch predicate - consistent end to end.

### Future work

A dev run of the two-task job to confirm the 19 full tables now take the
full-snapshot branch (not `/Keys/`) and that delete detection closes only
truly-absent keys. No further code change is anticipated for this fix.
