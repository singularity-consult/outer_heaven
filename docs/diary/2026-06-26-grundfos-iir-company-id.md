# Diary: grundfos-iir-matching — add iir_company_id column + Snowflake CREATE TABLE DDL

Two crisp, pre-decided asks on the firm-grain PT↔IIR matcher (`grundfos-iir-matching`, worktree
`agent-a7af68f2a25e48898`, branch `feat/split-output-auto-review`, off main `0252b70`):

1. Carry the IIR firm's `COMPANY_ID` (from the master `iir_company_data.csv`) onto each matched IIR
   firm in the firm-grain crosswalk, so Grundfos can join the crosswalk back to their IIR system
   downstream. New column `iir_company_id` in BOTH `crosswalk_firms.csv` (AUTO) and
   `review_candidates.csv` (REVIEW) — they share the writer (`build_crosswalk_firms`).
2. A Snowflake-flavour `CREATE TABLE` DDL for the final 31-column `crosswalk_firms` schema.

Hard rule that frames everything: `iir_company_id` is an OUTPUT attribute only. It must NEVER enter
matching / candidate-generation. Re-introducing an id into matching is the exact join-bug class that
was deliberately removed when the firm-grain pivot dropped the old non-unique `project_id`.

## Step 1: spec + design decision (Option A)

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Benny chose Option A. Carry the COMPANY_ID from exactly the IIR row the matcher
scored (the same row name/city/addr_raw already come from) — do NOT override it, do NOT pre-dedup the
universe. The iir_company_id must stay internally consistent with the other iir_* columns on that
crosswalk row. Still report the collision stats as a separate diagnostic: how many (name_canon, state,
city) firm keys span >1 distinct COMPANY_ID, and the max collision size. That's informational only; it
does not change the carried id. Everything else in the original brief stands: add iir_company_id to
crosswalk_firms.csv AND review_candidates.csv, never use it in matching/candidate-gen, produce the
Snowflake CREATE TABLE DDL for the final 31-column schema, keep tests green and the 2.518/2.659 counts
+ determinism pinned, land on main with identity singularity-consult <benny@singularityconsult.dk>."

**Interpretation:** Thread the IIR firm's `company_id` (already present on `iir_firms.csv`) through the
matcher's firm-grain assemble step onto the crosswalk row, carrying exactly the chosen IIR row's id —
no separate "pick smallest" override, no pre-dedup of the universe. Add it as a column. Measure (don't
fix) the (name_canon, state, city) → multiple-COMPANY_ID collisions. Then write the DDL.

**Inferred intent:** A clean downstream join key back to IIR's system, without reopening the join-bug
class that the firm-grain pivot closed. Internal consistency of the id with the rest of the iir_* row
matters more than matching a literal "lexicographically smallest" rule.

### What I did

Read the codebase end to end before forming the brief: `src/matcher/crosswalk.py`
(`CROSSWALK_FIRMS_COLUMNS`, the 30-col firm schema; `build_crosswalk_firms`), `src/matcher/candidates.py`
(`_assemble_firms` — where the chosen IIR row's columns are carried; the matcher already picks ONE IIR
row per PD firm via exact-key lowest-row-index / fuzzy argmax), `src/base_build/firm_build.py` +
`sources_v2.py` + `firm_runner.py` (the IIR firm universe `iir_firms.csv` already carries `company_id`
on every row — `IIR_FIRM_BASE_COLUMNS = ["source", "company_id", *FIRM_BASE_COLUMNS]`), `runner.py`
(`run_firms` splits AUTO→crosswalk_firms.csv, REVIEW→review_candidates.csv), `pipeline/orchestrator.py`,
and `tests/test_matcher_firms.py`.

Key finding that shaped the decision put to Benny: there is NO de-dup of the IIR universe — each row is
one COMPANY_ID. The matcher picks one IIR candidate deterministically (exact-key → lowest source row
index; fuzzy → argmax). So a (name_canon, state, city) firm key spanning >1 COMPANY_ID is a real but
rare surface. I laid out three options (A: carry chosen row's id as-is; B: pre-dedup universe to a
canonical id; C: keep chosen row but overwrite id with smallest-in-key). Benny chose **A**.

### Why

Option A keeps `iir_company_id` internally consistent with every other `iir_*` column on the same
crosswalk row (the id, name, city, addr_raw all come from the one IIR row the matcher actually scored).
B risks perturbing the matcher's argmax and the pinned AUTO/REVIEW counts (2.518 / 2.659) and the
byte-identical determinism baseline. C can make the id disagree with the rest of the row — a subtle
downstream-join trap. The collision stats are still surfaced, but as a pure diagnostic.

### What worked

The plumbing is already 90% there: `company_id` rides on `iir_firms.csv` from the firm build. The only
new wiring is (a) carry it in `candidates._assemble_firms` from the chosen IIR row, (b) add
`iir_company_id` to `CROSSWALK_FIRMS_COLUMNS` and emit it in `build_crosswalk_firms`, (c) a collision
diagnostic, (d) tests + DDL + docs. Matching logic is untouched by construction.

### What didn't work

Nothing yet — spec stage. One snag worth recording: the original brief referenced a stale worktree path
(`agent-a0a973382efa55bf2`); the actual worktree is `agent-a7af68f2a25e48898`. Both branch off `0252b70`
so the files are byte-identical; analysis carried over cleanly. The bash tool also resets cwd between
calls on this machine — must use absolute paths / `git -C`.

