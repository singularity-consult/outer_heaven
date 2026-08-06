# Diary: Enriched layer — generic, metadata-driven cleansing engine (Blok 2)

Datavilla's medallion is raw -> **enriched (merge+cleanse)** -> curated (dim/fact) ->
integration; the base layer is skipped. Raw now holds all sources (bank, spend/accounting,
crypto), with MetaMask on-chain + CoinGecko merged into master at `8988488`. This feature
builds the **enriched** layer. After a brainstorm that challenged several implicit
assumptions, Benny settled the direction firmly: enriched is NOT per-domain conform
modelling — it is a **generic, reusable, metadata-driven CLEANSING engine** that mirrors how
raw works (a generic engine + per-source YAML). Union/dedup/source-of-truth/FIFO/valuation
and segment-splitting all move UP to curated. This diary opens with the approved plan; no
code is written yet — a builder will implement it against this entry.

## Step 1: Approved plan + worktree preparation (no code yet)

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Benny GODKENDTE planen med alle tre defaults: (1) DK-søster hedder
`<navn>_dk`; (2) trim+snake_case opt-out/typning opt-in; (3) stale DSA-tabeller
(djurslandsbank, sparekassenkronjylland konti_base) parkeres fra enriched; segment-derivation
-> curated. Byg klar. Forbered worktreen (byg IKKE selv): opret branch
`feature/enriched-engine` fra ren master (`8988488`), skriv feature-diary Step 1 der beskriver
planen (motoren `src/datavilla/enriched/`, transform-bibliotek, current-view-læser, config
`enriched:`-blok, profile_enriched.py, generate_jobs-udvidelse, de tre defaults). Diary SKAL
ligge i datavilla-worktreen `docs/diary/`, ALDRIG i outer_heaven-repoet (den fejl skete ved
MetaMask). Verificér master er ren først. Rapportér den PRÆCISE worktree-sti + branch-navn, så
main spawner builderen på din plan. Ingen kode endnu — kun worktree + diary."

**Interpretation:** The enriched brainstorm is over and every open decision is settled. My
job in this step is NOT to implement, but to (a) create a clean feature worktree off master
`8988488`, (b) record the fully-approved plan in the feature diary inside the datavilla
worktree, and (c) report the exact worktree path + branch so a builder can be spawned onto it.

**Inferred intent:** Give the builder a single, unambiguous, approval-frozen specification to
implement against, and get the diary location right this time (it wrongly landed in
outer_heaven during the MetaMask feature). Keep the plan and its rationale in one place that
travels with the branch.

### What I did

Read the raw layer end to end to ground the plan in reality rather than assumptions: all
source configs under `src/config/sources/*.yml` (dsa, enablebanking, economic, corpayone,
pleo, kraken, kraken_privat, koinly, plus metamask + coingecko now on master), the three raw
write engines (`write/raw.py` append-only bronze, `write/scd2.py` key+content-hash versioning,
`write/snapshot.py` per-year partition replace), `config.py` (VALID_LAYERS already includes
`enriched`; `catalog_name` resolves `datavilla_<env>_enriched`), and the README's explicit
"Blok 2" contract (latest snapshot per key by greatest `_ingested_at`).

Then prepared the worktree: verified master is clean at `8988488` (`git status --porcelain`
empty; `git rev-parse master` = `8988488e3b22c09dab30b6d53b178cc0c650f271`), and created the
feature worktree:

```
git worktree add -b feature/enriched-engine ".claude/worktrees/enriched-engine" 8988488
```

Worktree path: `C:\claudes_folder\repos\datavilla\.claude\worktrees\enriched-engine`
Branch: `feature/enriched-engine` (based on master `8988488`).

**The approved plan the builder implements:**

**Architecture (mirrors raw).** A generic transform library (Spark `Column` expressions +
registry) + a generic current-view reader + a per-source `enriched:` block inside the EXISTING
`sources/*.yml`. The engine reads raw's current row, snake_cases + trims everything, applies
declared transform chains to the exception columns, and **full-overwrites**
`enriched.<schema>.<table>` 1:1 per raw table. No merge, no union, no dedup.

