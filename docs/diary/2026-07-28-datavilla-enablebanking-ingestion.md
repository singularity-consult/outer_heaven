# Diary: Enable Banking ingestion source (datavilla)

Add a new ingestion source "Enable Banking" to the datavilla repo: a PSD2 account
aggregation API pulling bank transactions for THREE bank sources — Sparekassen
Kronjylland business, Kronjylland personal, and Revolut personal — into three
separate `raw.*` schemas, reusing the existing extraction chain (API ->
date-partitioned landing NDJSON -> Auto Loader -> raw). Auth is a self-signed RS256
JWT built on-demand each run (no token endpoint, no refresh). This is the most
sensitive source in the repo to date (real bank transactions, IBANs, amounts,
names), so leak-discipline is absolute: everything in code/tests/fixtures/comments/
diary is synthetic. Dev environment only, Singularity "Microsoft Partner Network"
subscription (not SEGES). Commit at the end; do NOT push.

## Step 1: Requirements refinement + pattern verification (lead)

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Forfin krav til en ny ingestion-kilde \"Enable Banking\" i
datavilla (tre bank-kilder). Du forfiner + udfordrer + forbereder worktree; du
implementerer ikke, og du kan ikke selv spawne builder (main gør det efter din
rapport). Auth + API-form er ALLEREDE bevist live af drone under bootstrap — byg
ikke research om, verificér mod repoets faktiske mønstre." (Full brief covering:
base https://api.enablebanking.com; self-signed RS256 JWT auth via the `cryptography`
lib, no token endpoint/refresh; three vault-keyed sessions in
`enablebanking-sessions`; three schemas kronjylland_business / kronjylland_personal
/ revolut_privat; per-account `GET /accounts/{uid}/transactions` paginated on
`continuation_key`; consent expiry ~90d must HARD-FAIL loudly; three design
decisions to resolve — source-to-schema/job mapping, dedup key, get_secret for
PEM/JSON; strict data-leak discipline. Worktree
`.claude/worktrees/enablebanking-ingestion` on `feature/enablebanking-ingestion`
from master.)

**Interpretation:** Build Enable Banking as an extraction adapter in the
Kraken/CorPay shape but with (a) a third auth model — an on-demand self-signed JWT,
(b) a two-level fetch loop — outer over accounts, inner paginating a cursor, and (c)
three fully separate source systems split on schema + job like kraken /
kraken_privat. Verify the repo's actual mechanics support this before handing to a
builder; do not implement.

**Inferred intent:** A repeatable, cost-minimal, leak-safe way to land Benny's real
bank ledgers into datavilla's bronze layer, correct across full-history pulls, that
fails loudly and legibly the day a PSD2 consent expires (so Benny knows to re-run
`eb_consent.py`), and that never lets a real transaction value touch git.

### What I did

Read the reusable patterns end to end from the two live worktrees: the CorPay
adapter (`extract/corpayone.py`, the nearest forebear — an OAuth-ish extraction with
paging and hard-fail on 4xx), the Kraken adapter (`extract/kraken.py`), the
extractor contract (`extract/base.py`), the extract/autoload orchestration
(`extract_load.py`, `extract/runner.py`, `autoload.py`), the SCD2 merge engine
(`write/scd2.py`), the config model (`config.py` on both master and the CorPay
branch, which added `PIVOT_ADAPTERS` and made `endpoint.key_field` conditional), the
job generator (`scripts/generate_jobs.py`), the source ymls
(`config/sources/{kraken,kraken_privat,corpayone}.yml`), the secret helper
(`secrets.py`), and the Unity Catalog module
(`infra/modules/unity_catalog/{variables.tf,main.tf}`). Also read the drone's
reference scripts in scratchpad (`eb_consent.py`, `eb_verify.py`, `eb_probe.py`) to
pin the exact API form (JWT build, endpoints, response shapes) — they print only
counts and field-present/absent, never values.

Confirmed master == origin/master at f714763 (clean HEAD), then created the worktree
`.claude/worktrees/enablebanking-ingestion` on branch
`feature/enablebanking-ingestion` from master and started this diary.

### Why

The brief states auth and API shape are already live-verified by the drone, so the
value of this step is confirming the repo's mechanics support the required
combination (three separate systems, a cursor-paginated two-level loop, a JWT auth
model, and a full-pull history strategy) and pinning down the genuinely-open
decisions — not re-researching the API.

### What worked

The pattern matches and Enable Banking inherits most machinery for free, exactly as
CorPay did:

- Extraction adapters register via `@register_extractor(name)` + membership in
  `EXTRACTION_ADAPTERS` (config.py). The job shape (`EXTRACTION_JOB_TEMPLATE` in
  generate_jobs.py) is fully generic: one job per `landing.schema`, one shared
  single-node cluster bound to the cluster policy, `concurrency: 1`, run_as=SP,
  entry point `datavilla-extract-load`. Three landing schemas => three jobs
  (`ingest_kronjylland_business`, `ingest_kronjylland_personal`,
  `ingest_revolut_privat`) automatically.