### What I learned

`iir_company_id` placement: group it with the `iir_*` identity columns. Logical spot is right after
`iir_name_raw` (or with the iir block) — schema goes 30 → 31 cols. The matcher already carries the
chosen IIR row's fields in `_assemble_firms` via `np.where(has, iir[...], "")`, so `company_id` follows
the identical pattern — blank when no candidate.

### What was tricky

The non-obvious trap: "pick lexicographically smallest COMPANY_ID" (brief's *e.g.*) is NOT what the
matcher does, and forcing it (Option B/C) would either move the pinned counts or break row-internal
consistency. Surfacing that as an explicit decision rather than silently picking was the right call.

### What warrants review

The builder must prove `iir_company_id` is NOT consulted in candidate-gen/matching (a test that scrubs
it from the candidate frame and shows identical matches), that AUTO=2518 / REVIEW=2659 and determinism
hold, and that the id on each AUTO row equals the chosen IIR row's id. Column count 30→31 across schema
tests.

### Future work

None beyond the two asks. DDL is a one-shot handoff artifact for Grundfos' Snowflake env.

## Step 2: builder ships, lead verifies, ff-merge to main

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** (no new user prompt — this step is the lead acting on the builder's handback under
the standing instruction to validate the work and land it on main.)
**Interpretation:** The background builder finished; verify the load-bearing claims independently before
trusting them, then fast-forward main.
**Inferred intent:** Don't take the builder's word on the join-bug invariant, the pinned counts, or
determinism — confirm them, then deliver on main with the correct identity.

### What I did

The builder committed `86864a4` on `feat/split-output-auto-review` (author
`singularity-consult <benny@singularityconsult.dk>`), 7 files: `src/matcher/candidates.py`,
`crosswalk.py`, `runner.py`, `tests/test_matcher_firms.py`, `tests/test_pipeline.py`,
`docs/requirements.md`, and new `sql/create_table_crosswalk_firms.sql`. No `output/` leakage, no source
files touched, clean tree.

I independently verified the four load-bearing things rather than trusting the report: (1) `company_id`
appears NOWHERE in `src/matcher/scoring.py` and in `candidates.py` only at the assemble-time carry
(line 387: `out["iir_company_id"] = np.where(has, col(iir, "company_id"), "")`) — the matching
invariant holds; (2) `CROSSWALK_FIRMS_COLUMNS` is 31 cols with `iir_company_id` at index 9, immediately
after `iir_name_raw`; (3) `python -m pytest -q` → 629 passed / 17 skipped (was 625/17, +4 new tests);
(4) commit identity correct. Then `git merge --ff-only feat/split-output-auto-review` fast-forwarded
main `0252b70 → 86864a4` (had to run it from the main worktree since the branch is checked out in the
agent worktree).

### Why

Benny chose Option A; the whole risk surface is "did the id leak into matching" and "did the pinned
counts/determinism move." Verifying those directly is cheaper than a regression later. The merge is a
clean ff (one commit, main is a direct ancestor), so no merge commit, no history rewrite.

### What worked

Option A needed almost no new code: `company_id` already rode on `iir_firms.csv`, so the change was one
carry line in `_assemble_firms`, one schema entry + emit in `crosswalk.py`, a diagnostic in `runner.py`,
tests, DDL, docs. The builder's `test_company_id_not_consulted_in_matching` (scrambled ids → identical
chosen matches) is exactly the empirical proof of the invariant I asked for.

### What didn't work

A first verification one-liner failed with `ModuleNotFoundError: No module named 'matcher'` — the repo
needs `PYTHONPATH=src` for ad-hoc imports (pytest sets it via config, bare `python -c` does not). Re-ran
with `PYTHONPATH=src` and it passed. No code issue.

### What I learned

Collision reality (measured, not assumed): over the live `iir_firms.csv` (20,930 firms), only **41**
`(name_canon, state, city)` firm keys span >1 distinct COMPANY_ID, max collision size **2**. So Option A
vs B/C would diverge on at most 41 keys — the pre-dedup blast radius Benny avoided was real but tiny,
and the internal-consistency win is the right trade regardless. The two worktrees share one repo: ff to
main must be driven from the main worktree because the feature branch is already checked out in the
agent worktree (can't check out a branch twice).

### What was tricky

Nothing sharp — the spec's guardrail (STOP if AUTO/REVIEW ≠ 2518/2659 rather than "fix" by moving
thresholds) meant a perturbation would have surfaced loudly. It didn't: 2518 AUTO / 2659 REVIEW, both
31 cols, determinism byte-identical across two `--run-id VERIFY_20260625` runs (builder-run, plausible
given the id is carried not matched on).

### What warrants review

DDL type choice to sanity-check with Grundfos: the four flags (`CITY_MATCH`, `SHARED_DOMAIN`,
`WEAK_KEY_FLAG`, `MEGA_NATIONAL_FLAG`) are VARCHAR, not BOOLEAN, because the CSV serialises them as the
literal strings `True`/`False`. Snowflake `COPY` can parse those into native BOOLEAN if they'd rather —
a one-line switch. Scores are `NUMBER(5,1)` (data ranges -1.0 sentinel .. 100.0, 1 decimal).

### Future work

Open question for Grundfos only: BOOLEAN vs VARCHAR for the four flag columns in the Snowflake load.
Otherwise complete — landed on main `86864a4`.
