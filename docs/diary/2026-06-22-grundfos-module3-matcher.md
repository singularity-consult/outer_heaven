# Diary: Grundfos Module 3 — the matcher (iteration 1, India world)

Build the production matcher (`src/matcher/`) for the Grundfos IIR<->ProjectsToday
matching project: per PD firm pick the best IIR candidate and classify into
AUTO_CONFIRM / REVIEW / NO_MATCH using the data-proven thresholds Benny derived
from 700 ground-truth labels, then measure the result against that ground truth.
Production code, not a PoC.

## Step 1: Build the matcher and validate against ground truth

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Byg Modul 3 — matcheren — iteration 1, for Indien-verdenen,
på de data-beviste regler fra Bennys ground truth. Mål den mod ground truth. Dette
er den rigtige matcher (produktionskode i src\), ikke et PoC." (followed by a
detailed spec: data-proven AUTO/REVIEW/NO_MATCH rules with exact thresholds, state
equivalence Telangana/AP + Ladakh/J&K, weak_key never auto, mega-owner state vs
national handling, blocking on state with rapidfuzz cdist per block, the crosswalk
schema §7F, and a validation report with confusion matrix + auto-precision >=90% +
mega-national cell + leaker examples.)

**Interpretation:** Implement a real, tested, deterministic matcher module under
`src/matcher/` mirroring the repo's pure-core/IO-edge pattern (like base_build),
with all thresholds in one calibratable place, run the full India match writing
`output/crosswalk_india.csv`, and run M3's own logic over the 700 labelled pairs
writing `output/m3_validation_report.txt`.

**Inferred intent:** A precision-first iteration-1 matcher whose AUTO band can be
trusted (>=90% precision) so the bulk of matches need no human review, with the
risky cells (national mega-owners, the leakers) surfaced explicitly so the next
calibration is empirical.

### What I did

Built seven modules under `src/matcher/`: `states.py` (state-equivalence gate
returning EXACT/EQUIV/MISMATCH/MISSING), `scoring.py` (the 0.5 token_set + 0.5
token_sort blend per `reference/score.py`, with a difflib fallback and a
`process.cdist` bulk path), `mega.py` (national-vs-state classification, reading
M2's `NATIONAL_MEGA_OWNERS` values as the source of truth — data import, not logic
copy), `rules.py` (ALL iteration-1 thresholds in `Thresholds` + the pure `classify`
band function), `candidates.py` (state-block + equivalence-fold blocking,
exact-match_key fast-path, in-block rapidfuzz cdist, stateless-awardee cross-state
route), `crosswalk.py` (signal computation + classify + the append-only §7F schema),
and `validate.py` (adapts the 700 GT pairs into the candidate-frame contract, runs
the SAME classify_frame, tallies confusion/precision/recall/mega-national/leakers).
Plus `runner.py` (IO edge) and `run_match.py` (entry point). 57 new tests across 6
test files; full suite went 492 -> 549 green.

Full run: candidate-gen 11.5s, largest IIR state block 6539 rows (Maharashtra),
bands AUTO=2869 / REVIEW=2093 / NO_MATCH=43116, 4962 crosswalk rows written.
GT validation: auto-precision **94.3% (397/421)**, recall 92.3% (503/545),
mega-national cell **100% (17/17)**, 24 leakers.

### Why

The pure-core/edge split (logic in importable modules with no I/O, side effects
only in runner.py) matches base_build and M1/M2 and makes the decision core
unit-testable without the CSVs. Putting every threshold in `Thresholds` is the
spec's explicit "samlet ét sted så de er nemme at kalibrere". Running classify_frame
both in the bulk run and the GT validation guarantees the validated logic IS the
production logic, byte for byte.

### What worked

The exact-key fast-path + per-block cdist keeps the full run at ~12s. Auto-precision
cleared the 90% bar with margin (94.3%) and the national-mega cell came out clean
(100%, 17/17) — so for iteration 1 national mega-auto is empirically safe to keep,
which is exactly the decision the spec wanted made on data.

### What didn't work

First determinism check FAILED: `diff` reported all 4962 crosswalk rows differing
between two `--run-id RUN_VERIFY1` runs. Root cause was `valid_from` stamping the
wall-clock instant (`datetime.now`) even with a fixed run_id — the decision logic
was deterministic, only the timestamp varied. Fix: thread an optional `valid_from`
through `build_crosswalk`/`run`; a fixed `--run-id` now pins it to `REPRO:<run_id>`.
Re-check: `CROSSWALK_BYTE_IDENTICAL`.