- CorPay already blazed the "non-pivoting extraction adapter" trail:
  `PIVOT_ADAPTERS` gates the `endpoint.key_field` requirement, so a list-shaped API
  (Enable Banking returns `{transactions:[...], continuation_key}`) omits
  `key_field` WITHOUT a config lie and WITHOUT weakening Kraken's guardrail. Enable
  Banking is NOT a pivot adapter.
- `secrets.get_secret` returns the raw secret string via `client.get_secret().value`
  — a Key Vault secret preserves multiline content verbatim, so a multiline PEM and
  a JSON blob both come back intact as one string. NO change to secrets.py is needed:
  the extractor parses the JSON itself with `json.loads` and hands the PEM string to
  `cryptography.serialization.load_pem_private_key`. (Design decision 3 — resolved
  below.)
- Raw schema is auto-created by the framework at runtime: `ensure_raw_table` runs
  `CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}` (write/raw.py) and the SP holds
  CREATE_SCHEMA/CREATE_TABLE/MODIFY on raw. So — same as Kraken/CorPay — the ONLY
  infra change is adding the three landing schemas to the `landing_schemas` default
  set in `infra/modules/unity_catalog/variables.tf`. Each new key is a
  for_each-over-a-set ADD (schema + `incoming` volume); the `moved` blocks are keyed
  to "kraken" and untouched.

### What didn't work

Nothing broke. One thing I explicitly COULD NOT verify locally, by design: the
actual transaction field shape. `eb_verify.py` only ever printed counts and
"continuation present yes/no" (leak-discipline), and running it live needs the
vault PEM + the `eb_sessions.json` the drone already deleted after uploading to the
vault. So the dedup-key decision cannot be settled from local artifacts — it can
only be settled by inspecting one live transaction's field NAMES on a cluster. This
is a real check, not a guess, and I have flagged it as the builder's first live
task (see Design decision 2). `eb_probe.py` is only an `/aspsps` + `/application`
liveness probe; it carries no transaction fields.

