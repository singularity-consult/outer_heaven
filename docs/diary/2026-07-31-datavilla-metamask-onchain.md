# Diary: MetaMask on-chain source + CoinGecko price source for Datavilla

Add Benny's MetaMask wallet as a new Datavilla source so he OWNS the raw on-chain
transaction layer and can compute his own cost-basis (LIFO/HIFO/average),
trade-performance and what-if scenarios — things Koinly (locked to FIFO) will not
give him. On-chain data alone carries token amounts but no fiat price, so a second
price source (CoinGecko) is built in the same feature to enable the fiat/cost-basis
math downstream in curated.

## Step 1: Brainstorm -> refined requirements + finished build plan + worktree

**Author:** lead

### Prompt Context

**Verbatim prompt:** "BRAINSTORM (ikke byg, ikke forbered worktree) en potentiel ny
datavilla-kilde: Bennys MetaMask-wallet. Du skal UDFORSKE mulighederne, UDFORDRE
Bennys antagelser ... komme tilbage med en anbefalet retning + de åbne beslutninger
han skal træffe." Followed by two coordinator course-corrections: (1) Benny accepted
the Koinly challenge and gave the real purpose — own the raw layer for custom
cost-basis/performance/what-if, Koinly stays the tax truth he files; asked to place a
price layer and land a finished direction. (2) "Alt afklaret af Benny + verificeret
live af drone. Gå fra brainstorm til FÆRDIG byggeplan + forbered worktree (stadig
ikke byg)" with the final verified scope.

**Interpretation:** First produce a challenged, researched brainstorm; then, once the
purpose was clarified and the API surface verified live, convert it into a concrete
build plan for two new extraction sources and prepare the branch/worktree — without
writing implementation code (main spawns a builder on the report).

**Inferred intent:** Benny wants an automated, owned on-chain ledger he can run his
own tax/analytics logic over, decoupled from Koinly's FIFO lock-in. The lead's job is
to keep scope honest (the on-chain layer alone delivers none of his analytics goals
until a price layer + curated math exist) and to map both sources onto the existing
extraction-adapter framework rather than inventing new machinery.

### What I did

Read the extraction framework end to end in the master checkout: `extract/base.py`
(registry + `SourceExtractor` contract), `extract/kraken.py` (HMAC + offset paging +
id-keyed pivot), `extract/enablebanking.py` (self-signed JWT, internal account loop,
stamped `account_uid`, composite key, leak discipline), `config.py` (the whole
`SourceDefinition` model, `EXTRACTION_ADAPTERS`/`PIVOT_ADAPTERS`/`FILE_ADAPTERS`,
`job_group` = `landing.schema`, `IncrementalConfig` reserved-for-JDBC), `autoload.py`
(`_read_plan` writer selection off `history`), the Kraken/Koinly/EnableBanking source
YAMLs, `ingest_kraken.job.yml` (for_each_task shape, one cluster per system), and the
`unity_catalog` Terraform (`landing_schemas` set + `moved` blocks that must not be
disturbed).

Researched and (per coordinator) live-verified the API surface: Etherscan V2
multichain (`https://api.etherscan.io/v2/api?chainid=..&module=account&action=txlist|tokentx`),
its 2026 free-tier cuts (3 calls/s, 100k/day, 1000 records/request, internal-txn
by-block-range removed, ~90% chain coverage with Gnosis moved to paid), and CoinGecko
`market_chart` (keyless free = DKK prices but only ~1 year daily / 1 month intraday;
deep history is paid). Kraken OHLC was rejected as the price source (only lists
Kraken-listed assets; 720-candle depth cap).

Delivered the Koinly challenge (Koinly is a tax-computation product, not a
transaction feed — on-chain gives amounts, never fiat cost-basis), then a finished
direction and a phased build plan. Created the feature worktree:
`git worktree add -b feature/metamask-onchain
C:/claudes_folder/repos/datavilla/.claude/worktrees/metamask-onchain master` off a
clean master at `75d79c2`.

### Why

The framework already has every seam these two sources need — a new extractor is a
registry decorator plus a config shape, not an edit to the runner. Mapping MetaMask
onto EnableBanking's internal-loop + stamped-provenance + composite-key pattern and
CoinGecko onto Pleo's fan-out keeps both sources idiomatic. Verifying the free-tier
limits BEFORE build was required because they decide whether the free plan is viable
(it is, for the 3 chosen chains) and shape the load model (1000-record cap + years of
history => backfill-once-then-incremental, not full-pull-every-run).

### What worked

The purpose reframe held: Benny accepted that MetaMask does not replace Koinly but
adds an owned raw layer, and the real driver (escaping FIFO) is stronger than the
reconciliation angle I first offered. Live verification collapsed scope cleanly —
BNB and Optimism returned "Free API access is not supported for this chain", so they
and Tron were dropped as negligible, leaving 3 EVM chains on one free key.

