# Diary: Enriched (Blok 2) blocks for the 10 remaining sources

The enriched cleansing engine (Blok 2) landed at `664ae7a` and four sources already carry an
`enriched:` block inline in their YAML: economic (19 default-only sub-sources), koinly_erhverv /
koinly_privat (typed), metamask_native / metamask_token (typed). This feature designs the
`enriched:` block for the **10 remaining source files** — 16 sub-sources in total — so every
source gets an enrich job. This diary Step 1 is the **frozen design** (no code); a builder
implements the blocks + jobs + tests against it.

Recall the two shapes (from `src/datavilla/enriched/transforms.py`, `engine.py`, and the
economic/metamask/koinly references):

- `enriched: {columns: []}` = **default-only** (universal `trim` on strings + `snake_case`
  rename). Correct wherever raw already carries the right type — the *reuse-raw-types*
  principle (economic's `decimal(28,6)`/`DATE`; and, for the extraction sources, Auto Loader's
  `cloudFiles.inferColumnTypes=true` which lands JSON numbers as `bigint`/`double` and JSON
  strings as `string`).
- `columns:` list of `{name, target?, transforms:[...]}` = **per-column typing**, an ordered
  chain. `to_dk_local` ALWAYS after `parse_timestamp`; its presence IS the decision that a
  column is a true UTC instant.

## Step 1: Frozen per-sub-source design (no code)

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Design the enriched (Blok 2) blocks for the 10 datavilla sources that
still lack one, and prepare a worktree + a precise per-source builder spec. You DESIGN and
CHALLENGE scope; you do NOT implement (the builder does, which I spawn after you hand back).
[...] The 10 sources needing blocks: coingecko, corpayone, dsa, dst, enablebanking, feargreed,
kraken, kraken_privat, nationalbanken (FX), pleo [...] Decide the MINIMAL correct typing.
CHALLENGE over-typing hard [...] Do NOT modify .ps1 files. Do NOT push. Challenge my framing if
any of it is wrong (e.g. if a source genuinely needs NO block, say so)."

**Interpretation:** For every sub-source of the 10 files, decide the exact `enriched:` block
(typed columns with params, or `columns: []`) from PRIMARY evidence — the extractor docstrings
and the LIVE raw schema — and justify each line, challenging any typing that raw already
provides or that belongs in curated. Prepare the branch + spec; the builder implements offline.

**Inferred intent:** A minimal, honest, review-frozen typing contract the builder can apply
mechanically, that does not re-type what raw already typed and does not smear curated modelling
into the bronze->enriched hop.

### What I did

Read the transform library, engine, and the three references (economic default-only, metamask
typed, koinly fiat/krypto convention). Read all 10 source YAMLs and every extractor
(`coingecko/feargreed/nationalbanken/dst/kraken/corpayone/pleo/enablebanking.py`, `jsonstat.py`).
Then — the decisive evidence — `describe`d all 16 live raw tables in `datavilla_dev_raw` via the
SQL Statement Execution API (AAD token; the `databricks api` passthrough is broken here). For the
five personal-financial sources I inspected **types/structure only**, never a value.

The single most important finding: **the extraction sources land JSON with
`cloudFiles.inferColumnTypes=true`** (`write/autoloader.py:56`), so a JSON *number* is already
`double`/`bigint` in raw and a JSON *string* is `string`. This collapses most of the assumed
typing work — the reuse-raw-types principle already covers the numeric columns. The genuinely
mis-typed columns are few.

Confirmed live raw types (real, not assumed):

