# Diary: Grundfos PD↔IIR local end-to-end pipeline

Goal: build the **local** end-to-end pipeline for the Grundfos PD↔IIR company
matching project — the final local product Benny prioritised. One run that reads the
source extracts, cleans with Module 1 (geo) + Module 2 (name) as integrated pipeline
STEPS, runs the firm-grain matcher on the cleaned data, and writes ONE combined
output file (AUTO + REVIEW). ADF and the global world are explicitly out of scope.
Built on branch `feat/base-files` (not merged to main yet).

## Step 1: Refine requirements with Benny and lock §13

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Projekt: Grundfos PD↔IIR firma-matching. [...] OPGAVEN BENNY HAR
VALGT: byg den **lokale ende-til-ende pipeline** — det endelige produkt (defineret i
checkpoint 2026-06-20). ÉN kørsel der: læser kildeudtræk → renser med M1+M2 som
integrerede pipeline-TRIN (ikke separate kørsler) → kører firma-grain matcheren på
renset data → skriver ÉN samlet output-fil (klar til senere Snowflake-load).
Append/inkrementel. ADF kommer SENERE [...] DIN ROLLE: refinér dette til konkrete krav
og UDFORDR Bennys/mine antagelser før der bygges. [...] Implementér ikke selv — når
kravene er låst med Benny, kør builder."

**Interpretation:** Refine the local-pipeline idea into concrete, locked requirements
by asking Benny sharp one-at-a-time questions, then hand a builder a precise brief.
Do not implement.

**Inferred intent:** Get an unambiguous contract for the orchestration build so the
builder ships exactly the local product Benny wants, with auto-precision preserved,
and nothing speculative (ADF, global, history) creeping in.

### What I did
Read the two truth files (`command-deck/.../status.md`, `docs/requirements.md`) end to
end and verified repo state: I'm in a worktree off `feat/base-files`, 5 commits ahead
of main, all M3 work unmerged; 574 tests green; holdout census 450/450 = 100%
auto-precision. Read the four runners (`run_base`/`run_firms`/`run_match`) and
`src/matcher/crosswalk.py` to see what already exists.

Asked Benny four questions (Danish, one at a time). Answers:
1. Build on `feat/base-files`, merge together later (single dev).
2. ONE combined output file (AUTO + REVIEW, `decision` column); two-table split
   deferred to ADF time.
3. REVIEW is local-only / calibration; AUTO = the production deliverable; nothing
   downstream depends on REVIEW being actioned.
4. PD-side grain but **no history**: full rebuild + overwrite every run. The original
   append-only crosswalk with valid-from/to (Q-A, §7.4) is **superseded**. Cosmetic
   schema lock I took myself: drop `valid_to`, rename `valid_from` → `run_date`, keep
   `run_id`.
5. Global world out of scope (data: 0 non-Indian promoters, 84 foreign-awardee rows =
   38 distinct firms = 0.24% of PD).

Locked it in `docs/requirements.md`: marked Decision A superseded, added the matching
roll-up checkbox as superseded, and wrote a full new **§13 Local end-to-end pipeline**
(scope, boundaries, the one-file output, run semantics, the schema change, REVIEW
local-only, verification, decisions, acceptance criteria).

### Why
The pipeline build is orchestration + a small schema change + the combined output —
not a matcher rewrite. The questions surfaced one real correction (Benny dropped the
incremental/SCD2 model entirely, which removes the only genuinely new logic I'd
spotted as missing) and several scope cuts (global out, review inert). Locking §13
makes the builder brief unambiguous.

### What worked
The four stages already exist and are validated, so the build is genuinely small.
Verifying repo state against status.md up front confirmed the status file is accurate
(branch, commits, test count all matched).

### What didn't work
A key finding I raised early — that append-only / valid-from-to is specified (§7.4)
but **not implemented** (each run writes a fresh file, `valid_to` always empty) — was
moot: Benny withdrew the incremental requirement, so the gap is no longer a gap. No
errors; repeated transient 529 overload during the question loop, recovered.

### What I learned
The "append/inkrementel" framing in the original task brief was an assumption, not a
locked requirement — when challenged, Benny chose full-rebuild-overwrite. Worth
challenging carried-forward framing before treating it as a constraint.

### What was tricky
The original brief said "ÉN samlet fil" while the iir-sap pattern Benny himself
borrowed from points at a two-table split (TBL_MATCHES / TBL_REVIEW_CANDIDATES). Resolved
by deferring the split to ADF time (decision C) and keeping one file locally.

