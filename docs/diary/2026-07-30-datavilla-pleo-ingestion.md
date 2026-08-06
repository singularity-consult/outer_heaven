# Diary: Pleo ingestion source (datavilla)

Add a new ingestion source "Pleo" to the datavilla repo: a company-card / spend
API pulling accounting entries (card transactions with merchant, supplier, amount,
tax, team/employee metadata) into a new `raw.pleo` schema, reusing the existing
extraction chain (API -> date-partitioned landing NDJSON -> Auto Loader -> raw ->
SCD2). Auth is HTTP Basic (API key as username, empty password), NOT Bearer. The
data path is TWO-STAGE: discovery over export-jobs -> items yields the set of
`accountingEntryId`s, then a fan-out `GET /v1/accounting-entries/{id}` fetches the
full entry per id. This is real spend data (amounts, merchants, suppliers, company
name), so leak-discipline is absolute: everything in code/tests/fixtures/comments/
diary is synthetic (amount minors 12345, merchant "ACME", id "AAAA1111", date
1999-12-31; company_id may appear — it is a company UUID, not a secret). Dev
environment only, Singularity "Microsoft Partner Network" subscription (not SEGES).
Commit at the end; do NOT push.

## Step 1: Requirements refinement + pattern verification (lead)

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Forfin krav til en ny ingestion-kilde \"Pleo\" i datavilla.
Du forfiner + udfordrer + forbereder worktree; du implementerer ikke, og du kan
ikke selv spawne builder (main gør det på din rapport). Auth + API-form + data-vej
er ALLEREDE verificeret live af drone — byg ikke research om, verificér mod repoets
faktiske mønstre." (Full brief covering: base https://external.pleo.io; HTTP Basic
auth with the key as username and empty password, key in vault `pleo-api-key`;
company_id 5f4765f4-... as a non-secret config value required on every call; the
two-stage data path — export-jobs discovery -> items -> per-id
accounting-entries GET, because accounting-entries:search is RBAC-locked; key `id`,
watermark `updatedAt`, history scd2; rate limit 600 req/min, ~2000 entries, ~4 min
full pull; four design decisions to resolve — two-stage extractor structure,
incremental vs full, company_id placement, the exported-only limitation; strict
data-leak discipline. Worktree `.claude/worktrees/pleo-ingestion` on
`feature/pleo-ingestion` from master.)

**Interpretation:** Build Pleo as a fourth extraction adapter in the
Kraken/CorPay/Enable Banking shape, but with (a) a fourth auth model — HTTP Basic
with an empty password, (b) a two-stage fetch — a discovery pass over paginated
export-jobs and their items to collect the unique `accountingEntryId` set, then a
per-id fan-out to fetch the full entry, and (c) a single source/schema/job (`pleo`)
landing the full entries as NDJSON and merging SCD2 on `id`. Verify the repo's
actual mechanics support this before handing to a builder; do not implement.

**Inferred intent:** A repeatable, cost-minimal, leak-safe way to land Benny's real
Pleo spend ledger into datavilla's bronze layer, correct across full-history pulls,
versioning genuine changes to an entry (status/review/export transitions) via SCD2
on `id`, while making explicit — not silently hiding — that only entries already
exported to e-conomic are visible (the direct search endpoint is RBAC-locked).

### What I did

Read the reusable patterns end to end from the master checkout: the CorPay adapter
(`src/datavilla/extract/corpayone.py`, the nearest forebear for a paged REST
extraction with hard-fail on 4xx and within-run id dedup), the Enable Banking
adapter (`src/datavilla/extract/enablebanking.py`, the forebear for a two-level
fetch loop, per-record provenance stamping, and a decoupled config field), the
extractor contract (`src/datavilla/extract/base.py` — `SourceExtractor`,
`ExtractResult`, `register_extractor`), the config model (`src/datavilla/config.py`
— `EXTRACTION_ADAPTERS`, `PIVOT_ADAPTERS`, `EndpointConfig.require_key_field`,
`session_key`, `SourceDefinition.job_group`, `LandingConfig` path helpers), the SCD2
merge engine (`src/datavilla/write/scd2.py`), the raw writer
(`src/datavilla/write/raw.py`), the job generator (`src/scripts/generate_jobs.py`),
the secret helper (`src/datavilla/secrets.py`), the two forebear source ymls and the
corpayone job yml, the CorPay test (`src/tests/test_corpayone.py`) for the offline
test conventions, and the Unity Catalog module
(`infra/modules/unity_catalog/{variables.tf,main.tf}`). Also read the drone's
reference probe in scratchpad (`pleo_probe.py`) to pin the exact API form (Basic
auth header assembly, endpoint paths, response shapes) — it prints only field names
and counts, never values.

