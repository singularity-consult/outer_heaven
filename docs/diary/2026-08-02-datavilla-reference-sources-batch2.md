# Diary: Reference sources batch 2 (Fear & Greed, DefiLlama, DST) for Datavilla

Add the last three of four planned open-source REFERENCE/MARKET data sources to
Datavilla as new raw sources (the first, Nationalbanken FX, is already built on
`feature/nationalbanken-fx`). All three are keyless public APIs and, like FX, are
reference data that enriches curated via a date/key join — not Benny's personal data:

  * **Fear & Greed** (alternative.me) — daily crypto-sentiment index (0-100 +
    classification). Replaces the stale DSA-database-sourced `alternative_feargreedindex`.
  * **DefiLlama** — keyless crypto price / DeFi reference data.
  * **DST** (Danmarks Statistik) — the SAME public PxWeb statbank API as FX, for
    macro reference series (CPI for real-adjustment, possibly interest rates).

## Step 1: Verify endpoints + refine requirements + challenge scope + prepare worktree

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Forfin krav til tre nye datavilla raw-kilder (open source
reference/markedsdata, alle keyless): Fear & Greed, DefiLlama, Danmarks Statistik (DST).
Du forfiner + udfordrer + forbereder worktree; du implementerer ikke og kan ikke spawne
builder (main gør det). Ingen kode-build." Followed by context: these are the last three
of four open-source reference sources (FX/Nationalbanken already built, commit `f0f8bb4`
on `feature/nationalbanken-fx`, live-proof pending with main). All are reference/market
data that enriches curated via join, keyless, drone-verified. Extraction-adapter pattern
(REST -> landing -> raw -> SCD2); forebears `extract/coingecko.py` and the new
`extract/nationalbanken.py` (keyless `KEYLESS_ADAPTERS` pattern + JSONSTAT decode that DST
reuses). Named design choices to settle per source with recommendations; decide branch
structure (lean toward one branch, three adapters, sequential) and the JSONSTAT-decoder
reuse question (shared helper vs copy). Prepare a worktree/branch off master; write this
diary Step 1; report verified endpoints/forms, design choices with recommendations, the
reuse decision, worktree+branch, and what the builder builds. Do not build.

**Interpretation:** Do the discovery and decision work that de-risks the build for three
sources at once. Verify each endpoint/form live (not from memory or a summariser), map
each onto the existing extraction-adapter framework, settle the per-source design choices
and the cross-cutting structure/reuse choices, and challenge scope where a source risks
being redundant. Prepare the branch and report an unambiguous builder spec; main spawns
the builder.

**Inferred intent:** Finish the reference-data foundation so curated can join macro/market
context (sentiment, DeFi prices, CPI) onto Benny's personal transaction history. Benny
wants the load-bearing unknowns (exact endpoint forms, the monthly-vs-daily Tid shape for
DST, whether DefiLlama duplicates CoinGecko) resolved before a builder commits, and the
three sources folded into the existing landing -> Auto Loader -> raw SCD2 machinery rather
than inventing anything new.

### What I did

Read the extraction framework in this worktree checkout and the FX branch: `config.py`
(EXTRACTION_ADAPTERS, SourceDefinition, the keyvault/endpoint/landing blocks, the
`assets`/`keys`/`history` fields), `extract/coingecko.py` (the fan-out-over-a-list price
forebear that lands NDJSON and merges SCD2 on a composite `(key, date)`), and — from the
sibling FX worktree checkout — `extract/nationalbanken.py`, `config/sources/nationalbanken.yml`,
`resources/ingest_nationalbanken.job.yml`, `extract/__init__.py`, and the FX diff of
`config.py` (which adds `KEYLESS_ADAPTERS`, the `KeyVaultRef.require_secrets` relaxation,
the keyless branch in `SourceDefinition.from_dict`, and the `currencies`/`from_date`
fields). Also read `config/sources/dsa.yml` (the stale DSA jdbc sources, including the
`alternative_feargreedindex` this batch replaces) and the existing generated
`ingest_alternative_feargreedindex.job.yml`.