### What warrants review
`docs/requirements.md` §11-A (now marked superseded) and the new §13 — confirm the
schema change (drop `valid_to`, `valid_from`→`run_date`, keep `run_id`) and the
no-history semantics read as intended.

### Future work
Builder ships the orchestration. After it lands: global world (parked), then ADF
deployment in NightSky (iir-sap pattern), both separate tracks.

## Step 2: Builder builds the orchestration

**Author:** builder

### Prompt Context

**Verbatim prompt:** "You are building the **local end-to-end pipeline** for the
Grundfos PD↔IIR company-matching project. Work in the worktree at the
grundfos-iir-matching repo, on branch `feat/base-files` [...] The job (orchestration
+ a small schema change — NOT a matcher rewrite): 1. A single orchestrating entry
point (e.g. `run_pipeline.py` + a small `src/pipeline/` module if it helps) that
chains, in one command, end to end on the **Indian world only**: clean → firms →
match → output: ONE combined file [...] 2. The schema change (§13.4) on the
firm-grain crosswalk: Drop `valid_to` entirely. Rename `valid_from` → `run_date`.
Keep `run_id`. Apply the same change to the occurrence-grain path [...] if cheap.
[...] Verification (HARD requirement — auto-precision must not fall): Run the full
pipeline end to end [...] Verify auto-precision is unchanged against BOTH the
700-pair ground truth and the blind holdout census (450 pairs). [...] Do NOT commit."

**Interpretation:** Add a single orchestrating entry point that glues the four
already-built, already-validated stages into one Indian-only command, plus the
cosmetic §13.4 schema change on the crosswalk. Do not touch the matcher logic or
thresholds. Prove auto-precision did not fall against GT + holdout, keep 574 tests
green plus new tests, prove determinism, leave it uncommitted.

**Inferred intent:** Ship the local product Benny prioritised as thin glue over the
validated stages, with hard evidence that nothing regressed — the whole point of the
brief is that the matcher stays byte-for-byte the production logic.

### What I did
Read the contract (`docs/requirements.md` §13, §7, §11-A) and the four runners +
their modules (`run_base/run_firms/run_match`, `base_build.runner`,
`base_build.firms_runner`, `matcher.runner`, `matcher.crosswalk`). Established the
baseline FIRST, from raw sources, into a scratch out dir: 678 AUTO_CONFIRM, GT
firm-grain auto-precision 99.0% (378/382), recall 96.7%, 700/700 GT pairs mapped;
holdout per-route 401/401 (route1_strong_name) and 49/49 (route2_twin_geo) = 100%.
The holdout precision is measured by joining the IRREPLACEABLE
`holdout_firms_sample_LABELLED.csv` (450 pairs, all label=1) to
`holdout_firms_key.csv` (route tags) and checking each identity is still
AUTO_CONFIRM in the fresh crosswalk — I wrote a read-only `verify_holdout.py` in
scratch for this (the committed `scratch/_verify_holdout_firms.py` checks
blindness/determinism, not the precision number).

**Schema change** in `src/matcher/crosswalk.py`: dropped `valid_to`, renamed
`valid_from`→`run_date` in BOTH `CROSSWALK_COLUMNS` (occurrence grain) and
`CROSSWALK_FIRMS_COLUMNS` (firm grain), and renamed the `valid_from` parameter to
`run_date` in `build_crosswalk` + `build_crosswalk_firms`. Propagated the rename
through `src/matcher/runner.py` (`run`, `run_firms`, and the determinism docstring).
The occurrence-grain alignment was cheap (same file, same edit), so I did it — both
crosswalks now end `...,run_id,run_date`.

**Orchestrator**: new `src/pipeline/` package (`__init__.py`, `orchestrator.py`) and
root entry `run_pipeline.py`. `orchestrator.run_pipeline(run_id)` chains, in-process:
(1) clean — reuses `base_build.runner` to build ONLY the Indian `iir_base`/`pd_base`
(skips the global non-Indian/foreign-awardee files `runner.main` also writes — out of
scope §13.2); (2) firms — reuses `base_build.firms`; (3) match+output — calls
`matcher.runner.run_firms(run_id, run_date)`, whose `crosswalk_firms.csv` IS the one
combined product file. It honours `GRUNDFOS_DATA_DIR`/`GRUNDFOS_OUT_DIR` (reused from
`base_build.runner`) and pins `run_date` via a fixed `--run-id`. Returns a
`PipelineResult` dataclass for tests/logs.

