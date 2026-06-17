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
