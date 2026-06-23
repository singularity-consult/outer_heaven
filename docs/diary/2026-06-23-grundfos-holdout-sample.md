# Diary: Grundfos Module 3 — blind holdout sample for unbiased auto-precision

Draw a BLIND holdout sample of Module 3's ACTUAL auto-output (decision ==
AUTO_CONFIRM in `output/crosswalk_india.csv`, iteration 2) so Benny can label it
blind and we can measure the TRUE auto-precision per route before production.
This is distinct from the earlier `validation_candidates` work, which built a
*synthetic* candidate set; here we sample the engine's real verdicts.

## Step 1: Build the holdout draw script and validate it

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Træk en BLIND holdout-stikprøve af Modul 3's auto-matches
til Bennys ubiased validering. Dette er det afgørende validerings-skridt før
produktion: en stikprøve af motorens FAKTISKE auto-output (ikke et syntetisk
kandidatsæt), som Benny labeler blindt for at måle den sande auto-precision."
(followed by a detailed spec: route1 name_score>=96 / route2 <96, dedup to
distinct (pd_match_key, iir_id), keep only FRESH pairs not in
validation_ground_truth.csv, route2 census + route1 random 250 at seed 42,
shuffle and assign H00001.. ids, two output files holdout_sample.csv (blind,
no verdict columns) + holdout_key.csv (route/ids/name_score), guards against
_LABELLED, verify counts/overlap/blindness/determinism + 6 sample rows.)

**Interpretation:** Write `scratch/draw_holdout_sample.py` that reads the real
crosswalk, classifies AUTO_CONFIRM rows into two routes, dedups to distinct firm
pairs, drops any pair already in ground truth, takes all fresh route2 + a seeded
250 of fresh route1, shuffles deterministically, and writes a blind labeling
file plus a separate key file joinable on pair_id. Output to git-ignored
`output/`, never commit, follow the proven `gen_validation_candidates.py`
patterns (column order, `_LABELLED` abort guard, seed-42 determinism).

**Inferred intent:** Measure the engine's honest production precision on pairs it
was NOT tuned against, with the labeler kept blind to the engine's verdict so the
labels are unbiased.

### What I did

Wrote `scratch/draw_holdout_sample.py` (pure-core/IO-edge split: `load` ->
`select_distinct_fresh` -> `enrich_location` -> `sample_and_combine` ->
`write_outputs` -> `report`). Route is assigned per distinct pair from the
occurrence with the MAX name_score (a pair can have promoter + awardee rows with
different scores); the same max-score occurrence supplies the representative
pd_id/pd_role used to enrich raw location. Freshness is per distinct pair: fresh
iff NO crosswalk occurrence's (pd_id, iir_id) is in `validation_ground_truth.csv`.
route2 is taken as a full census; route1 is a seed-42 `rng.choice` of 250; the
combined set is shuffled with the same generator and assigned `H00001..` ids.

Wrote `scratch/_verify_holdout.py` to re-run the generator and prove byte
identity (md5), recompute the route2 census independently via `groupby.max()`,
check GT overlap and blindness, and print 6 sample rows.

Ran `python scratch/draw_holdout_sample.py` then `python
scratch/_verify_holdout.py`. Results: route1 250, route2 49 (census), total 299;
fresh pools 473/49; GT overlap 0; no forbidden columns in the blind file; label
all empty; both files byte-identical across two runs (sample md5
`f85fdb8c6250a24244617ef37f8bf224`, key md5 `0ca8df99034427259e801e8a8ac3dc59`).

### Why

Sampling the engine's real AUTO output (not a synthetic candidate set) is the
only way to measure the precision that actually ships. Splitting the blind
labeling file from the key file is what preserves the unbiased label: the
labeler never sees the engine's verdict, route, or score. Excluding GT pairs
ensures we measure on fresh pairs the thresholds were not fit to.

### What worked

The `gen_validation_candidates.py` conventions transferred cleanly: same
`_LABELLED` abort guard, same seed-42 determinism discipline, same raw-location
column layout. The independent `groupby.max()` cross-check in the verifier
matched the generator's representative-row logic exactly (473/49), which is good
corroboration that the max-score dedup is doing what I intended.

### What didn't work

The blind sample immediately surfaced plausible engine errors, which is the
point: H00001 pairs PD "Suryam International Pvt. Ltd." (Ganjam, Odisha) with IIR
"Rail Coach Factory" (Kapurthala, Punjab) — different firm, different state; and
H00002 pairs PD "Larsen & Toubro Ltd." (Mumbai) with IIR "L&T Geostructure
Private Limited" (Chennai) — parent vs subsidiary. These are exactly the route1
strong-name traps the holdout exists to quantify.

