# Diary: Split matcher output — production AUTO-only crosswalk + local REVIEW diagnostic

Grundfos PT↔IIR firm-grain matcher. Today the firm-grain matcher writes ONE file
`output/crosswalk_firms.csv` containing BOTH `decision == AUTO_CONFIRM` (2.518 rows)
and `decision == REVIEW` (2.659 rows), separated only by the `decision` column
(NO_MATCH counted, not written). The final/production solution has NO review
capability, so a single file mixing confirmed and unconfirmed rows risks a downstream
Snowflake consumer treating REVIEW rows as matches.

The change: make `crosswalk_firms.csv` the production deliverable containing ONLY
AUTO_CONFIRM rows, and move REVIEW rows into a separate, explicitly-local diagnostic
file `output/review_candidates.csv` (Benny inspects it once for systematic matcher
improvements; it is never loaded to Snowflake and must NOT be confused with the
iir-sap-style production TBL_REVIEW_CANDIDATES table — different project, different
frame).

Hard constraints: git identity `singularity-consult <benny@singularityconsult.dk>`
(never Co-Authored-By, never Claude as author, never seges.dk); repo has NO remote
(commit only, no push); output/ git-ignored; the LABELLED holdout/gold files in
output/ are IRREPLACEABLE and must not be touched; full suite stays green (baseline
625 passed / 16 skipped); determinism preserved; land on main (89a20ed).

## Step 1: Spec the change and scope the touch points

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "The change: split the matcher output so the production file
contains ONLY confirmed matches. `output/crosswalk_firms.csv` = the PRODUCTION
deliverable = ONLY `decision == AUTO_CONFIRM` rows (currently 2.518). REVIEW rows
(currently 2.659) -> a SEPARATE file `output/review_candidates.csv` — a LOCAL/DEV
diagnostic artifact only, never loaded to Snowflake, documented as such. NO_MATCH
unchanged. After the change, crosswalk_firms.csv must contain ZERO non-AUTO_CONFIRM
rows." (Plus hard constraints and a definition of done — full prompt in the task.)

**Interpretation:** A crisp, already-decided change. No requirement refinement needed
from Benny. My job: verify the touch points, spec tightly, run a builder to ship it
validated, land on main with the correct identity.

**Inferred intent:** Eliminate the ambiguity risk of a mixed-decision production file
before it reaches Grundfos' Snowflake env. Production = AUTO only; REVIEW becomes a
local calibration artifact, decoupled from any production workflow.

### What I did

Read the write path and verified the touch-point list rather than trusting it:
- `src/matcher/crosswalk.py` — `build_crosswalk_firms` (line 320) classifies and
  returns a frame of AUTO + REVIEW rows in `CROSSWALK_FIRMS_COLUMNS` order, plus a
  `counts` dict (AUTO / REVIEW / NO_MATCH). It does NOT write files.
- `src/matcher/runner.py` — `run_firms` (line 158) calls `build_crosswalk_firms`,
  then writes the whole frame to `crosswalk_firms.csv` (line 204-205). THIS is the
  single write point that needs splitting.
- `src/pipeline/orchestrator.py` — `run_pipeline` calls `run_firms`; docstrings
  (lines 1-29, 50, 124-139) describe "ONE combined product file (AUTO + REVIEW)".
- `run_pipeline.py` docstring lines 11-18 say the same.
- `docs/requirements.md` §13.3 / §13.5 / §13.8 and overview lines 580/584 describe
  the one-combined-file contract. ("§7F" in the task refers to the self-contained
  raw-location property, which does NOT change — only the one-file contract does.)
- Tests: `tests/test_pipeline.py` lines 90-99 assert AUTO+REVIEW both live in the
  product file; `tests/test_matcher_crosswalk.py` and `tests/test_matcher_firms.py`
  assert at the BUILD level (`build_crosswalk*` returns AUTO+REVIEW, len == AUTO+
  REVIEW). The build functions stay unchanged, so those build-level assertions
  remain valid — only the pipeline/runner file-write expectations change.

Decided the split point: keep `build_crosswalk_firms` returning AUTO+REVIEW (its
build-level tests depend on that and the frame is the natural place to compute both
bands), and split at the WRITE boundary in `run_firms` — filter AUTO to
`crosswalk_firms.csv`, REVIEW to `review_candidates.csv`. This is the smallest,
lowest-risk change and keeps the decision core untouched.

### Why

The mixed-decision file is the production risk. Splitting at the write boundary in
`run_firms` isolates the change to I/O, leaves the validated decision/scoring logic
byte-for-byte identical, and keeps determinism trivial to preserve (same frame, two
deterministic filters, two sorted writes).

### What worked

Reading the actual code confirmed the touch-point list was accurate and located the
single clean seam (`run_firms` write). The build functions already separate counts
from the written frame, so the diagnostic split needs no new classification logic.

### What didn't work

Nothing yet — spec/scoping step only. The `scratch/` generators named in the task
(gen_holdout_new_auto.py, draw_holdout_firms.py) are not present in this worktree
(git-ignored), so the "confirm they don't break" check is moot here; their
`decision=='AUTO_CONFIRM'` filter becoming a no-op against an AUTO-only crosswalk is
behaviourally safe regardless.

### What I learned

The `counts` dict from `build_crosswalk_firms` is the source of truth for band
totals (AUTO / REVIEW / NO_MATCH) independent of what gets written, so the runner can
report all three bands accurately even after splitting the written rows across two
files. The determinism contract is anchored on a fixed `--run-id` pinning `run_date`
to `REPRO:<run_id>`; both output files inherit it.

### What was tricky

The naming trap: `review_candidates.csv` must be documented as a LOCAL diagnostic,
explicitly NOT the production `TBL_REVIEW_CANDIDATES` table from the separate iir-sap
project. The builder must add that disambiguation in docstrings/requirements, not
just rename a file.