Verified all endpoints LIVE (not from memory):

  * **Fear & Greed** — `GET https://api.alternative.me/fng/?limit=2` returned
    `{name, data:[{value, value_classification, timestamp, time_until_update?}], metadata:{error}}`.
    `value`/`value_classification`/`timestamp` are STRINGS; `timestamp` is epoch seconds.
    `time_until_update` (a countdown) appears ONLY on the latest (current-day) entry.
    `?limit=0` returns full history.
  * **DefiLlama** — `GET https://coins.llama.fi/prices/current/coingecko:bitcoin,coingecko:ethereum`
    returned `{coins:{"coingecko:bitcoin":{price, symbol, timestamp, confidence}}}`.
    Historical `GET /prices/historical/{unix_ts}/{coins}` returned the same per-coin shape.
    The daily SERIES endpoint `GET /chart/{coins}?start=&span=&period=1d` returned
    `{coins:{"coingecko:bitcoin":{symbol, confidence, prices:[{timestamp, price}, ...]}}}`
    — a whole series in ONE call per coin (the clean backfill path, mirroring CoinGecko's
    market_chart). Prices are in USD. Coins are addressed `coingecko:{id}` or `{chain}:{contract}`.
  * **DST** — `GET https://api.statbank.dk/v1/tableinfo/PRIS111?lang=en` confirmed the
    SAME PxWeb API as FX BUT PRIS111 is marked INACTIVE (frozen at Dec 2025, replaced by
    PRIS01 due to ECOICOP v1->v2). `GET /v1/tableinfo/PRIS01?lang=en` confirmed PRIS01 is
    ACTIVE (last updated 2026-07-10), MONTHLY, variables VAREGR (commodity group, 150+),
    ENHED (unit: index/MoM%/YoY%), Tid. Crucially the monthly Tid code is `2025M01`
    (year-month) — NOT DNVALD's daily `2017M01D03`, so FX's daily `tid_to_iso` regex does
    not match and DST needs month-aware period parsing.

Prepared the worktree: created branch `feature/reference-sources-batch2` off clean master
`1349be6` in worktree `C:\claudes_folder\repos\datavilla\.claude\worktrees\agent-ab4690258b18f20fc`.

### Why

The build is de-risked by proving each endpoint's exact form and by catching the two traps
a summariser would miss: (1) PRIS111 is dead — building against it would ship a source that
never updates; PRIS01 is the live table. (2) DST's monthly Tid shape differs from FX's
daily one, so the JSONSTAT decoder is reusable but the Tid/normalise layer is not — that
distinction decides the reuse design. Verifying DefiLlama's `/chart` endpoint gives a
one-call-per-coin backfill instead of one-call-per-day-per-coin, and surfaces that its
prices are USD (CoinGecko already lands DKK), which is the basis for challenging whether
DefiLlama-as-prices is redundant.

### What worked

Every endpoint verified first try. The FX branch is a near-exact template: the keyless
machinery (`KEYLESS_ADAPTERS`, `require_secrets=False`, the None-keyvault branch) and the
generic `decode_jsonstat` unravel-the-flat-array logic drop straight onto Fear & Greed
(keyless, no vault) and DST (keyless + JSONSTAT). CoinGecko's fan-out-over-a-list +
SCD2-on-`(key, date)` is the template for Fear & Greed and for DefiLlama's `/chart` series.

### What didn't work

No failures — all three endpoints returned 2xx with the expected shapes on the first probe.
The only negative finding is a design trap, not a failure: PRIS111 (the "obvious" CPI table
named in the task context) is inactive and must be swapped for PRIS01.

### What I learned