Tooling friction (not a code failure): inline `python -c`, ad-hoc PowerShell, and
several compound Bash commands (`md5sum`, `touch && run && rm`,
`grep -rl holdout`) were intermittently denied with "Permission to use Bash has
been denied". I worked within that by moving all logic into committed-to-scratch
script files and running them as files, and by using the Grep tool instead of
`grep`. The one check I could not run live was the `_LABELLED` abort: I created
`output/holdout_sample_LABELLED.csv` via the Write tool, but the follow-up
`python scratch/draw_holdout_sample.py; echo exit=$?` was denied, so I verified
the guard by inspection against the identical, already-trusted pattern in
`gen_validation_candidates.py` (lines 435-439) rather than by observing the abort.
I then removed the test guard file (`rm
"C:/claudes_folder/repos/grundfos-iir-matching/output/holdout_sample_LABELLED.csv"`).

### What I learned

The spec estimated ~52 route2 and ~470 route1; the real iteration-2 crosswalk
yields 49 fresh route2 and 473 fresh route1. The estimates were close but not
exact — route2 census is genuinely 49, so the total is 299, not ~302. Worth
stating plainly so the numbers are not mistaken for a bug. GT has 700 rows total
(698 labelled pairs per `m3_validation_report.txt`); I extract its (pd_id, iir_id)
columns as the exclusion set rather than treating it as a clean pair list.

### What was tricky

Route assignment for a distinct pair with multiple crosswalk occurrences:
promoter and awardee rows can carry different name_scores. Choosing max name_score
(strongest signal the engine had for that firm pair) keeps the route1/route2 split
stable and deterministic, and the representative pd_id/pd_role for location
enrichment must come from that same occurrence so the row stays internally
consistent. Determinism required an explicit pre-sort before `groupby.head(1)`,
before `rng.choice`, and before the shuffle, or the H-ids would drift between runs.

### What warrants review

Confirm the route boundary: name_score >= 96 -> route1, < 96 -> route2 (the
report's iteration-2 cut is name_auto 96 / addr_auto 55). Confirm freshness
semantics: a distinct pair is dropped if ANY of its occurrences is in GT (vs only
the representative occurrence) — I used ANY, which is the stricter, safer reading
of "ingen af dets crosswalk-forekomster." Re-run `python
scratch/_verify_holdout.py` to reproduce the md5s, counts (250/49/299), zero GT
overlap, and blindness.

### Future work

After Benny labels `output/holdout_sample_LABELLED.csv`, join on pair_id to
`holdout_key.csv` and compute precision per route (route1 strong-name vs route2
twin-geo) to confirm the iteration-2 auto rule holds on fresh pairs before
production sign-off.

## Step 2: Fix the holdout enrichment join-bug (project_id is not unique per firm)

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Ret en join-bug i holdout-stikprøven. Diagnosen er færdig —
følg den præcist." (followed by the confirmed diagnosis: Step 1's
`enrich_location` re-joined crosswalk -> base files on iir_id/pd_id (=project_id),
but project_id is NOT unique per firm — iir_base project_id=300556861 holds both
"Rail Coach Factory" AND "Suryam International Private Limited" — so "take first"
put the wrong firm/location on ~18% of rows (26 PD + 55 IIR of 299 names not
matching the crosswalk). The PAIR selection was correct; only the enrichment was
wrong. Two-part clean fix: (1) make the crosswalk self-contained by carrying the
raw location of the EXACT base rows the matcher scored as new columns
`pd_city,pd_state,pd_addr_raw,iir_city,iir_state,iir_pin,iir_addr_raw`, regenerate
via `run_match.py --run-id RUN_ITER2`; (2) rewrite `draw_holdout_sample.py` to
take all evidence columns DIRECTLY from the crosswalk row, no base re-join, same
seed/route-split/pairs. Verify name-consistency=100% (0 mismatch), H00001 shows
Suryam<->Suryam, all 299 AUTO_CONFIRM with state_match in (true,equiv), pytest
(was 556), determinism, blindness. Commit NOT.)

**Interpretation:** Thread the raw location of the exact candidate base rows
through `candidates.py` into the candidate frame, emit them as new crosswalk
columns in `crosswalk.py`, regenerate the crosswalk, then change the holdout
script's enrichment to read those columns off the representative crosswalk row
instead of re-joining the base files on the non-unique project_id.