Confirmed the master checkout is clean at `abf157f` (CorPay + Enable Banking merged;
no pre-existing feature worktrees). Prepared the feature branch `feature/pleo-ingestion`
from master and this diary — see "What was tricky" for why the feature ended up in
the harness-isolated lead worktree rather than a hand-made `.claude/worktrees/
pleo-ingestion` path.

### Why

The brief states auth, API shape and data path are already live-verified by the
drone, so the leverage here is not re-research but confirming the repo's four
existing seams accept a fourth extraction dialect without reshaping them — and
pinning down the two genuinely new things (a two-stage discovery+fanout fetch, and a
"full entry as one NDJSON line" landing) against how CorPay/Enable Banking already
do paging, dedup, provenance stamping and SCD2. Getting the four design decisions
resolved with recommendations before a builder starts is what keeps the build a
config + one-module change rather than a framework change.

### What worked

The pattern fits Pleo cleanly, seam by seam — verified in the actual code, not
assumed:

- **Adapter kind.** Pleo is a straight fourth member of `EXTRACTION_ADAPTERS`
  (`config.py`). It carries `keyvault` + `endpoint` + `landing` (not
  `connection`/`source`), runs API -> landing NDJSON -> Auto Loader -> raw, and
  combines `is_extraction` with `history: scd2` exactly as CorPay/Enable Banking do
  — `autoload._read_plan` selects the SCD2 writer off `history` regardless of source
  kind, so no writer change is needed.
- **No pivot.** Pleo returns list/object shapes with the id already a field (`id`),
  not an id-keyed map, so it stays OUT of `PIVOT_ADAPTERS`. Because
  `EndpointConfig.from_dict` is called with `require_key_field=<adapter in
  PIVOT_ADAPTERS>` (config.py:732), a non-pivoting adapter omits `endpoint.key_field`
  with no guardrail weakening — same as CorPay/Enable Banking.