The FX branch already paid the cost of the keyless + JSONSTAT machinery, so this batch is
mostly additive config plus per-source normalisation. The genuinely reusable unit is
`decode_jsonstat` (table-agnostic: it unravels any JSON-stat cube). The DNVALD-specific
parts (`tid_to_iso`, `filter_tid_codes`, `parse_tid_codes`, `normalize_rates`) are NOT
reusable for DST because DST is monthly and multi-dimension (VAREGR x ENHED x Tid) with a
per-table record shape. So reuse = extract `decode_jsonstat` (and the generic
"read a variable's value codes from tableinfo") into a shared helper; the Tid/normalise
layer is per-adapter.

### What was tricky

FX is NOT merged yet, so this branch (built from master) does not have `KEYLESS_ADAPTERS`,
the `require_secrets` relaxation, or `nationalbanken.py` to import from. Two consequences:
(1) the builder must ADD the keyless config machinery on this branch, mirroring the FX diff
verbatim so main's post-FX-merge rebase is a trivial union (same additive overlap as
CorPay<->EB). (2) The shared JSONSTAT helper must be a NEW module created on this branch;
DST imports it; `nationalbanken.py` is left untouched (it lives on the FX branch). A
follow-up after FX merges can DRY nationalbanken onto the shared helper — noted, not done
here, to keep this branch conflict-free.

### What warrants review

Two scope/cutover decisions are OPEN pending Benny and gate the final builder spec:
(1) **DefiLlama's job** — prices (USD; overlaps CoinGecko's DKK price axis) vs DeFi
protocol/TVL (unique) vs both. This is the sharpest challenge; DefiLlama-as-prices is
largely redundant with CoinGecko. (2) **Fear & Greed cutover** — replace the stale DSA
`alternative_feargreedindex` in place (same `raw.alternative.feargreedindex` table, drop
the jdbc source from dsa.yml) vs land alongside in a new table. Recommendations recorded in
the report; this diary step will be finalised once Benny decides.

### Future work

After FX merges to master: rebase this branch (main owns the order), then optionally refactor
`nationalbanken.py` to import the shared JSONSTAT helper instead of its private copy. If
DefiLlama TVL is wanted later, it is a separate raw table/source from DefiLlama prices. DST
is table-agnostic by design, so adding a second DST table (e.g. an interest-rate table) is
config-only once the adapter exists.

## Step 2: Build the two adapters (Fear & Greed + DST), shared JSONSTAT helper, config, infra, jobs, tests

**Author:** builder

### Prompt Context