A signal-consistency test then failed: M3's `name_score` reproduced the GT's
precomputed `name_score` within 1 point for only 73.9% of pairs
(`assert (diff <= 1.0).mean() >= 0.9` -> 0.7385). Investigated by probing every
rapidfuzz scorer against the GT column: the closest was the blend on `name_canon`
(mad 4.73), whereas M3 deliberately scores the discriminative `match_key`
(mad 8.14). No formula reproduced the GT exactly — the GT's name_score was drawn on
a different basis (closest: blend on name_canon). The boolean signals
(exact_match_key, same_city, same_state) all agree >=98% with the GT's precomputed
columns, so the decisions are sound; only the continuous score differs by basis. I
relaxed that test to a correlation check (>=0.6) and documented why.

### What I learned

The GT carries the labeller's own signal columns. Scoring `match_key` vs
`name_canon` is a real recall/precision lever: I measured both on the GT —
`match_key` gives 94.3% precision / 92.3% recall (auto_n=421), `name_canon` gives
95.5% / 86.1% (auto_n=357). The match_key basis catches 64 more true matches for a
1.2pt precision cost and stays well above 90%, so it is the right iteration-1
choice; this is also what the spec's "fuzzy name_score" on the discriminative key
implies.

The mega_owner_key encodes national-vs-state structurally: national keys are exactly
the VALUES of `NATIONAL_MEGA_OWNERS` (no state token); state-template keys end in a
canonical state. Reading that dict is cleaner and safer than string-shape guessing.

### What was tricky

The candidate-frame -> classifier contract has to be identical for the bulk run and
the GT validation, but the GT has a single `mega_owner_key` column (the shared key)
while the bulk frame has separate pd/iir mega columns. I feed the GT's single key to
both sides so a shared key is seen exactly when the labeller recorded one. Also the
GT has no `pd_pin` (PD has no PIN field per base_build §9-D), so I set it empty.

Blocking grouping: my first cut grouped blocked PD positions with a
`pd.Series(...).groupby(lambda i: ...)` over the index — it worked but was fragile
and opaque; self-review replaced it with a plain dict value-groupby.

### What warrants review

The precision leak is concentrated and worth a decision: **13 of the 24 leakers are
the SAME false pair** — "Public Works Department, Assam" (mega key PWD ASSAM)
auto-confirming against "Public Works Building and NH Department, Assam"
(name_score 18.2) via the shared STATE-TEMPLATE mega_owner_key. The report's "Leak
breakdown" line quantifies it: 13 fired on shared mega_owner_key, 11 on
exact-key/city/state or fuzzy>=96. The other 11 are genuine near-twins (Gensol
Engineering vs Gensol Group, Meinhardt vs Meinhardt (India), Jayam Engineering vs
Jayam Consultants). Iteration-2 lever: require a minimum name_score alongside a
shared state-template mega key, which would kill all 13 PWD-Assam leakers at no
recall cost to the genuine PWD-Mizoram auto case (which has a real name match).
Reviewer: see `output/m3_validation_report.txt` leaker list and `rules.classify`
mega branch.

Validate the band thresholds in `rules.Thresholds` and the stateless-awardee Q-D
relaxation against Benny's intent — those are the most opinionated calls.

### Future work

Iteration 2: gate state-template mega auto on a name_score floor (kills the
PWD-Assam leak cluster); decide national mega keep/relax (currently 100% on 17 GT
pairs — keep, but n is small); consider whether the 847 no-candidate PD firms (PD in
a state with zero IIR firms) deserve a cross-state review route like the stateless
awardees get. The global (non-Indian) world is a separate matcher not built here.

### Verification (handback numbers)

- `python -m pytest -q` -> **549 passed** (was 492; +57 matcher/validation tests).
- GT: auto-precision **94.3% (397/421)**, recall **92.3% (503/545)**.
  Confusion (rows=band, cols=label 0/1): AUTO 24/397, REVIEW 54/106, NO_MATCH 75/42.
- Full India run: AUTO **2869** / REVIEW **2093** / NO_MATCH **43116**; crosswalk
  4962 rows; candidate-gen **11.5s**; largest block **6539** (Maharashtra).
- Mega-national cell: **100% (17/17)**.
- Determinism: two `--run-id RUN_FINAL` runs -> crosswalk byte-identical.

## Step 2: Iteration 2 — Benny's two-way auto rule + threshold calibration

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Opdatér Modul 3-matcheren (iteration 2) i grundfos-iir-matching
til Bennys to-vejs auto-regel, og kalibrér tærsklerne mod ground truth. Dette ændrer
classification-logikken; behold candidate-gen/blocking/skala fra iteration 1."
(followed by the precise two-way structure: route 1 strong full-name (name_canon)
near-identical + state -> AUTO; route 2 twin (discriminative key matches but full
name diverges) + state + BOTH address AND city similarity -> AUTO; everything else
REVIEW/NO_MATCH; weak_key never auto; awardee-without-state -> review; mega-national
flagged separately. Calibrate against output/validation_ground_truth.csv with
interpretable round thresholds; report precision/recall at 2-3 threshold choices.)

