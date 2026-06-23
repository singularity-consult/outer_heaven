# Diary: Grundfos firm-level base files (de-dup occurrence base to unique firms)

Shift the matching grain in the Grundfos IIR/PD pipeline from project-firm-occurrence
to UNIQUE FIRM (name + location), per Benny's directive: matching happens between
unique firm names with their location, never via project id. Concretely: de-duplicate
the occurrence-level base files (`iir_base.csv`, `pd_base.csv`) into firm-level files
(`iir_firms.csv`, `pd_firms.csv`) keyed on `(name_canon, state_canon, city_canon)`.

## Step 1: Build the firm de-dup module, runner, and tests

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** Byg firma-niveau base-filer ved at de-duplikere de eksisterende
forekomst-niveau base-filer. Dette skifter matchingens grain fra projekt-firma-forekomst
til UNIKT FIRMA (navn + lokation), efter Bennys direktiv: matching skal ske mellem unikke
firmanavne med tilhørende lokation, aldrig via projekt-id. [Plus full spec: de-dup key
(name_canon, state_canon, city_canon) separately for IIR / PD-promoter / PD-awardee
universes; keep empty-state awardees; deterministic representatives for name_raw (most
frequent, alpha tie-break), pin_canon (most frequent non-empty), addr_clean+addr_raw
(most complete address), occurrence_count metadata; new files in output/, do not touch
src/matcher/ or scratch/draw_holdout_sample.py or crosswalk/holdout files; verify
reductions, determinism md5, sanity, 6 samples, weak/mega variance flag, pytest green.]

**Interpretation:** Add a NEW de-dup stage that reads the already-cleaned occurrence
base files and collapses them to one row per distinct firm, separately per universe,
with deterministic collapse rules; ship as a new module + runner + entry point + tests,
without touching the matcher work another builder is doing in parallel.

**Inferred intent:** Make the firm the unit of matching so M3 compares firms, not
project rows — and prove the collapse is correct and byte-reproducible before handoff.

### What I did
New code, all under `src/base_build/` (the lane the prompt assigned, away from the
matcher builder):
- `src/base_build/firms.py` — the pure de-dup core. `dedup_firms()` groups an occurrence
  frame on `FIRM_KEY = [name_canon, state_canon, city_canon]` with `dropna=False` so
  empty state/city are valid key parts. Representatives: `_most_frequent()` (Counter +
  alphabetical `min` tie-break) for name_raw and for non-empty pin; `_representative_address()`
  picks the occurrence with the longest non-empty `addr_clean`, tie-broken by longer
  `addr_raw` then earliest input row (`-idx` in a max-tuple). `addr_raw` is line1+line2
  via the upstream `address_clean.combine_lines` so it matches how the occurrence build
  combined them. `_flag_name_key_variance()` flags any firm group where match/weak/mega
  is not constant (should never happen — they are name-derived). `build_iir_firms` and
  `build_pd_firms` (the latter splits role==promoter / role==awardee, de-dups each
  independently, stacks promoters first).
- `src/base_build/firms_runner.py` — I/O edge. Reads `output/iir_base.csv` + `pd_base.csv`
  (read-only), writes `output/iir_firms.csv` + `output/pd_firms.csv`, prints reductions
  and any variance flags. Reuses `base_build.runner.out_dir` for the env-driven path.
- `run_firms.py` — convenience entry point mirroring `run_base.py`.
- `tests/test_firms.py` — 11 hermetic unit tests on tiny in-memory frames.
- `tests/test_firms_integration.py` — 2 tests asserting the contract against the real
  base files, auto-skipped when they are absent.

Ran `python run_firms.py`, a determinism re-run (md5 via Python tempfile), a sanity
script (dupes / occurrence-sum / reduction), and `python -m pytest -q`.