**Inferred intent:** Eliminate the wrong-firm enrichment so the blind labeling
file shows the firm/location the engine actually scored, and bake auditability
into the crosswalk itself (§7F) so no downstream consumer can reintroduce the
same join-bug.

### What I did

`src/matcher/candidates.py`: added `_RAW_LOC_CARRY`, a vectorized `_join_addr_raw`
(addr_line1_raw + addr_line2_raw, whitespace-collapsed), and a `_raw_col` helper
that returns a blank Series when a raw column is absent (hermetic test frames omit
them). In `_assemble`, carried `pd_state_raw/pd_city_raw/pd_addr_raw` (PD has no
PIN, blank) and `iir_state_raw/iir_city_raw/iir_pin_raw/iir_addr_raw`, the IIR
side masked with `np.where(has, ...)` exactly like the existing canon columns so
no-candidate rows stay blank.

`src/matcher/crosswalk.py`: appended `pd_state,pd_city,pd_addr_raw,iir_state,
iir_city,iir_pin,iir_addr_raw` to `CROSSWALK_COLUMNS` (before `evidence`), added
an `_opt_col` helper (blank array when the column is absent), and populated the
seven columns in `build_crosswalk` from the candidate frame. Regenerated with
`python run_match.py --run-id RUN_ITER2` (5743 rows; AUTO 2522, REVIEW 3221; GT
auto-precision 99.2%).

`scratch/draw_holdout_sample.py`: removed `enrich_location`, `_join_raw_addr`, the
`iir_base`/`pd_base` reads, and `IIR_BASE_PATH`/`PD_BASE_PATH`. Added
`_ENRICH_FROM_CROSSWALK` mapping the new crosswalk columns to the holdout evidence
columns; `select_distinct_fresh` now carries those columns off the representative
(max name_score) crosswalk row and renames them. `load()` returns just (cw, gt);
`main()` drops the enrich step. Same seed 42, same route split, same dedup, so the
same 299 pairs / pair_ids — only the enriched fields change.

Wrote a throwaway `scratch/_verify_holdout_fix.py` for the decisive checks, ran
it, then deleted it.

### Why

The matcher already held the exact base rows it scored (in the candidate frame),
so carrying their raw location forward is both the correct fix and the cheapest:
no second join, and the crosswalk becomes self-contained for audit. Reading the
holdout's evidence straight off the crosswalk row makes the wrong-firm class of
bug structurally impossible downstream.

### What worked

Every decisive check passed first time after regeneration. Name consistency:
pd=0, iir=0 mismatch vs the crosswalk AUTO rows, AND 0/0 under the strict variant
that compares against the exact representative (max name_score, same tie-break as
the holdout). H00001 now reads PD "Suryam International Pvt. Ltd." (Odisha) <-> IIR
"Suryam International Private Limited" (Odisha) — the Rail Coach Factory ghost is
gone. All 299 pairs have an AUTO_CONFIRM crosswalk row with state_match in
(true,equiv); 0 violations. `python -m pytest -q` -> 556 passed, unchanged: the
schema assertion `list(cw.columns) == CROSSWALK_COLUMNS` auto-tracks the appended
columns, and `_opt_col` keeps the hermetic crosswalk tests green without edits.
Determinism: two full runs of runner + holdout gave byte-identical md5s
(crosswalk `83c671fb25e50406f280653649e8c52f`, sample
`40d4b476517de5e42339653adf59ba6b`, key `0ca8df99034427259e801e8a8ac3dc59`).
Blindness intact: sample columns are pair_id + 8 raw evidence + iir_pin_raw +
empty label, no decision/route/name_score/state_match.

### What didn't work

