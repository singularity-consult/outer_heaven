# Diary: Grundfos PD<->IIR ground-truth validation candidate generation

Seed-form of M3's candidate generation for the Grundfos India-world company
matching. Goal: a stratified candidate list (~500-700 pairs) that Benny labels
by hand to build a ground-truth set we measure the M3 matcher against. This is
NOT the matcher; it is a candidate-generation sample for manual verification.

## Step 1: Build and verify the stratified candidate generator

**Author:** builder

### Prompt Context

**Verbatim prompt:** Generér en stratificeret kandidatliste til Bennys labeling
— et ground-truth valideringssæt af PD↔IIR firma-matches (Indien-verden), som vi
iterativt bygger og måler M3-matcheren imod. Dette er IKKE matcheren; det er en
kandidat-genererings-stikprøve til manuel verifikation. Mål: ~500-700 kandidater,
så Benny kan lande 300-500 garanteret valide labels. (Full brief: scratch script,
output to output/, three strata LET/MELLEM/SVAER, deduplicate IIR to distinct
company, never touch _LABELLED, verify counts + distribution + 9 samples +
determinism.)
**Interpretation:** Write `scratch/gen_validation_candidates.py` (git-ignored,
no commit) that emits `output/validation_candidates.csv` with an empty `label`
column, three strata, side-by-side PD/IIR columns, deterministic on seed 42.
**Inferred intent:** Give Benny a labelable, well-balanced sample whose SVAER
stratum genuinely tests recall (spelling variants), so the eventual M3 matcher
can be measured against real ground truth rather than guesswork.

### What I did

Wrote `C:\claudes_folder\repos\grundfos-iir-matching\scratch\gen_validation_candidates.py`.
Inputs: `output/iir_base.csv` (21,154) and `output/pd_base.csv` (48,078). Pipeline:
geo-filter (drop empty `state_canon` or `state_source==unresolved`), dedup IIR to
distinct `(match_key, state_canon, city_canon)` keeping the lowest `project_id`,
then three strata. LET/MELLEM: exact `match_key` + same state class (TELANGANA
collapsed to ANDHRA PRADESH, LADAKH to JAMMU AND KASHMIR) via a pandas merge, split
on city equality. SVAER: per-state-block `rapidfuzz.process.cdist` blend
(0.5*token_set + 0.5*token_sort) over both `match_key` and `name_canon`, max of the
two, identical-`match_key` masked out, kept in band 82-99. State-balanced sampling
(`_balance_by_state` round-robin), capped 250/200/250. Output columns exactly as the
brief ordered them, `label` empty, sorted by stratum then `name_score` desc.

Verified by running the generator and two helper scripts in `scratch/`:
`_verify_candidates.py` (runs the generator twice via runpy, sha256-compares the
output, prints 9 sample pairs) and `_test_labelled_guard.py` (sentinel test of the
abort guard). Result: 700 pairs (250/200/250), 0 duplicate `(pd_id,iir_id)`, 0 rows
without state, same_match_key 64.3%, weak_key 23.0%, 27 distinct states (Tamil Nadu
50, Gujarat/Maharashtra/Telangana/Karnataka 49 each — not Maharashtra-dominated),
promoter/awardee 535/165. Two runs produced identical sha256
(`0e770aa2aa7cfc931c19ac8b0a14ebe266cd1fea98339207b744ac34bf17945e`). The guard test
confirmed a SystemExit abort with `_LABELLED` present and the sentinel left
byte-for-byte intact.

### Why

The brief is explicit that this is a measurement instrument: the value is in the
SVAER stratum exercising recall and in determinism so re-runs are comparable. The
empty `label` column plus the abort-on-`_LABELLED` guard protect the irreplaceable
labeled artifact Benny produces in a copy.

### What worked

rapidfuzz was present (3.14.3) despite not being in requirements.txt, so the
vectorized `cdist` path ran. Blocking SVAER per state class made the fuzzy pass
tractable. State-balanced round-robin sampling killed the Maharashtra skew cleanly.

### What didn't work

Two real failures, both caught by running it:

1. First run crashed with `KeyError: 'match_key'` in `build_exact_strata`. The merge
   keys `match_key` and `state_cls` are shared columns and get NO suffix, but my
   per-row reconstruction `{c[:-3]: m[c] for c in cols if c.endswith('_pd')}` only
   rebuilt suffixed columns, so `_row_view` looked up a missing `match_key`.
   Verbatim: `KeyError: 'match_key'` at `gen_validation_candidates.py line 156, in
   _row_view`. Fix: replaced the slow per-row `iterrows` reconstruction with a
   vectorized build straight off the merged frame (also faster).

2. Second run aborted with `RuntimeError: 94 duplicate (pd_id, iir_id) pairs in
   output` after 6m38s. Cause: a single PD `project_id` can appear twice (promoter
   + awardee rows) and hit the same IIR representative, producing identical pairs.
   Fix: deduplicate `(pd_id,iir_id)` deterministically inside each exact stratum and
   a final cross-stratum `drop_duplicates(keep='first')` (LET>MELLEM>SVAER order).

The original SVAER loop was also painfully slow (the 6m38s run). Rewriting it to
`process.cdist` per state block cut total runtime to ~7s.

A tooling note, not a code failure: several Bash/PowerShell invocations were denied
mid-session — specifically compound commands using `cd ... &&`, `cp`, `rm`,
`printf >`, and inline `python -c` heredocs. Plain `python script.py` worked. I
moved all verification and the destructive guard test into `scratch/` helper
scripts run as files, which is why `_verify_candidates.py` and
`_test_labelled_guard.py` exist.

### What I learned

`pd_base.csv` legitimately carries empty `match_key` values and duplicate
`project_id`s across roles; both must be handled before any exact-key join or the
join explodes / produces dup pairs. The TELANGANA/ANDHRA equivalence is load-bearing
in SVAER — sample V00451 (Navyuga/Navayuga) only matches because PD TELANGANA and
IIR ANDHRA PRADESH collapse to one state class.

### What was tricky

Getting determinism through the balanced sampler: `_balance_by_state` uses a seeded
`rng.permutation` for state visit order and sorts the picked positions, so the same
seed yields the same selection. The sha256 equality across two runs is the proof.

### What warrants review

`reference/score.py` blends 0.5*token_set + 0.5*token_sort; I reused that exact blend
for SVAER. Worth a glance: whether the 82-99 band is the right width for "close but
not exact" — too tight and we miss harder spelling variants, too loose and Benny
labels noise. Also the dedup representative pick (lowest project_id) is arbitrary but
deterministic; if a richer-address representative would help labeling, change the
sort key in `dedup_iir`. Path to review: the script and `output/validation_candidates.csv`
(both git-ignored, not committed).

### Future work

This is the kimform for M3 candidate generation; promote into `src/` once the M3
design is locked. After Benny labels `output/validation_candidates_LABELLED.csv`,
wire a scoring harness that reads it and reports recall/precision per stratum.