**Tests**: added `tests/test_pipeline.py` (3 hermetic: product-file constant, stamp
resolution reproducible/timestamp; 2 integration that run the WHOLE pipeline from real
sources into a tmp dir and assert the one-file/§13.4-schema/overwrite/determinism
criteria, skipped when sources absent), a `test_firm_crosswalk_schema_no_history_columns`
in `tests/test_matcher_firms.py`, and updated the `valid_to` assertion in
`tests/test_matcher_crosswalk.py` to assert `valid_to`/`valid_from` gone + `run_date`
present.

Single command:
`GRUNDFOS_OUT_DIR=output python run_pipeline.py --run-id RUN_GRUNDFOS`.

### Why
The brief is explicit that this is glue, not a rewrite — so the orchestrator calls the
existing builder functions directly rather than re-implementing or even shelling out to
the runners. Building the baseline before touching anything gave me the exact numbers
to prove "auto-precision did not fall" rather than asserting it. Routing the match
stage through the existing `run_firms` (instead of re-driving `build_crosswalk_firms`)
means the product file and the GT validation report come from the identical code path
that was holdout-validated.

### What worked
End-to-end on the first orchestrated run the numbers matched the baseline exactly:
678 AUTO, GT 99.0% (378/382), recall 96.7%, 700/700 mapped; holdout 401/401 + 49/49 =
100%. Determinism is clean — two runs with `--run-id RUN_PIPE_TEST` produced
byte-identical `crosswalk_firms.csv`, `iir_base.csv`, `pd_base.csv`, `iir_firms.csv`,
`pd_firms.csv` (sha256 matched on all five). Re-running into a populated dir kept the
row count constant (overwrite, not append). Full suite: 580 passed (574 + 6 new),
including the two integration tests that genuinely exercised the whole pipeline under
pytest (data was present).

### What didn't work
No failures, no errors during the build. The only friction was a tooling mistake of my
own: I first tried `cut -d, -f12` on `holdout_firms_sample_LABELLED.csv` to read the
label column, which mangled the output because address fields contain embedded commas
and quotes — the label distribution came out as a wall of address fragments. Switched
to pandas (`pd.read_csv(...).fillna('')`) and got the clean answer: 450 rows, all
label=1, route1=401 / route2=49.

### What I learned
The "holdout census 450/450" headline is structurally a recall-style check, not a
classic precision check: every holdout label is 1, so per-route "precision" is really
"of the 450 labelled-genuine auto-confirms, how many are STILL auto-confirmed after a
rebuild" — it catches a regression that would silently drop genuine autos, which is
exactly the failure mode the brief guards. The route split (name_score ≥ 96 →
route1_strong_name, else route2_twin_geo) lives in `scratch/draw_holdout_firms.py`, not
in the matcher; the matcher's `rules.py` calls them "route 1 / route 2" in prose.

### What was tricky
The determinism contract for the orchestrator. `matcher.runner.run_firms` already has
the run_id→run_date pinning rule (`REPRO:<run_id>` for a fixed id), but the orchestrator
needs the resolved stamps up front for its own `PipelineResult` and to pass them
explicitly into `run_firms`. I duplicated the resolution in
`orchestrator._resolve_stamps` and pass both `run_id` and `run_date` explicitly, so the
two never diverge — the explicit `run_date` skips `run_firms`' own None-branch. A
hermetic test (`test_resolve_stamps_*`) pins this rule so the duplication can't drift.

### What warrants review
- `src/pipeline/orchestrator.py` — confirm the clean stage deliberately skips the
  global files is the intended reading of §13.2 (it builds `iir_base`/`pd_base` only,
  not `iir_non_indian_base.csv` / `pd_foreign_awardee_base.csv`).
- The schema diff in `src/matcher/crosswalk.py` — both schemas + both build functions;
  and that aligning the occurrence-grain path (`crosswalk_india.csv`) was the right call
  (brief said "if cheap"; it was).
- `tests/test_pipeline.py` integration tests run the real pipeline (~30s) when data is
  present; in CI without data they skip — confirm that's acceptable (matches
  `test_base_build_integration.py` convention).

### Future work
None beyond what Step 1 already parked (global world, ADF deployment). The README does
not mention any runner, so I left it for the lead to decide whether `run_pipeline.py`
should be listed there — it was outside the §13 brief. Not committed, per instruction.