### What warrants review

After the build: confirm `crosswalk_firms.csv` has ZERO non-AUTO rows (2.518) and
`review_candidates.csv` holds exactly the 2.659 REVIEW rows; both byte-identical
across two `--run-id VERIFY_20260625` runs; full suite green with the new
zero-non-AUTO assertion added.

### Future work

If/when the ADF/Snowflake layer materializes, the production TBL_MATCHES /
TBL_REVIEW_CANDIDATES split is a separate, deferred decision (§13.3) — out of scope
here.

## Step 2: Build, validate, land on main

**Author:** builder (subagent "Ship matcher output split")

### Prompt Context

**Verbatim prompt:** (from the lead) "Split the firm-grain matcher output into TWO
files so the production file contains ONLY confirmed matches. crosswalk_firms.csv =
AUTO_CONFIRM only; review_candidates.csv = REVIEW only (local diagnostic, never to
Snowflake, NOT the iir-sap TBL_REVIEW_CANDIDATES). Make the split at the WRITE
boundary in run_firms; leave build_crosswalk_firms and CROSSWALK_FIRMS_COLUMNS
unchanged. Update docstrings + docs §13.3/§13.5/§13.8 + overview. Update tests +
add a zero-non-AUTO assertion. Validate with --run-id VERIFY_20260625 (twice,
byte-identical), full suite green, land on main with the correct identity, no push."

**Interpretation:** I/O-only change at the run_firms write seam; decision core
untouched; documentation and tests follow the split contract.

**Inferred intent:** An unambiguous production file (AUTO only) for the Snowflake
load, with REVIEW demoted to an inert local diagnostic.

### What I did

Split at the write boundary in src/matcher/runner.py: after build_crosswalk_firms
returns (crosswalk, counts), filtered the frame by the `decision` column with boolean
masks (preserving the existing deterministic sort, no re-sort), wrote AUTO rows to
crosswalk_firms.csv and REVIEW rows to review_candidates.csv (both index=False,
encoding="utf-8"). `crosswalk_rows` in the summary now = AUTO-only count; added a new
`review_rows` key without breaking existing keys. Left build_crosswalk_firms and
CROSSWALK_FIRMS_COLUMNS untouched. Added a REVIEW_FILE constant + review_path/
review_rows to PipelineResult in orchestrator.py and updated its docstring/_log
lines. Updated run_pipeline.py docstring and docs/requirements.md §13.3/§13.5/§13.7/
§13.8 + overview to the split contract with the iir-sap TBL_REVIEW_CANDIDATES naming
caveat; kept the §7F self-contained property. Updated tests/test_pipeline.py: the
integration test now asserts crosswalk_firms.csv decisions == {AUTO_CONFIRM} and
review_candidates.csv == {REVIEW}, same 30-col schema on both, NO_MATCH in neither;
the determinism test was extended to confirm review_candidates.csv byte-identical
across two fixed-run-id runs; a new constant test was added.

Diff: 5 files, +193/-79 — docs/requirements.md, run_pipeline.py, src/matcher/
runner.py, src/pipeline/orchestrator.py, tests/test_pipeline.py.

### Why

The write boundary is the only seam that needs to move; keeping the build function
and column schema fixed preserves all build-level tests and the validated decision
logic byte-for-byte.

### What worked

`python run_pipeline.py --run-id VERIFY_20260625` ran clean twice. Band counts:
AUTO_CONFIRM=2518, REVIEW=2659, NO_MATCH=17530 (written to neither). Row counts hit
the targets exactly: crosswalk_firms.csv = 2.518 (AUTO only, 0 non-AUTO rows by
direct read), review_candidates.csv = 2.659 (REVIEW only, 0 non-REVIEW rows). Both
files byte-identical across the two runs (sha256 matched: crosswalk bca47f85…,
review 1799ff6f…). GT auto-precision 98.9% (368/372), recall 96.0% — unchanged.
`python -m pytest -q`: 625 passed, 17 skipped, 0 failed.

### What didn't work

No functional failures. One skip-count discrepancy to flag: the suite reports 17
skips vs the baseline 16. The extra skip is tests/test_matcher_email.py:190, which
gates on scratch/out_v2 — a directory absent from this worktree and out of scope to
touch. It is purely environmental (the baseline 16 was measured in the main repo
where scratch/out_v2 exists); unrelated to this change.

### What I learned

The integration tests in test_pipeline.py only un-skip when output/ contains the
derived artifacts (validation_ground_truth.csv + base/canon CSVs). The builder copied
those derived files from the main repo's git-ignored output/ into the worktree
output/ to reproduce the baseline environment — sources (OneDrive, read-only) and the
four IRREPLACEABLE labelled files were not touched. The determinism check itself ran
against an isolated GRUNDFOS_OUT_DIR scratch dir with only the GT copied in.

### What was tricky

Keeping the summary/return contract stable for orchestrator.py (which reads
summary["counts"], summary["crosswalk_rows"], etc.) while repurposing crosswalk_rows
to mean AUTO-only — solved by adding review_rows as a new key rather than overloading
an existing one.

### What warrants review

Lead verified independently on main (0252b705a7adf5bc6cb63e26dd63d82f1bca658f):
author `singularity-consult <benny@singularityconsult.dk>`, no Co-Authored-By/Claude
trailer, main fast-forwarded from 89a20ed (not dangling — branch
feat/split-output-auto-review points at the same commit), 5 files changed. The 17-vs-16
skip is the only deviation and is environmental, not a regression.

### Future work

None beyond the already-deferred ADF/Snowflake TBL_MATCHES / TBL_REVIEW_CANDIDATES
split (§13.3).