**Engine location — new subpackage `src/datavilla/enriched/`:**
- `transforms.py` — the library: `Column`-expression functions + `@register_transform` registry
  (same pattern as `@register_extractor` / `register/get_adapter`).
- `reader.py` — `read_current(raw_table, history, keys)`, dispatch on `history`.
- `engine.py` — orchestration + `datavilla-enrich` CLI entry point.
- `config.py` gains `EnrichedSpec` / `EnrichedColumn` dataclasses parsing the `enriched:` block,
  alongside the existing `TargetConfig` / `FileConfig`.

**Transform library.** Universal (opt-out, auto on all columns): `trim` (F.trim on string cols);
`to_snake_case` (column-NAME transform: lowercase, non-alnum->`_`, collapse/strip; `Gain (DKK)`
-> `gain_dkk`, `CVR-nr.` -> `cvr_nr`, `Sending Wallet` -> `sending_wallet`; keeps source language;
collision -> hard error). Declared (opt-in per column, only on columns still string-typed in raw):
`parse_timestamp(col, format=... | epoch_seconds=True)` -> UTC-instant TimestampType;
`to_dk_local(col)` -> `from_utc_timestamp(col,'Europe/Copenhagen')`, ADDS a `<name>_dk` sibling and
keeps the UTC source; `to_decimal(col, style="us"|"dk", category="krypto"|"fiat"|"procent")`
(us: strip ',' thousands keep '.'; dk: strip '.' thousands, ',' -> '.'); `scale_by_decimals(value_col,
decimals_col)` -> value / 10^decimals (metamask `value`/`tokenDecimal`); `round_by_category(col,
category)` for already-numeric columns; `sign_by_indicator(amount_col, indicator_col,
negative="DBIT")`; `map_values(col, mapping, default)`; trivial `to_long`/`to_integer`/`to_boolean`.
Category -> precision: `krypto` = decimal(38,18), `fiat` = decimal(38,3), `procent` = decimal(38,2).
Escape-hatch: `@register_transform("navn")` registry for the irreducible ~5%. Crosswalk (XXBT->BTC)
is NOT here — Benny sent it to curated.

Conventions: parse/type transforms replace the column in place (same snake name); `to_dk_local`
ADDS a `_dk` sibling. Chain order matters (`parse_timestamp` BEFORE `to_dk_local`). No separate
"is-UTC" flag: `to_dk_local` being present in the chain IS the decision that the column is a true
UTC instant. Optional per-column `target:` rename override.

**Current-view reader.** Dispatch on `history` (already in config): `scd2` -> `WHERE _is_current`;
`append` + keys -> `row_number() over(partition keys order by _ingested_at desc)=1`; `append`
without keys -> rows from `max(_load_batch_id)` (covers kraken trades and the keyless jdbc sources);
`snapshot` -> all rows (koinly keeps its legitimate byte-identical duplicates; dedup is curated).

**Writer.** ONE mode — full overwrite (`mode("overwrite")`) on `enriched.<schema>.<table>`; enriched
always full-loads from raw's current-view, so no SCD2/merge. Keep provenance audit columns
(`_source`, `_ingested_at`, `_load_batch_id`, and `_source_file`/`_source_table`/`chain` where
present); DROP the SCD2 bookkeeping (`_is_current`/`_valid_from`/`_valid_to`/`_row_hash`).

**Config format.** `enriched:` block in the existing source entry. Default (trim+snake_case, all
string) is implicit; only exceptions are listed. Reuse-raw-hints mechanism: read raw's ACTUAL
materialized schema — any column already non-string passes through untouched (only snake_cased);
only string columns are candidates for typing transforms. Do NOT re-parse `file.decimal_columns`.
Worked examples:
- `koinly_privat`: `Date` already timestamp in raw -> `[to_dk_local]` only; the 8 amount strings
  typed (`Sent/Received/Fee Amount` -> `to_decimal(us, krypto)`; `Sent/Received Cost Basis`, `Gain
  (DKK)`, `Net Value (DKK)`, `Fee Value (DKK)` -> `to_decimal(us, fiat)`).