- **SCD2 on `id`.** `history: scd2` + `keys: [id]` is validated at config load
  (config.py:706 requires a non-empty `keys` for scd2) and `write_scd2` versions on
  the content hash of all non-audit columns, so a re-pulled unchanged entry hashes
  identically and no-ops, while a genuine change (status / reviewStatus /
  exportStatus / `updatedAt`) is versioned. `updatedAt` sits INSIDE the hashed
  content, so it need not be a second key — a change to it alone still yields a new
  version. The single key `id` is safe (unlike Enable Banking's composite) because an
  accounting-entry id is globally unique within the one company, not per-account.
- **Secrets.** `secrets.get_secret(vault, name, service_credential)` fetches the one
  `pleo-api-key` via the same UC service-credential -> Key Vault path CorPay/Enable
  Banking already use; the connector MI already holds `Key Vault Secrets User` on the
  whole vault, so no new IaC grant.
- **Raw schema is free.** `ensure_raw_table` runs `CREATE SCHEMA IF NOT EXISTS`
  (raw.py:122) at runtime, so the `raw.pleo` schema is auto-created. The ONLY
  Terraform change is one line adding `pleo` to `landing_schemas`
  (unity_catalog/variables.tf) so the landing volume
  `/Volumes/datavilla_<env>_landing/pleo/incoming/` exists — a for_each-over-a-set
  add, no `moved` blocks touched.
- **Job generation is automatic.** `generate_jobs.py` groups by `job_group` (=
  `landing.schema` for landing sources), so a single `pleo` source produces one
  `ingest_pleo` job with one for_each iterating its one endpoint — one cluster, one
  spinup. The builder regenerates with `python scripts/generate_jobs.py`; it must not
  hand-write the job yml.

### What didn't work

No verification check failed — every pattern check resolved in the repo's favour.
The friction was entirely in worktree mechanics (next section). The `git worktree
add` for the requested path succeeded ("Preparing worktree (new branch
'feature/pleo-ingestion')" / "HEAD is now at abf157f"), but I could not write into
that path afterwards, so I unwound it.

### What I learned

The two genuinely new things versus the three forebears, and how each maps onto an
existing mechanism:

- **Two-stage fetch (discovery -> fanout), not one paged loop.** CorPay pages one
  endpoint by offset; Enable Banking loops accounts x cursor pages. Pleo is
  different again: a DISCOVERY pass pages `GET /v2/export-jobs?company_id=..` and,
  per job with `numberOfItems > 0`, pages `GET /v2/export-jobs/{jobId}/items` to
  collect the UNIQUE set of `accountingEntryId`s; then a FANOUT does one `GET
  /v1/accounting-entries/{id}?company_id=..` per unique id and lands the FULL entry
  (`{data:{...}}`). The N+1 fanout is the cost (~2000 entries ~= 4 min under the 600
  req/min limit); acceptable and the same "full pull every run" philosophy as the
  forebears.
- **Within-run dedup is on the DISCOVERY id set, not on a landed page.** The same
  `accountingEntryId` can appear in more than one export-job, so the unique-id set
  is de-duplicated during discovery (a plain `set`), which also means the fanout GETs
  each entry once and each entry lands as exactly one NDJSON line — so a duplicate
  key can never reach and abort the SCD2 merge. This is the CorPay `seen`-set idea,
  moved one stage earlier (to the id list) because dedup here is about not
  double-fetching, not just not double-landing.
- **Auth Basic-with-empty-password.** `Authorization: Basic base64("<key>:")` — the
  trailing colon (empty password) is load-bearing; it is NOT Bearer (a Bearer here
  expects a JWT and would 401). This is a fourth distinct auth model and, like the
  others, is hardcoded contract in the module with only the key coming from
  config/vault.
- **company_id is a required query param on every call and is NOT a secret** — it is
  a company UUID (`5f4765f4-40b8-4995-a6f7-b97854d728fa`). It has no forebear slot:
  CorPay resolves TeamId from a live lookup, Enable Banking reads account_uids from a
  JSON secret. Pleo's company_id is a stable, non-secret, per-source scalar — see the
  decision below on where it lives.

### What was tricky

- **The worktree reality vs the requested path.** The harness launched this lead
  agent already isolated inside its own worktree
  (`.claude/worktrees/agent-ad43a86c6819f7c2b`), and every write/bash/PowerShell tool
  is hard-pinned to it: attempts to write the diary or run git inside a hand-made
  `.claude/worktrees/pleo-ingestion` were refused ("Edit the worktree copy of this
  file instead of the shared-checkout path" / "commands ... must run inside its
  worktree"). `EnterWorktree`/`ExitWorktree` could not move that pin (ExitWorktree is
  blocked for a cwd-overridden subagent; EnterWorktree moved only cwd, wedging the
  shells until I re-entered the launch worktree). So the feature necessarily lives in
  the lead's own isolated worktree, which is exactly the harness design ("builders
  you spawn share this worktree"). I removed the redundant hand-made worktree
  (`git worktree remove` + `git branch -D`) and renamed the lead worktree's branch to
  `feature/pleo-ingestion` (`git branch -m`). Net end state matches intent — branch
  `feature/pleo-ingestion` from master `abf157f` — but the on-disk path is the lead
  worktree, not `.claude/worktrees/pleo-ingestion`. The builder must be pointed at
  this worktree.
- **Where company_id belongs.** It does not fit `keyvault.secrets` (not a secret) and
  there is no generic "endpoint query params" slot in `EndpointConfig`. The cleanest
  fits without reshaping config are (a) reuse the existing nullable `session_key`
  field, or (b) add a small explicit `company_id` field to `EndpointConfig` /
  `SourceDefinition`. Reusing `session_key` overloads a field whose name means
  something else (Enable Banking's JSON session selector) — a readability trap. See
  the recommendation below.
- **The exported-only limitation is a data-completeness caveat, not a bug.** Because
  `accounting-entries:search` is RBAC-locked, the only reachable entries are those
  that appear in an export-job — i.e. entries already exported to e-conomic. Entries
  not yet exported are INVISIBLE to this pipeline. This must be stated explicitly in
  the config comment and the diary so a future reader does not mistake a partial
  ledger for the whole one, and so SCD2's no-delete-detection stance stays correct
  (an entry absent from a run may simply be not-yet-exported, never "deleted").
- **Provenance stamping across stages.** The full entry comes from
  `/v1/accounting-entries/{id}`, but `exportedAt` / `externalId` (the e-conomic ref)
  live on the export-ITEM, not the entry. Stamping those onto the landed entry (as
  Enable Banking stamps `account_uid`) preserves the discovery provenance. Optional
  for v1; it adds a little coupling between the two stages. Flagged as a decision,
  leaning yes-but-minimal.

### What warrants review

For the builder and for me reviewing the builder's diff:

- **The four design decisions below** — confirm the recommendations hold once the
  builder sees the concrete extractor shape.
- **Leak discipline in the diff.** I (lead) must scan the builder's diff for ANY real
  amount, merchant, supplier, family/company name, or real entry id BEFORE commit.
  Only synthetic values (minors 12345, "ACME", "AAAA1111", 1999-12-31) and the
  non-secret company_id are permitted. Any afsøgning/probe must print field names +
  counts only, never values.
- **Within-run id dedup** must be exercised by a test that puts the same
  `accountingEntryId` in two export-jobs and asserts one landed entry / one entry GET.
- **Hard-fail on 4xx** (401 dead key, 403 RBAC on the search path if ever called,
  other non-2xx) must raise a typed error and never land zero rows silently — the
  CorPay/Enable Banking stance. Distinguish the fanout 404 (an entry id from
  discovery that no longer resolves) as its own decision: skip-with-warning vs
  hard-fail (lean skip-with-count, since a stale export-item id is a benign race).
- **`generate_jobs.py --check`** must pass (no drift) and the `pleo` line must be in
  `landing_schemas`.

### Future work

- Incremental pull via export-jobs `createdAt`/`lastUpdatedAt` since the last run, if
  the ~4 min full pull ever becomes a cost concern (recommended AGAINST for v1 below).
- If Pleo ever grants RBAC on `accounting-entries:search`, the discovery stage could
  be replaced by a direct watermarked search, removing the N+1 fanout and the
  exported-only limitation — a larger rework, explicitly out of scope now.
- Downstream (Blok 2+) shaping of the entry into enriched/curated is not part of this
  ingestion source.

## Step 2: Implementation + live proof (builder)

**Author:** builder (async sub-agent)

### Prompt Context

**Verbatim prompt:** "Byg ingestion-kilden \"Pleo\" i datavilla efter lead's forfinede
spec. Auth + API + data-vej er verificeret live; du udfører, re-researcher ikke."
(Full brief: config.py adds `pleo` to EXTRACTION_ADAPTERS + a new nullable `company_id`
field; extract/pleo.py with a `PleoClient` (Basic auth, discovery over export-jobs+items
with pagination, fanout get-by-id, hard-fail 4xx except 404-on-fanout=skip-with-count,
shape-error on unexpected 2xx) and a `@register_extractor("pleo")` `PleoExtractor` that
dedups accountingEntryId in a set and lands batched ~100-entry NDJSON files; a
side-effect import; config/sources/pleo.yml; the `pleo` landing schema in Terraform;
tests all-synthetic; regenerate jobs; deploy dev + live-prove rows==distinct id and a
SCD2 no-op re-run; leak discipline absolute. Commit, do not push.)

**Interpretation:** Implement Pleo as the fourth extraction adapter exactly to the
lead's resolved decisions (explicit `company_id` field, two-stage discovery+fanout,
404-fanout skip-with-count, batched NDJSON), verify against the repo's real seams, and
prove it end to end on the live dev workspace — not re-derive the API.

**Inferred intent:** Land Benny's real Pleo spend ledger into `raw.pleo.accounting_entries`
correctly and leak-safely, with the SCD2-on-`id` no-delete stance and the exported-only
caveat made explicit, and a live proof that the within-run dedup and the merge no-op
both actually hold on the real ~1.5k-entry ledger.

### What I did

Built the six pieces and proved them. In `src/datavilla/config.py`: added `pleo` to
`EXTRACTION_ADAPTERS` (with a fourth-dialect comment) and a new nullable `company_id`
dataclass field parsed in `from_dict` — the explicit-field decision, kept distinct from
`session_key`. New `src/datavilla/extract/pleo.py`: a `PleoClient` assembling the Basic
header as `base64("<key>:")`, a generic offset/limit `_paginate` that stops on an empty
page (tolerating a server-clamped limit) with a loud `MAX_PAGES` cap, `export_jobs`/
`export_job_items`/`accounting_entry` (the last returning `None` on 404), a request
pacer (`min_interval` default 0.11s) to stay under 600/min, and a `PleoExtractor` that
discovers the unique `accountingEntryId` set, fans out, stamps export-item provenance
(`exportedAt`/`externalId`) without clobbering, and lands batched ~100-entry NDJSON.
Registered it in `extract/__init__.py`; wrote `config/sources/pleo.yml` (with the
exported-only caveat comment) and `tests/test_pleo.py` (32 all-synthetic cases); updated
`test_config.py` and `test_generate_jobs.py`; added `pleo` to `landing_schemas` in
`infra/modules/unity_catalog/variables.tf`; regenerated jobs (`ingest_pleo.job.yml`).

Full suite: `240 passed`. Terraform `fmt`/`validate` clean; dev plan was exactly `2 to
add (schema pleo + volume incoming), 0 to change, 0 to destroy` and applied cleanly.
Deployed the dev bundle and ran `ingest_pleo` twice (non-blocking `jobs run-now`, short
repeated `jobs get-run` polls — never a long blocking sleep).

### Why

The whole leverage was confirming the four existing seams accept a fourth dialect
without reshaping them (they do) and proving the two genuinely new behaviours — the
two-stage discovery+fanout and the within-run id dedup — hold on the real ledger. The
live proof is the verification the offline tests cannot give (real pagination, real
dedup, real merge no-op), which is exactly the CorPay/Enable Banking "unverified
offline, confirmed against the live API" stance.

### What worked

Every check passed on the real workspace. Run 1 (run_id `466973977612322`, SUCCESS):
`raw.pleo.accounting_entries` landed **1549 rows, 1549 distinct `id`, 1549 current, 0
duplicate current keys** — rows == distinct id, so the discovery dedup holds on the real
ledger. Run-log: extract `rows_out=1549` in 180s (the 0.11s pacing over ~1549 fanout +
discovery calls, right on the ~3-4 min estimate), autoload `rows_inserted=1549`,
`rows_updated=0`. Run 2 (run_id `601270432787860`, SUCCESS) is the SCD2 no-op proof:
the table stayed at **1549 rows** and the run-log shows extract re-fetched 1549 but
autoload `rows_out=0, rows_inserted=0, rows_updated=0` — every re-delivered entry hashed
identically and the merge absorbed it as a pure no-op. Terraform plan was the predicted
+2/0/0 additive change, no `moved` blocks touched.

### What didn't work

Two test-fixture bugs on the first pytest run, both mine, both in `test_pleo.py` (not the
module): the `FakeTransport` raised `IndexError: list index out of range` because a
single non-empty page with no `pagination.total` made the offset pager request a second
(absent) page — fixed by having the fake return an empty terminating page past the
supplied pages (which also models "no more data" honestly); and the `entries` fixtures
passed raw `{data:...}` bodies where the transport expects `(status, body)` tuples,
giving `ValueError: too many values to unpack` inside `_get` — fixed with an `_entry_resp`
helper wrapping `(200, body)`. After both fixes: `90 passed` on the affected modules,
`240 passed` overall. I also left one nonsense leftover assertion
(`assert sorted(... for _ in [0]) is not None`) which I caught and replaced in
self-review with a real `len(transport.entry_calls()) == 2` check.

The one thing I could NOT capture: the exact **skipped-404-fanout count**. The extractor
prints it to driver stdout (`pleo: skipped N stale export-item id(s)...`), but
`databricks jobs get-run-output` returns only `{metadata}` for a `python_wheel_task` and
these ephemeral job clusters have no queryable log delivery, so the integer is not
recoverable post-hoc. What IS known: `records_written`/landed = 1549 already EXCLUDES any
skips (a skip increments a separate counter and is never landed), and the skip path is
unit-tested (`test_extract_skips_404_fanout_with_count`). Whether run 1 skipped 0 or N is
unobservable from here because discovery's distinct-id count is not surfaced separately.

### What I learned

`offset` was a genuine unknown — only `limit` was confirmed (the probe used `&limit=5`).
Rather than guess-and-hope, I made the pager correct-by-termination: it advances `offset`
by the REAL returned page length and stops on an empty page, so a server-clamped `limit`
is tolerated, and a `MAX_PAGES` cap turns an ignored-offset cursor API into a loud
`PleoApiError` instead of a hang — protecting the live cluster run. The live 1549==distinct
result confirms offset paging is honoured. Second: the 600/min limit and ~2000 fanout GETs
sit right on top of each other, so pacing is not optional — without the 0.11s min-interval
a fast loop would 429, and 429 is a 4xx that hard-fails; the 180s extract duration is the
pacing working as designed. Third: the real entry count is 1549, not the briefed ~2000 —
the estimate was approximate, and the exported-only limitation (only e-conomic-exported
entries are visible) plausibly explains the gap.

### What was tricky

The skip-count observability gap above is the honest sharp edge. The pagination
param-name uncertainty was the design risk, handled by making termination independent of
the guess. Poll discipline mattered: a previous builder died on a watchdog from a long
blocking sleep, so every wait here was a short (<60s) sleep followed by one fast
`jobs get-run` call, never a single long block. Cluster spinup on the minimum-cost
single-node job dominates wall-clock (~8-10 min/run, mostly spinup; the pull itself is
~3 min), so both runs took a while with nothing to do but poll.

### What warrants review

- **Leak discipline in the diff** (lead's gate): everything in code/tests/fixtures/
  comments is synthetic (minors 12345, merchant "ACME", id "AAAA1111", date 1999-12-31,
  externalId "EXT-0001"); the only real value is `company_id` (a non-secret company UUID,
  explicitly permitted). No landing filename carries a merchant/amount (they use run
  timestamp + batch ordinal). The 404-skip log prints a COUNT only.
- **The `offset` pagination assumption** — confirmed by the live 1549==distinct result,
  but it is the one thing that was inferred, not briefed; worth a glance.
- **The skip-count gap** — if the count must be reportable, surface it via the run-log or
  `ExtractResult` rather than stdout (see Future work); today it is stdout-only.
- **`_job_has_items` is deliberately lenient** (fetches items when `numberOfItems` is
  absent/unparseable) to avoid silently dropping a job's items on a field-name mismatch —
  correctness over the empty-job optimisation.

### What I learned warrants a second look next time

The batched-NDJSON writer and the SCD2 merge no-op both behaved exactly as the forebears',
so no writer change was needed — confirmed live by `rows_updated=0` on re-run.

### Future work

- Surface the skipped-404 count into the run-log (e.g. a `rows_skipped` column or a
  `notes` field) or onto `ExtractResult`, so a benign-race count is observable without
  driver stdout — the one DoD item that is currently stdout-only.
- Everything the lead listed in Step 1 (incremental pull; a direct watermarked search if
  RBAC on `accounting-entries:search` is ever granted; Blok 2+ curated shaping) still
  stands and is out of scope here.
