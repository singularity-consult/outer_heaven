# Diary: Nationalbanken FX (foreign-exchange rates) reference source for Datavilla

Add Danmarks Nationalbank's daily foreign-exchange rates as a new Datavilla raw
source. This is REFERENCE/MARKET data (not Benny's personal data): a daily series of
DKK-per-100-units-of-foreign-currency rates that curated joins on date to convert
fiat amounts (EUR/USD/GBP -> DKK) when pricing bank and crypto transactions. It is the
first of four planned open-source reference sources (the others — Fear&Greed,
DefiLlama, DST — are out of scope here) and is prioritised because curated's fiat
conversion cannot run without it. Benny's crypto/bank history reaches back to 2017, so
the source must carry deep daily history, not just the latest rate.

## Step 1: Verify the historical endpoint + refine requirements + prepare worktree

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Forfin krav til en ny datavilla raw-kilde: Nationalbanken
valutakurser (FX). Du forfiner + udfordrer + forbereder worktree; du implementerer
ikke, og kan ikke spawne builder (main gør det på din rapport). Ingen kode-build."
Followed by context: FX is the first of four open-source reference sources and is
PRIORITISED because curated fiat conversion (EUR/USD -> DKK) needs it; reference data
that enriches curated via a date join. The drone verified the DAILY endpoint
(`currencyratesxml`, 200, XML, 30 codes, latest day only) but NOT the historical
backfill — the lead must find and verify the historical FX endpoint (URL, format, how
far back). Four named design choices to settle with recommendations (XML parsing;
daily+historical one adapter or two; raw faithful form; keyless-secret handling; which
currencies). Prepare branch `feature/nationalbanken-fx` off clean master `1349be6`,
write this diary Step 1, report the verified endpoint + choices + worktree, and let
main spawn the builder. Do not build.

**Interpretation:** Do the discovery and decision work that de-risks the build. The
load-bearing unknown is the historical backfill endpoint — verify it live, not from
memory or a summariser. Map the source onto the existing extraction-adapter framework
(the CoinGecko price source is the nearest forebear) and settle the five design
choices so the builder gets an unambiguous spec. Prepare the worktree/branch and
report; the builder implements.

**Inferred intent:** Curated's whole fiat-conversion capability is blocked on this
source, and it only earns its place if it carries enough history to price a 2017
transaction. Benny wants the lead to prove the deep-history path works before a builder
commits to it, and to fold the source into the existing landing -> Auto Loader -> raw
SCD2 machinery rather than inventing anything new.

### What I did

Read the extraction framework end to end in the worktree checkout: `extract/base.py`
(registry + `SourceExtractor` contract), `extract/coingecko.py` (the nearest forebear:
a keyless-ish reference time series that fans out over a configured list, lands NDJSON,
merges SCD2 on a composite `(key, date)`), `config.py` (`EXTRACTION_ADAPTERS`,
`SourceDefinition`, the `assets`/`keys`/`history` fields and the keyvault/endpoint/
landing blocks), `secrets.py` (UC service-credential -> Key Vault token path), the
existing `config/sources/coingecko.yml`, and `write/scd2.py` (the versioning merge and
its overlap no-op).

Then I verified the endpoints live. The daily `currencyratesxml` returns
`<exchangerates><dailyrates id="YYYY-MM-DD"><currency code=.. desc=.. rate=..>` — the
latest banking day only, as the drone reported. The old SharePoint history endpoint
`_vti_bin/DN/DataService.svc/CurrencyRatesHistoryXML` still responds but returns a
DIFFERENT XML dialect (ECB `gesmes:Envelope`) and only a ~5-day rolling window by
default; probing it for a date-range parameter (`year=2017`) returned HTTP 404, and
curl from this environment is WAF-blocked, so it is a dead end for deep history.

The real find: Nationalbanken's daily rates are published as PxWeb table **DNVALD**
("Daily exchange rates") through the shared statbank API at
**`https://api.statbank.dk/v1/`** — the SAME PxWeb API contract Danmarks Statistik
(the future DST source) uses. `GET /v1/tableinfo/DNVALD?lang=en` returned full
metadata (contact `stat@nationalbanken.dk`, source "Danmarks Nationalbank"): three
query variables — `VALUTA` (55 currencies), `KURTYP` (4 types; `KBH` = "Exchange rates
(DKK per 100 units of foreign currency)" is the spot rate), and `Tid` (12,510 daily
dates from `1977M01D03` to `2026M07D30`, format `YYYY'M'MM'D'DD`, banking days only).
`USD` reaches back to Jan 1977, `EUR` to Jan 1999, `GBP` to Jan 1981 — far past
Benny's 2017 floor.

I then verified I can actually PULL values, not just metadata. A `POST /v1/data/DNVALD`
with `VALUTA=[EUR,USD]`, `KURTYP=[KBH]`, `Tid=[2017M01D03, 2024M06D14]` returned real
rates: EUR 2017-01-03 = 743.41 DKK/100 (i.e. ~7.43 DKK/EUR — matches the known peg),
USD = 715.85. CSV came back Danish-locale (comma decimals, Danish labels); the
`JSONSTAT` format with `lang:"en"` in the POST body returned clean JSON numbers
(`value:[715.85]`, `decimals:4`, `source:"Danmarks Nationalbank"`) and English labels
— parseable with stdlib `json`, no XML.

Prepared the worktree: confirmed master clean at `1349be6`, working tree clean, and
created branch `feature/nationalbanken-fx` in the isolated worktree
`C:\claudes_folder\repos\datavilla\.claude\worktrees\agent-a2a29656facf8bc17`.

### Why

The task's stated primary endpoint (`currencyratesxml`) only ever yields the latest
day, and the legacy XML history service is unreliable and shallow. Curated cannot price
a 2017 transaction from either, so the whole source hinges on finding a deep-history
endpoint — hence verifying DNVALD live and pulling actual 2017 values before any code
is written. Discovering that DNVALD is served through the identical PxWeb contract the
DST source will use collapses two of the design choices (no XML, one endpoint) and
turns this source into the reference implementation for the DST source that follows.

### What worked

Going straight to the data API instead of the legacy XML service. `api.statbank.dk`
serving a Nationalbanken table was unexpected but verified twice (metadata + a real
data pull), and the JSONSTAT format sidesteps the entire XML-parsing question the task
posed. The CoinGecko forebear maps almost one-to-one: keyless reference series, trailing
re-pull window, SCD2 on `(entity, date)` — the builder inherits a proven shape.

### What didn't work

The legacy history endpoint `CurrencyRatesHistoryXML` is a dead end: default response is
a ~5-day window, `?...&year=2017` returned `HTTP 404 Not Found`, and it emits a third
XML dialect (`gesmes:Envelope`) unrelated to `currencyratesxml`. Direct `curl` to
`nationalbanken.dk` returned empty bodies (WAF-blocking this environment's user agent),
so all live verification of Nationalbanken hosts had to go via WebFetch or the
`api.statbank.dk` host, which is not WAF-blocked. The WebFetch summariser also
hallucinated specific rate numbers (labelled EUR as "Australian dollars"), so I trusted
only the raw `api.statbank.dk` responses for values.

### What I learned

Nationalbanken's authoritative daily FX history is not on nationalbanken.dk at all — it
is PxWeb table DNVALD on `api.statbank.dk`, the same API family as DST. `KURTYP=KBH` is
the spot rate and is quoted as DKK per 100 units of foreign currency (confirming the
drone's "per 100" note from the source's own type label, not an assumption). The `Tid`
code format is PxWeb's `YYYY'M'MM'D'DD`. DNVALD lags the live `currencyratesxml` by
about one banking day (latest `Tid` 2026-07-30, updated 2026-07-31 06:00Z), which is
irrelevant for pricing already-settled transactions.

### What was tricky

Separating three superficially similar XML/endpoints (`currencyratesxml`,
`CurrencyRatesHistoryXML`, and the DNVALD data API) and not being misled by the legacy
history service that "works" but is shallow. Also resisting the summariser's fabricated
numbers — the design decision on "per 100" and faithful raw form rests on real values,
so verification had to come from raw API bytes.

### What warrants review

The builder should re-run the two `api.statbank.dk` probes (tableinfo + a small data
POST) on the target runtime to confirm the host is reachable from Databricks and the
JSONSTAT value-array mapping (cartesian product of dimension indices) is decoded
correctly. The one-vs-two-source recommendation (DNVALD only, drop the XML daily) is a
scope decision Benny should confirm — it trades ~1 banking-day freshness for dropping
the entire XML path.

### Future work

The DST reference source (planned, out of scope here) uses the same `api.statbank.dk`
PxWeb contract, so a clean, reusable PxWeb/JSONSTAT parsing helper written here should
be factored so DST can reuse it. If a future dashboard ever needs same-day rates,
`currencyratesxml` can be added as a second endpoint then — deliberately deferred.

## Step 2: Build the extractor + keyless config change + tests

**Author:** builder

### Prompt Context

**Verbatim task (condensed):** Build the Nationalbanken FX raw source per the lead's
refined plan — auth-free, JSON, live-verified. Build CODE + TESTS OFFLINE + report;
do NOT deploy the bundle or run jobs (that is main's role, per `src/databricks.yml`;
attempting warehouse materialisation / job runs killed the previous enriched builder).
Seven build items: `extract/nationalbanken.py` (model on `extract/coingecko.py`),
`config/sources/nationalbanken.yml`, register the adapter + loosen `KeyVaultRef`
secrets-validation so a keyless extraction source can have EMPTY `keyvault.secrets`,
`landing_schemas` +1, regenerate jobs, and synthetic tests. DoD: `pytest` green,
`generate_jobs.py --check` green, diary updated, commit (do NOT push), confirm
`landing_schemas` is +1, confirm I did NOT deploy/run jobs.

**Interpretation:** Faithful offline build following the CoinGecko forebear's shape.
The load-bearing novelty is the JSONSTAT flat-array decode and the FIRST keyless
source (no vault). Verify the exact API behaviour by hand (read-only probes are
allowed and necessary to get the decoder right) but never run a Databricks job.

### What I did

Probed the live `api.statbank.dk` DNVALD endpoints read-only to nail down the exact
shapes before writing the decoder (this is verification, not job-running):
`GET /v1/tableinfo/DNVALD?lang=en` → 3 variables VALUTA/KURTYP/Tid confirmed;
`POST /v1/data/DNVALD` with JSONSTAT returned `{"dataset":{dimension:{id:[VALUTA,
KURTYP,ContentsCode,Tid], size:[...], <dim>.category.{index,label}}, value:[flat
row-major array]}}`. Three findings drove the design:
  * The API injects an extra `ContentsCode` dimension we never send, so the decoder
    must be GENERIC over `dimension.id` order, not hardcoded to 3 axes.
  * A currency with no rate on a banking day (EUR in 1977) lands as JSON `null` in
    `value[]` (plus a `status` map of `".."`). Must be DROPPED, never a zero row.
  * An invalid / non-banking-day Tid code (e.g. Sunday `2017M01D01`) returns an ERROR
    body `{"errorTypeCode":"EXTRACT-NOTFOUND"}`, NOT a 200. So the extractor cannot
    send computed calendar dates — it must DISCOVER valid Tid codes from `tableinfo`
    first, filter to the window, and POST only those. A local calendar can't know the
    Danish holiday set.
  * Verified a single POST for the full 2017→today window (7 currencies × 2390 banking
    days = 16,730 cells) returns HTTP 200 with 42 nulls — so NO chunking is needed; one
    discover-GET + one data-POST per run.

Built:
  * `src/datavilla/extract/nationalbanken.py` — a two-call extractor (tableinfo GET →
    data POST). Pure, separately-tested core: `tid_to_iso` (`2017M01D03`→`2017-01-03`),
    `parse_tid_codes` (tableinfo → valid banking-day codes), `filter_tid_codes` (keep
    ≥ from_date, ISO strings sort chronologically), `decode_jsonstat` (unravel the flat
    row-major array via per-dimension strides back to `{dim_id: code}` + value, drop
    nulls, shape-check hard), `normalize_rates` (cells → one record per
    `(currency_code, rate_date)`, `rate` VERBATIM as DKK-per-100, sorted). Hard-fails
    loudly: `NationalbankenApiError` on any non-2xx, `NationalbankenShapeError` on a
    2xx that isn't the expected JSONSTAT/tableinfo shape.
  * `src/config/sources/nationalbanken.yml` — `adapter: nationalbanken`, `history:
    scd2`, `keys: [currency_code, rate_date]`, `currencies: [EUR,USD,GBP,SEK,NOK,CHF,
    JPY]`, `from_date: 2017-01-01`, endpoint `exchange_rates`, target
    `raw.nationalbanken.exchange_rates`. Deliberately NO `keyvault` block.
  * `config.py` — added `nationalbanken` to `EXTRACTION_ADAPTERS`; added a SCOPED
    `KEYLESS_ADAPTERS = {"nationalbanken"}`; `KeyVaultRef.from_dict` gained a
    `require_secrets: bool = True` kwarg (keyed sources still reject empty/missing
    secrets); `from_dict` sets `keyvault = None` when a keyless adapter omits the block
    (else parses with `require_secrets=False`). Added two nullable fields `currencies:
    list[str]` and `from_date: str | None` (mirroring `chains`/`assets`/`company_id`).
  * `extract/__init__.py` — import to register the extractor.
  * `infra/modules/unity_catalog/variables.tf` — `landing_schemas` +1
    (`nationalbanken`), 11 → 12 entries.
  * Regenerated jobs → `resources/ingest_nationalbanken.job.yml` (its own extraction
    system; shared extraction template).
  * Tests: new `tests/test_nationalbanken.py` (all rates/dates synthetic — rate
    12345.0, dates 1999-12-31/2000-01-01; real currency codes are public identifiers)
    covering the decode core incl. null-drop and the VALUTA×Tid cross, tableinfo parse,
    window filter, client POST-body shape + non-2xx hard-fail, and extract()
    orchestration. Extended `tests/test_config.py` (keyless-parser + scoped-relaxation
    guard) and `tests/test_generate_jobs.py` (16th ingest job).

### JSONSTAT decode approach (the core)

JSON-stat packs an N-dim cube into ONE flat `value` array in row-major order over the
dimensions in `dimension.id` order (last axis varies fastest). The decoder inverts each
dimension's `category.index` (code→ordinal) to ordinal→code, computes row-major strides
(`stride[d] = ∏ size[d+1:]`), then for each flat index derives every axis ordinal
(`(i // stride[d]) % size[d]`) → code, skipping `null` cells. Verified against real
EUR/USD data: `EUR 2017M01D03 = 743.41` (matches the given peg-sanity). Kept generic so
it tolerates the auto-injected `ContentsCode` axis and is reusable for the future DST
PxWeb source.

### The keyless change

`KeyVaultRef.from_dict(require_secrets=…)` + `KEYLESS_ADAPTERS` scope the relaxation
exactly like `PIVOT_ADAPTERS` scopes `key_field`: only `nationalbanken` may omit the
vault or carry empty secrets; kraken/pleo/etc. still hard-fail on empty/missing secrets
(guarded by `test_keyless_relaxation_is_scoped_to_keyless_adapters` and the existing
`test_kraken_requires_keyvault_and_endpoint`). `keyvault = None` is already a supported
state for file-drop sources (economic/koinly), so the load path needed no change — I
grepped `extract_load.py`/`autoload.py`/`write/` and confirmed none read `.keyvault`.

### Self-review

Read my own diff first. The keyless logic is scoped and the existing kraken guard
still fires. The extractor separates a pure, exhaustively-tested core from the two I/O
calls. One edge I added a test for: an empty backfill window (from_date after every
banking day) lands nothing and makes NO data POST (an empty Tid set would be rejected
by the API). Then ran the checks:
  * `python -m pytest -q` → **380 passed** (was 351 before; +29 new: 22 in
    test_nationalbanken + 7 config/jobs additions/updates).
  * `python scripts/generate_jobs.py --check` → "job resources are up to date".
  * `terraform fmt -check -recursive modules/unity_catalog/` → exit 0; `git diff`
    confirms `landing_schemas` is +1 (`nationalbanken`). Did NOT run `validate`/`plan`/
    `apply` — no provider init here and infra apply is main's call.

Everything green; no invented problems.

### What warrants review / follow-up

  * The generated `ingest_nationalbanken.job.yml` still pins `azure-keyvault-secrets` +
    `azure-core` (the shared extraction template does), though a keyless source never
    imports them — the nationalbanken extractor calls no secret getter. Harmless (a few
    seconds of unused pip install per run) but genuinely wasteful; a follow-up could
    teach `generate_jobs.py` to drop the azure libs for `KEYLESS_ADAPTERS`. I left the
    template uniform rather than fork it, since the plan's DoD didn't ask for it.
  * `decode_jsonstat` is the reusable PxWeb helper the lead flagged for the future DST
    source; it lives in the nationalbanken module today. When DST lands, lift the pure
    decode/tid helpers into a shared `pxweb`/`jsonstat` module.
  * LIVE PROOF IS MAIN'S: I did NOT deploy the bundle and did NOT run any job or
    warehouse query. The value-array mapping and host-reachability-from-Databricks that
    the lead flagged for review still need a live run — main does the live-proof.

### Commit

Committed on `feature/nationalbanken-fx` (NOT pushed).