## Step 3: Lock §14 — email signal + final firm-grain source format

**Author:** lead

### Prompt Context

**Verbatim prompt:** "Ny stor opgave. To beslutninger er truffet med Benny siden
sidst, og der er kommet et nyt ENDELIGT kildeformat (det format vi kører i ADF).
KONTEKST 1 — volumen-eksperimentet er afsluttet, konklusion: name_auto BLIVER på 96.
[...] marginal-præcision 25/73 = 34%. [...] Volumen skal komme fra et NYT signal
(email), ikke fra navne-tærsklen. KONTEKST 2 — nyt endeligt kildeformat:
projects_today_company_data.csv (22.707 rk, FIRMA-grain [...] PT_COMPANY_TYPE
=Promoter/Awardee), iir_company_data.csv (20.930 rk, FIRMA-grain, COMPANY_ID NY [...]
CONTACT_EMAILADDRESS). OPGAVEN: 1. NY email-rensning (eget lille modul): isolér domæne
[...] filtrér IKKE-DISKRIMINATIVE domæner (>=3 distinkte firmaer droppes). 2.
base_build OMSKRIVES til de nye firma-grain-filer. 3. Matcher-integration: email-domæne
som KORROBORERENDE signal, ALDRIG standalone." Plus follow-ups: validation = C (regression
re-map + fresh blind email holdout, 678 untouched); no country filter (C); email gate = A
(state required both routes, route (a) domain replaces address, route (b) name min
calibrated).

**Interpretation:** Move the project onto the final firm-grain ADF source files and add
an email-domain corroboration signal that is purely additive on top of the 678 existing
name+geo AUTO. Lock all of it as requirements, then run a builder.

**Inferred intent:** Get more AUTO volume from a NEW, safe signal without weakening the
state-gated precision that carries the product — and without the over-promising that
sank the global world. Keep the validated 678 byte-for-byte untouched.

### What I did
Verified the prior build's tests landed (580 passed, confirmed in the background output).
Inspected the actual new source files on the OneDrive read-only path before forming
questions: PT 22,707 rows (Promoter 16,059 / Awardee 6,648; PT_COUNTRY = 22,173 India,
491 blank, ~40 foreign), IIR 20,930 rows (100% India; `_COUNTYNAME` == `_STATENAME` on
20,592 rows, differences are stale/misspelt states like Orissa/Odisha). Asked Benny three
questions one at a time (validation, country filter, email gate). Locked everything as a
new **§14** in `docs/requirements.md` (new source format + field decisions, email-cleaning
module with DF≥3 drop, base_build rewrite, the two email gate routes with state required,
the additive invariants, validation=C, the closed name_auto experiment §14.6, decisions,
acceptance criteria). Then briefed and launched the builder on `feat/base-files`.

### Why
The new files are the format that will run in ADF, so the rewrite has to happen on real
firm-grain data now, not deferred. Locking the gate design precisely (state required;
route (a) domain replaces the address leg, not added on top; route (b) name minimum
calibrated to a holdout, not guessed) prevents the builder from drifting on the one part
that is genuinely new logic. Inspecting the files first let me make the country-filter and
county-vs-state questions concrete with real numbers rather than guessing.