- `metamask_token`: `timeStamp` -> target `block_time`, `[parse_timestamp(epoch_seconds), to_dk_local]`;
  `value` -> `[scale_by_decimals(tokenDecimal), round_by_category(krypto)]`; `blockNumber` -> `to_long`;
  `tokenDecimal` -> `to_integer`.
- `economic_postering`: `columns: []` — raw already typed the decimals/dates (dates are CALENDAR
  dates, no tz-convert), so default trim+snake_case is all that runs. Demonstrates the reuse principle.

**Profiling assist.** Dev-time CLI `src/scripts/profile_enriched.py` (`datavilla-profile`), analogous
to `generate_jobs.py`. Input: a source/raw table. Scans the actual schema, selects only string
columns (skips already-typed), samples ~1000 rows, runs heuristics (date/timestamp pattern; US-comma
vs DK-comma numeric vs big base-unit int; category via name hint like `(DKK)` + magnitude; int/bool).
Emits (1) a DRAFT `enriched:` YAML block Benny edits into `sources/*.yml`, and (2) a human-readable
profile report (per column: samples, inferred type, confidence, null/distinct rates). Nothing
auto-applies — suggestion -> Benny validates -> becomes config.

**Job generation.** Extend the EXISTING `generate_jobs.py` (it already owns `resources/*.job.yml` and
groups per system via `job_group`/`for_each`). Add an enriched job template running
`datavilla-enrich <source>` per source, grouped like raw (economic's tables -> one enriched job/cluster).
`enriched` catalog already exists in IaC, so `target.layer=enriched` needs no infra change. Enriched
job depends on the raw job (raw runs first) — orchestration/trigger is a scheduling detail, flagged.

**The three approved defaults:**
1. DK-local sibling is named `<name>_dk`.
2. trim+snake_case are opt-OUT (automatic on all); typing/transforms are opt-IN (declared/profiled).
   String->string is the safe default (ids and wallet addresses stay string unless declared).
3. Stale DSA tables `djurslandsbank.allaccounts` and `sparekassenkronjylland.konti_base` (free-text /
   generic `Prop_*`, no keys) are PARKED — no `enriched:` block, excluded from the enriched job,
   reversible when real data lands. `alternative.feargreedindex` and `historic.transactions` are
   enriched normally. Segment-derivation (PSD2 `usage` -> erhverv/privat) goes to CURATED, not enriched
   (consistent with crosswalk); the `map_values` primitive stays in the library, its kronjylland
   application does not.

### Why

Grounding the plan in the real raw configs and write engines is what made the boundary defensible:
the three history modes (scd2/append/snapshot) are exactly why a generic current-view reader is needed;
the pervasive faithful-string amounts and messy Delta-column-mapped names are exactly the repeated
cleansing that justifies a shared engine rather than per-fact re-typing in curated. Creating the
worktree off a clean `8988488` gives the builder an isolated, reproducible base. Writing the plan into
the diary NOW — before any code — freezes the approved spec so the builder implements decisions rather
than re-litigating them, and keeps the rationale attached to the branch.

### What worked

Master was clean on the first check and the worktree was created without contention. The `enriched`
catalog and `VALID_LAYERS`/`catalog_name` machinery already existing in `config.py` means the target
layer needs no infra work — the plan slots into existing scaffolding. The raw configs are unusually
well-documented (every key/format decision is annotated), which let the plan cite concrete column
names (`Net Value (DKK)`, `tokenDecimal`, `Sending Wallet`) instead of hand-waving.

### What didn't work

One real snag: my original isolated worktree (`agent-a73f89166d31b8e05`) was cleaned up mid-session —
`cd` into it failed with `No such file or directory`, and `.claude/worktrees/` was empty. This is the
known "worktrees do not survive across long gaps" hazard. Recovered by working from the main datavilla
checkout (clean master) and creating a fresh, named feature worktree rather than reusing the ephemeral
agent one. No work was lost because nothing had been committed there yet.

### What I learned

The `history` field already sitting in every source config is the linchpin that makes the current-view
reader genuinely generic — the layer does not need any new per-source flag to know how to read "the
current row". And raw's ALREADY-materialized types are a better reuse signal than re-reading the
`file.*_columns` hints: trusting the raw schema means JDBC (typed at source), economic (typed in raw),
and koinly (partially typed) all flow through one uniform "skip non-string columns" rule.

### What was tricky

The sharpest boundary call was time. A blanket UTC->DK conversion is a correctness trap: economic's
`Dato`/`FakturaDato` are Danish CALENDAR dates (no instant), so converting them is a category error,
while metamask epoch and koinly's `'UTC'`-literal ARE true instants. The resolution — tz-convert only
where `to_dk_local` is explicitly declared, keep the UTC source alongside the `_dk` sibling — keeps
join/order correctness (relevant for crypto cost-basis) while giving Benny the human DK view. Also
subtle: the append-WITHOUT-keys case (djurslandsbank, kraken trades that declare no YAML `keys`) needs
the `max(_load_batch_id)` fallback, or "current view" is undefined.

### What warrants review

For the builder and reviewer: (1) the snake_case algorithm must handle every real messy name in raw
and hard-error on collisions rather than silently overwrite — verify against `economic_kunde`
(`E-mail til fakturaer`, `CVR-nr.`) and koinly (`Gain (DKK)` vs a hypothetical `Gain DKK`). (2) The
current-view reader's three branches — especially append-without-keys — need offline unit tests like
the existing `write/` modules have. (3) `scale_by_decimals` must cast `value` to a wide-enough decimal
BEFORE dividing (base-unit integers can exceed long range as strings) — verify precision. (4) Confirm
the enriched writer keeps provenance columns and drops only SCD2 bookkeeping.

### Future work

Noted but explicitly OUT of this plan: a separate NEW raw source for fiat FX day-rates (USD/DKK/EUR),
needed by curated for computed-currency valuation — comes AFTER enriched. Also downstream of enriched:
the curated layer (union/conform, Kraken<->Koinly and Pleo<->economic dedup/source-of-truth,
FIFO/cost-basis/what-if, segment-split, asset crosswalk XXBT->BTC), which this feature deliberately
does not touch.

### Handoff

Worktree ready for the builder: `C:\claudes_folder\repos\datavilla\.claude\worktrees\enriched-engine`
on branch `feature/enriched-engine` (from master `8988488`). No code written yet.

## Step 3 — live-bevist i dev (main kørte deploy+jobs; builder byggede+testede)
Bundle deployet af main (per databricks.yml: deploy er mains rolle). Tre enrich-jobs kørt grønt, verificeret via warehouse (kun schema/typer, ingen værdier):
- **economic** (nul-config): snake_case (LoebeNr→loebe_nr, BeloebDKK→beloeb_dkk), `beloeb_dkk` DECIMAL, `dato`/`forfalds_dato` DATE (kalenderdatoer — IKKE tz-konverteret, den kritiske korrekthed).
- **koinly_privat**: US-komma→DECIMAL; kategori-præcision `net_value_dkk` DECIMAL(38,3) fiat / `sent_amount` DECIMAL(38,18) krypto; `date` TIMESTAMP + `date_dk` TIMESTAMP (UTC+DK-søster).
- **metamask token_transfers**: `block_time` TIMESTAMP (epoch→UTC) + `block_time_dk`; `value` DECIMAL(38,18) skaleret via tokenDecimal.
Offline: 351 tests grønne. Første Blok 2-lag live.