Separately, the harness isolates this lead into its own worktree
(`agent-ac3dd06accf3baf42`) and the Write/Edit tools refuse to write into a sibling
worktree ("Edit the worktree copy of this file instead of the shared-checkout
path"). The feature worktree was created via git and this diary was written into it
via a shell copy, which the sandbox permits. The builder must be spawned with its
cwd pinned to `.claude/worktrees/enablebanking-ingestion` so its work and commit
land on `feature/enablebanking-ingestion`.

### What I learned

Enable Banking is a genuinely NEW extraction shape, not just a third dialect:

1. **Auth is a self-signed JWT with no server round-trip.** Header
   `{typ:JWT, alg:RS256, kid:<app_id>}`, payload
   `{iss:enablebanking.com, aud:api.enablebanking.com, iat, exp<=iat+3600}`, signed
   with the RSA private key via `cryptography` (PKCS1v15 / SHA256) — NOT PyJWT
   (not installed on the runtime). Built fresh on-demand each run; there is no token
   endpoint and no refresh token to store or rotate. Contrast Kraken (API-key + HMAC
   nonce) and CorPay (OAuth refresh-token dual-host).
2. **The fetch is TWO levels: outer over accounts, inner over a cursor.** A session
   holds a LIST of `account_uids`. For each, `GET /accounts/{uid}/transactions`
   returns `{transactions:[...], continuation_key}` and the extractor pages on
   `continuation_key` until it is empty. This is CURSOR pagination, not the
   offset/`total` model `EndpointConfig` encodes (offset_param/count_field). Like
   CorPay, the extractor should run its OWN loop and not force-fit the Kraken
   pagination fields.
3. **The identity/account inputs come from a JSON SECRET, not from config.** The
   `session_id` and `account_uids` live in the `enablebanking-sessions` vault secret,
   keyed by source. Config carries only WHICH session key this source uses; the
   extractor reads the JSON, selects its session, and iterates that session's
   accounts. This is new — Kraken/CorPay took all their runtime inputs from short
   scalar secrets.

### What was tricky

Three design tensions resolved and handed to the builder as constraints, not left
implicit. These are the three decisions the brief asked me to settle:

**Decision 1 — three sources -> three schemas -> three jobs (RECOMMEND, and it is
the only correct option).** Follow the kraken / kraken_privat split exactly: one
`landing.schema` per source (`kronjylland_business`, `kronjylland_personal`,
`revolut_privat`), each its own `target.schema`, each generating its own
`ingest_<schema>` job via `SourceDefinition.job_group` (which keys on
`landing.schema`). Do NOT collapse the three into one `for_each` job over sessions.
The argument for one job (fewer clusters) is real but wrong here: the three sessions
are three separate consents with three separate `session_id` credentials and three
independent expiry clocks, and — decisively — Kronjylland business vs personal share
ZERO accounts (drone-verified), so there is no overlap to justify fusing them. Three
schemas keep landing state, checkpoints and raw tables cleanly isolated and let one
consent expire/renew without touching the other two. Each source is ONE logical
endpoint ("transactions") whose extractor loops over that session's accounts
internally, so each job is a single-endpoint job (not a multi-endpoint for_each like
Kraken's) — three one-task extraction jobs. Cost is three cluster spinups on a
schedule; for three independent bank consents that is the right isolation, and it
matches the precedent set for the two Kraken accounts.

**Decision 2 — dedup / history strategy (the MAIN decision; RECOMMEND SCD2 on a
COMPOSITE key IF a stable per-transaction id exists, else fail fast and reconsider —
builder must verify field NAMES live first).** The mechanics force the shape of this
choice:
  - Full history is pulled EVERY run with no date filter. Under plain `append`
    (Kraken's model) every daily run re-appends all history, so raw doubles/triples
    without bound — wrong for a transaction ledger. So append is out.
  - SCD2 is the CorPay-proven fit for "full pull every run": a re-delivered unchanged
    transaction hashes identically and writes nothing; a corrected one is versioned.
    This is what we want — BUT SCD2 needs a stable, non-null, batch-unique key, and
    PSD2 transactions are notorious for lacking one: `entry_reference` is
    bank-optional and can be null, and pending->booked transitions can change a
    transaction's identity. `write/scd2.assert_keys_not_null` HARD-FAILS on a null
    key (correct — a null key would insert a duplicate every run), so a nullable key
    is not merely suboptimal, it aborts the load.
  - CRITICAL batch constraint I verified: for EXTRACTION sources
    `autoload._read_plan` sets `dedupe_order=None`, and Auto Loader drains ALL new
    files in ONE batch. So (a) the extractor MUST dedup within a run (a
    continuation-key page-shift can surface the same transaction twice — the same
    pattern CorPay handles for its Count/Offset shift), and (b) because ALL of a
    session's accounts land into ONE raw `transactions` table in one batch, the
    dedup/merge key MUST be COMPOSITE: `(account_uid, <transaction id>)`. A bank's
    `entry_reference`/`transaction_id` is only guaranteed unique WITHIN an account;
    two accounts could collide on a bare id and abort the merge or mis-version. The
    extractor already knows `account_uid` from its outer loop and MUST stamp it onto
    every landed record as an explicit field (also needed as raw provenance:
    otherwise a row cannot be traced to its account).
  - RECOMMENDATION: the builder's FIRST live step is to inspect ONE transaction's
    field NAMES (never values) per bank via the `eb_verify` pattern and confirm
    whether a stable, always-present id exists (`entry_reference` and/or
    `transaction_id`). If yes -> `history: scd2`, `keys: [account_uid, <that
    field>]`, extractor dedups the same composite within a run. If NO stable non-null
    id exists on either bank -> STOP and escalate to Benny: the fallback is
    snapshot-style (treat each full pull as the truth and overwrite), which needs a
    partition key and loses correction history, so it is a real product decision, not
    a builder default. I am NOT calling SCD2 "probable" — it is the right answer only
    if the live field check passes, and that check has not been run.

**Decision 3 — `get_secret` for PEM + JSON (RECOMMEND no change).** Verified
`secrets.get_secret` returns `SecretClient.get_secret(name).value`, i.e. the raw
string. Azure Key Vault stores and returns a secret value verbatim, newlines
included, so a multiline PEM and a JSON blob both round-trip as one string with no
special handling. The extractor does the parsing: `json.loads` on the sessions
string, `load_pem_private_key` on the PEM string. So secrets.py needs NO change —
the "new for this source" worry (multiline/JSON) is handled entirely on the caller
side. The builder should add a test that a multiline-PEM-shaped and a JSON-shaped
string survive the injected `secret_getter` seam unaltered (a pure test, no vault).

### What warrants review

Lead (me) will review the builder's diff for REAL-DATA LEAKAGE before any commit —
this is the most sensitive source in the repo and the brief flags two prior leak
incidents (e-conomic, Koinly) caused by real values used as "format examples". The
builder's green report is NOT the last check. Every example in code/tests/fixtures/
comments/diary must be synthetic (amount 12345, IBAN "DK0000000000000000", name
"ACME", uid "acc-001", date 1999-12-31), and when probing live data the builder must
print field NAMES and counts only, never values. Also verify: the honest dedup-key
resolution (composite key, live field-name check actually done); `account_uid`
stamped on every record; consent-expiry HARD-FAIL with a clear per-source message
("Enable Banking-session udløbet for <kilde> — kør eb_consent.py igen") and NEVER a
silent zero-load; within-run dedup on the composite key; and the JWT built with
`cryptography` (not PyJWT) with `exp <= iat + 3600`.

### Future work

If the live field check finds NO stable transaction id on a bank, the snapshot
fallback (and whether to add a booking-date partition) becomes a Benny decision —
deferred until the check is run. A `/balances` raw table per account is a trivial
later add if Benny wants balance history (the drone's verify already reads it); not
in v1 scope. Consent renewal is a manual local run of `eb_consent.py` every ~90
days that rewrites the `enablebanking-sessions` vault secret; a future nicety is a
run-log/alert that surfaces the approaching `valid_until` before it expires rather
than discovering it via a hard-fail.

## Step 2: Build the extractor, config, tests; run the live field-name probe

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Byg ingestion-kilden \"Enable Banking\" (tre bank-kilder) i
datavilla. Lead har forfinet kravene, verificeret mønstret mod koden og forberedt
worktreen. Du udfører efter lead's specifikation nedenfor." (Full builder brief:
work ONLY in the `enablebanking-ingestion` worktree; follow the lead's 8-point plan
— extractor + registry + config `session_key`/`EXTRACTION_ADAPTERS` + three-source
yml + generate_jobs + variables.tf + tests + live proof; Decision 2 = probe field
NAMES live FIRST and pick a stable composite id or escalate; absolute leak
discipline — everything synthetic, print only field names + counts; commit at the
end with identity `singularity-consult <benny@singularityconsult.dk>`, do NOT push.)

**Interpretation:** Implement Enable Banking end to end in the CorPay extraction
shape but with a self-signed-JWT auth, a two-level account/cursor fetch, and three
separate schema/job systems — and, before finalising the dedup key, actually run
the live leak-safe field-name probe to settle whether a stable transaction id
exists, rather than assuming SCD2 works.

**Inferred intent:** Get Benny's three real bank ledgers landing into datavilla's
bronze layer, correct across full-history pulls, failing loudly on an expired
consent, with the dedup key proven on the real data and not one real transaction
value ever touching git.

### What I did

Read the reusable machinery first (the lead's Step 1 pointed straight at it): the
CorPay adapter and its config/test diff on `feature/corpayone-ingestion` (commit
`7f65d6d`), the extractor contract (`extract/base.py`), the config model, the job
generator, `secrets.py`, `write/scd2.py`, `autoload._read_plan`, and the UC module
`variables.tf`. Also re-read the drone's `eb_consent.py`/`eb_verify.py` in scratchpad
for the exact JWT build and endpoints.

Then, before writing the writer's key, I ran the **live leak-safe field-name probe**
(Decision 2). Azure CLI was already authenticated on the correct dev subscription
("Microsoft Partner Network"), the API was reachable (`GET /application` → 401 =
reachable), and all three `enablebanking-*` secrets were readable (checked via
metadata only, never printing a value). I downloaded the PEM and the sessions JSON
to the scratchpad (never the repo, never stdout), then wrote `eb_fieldprobe.py`
which, per session per account, paginates ALL transactions on `continuation_key` and
prints ONLY field names, record counts, non-null counts and distinct counts —
distinctness measured by hashing each value (sha256) and counting distinct hashes,
so no value is ever printed, stored or logged; accounts are referred to by ordinal.
The first run block-buffered its output and truncated on the harness's file capture,
so I re-ran with `python -u` capped to four accounts per session across all three
sessions. Then I deleted the PEM and sessions JSON from scratchpad.

Built the deliverable: `extract/enablebanking.py` (self-signed RS256 JWT via
`cryptography`, two-level account/cursor loop, `account_uid` stamping, within-run
COMPOSITE dedup, leak-safe ordinal filenames, typed hard-fail errors), registered it
in `extract/__init__.py`, added `enablebanking` to `EXTRACTION_ADAPTERS`, reproduced
CorPay's `PIVOT_ADAPTERS` gate verbatim (so a future merge is clean) to make
`endpoint.key_field` optional for non-pivot adapters, added a new explicit
`session_key` field to `SourceDefinition`, wrote `config/sources/enablebanking.yml`
(three sources), regenerated the jobs (three new `ingest_*.job.yml`), and added the
three landing schemas to `variables.tf`. Wrote `tests/test_enablebanking.py` (23
tests) plus additions to `test_config.py` and `test_generate_jobs.py`. Ran
`fmt`/`validate`/`plan` on the infra.

### Why

The probe is the whole point of Decision 2: SCD2 on a composite key is only correct
if a stable, always-present, within-account-unique id exists, and PSD2 famously
often lacks one. Running it on the real ledgers — not guessing — is what lets the
`keys` and `history: scd2` in the yml be asserted rather than hoped. Everything else
follows the CorPay precedent because Enable Banking inherits the same extraction
chain; reproducing the `PIVOT_ADAPTERS` gate byte-for-byte (rather than inventing a
different relaxation) keeps the eventual merge of the two branches trivial.

### What worked

The probe settled Decision 2 cleanly and on real data: **`entry_reference` is
present on 100% of transactions and distinct on 100% within every account probed,
across all three banks** (Kronjylland business, Kronjylland personal, and — a
different ASPSP with a partly different schema — Revolut). `transaction_id` is
entirely null everywhere (PSD2-optional), so it is NOT usable; `booking_date` and
`value_date` are full but not unique. So the composite `(account_uid,
entry_reference)` is the right SCD2 key, `assert_keys_not_null` will pass, and NO
escalation was needed. One Revolut account (a2) has zero transactions — the
extractor handles that by writing no file, verified in a test.

The build fell straight out of the CorPay shape. All 185 tests pass; `generate_jobs
--check` reports no drift; the extractor registers (`get_extractor('enablebanking')`
resolves); `terraform validate` succeeds and the plan creates exactly the three
schemas + three volumes I intended.

### What didn't work

Two real blockers, both reported honestly rather than papered over:

1. **The infra apply is BLOCKED by shared-dev-state divergence — I did NOT apply.**
   `terraform plan -var-file=dev.tfvars` returned `Plan: 7 to add, 7 to change, 3 to
   destroy`, NOT the lead's expected `+3/+3, 0 destroy`. The three destroys and part
   of the changes are `module.unity_catalog.databricks_schema.landing["corpayone"]`
   and `...databricks_volume.landing["corpayone"]` being **destroyed**, plus seven
   `databricks_grants.layers[*]` / policy-permission updates. Root cause: the shared
   dev remote state already has CorPay's infra applied (from the unmerged
   `feature/corpayone-ingestion` branch), but THIS branch is forked from master
   (`f714763`) and its `landing_schemas` set has no `corpayone`, so terraform wants
   to delete it. Applying would destroy another feature's landing schema/volume in
   dev. Per the terraform safety rule ("never apply a plan with unexpected
   destroys"), I stopped. The three EB additions in the plan are correct; the
   destroys are not mine to make. This is a lead/integration decision (rebase this
   branch onto a base that includes corpayone, or reconcile the two branches before
   any dev apply).

2. **The live twice-run SCD2 no-op proof is consequently BLOCKED too.** Without the
   apply there are no EB landing volumes and no raw tables to write to, so "raw rows
   == distinct composite keys" and "second run = SCD2 no-op" cannot be demonstrated.
   I refuse to report these as green when I have not seen them run. They are
   verifiable the moment the infra divergence is resolved and the bundle is deployed:
   the offline tests already prove the extractor's pagination, composite dedup,
   account_uid stamping and hard-fails against a fake transport; what remains is the
   real API + Spark/Delta merge, which only a cluster can confirm.

The only in-code hiccup was a test I initially wrote (`test_session_key_is_required`)
using the secret name `ss`, which my fake getter didn't recognise as the sessions
secret, so it surfaced a JSON-parse error instead of the session_key error. The real
fix was better ordering: `_account_uids` now validates `session_key` presence BEFORE
spending a vault fetch, which is also more correct (a missing session_key is a config
error, not a secret problem).

### What I learned

The Enable Banking transaction schema (field NAMES only, from the probe): the stable
scalar id is `entry_reference`; `transaction_id` is always null; `booking_date`,
`value_date`, `credit_debit_indicator`, `status` are full but non-unique; and the
schema is NOT identical across banks — on Kronjylland `bank_transaction_code` is a
scalar, on Revolut it is a nested object. That last point vindicates landing each
transaction verbatim (no pivot) and relying on Delta column mapping + a composite key
rather than any assumption about a uniform flat shape. Also: the two Kronjylland
sessions' first accounts returned byte-identical counts (1277 tx, same distincts),
which is at odds with the Step 1 note that business and personal "share ZERO
accounts" — flagged below; it does not affect correctness because each session lands
in its own isolated schema.

Mechanically: `_read_plan` sets `dedupe_order=None` for extraction sources, so the
within-run dedup MUST live in the extractor (a page-shift duplicate would otherwise
abort the Delta merge), and it MUST be the composite `(account_uid, entry_reference)`
because all of a session's accounts land into one raw table in one Auto Loader batch
and `entry_reference` is unique only within an account.

### What was tricky

The branch base. The lead's plan repeatedly references the `PIVOT_ADAPTERS`
mechanism as if it were in-tree, but this worktree is forked from master, where
CorPay (which introduced `PIVOT_ADAPTERS`) does not exist and `endpoint.key_field` is
unconditionally required. I reproduced CorPay's config change verbatim (same
`PIVOT_ADAPTERS` line, same `require_key_field` param, same wiring) so Enable Banking
parses without a `key_field` AND a later merge of the two branches is a no-op rather
than a conflict. The same divergence is what makes the dev terraform plan messy — the
two feature branches and the dev state are three different points in history.

The JWT lifetime was a subtle correctness edge: built once and reused, a genuinely
long single-session pull could age the token past Enable Banking's `exp <= iat +
3600` ceiling and then a 401 would be MISREPORTED as an expired consent. A JWT is a
cheap local RSA sign, so I made the extractor `refresh_auth()` per account, bounding
each token's age to one account's pull (the largest probed was 3,787 tx over 19
pages — well under an hour). A 401 now always means a dead consent.

### What warrants review

- **Leak review before push (lead's gate).** I held everything synthetic from the
  start (amount 12345, IBAN `DK0000000000000000`, name ACME, uid `acc-001`, id
  `TX0001`, date 1999-12-31) and scanned the diff: no app_id/session_id, no
  real IBAN, no probe artifacts staged, no PEM/JSON secret files. The probe's real
  output lives only in scratchpad and contains field NAMES + counts only, never a
  value. Please still run the final leak eye over the diff before any push.
- **The terraform divergence (blocker 1).** Decide how to reconcile this branch with
  the dev state that already has corpayone — the EB apply and the live proof both
  wait on it.
- **The Kronjylland business/personal identical first-account counts** — worth a
  quick check that the two consents really do point at different accounts, given
  Step 1 asserted zero overlap.
- The composite-key contract: `account_uid` is stamped by the extractor and is
  `keys[0]`; `entry_reference` is `keys[1]` and what the within-run dedup keys on.

### Future work

Resolve the branch/state divergence, apply the (corrected) infra, deploy the bundle,
and run each of the three jobs twice to capture the live proof (raw rows == distinct
composite keys; second run inserts/updates zero). Everything else — a `/balances`
raw table, a consent-expiry pre-warning before `valid_until` — remains as Step 1
noted, out of v1 scope.

## Step N: Deploy bundle + live twice-run proof (dev)

**Author:** builder (async)

### Prompt Context

**Verbatim prompt:** "Bevis Enable Banking-kilden live i dev. Koden er bygget,
konflikt-fri rebased, og infra er ALLEREDE applied (3 landing-volumes +
raw-schemas auto-oprettes). Du deployer bundle og kører de tre jobs mod ægte
data, verificerer rækketal + SCD2 no-op. Du ændrer IKKE koden — kun deploy + run
+ verificér. Findes en reel fejl: STOP og rapportér, fabrikér ikke grønt."

**Interpretation:** The code and infra are done; my job is purely the operational
proof — deploy the DAB dev bundle, run the three ingest jobs against the real
banks, and confirm both that each raw table's row count equals its distinct
composite-key count (the dedup key holds) and that a second identical run adds no
rows (the SCD2 overlap no-op). No code changes; a genuine failure means stop and
report, not paper over.

**Inferred intent:** Turn "built and reviewed" into "demonstrably works against
live PSD2 data in dev" — the last gate before this source is trusted.

### What I did

Deployed the dev bundle from `src/` with
`databricks bundle deploy -t dev --var cluster_policy_id=<dev minimum-cost job
policy id>` (found by listing cluster policies: the `datavilla-dev-minimum-cost-job`
policy). The first deploy died on `error downloading Terraform: unable to verify
checksums signature: openpgp: key expired`; pointing the CLI at the winget
Terraform via `DATABRICKS_TF_EXEC_PATH` + `DATABRICKS_TF_VERSION=1.14.6` fixed it
and the deploy completed. Three jobs appeared: `ingest_kronjylland_business`,
`ingest_kronjylland_personal`, `ingest_revolut_privat`. Confirmed the three landing
schemas + `incoming` volumes already exist; the three `raw.*` schemas did not, and
auto-created on first write (`write/raw.py` `CREATE SCHEMA IF NOT EXISTS`).

Ran each job non-blocking (`jobs run-now --no-wait`) and polled `jobs get-run` in
short calls. Verified counts via the Statement Execution API on the serverless
warehouse with an az token. For each raw `transactions` table I compared
`count(*)`, `count(distinct account_uid|entry_reference)`, `count_if(_is_current)`
and `count(distinct account_uid)`, then re-ran the job and re-checked.

Aggregate results (no values, per leak-discipline):

- kronjylland_business: run1 + run2 both SUCCESS. rows 8568 == distinct composite
  8568 == current 8568, 10 accounts. Second run: 8568 unchanged. No-op holds.
- kronjylland_personal: run1 + run2 both SUCCESS. rows 8568 == distinct composite
  8568 == current 8568, 10 accounts. Second run: 8568 unchanged. No-op holds.
- revolut_privat: run1 + run2 both SUCCESS. rows 42 == distinct composite 42 ==
  current 42, 3 accounts. Second run: 42 unchanged. No-op holds.

### Why

The twice-run proof is the whole point: run1 shows the composite dedup key is
correct (every row is a distinct `(account_uid, entry_reference)` and all are
current), and run2 re-delivering the identical ledger writing zero new rows /
versions is the SCD2 overlap no-op — the dedup contract proven against live data,
not synthetic fixtures.

### What worked

The extraction chain ran clean end to end for all three consents once quota was
respected. Per-table the SCD2 key behaves exactly as designed: rows == distinct
composite == current on first run, and byte-identical on re-run.

### What didn't work

Two real failures. First, the Terraform-binary download (`openpgp: key expired`) —
the documented winget-Terraform override cleared it. Second, and more instructive:
firing all three jobs at once terminated the revolut cluster with
`AZURE_QUOTA_EXCEEDED_EXCEPTION ... QuotaExceeded: ... Total Regional Cores quota
... Location: northeurope`. Three single-node `Standard_F4s_v2` clusters at once =
12 vCPU, over the region's approved cores. Not a code defect — my parallel fire was
wrong. Fix: run the jobs serially (one cluster at a time); all three then
succeeded. The per-consent isolation design means three spinups, but they must be
sequential in this subscription.

### What I learned

The dev subscription's northeurope core quota does not fit three ingest clusters
concurrently — operationally these jobs must be triggered serially (or the quota
raised) even though each is independent. The serverless warehouse auto-starts from
STOPPED on first statement, so verification needs no manual warehouse start.

### What was tricky

Distinguishing a real code/consent fault from an operational one under a "don't
fabricate green" mandate. The quota kill looked like a job failure; reading the
iteration's terminated-cluster reason showed it was infrastructure, not the
extractor. And the headline finding below took three leak-safe aggregate probes to
pin down without ever surfacing a value.

### What warrants review

**CONFIRMED: kronjylland_business and kronjylland_personal are NOT disjoint.** The
prior step's "What warrants review" asked for a check that the two consents point
at different accounts, given Step 1 asserted zero overlap. Live answer: their
`entry_reference` sets are 100% identical (shared 8568 of 8568), while their
`account_uid` sets are fully disjoint (0 shared) because Enable Banking issues a
session-scoped uid per consent. So the two Kronjylland consents cover the SAME
physical accounts / same transactions; the two raw tables are duplicates of one
ledger, differing only by consent-scoped `account_uid`. Confirmed further by
identical per-account count distributions (min 7, max 3790, avg 856.8, 9 distinct
count-values in BOTH). Revolut is genuinely separate (0 entry_reference overlap
with Kronjylland). Step 1's "share ZERO accounts" premise is false against live
data. The code is correct per-table (dedup + SCD2 hold within each table); this is
a consent-setup / design-premise decision for Benny: fuse the two, drop one
consent, or keep both intentionally. Nothing was changed in response — reporting
only.

### Future work

Benny to decide on the business/personal duplication. Operationally, gate the three
jobs to run serially (or raise the northeurope core quota) so a triggered "run all"
does not quota-kill a cluster.

## Step: Reduce three sources to two (Kronjylland dublet cleanup)

**Author:** builder (async)

### Prompt Context

**Verbatim prompt:** "Justér Enable Banking-kilden fra tre til TO kilder i
datavilla. De to Kronjylland-consents (business/personal) viste sig at være SAMME
ledger (verificeret: begge 8568 rækker, alle entry_reference identiske — psu_type
filtrerer ikke konti). Reducér til én `kronjylland`-kilde (alle 10 konti) + behold
`revolut_privat`. Erhverv/privat-split laves senere i curated på PSD2 `usage`-feltet,
IKKE via consents." (Full brief: new commit on top of dcda4cc, do NOT amend/push;
vault already collapsed to two keys `kronjylland` + `revolut_personal`; config to one
`enablebanking_kronjylland`; variables.tf landing_schemas remove the two dubletter add
`kronjylland`; terraform plan-before-apply expecting DESTROY 2 pairs + ADD 1 pair,
pre-approved, STOP if it touches anything else; drop the two dublet raw schemas via
Statement Execution API, preserve raw.revolut_privat; regenerate jobs; update the
three test files to two sources / 12 jobs / 32 sources; deploy dev bundle and run only
`ingest_kronjylland`, verifying rows == distinct composite keys and a second-run SCD2
no-op; leak-discipline aggregate-only.)

**Interpretation:** The prior step's live finding — that the two Kronjylland consents
expose the SAME physical ledger (identical entry_reference sets, disjoint only on
consent-scoped account_uid) — is now acted on. Collapse the two Kronjylland sources
into one `kronjylland` source over all 10 accounts, keep Revolut untouched, and prove
the single source end to end. The erhverv/privat distinction Benny needs moves
downstream to curated on the PSD2 `usage` field rather than being faked with two
consents.

**Inferred intent:** Stop double-ingesting one ledger into two raw tables. One
consent, one raw table, the erhverv/privat split derived later from a real per-account
attribute — a cleaner and cheaper bronze that still carries everything curated needs.

### What I did

Rewrote `config/sources/enablebanking.yml` from three sources to two: replaced
`enablebanking_kronjylland_business` + `enablebanking_kronjylland_personal` with a
single `enablebanking_kronjylland` (session_key `kronjylland`, landing/target schema
`kronjylland`, history scd2, keys `[account_uid, entry_reference]`, same vault secret
NAMES), and left `enablebanking_revolut_privat` (session_key `revolut_personal`,
schema `revolut_privat`) byte-unchanged. Updated the file's header comments so they no
longer claim "three sources / business vs personal share ZERO accounts" (that premise
is false against live data) and instead record the same-ledger finding and the
curated-split decision. Fixed the docstring reference in
`datavilla/extract/enablebanking.py` (the session-key example list) to `kronjylland` /
`revolut_personal`; no extractor logic changed (it is generic).

In `infra/modules/unity_catalog/variables.tf` removed `kronjylland_business` and
`kronjylland_personal` from the `landing_schemas` set and added `kronjylland`, updating
the accompanying comment. Regenerated jobs with `python scripts/generate_jobs.py` (not
by hand): it removed `ingest_kronjylland_business.job.yml` +
`ingest_kronjylland_personal.job.yml` and wrote `ingest_kronjylland.job.yml`; Revolut
and all other jobs unchanged. `generate_jobs.py --check` is clean.

Updated the three test files: `EXPECTED_ENABLEBANKING_SOURCES` is now
`{enablebanking_kronjylland, enablebanking_revolut_privat}`; the job-file set drops the
two dubletter and adds `ingest_kronjylland.job.yml` (12 jobs); the shared-cluster-spec
count assertion 13 -> 12; the "three consents" tests became two-consent tests over
`kronjylland` / `revolut_privat`; the synthetic fixtures in `test_enablebanking.py`
(`_eb_def` default, `_sessions` key, the landing-path assertion) renamed
`kronjylland_business` -> `kronjylland`. Full suite green: **206 passed**.

Infra: `terraform fmt -check` clean, `validate` Success, then `plan -var-file=dev.tfvars
-var service_principal_application_id=3953a8d0-...` against dev. Plan was exactly
**2 to add, 0 to change, 4 to destroy** — create `databricks_schema.landing[kronjylland]`
+ `databricks_volume.landing[kronjylland]`, destroy the schema+volume pair for each of
`kronjylland_business` and `kronjylland_personal`. Verified from the plan JSON that the
ONLY non-no-op resources were those six; corpayone, revolut, kraken, grants — all
untouched. Applied the saved plan: `Apply complete! Resources: 2 added, 0 changed, 4
destroyed`; the `landing_volume_paths` output now lists a single `kronjylland` plus
`revolut_privat` and everything else unchanged.

Dropped the two framework-created dublet raw schemas via the Statement Execution API
(serverless warehouse `03b065855ce85160`, az token for resource `2ff814a6-...`):
`DROP SCHEMA IF EXISTS datavilla_dev_raw.kronjylland_business CASCADE` and
`...kronjylland_personal CASCADE`, both SUCCEEDED. Confirmed no `kronjylland*` schema
remains in `datavilla_dev_raw` and that `raw.revolut_privat.transactions` still holds
42 rows (untouched).

Deployed the dev bundle (`databricks bundle deploy -t dev --var
cluster_policy_id=0016CFDC5ABE5A9C`, azure-cli auth, winget-terraform override
`DATABRICKS_TF_EXEC_PATH` + `DATABRICKS_TF_VERSION=1.14.6`). Ran ONLY
`ingest_kronjylland` (job 319913280161159), non-blocking, polled `jobs get-run` in
short repeated calls (no long blocking sleep — the earlier async builder died on the
watchdog). Run 1 (run_id 757717844743607) SUCCESS after ~13 min (cluster spinup
dominates). Verified `raw.kronjylland.transactions`: rows **8571** == distinct
`(account_uid, entry_reference)` **8571** == current **8571**, across **10 accounts**.
Then re-ran for the SCD2 no-op (run_id 1034090182081682) SUCCESS: the table is
**8571 / 8571 / 8571 / 10** again — byte-identical to run 1, zero new rows or
versions. The overlap no-op holds on the consolidated single source.

### Why

The two Kronjylland consents were proven in the prior step to be the same ledger
(100% identical entry_reference sets; disjoint only on consent-scoped account_uid).
Keeping both meant two raw tables that are duplicates of one another — pure double
ingestion and double cluster cost, with a business/personal label that PSD2 psu_type
does not actually enforce at the account level. One consent over all 10 accounts is
the honest bronze; the erhverv/privat split Benny needs belongs downstream in curated
where it can key on the real per-account PSD2 `usage` attribute, not on a consent that
does not filter.

### What worked

The change was almost entirely declarative: config + one line of the terraform set +
regenerate. The terraform plan matched the pre-approved forecast exactly and touched
nothing but the six intended resources, so the destructive apply was safe. Run 1's raw
invariant held perfectly — rows == distinct composite == current over 10 accounts —
which is the whole dedup-key proof on the consolidated single source.

### What didn't work

Nothing broke. Both runs succeeded first try, the terraform plan and apply matched the
forecast exactly, the raw dublet drops and the two-run proof all came back clean, and
the full test suite stayed green. The run-2 SCD2 no-op — the one check that could have
exposed a broken dedup key on the consolidated source — held: identical 8571 rows.
The only cost was wall-clock: each run is ~9-13 min, almost all cluster spinup on the
minimum-cost single-node policy.

### What I learned

The row count is **8571**, not the prior step's 8568. That is expected and not a
regression: this is a freshly-minted single `kronjylland` consent read two days later
(2026-07-30 vs 07-28), so a handful of new transactions posted in the interim. What
matters for correctness is the invariant rows == distinct composite == current, which
holds exactly at whatever the current ledger size is. The count is a moving target;
the key contract is not.

### What was tricky

Poll discipline. The prior async builder died on the watchdog from a long blocking
wait; here every wait was a short `jobs get-run` call, fired after a non-blocking
`run-now`, never a single sleep over ~60s. Cluster spinup on the minimum-cost
single-node F4s policy is ~5-9 min and dominates wall-clock, so "still RUNNING at 10
min" is normal, not a hang — confirmed by reading elapsed time and the for_each task
state rather than assuming.

### What warrants review

- **Leak discipline:** everything reported and written here is aggregate only — row
  counts, distinct-key counts, account counts, run_ids. No IBAN, name, amount, or
  entry_reference value appears in code, tests, diary or report. The synthetic
  fixtures are unchanged in spirit (acc-001, TX0001, 12345, DK0000...).
- **The destructive infra apply** was pre-approved as a dublet cleanup; the plan JSON
  was checked to touch only the six kronjylland resources. Re-confirm against the
  applied state if desired.
- **Curated erhverv/privat split** now depends on the PSD2 `usage` field being present
  and populated per account in `raw.kronjylland.transactions` — worth confirming when
  the curated layer is built that `usage` (or an equivalent account attribute) is
  actually landed and non-null, since the split has no fallback if it is missing.

### Future work

Build the curated erhverv/privat split on `usage`. If `usage` turns out to be null or
absent for some accounts, that is a real product decision for Benny (map accounts by
IBAN, or carry an explicit account->segment lookup) rather than a silent default. The
consent-expiry pre-warning and a `/balances` raw table remain out of scope as before.