### What worked
The headers and distributions on disk matched the relayed brief exactly, and two
field questions answered themselves from the data (`_STATENAME` is clean, `_COUNTYNAME` is
noise; foreign PT firms can't pass the state gate anyway, so no country filter is needed).
That let the questions stay genuinely about Benny's risk appetite, not about facts I could
check myself.

### What didn't work
No failures. The repeated transient 529 overloads during the question loop were
environment, not the task — recovered each time and resumed.

### What I learned
The "additive, 678 untouched" framing converts neatly into a testable invariant:
email-enabled AUTO must be a strict superset of email-disabled AUTO with the original rows
identical. I wrote that into §14.4 as a required test so the guarantee is enforced by code,
not just intent.

### What was tricky
The email gate's two routes interact with the existing route-2 (twin+geo). Route (a)
deliberately REPLACES the address leg with the shared domain (state + twin + domain →
AUTO), because adding domain on top of the existing addr requirement would promote ~zero
new pairs — the whole point is new volume. Stating "replaces, not on top" explicitly was
the sharp edge; got Benny to confirm it directly.

### What warrants review
- `docs/requirements.md` §14 in full — especially §14.4 (the two routes + the additive
  invariants) and §14.5 (validation = regression re-map + fresh blind email holdout).
- The feasibility expectation: email is ~hundreds of pairs (PT 26% / IIR 11% usable
  domain; ~300 shared discriminative domains), explicitly NOT a big lever — §14.2 sets
  the expectation so it isn't mis-sold like the global world was.

### Future work
Builder ships §14. After it lands: lead/main runs the regression re-map (report drop-out,
confirm 678 untouched), Benny labels the fresh email-promoted blind holdout, route-(b)
name minimum is calibrated to it. Then global world (still parked) and ADF deployment.

## Step 4: Builder builds the email signal + new source readers

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Repo: C:\claudes_folder\repos\grundfos-iir-matching, branch
feat/base-files (allerede checked out, IKKE flettet til main). [...] En tidligere
builder byggede halvdelen af en email-leverance og stallede på et miljø-problem. Du
færdiggør resten. [...] DIT ARBEJDE (i prioriteret rækkefølge): 1. KERNEN, mangler
helt: matcher email-integration i src/matcher/rules.py + crosswalk.py per §14.4 [...]
2. base_build: verificér firm_build/sources_v2 [...] 3. Tests [...] 4. Kør HELE suiten
grøn." (full brief covered the two AUTO routes, hard invariants, the additive
superset guarantee, and per-route counts.)

**Interpretation:** A previous builder did the new firm-grain source readers
(`firm_build`/`firm_runner`/`sources_v2`), the `email_canon` cleaning module, and the
§13.4 schema rename (`valid_from`→`run_date`), but NONE of the actual matcher email
integration — `rules.py`/`crosswalk.py` had zero email reference. My job: wire the
email-domain corroboration signal into the matcher as two additive AUTO routes,
enforce the hard invariants in code + tests, verify the new base_build runs, and turn
the suite green.

**Inferred intent:** Add a small, safe volume lever (email) on top of the locked
name+geo rule WITHOUT touching the validated thresholds or the existing AUTO set —
provably additive, so Benny can later label a blind holdout of only the NEW pairs.

### What I did

The core was an `auto_route(sig, thresholds)` function in `src/matcher/rules.py` that
returns WHICH gate fired (`national_mega`/`strong_name`/`twin_geo`/`email_twin`/
`email_name_divergent`/none). `classify` now delegates its AUTO decision to it. The
email-free routes are evaluated FIRST and identically regardless of the email toggle,
so email can only ever ADD an AUTO — the additive guarantee is structural, not a test
artefact. Added `shared_domain: bool` to `MatchSignals` (defaults False so every
existing caller/test is unaffected) and two threshold fields to `Thresholds`:
`email_enabled` (master toggle, the superset test flips it) and `email_name_min` (the
route-(b) name floor, provisional 70, commented as CALIBRATE-against-holdout).

Route (a) keeps route-2's twin-key + state + twin name-window `[70,96)` but lets a
shared discriminative domain REPLACE the addr/city leg (not stack on top). Route (b)
rescues a non-twin, name-divergent pair `[email_name_min,96)` when the domain is
identical and state agrees. Both sit inside the `not weak_key` and `same_state`
guards.

`src/matcher/crosswalk.py`: `classify_frame` now reads optional
`pd_email_domain`/`iir_email_domain` (via `_opt_col`, so absent → blank → no email
route), computes `shared_domain`, and emits `shared_domain` + `auto_route` columns.
`CROSSWALK_FIRMS_COLUMNS` gained `auto_route`, `pd_email_domain`, `iir_email_domain`,
`shared_domain`. `src/matcher/candidates.py` `_assemble_firms` now carries the two
email-domain columns through. Rewrote `src/pipeline/orchestrator.py` to drive the new
`base_build.firm_runner` (the new sources are already firm-grain, so the old
occurrence build + de-dup collapses to one "firms" stage).

Tests: `tests/test_email_canon.py` (39, email cleaning: isolation, freemail/telecom
drop, DF=3 cut, name-similar pick, cross-source DF builder),
`tests/test_matcher_rules.py` (+12, both routes + invariants + tunable min + toggle),
`tests/test_matcher_email.py` (frame-level + the data-backed additive superset
invariant on the real firm files), `tests/test_firm_base_integration.py` (new-format
base build on real data), and re-pointed `tests/test_pipeline.py` at the new
filenames so its integration runs WITH data.

### Why