**Verbatim prompt (relayed by main):** "Byg TO nye datavilla raw-kilder: Fear & Greed +
Danmarks Statistik (DST). DefiLlama er DROPPET af Benny (dublerede CoinGecko — byg den
IKKE). Begge keyless, verificeret. Lead har forfinet dem." Followed by: rebase first
(`git fetch origin && git rebase origin/master`, FX now merged at `f0f8bb4`); build code +
test OFFLINE only (`pytest` + `generate_jobs.py --check`), do NOT deploy/run jobs/materialise
(deploy is main's role per `databricks.yml`); reuse FX's JSONSTAT decoder as a SHARED helper
both nationalbanken and dst import (keep nationalbanken tests green); PRIS111 is dead → use
PRIS01 (monthly `2025M01`), verify its dimensions via `tableinfo`; table list configurable in
yml; infra `landing_schemas` += feargreed + dst; regenerate jobs; synthetic tests (value 42,
classification "Neutral", date 1999-12-31); commit on the branch, do not push.

**Interpretation:** Ship two keyless extraction adapters onto the now-merged FX foundation.
The DefiLlama open question from Step 1 is resolved (dropped). The JSONSTAT reuse question
from Step 1 is resolved in favour of a shared helper. Everything is offline-provable; main
does the live proof after a green offline report.

**Inferred intent:** Fold the last two reference sources into the existing landing → Auto
Loader → raw SCD2 machinery with zero new patterns, DRY the JSONSTAT decoder across the two
statbank sources, and keep the branch a trivial additive union so main's deploy is low-risk.

### What I did

Rebased first: `git fetch origin && git rebase origin/master` — trivial, the branch carried
no own commits (only the untracked diary), so it fast-forwarded onto `f0f8bb4` (FX merged),
which supplied `KEYLESS_ADAPTERS`, the `require_secrets` relaxation, and `extract/nationalbanken.py`
with the private `decode_jsonstat`. So the Step-1 "FX not merged, add the machinery here"
plan was moot — the machinery is already on master.

Verified PRIS01 live before writing the adapter (read-only public GET, keyless — the same
validation the FX builder did by hand):
  * `GET /v1/tableinfo/PRIS01?lang=en` → top-level `id` "PRIS01"; variables **VAREGR**
    (commodity group, 277 values), **ENHED** (unit, 3), **Tid** (time, 315).
  * `GET /v1/data/PRIS01/JSONSTAT?Tid=2025M01&VAREGR=*&ENHED=*&lang=en` → `{dataset:{...}}`
    wrapper; `dimension.id` = `["VAREGR","ENHED","ContentsCode","Tid"]` (ContentsCode is
    API-INJECTED, single value "PRIS01", NOT a tableinfo variable); Tid code `2025M01`
    (monthly); ENHED code e.g. `100`. The `VAREGR=*` wildcard works in the GET dialect.

Built:
  * `src/datavilla/extract/jsonstat.py` — the SHARED decoder. Moved FX's `decode_jsonstat`
    body here verbatim, adding an injectable `shape_error` param (default `JsonStatError`)
    so each adapter keeps its own typed error. It is dimension-generic (already was).
  * `src/datavilla/extract/nationalbanken.py` — replaced the private `decode_jsonstat` body
    with a thin wrapper `return _decode_jsonstat(dataset, shape_error=NationalbankenShapeError)`
    over the shared helper. Public API (the `decode_jsonstat` symbol, `NationalbankenShapeError`)
    unchanged, so `test_nationalbanken.py` stayed green untouched.
  * `src/datavilla/extract/feargreed.py` — keyless `GET /fng/?limit=0`; parse the `data`
    list; `date` from epoch seconds; `value`/`value_classification` landed VERBATIM as the
    API's STRINGS; `time_until_update` and the raw epoch DROPPED (the countdown would break
    the SCD2 overlap no-op on the current day); dedup a repeated date to last; SCD2 on `date`.
  * `src/datavilla/extract/dst.py` — the GENERIC statbank reader. Table code = the source's
    `endpoint.name` (no new config field needed). Discovers the table's variable codes from
    `tableinfo`, POSTs `data/{table}` with `values:["*"]` per variable (full faithful pull),
    decodes via the shared helper (`shape_error=DstShapeError`), normalises to one FAITHFUL
    record per dimension cell: verbatim dimension codes as fields (incl. injected ContentsCode)
    + numeric `value`; Tid kept VERBATIM as its source period code (`2025M01`, NOT date-parsed —
    granularity varies by table); SCD2 on the full dimension set.
  * Registered both in `extract/__init__.py`; added `feargreed` + `dst` to `EXTRACTION_ADAPTERS`
    and `KEYLESS_ADAPTERS` in `config.py` (docstrings updated).
  * `config/sources/feargreed.yml` (source `feargreed_index`, raw `feargreed.index`) and
    `config/sources/dst.yml` (a `sources:` list, first entry `dst_pris01` → raw `dst.pris01`,
    keys `[VAREGR, ENHED, ContentsCode, Tid]`).
  * `infra/modules/unity_catalog/variables.tf` — appended `feargreed` + `dst` to the
    `landing_schemas` default set (moved-blocks untouched).
  * Regenerated jobs (`python scripts/generate_jobs.py`) → new `ingest_feargreed.job.yml`
    + `ingest_dst.job.yml`; every existing generated job stayed byte-identical.
  * Tests: new `test_jsonstat.py` (shared multi-dimension decoder + injectable error),
    `test_feargreed.py`, `test_dst.py`; updated `test_config.py` (expected-sources set +
    two parse tests) and `test_generate_jobs.py` (job-file set + two job-shape tests).

