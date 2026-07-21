# Diary: Datavilla — Kraken PRIVAT account as a new, independent source

Add support for a second Kraken account (Benny's PRIVATE account) to the datavilla
metadata-driven ingestion framework, alongside the existing ERHVERV (business)
account. The two accounts must be separated on BOTH schema AND job. Approach is
strictly ADDITIVE: build the private account as a brand-new source system; do not
touch the existing `kraken.*` tables, landing, or Auto Loader checkpoints (renaming
or recreating any of those risks re-ingesting live data). Erhverv stays in the
`kraken` schema / `ingest_kraken` job exactly as today.

Solo learning project. Azure subscription "Microsoft Partner Network". Dev only.
Git identity already set locally. Not to be committed by the team — main reviews
and commits.

## Step 1: Requirements, verification, and design

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Byg support for Kraken PRIVAT-konto i datavilla-repoet, og driv
builder til at gore det gront live i dev." (Full brief carried locked decisions:
1) private and erhverv separated on BOTH schema AND job; 2) ADDITIVE — build ONLY
the private account as a new independent source, do not touch erhverv's existing
kraken.* tables/landing/checkpoints; 3) private credentials already in
kv-datavilla-dev as secrets kraken-privat-api-key / kraken-privat-private-key —
use them, never write secret VALUES to git. DoD: unit tests green (existing 119
must not break), ingest_kraken_privat run green live in dev with raw tables
verified filled, existing 6 jobs + erhverv kraken.* data untouched, NOT committed —
report diff + terraform plan + live verification numbers. Paraphrased here; no
secret values recorded.)

**Interpretation:** Add a second Kraken account as a fully independent source
(schema `kraken_privat`, job `ingest_kraken_privat`) without disturbing the live
erhverv pipeline, then prove it green live in dev.

**Inferred intent:** Exercise the framework's extension seams on the hardest case
its "one job per adapter" grouping does not yet handle — two accounts of the SAME
adapter that must NOT share a job (separate credentials, separate nonce sequences,
separate data) — done additively so live erhverv data is never at risk.

### What I did

Read the framework end to end before forming any plan: `src/config/sources/kraken.yml`,
`src/datavilla/config.py`, `src/scripts/generate_jobs.py`, `src/config/sources/economic.yml`,
`src/datavilla/secrets.py`, `src/datavilla/write/raw.py`, `infra/modules/unity_catalog/main.tf`
and `variables.tf`, plus a grep sweep for hardcoded "kraken" across the package and tests.
Established the design and handed a builder the concrete requirements.

### Why

The brief is explicit that the grouping key must change to include account/schema,
but insists nothing existing may break. Before any code I had to confirm that a
schema-based grouping key preserves every existing job name and that the extractor/
secret/path logic is already generic enough to carry a second account with no code
change beyond the grouping key and the config.

### What worked

Verification confirmed the design is clean and low-risk:

- Grouping key. `SourceDefinition.job_group` (config.py:541-561) returns
  `self.adapter` for landing sources, so two `adapter: kraken` accounts collapse
  into one `ingest_kraken` job — the exact thing that must not happen. For EVERY
  existing landing source, `landing.schema == target.schema == adapter`
  (kraken->kraken, economic->economic). So changing the landing-source grouping key
  from `adapter` to `landing.schema` preserves `ingest_kraken` and `ingest_economic`
  unchanged and gives the new account its own `ingest_kraken_privat`. jdbc sources
  keep `self.name`.
- Generic paths/secrets. `LandingConfig.volume_root` uses `self.schema`, so
  `kraken_privat` lands at `/Volumes/datavilla_dev_landing/kraken_privat/incoming/...`
  automatically. Secret names come from `KeyVaultRef.secrets` (config). No hardcoded
  "kraken" in path or secret logic. Checkpoints live under each schema's own `/_ops`,
  so `kraken` and `kraken_privat` checkpoints never collide even though the endpoint
  names (Balance/TradesHistory) are identical.
- Same extractor reused. `@register_extractor("kraken")` is keyed by adapter;
  `kraken_privat` keeps `adapter: kraken`, so it reuses the same Kraken signer — the
  only differences are schema, secrets, job, and cluster.
- Raw schema is runtime-created. `write/raw.py:104` does `CREATE SCHEMA IF NOT
  EXISTS`, so `datavilla_dev_raw.kraken_privat` is created by the job on first write
  — same as `datavilla_dev_raw.economic`. No infra change for raw.
- Infra is purely additive. `landing_schemas` is a `set(string)` default
  `["kraken","economic"]` in `modules/unity_catalog/variables.tf` (not overridden in
  tfvars). Adding `kraken_privat` is a for_each-over-a-set add: 2 creates (schema +
  volume), 0 destroy. The `moved` blocks are keyed to `"kraken"` and are unaffected.

### What didn't work

Nothing failed at the design/verification stage — this section is genuinely empty
for Step 1. Live-run outcomes and any test breakage will be recorded by the builder
in later steps.

### What I learned

The framework's "one job per adapter" grouping (documented at length in config.py
and generate_jobs.py) silently assumes one account per adapter. That assumption was
invisible until a second account of the same adapter appeared. The fix is not a new
YAML field but recognising that `schema` already encodes "the account/system" for
landing sources — the grouping key was one abstraction level too coarse.

### What was tricky

The trap is job-name preservation. A naive `f"{adapter}_{schema}"` key would rename
`ingest_kraken`->`ingest_kraken_kraken` and `ingest_economic`->`ingest_economic_economic`,
breaking 2 live jobs. `landing.schema` alone is safe only because of the (verified)
invariant that schema == adapter for every existing landing system — worth stating
in the code comment so a future reader does not "simplify" it back to something that
breaks. Also load-bearing for CORRECTNESS not just cost: the two accounts have
separate credentials and therefore separate Kraken nonce sequences; keeping them in
ONE for_each job would run both under one serialized nonce assumption that is wrong.
Separate jobs is the correct design, not merely the tidy one.

### What warrants review

- The one-line change to `job_group` and its comment/docstring honesty (config.py),
  and the parallel docstring in generate_jobs.py that still says "group by adapter".
- Test updates: `test_config.py:285`, `test_economic.py:155`, and
  `test_generate_jobs.py` expected-file-list — these encode the OLD grouping and must
  be updated to the new schema-based grouping, not deleted.
- The terraform plan must show 0 destroy / 0 replace on existing resources.
- Live proof: `datavilla_dev_raw.kraken_privat.balance` + `.trades` row counts, and
  that `kraken.trades` erhverv row count is unchanged.

### Future work

Test/prod rollout of the private account (this task is dev-only). If a third account
of any adapter ever appears, the schema-based grouping already handles it with no
further code change — only config + one `landing_schemas` entry.
