# Diary: CorPay One ingestion source (datavilla)

Add a new ingestion source "CorPay One" to the datavilla repo: an OAuth2
refresh-token REST extraction that pulls expense bills into `raw.corpayone.expenses`
as SCD2-versioned rows, reusing the existing Kraken extraction chain
(API -> date-partitioned landing NDJSON -> Auto Loader -> raw) and the e-conomic
SCD2 merge engine (key + content hash, no delete detection). Dev environment only,
Singularity "Microsoft Partner Network" subscription (not SEGES).

## Step 1: Requirements refinement + pattern verification (lead)

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Byg en ny ingestion-kilde \"CorPay One\" i datavilla-repoet. Du
forfiner krav, udfordrer huller, og driver builderen; du implementerer ikke selv.
Al auth og API-form er ALLEREDE verificeret live af main ... " (full brief covering:
OAuth2 refresh_token flow against identity.corpayone.com; teamId prefetch from
GET /external/v1/teams; expenses via GET /external/v2/expenses?TeamId&Count(10-100)/Offset
paginated on `total`; only expenses has data — creditaccounts/transactions/payments
are empty and must NOT be built; SCD2 on bill id, no delete detection; secrets
corpayone-refresh-token/-client-id/-client-secret in kv-datavilla-dev; hard-fail on
400/401; strict data-leak discipline — no real amounts/ids/vendors/dates in
code/tests/diary/comments). Coordinator decision mid-step: teams is a lookup only
(option A), no `corpayone.teams` raw table.

**Interpretation:** Build CorPay as an extraction adapter in exactly the Kraken shape
but with an OAuth refresh-token auth model and a list-shaped (not id-keyed-map) API
response, writing SCD2 like e-conomic. Verify the repo's actual patterns before
handing to a builder; do not implement.

**Inferred intent:** A repeatable, cost-minimal, leak-safe way to land Benny's real
CorPay expense ledger into datavilla's bronze layer, dedup-safe across full pulls,
that fails loudly if the refresh token dies (so Benny knows to re-bootstrap).

### What I did

Read the reusable patterns end to end: `src/config/sources/{kraken,economic,koinly}.yml`,
`src/datavilla/config.py`, `src/datavilla/extract/{base.py,kraken.py,runner.py}`,
`src/datavilla/extract_load.py`, `src/datavilla/autoload.py`,
`src/datavilla/write/{raw.py,scd2.py,autoloader.py}`, `src/datavilla/secrets.py`,
`src/scripts/generate_jobs.py`, and the infra Unity Catalog module
(`infra/modules/unity_catalog/{variables.tf,grants.tf}`, `infra/keyvault_access.tf`,
`infra/dev.tfvars`). Confirmed the git identity in the worktree is
`singularity-consult <benny@singularityconsult.dk>` and the extract-load entry point
is generic.