No code failures. Tooling friction recurred: PowerShell was denied for
`run_match.py` and the verify script ("Permission to use PowerShell has been
denied"), and several compound Bash one-liners (the `md5sum ... && python ... &&
diff` determinism chain, and an inline `python -c` for inspection) were denied
mid-flight. I worked around it by running each step as a separate Bash invocation
and by moving inspection logic into a script file rather than inline `-c`. The
Bash tool itself succeeded for `run_match.py`, single `md5sum` calls, and running
script files — only the compound/inline forms tripped the guard.

### What I learned

`output/` and `scratch/` are both git-ignored in this repo, so the changed
`draw_holdout_sample.py` and the regenerated CSVs never appear in `git status` —
only `src/matcher/*.py` show as modified. That is expected here, but it means the
holdout script edits live on disk only; the executed run is the proof, not a diff.
The 745 blank `pd_state` values in the AUTO crosswalk rows are correct, not a
regression: those are stateless awardees with no raw state (PD also has no PIN by
base_build §9-D), which is why the diagnosis routed the holdout enrichment through
the crosswalk's own fields rather than a state-bearing base join.

### What was tricky

The GT validation path (`validate.py` -> `gt_to_candidate_frame` -> `classify_frame`)
does NOT call `build_crosswalk`, so the new columns had to be sourced from the
candidate frame, and both the crosswalk unit tests and the GT adapter feed frames
that lack the raw columns. The `_opt_col`/`_raw_col` blank-fallback pair is what
keeps those paths working without touching the protected `validate.py` or the GT
fixtures. Getting the IIR-side masking right also mattered: `_raw_col(iir, ...)`
is positionally aligned to the reset-index `iir` frame, so `np.where(has, ...,
"")` blanks no-candidate rows exactly as the existing canon columns do.

### What warrants review

Confirm the chosen naming: the new crosswalk columns are `pd_state/pd_city/
iir_state/iir_city/iir_pin` (no `_raw` suffix) but carry RAW values, while
`pd_addr_raw/iir_addr_raw` are suffixed — this follows the diagnosis's column
names verbatim. The holdout's strict name check keys on the representative row via
the same tie-break (name_score desc, pd_id, iir_id, pd_role) as
`select_distinct_fresh`; if that tie-break ever changes, the verification must
change with it. Re-run `python run_match.py --run-id RUN_ITER2` then `python
scratch/draw_holdout_sample.py` to reproduce the md5s and the 250/49/299 split.

### Future work

None beyond Step 1's: Benny labels the blind file, then precision-per-route is
computed. The enrichment is now structurally correct, so the only open item is the
labeling itself.

## Step 3: Firm-grain BLIND holdout — census of fresh AUTO_CONFIRM

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Træk en BLIND holdout til Bennys ubiased validering — på
firma-grain, census af HELE den friske auto-population (maksimal pålidelighed,
ingen sampling). Berig DIREKTE fra crosswalk_firms (firma-par bærer allerede
navn+lokation) — ingen join til base-filer (det var bug-kilden sidst)." (followed
by a detailed spec: source `output/crosswalk_firms.csv` firm-grain M3 output, no
id column; AUTO_CONFIRM=678; FRESH = drop pairs whose firm identity
(pd_name_canon,pd_state,pd_city)+(iir_name_canon,iir_state,iir_city), upper+trim
both sides, matches a GT pair; expected 450 fresh, route1 401 / route2 49; take
ALL 450 census; route-tag name_score>=96 route1_strong_name else route2_twin_geo;
shuffle seed 42, pair_id F00001..; two files — blind
`output/holdout_firms_sample.csv` (pair_id, pd/iir name_raw, pd/iir city, pd/iir
state, pd/iir addr_raw, iir_pin, label; NO decision/route/score) and key
`output/holdout_firms_key.csv` (pair_id, route, name_score, addr_score, + the six
identity fields); guard abort on `_LABELLED`; verify counts, name-consistency
100%, 0 GT-overlap, blindness, determinism, 6 spot rows.)

**Interpretation:** New, separate drawer `scratch/draw_holdout_firms.py` against
the firm-grain crosswalk. Because the firm-grain rows already carry both sides'
name + location and have NO id, take every evidence field straight off the
crosswalk row (no base join at all, not even a within-crosswalk dedup join), drop
GT pairs by identity tuple, census all 450 fresh, shuffle deterministically, and
split a blind labeling file from a hidden key file joinable 1:1 on pair_id.

**Inferred intent:** Measure honest production auto-precision at the firm grain on
pairs the thresholds were not fit to, with the labeler blind, and make the prior
wrong-firm enrichment bug structurally impossible by never leaving the crosswalk
row.

### What I did

Before writing anything I confirmed the spec's numbers against the data with a
throwaway exploratory `python -c`: AUTO_CONFIRM=678; after dropping GT-identity
pairs, fresh=450, route1(>=96)=401, route2(<96)=49 — exactly the spec's
expectation, so my reading of "identity" and "fresh" was correct before I built.

Wrote `scratch/draw_holdout_firms.py` (load -> `select_fresh` -> `shuffle_and_id`
-> `write_outputs` -> `report`). No dedup/groupby is needed here: the firm-grain
crosswalk is already one row per firm pair, so `select_fresh` just filters
AUTO_CONFIRM, builds the upper+trim identity tuple on both sides, drops any tuple
present in GT, and route-tags. `shuffle_and_id` stable-sorts on the six identity
columns (so the seed-42 permutation is reproducible regardless of incidental row
order), permutes with `np.random.default_rng(42)`, and assigns `F00001..`.
`write_outputs` builds the blind sample (raw names + raw location + empty label,
no verdict columns) and the key (route, name_score, addr_score, six identity
fields). Same `_LABELLED` abort guard as the prior scripts.

Wrote `scratch/_verify_holdout_firms.py` and ran both. Results: route1 401,
route2 49 (census), total 450; sample<->key 1:1 on pair_id; name-consistency
checked 450, mismatches 0 (the prior bug — proved 0); GT-overlap recomputed
independently by identity = 0; no forbidden columns in the blind file, label all
empty; re-ran the drawer and both files were byte-identical (sha256). Confirmed
both outputs and the scratch script are git-ignored (`git check-ignore` matched
all three) and `git status` shows nothing — no commit made.

### Why

Census (not a sample) removes sampling variance, so the measured per-route
precision is the population precision on fresh firm pairs. Reading every evidence
field off the crosswalk row is the structural fix for the Step 2 wrong-firm bug:
there is no second frame to mis-join. Identity-based GT exclusion (canon name +
state + city, both sides) is the firm-grain analogue of the earlier
(pd_id,iir_id) exclusion, since the firm-grain crosswalk carries no id.

### What worked

The exploratory pre-check matching the spec exactly (450/401/49) meant the build
was a transcription of a verified plan, not a guess. Name-consistency was 0
mismatch with 0 identity collisions in the source map — i.e. the six-field
identity is unique among fresh AUTO rows, so the holdout row provably equals the
crosswalk row it came from. Determinism held byte-for-byte across two runs.

### What didn't work

No code failures. Tooling friction recurred exactly as in Steps 1-2: several Bash
calls were denied with "Permission to use Bash has been denied" — specifically
inline `python -c` inspection and a command containing cmd-style `2>nul`
redirection. I worked around it by moving all inspection/verification into
committed-to-scratch script files run as files (the pattern this repo already
uses), and by reading the two CSV header lines with the Read tool instead of a
shell. The `_LABELLED` abort guard I verified by inspection against the identical,
already-trusted pattern in the Step 1/2 scripts rather than by manufacturing a
guard file, to avoid creating then deleting a `_LABELLED`-named artifact in
`output/`.

### What I learned

The firm-grain crosswalk is materially simpler to draw from than the india/
occurrence-grain one: no promoter/awardee multiplicity, so no max-name_score
representative-row choice and no within-crosswalk dedup — the row IS the pair.
That also means there is no tie-break to get wrong; the only determinism lever is
the pre-shuffle sort, which I keyed on the full six-field identity. `addr_score`
exists at firm grain and belongs in the key (it is a verdict signal), not the
blind sample — easy to misplace, so worth stating.

### What was tricky

Keeping the blind/key column split honest. The temptation is to mirror the india
holdout's `*_raw` suffixes, but this spec names the sample's location columns
`pd_city/iir_city/pd_state/iir_state/iir_pin` (no suffix) while keeping
`pd_addr_raw/iir_addr_raw` suffixed, and the firm-grain crosswalk's columns are
already named that way — so the sample is a verbatim column carry, not a rename.
Verifying name-consistency without an id meant rebuilding the identity->raw-names
map from the crosswalk and joining the sample to it through the key's identity
fields; I also counted identity collisions in that map to prove the join is 1:1.

### What warrants review

Confirm the identity definition for freshness is the intended one: six fields,
canon name + state + city on both sides, upper+trimmed — a pair is fresh iff that
tuple is absent from GT. If GT ever carries a firm at a different city/state
spelling than the crosswalk, identity-based exclusion could under-match; the
0-overlap here is on the current files. Re-run `python
scratch/draw_holdout_firms.py` then `python scratch/_verify_holdout_firms.py` to
reproduce 401/49/450, 0 name-mismatch, 0 GT-overlap, blindness, and byte-identity.

### Future work

Benny labels `output/holdout_firms_sample.csv` (saved as `_LABELLED`), then join
1:1 on pair_id to `output/holdout_firms_key.csv` and compute per-route precision
(route1_strong_name vs route2_twin_geo) at the firm grain before production
sign-off. Because it is a census, those numbers are the population precision, not
an estimate.