The matcher email integration was the missing KERNEN. Routing the AUTO decision
through a single `auto_route` made the additive-superset invariant provable by
construction (email branch is unreachable until all email-free branches return), which
is exactly the §14.4 guarantee Benny insisted on.

### What worked

The base_build the previous builder left actually runs clean on the real new files:
`firm_runner` produced 20,930 IIR / 22,707 PT (16,059 promoter / 6,648 awardee) firms
— exactly the §14.1 counts — each carrying the cleaned `email_domain`, with 202 shared
discriminative domains across sources (contract said ~300). The full pipeline runs end
to end and is byte-identical across two fixed-`--run-id` runs (md5 da81b127…).

### What didn't work

Two self-inflicted test failures, both my unrealistic example data, not the code:
1. `test_classify_frame_reads_shared_domain` asserted AUTO for "GENSOL ENGINEERING" vs
   "GENSOL GROUP" — but `name_score` of that pair is 53.3, BELOW the twin floor 70, so
   route (a) correctly did not fire (`assert 'REVIEW' == 'AUTO_CONFIRM'`). Route (a)
   replaces the *address* leg, not the *name window* — a 53 name is a different firm.
   Fixed by using "GENSOL ENGINEERING" vs "GENSOL ENGINEERING GROUP" (~93).
2. The data-backed superset test joined on a non-unique identity key and so compared
   the wrong rows (`assert 'REVIEW' == 'AUTO_CONFIRM'`). Fixed by comparing email-on
   vs email-off POSITIONALLY (both are `classify_frame` over the same `cand` frame, so
   they share the row index) instead of a fragile key join.

Also caught a mislabelled fixture: I called APOLLO TYRES LIMITED/LTD a "strong_name"
AUTO, but it scores 88.9 (< name_auto 96), so it was itself an email promotion —
making the row identical on both sides fixed it.

### What I learned

The email uplift on the NEW data is **6 net new AUTO pairs** (2 route-a `email_twin`,
4 route-b `email_name_divergent`) on top of 2,512 email-free AUTO. Tiny, exactly as
§14.2 framed it ("small, safe signal"). The 678 figure in the brief is the OLD-format
count; the new firm-grain sources give a different baseline (2,512), so the invariant
to hold is the SUPERSET, not a literal 678. The promoted pairs are visibly good
(SUPRIYA LIFE SCIENCE / SUPRIYA LIFESCIENCE sharing supriyalifescience.com; AUTOLIV
INFLATORS INDIA / AUTOLIV INDIA sharing autoliv.com) — same-state, shared
discriminative domain.

### What was tricky

Keeping GT validation email-FREE was a deliberate call, not an oversight:
`gt_to_firm_candidate_frame` does not copy `email_domain` into the candidate frame, so
`shared_domain` is always False there and the GT report stays the email-free
regression baseline (§14.5 part 1). I added an explicit docstring note so a future
reader doesn't "fix" it. The fresh blind email holdout (§14.5 part 2) is the
authoritative measure and is main+Benny's job.

### What warrants review

- `src/matcher/rules.py` `auto_route` — confirm the email branch is genuinely
  unreachable when `email_enabled=False` (the additive guarantee). The test
  `test_email_disabled_falls_back_to_pre_email_rule` pins it.
- `src/matcher/crosswalk.py` `classify_frame` — the `_opt_col` email reads (safe when
  columns absent) and the new emitted columns.
- `tests/test_matcher_email.py::test_additive_superset_invariant_real_firms` — the
  data-backed proof; positional comparison, not a key join.
- The route-(b) `email_name_min=70` is PROVISIONAL — must be calibrated to the blind
  holdout before this is trusted in production.

### Future work

Not my job (explicitly main+Benny's): the §14.5 validation — regression re-map of the
old GT(700)+holdout(450) onto the new firm-grain data (report drop-out, confirm the
existing AUTO untouched), and generate + label the fresh blind holdout of the 6
email-promoted pairs, then calibrate `email_name_min`. The matcher now PRODUCES those
pairs (flagged `email_twin`/`email_name_divergent` in `crosswalk_firms.csv`) so the
holdout can be generated. Suite: **625 passed, 16 skipped** (the 16 are the OLD-format
integration tests — `test_base_build_integration`, `test_coverage_integration`,
`test_name_canon_integration` — which target the retired occurrence-grain code against
source files that no longer exist; left skipping, not rewritten, as out of scope for
the email leverance).