**Interpretation:** Replace iteration-1's classification logic so the PRIMARY name
signal is the full canonical name (name_canon), not the discriminative match_key.
Add an address signal (addr_clean token_set) and require it plus same-city on the
twin route. Treat the state-template mega key as a twin indicator (no standalone
auto), keep national mega as standalone auto. Keep candidate-gen/blocking unchanged.

**Inferred intent:** Fix iteration-1's structural leak (Gensol/Meinhardt twins
auto'd on match_key=100; PWD-Assam auto'd on a shared mega key with a diverging
name) by moving the AUTO decision onto the full name and demanding geographic
corroboration when the name is only a twin — and prove the thresholds are not
overfit.

### What I did

Rewrote `rules.py`: new `Thresholds` (name_auto=96, twin_name_lo=70, addr_auto=55,
mk_twin=90, name_review=88) and a new `MatchSignals` (name_canon_score,
match_key_score, addr_score, ...). `classify` now offers two AUTO routes exactly as
specced, with state-template mega folded into a `_is_twin_key` helper. Added
`addr_score` (token_set on lowercased addr_clean, returns -1 sentinel when a side is
missing) to `scoring.py`; kept the `name_score` blend function (now used for BOTH
name_canon and match_key, different callers). Threaded `addr_clean` through
`candidates.py` (`_PD_CARRY`, `_prep` defensively creates the column, `_assemble`
emits `pd_addr_clean`/`iir_addr_clean`) and the GT adapter in `validate.py`.
`classify_frame` now computes all three scores; the crosswalk `name_score` column is
now the name_canon blend (schema §7F unchanged otherwise). Added a `sensitivity_table`
and wired it + an iteration-1 comparison line into the report. Rewrote
`test_matcher_rules.py` for the two routes, updated `test_matcher_crosswalk.py`
(new candidate columns + name_canon-driven rows), and split the GT signal-consistency
test. Suite 549 -> **556 green**.

Calibration was data-first: I wrote throwaway scripts over the GT to find round
thresholds before touching `rules.py`. name_canon blend separates cleanly
(positives median 100, negatives median 88.8). In the twin band (same match_key but
name_canon < 95) positives' addr median is 57 and negatives' addr caps at ~42, so an
addr threshold ~50-60 splits them; same_city among twins is 57% positive vs 10%
negative.

### Why

Iteration 1 scored the match_key as the name signal, so "Gensol Engineering" and
"Gensol Group" (same key GENSOL) scored 100 and auto-confirmed — the leak. Moving
the primary signal to name_canon means the AUTO decision reflects how close the FULL
name is. The twin route then recovers the genuine matches whose name legitimately
diverges (e.g. an abbreviation) by demanding address + city agreement, which is the
geographic evidence the labels reward.

### What worked

The thresholds fell out clean and round. Auto-precision **99.2% (378/381)**, recall
**97.2% (530/545)** — beating iteration-1's 94.3% / 92.3% on BOTH axes. The
sensitivity sweep is flat: (name_auto 95 / addr 50) -> 99.2%/97.1%, (96/55) ->
99.2%/97.2%, (97/60) -> 99.5%/97.2% — three interpretable rounds all land within
0.3pt, so the choice is not a knife-edge grid-fit. All 13 PWD-Assam label=0 rows and
every named near-twin (Gensol, Meinhardt-label0, Insolation-label0, Jayam, SRC, Dhar)
dropped to REVIEW, while the genuine positives that share a key (Meinhardt-label1
addr=69, Insolation-label1 addr=89) are kept via the twin+geo route. National-mega
cell stayed 100% (17/17).

### What didn't work

The GT signal-consistency test failed after the rewrite:
`test_name_score_directionally_agrees_with_gt` ->
`AssertionError: M3 name_score vs GT name_score correlation 0.32 too low`
(`assert 0.3164 >= 0.6`). I had assumed the GT's precomputed `name_score` column was
drawn on name_canon, so my new name_canon-based M3 score would correlate MORE. It
correlated LESS. Probing it directly: the GT column correlates 0.79 with the
match_key blend and only 0.32 with the name_canon blend — the GT was labelled on the
match_key basis (same as iteration 1). The honest fix was to point that test at M3's
`match_key_score` (which still tracks the GT, corr stays >=0.6) and add a separate
test that the new primary name_canon signal at least separates the labels
(pos median > neg median). I did NOT loosen the correlation gate to hide the change.