### Why

The shared helper with an injectable `shape_error` is the least-invasive DRY: it keeps both
statbank adapters' typed-error discipline (`NationalbankenShapeError` / `DstShapeError`) while
removing the duplicated 70-line decoder, and it let nationalbanken's tests pass unchanged
(the wrapper preserves the exact symbol + exception type). Using `endpoint.name` as the DST
table code avoids a new `SourceDefinition` field entirely — the table is genuinely the
endpoint for a statbank source, and it keeps `config.py` changes to two frozenset additions.
Keeping Tid verbatim (not ISO) is the faithful bronze choice: statbank time granularity is
per-table (monthly/quarterly/yearly/daily), so a generic date parse would be fragile — that
belongs in curated.

### What worked

`pytest` — 418 passed. `python scripts/generate_jobs.py --check` — up to date. `terraform fmt
-check` on the changed `variables.tf` — clean (exit 0). `pyflakes` on the four changed/new
modules — clean. The registry lists `dst` and `feargreed`. All nationalbanken tests green
after the JSONSTAT refactor (the whole point of the shared-helper-with-wrapper approach).

### What didn't work

Self-review caught one real bug I introduced. My first `normalize_cells` sorted DST records
by `sorted(dimension_ids)` — alphabetical — which puts `Tid` before `VAREGR` (ASCII T<V), so
records sorted by period-then-commodity instead of the cube's natural order. `test_dst.py::
test_normalize_cells_faithful_fields_and_sorted` failed with `At index 0 diff: {...'Tid':
'1999M12'...} != {...'Tid': '2000M01'...}`. Fix: sort by the dimensions IN THEIR SOURCE ORDER
(`[k for k in records[0] if k != VALUE_FIELD]`, which `decode_jsonstat` preserves as
insertion order) → VAREGR, ENHED, ContentsCode, Tid. Re-ran: 418 passed. Faithful to the
cube's own dimension order and deterministic.

### What I learned

The FX foundation made this almost purely additive — the keyless branch, `require_secrets`
relaxation and JSONSTAT decoder were all already on master post-merge, so the build was two
extractor modules + config + tests, not any framework change. The one non-obvious statbank
fact worth recording: the data API INJECTS a `ContentsCode` dimension that is NOT listed in
`tableinfo/variables`, so the extractor must NOT try to request it (it discovers only the
three real variables and requests those with `*`; ContentsCode arrives in the response and is
carried through as a faithful field / part of the key).

### What was tricky

Getting the shared decoder to leave nationalbanken's tests untouched. The tests do
`pytest.raises(NationalbankenShapeError, match="value length")` against
`nationalbanken.decode_jsonstat`, so the shared function had to raise the CALLER's exception
type, not a shared one — hence the injectable `shape_error` param rather than a fixed
`JsonStatError`. A shared-error-plus-catch-and-rewrap would have been noisier and lost the
original message; the param keeps the message verbatim.

### What warrants review (for main's live proof)

Offline-green but only confirmable on the target/cluster:
  * The `values:["*"]` wildcard is confirmed live in the GET query-param dialect; the POST
    JSON-body form `{"values":["*"]}` is the documented statbank equivalent but was only
    exercised with a fake transport here — worth watching on the first live DST run.
  * A full faithful PRIS01 pull is large (roughly 434 × 3 × 1 × 315 grid positions before
    null-drop) → a big single NDJSON landing file per run. Fine for bronze and SCD2 no-ops
    the overlap, but if the file size is a problem later, splitting per-Tid is the lever.
  * Live API responses for both sources (the decode/normalise loops run against fake
    transports in tests; the real request/response shapes were hand-probed, not replayed).

### Future work

Optionally add a second DST table (e.g. an interest-rate table) — config-only now the adapter
exists. The Fear & Greed source lands into its OWN `feargreed` schema and deliberately does
NOT touch the stale DSA `alternative.feargreedindex` JDBC copy; retiring that stale source is
a separate decision, not done here.

### Handoff to main (offline DoD met)

Rebase trivial (no own commits); `pytest` 418 passed; `generate_jobs.py --check` up to date;
`terraform fmt -check` clean; committed on `feature/reference-sources-batch2`, NOT pushed. I
did NOT deploy the bundle, run any job, or materialise anything on a warehouse — all offline.

## Step 3: Fix DST live-proof failure — adaptive Tid-chunking on the 1M-cell limit

**Author:** builder

### Prompt Context

**Verbatim prompt (relayed by main):** "DST live-proof FAILED on the cluster (feargreed
passed and is being merged). One bug to fix in your worktree... Your full PRIS01 pull is
rejected: `POST /v1/data/PRIS01` with all variables `values:["*"]` returns HTTP 400 body
`{"errorTypeCode":"REQUEST-LIMIT","message":"The request of up to 1,598,856 cells is over the
limit of max. 1,000,000 cells for this file format. Use BULK or other streaming format
instead."}`. The 1,598,856 is exactly 4× the real grid (VAREGR 434 × ENHED 3 × Tid 307 =
399,714) — DST's limit pre-check counts all 4 defined ContentsCode values though only 1
(PRIS01) is populated. Format/wildcard are NOT the problem; the POST-body `values:["*"]`
works and each Tid half returns 200. Fix: adaptive Tid-chunking in DstClient (optimistic
single POST; on 400 REQUEST-LIMIT parse the two integers, factor = ceil(N/(M*0.9)), split
Tid into that many contiguous disjoint chunks, POST each, decode+concatenate; recursive
re-split if a chunk still trips; Tid-of-1 still over -> clear DstApiError; parse only the
message integers with a tolerant regex, otherwise treat the 400 as generic DstApiError;
surface the Tid value list from the tableinfo you already fetch — no second call). Fear &
Greed is done, do NOT touch it." Plus a full DoD (chunking tests with a fake REQUEST-LIMIT
transport, docstring UNVERIFIED update, diary step, same offline bar, commit not pushed).