### What didn't work

My own worktree vanished across the session's midnight boundary: the harness had
pinned me to `.claude/worktrees/agent-adc3b6a22cb809d4c`, and after the date rolled to
2026-07-31 that directory was gone (`fatal: cannot change to '...agent-adc3b6a...':
No such file or directory`). Confirmed via `git worktree list` that only the main
checkout remained and it sat clean on master `75d79c2` — no work lost, because Step 1
had produced only a report, not files. Recreated a non-agent-prefixed worktree so it
survives future session boundaries. This is exactly the failure mode memory warns
about ("worktrees overlever ikke sleep").

### What I learned

`IncrementalConfig` is reserved for JDBC and carries only `watermark_column`; there is
NO runtime watermark STORE wired for extraction sources. So MetaMask's
incremental-by-block cannot reuse existing machinery. The clean design is to derive the
per-chain watermark from `max(blockNumber)` in the source's own raw table at extract
time (extract runs before autoload in `datavilla-extract-load`, so raw holds up to the
previous run) — self-healing, no new state store, empty/missing table => startblock 0 =
full backfill. `job_group` keys on `landing.schema`, so both MetaMask sources
(schema `metamask`) generate into one `ingest_metamask` job and CoinGecko (schema
`coingecko`) into its own, each one cluster spinup.

### What was tricky

Two framework-fit edges the builder must handle. (1) The extraction path REQUIRES a
non-empty `keyvault.secrets` (`KeyVaultRef.from_dict` raises otherwise), but CoinGecko
free is keyless — so either relax that validation or store a free CoinGecko demo key in
vault; recommended the demo-key route (lower blast radius, also lifts the shared-IP
rate limit). (2) Etherscan caps a single (startblock,endblock) query at a 10000-record
window, so backfill must advance startblock to the last block seen and re-query, not
just page offset — the 1000-record page cap alone does not cover it.

### What warrants review

The load-model departure from the "full-pull-every-run" idiom (Kraken/EnableBanking):
MetaMask backfills once then reads `startblock = last-seen block per chain`, relying on
on-chain immutability + SCD2 to absorb overlap. A reviewer should confirm that reading
`max(blockNumber)` from raw is sound given native and token are separate raw tables
(each tracks its own watermark). Also review the composite keys — `(chain, tx_hash)`
native, `(chain, tx_hash, log_index)` token — since the same address on 3 chains makes
`tx_hash` unique only within a chain, mirroring EnableBanking's `(account_uid,
entry_reference)`.

### What was leak-sensitive

On-chain history + wallet address is EnableBanking-class personal financial data. The
address lives in Key Vault (`metamask-wallet-address`), config carries only the secret
name + the chain list, landing-only, never git. All code/tests/diary examples must be
synthetic (address `0xAAAA...`, token `TEST`, amount `12345`, date `1999-12-31`); any
field probe prints field names + counts only, never counterparties or amounts.

### Future work

Phase 1 (build now): EVM-3 on-chain raw adapter (native + token, one Etherscan key,
chain-stamped, SCD2, backfill+incremental-by-block) + CoinGecko latest-year price
source. Phase 2 (Benny's curated logic, not this build): join transaction x
price@timestamp -> fiat, with Koinly-derived spot for deep history and explicit
0-fallback for priceless tokens, then FIFO/LIFO/HIFO/average + trade-performance +
what-if. Derived-discovery of price assets from raw `token_transfers` (Pleo-style
two-stage) is a clean v2 once the on-chain table exists — deferred to avoid a
cross-job dependency in v1.

## Step 2: Build both sources, fix two live-surfaced bugs, prove on-chain + CoinGecko

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Byg to nye datavilla-kilder efter lead's byggeplan: MetaMask
on-chain (byg FØRST — den nye/svære) + CoinGecko priser (anden source, samme branch).
Auth + API-form er verificeret live; du udfører." Followed by coordinator
course-corrections: (1) the first `ingest_metamask` run FAILED — diagnose the
iteration-level errors and fix the root cause in code, re-deploy, re-run, drive it to
green with short repeated `jobs get-run` polls (never a long blocking sleep); (2) once
on-chain is green (rows == distinct keys, no-op on re-run), do CoinGecko, then commit;
(3) all three verified green — commit, and explain in the report whether ERC-20 pricing
was deliberately out of scope.

**Interpretation:** Implement the two extraction adapters + the `chains`/`assets` config
fields + infra + tests exactly to the plan, apply infra to dev, deploy, and LIVE-PROVE
on-chain (row==distinct-key, watermark/SCD2 no-op on re-run) then CoinGecko, fixing
whatever the live runs surface, and commit on the branch without pushing.

**Inferred intent:** A verified, owned on-chain + price raw layer running on the real
dev workspace — not just code that looks right, but code proven to land the wallet's
real multichain history and re-run idempotently.

### What I did

Read the whole extraction framework (base registry, kraken/pleo/enablebanking
extractors, `config.py`, `autoload._read_plan`, `scd2.py`, `generate_jobs.py`,
`secrets.py`, the job templates and the `unity_catalog` Terraform) and built to the
existing seams:

- Added `metamask` + `coingecko` to `EXTRACTION_ADAPTERS`, and two new nullable
  `SourceDefinition` fields: `chains: list[int]` (metamask's EVM sweep) and
  `assets: list[dict]` (coingecko's fan-out list), parsed/validated in `from_dict`
  parallel to `session_key`/`company_id`.
- `src/datavilla/extract/metamask.py`: one multi-chain Etherscan V2 client (base
  `https://api.etherscan.io/v2/api`, `apikey` query auth, paced under 3 req/s),
  looping chains [1, 137, 59144] and stamping `chain`. `parse_result` hard-fails on
  `status != "1"` except the "No transactions found" empty sentinel, and shape-checks
  `result`. Incremental-by-block: `startblock = max(blockNumber)+1` read from the
  source's own raw table via injected `watermark_reader` (missing/empty table -> 0 =
  full backfill). The >10,000-record window is handled by a WINDOW-WALK: a full page
  advances `startblock` to the last block seen and re-queries; the overlap is deduped
  on the composite key.