Refined the requirements, laid out the one genuinely-open scope fork (land teams or
not) with trade-offs, and got decision A (lookup only). Recovered from an
environment failure (see What didn't work) by creating a fresh shared worktree.

### Why

The brief states auth and API shape are already live-verified, so the value of this
step is confirming the repo's mechanics actually support the required combination and
pinning down the few real decisions — not re-researching the API.

### What worked

The pattern matches cleanly and CorPay inherits most of the machinery for free:

- Extraction adapters register via `@register_extractor(name)` + membership in
  `EXTRACTION_ADAPTERS` (config.py). The job shape (`EXTRACTION_JOB_TEMPLATE` in
  generate_jobs.py) is fully generic: one job per `landing.schema`, one shared
  single-node cluster bound to the cluster policy, `concurrency: 1`, run_as=SP,
  entry point `datavilla-extract-load`. CorPay gets `ingest_corpayone` automatically.
- SCD2 (`write/scd2.py`) is generic on key + content hash with no delete detection —
  exactly the e-conomic behaviour — selected purely by `history: scd2` + `keys:` in
  config, wired in `autoload._read_plan`.
- Secrets reuse: `secrets.get_secret` mints a vault.azure.net token via the SAME UC
  service credential (`datavilla_dev_sql_cred`) Kraken uses. `keyvault_access.tf`
  grants the connector MI `Key Vault Secrets User` on the WHOLE vault ("every future
  API key"), so `corpayone-*` needs no new infra.
- Raw schema is auto-created by the framework (`ensure_raw_table` = CREATE SCHEMA IF
  NOT EXISTS; the SP holds CREATE_SCHEMA/CREATE_TABLE/MODIFY on raw). So the ONLY
  infra change is adding `corpayone` to the `landing_schemas` default set in
  `infra/modules/unity_catalog/variables.tf` (creates landing schema + `incoming`
  volume; SP volume grants already cascade).

### What didn't work

The lead's isolated worktree `agent-a184486610f29fa52` vanished mid-session. After
the initial reads succeeded from it, later commands failed:

```
cd: C:/claudes_folder/repos/datavilla/.claude/worktrees/agent-a184486610f29fa52: No such file or directory
```

and `git worktree list` in the datavilla repo showed only `master` — the agent
worktree was gone from disk and from git's registry. `EnterWorktree` refused to
create a replacement from a cwd-pinned subagent:

```
EnterWorktree cannot create a worktree from a subagent with a cwd override ... spawn an Agent with `cwd` set to it.
```

Only reads had happened, so no work was lost. Recovered by creating a fresh shared
worktree from the datavilla repo:
`git worktree add .claude/worktrees/corpayone-ingestion -b feature/corpayone-ingestion master`
and will spawn the builder with its `cwd` pinned there.

### What I learned

CorPay is the FIRST source in the repo to combine `is_extraction` with
`history: scd2`. Kraken is extraction+append; e-conomic is scd2 but file-drop. The
combination is supported by construction (`_read_plan` selects the writer off
`history` regardless of source kind), but it has never been exercised — the builder
must add a test for it.

CorPay's response is a plain LIST (`{total, offset, count, data:{bills:[...]}}`), not
an id-keyed map, so Kraken's `normalize_result` pivot does NOT apply — CorPay lands
each bill as one NDJSON line directly. And it uses two hosts (identity.corpayone.com
for the token, api.corpayone.com for data) and an OAuth refresh flow rather than
Kraken's API-key + HMAC nonce, so it needs its own extractor module, not a config of
the Kraken one.

### What was tricky

Two design tensions handed to the builder as constraints, not left implicit:

1. `SourceDefinition.from_dict` forces `EndpointConfig` for extraction adapters, and
   `EndpointConfig.key_field` is REQUIRED (it names the pivot column for Kraken's
   id-keyed maps). CorPay does not pivot, so a fake `key_field` would be a config lie
   the repo explicitly warns against. The builder must resolve this honestly (e.g.
   relax `key_field` to optional for non-pivoting endpoints and/or add CorPay-specific
   endpoint fields) WITHOUT weakening Kraken's guardrail or renaming existing jobs.
2. Pagination-shift duplicate risk: a full Count/Offset pull can see the same bill id
   twice if a bill is inserted/removed between page fetches, and with `dedupe_order=None`
   on the extraction+SCD2 path a duplicate key in one Auto Loader batch ABORTS the
   Delta merge. The extractor must dedup bill `id` within a single run (bill id is the
   PK, so a same-run duplicate can only be the pagination artifact — dedup is correct,
   not lossy).

### What warrants review

Lead will review the builder's diff for real-data leakage BEFORE any commit (the
brief flags two prior leak incidents on this repo; >700 real bills with real
amounts/vendors here). The builder's green report is NOT the last check. Also verify:
the honest resolution of the `key_field` tension; the hard-fail on 400/401 from token
or API (no silent zero-load); and the live dev proof — `raw.corpayone.expenses` row
count == API `total`, then a second run is an SCD2 no-op (row count unchanged).

### What I learned / Future work

Option B (landing `corpayone.teams` as reference data) is a trivial later add if Benny
wants team name/VAT/country in curated. Deferred by decision A. If CorPay's server
ever begins rotating the refresh token (the `refresh_token` field in the token
response differing from the input), that must be logged and handled — but current
observed behaviour is no rotation, so the adapter must NOT write a new refresh token
back to the vault.

## Step 2: Verify rescued work, prove SCD2 no-op, leak-review, commit (builder)

**Author:** builder (a184486610f29fa52 worktree)

### Prompt Context

**Verbatim prompt:** "Færdiggør CorPay One-kilden i datavilla. En tidligere builder
byggede den FÆRDIG men DØDE (stall-watchdog) under verifikation af run 2. Arbejdet er
reddet og ligger UNCOMMITTED i worktreen — du overtager det, du bygger IKKE om fra
bunden. ... FØRSTE skridt: læs disse filer + diaryen ... Run 1 var GRØNT ... Det der
mangler er: bekræft SCD2 no-op (dedup), kør tests, læk-review, commit. ... undgå at dø
som forgængeren (watchdog): pol med KORTE, GENTAGNE separate bash-kald ... SCD2 no-op:
count før → gen-kør → count efter, uændret = bevist. ... data-læk-review FØR commit ...
Commit i worktreen, korrekt identitet, IKKE pushet."

**Interpretation:** Do not rebuild. Read and verify the predecessor's uncommitted
extractor + config + job + infra + tests, run the suite, prove the SCD2 dedup is a
no-op on a second full pull by comparing the raw row count before and after a fresh
run, scan every committed file (diary included) for real accounting data, then commit
in the worktree under the Singularity identity without pushing.

**Inferred intent:** Land the predecessor's finished-but-unverified CorPay source as a
trustworthy, leak-clean commit, with the one live proof it never got to make (the
re-run no-op), and without repeating the blocking-poll mistake that killed it.

### What I did

Read the whole rescued diff first: `extract/corpayone.py`, `config/sources/corpayone.yml`,
`resources/ingest_corpayone.job.yml`, `tests/test_corpayone.py`, and the config/infra/
test edits (`config.py`, `extract/__init__.py`, `unity_catalog/variables.tf`,
`test_config.py`, `test_generate_jobs.py`), plus `write/scd2.py` to pin down what
"no-op" means mechanically.

Ran the suite from `src/`: the three CorPay-touching files first (68 passed), then the
whole suite (`python -m pytest -q` → 177 passed).

Checked infra with `terraform plan -var-file=dev.tfvars -detailed-exitcode` (env:
`DATABRICKS_AUTH_TYPE=azure-cli`, host adb-7405615279684706, `DATABRICKS_TF_EXEC_PATH`
→ winget terraform.exe, `DATABRICKS_TF_VERSION=1.14.6`). `terraform state list` confirms
`module.unity_catalog.databricks_schema.landing["corpayone"]` and
`...databricks_volume.landing["corpayone"]` are already applied.

Proved the no-op via the Statement Execution API on the serverless warehouse
(`03b065855ce85160`, az token for resource 2ff814a6-…): counted `raw.corpayone.expenses`
(718 rows / 718 distinct id), fired `ingest_corpayone` (job 384294713274379) non-blocking
with `jobs/run-now` (run_id 668794643796244), polled with short repeated `runs/get` calls
until TERMINATED/SUCCESS, then re-counted (718 / 718 / 718 current). Independently
confirmed the run did a real full pull, not a hollow zero-load, by listing the landing
volume: a fresh 8-file page set stamped `20260724T092621…Z` with byte sizes identical to
the two prior full pulls.

### Why

The predecessor's green report is not proof; the brief flags two prior leak incidents and
one death mid-verification. The value of this step is the checks the predecessor never
landed: the suite actually running, the count actually unchanged after a real re-pull, and
every file actually scanned before the commit exists.

### What worked

Non-blocking `jobs/run-now` + short repeated `runs/get` polls kept continuous tool
progress and never came near the 600s stall watchdog — the run also happened to finish on
the second poll (warm cluster). The row-count no-op is clean and unambiguous: 718 → 718,
with 718 current versions == 718 distinct keys, i.e. exactly one current version per bill
and zero new versions from the re-pull. The landing-file listing is the independent
witness that the pull was real.

### What didn't work

`terraform plan` did NOT come back as the brief's expected "+2 add, 0 destroy". It showed
`1 to add, 7 to change, 1 to destroy`. On inspection the "1 add" is a `databricks_grant.
sql_credential_access` REPLACE and the 7 changes are `databricks_grants.layers[...]` +
`databricks_permissions` churn hitting ALL SIX catalog layers (base/curated/enriched/
integration/landing/raw) equally — a principal→null grant-block rewrite. The CorPay change
only touches the landing schema, so it cannot be the cause; the schema+volume are already
in state and absent from the plan. This is pre-existing global grant/provider drift,
unrelated to CorPay, and applying it is out of scope for this task — left for Benny.

`runs/get-output` on the for_each parent returns only `metadata` (no per-iteration logs),
so I confirmed the pull volume from the landing files instead of the run stdout.

### What I learned

The predecessor's run 2 actually DID land — the 2026-07-23 partition holds two full page
sets (18:41 and 18:54). It died proving the count, not producing it. My run is a clean
third full pull that closes that gap independently, so chasing the old run 2 was
unnecessary (as the brief anticipated).

### What was tricky

Distinguishing "my change's plan" from "ambient drift". The `-detailed-exitcode` 2 and the
destroy line looked alarming until `terraform state list` + the fact that the grant churn
is uniform across all six layers showed it is global, not CorPay's. The honest call was to
NOT apply it rather than fold unrelated grant replacement into a CorPay commit.

### What warrants review

The uncommitted infra grant drift (1 replace + 7 changes across all catalog layers) is
real and pending — it should be planned and applied deliberately by Benny, separate from
this feature. Nothing in the CorPay diff depends on it. Everything committed here is the
predecessor's code plus this diary step; the code was read but not modified.

### Future work

Apply (or explicitly dismiss) the ambient UC grant drift in dev under Benny's approval.
The CorPay job currently has no schedule wired; if it should run on a cadence, add the
trigger the same way the other ingest jobs get theirs.