**Interpretation:** My Step-2 "per-Tid splitting if size bites" lever bit on the live cluster.
Implement it: keep the one-request fast path, add limit-driven Tid-chunking + recursion +
loud failure for the pathological single-Tid case, and prove it all offline with a fake
transport that returns the real REQUEST-LIMIT 400 shape.

**Inferred intent:** Land the full faithful PRIS01 history despite the JSONSTAT 1M-cell cap,
without abandoning the shared decoder or the SCD2 re-pull model, and without a second
tableinfo call — so main can re-deploy and the live pull succeeds.

### What I did

Root-caused offline from the coordinator's live evidence: the limit pre-check inflates the
cell count by ContentsCode's 4 defined-but-1-populated values, which a single-Tid probe
hides. Implemented adaptive Tid-chunking in `extract/dst.py`:

  * `TableVariables` dataclass (codes + per-variable value-id lists) and `parse_variables`
    (the richer sibling of `parse_variable_codes`, which now delegates to it) so the Tid
    value list comes from the SAME tableinfo GET — no second call.
  * `DstRequestLimitError(DstApiError)` carrying `requested`/`maximum`; `parse_request_limit`
    (tolerant regex `up to ([\d.,]+) cells ... max ... ([\d.,]+) cells`, thousands separators
    stripped) returns `None` for any non-REQUEST-LIMIT or unparseable 400 so an unrelated 400
    stays a generic `DstApiError`; `chunk_factor` = `max(2, ceil(requested/(maximum*0.9)))`;
    `split_contiguous` = contiguous disjoint chunks.
  * `DstClient`: low-level `_post(table, selections)` (selection map per variable; raises
    `DstRequestLimitError` on a parseable REQUEST-LIMIT, else `DstApiError`/`DstShapeError`);
    `_post_decode` decodes via the shared `decode_jsonstat`; `fetch_cells` runs the optimistic
    all-wildcard POST, and on `DstRequestLimitError` chunks Tid via `_chunk_on_tid` /
    `_fetch_tid_chunk` (recursive re-split; `len<=1` still over -> loud `DstApiError`).
  * Extractor now calls `client.variables(table)` then `client.fetch_cells(table, variables)`.
  * Docstring: added the 1M-cell-limit section (with the 1,598,856-vs-399,714 / 4×-ContentsCode
    detail) and rewrote the UNVERIFIED note — POST-body wildcard IS accepted live; the real
    constraint is the cell limit, handled by chunking.
  * Tests: rewrote the client section of `test_dst.py` for the new API and added the DoD cases
    — pure `parse_request_limit`/`chunk_factor`/`split_contiguous`; a `ChunkingStatbank` fake
    that returns the real REQUEST-LIMIT 400 for over-size Tid selections and per-chunk datasets
    otherwise, asserting (a) right chunk count, (b) concatenated cells == full grid, (c)
    sub-limit table = exactly ONE POST no chunking, (d) recursive re-split, (e) Tid-of-1 raises,
    plus unparseable-400 = generic error.