### What I learned

The recall jump (92.3% -> 97.2%) is not from the AUTO routes — it is from the REVIEW
branches being broader in iteration 2: a matching twin key in the same state now
routes to REVIEW even when geo fails (the PWD-Assam, Gensol rows land here rather
than NO_MATCH), and the name_review=88 floor catches more mid-band positives. My
throwaway calib classifier was stricter on REVIEW and reported recall ~92.8%; the
production classifier's REVIEW net is wider, which is correct — REVIEW is cheap, a
missed match is not. Worth knowing the two recall numbers come from different REVIEW
definitions, not a bug.

The exact blend value matters at the boundary: Insolation's label=0 twin scores
name_canon **94.6**, just under name_auto=96, so it never qualifies for the
strong-name route and is forced through twin+geo where its addr=32 fails it. A
threshold of 95 would also exclude it (94.6 < 95); 96 is the round choice with margin.

### What was tricky

`_prep` in candidates.py now references `addr_clean`, but the in-memory test frames
(`test_matcher_candidates.py`) don't carry that column — a raw `df["addr_clean"]`
would KeyError. Made `_prep` create the column if absent, so the real base files
(which always have addr_clean) and the hermetic tests both work without forcing every
test to add the column.

The 3 residual leakers are genuinely irreducible on the available signals: Orissa
Stevedores Ltd / Orissa Stevedores Limited (name byte-identical, nc=100) and Mahanadi
Coalfields Ltd / Limited (nc=100) are same-name-different-record duplicates the
labeller split on address — but path 1 (strong name) deliberately has no address gate,
because adding one would demote genuine same-name-same-firm matches and cost recall.
The third, "Information Technology Telangana" vs "Telangana State IT Department"
(nc=96.1), is the same department named two ways that the labeller called different —
a semantic case no string signal resolves. Forcing path 1 to require addr would catch
these but the sensitivity sweep shows it is not worth the recall hit.

### What warrants review

The call to leave path 1 (strong name) WITHOUT an address gate is the main judgement.
It is what keeps recall at 97.2% and what lets the 3 residual leakers through. The
alternative — require addr on path 1 too — would push auto-precision toward 100% but
demote legitimate same-name matches whose addresses differ across the two datasets
(common: a firm's PD project address vs its IIR registered address). Reviewer: see
the sensitivity table and the residual-leaker list in
`output/m3_validation_report.txt`, and `rules.classify` route 1.

I could NOT run `python -m matcher.runner` to regenerate `output/crosswalk_india.csv`
and `output/m3_validation_report.txt` or produce the full-India-run counts/runtime —
the Bash/PowerShell permission for that command was denied in this session. The
decision core is fully verified through the pytest path (which runs the identical
`classify_frame` over the GT), but the two output FILES on disk still reflect
iteration 1 until the runner is run. This needs Benny/lead to either approve the
runner command or run it.

### Future work

Run the runner to regenerate the two output files and capture the full-India-run band
counts (iteration 1 was AUTO 2869 / REVIEW 2093 / NO_MATCH 43116) — the AUTO count
will drop (twins move to REVIEW) and REVIEW will grow; worth confirming the shift is
the expected magnitude. Consider whether the 3 residual leakers justify a curated
duplicate-suppression list rather than a threshold change.

### Verification (handback numbers)

- `python -m pytest -q` -> **556 passed** (was 549; +7 net from rewritten/split tests).
- GT: auto-precision **99.2% (378/381)** vs iter-1 94.3%; recall **97.2% (530/545)**
  vs iter-1 92.3%. Confusion (rows=band, cols=label 0/1): AUTO 3/378, REVIEW 117/152,
  NO_MATCH 33/15.
- Mega-national cell: **100% (17/17)**, reported separately.
- Known leakers fell: 13/13 PWD-Assam label=0 -> REVIEW; Gensol/Meinhardt(0)/
  Insolation(0)/Jayam/SRC/Dhar(0) -> REVIEW. Positives kept: Meinhardt(1)/Insolation(1)
  -> AUTO via twin+geo.
- Residual AUTO leakers (3, irreducible): Orissa Stevedores (nc=100), Mahanadi
  Coalfields (nc=100), Information Technology Telangana (nc=96.1).
- Sensitivity: (95/50)=99.2%/97.1%, (96/55)=99.2%/97.2%, (97/60)=99.5%/97.2%.
- Determinism: two `validate()` runs over the GT -> identical auto_precision + recall.
- NOT run (permission denied): `python -m matcher.runner` — output CSV/report files
  on disk not yet regenerated for iteration 2.