### Why
The matcher needs firms, not occurrences, so the same `LARSEN AND TOUBRO LIMITED` in
three states becomes three firm rows and identical occurrences collapse to one with an
`occurrence_count`. Reading the existing occurrence base (rather than re-canonicalising)
keeps the de-dup a pure, fast pandas pass and avoids re-running M1/M2. Putting everything
in `base_build` and new output filenames respects the parallel matcher builder's lane.

### What worked
First clean run. Reductions: IIR 21,154 -> 3,734; PD-promoter 34,385 -> 12,325;
PD-awardee 13,693 -> 5,836. No name-key variance flags (match/weak/mega constant within
every firm, as expected). Determinism: both files byte-identical across two runs
(IIR md5 `a2a278a9ef8e0e34879e246a5259e0f2`, PD `b8d78aea660292016ffb0dd3ca2e3663`).
Sanity: zero `(name_canon,state,city)` duplicates per universe; `sum(occurrence_count)`
equals input occurrences exactly for all three universes; 803 empty-state awardees
retained. Full suite 569 passed (was 556 + 13 new). The L&T sample is a clean
demonstration of the grain shift.

### What didn't work
The de-dup logic itself had no failures. The friction was the sandbox denying ad-hoc
inline commands. `cp output/...` in Bash was denied outright ("Permission to use Bash
has been denied"). My Python determinism check then failed because `/tmp` does not
resolve to a writable Windows path:
`FileNotFoundError: [Errno 2] No such file or directory: '/tmp/iir_firms_run1.csv'`
— fixed by using `tempfile.mkdtemp()`. Later, two more ad-hoc verification commands
(one Bash `python -c`, one PowerShell `python -c`) were denied with the same sandbox
message even though earlier near-identical `python -c` calls had run. I stopped fighting
it and moved those spot-checks into `tests/test_firms_integration.py` instead, which is
their proper home anyway and is reproducible.

### What I learned
The occurrence base has no single `addr_raw` column — it carries `addr_line1_raw` and
`addr_line2_raw` separately. The output spec's `addr_raw` therefore means line1+line2
COMBINED, and the only correct way to combine is the upstream `combine_lines` (it joins
with `", "` and collapses to line1 when line2 is empty, matching how the cleaned address
was produced). `weak_key` is serialised as the string `"True"`/`"False"` in the CSV, so
the variance check and representative selection operate on strings — fine, since they
only need equality/constancy, not boolean semantics.

### What was tricky
Determinism under a groupby. `groupby(..., sort=False)` gives groups in input order, so
the OUTPUT row order must be re-imposed independently — I sort the final frame on the
(unique) firm key with `kind="mergesort"`. The address tie-break also has to be
order-independent: I encode "earliest input row wins a full tie" as `-idx` inside a
max-compared tuple, relying on groupby preserving the original DataFrame index. Both are
proven by `test_dedup_is_deterministic_regardless_of_input_order` (reversed input gives
an identical frame) and the byte-identical md5 re-run.

### What warrants review
Two judgement calls worth a second look: (1) for match/weak/mega I take the representative
from the most-frequent `name_raw`'s rows rather than the most-frequent value of each key
column — irrelevant today because there is zero variance, but if variance ever appears the
flag fires and a reviewer should decide the policy. (2) `pin_canon` uses most-frequent
non-empty independently of the chosen address occurrence, so the pin and the address can
come from different occurrences; acceptable since pin is geo and address is text, but
flagged here in case Benny wants pin tied to the address representative. Look at
`src/base_build/firms.py` `_representative_address` and `dedup_firms`.

### Future work
The firm-level files are not yet consumed by the matcher — wiring M3 candidate generation
onto `iir_firms.csv` / `pd_firms.csv` (instead of the occurrence base) is the next step,
and is owned by the matcher builder. The two global files (`iir_non_indian_base`,
`pd_foreign_awardee_base`) were left at occurrence/name grain; if the global match also
needs firm grain, a parallel de-dup on `core` + country/region would be the analogue.

### What didn't work (explicit nil where applicable)
No logic or test failures; the only failures were the sandbox/`/tmp` issues recorded above.