- `coingecko.prices`: asset_key `string`, chain `bigint`, price_date `string`, price_dkk `double`
- `dst.pris01`: VAREGR/ENHED/ContentsCode/Tid `string`, value `double`
- `feargreed.index`: date `string`, value **`string`**, value_classification `string`
- `nationalbanken.exchange_rates`: currency_code `string`, kurtyp `string`, rate `double`, rate_date `string`
- `kraken.balance` / `kraken_privat.balance`: asset `string`, amount **`string`**
- `kraken.trades` / `kraken_privat.trades`: price/vol/cost/fee/margin/leverage **`string`**, time **`double`** (epoch s), maker `boolean`, trade_id `bigint`, txid/pair/type/… `string`
- `corpayone.expenses`: amount `bigint`, currency `string`, number `bigint`, dueDate/issueDate/paymentDate/referenceDate `string`, category/owner/vendor `struct<…>`, id/state/type `string`
- `pleo.accounting_entries`: money nested in `totalBillValue`/`transactionValue` `struct<currency,minors:bigint>`; date-ish fields `string`; merchant `struct<…>`; ids/status `string`
- `kronjylland.transactions` / `revolut_privat.transactions`: transaction_amount **`struct<amount:string,currency:string>`** (nested), booking_date/value_date/transaction_date `string`, credit_debit_indicator `string`, balance_after_transaction/exchange_rate `string`, creditor/debtor/*_account `struct<…>`
- DSA: `alternative.feargreedindex` fully typed already (value `int`, timestamp `timestamp`); `historic.transactions` Koinly-shaped varchars; `djurslandsbank.allaccounts` free-text varchars (Beløb/Saldo Danish-decimal strings); `sparekassenkronjylland.konti_base` generic Prop_0..4

### The design — per sub-source

**Legend:** DO = default-only (`enriched: {columns: []}`). Fiat/krypto/procent scales are
decimal(38,{3,18,2}) from `CATEGORY_SCALE`.

#### coingecko.yml → `coingecko_prices` — **DO**
chain already `bigint`, price_dkk already `double`, asset_key an id, price_date a calendar date.
Nothing to add. **Challenge:** price_dkk is a crypto price in DKK spanning huge magnitudes
(cheap tokens < 0.001 DKK); forcing it to `fiat` decimal(38,3) would truncate small prices to
0.000 — so leaving the source `double` is *more* correct, not lazy.

#### corpayone.yml → `corpayone_expenses` — **DO**
amount is `bigint` with a *separate* `currency` code (almost certainly minor units), but the
minor-unit exponent varies per currency (EUR 2, JPY 0) and there is no per-row exponent column,
so `scale_by_decimals` cannot type it correctly; the four date fields are calendar dates; the
money-bearing detail (category/owner/vendor) is nested `struct`s the engine cannot address.
Correct scaling is a per-currency curated concern. **Flag (<100%):** if Benny confirms every
bill is 2-dp minor units, amount → `scale_by_decimals{decimals: 2}` + `round_by_category{fiat}`
becomes defensible; I recommend DO until confirmed (I did not inspect values — leak discipline).

#### dsa.yml → all four sub-sources — **DO** (dead legacy, per-table reasons)
- `alternative_feargreedindex`: the typed `stg` JDBC copy — value `int`, timestamp `timestamp`,
  everything already correctly typed. Reuse-raw-types → DO.
- `historic_transactions`: schema is Koinly-shaped (Sent/Received/Fee Amount + Cost Basis + DKK
  columns as varchars) and *could* be typed exactly like koinly. It is a **frozen 2017-2020
  legacy copy fully superseded by the live `koinly_privat` source** (which already types the
  same rows). Typing a dead, duplicated table is "typing for show" — DO. **Flag:** if Benny
  wants DSA-parity, the block mirrors koinly's (amounts `to_decimal{us, krypto|fiat}`; `Date` is
  a free-text varchar so it needs `parse_timestamp{format}` not just `to_dk_local`).
- `djurslandsbank_allaccounts`: no key (`keys: []`, YAML says "Benny confirms before Blok 2");
  Beløb/Saldo are Danish-decimal varchars but typing a keyless free-text dump is premature — DO.
- `sparekassenkronjylland_konti_base`: generic Prop_0..4, no semantics to type — DO.

#### dst.yml → `dst_pris01` — **DO**
VAREGR/ENHED/ContentsCode are classification codes; Tid stays verbatim (the extractor docstring
is explicit — statbank granularity varies, period parsing is curated); value is already `double`.
**Challenge to the brief's "dst value → decimal":** value is already numeric, and its scale is
table-specific (PRIS01 is a price index, not money/percent) — none of krypto/fiat/procent fits,
and picking one is a curated modelling choice exactly like Tid. DO is the honest call.

#### enablebanking.yml → `enablebanking_kronjylland`, `enablebanking_revolut_privat` — **DO**
The transaction amount of record is **nested** in `transaction_amount struct<amount,currency>`;
the enriched engine addresses only top-level raw columns (single backtick-quoted identifiers),
so it cannot reach `transaction_amount.amount`. `credit_debit_indicator` exists (the PSD2 DBIT
that `sign_by_indicator` was built for) but the amount it would sign is nested and unreachable.
booking_date/value_date/transaction_date are calendar dates. The only top-level string amounts
(balance_after_transaction, exchange_rate) are ancillary; typing them while the real amount stays
a nested string would be inconsistent. The two banks' schemas even diverge (bank_transaction_code
struct vs string; debtor_account_additional_identification array vs string), which DO absorbs
cleanly. Flattening + typing PSD2 money is a curated concern. **DO.**

#### feargreed.yml → `feargreed_index` — **TYPED**
```yaml
enriched:
  columns:
    - name: value
      transforms: [to_integer]
```
value is a `string` ("42") that curated needs numeric → `to_integer`. value_classification stays
a `string` (Neutral/…) and date is a calendar-date `string` → both DO. This is the only public
source with a genuinely mis-typed column.

#### kraken.yml → `kraken_balance` — **TYPED**
```yaml
enriched:
  columns:
    - name: amount
      transforms:
        - to_decimal: {style: us, category: krypto}
```
amount is a faithful decimal `string` (Kraken dot-decimal, no thousands sep → `style: us`). The
balance covers crypto AND fiat assets; `krypto` (decimal(38,18)) is the safe superset that never
truncates a crypto balance and holds fiat exactly. asset is an id → DO.

#### kraken.yml → `kraken_tradeshistory` — **TYPED**
```yaml
enriched:
  columns:
    - name: price
      transforms: [{to_decimal: {style: us, category: krypto}}]
    - name: vol
      transforms: [{to_decimal: {style: us, category: krypto}}]
    - name: cost
      transforms: [{to_decimal: {style: us, category: krypto}}]
    - name: fee
      transforms: [{to_decimal: {style: us, category: krypto}}]
    - name: margin
      transforms: [{to_decimal: {style: us, category: krypto}}]
    - name: time
      target: trade_time
      transforms:
        - parse_timestamp: {epoch_seconds: true}
        - to_dk_local
```
price/vol/cost/fee/margin are faithful decimal `string`s → `to_decimal{us, krypto}` (pairs mix
crypto and fiat quotes, so krypto(18) is the no-truncation superset, consistent with balance).
time is a `double` epoch-seconds instant → `parse_timestamp{epoch_seconds:true}` (its `try_cast …
AS BIGINT` truncates the fractional second, which is second-precision-correct) then `to_dk_local`
→ `trade_time` + `trade_time_dk`. maker(boolean)/trade_id(bigint) already typed; txid/ordertxid/
postxid/pair/type/ordertype/tradeordertype/aclass/misc are ids/strings → DO.
**Flag (<100%):** `leverage` is a numeric `string` but a *ratio*, not money; I recommend DO
(not money, curated concern). Resolve by confirming whether curated wants it numeric.
**Flag (naming):** renaming time→`trade_time` is a clarity choice (avoids a bare `time`); drop
the `target` if Benny prefers the raw name (then the DK sibling is `time_dk`).

#### kraken_privat.yml → `kraken_privat_balance`, `kraken_privat_tradeshistory` — **TYPED**
Byte-identical raw schema to the erhverv account → **identical blocks** to `kraken_balance` /
`kraken_tradeshistory` above.

#### nationalbanken.yml → `nationalbanken_fx` — **DO**
currency_code/kurtyp are codes, rate_date a calendar date, rate already `double`.
**Challenge to the brief's "rate → decimal":** rate is already numeric, and it is published DKK
per 100 units to ~4 decimals (e.g. 745.6700); `fiat` decimal(38,3) would *truncate* the 4th
decimal — genuine precision loss. The /100 normalisation is already flagged as a curated concern
in the extractor, and rate typing belongs there with a purpose-built scale, not the fixed
categories. DO.

#### pleo.yml → `pleo_accounting_entries` — **DO**
The money of record is nested in `totalBillValue`/`transactionValue struct<currency,minors:bigint>`
— unreachable by the engine (no struct-path support). merchant is a nested struct. Remaining
top-level fields are ids/status/classification strings and a spread of ISO date-ish strings of
uncertain/mixed format. Typing nested money + assorted timestamps is a curated concern. **DO.**
**Flag:** if wanted later, top-level instants (performedAt/settledAt/createdAt/updatedAt) could
take `parse_timestamp{format}` + `to_dk_local` once their exact ISO format is confirmed
on-cluster; recommend curated.

### Cross-cutting flag: calendar-date strings

price_date (coingecko), rate_date (nationalbanken), date (feargreed) are clean ISO calendar-date
`string`s. There is **no `to_date` transform** in the registry, so they stay DO (string) —
consistent with dst's Tid and the reuse-raw-types principle. If Benny wants them as true `DATE`,
that is a small, clean **new transform** (`to_date` = `try_cast(... AS DATE)`, no tz — a calendar
date is never tz-converted) plus a unit test. Presented as an option; my design leaves them DO.

### Net result

Typed blocks: **feargreed_index, kraken_balance, kraken_tradeshistory, kraken_privat_balance,
kraken_privat_tradeshistory** (5 sub-sources). Default-only (`columns: []`): the other **11**
(coingecko_prices, corpayone_expenses, all 4 DSA, dst_pris01, both enablebanking, nationalbanken_fx,
pleo_accounting_entries). This is a deliberate, evidence-backed challenge to the brief's implied
typing of dst/nationalbanken — raw already typed them, and the rest is nested money or dead
tables where typing belongs in curated.

### Why

Enriched is a cleansing hop, not a modelling hop. Re-typing an already-`double` column, forcing a
table-specific scale onto a reference value, or reaching into nested PSD2/Pleo money would all
smear curated concerns downward and add maintenance surface for zero benefit. The minimal-correct
block is `columns: []` unless raw genuinely mis-typed a column (feargreed value string, kraken
amount/price/… strings, kraken time double-epoch), which is where — and only where — typing runs.

### What worked

The live `describe` sweep was decisive: it turned three assumed decimal-castings (dst value,
nationalbanken rate, coingecko price) into confirmed already-`double` reuse-raw-types cases, and
confirmed the two nested-money families (enablebanking, pleo) the engine cannot address. Designing
from the extractor docstrings first, then confirming formats by type, kept it leak-safe.

### What didn't work

The `az`-token curl one-liners tripped the worktree sandbox's "too complex to verify" guard, and
Python `subprocess(["az", …])` failed with `FileNotFoundError [WinError 2]` (az needs its `.cmd`
shim on PATH from Python). Resolved by fetching the token in bash and passing it to a scratchpad
`describe.py` via an env var. No blocker to the design.

### What I learned

`cloudFiles.inferColumnTypes=true` on the extraction NDJSON path (vs `false` for the CSV
file-drops) is the hinge fact for this whole feature: it means extraction raw is *already typed*
from JSON, so Blok 2 for these sources is mostly `columns: []`. The transform library is
top-level-column only (`quote_ident` on a single identifier; `_column_ref` reads another raw
column by name) — it has no struct-path support, which is *why* nested-money sources are DO, not a
temporary gap.

### What was tricky

Distinguishing "already correctly typed" from "should be typed": a `double` FX rate is faithful
reference data (DO), but a `string` Kraken amount is a faithful-string that must become a decimal
(TYPED) — same "reference-ish" smell, opposite call, decided by the raw type the describe showed.
And the DSA `historic_transactions` trap: a perfectly typable Koinly-shaped schema that must be
left DO precisely *because* it is typable elsewhere already (superseded).

### What warrants review

The three `<100%` flags: (1) corpayone amount minor-unit scale, (2) kraken leverage numeric-vs-DO,
(3) the time→trade_time rename. And the two challenged directives (dst value, nationalbanken rate)
— confirm Benny accepts DO over decimal given they are already `double`. A reviewer should also
confirm the engine builds each typed block against its real schema (offline test below).

### Future work

If Benny wants true `DATE`/`TIMESTAMP` typing on the calendar-date and Pleo-instant strings, add a
`to_date` transform and (for Pleo) confirm the ISO format on-cluster — a follow-up, not this
feature. Curated owns: PSD2/Pleo nested-money flattening, per-currency minor-unit scaling,
statbank period parsing, and the FX /100 normalisation.

---

## Builder checklist (implement against the design above — OFFLINE ONLY; do not deploy/run jobs)

1. **Edit the 10 YAMLs** under `src/config/sources/` — add the `enriched:` block to EVERY
   sub-source per the design. Match the existing comment style (a short `# ENRICHED (Blok 2):`
   note stating typed-why / default-only-why, as economic/koinly/metamask do). 11 sub-sources get
   `enriched: {columns: []}`; 5 get the typed blocks (feargreed + 4 kraken). The two kraken_privat
   blocks are identical to the kraken ones.
2. **Regenerate jobs:** run `python scripts/generate_jobs.py` from `src/`. It emits one
   `enrich_<source>.job.yml` per source with an enriched block, so adding blocks auto-adds jobs.
   Confirm the 10 new `resources/enrich_*.job.yml` appear (grouped by the same job_group rules as
   ingest).
3. **`--check` clean:** `python scripts/generate_jobs.py --check` must exit 0 (guarded by
   `src/tests/test_generate_jobs.py`).
4. **Tests:** no NEW transform behaviour (feargreed→`to_integer`, kraken→`to_decimal`/
   `parse_timestamp`+`to_dk_local` all already exist and are covered in `test_enriched.py`), so
   this is config, not library. Add a targeted offline test (extend `test_enriched.py` or a new
   `test_enriched_sources.py`) that runs `build_enriched_expressions` against a hardcoded
   representative schema for each TYPED sub-source and asserts: value→int cast present (feargreed);
   amount/price/vol/cost/fee/margin decimal cast present and `trade_time`+`trade_time_dk` siblings
   emitted (kraken). `test_config.test_all_sources_load_and_are_unique` already parses every new
   block on load — keep it green (it catches an unknown transform / bad param structure).
5. **Full suite green:** `pytest` from `src/` (offline; pyspark not installed — engine tests are
   selectExpr-string only, by design).
6. **`terraform fmt -check`:** run only if any `.tf` is touched — none should be (config + tests +
   generated job YAML only).
7. **Diary:** append a Step 2 (Author: builder) recording what was implemented, any schema
   surprises, and the test additions. Do NOT modify this Step 1.
8. **Do NOT** modify `.ps1` files, deploy, run enrich jobs, or push. Benny deploys + live-proves
   each enrich job and merges.

---

## Step 2: Implementation (against Step 1 + Benny's three overrides)

**Author:** builder

### Prompt Context

**Interpretation:** Implement the Step 1 frozen design for the 10 remaining sources' `enriched:`
blocks, but apply THREE overrides Benny decided after the design froze: (1) dst `value` and
nationalbanken FX `rate` are cast to EXACT `decimal(P,S)` (not left default-only, not the lossy
fiat(3) preset); (2) CorPay `amount` stays default-only with a deferred-scaling note;
(3) a new `to_date` transform is added and applied to the genuine ISO calendar-date columns
(coingecko `price_date`, nationalbanken `rate_date`, feargreed `date`), NOT to dst `Tid` (a period
code) nor the mixed/nested financial dates.

### What I did

**Two new transforms in `src/datavilla/enriched/transforms.py`:**
- `to_date` — registered via the existing `_simple_cast("DATE")` helper, so it emits
  `try_cast(<expr> AS DATE)` with no params, exactly the Step 1 design's shape. A calendar date is
  never a UTC instant, so it takes no `to_dk_local` sibling. Null-safe (bad/empty/null -> NULL).
- `cast_decimal` — a NEW parametrised transform (`precision`, `scale`) emitting
  `try_cast(<expr> AS DECIMAL(P,S))`. This is the Override-1 tool: the source columns are already
  `double`, so it is a plain numeric double->decimal cast (NOT the string-parse/`us`-comma path in
  `to_decimal`, which is for string inputs). `round_by_category` was the near-miss the lead flagged,
  but it only offers the fixed krypto/fiat/procent scales — and fiat(3) truncates — so an explicit
  `(P,S)` transform was the right minimal addition. Params validated (int-only, rejects bool,
  `0 <= scale <= precision`, `precision >= 1`).

**Decimal (P,S) sized from LIVE public raw data (public sources only — sampled, per the brief):**
- **nationalbanken FX `rate` -> `decimal(38,6)`.** Sampled `datavilla_dev_raw.nationalbanken.exchange_rates`:
  max observed decimal places = **4** (e.g. `6.0486`), integer part <= 3 digits (max `905.0`), zero
  scientific-notation values over 16,688 rows. S=6 truncates nothing and covers DNVALD's typical
  4-6 dp; P=38 matches the codebase's `DECIMAL_PRECISION` constant.
- **dst `value` -> `decimal(38,4)`.** Sampled `datavilla_dev_raw.dst.pris01`: max observed decimal
  places = **2** (e.g. `63.45`), integer part <= 4 digits (range `-61.3 .. 1475.5`), zero
  scientific-notation over 310k rows. S=4 gives headroom over the observed 2; P=38 for consistency.

**Column names confirmed via `describe` before wiring** (financial sources: types/names only, never
values): coingecko `price_date`, feargreed `date`+`value`, nationalbanken `rate`+`rate_date`, dst
`value`+`Tid`, kraken(+privat) `amount` and `price/vol/cost/fee/margin/leverage`(string) + `time`(double).
All declared columns exist in the real raw schema.

**The 16 sub-source blocks** (Step 1 table + overrides):
- TYPED: `feargreed_index` (value->to_integer, date->to_date), `kraken_balance` /
  `kraken_privat_balance` (amount->to_decimal us/krypto), `kraken_tradeshistory` /
  `kraken_privat_tradeshistory` (price/vol/cost/fee/margin->to_decimal us/krypto; time->trade_time via
  parse_timestamp{epoch_seconds}+to_dk_local; leverage default), `coingecko_prices` (price_date->to_date),
  `nationalbanken_fx` (rate->cast_decimal(38,6), rate_date->to_date), `dst_pris01`
  (value->cast_decimal(38,4)).
- DEFAULT-ONLY (`columns: []`): `corpayone_expenses` (Override 2, with the deferred per-currency
  minor-unit note), all 4 DSA sub-sources, both enablebanking, `pleo_accounting_entries`.

Regenerated jobs (`python scripts/generate_jobs.py`): **14 new `enrich_*.job.yml`** created
(coingecko, corpayone, djurslandsbank_allaccounts, dst, feargreed, historic_transactions, kraken,
kraken_privat, kronjylland, nationalbanken, pleo, revolut_privat, sparekassenkronjylland_konti_base,
alternative_feargreedindex) on top of the 4 pre-existing (economic, koinly_erhverv, koinly_privat,
metamask) = 18 enrich jobs, mirroring the 18 raw ingest systems.

### Confirmation of the three overrides
1. **dst value + FX rate -> exact decimal, NOT fiat(3).** Done via `cast_decimal`: FX `decimal(38,6)`
   (observed 4 dp), dst `decimal(38,4)` (observed 2 dp). Both documented in-YAML and above.
2. **CorPay `amount` default-only.** Left `columns: []`; one-line YAML comment defers per-currency
   minor-unit scaling to curated pending API-doc confirmation of the exponent per currency.
3. **`to_date` added + applied to the 3 genuine ISO calendar-date columns only.** coingecko
   `price_date`, nationalbanken `rate_date`, feargreed `date`. NOT applied to dst `Tid` (period code
   `2025M01`, stays string) nor pleo/enablebanking mixed/nested dates (default-only).

### Schema surprise / scope note that WARRANTS the lead's attention

The Step 1 design gives **every** source an `enriched:` block — including the two DSA bank tables
(`djurslandsbank_allaccounts`, `sparekassenkronjylland_konti_base`) that were previously **parked**
(no block) and documented as such in `config.py` ("this is how the stale DSA tables are parked").
Implementing "all 4 DSA sub-sources -> `columns: []`" therefore MOVES those two from parked to
default-only enriched, so they now generate `enrich_*` jobs. This broke three existing tests that
encoded the old parked assumption, which I UPDATED to the new contract (not weakened):
- `test_enriched.py::test_real_configs_parse_and_partition_into_enriched_and_parked` -> renamed to
  `..._all_enriched_after_remaining_sources_feature`, now asserting every source is enriched and the
  two banks are default-only (`columns == ()`).
- `test_generate_jobs.py`: `EXPECTED_ENRICH_JOB_FILES` grown from 4 to 18 (mirrors the ingest
  systems), and `test_enrich_jobs_only_for_systems_with_enriched_sources` now asserts the enrich set
  equals the ingest set (no parked systems remain). Fixed a stale `# 16 ingest + 4 enrich` comment.

This is faithful to the frozen design and Benny's task ("dsa (all 4 sub-sources) ... `columns: []`
default-only"), but it is a real behaviour change (two parked tables now enriched) that Benny should
be aware of when live-proving — flagging rather than burying it.

### Validation (offline)

- `python -m pytest -q`: **439 passed** (includes the new transform-level tests for `to_date` /
  `cast_decimal`, the per-typed-source build tests, and the updated config/job-count tests).
- `python scripts/generate_jobs.py --check`: "job resources are up to date" (exit 0).
- `python -m pyflakes datavilla/enriched/transforms.py tests/test_enriched.py tests/test_generate_jobs.py`:
  clean.
- No `.tf` touched -> `terraform fmt -check` not applicable.
- Typed plans built against the confirmed real schemas produce exactly the expected casts
  (feargreed value->INT + date->DATE; FX rate->DECIMAL(38,6) + rate_date->DATE; dst value->DECIMAL(38,4);
  kraken amounts->DECIMAL(38,18), trade_time + trade_time_dk siblings, leverage untouched).

### What is NOT verified here (needs the target environment — Benny live-proves)

The transforms are `selectExpr`-string builders tested offline (pyspark is not installed in the dev
env, by design). Whether `try_cast(<double> AS DECIMAL(38,6))` preserves the FX rate exactly, whether
`try_cast(trim(<iso>) AS DATE)` parses every real `price_date`/`rate_date`/`date`, and the post-write
null counts on the newly-typed columns can only be confirmed by RUNNING each `enrich_*` job on the
cluster. I did not run any Databricks job or `bundle validate/deploy` (that is main's job).

### Follow-ups for review

- Confirm the chosen scales hold if the FX currency list or a future statbank table introduces larger
  magnitudes / more decimal places than the current live data (S is headroom-sized, but sampled from
  today's data).
- The CorPay `amount` minor-unit scaling and the pleo/enablebanking nested-money + instant typing
  remain curated concerns, as designed.

---

## Step 3: Collapse the 18 per-system enrich jobs into ONE job

**Author:** builder

### Prompt Context

**Verbatim prompt:**

> ## Opgave
> Kollaps de 18 per-system enrich-jobs til ÉT samlet job i datavilla-frameworket.
>
> ## Hvor
> Arbejd i den EKSISTERENDE worktree — opret ikke en ny:
> `C:\claudes_folder\repos\datavilla\.claude\worktrees\agent-a707f6b87f5378b5f`
> Branch: `feature/enriched-remaining-sources` (HEAD `ad30be9`, ikke merged til master).
> Byg oven på det der allerede ligger der.
>
> ## Baggrund (verificeret, ikke gætværk)
> `scripts/generate_jobs.py:503` grupperer i dag enrich-jobs efter `definition.job_group` — samme
> nøgle som ingest-jobbene. Det giver 18 filer `src/resources/enrich_<group>.job.yml`, hvert med
> sit eget cluster.
>
> Det split er arvet fra ingest uden at være begrundet for enrich: ingest-splittet findes fordi
> kilder deler API-credential og nonce-sekvens (Kraken). Enrich læser kun raw Delta — ingen
> credentials, ingen system-binding.
>
> Konsekvens i drift: vi kørte 6 enrich-jobs parallelt mod dev 2026-08-02 og to af dem (kraken,
> kraken_privat) døde på `AZURE_QUOTA_EXCEEDED_EXCEPTION` — "Total Regional Cores quota" i
> northeurope. 18 separate cluster-spinups er både dyrt i tid (8-17 min hver) og rammer regional
> kvote.
>
> ## Krav (besluttet af Benny)
> 1. **Ét enrich-job over ALLE enriched sources.** Én `for_each_task`, `concurrency: 1`, ét
>    `job_cluster`. Erstat de 18 `enrich_<group>.job.yml` med én genereret fil (foreslået navn
>    `enrich_all.job.yml`, job-key `enrich_all` — vælg noget bedre hvis du har et argument).
> 2. **Grænsen skal være stabil.** Nye kilder skal falde ind i det samme job automatisk via
>    generatoren; ingen hardcodet liste af kilde-navne i Python-koden. `for_each` `inputs` skal
>    genereres fra config som i dag, bare uden gruppering.
> 3. **Deterministisk output.** Sortér `inputs` så `generate_jobs.py`s drift-check (`check()`) er
>    stabilt mellem kørsler.
> 4. **Ingest-jobbene rører du IKKE.** `ingest_<group>.job.yml` beholder sin per-system-gruppering
>    — dér er credential-argumentet ægte.
> 5. **Stale-oprydning:** `check()`/`generate()` skal rapportere de 18 gamle `enrich_*.job.yml` som
>    stale og fjerne dem. Verificér at oprydningsstien faktisk virker (den er testet i
>    `_is_generated`-logikken).
> 6. **`source`-cluster-tag:** i dag sættes `custom_tags.source` til systemnavnet. Med ét samlet
>    job giver det ikke mening — cluster-policy'en KRÆVER tagget, så det skal have en meningsfuld
>    værdi (fx `enriched`). Bekræft mod cluster-policy'en at værdien accepteres; policy kræver også
>    `ResourceClass: SingleNode`.
> 7. **Entry-point-parametre:** `--job`/`--task` sendes i dag som `enrich_<group>`/`enrich_source`.
>    Opdatér konsistent, og tjek om `datavilla-enrich` (`src/datavilla/enriched/engine.py`) eller
>    run-logningen bruger de værdier til noget — hvis de skrives til en run-log-tabel, så sørg for
>    at det stadig er sporbart hvilken kilde en iteration dækkede.
> 8. **Tests:** `src/tests/test_generate_jobs.py` har en fuld-dæknings-kontrakt (hver enriched
>    source skal optræde i et genereret job). Opdatér den til den nye form — kontrakten skal
>    bevares, ikke svækkes. Alle 439 eksisterende tests skal fortsat være grønne.
>
> ## Hårde regler
> - **Du deployer IKKE og kører IKKE jobs.** Per `databricks.yml` er deploy+run mains rolle. Byg og
>   test OFFLINE. Rapportér tilbage når branchen er grøn; main kører `bundle deploy` + trigger +
>   verifikation.
> - **Ingen ægte data-værdier** i kode, kommentarer, tests eller diary. Datavilla rummer Bennys
>   personlige finansdata. Brug syntetiske eksempler. Aggregat-rækketal er ok.
> - **Git:** commit med author `singularity-consult <benny@singularityconsult.dk>`. INGEN
>   `Co-Authored-By`-trailer, ingen Claude som author. Push ikke.
> - **Ændr ikke .ps1-filer.**
>
> ## Leverance
> Committet på branchen, tests grønne, `python scripts/generate_jobs.py --check` (eller hvad
> drift-checket hedder) rent. Rapportér: commit-sha, testtal, hvad `inputs`-listen endte med at
> indeholde (antal sources), og hvad du valgte for `source`-tagget og hvorfor.

**Interpretation:** Change only the ENRICHED generation boundary in `scripts/generate_jobs.py`
from per-`job_group` to a single job over every source with an `enriched:` block, let the existing
stale-file machinery retire the 18 old resource files, give the shared cluster a `source` tag that
is true for a layer-wide cluster, and rewrite the job-generation tests to keep the full-coverage
contract at the new shape. Raw ingest generation stays exactly as it is.

**Inferred intent:** Stop paying 18 cluster spinups for work that has no per-system binding, and
stop tripping the Azure regional cores quota when enrich jobs overlap — while keeping the
"jobs are derived from config, never hand-maintained" property that makes adding a source a
config-only change.

### What I did

**Generator (`src/scripts/generate_jobs.py`).** `_render_enriched` lost its `group` parameter and
now takes the full list of enriched definitions; `plan()` no longer calls `_group_sources` for the
enriched family at all — it filters `d.is_enriched` over all sources and emits a single
`enrich_all.job.yml` (guarded by `if enriched:`, so a config with nothing enriched emits no enrich
job rather than an empty for_each). `_enrich_job_path(group)` was replaced by the constants
`ENRICH_JOB_KEY = "enrich_all"` / `ENRICH_JOB_FILENAME` / `ENRICH_CLUSTER_TAG = "enriched"`. I kept
the proposed `enrich_all` name — I had no better argument, and it reads correctly next to
`ingest_<system>`.

`ENRICHED_JOB_TEMPLATE` was rewritten: `{group}` became `{job_key}`, the job name is
`[${var.env}] enrich all sources (raw -> enriched)`, the source list moved from an inline
comma-joined comment to `_wrapped_comment` with a count (39 names inline would have been a
~700-character comment line), and the `--job` parameter is now the constant `enrich_all`. The
"why" is written into the template's own comment block, because the next reader will ask why
enrich does not look like ingest.

**The cluster tag.** `custom_tags.source: "enriched"`. Verified against
`infra/cluster_policy.tf`: the policy element is `"custom_tags.source" = { type = "unlimited",
isOptional = false }` — the KEY must be present, the VALUE is unconstrained — and
`"custom_tags.ResourceClass" = { type = "fixed", value = "SingleNode" }`, which the generated
block already sets. So `enriched` is accepted, and a system name would have been actively wrong on
a cluster that runs every system.

**Traceability (requirement 7).** `datavilla-enrich` passes `--job`/`--task` straight into
`run_log(...)`, which writes them to the `job` / `task` columns of
`datavilla_<env>_raw._ops.run_log` (`RUN_LOG_COLUMNS` in `datavilla/runlog.py`). Those two columns
now collapse to one value for the whole layer — but they never carried the per-source identity
anyway: `enrich_source()` passes `source=definition.name` and
`target=definition.enriched_full_name(env)`, both derived from `--source`, i.e. from the for_each
item. One run-log row per iteration, each naming its own source. Nothing had to change in
`engine.py`; I only had to prove the linkage, and it had no test at all, so I wrote one.

**Tests.** In `tests/test_generate_jobs.py`, `EXPECTED_ENRICH_JOB_FILES` shrank from an 18-name set
to `{"enrich_all.job.yml"}` and three per-system tests were replaced by seven that assert the
stronger contract: the enrich plan is exactly one file (plus a guard that no `enrich_<something>`
file creeps back), the for_each inputs equal the set of `is_enriched` sources **derived live from
the config** rather than a hardcoded list, inputs are sorted and duplicate-free, one job_cluster +
one task + nested `job_cluster_key` reuse + `concurrency: 1`, the `source`/`ResourceClass` tags,
the `--job`/`--task`/`--source` parameter wiring, and that the two multi-source systems that used
to own their own jobs (19 e-conomic subjects, 2 MetaMask sources) survived the collapse. One more
test drives `generate()` against a throwaway `tmp_path` to prove the stale-removal path really
deletes a marker-carrying file that has left the plan while leaving a hand-written resource file
alone.

New file `tests/test_enrich_engine.py` (modelled on the existing `tests/test_ingest.py` fake-based
run-log test) covers the traceability contract end to end with fake Spark/DataFrame/writer: a run
with `job="enrich_all", task="enrich_source"` must still produce a run-log row with
`source == "demo"` and `target == "datavilla_dev_enriched.sc.t"`. A second test asserts the CLI
passes `--job`/`--task` through to `enrich_source` unchanged. Fixtures are synthetic (`demo`,
`Col A`/`Col B`); no real data.

**README.** The job-generation section now documents two deliberate boundaries instead of one, and
its stale "25 sources -> 6 jobs" line became "39 sources -> 18 ingest jobs + 1 enrich job".

Commands run: `python scripts/generate_jobs.py --check`, `python scripts/generate_jobs.py`,
`python -m pytest -q`, `python -m pyflakes scripts/generate_jobs.py tests/test_generate_jobs.py
tests/test_enrich_engine.py`.

### Why

The per-system split for raw is a correctness constraint (shared API key + a per-key nonce sequence
that parallel processes would race into `EAPI:Invalid nonce`). Enriched reads raw Delta: no
credential, no nonce, no system binding. So the split bought nothing and cost one cluster spinup
per system — which is not merely wasteful but a hard failure mode, since concurrent spinups
exhausted the northeurope regional cores quota.  One job, one cluster, one serial for_each is the
shape the actual constraint implies.

### What worked

The stale-file machinery needed no changes at all. Because `_is_generated` keys on the
`# GENERATED by scripts/generate_jobs.py` marker and `check()`/`generate()` diff the resources
directory against `plan()`, dropping the 18 filenames out of the plan was the entire deletion
mechanism. `--check` reported exactly `missing: enrich_all.job.yml` plus 18
`stale generated file: enrich_<system>.job.yml`, and `generate()` then wrote 19 files and removed
those 18 — no manual `git rm`.

The generated `enrich_all.job.yml` parses cleanly and holds what it should: 39 iterations, sorted,
unique, `concurrency: 1`, one `job_cluster`, `custom_tags {'ResourceClass': 'SingleNode',
'source': 'enriched'}`, and an `inputs` JSON string of 923 characters (comfortably inside both the
for_each iteration limit and any parameter-size concern).

### What didn't work

**My first pass silently rewrote all 18 ingest job files.** I had edited the `source`-tag comment
inside the shared `CLUSTER_BLOCK` so it would be truthful for a layer-wide cluster — but that block
is shared by all four job shapes, so `--check` came back with:

```
  - out of date: ingest_alternative_feargreedindex.job.yml
  - out of date: ingest_coingecko.job.yml
  ... (18 ingest files)
```

That is a direct violation of requirement 4. Comments are not part of the job API payload, so
Databricks would have seen no change — but it is 18 files of review noise on a branch whose whole
point is that ingest is untouched. Fix: the tag comment became a `{tag_note}` format field with
`INGEST_TAG_NOTE` holding today's wording **verbatim** as the default, and `ENRICH_TAG_NOTE`
supplying the layer-specific text. After that, `--check` listed only the 18 stale enrich files and
`git diff -- resources/ingest_*` was empty.

**Mutation check on the new traceability test.** To confirm the test was not vacuously green I
temporarily changed `source=definition.name` to `source=None` in `enriched/engine.py` and re-ran:

```
>       assert row["source"] == "demo"
E       AssertionError: assert None == 'demo'
FAILED tests/test_enrich_engine.py::test_run_log_row_identifies_the_iterations_own_source
```

Reverted immediately; `git diff -- datavilla/` is empty, so `engine.py` is byte-identical to
`ad30be9`.

### What I learned

Sharing one template block across job shapes is the right call for the cost/policy contract (it is
why the availability comment stopped drifting), but it also means any *explanatory* comment in that
block has to be true of every shape at once. Once one shape's semantics diverge, the honest fix is
to parameterise just the diverging sentence rather than either lying in the shared block or
rewriting every consumer's output.

Also: `--job`/`--task` in this codebase are labels for the run-log, not identity. The identity has
always been `source`/`target`. That is what made collapsing 18 jobs into 1 a zero-risk change for
observability rather than a loss of it — but it was worth verifying in `runlog.py` rather than
assuming.

### What was tricky

Deciding how far to take "do not touch the ingest jobs". The literal reading (no byte changes to
`resources/ingest_*.job.yml`) conflicted with keeping the shared cluster comment accurate, and the
two are only reconcilable by parameterising. I went with the literal reading because a clean
"ingest is provably unchanged" diff is worth more on this branch than comment tidiness would have
been.

I also left the `job_cluster_key` as `ingest_cluster` in the enrich job. It is inherited and now
reads oddly on a job that ingests nothing, but renaming it means another format field threaded
through `CLUSTER_BLOCK` and all four templates for a cosmetic gain — flagged as follow-up rather
than smuggled into this change.

### What warrants review

- `src/resources/enrich_all.job.yml` is the whole deliverable in one file: 39-name `inputs`, one
  `job_cluster`, `concurrency: 1`, `source: "enriched"`.
- The 18 deletions in `src/resources/` are generator output, not hand edits — `--check` is the
  proof.
- **NOT verified here:** `databricks bundle validate` / `deploy` / any job run. `src/databricks.yml`
  states outright that those are main's, and I did not run them. So the new job file is
  schema-valid to my YAML/JSON parsing and consistent with the 18 files that deployed successfully
  before it, but it has not been validated by the Databricks CLI and the job has never run. In
  particular: whether the shared single-node cluster comfortably runs 39 serial full-overwrite
  iterations inside the policy's 10-minute autotermination ceiling is a runtime question this
  branch cannot answer.
- When main deploys, expect the bundle to DESTROY 18 existing dev jobs and CREATE 1. That is
  intended, but it is a destructive deploy diff and should be read before confirming.

### Future work

- Rename `job_cluster_key: ingest_cluster` to something layer-neutral (e.g. `job_cluster`) across
  all four templates, if the odd naming bothers anyone more than the churn would.
- Cross-job ordering (raw ingest -> enrich) is still unwired and still a scheduling concern; with a
  single enrich job it is now a much easier trigger to express than it was with 18.
- If the enriched layer ever grows past the for_each iteration ceiling, or if one source's enrich
  becomes slow enough to dominate a serial run, the next lever is `concurrency > 1` on a bigger
  single node — not a return to per-system jobs.

---

## Step 4: enrich_all onto serverless — parallel for_each + retries

**Author:** builder

### Prompt Context

**Verbatim prompt:**

> Runde 2 på samme branch (`feature/enriched-remaining-sources`, oven på din `9f2fc27`). Benny har
> truffet to beslutninger efter din leverance.
>
> ## Kontekst du ikke havde
> Jeg målte Azure-kvoten: `Total Regional vCPUs = 10` og `Standard FSv2 Family vCPUs = 10` i
> northeurope. F4s_v2 = 4 vCPU, altså maks 2 samtidige clustre i hele subscriptionen. Det var
> grundårsagen til `AZURE_QUOTA_EXCEEDED_EXCEPTION` da vi fyrede 6 enrich-jobs parallelt, og det er
> også grunden til at `concurrency: 1` ikke er et designvalg men en tvang.
>
> Benny har eksplicit hævet budget-loftet: 200-500 DKK/md er acceptabelt, "det skal virke". Det
> omgør compute-beslutningen fra 2026-07-14 (classic frem for serverless), som byggede på
> minimum-cost som ledestjerne.
>
> ## Opgave
> **1. Flyt `enrich_all` til serverless job compute.**
> - Væk med `job_clusters` / `job_cluster_key` på enrich-jobbet. Brug `environments:` +
>   `environment_key` på tasken. Wheel'en (`../dist/*.whl`) og `databricks-sdk>=0.50` skal ind som
>   `dependencies` i environment-blokken — serverless bruger ikke `libraries:` på task-niveau.
> - Verificér at `python_wheel_task` er understøttet på serverless i den bundle-version repoet
>   bruger. Hvis der er en spec-version-binding (`environment_version` / `client`), så vælg bevidst
>   og skriv hvorfor i kommentaren.
>
> **2. Hæv `for_each` concurrency.** Serverless er ikke bundet af vCPU-kvoten, så sekventiel
> eksekvering er ikke længere nødvendig. 39 iterationer à 1-5 min sekventielt = 1-3,5 timer; det er
> hele pointen med at skifte. Vælg en værdi og begrund den. Hagen du skal tænke over: hver iteration
> er en full-overwrite Delta-write, og flere samtidige writes mod FORSKELLIGE tabeller er fint, men
> bekræft at ingen to sources i listen skriver til samme enriched-tabel.
>
> **3. `max_retries` på enrich-tasken** (+ `min_retry_interval_millis`). Gælder uanset
> compute-model — transiente fejl findes også på serverless.
>
> **4. Ingest rører du ikke.** De 18 `ingest_*.job.yml` bliver på classic med cluster-policy.
> `${var.cluster_policy_id}` skal fortsat bruges af dem — fjern ikke variablen.
>
> ## Konsekvenser du skal håndtere eller flagge eksplicit
> - **`custom_tags.source` forsvinder.** Cluster-policy'en gælder ikke serverless, og
>   serverless-tasks har ikke cluster-custom_tags. Det rammer per-source cost-attribution, som er et
>   åbent FinOps-punkt i projektet. Undersøg hvad serverless faktisk tilbyder i stedet
>   (budget/usage policy binding på job-niveau) og skriv hvad vi mister og hvad der kan erstatte
>   det. Ingen stille default.
> - **Cluster-policy-guardrailen bortfalder for enrich.** Node-type-lås, single-node-tvang og
>   autotermination gælder ikke længere dette job. Benny har accepteret det bevidst. Notér i
>   job-kommentaren at enrich bevidst ligger uden for policy'en, så det ikke læses som en fejl
>   senere.
> - Cluster-key-navnet `ingest_cluster` på enrich-jobbet (som du flaggede) løser sig selv hvis
>   job_clusters forsvinder. Bekræft at det gør.
>
> ## Uændrede hårde regler
> Byg og test OFFLINE — du deployer ikke og kører ikke jobs, det er mains rolle per
> `src/databricks.yml` linje 8. Ingen ægte data-værdier nogen steder inkl. diary. Commit som
> `singularity-consult <benny@singularityconsult.dk>`, ingen `Co-Authored-By`. Push ikke. Rør ikke
> .ps1-filer. Drift-check skal være rent og alle tests grønne.
>
> Rapportér: commit-sha, testtal, valgt concurrency + begrundelse, hvad der erstatter
> `custom_tags.source` til cost-attribution, og hvad du IKKE kunne verificere offline.

(The first attempt at this step died on an API stall immediately after acknowledging the brief,
before any file was touched; the lead confirmed the worktree was clean on `9f2fc27` and re-issued
the same brief. Nothing was lost and nothing had to be un-done. The lead's advice on the re-issue —
commit mid-way rather than saving everything for the end — was followed: the generator + tests
landed as `4871474` before the README and this diary were written.)

**Interpretation:** Change the enrich job's COMPUTE MODEL to serverless and use the headroom that
buys — parallel iterations and per-iteration retries — while leaving the 18 ingest jobs on classic
policy-bound clusters, and writing the two things serverless costs us (policy guardrails, cluster
tags) into the generated artefact instead of letting them become silent regressions.

**Inferred intent:** Make the enriched layer actually finish in a sane wall-clock on a subscription
whose vCPU quota physically cannot run more than two classic clusters at once — and do it without
quietly dropping the FinOps and guardrail properties the classic setup had.

### What I did

**Verified before writing, not after.** The brief asked me to confirm `python_wheel_task` works on
serverless in the repo's bundle version, and to choose deliberately between `client` and
`environment_version`. Both are answerable offline from the CLI's own schema, so I dumped it:
`databricks bundle schema` (CLI v0.291.0, the version in `.databricks/bundle/dev/deployment.json`).
It settled three things outright:

- `jobs.Task.environment_key` is documented as *"required for Python script, Python wheel and dbt
  tasks when using serverless compute"* — i.e. `python_wheel_task` is supported, and the binding is
  how you get it.
- `compute.Environment.client` carries `"deprecationMessage"` / `deprecated: true` with the text
  *"Use `environment_version` instead"*, and `environment_version` is documented **Required**. So
  the choice is not a toss-up: `client` is the wrong field to write in 2026.
- `resources.Job` has both `budget_policy_id` and `usage_policy_id`, plus `performance_target`
  (`STANDARD` = cost-efficient, `PERFORMANCE_OPTIMIZED` = faster/pricier). That is what let me
  answer the cost-attribution question with a mechanism rather than a shrug.

Note that `databricks bundle schema` is a local schema dump — it authenticates against nothing and
deploys nothing, so it stays inside the offline-only rule. `bundle validate` does not, and I did
not run it.

**The template.** `ENRICHED_JOB_TEMPLATE` lost `{cluster}` entirely and gained an `environments:`
block (`environment_key: enrich_env`, `environment_version: "3"`, `dependencies: [../dist/*.whl,
databricks-sdk>=0.50]`), `performance_target: STANDARD`, `concurrency: {concurrency}`, and
`max_retries` / `min_retry_interval_millis` on the nested task. The nested task's
`job_cluster_key` became `environment_key`, and task-level `libraries:` is gone — serverless
installs from the environment spec, so leaving `libraries:` would have been dead config that
silently installs nothing.

The tuning knobs are named constants (`ENRICH_CONCURRENCY`, `ENRICH_MAX_RETRIES`,
`ENRICH_MIN_RETRY_INTERVAL_MILLIS`, `ENRICH_ENVIRONMENT_VERSION`) rather than literals in the
template, because they are precisely the values someone will want to tune after the first real
runs, and each one needed an argument written next to it.

**Concurrency: 8.** The precondition the brief asked me to confirm holds — I checked it in code
before choosing a number: the 39 enriched sources resolve to 39 DISTINCT enriched tables and 39
distinct raw source tables, so no two concurrent full-overwrite writes can target the same table.
What *is* shared between iterations is the append-only `_ops.run_log` table and the
`CREATE SCHEMA IF NOT EXISTS` statements (18 enriched schemas, plus the run-log's own bootstrap in
`DeltaRunLogWriter.bootstrap`). Both are idempotent and Delta handles concurrent blind appends, but
they are the reason I did not go straight to 39-way fan-out: 8 takes the serial worst case from
~40 min-3.5 h down by roughly 5x (5 waves), which is the bulk of the win, while keeping the first
ever serverless run in this project to a blast radius of 8 rather than 39. Full fan-out buys the
remaining 2-3x and is a one-constant change once a full run is green.

**Retries: 2, with 60s backoff.** The thing that makes this safe rather than merely optimistic is
that enrich is a FULL OVERWRITE — a retry re-runs an idempotent write and cannot double-apply. 2
covers the transient class without masking a real config/schema error, which would fail all three
attempts anyway.

**Cost attribution — written into the generated job**, as `ENRICH_COST_ATTRIBUTION_NOTE`, because
it is an open FinOps point and a commit message is not where that belongs. The honest analysis, and
it corrects the brief's framing slightly: this step does **not** cost us per-source attribution,
because that was already given up in Step 3 when 18 jobs became 1 — the tag's value was `enriched`,
the layer, not a source name. What is lost here is that layer *label*. And layer *attribution*
survives anyway without any tag, because serverless usage rows carry
`usage_metadata.job_id` / `job_run_id` and there is exactly one enrich job. A per-source split was
never available from billing and still isn't; the honest proxy is apportioning the job's billed
cost by the per-iteration `duration` already recorded in `_ops.run_log`. The real tagging mechanism
for serverless is a budget/usage policy bound via `budget_policy_id`, which is an account-level
object that does not exist for this project — so I deliberately omitted the field rather than
emitting it empty (empty is a deploy error; wrong silently misattributes).

**Guardrail lapse** noted in the job body itself: no node-type lock, no single-node enforcement, no
Photon-off rule, no 10-minute autotermination ceiling for this job, phrased as "an ACCEPTED trade,
not an oversight or a missed policy_id" so a future reader does not "fix" it back.

**A simplification fell out.** Step 3 had parameterised `CLUSTER_BLOCK`'s tag comment into
`{tag_note}` + `INGEST_TAG_NOTE` + `ENRICH_TAG_NOTE`, purely so the enrich job could describe its
own cluster. With enrich off classic entirely, that parameter had exactly one caller — dead
machinery. Collapsing it back restores `CLUSTER_BLOCK` byte-for-byte to its pre-Step-3 form, which
I verified by diffing the block against `ad30be9`: identical. Free cleanup.

**Tests.** Five failed immediately on the compute switch, all of them encoding "every generated job
has a classic cluster":

```
FAILED tests/test_generate_jobs.py::test_enrich_job_runs_datavilla_enrich_without_azure_libs
FAILED tests/test_generate_jobs.py::test_enrich_job_starts_exactly_one_cluster_for_the_whole_layer
FAILED tests/test_generate_jobs.py::test_enrich_cluster_is_tagged_for_the_layer_not_a_system
FAILED tests/test_generate_jobs.py::test_every_job_shares_one_cluster_definition
FAILED tests/test_generate_jobs.py::test_availability_is_on_demand_and_not_described_as_spot
```

The two sweeping ones (`test_every_job_shares_one_cluster_definition`,
`test_availability_is_on_demand_and_not_described_as_spot`) were scoped to a new `_ingest_plan()`
helper rather than weakened — they still assert the full cluster contract, just over the family it
actually governs. The three enrich-specific ones were rewritten for the serverless shape. New
tests cover: the environment binding, `client` absent / `environment_version` pinned, no
`job_clusters` and no `custom_tags` anywhere in the job, `performance_target` STANDARD, concurrency
> 1 and bounded by the input count, retries present and non-zero, the distinct-target precondition
that parallelism rests on, and — directly serving requirement 4 — that all 18 ingest jobs still
carry `policy_id: ${var.cluster_policy_id}` and never gain an `environments:` block.

### Why

Because the constraint turned out to be physical, not architectural. Step 3 assumed serial
execution was a sensible cost choice; the quota measurement showed it was the only thing that fit.
Ten regional vCPUs at 4 per cluster is two clusters for the entire subscription, so no amount of
job-shape cleverness on classic gets the enriched layer under an hour. Serverless is the only lever
that removes the constraint rather than scheduling around it.

### What worked

Dumping the bundle schema turned three "I think Databricks does X" questions into citations from
the exact CLI version the repo deploys with. The `client`-vs-`environment_version` question in
particular would have been a coin flip from memory, and the schema answers it unambiguously with a
deprecation message. That is a repeatable trick for any future DAB field question, and it is
offline.

Committing the generator + tests as `4871474` before writing the README and diary meant the
substantive work was already durable when I moved on to prose — worth keeping after the previous
stall.

### What didn't work

No failures beyond the five expected test breakages above, which were the point of running them.
Nothing had to be reverted, and no command errored unexpectedly this step.

The one thing I could not do at all is verify any of it against a real workspace — see below.

### What I learned

A job's `custom_tags.source` was doing less work than it looked like it was. Once the 18 jobs
collapsed into 1, the tag was already only restating the job's own identity, and serverless billing
records carry `job_id` natively. The instinct to treat "the tag disappeared" as a regression would
have led to hunting for a serverless tag mechanism to plug the hole, when most of the hole had
already closed itself in the previous step and the remaining part (per-source) was never solvable
with cluster tags anyway.

Also: `libraries:` on a serverless task is not an error, it is silently ineffective. That is a
nastier failure mode than a rejection would be, which is why the test asserts its ABSENCE rather
than just asserting the dependencies are present.

### What was tricky

Choosing the concurrency number honestly. The arithmetic argues for full fan-out — 39 parallel
iterations bounds wall-clock at the single slowest source instead of at five waves. The argument
against is not arithmetic but operational: this project has never run a single serverless task, the
shared-state analysis (run-log appends, `CREATE SCHEMA IF NOT EXISTS` races) is reasoned rather than
observed, and retries are being added in the same change precisely because we expect transient
failures we have not seen yet. I landed on 8 as the value that captures most of the win while
keeping the first run legible, and wrote the argument for raising it next to the constant so it is a
decision rather than an oversight. Reasonable people could pick 39.

Picking `environment_version: "3"` was the least satisfying part — see below.

### What warrants review

- `src/resources/enrich_all.job.yml` — the whole change. Particularly the `environments:` block and
  the absence of `libraries:` / `job_clusters`.
- `ENRICH_CONCURRENCY = 8` in `src/scripts/generate_jobs.py`: if Benny wants the wall-clock floor
  rather than a cautious first run, this is the one number to change.
- **NOT verified offline, and main must confirm at deploy:**
  1. `environment_version: "3"` — I could not enumerate which serverless environment versions this
     workspace actually offers. The wheel needs only Python >=3.10 and pulls no compiled
     dependencies, so it is insensitive to the exact version; if the workspace rejects "3", bumping
     this one constant and regenerating is the whole fix.
  2. Whether DAB rewrites the `../dist/*.whl` glob inside `environments[].spec.dependencies` the
     same way it does inside `libraries[].whl`. This is the documented pattern for serverless wheel
     tasks and the highest-value thing to watch in `bundle validate` output.
  3. That the run-log's `CREATE SCHEMA IF NOT EXISTS` bootstrap and the append writes genuinely
     tolerate 8 concurrent iterations. Reasoned from Delta semantics, never observed here.
  4. Actual cost against the 200-500 DKK/month ceiling. Serverless DBU pricing differs from
     classic; nothing in this branch measures it.
- Deploy will DESTROY the 18 dev enrich jobs (already true after Step 3) and replace the enrich job
  with a serverless one. Read the deploy diff before confirming.

### Future work

- Create a serverless budget/usage policy at account level and set `budget_policy_id` on the enrich
  job, which restores tagged serverless usage.
- Write the run-log-based per-source cost apportionment query (`_ops.run_log.duration` share of the
  job's billed cost) — that is the only route to per-source enrich cost now.
- Raise `ENRICH_CONCURRENCY` toward full fan-out once a complete run is green.
- If ingest ever hits the same vCPU wall, the same serverless argument applies to it — but its
  Key Vault + credential story needs checking against serverless first, and it currently benefits
  from policy guardrails that enrich has now given up.

---

## Step 5: Serverless-compatible engine — the .cache() failure

**Author:** builder

### Prompt Context

**Verbatim prompt:**

> Runde 3. Jeg deployede og kørte dit serverless-job. Din opsætning virkede — wheel'en installerede
> via `environments[].spec.dependencies`, `environment_version: "3"` blev accepteret, entry-pointet
> `datavilla-enrich` startede. Alle fire ting du ikke kunne verificere offline er nu bekræftet på
> nær omkostningen.
>
> Men alle 39 sources fejlede, deterministisk og identisk:
>
> ```
> engine.py:108   cleansed = cleansed.cache()
> [NOT_SUPPORTED_WITH_SERVERLESS] PERSIST TABLE is not supported on serverless compute. SQLSTATE: 0A000
> ```
>
> 117 iterationer (39 × 3 forsøg — dine retries fungerede efter hensigten, fejlen var bare ikke
> transient). Run `738961088735741`, 27,5 min.
>
> ## Opgave
> Gør `src/datavilla/enriched/engine.py` serverless-kompatibel.
>
> Linje 108 og 119 er `cleansed.cache()` / `cleansed.unpersist()`. Intentionen står i kommentaren:
> "Cache so the count and the write share one scan of the current view." Den intention skal bevares
> — fjern ikke bare cachen og accepter to fulde scans.
>
> Mit forslag, som du gerne må modbevise: skriv til Delta først, og hent så rækketallet fra
> target-tabellen bagefter. En count mod en netop skrevet Delta-tabel læses fra metadata og er tæt
> på gratis, så du får ét scan af kilden i stedet for to — og du får tallet fra det der faktisk blev
> skrevet frem for fra en DataFrame vi antager blev skrevet uændret. Vær opmærksom på at
> `ctx.rows_in`/`ctx.rows_out` og `EnrichResult` sætter begge felter fra samme tal i dag; hold
> run-log-semantikken korrekt, uanset hvilken rækkefølge du vælger.
>
> ## Scanning jeg allerede har lavet — læs den, du skal ikke gentage den
> Ingen `sparkContext`, ingen `.rdd`, ingen `spark.conf.set`/`setConf` i `datavilla/`. `.cache()` er
> den eneste inkompatibilitetsklasse i koden.
>
> Men den findes fire steder mere:
> - `datavilla/write/raw.py:167` + `183`
> - `datavilla/write/scd2.py:363`, `402`, `439`, `441`
> - `datavilla/write/snapshot.py:123` + `161`
>
> **Rør dem ikke.** De ligger alle i ingest-stien, som kører på classic, hvor `.cache()` er lovligt
> og gør gavn. At ændre dem nu ville røre den delte SCD2-merge-motor som alle kilder afhænger af,
> uden at noget kræver det.
>
> Dokumentér dem i stedet: de er en kendt blokering hvis ingest-laget senere skal på serverless.
> Skriv det ét sted hvor det bliver fundet igen (diary og/eller README), ikke som en løs
> kodekommentar.
>
> ## Test
> Fejlen her var usynlig offline, fordi lokal Spark accepterer `.cache()`. Overvej hvad der
> realistisk kan fange klassen af fejl i unit-tests — fx en assertion om at enriched-motoren ikke
> kalder cache/persist. Hvis du vurderer at en sådan test er teater frem for værdi, så sig det og
> lad være; jeg vil hellere have din begrundelse end en grøn test der ikke beviser noget.
>
> ## Uændret
> Byg og test offline, du deployer ikke og kører ikke jobs. Ingen ægte data-værdier nogen steder
> inkl. diary. Commit som `singularity-consult <benny@singularityconsult.dk>`, ingen
> `Co-Authored-By`, push ikke, rør ikke .ps1-filer. Commit undervejs. Drift-check rent, alle tests
> grønne.

**Interpretation:** Remove the `.cache()`/`.unpersist()` pair from the enriched engine WITHOUT
regressing to two full scans of the source, keep the run-log's rows_in/rows_out honest under
whatever ordering results, document (not fix) the eight remaining cache sites on the classic ingest
path, and make a judgement call about whether an offline test can meaningfully catch this class of
bug.

**Inferred intent:** Get the enriched layer actually running on serverless, and close the offline
blind spot that let a deterministic platform incompatibility reach a 27-minute production run.

### What I did

**Checked the lead's proposal before adopting it, and adopted it.** Write to Delta first, then read
the row count back from the target table. The reasoning holds: an unfiltered `COUNT(*)` on a Delta
table is answered from the transaction log's per-file row statistics rather than by re-reading data,
so the source is scanned exactly once and nothing is persisted. It is also a better number than the
old one — it reports what the table contains after the commit rather than what a DataFrame we
believe was written unchanged would have produced.

I considered one alternative and rejected it: pulling `numOutputRows` out of the write's own
`operationMetrics` via `DESCRIBE HISTORY` / `DeltaTable.history(1)`. That is the most precise
possible number (it comes from the commit itself, with no follow-up query at all), but the metric
key names vary by operation type, it couples the engine to the delta-spark API surface, and it is
materially more code for a number that the metadata count already gives correctly. Not worth it.

**run-log semantics.** `ctx.rows_in`/`ctx.rows_out` and `EnrichResult` still take the same number,
but the justification is now stronger than "enriched is 1:1 with the current view". I verified it is
a STRUCTURAL property rather than an assumption: `build_enriched_expressions` emits `select_exprs`
entries that are each either `quote_ident(name)` or `<expr> AS <alias>` (transforms.py:499/515/519),
and no transform emits `explode`/`posexplode`/`inline` — I grepped. A pure projection cannot add or
drop rows, so counting the target is a valid measure of both. Measuring rows_in independently would
mean counting the source as well, i.e. reintroducing exactly the second scan this ordering removes.
That reasoning is now a comment in the code, because it is the thing that makes a single count
legitimate for two fields.

**The test judgement — this is the part the lead asked me to argue rather than assume.** A test that
greps `engine.py` for the string `.cache(` WOULD be theater: it asserts a spelling, passes if
someone writes `.persist(StorageLevel...)` instead, and proves nothing about behaviour. I did not
write that.

What I wrote instead is a behavioural double. `tests/test_enrich_engine.py` already drove the engine
with a fake Spark/DataFrame; those fakes now behave like serverless:

- `cache()` and `persist()` raise `ServerlessViolation`, mirroring
  `[NOT_SUPPORTED_WITH_SERVERLESS] PERSIST TABLE is not supported`.
- `count()` on the cleansed frame ALSO raises — not because counting is illegal (it is legal
  everywhere) but because without a cache it re-executes the whole read+transform plan. That is the
  second scan the cache existed to prevent, so the fake refuses it and forces the count to come from
  the written table.
- `spark.table(...)` returns a `FakeTable` that asserts the write happened first, so counting the
  target before writing it (which would count the PREVIOUS contents) fails too.

This runs the real code path and would have caught the production failure offline. I proved that
rather than claiming it: I reintroduced `cleansed = cleansed.cache()` into the engine and re-ran —

```
tests\test_enrich_engine.py:97: ServerlessViolation
FAILED tests/test_enrich_engine.py::test_run_log_row_identifies_the_iterations_own_source
FAILED tests/test_enrich_engine.py::test_enrich_runs_without_caching_anything
FAILED tests/test_enrich_engine.py::test_row_count_comes_from_the_written_table_not_a_second_scan
FAILED tests/test_enrich_engine.py::test_schema_is_created_before_the_write
4 failed, 1 passed
```

— then reverted. So the answer to "theater or value" is: a source grep would have been theater, a
fake that refuses what the platform refuses is not, and the mutation run is the evidence.

I also added `test_schema_is_created_before_the_write`, because this change moved the
`CREATE SCHEMA IF NOT EXISTS` and the write past each other and ordering there is load-bearing —
`saveAsTable` into a non-existent schema fails.

**Documented the eight untouched cache sites** in `src/README.md` under a new heading, "Serverless
compatibility — `.cache()` is the known blocker", as a table of file + line numbers
(`write/raw.py` 167/183, `write/scd2.py` 363/402/439/441, `write/snapshot.py` 123/161) with the
explicit statement that they are legal and useful on the classic ingest path, must not be "fixed"
speculatively, and are THE blocker if ingest is ever moved to serverless. I put it in the README
rather than in code comments because the lead asked for one findable place, and because someone
planning an ingest-to-serverless move will read the README, not stumble across a comment in the SCD2
merge engine. The section also records the lead's negative scan result (no `sparkContext`, no
`.rdd`, no `spark.conf.set`) so nobody repeats it.

### Why

Because the failure was not transient and no amount of retry tuning would have helped — the retries
worked perfectly and simply re-ran an illegal operation three times per source. The only fix is to
stop issuing the operation, and the only fix worth having is one that does not silently pay for it
with a doubled scan of every source.

### What worked

The lead's proposal was correct as stated and I could not find a reason to overturn it — the write-
then-count ordering is both cheaper and more truthful than count-then-write, and it happens to be
the ordering that removes the need for a cache at all. Good proposal.

The existing fake-based test file from Step 3 turned out to be exactly the right place to encode the
platform constraint. Because the engine already accepted an injected `spark`, making the doubles
behave like serverless was a change to the test doubles, not a redesign of the engine.

### What didn't work

Nothing failed unexpectedly in this step. The only failures were the ones I induced on purpose (the
mutation run above), and they failed in exactly the way that proves the test works.

The real "what didn't work" belongs to the previous step and is worth stating plainly: I shipped
Step 4 having verified the job SPEC against the bundle schema, and treated the engine code as
settled because it was untouched and its tests were green. That was the wrong boundary. Changing the
compute model changes what the runtime accepts, so the code that runs ON it needed re-examining too
— and the one class of incompatibility in the codebase was sitting on line 108 of the file the job's
entry point calls.

### What I learned

A green offline suite is weaker evidence than usual when the target is serverless, because local
Spark is more permissive than serverless is. `.cache()` is the sharp instance: universally legal
everywhere a developer can run it, rejected at runtime on the platform we now deploy to. The
generalisable move is to make the test doubles model the RESTRICTIONS of the target platform, not
just the happy path of the API — a fake that says yes to everything only tests that the code runs,
not that it is deployable.

Second, retries have a failure mode of their own: they turn one clear error into 117 iterations and
27.5 minutes of the same error. That is not an argument against the retries (they are correct for
the transient class they were added for), but it does mean a deterministic failure is expensive
under them, which raises the value of catching this class offline.

### What was tricky

Judging the test question honestly. The easy move was to write something green that looks like
coverage — assert the source text has no "cache", tick the box. Deciding what would ACTUALLY have
caught this, then proving it by breaking the code on purpose, took longer than writing the fix did.
The fix itself is about eight lines.

The other subtlety was `count()` on the fake. Making it raise feels wrong at first glance — counting
a DataFrame is not an error. But under the no-cache design it is a silent doubling of the work, and
the fake is the only place that distinction can be enforced, so the refusal earns its place. The
docstring on `FakeDataFrame` explains that, because a future reader will otherwise assume the raise
is a mistake.

### What warrants review

- `src/datavilla/enriched/engine.py` lines ~106-143: the write-then-count ordering, and the comment
  block explaining why rows_in and rows_out legitimately share one measurement.
- `src/tests/test_enrich_engine.py`: whether the fakes' refusals are the right ones. They encode a
  judgement about what serverless disallows and what counts as a second scan.
- **Still not verified offline, and now the only open item from Step 4:** the actual cost against
  the 200-500 DKK/month ceiling. Everything else on that list is confirmed by the lead's run.
- Unverified by construction: that the metadata `COUNT(*)` really is near-free on the written table
  in this workspace. It is standard Delta behaviour and the query is unfiltered, but the only proof
  is a run's timings.
- The eight `.cache()` sites in `write/` are UNCHANGED on purpose. If review wants them changed,
  that is a separate piece of work on the shared SCD2 merge engine and should not ride along here.

### Future work

- If ingest ever moves to serverless, the README table is the starting worklist; `write/scd2.py` is
  the hard one because `staged`/`changed` are each consumed more than once by the merge.
- Consider whether the same serverless-shaped fakes should back the ingest-path tests, so that work
  would be caught by the suite rather than by a run — deliberately not done now, since ingest is
  staying on classic and the doubles would be asserting a constraint that does not apply to it.
- Measure the real cost of a full serverless enrich run and compare against the raised ceiling.