- `src/datavilla/extract/coingecko.py`: fan-out over the configured `assets`, one
  `market_chart?vs_currency=dkk&days=365` per asset (demo key as `x-cg-demo-api-key`
  header), normalised to one record per `(asset_key, price_date)`.
- Config YAMLs (2 metamask sources sharing schema `metamask`; 1 coingecko source),
  regenerated jobs (`ingest_metamask` for_each concurrency 1, `ingest_coingecko`),
  added `metamask`/`coingecko` to Terraform `landing_schemas`, and wrote
  `test_metamask.py` + `test_coingecko.py` plus config/generate_jobs test updates
  (292 tests green).

Infra: `terraform fmt`/`validate` clean, `plan` was exactly +4/0-change/0-destroy (2
schemas + 2 volumes, no `moved`-block disturbance), applied to dev. Deployed the dev
bundle and ran the jobs serially with short repeated `jobs get-run` polls driven from
a backgrounded until-loop (one completion notification, no long foreground sleep).

### Why

Every seam these sources need already existed — a new extractor is a registry
decorator plus a config shape. Mapping metamask onto the enablebanking internal-loop +
stamped-provenance + composite-key pattern and coingecko onto the Pleo fan-out kept
both idiomatic. Reading `max(blockNumber)` from raw (extract runs before autoload, so
raw holds the previous run) is a self-healing watermark with no new state store.

### What worked

The watermark against a not-yet-existing raw table did exactly the right thing on the
first backfill (table absent -> startblock 0 -> full pull). The intrinsic token key
(below) handled real multi-transfer transactions (a live tx emits up to 6 ERC-20
transfer logs) with zero loss. Final live proof, all `_is_current` rows:

- `raw.metamask.native_transfers`: **1166 rows == 1166 distinct `(chain, hash)`**,
  3 chains. Run `480814180401249` SUCCESS.
- `raw.metamask.token_transfers`: **1230 rows == 1230 distinct
  `(chain, hash, contractAddress, from, to, value)`**, 3 chains.
- Re-run (`1010143997379171`, SUCCESS): both tables **unchanged** at 1166 / 1230 —
  watermark fetched ~0 new blocks, SCD2 no-op holds.
- `raw.coingecko.prices`: **831 rows == 831 distinct `(asset_key, price_date)`**,
  3 assets. Run `49262197087828` SUCCESS.

### What didn't work

The FIRST `ingest_metamask` run (`177942531440258`) FAILED — INTERNAL_ERROR / "Some
iterations failed". Both for_each iterations failed in the SCD2 autoload (the extract
phase and landing had SUCCEEDED — data was on disk), for two DISTINCT root causes I
pulled from `jobs get-run-output` on the child runs:

1. Native (`txlist`): `pyspark ... AnalysisException: [AMBIGUOUS_REFERENCE] Reference
   \`_t_hash\` is ambiguous, could be: [\`_t_hash\`, \`_t_hash\`]` at
   `write/scd2.py:382`. A latent bug in the SHARED SCD2 engine: it aliases the target
   row-hash column to `_t_hash`, which collides with the per-key alias `_t_{key}` when
   a business key is literally named `hash` — which metamask's native key `[chain,
   hash]` is. No prior source had a key named `hash`, so it had never surfaced. Fixed
   by giving keys and the hash DISJOINT alias namespaces (`_tk_` / `_tv_hash`), which
   cannot collide for any key name. This is a real fix to `scd2.py` that benefits every
   future source, not a metamask-local workaround.
2. Token (`tokentx`): `datavilla.write.scd2.Scd2Error: key column(s) ['logIndex'] not
   in the batch for datavilla_dev_raw.metamask.token_transfers`. My plan-carried
   assumption that tokentx returns a `logIndex` was WRONG: the live response has NO
   per-log index. I confirmed this leak-safely from the landed schema (field NAMES
   only): tokentx returns `blockHash, blockNumber, chain, confirmations,
   contractAddress, cumulativeGasUsed, from, functionName, gas, gasPrice, gasUsed,
   hash, input, methodId, nonce, statusRep, timeStamp, to, tokenDecimal, tokenName,
   tokenSymbol, transactionIndex, value` — where `transactionIndex` and `nonce` are
   per-TRANSACTION (identical across a tx's logs), so neither indexes a log. Changed
   the token key to the INTRINSIC combination `(chain, hash, contractAddress, from,
   to, value)` — the token, direction and amount — which distinguishes same-tx
   transfers order-independently (so the window-walk overlap dedups regardless of page
   boundaries) and is faithful to source (no synthetic column).

A second-order gotcha: the failed run had already landed extract files, and re-running
re-extracts (watermark still 0), so the two file-sets would collide as duplicate keys
in one Auto Loader batch. I reset cleanly by deleting the metamask landing subtrees
(`txlist`, `tokentx`, `_ops`) before the re-run — safe because the raw tables did not
yet exist.

### What I learned

Etherscan V2 `tokentx` genuinely has no log-index — the plan flagged this as
"verify from the actual response", and the answer is that identity for a token transfer
must be synthesised from its intrinsic fields. The `from` reserved word works fine as
both a raw column and an SCD2 key because raw tables use Delta column-mapping and
`scd2.py` backtick-quotes every column reference. And the SCD2 alias-collision proves a
general rule: any hardcoded internal alias (`_t_hash`) is a landmine once business keys
are arbitrary source names.

### What was tricky

The window-walk / composite-key interaction. Advancing `startblock` to the last block
seen (inclusive) deliberately re-fetches that block, so within-run dedup is REQUIRED —
and it must dedup on a key that is stable regardless of which page a record lands in. A
stamped per-tx transfer ordinal would NOT be stable across the page boundary (a block
split across the 1000-record cap would re-index differently on the re-query), which is
the decisive argument for the intrinsic-field key over a synthetic index.

### What warrants review

The `scd2.py` alias-namespace fix touches the shared SCD2 engine used by every scd2
source (economic, enablebanking, pleo, corpayone) — the change is internal to the
change-detection join and the aliases are dropped before the merge, and all 292 tests
plus the live metamask merge pass, but a reviewer should confirm no regression for the
existing sources. Also review the token key choice: its only theoretical collision is
two byte-identical transfers (same token/from/to/value) in one tx, which would abort
the merge LOUDLY rather than corrupt silently, and does not occur for a personal wallet.

### CoinGecko asset scope (answer to the coordinator's question)

Native-only in v1 is BY DESIGN, matching the build plan, not a gap in the code. The
plan specifies: v1 prices the three chains' native coins (configured now — ethereum,
matic-network, linea-eth) and DERIVES the ERC-20 list from `raw.token_transfers` AFTER
the on-chain run, configuring only tokens CoinGecko actually lists and OMITTING the
rest (0-fallback for priceless tokens belongs in curated/enriched, not raw). The
extractor's `asset_request` fully supports contract-addressed tokens
(`/coins/{platform}/contract/{addr}/market_chart`, unit-tested), so adding ERC-20
entries is a config-only change. I did NOT populate them because the on-chain table
shows 266 distinct `contractAddress` / 231 distinct `tokenSymbol`, the large majority
of which are spam/airdrop tokens with no CoinGecko listing; per-token contract lookups
against 266 addresses to price a handful of real holdings is exactly the derived,
match-or-omit v2 step the plan deferred to avoid a v1 cross-job dependency. So: capability
present in code, scope intentionally native-only for v1.

### Future work

v2: derive the ERC-20 price asset list from distinct `(contractAddress, tokenSymbol)`
in `raw.metamask.token_transfers`, keep those CoinGecko lists, omit the unmatched (spam)
tokens. Phase 2 curated cost-basis math (FIFO/LIFO/HIFO/average, trade-performance,
what-if) joining on-chain amounts to `coingecko.prices` with Koinly-derived spot for
deep (>365-day) history and explicit 0-fallback for priceless tokens.