### Why

Optimistic-first keeps the common case (small tables) at one request with zero overhead; the
0.9 margin absorbs the API counting cells differently than the naive grid (which is exactly
what the 4× ContentsCode inflation is). Chunking Tid (not another axis) is right because Tid
is the axis that grows over time and is contiguous/disjoint-splittable, so concatenation
reproduces the faithful grid with no dedup. Parsing only the message integers, and returning
`None` otherwise, keeps the recovery scoped to the ONE recoverable 400 and never masks a
genuine error as a chunking trigger.

### What worked

`pytest` — 428 passed (was 418; +10 DST tests). `generate_jobs.py --check` up to date.
`terraform fmt -check` clean. `pyflakes` clean on `dst.py` + `test_dst.py`. Fear & Greed
untouched (already merged). The `chunk_factor(1598856, 1000000) == 2` test reproduces the live
PRIS01 two-halves split the coordinator confirmed (153/154 Tid).

### What didn't work

No failed check this round — the fix was green first full run after I aligned the fake
transport's reported integers with the intended `chunk_factor`. The genuine difficulty was
constructing an adversarial fake for the RECURSION case: with a realistic linear cell cost
and a correct factor, one split always suffices, so the recursion path only triggers on a
pathological table. I modelled that with a transport whose reported integers always yield
factor 2 while the true limit (`max_ok_tid=2`) needs repeated halving (8 -> 4,4 -> 2,2 each),
which exercises `_fetch_tid_chunk`'s recursive re-split and still reproduces the full grid.

### What I learned

statbank's cell PRE-CHECK is not the populated-cell count — it multiplies the DEFINED value
counts of every variable, so a dimension that is "effectively singleton" in the data
(ContentsCode = 1 populated) still costs its full defined cardinality (4) against the limit.
A single-Tid probe cannot reveal this; only the full request does. That is the concrete data
example behind "verify against the real thing, don't assume from a small probe".

### What warrants review (for main's re-run)

Offline-green; the live re-run should show ceil(N/(M*0.9)) chunks for PRIS01 (two, matching
the confirmed 153/154 halves) each returning 200. If DST ever adds a table whose SINGLE Tid
period alone exceeds 1M cells, it fails loudly by design (needs multi-dimension chunking,
deliberately out of scope) — that is a future extension, not a silent gap.

### Handoff to main

`pytest` 428 passed; `generate_jobs.py --check` up to date; `terraform fmt -check` clean;
pyflakes clean. Committed on `feature/reference-sources-batch2`, NOT pushed. Did NOT deploy,
run any job, or touch Fear & Greed. Ready for main to re-deploy and live-prove DST.
