# Diary: Grundfos IIR matching — v3 identity model, ground-truth remap and new matcher

Grundfos delivered fresh extracts of both sources at a different grain than everything built
in June. The old world was firm grain on both sides; the new one is project grain on the
Projects Today side and (company × address) grain on the IIR side. That means identity has to
be rebuilt from raw rows before any matching can happen, and — the part that actually bites —
the 700 hand-labelled validation pairs were keyed to the *old* extract and no longer point at
anything the new build produces.

The work splits into two deliverables with a hard gate between them. **A:** remap the ground
truth onto the new identities and report how much survives, then stop. **B:** build the v3
matcher, but only once Benny has ruled on A. This file covers both as they land.

## Step 1: Gate feasibility read, and standing the team up

**Author:** lead

### Prompt Context

**Verbatim prompt:**

> Grundfos Projects Today ↔ IIR matching. Repo: C:\claudes_folder\repos\grundfos-iir-matching
> (main = 54f065b, git identity `singularity-consult <benny@singularityconsult.dk>`, NO remote,
> no Claude co-author trailer ever).
>
> Benny has delivered new source extracts with a different grain. I (main) have already profiled
> them and built the identity foundation inline. Your job: run the builder to (A) remap the
> ground truth, then STOP and report, then (B) build the v3 matcher.
>
> [... design decisions 1–8 and the hard invariants, omitted here for length; they are recorded
> in the builder brief and in the source docstrings ...]
>
> DELIVERABLE A — do this first, then STOP and report to me. Remap
> `output/calib/validation_ground_truth.csv` (700 labelled pairs, keyed to name+state+city from
> the OLD extract) onto the new identities (PT side) and company_ids (IIR side). Report: how many
> of the 700 map on both sides, how many fail and why, and the confusion matrix that the CURRENT
> committed matcher would produce if it could be evaluated. Do NOT tune anything against it yet.
> This is a gate: if the remap rate is poor, Benny must decide on relabelling before any
> calibration happens. Note that the new identity model structurally merges pairs the old labels
> split [...] — surface exactly which labels that affects.
>
> Work on a branch off main. Report back with numbers, not adjectives.

**Interpretation:** Do not implement. Establish whether Deliverable A is even feasible, frame the
gate decision for Benny, then hand the rigorous pass to a builder.

**Inferred intent:** The real question behind A is not "produce a remap" but "is the June labelling
investment still usable, or does Benny have to re-label 700 pairs before anything can be
calibrated?" Everything downstream depends on that answer, so it needs to be settled with measured
numbers before a single matcher rule is written.

### What I did

Read the three new modules (`sources_v3.py`, `identity_v3.py`, `identity_runner_v3.py`) and the
ground-truth file, then ran read-only profiling to answer four questions the brief left open:
does the ground truth actually carry labels, does the old IIR key still join, does the PT side
still resolve, and does the new identity model create label contradictions.

Then resolved a blocker (below), created the feature worktree `feat/v3-matcher` off `dbcc684` at
`.claude/worktrees/v3-matcher`, and briefed the builder for Deliverable A.

### Why

The brief asserted "700 labelled pairs" and implied the remap would be keyed on name+state+city.
Both deserved checking before a builder spent effort on them, because if the old IIR identifier
still joined, the whole IIR side of the remap would be a trivial id merge — and if it did not,
the remap path is fundamentally different. That is a fact that can only be settled by checking,
so I checked rather than assuming either way.

### What worked

The profiling answered the gate cleanly. Of 700 rows, 698 carry a usable label (545 positive,
153 negative, 2 blank). The PT side resolves for 697 of 700 on raw name plus role, with zero
role mismatches. The IIR side resolves for every single row — 671 land on exactly one company,
29 on several, none missing.

Creating the worktree explicitly with `git worktree add -b feat/v3-matcher ... dbcc684` rather
than via `EnterWorktree` was the right call: that tool defaults to branching from
`origin/<default-branch>`, and this repo deliberately has no remote, so the default path would
have failed.

### What didn't work

The old IIR identifier is dead as a join key, and not partially — completely. Zero of the 305
distinct values in the ground truth appear in the new extract:

```
distinct gt iir_id: 305
present in new IIR (any country): 0
MISSING: 305
```

The cause is that the two extracts use different identifier systems entirely: the old key is a
9-digit space beginning `300`, the new `COMPANY_ID` is 7 digits. This matters beyond this task —
it is precisely the class of trap that was banned back in June, a system key that *looks*
joinable, joins cleanly against nothing, and would have silently produced an empty remap had
anyone trusted it. Name plus geography is the only correct path.

Separately, my own working directory disappeared mid-task. I had been placed in an isolated
worktree, `agent-a48ea13e27c298615`, which was auto-cleaned the moment it went a while unchanged
— and it was unchanged precisely *because* I was doing read-only profiling in it. The next
command failed with:

```
/usr/bin/bash: line 1: cd: .../worktrees/agent-a48ea13e27c298615: No such file or directory
```

No work was lost, since nothing had been written there, but it is worth knowing that a
read-only agent can have the ground removed from under it for the crime of not writing anything.

### What I learned

The new identity model merges pairs the old labelling deliberately split, and the damage is
small and countable rather than pervasive. The 669 cleanly-resolving rows collapse to 350
distinct (PT identity × IIR company) pairs. Of those, 112 merged consistently — several old
rows, one label, no conflict. Only **7** are contradictory, carrying both a positive and a
negative label for what is now a single pair.

The pattern behind all 7 is the same and is a consequence of the design, not a labelling error:
under the old model a company recorded at two different sites was two rows, and a labeller could
legitimately mark one a match and the other not. A state-owned coalfield operator recorded at two
different mining towns is the clearest instance — 9 rows, both labels present. Under the new
model geography is evidence rather than identity, so those became one identity and the two
verdicts now collide.

That reframes the gate result. The question for Benny is not "re-label 700 pairs" but "rule on 7",
which is a materially different conversation and the reason it was worth measuring before
escalating.

### What was tricky

Two things nearly produced wrong answers.

First, reading the ground-truth CSV by eye suggested the `label` column was empty — the first two
rows appeared to have nothing in that position. That was an artefact of embedded commas inside the
address fields shifting the visual column count; parsed properly, the labels are all there. Eyeballing
a CSV with free-text address fields is not a reliable way to read it.

Second, the `output/` directory is git-ignored, so the feature worktree does not contain the ground
truth, the stored crosswalk, or the built universes. Everything resolves through a
`GRUNDFOS_OUT_DIR` environment variable, which makes this manageable, but it is a real trap: a
builder working in a fresh worktree will find the calibration assets simply absent and could
easily mistake that for a resolver bug.

### What warrants review

The numbers above are a deliberate *lower bound*: they use raw string equality, not the
canonicalisation the real build applies. The builder's rigorous pass should come out equal or
better on the PT side, and the 3 currently-unresolved PT names may well be recovered by
canonicalisation — or may merge into something else, which would itself need surfacing.

The 7 contradictory pairs must not be resolved or dropped by anyone but Benny. They need to reach
him with the raw evidence per row so he can rule on all 7 in one pass.

### Future work

Deliverable B, gated on Benny's ruling. Also settled during this step: the baseline for comparison
is the *stored* output of the current matcher, not a re-run. That matcher consumes the old grain
and its source file no longer exists, so it cannot be executed against the new data at all;
porting its rules onto the v3 universes to force a comparison would mean building B early and
would produce a baseline that had itself never been validated.

## Step 2: Deliverable A — the rigorous remap, and what it says about the ground truth

**Author:** builder

### Prompt Context

**Verbatim prompt:**

> Grundfos Projects Today <-> IIR matching. You are building **Deliverable A only**: remap the June ground truth onto the new v3 identity model, report numbers, and STOP. Do NOT build or tune a matcher. Do NOT modify any matching rule. This is a measurement task and a gate.
>
> ## Where to work
> Worktree: `C:\claudes_folder\repos\grundfos-iir-matching\.claude\worktrees\v3-matcher`
> Branch: `feat/v3-matcher`, already created off `dbcc684`. Work only there.
> Git identity is `singularity-consult <benny@singularityconsult.dk>`. NO remote. Never add a Claude co-author trailer. Commit when the work is done and validated.
>
> ## Critical environment trap — read before anything else
> `output/` is git-ignored, so your worktree has NO calibration assets and NO built universes. They exist only in the shared checkout at `C:\claudes_folder\repos\grundfos-iir-matching\output\`.
>
> Everything resolves through the `GRUNDFOS_OUT_DIR` env var (default `<repo>/output`). Set up your worktree like this, and do NOT write into the shared checkout's `output/` — main's artifacts live there:
>
> 1. Create `<worktree>\output\calib\`.
> 2. Copy in the read-only inputs that cannot be regenerated:
>    - `output\calib\validation_ground_truth.csv` (the 700 labelled pairs)
>    - `output\crosswalk_firms.csv` (the stored baseline, 2,592 AUTO / 2,752 REVIEW)
> 3. Rebuild the v3 universes into your own worktree output rather than copying them — it doubles as a determinism check:
>    `GRUNDFOS_OUT_DIR=<worktree>\output PYTHONPATH=src python -m base_build.identity_runner_v3`
>    Expect PT 22,614 identities (14,561 promoter / 8,053 awardee), 33,331 projects; IIR India 19,945 companies over 40,141 address rows. If your numbers differ, stop and report — do not proceed on a different base.
>
> Source extracts (read-only): `C:\claudes_folder\projects\grundfos_pd_iir_matching\base_files\` — `pt_company_data.csv`, `iir_company_data.csv`.
>
> ## Read first
> - `src/base_build/sources_v3.py`, `identity_v3.py`, `identity_runner_v3.py` — the identity foundation, well documented. PT identity = `(role, name_canon)`; IIR identity = `COMPANY_ID`. Geography/addresses/domains/groups are EVIDENCE SETS, never part of the key.
> - `src/matcher/runner.py` — note the public `gt_path()` resolver; reuse it, do not hand-roll a second path resolver.
>
> ## The one fact that determines the method
> The old IIR key in the ground truth (`iir_id`) is **dead**. I measured it: 0 of its 305 distinct values appear in the new extract. The old key is a 9-digit space starting `300`; the new `COMPANY_ID` is 7-digit. Different systems entirely. This is the same trap Benny banned in June — a system key that looks joinable and joins against nothing. **Name + geography is the only correct remap path. Do not join on `iir_id`.** State this explicitly in your report.
>
> Likewise `pd_id` in the ground truth is a project id, not a firm id (639 distinct over 700 rows). Not a PT identity key.
>
> ## What to build
> A remap module plus a runner, in the project's existing style (pure logic separated from the I/O edge, as `identity_v3.py` is separated from `identity_runner_v3.py`). It should:
>
> 1. **PT side:** map each ground-truth row to a v3 PT identity key `role|name_canon`, using the same canonicalisation the real build uses (`canonicalize_name` with the same doc-frequency table and gazetteer the runner builds). Do not invent a separate normalisation.
> 2. **IIR side:** map each ground-truth row to a `COMPANY_ID` via canonical name, disambiguating with the row's own `iir_city_raw` / `iir_state_raw` / `iir_pin_raw` where the name maps to several companies.
> 3. Emit a remapped ground-truth table plus an unmapped/failure table carrying a **reason code** per failed row.
>
> ## Numbers I need back (this is the deliverable)
> - Of 700: how many map on **both** sides, how many fail, broken down by side and by reason.
> - The label distribution that survives (baseline: 698 labelled — 545 positive, 153 negative, 2 blank).
> - How many rows collapse onto a shared (PT identity x IIR company) pair, and the resulting distinct pair count.
> - **The confusion matrix of the STORED baseline** `output/crosswalk_firms.csv` evaluated against the remapped ground truth. Evaluate the stored file as-is — it is what Grundfos was actually handed. Do NOT port the v2 rules onto the v3 universes to synthesise a comparison; that is Deliverable B early, and the baseline would itself be unvalidated. Report AUTO and REVIEW separately, and report explicitly how many ground-truth pairs the stored output simply has no opinion on.
>
> ## The 7 contradictory pairs — handle with care
> My lower-bound pass (raw strings, no canonicalisation) found 7 (PT identity x IIR company) pairs carrying BOTH label 1 and label 0. This is a structural consequence of the design: under the old model a company at two sites was two rows and a labeller could mark one a match and one not; the new model makes them one identity, so the verdicts collide.
>
> The 7 (raw PT name / IIR company id): *[roster redacted here — customer data and licensed-register
> record content. The actual pairs are in the repo-internal report, which is not public.]*
>
> **Do NOT resolve them and do NOT drop them.** Benny rules on all 7 in one pass. Your job is to hand him the evidence. Recompute the contradiction set properly with canonicalisation (my list is a lower bound — canonicalisation may add or remove members) and produce a per-row evidence table with: both raw names, both raw addresses, both cities, both states, the label, and which PT rows carried which label.
>
> Give **the property developer** extra care and lay its two labelled rows out in full. Context you need: on 29 June a REVIEW pair matching that same developer to an unrelated energy company was the concrete nonsense that made Benny reject shipping the whole review layer. He will look at this one hardest.
>
> Benny has already reasoned about the engineering consultancy and the coalfield operator this session and landed on "same company at a different site". The other five are new to him.
>
> ## Constraints
> - Determinism is a hard invariant: byte-identical output for a fixed input. Any tie-break must be deterministic (e.g. lowest company_id) — never randomness, never set-iteration order.
> - System keys (`COMPANY_ID`, `PROJECT_ID`, `ORDER_ID`) are for output and join-back only; never compare, score or block on them. The remap's use of `COMPANY_ID` as a join *target* is fine; deriving match evidence from it is not.
> - Do not tune anything against the ground truth. Measure only.
> - Full test coverage for the remap logic, in the repo's existing pytest style. The existing suite is 629 passing / 26 skipped (the skips are old-data-world integration tests whose source file no longer exists — leave them skipped). Do not break it.
>
> Follow the `outer_heaven:python` skill conventions. Report back with numbers, not adjectives. Then stop — do not start Deliverable B.

**Interpretation:** Build a measurement-only remap (pure core plus I/O runner, mirroring the
`identity_v3` / `identity_runner_v3` split), project the 700 June pairs onto the v3 identity
model using name plus geography only, score the stored crosswalk against what survives, and hand
back the contradictory pairs as evidence rather than resolving them.

**Inferred intent:** Establish, before any matcher work begins, whether enough validated ground
truth survives the grain change to justify building Deliverable B — and give Benny exactly the
evidence he needs to rule on the contradictions in one sitting.

### What I did

Set the worktree up as instructed and rebuilt the universes rather than copying them. Every
expected invariant matched exactly: PT 22,614 identities (14,561 promoter / 8,053 awardee) over
33,331 distinct projects, IIR India 19,945 companies across 40,141 address rows. That gave
confidence the rebuild was on the same base the lead measured.

Before writing anything I re-measured the lead's central claim rather than taking it on trust.
Confirmed: 0 of the ground truth's 305 distinct `iir_id` values occur in the v3 `COMPANY_ID`
space, and all 700 are 9-digit against a 7-digit target. I also measured the converse for the
stored baseline, which the brief did not mention: all 2,930 distinct `iir_company_id` values in
`crosswalk_firms.csv` ARE present in the v3 universe. So the baseline joins cleanly on its IIR
side and only its PT side needed re-deriving.

Then wrote `src/base_build/gt_remap_v3.py` (pure, dependencies injected) and
`src/base_build/gt_remap_runner_v3.py` (I/O edge, reusing `matcher.runner.gt_path`), plus 48
hermetic tests in `tests/test_gt_remap_v3.py`. Committed as `c66bd72` on `feat/v3-matcher`.

The headline numbers: 670 of 700 map on both sides. 3 PT failures, 27 IIR failures, no row fails
on both. 668 labelled rows survive (517 positive, 151 negative, 2 blank) against the lead's
baseline of 698 labelled. The 670 mapped rows collapse onto 356 distinct pairs — 433 of them land
on one of 119 pairs holding more than one row. Stored baseline scored as-is at ground-truth row
grain: AUTO 314 correct / 3 wrong (99.1%), REVIEW 124 / 22 (84.9%), and no opinion at all on 205
rows, of which 79 are label=1 misses and 126 are label=0 correct silences.

### Why

The pure/edge split was not decoration: it is what let the disambiguation rules be tested against
tiny hand-built universes instead of the 20k-company real one, so the tests state contracts
("ambiguity geography cannot break is a failure, not a guess") rather than re-deriving numbers.

The one design decision worth naming is what happens when a canonical name reaches several
companies and geography cannot separate them. The brief offered "lowest company_id" as an example
of an acceptable deterministic tie-break. I did not take it. A silent tie-break there invents a
ground-truth pair, and an invented pair is worse than an honest unmapped row in a file whose whole
purpose is to be trusted as truth. Ambiguity that survives PIN, city and state is emitted as
`IIR_AMBIGUOUS` with the candidate ids attached. In the event it cost exactly one row.

### What worked

The geography narrowing was applied most-specific-first (PIN, then city, then state) with a rule
that a signal which would empty the candidate set is skipped rather than obeyed — the ground
truth's geography is a v2 transcription and can be stale. That handled all 30 ambiguous-name rows
except one: PIN resolved 29 of them and city and state resolved none, which says the PIN column is
carrying the disambiguation work almost single-handedly.

Determinism held on the first try and survived a later refactor. Verified by md5summing all four
outputs across repeated runs, not by assuming.

### What didn't work

The full suite came back **676 passed, 27 skipped** against the brief's stated baseline of 629 / 26
— one more skip than expected, which looked like a regression I had caused. It was not. Running
`python -m pytest -q --ignore=tests/test_gt_remap_v3.py` gave 628 / 27, showing the delta was
entirely my 48 new tests plus one pre-existing skip. The culprit is
`test_matcher_email.py::test_additive_superset_invariant_real_firms`, gated on
`_firm_files_present()`, which looks in `<repo>/scratch/out_v2/` — a git-ignored scratch directory
that exists only in the shared checkout. In the shared checkout that same file runs 6 passed / 0
skipped. Nothing to do with my change; the brief's 629/26 was simply measured in the shared
checkout, not in a fresh worktree.

I briefly chased this down the wrong path first, copying `iir_firms.csv` and `pd_firms.csv` into
the worktree `output/` on the assumption the gate read from `GRUNDFOS_OUT_DIR`. The skip count did
not budge. Reading the gate function showed it reads `scratch/out_v2` and ignores the env var
entirely. Removed the copies again.

An earlier attempt to append this diary entry via a bash heredoc failed with
`/usr/bin/bash: -c: line 71: unexpected EOF while looking for matching ''` despite the delimiter
being single-quoted; writing the entry to a file and concatenating it worked instead.

### What I learned

The most important finding is one the brief's framing did not anticipate, and it contradicts the
premise it was handed to me with.

The lead described the contradictory pairs as "a structural consequence of the design" — one
company at two sites collapsing into one identity so two legitimate verdicts collide. That is true
for some of them and demonstrably false for others. I added a check that asks, for each
contradictory pair, which raw evidence fields actually differ across its rows. For two of the six
(a north-eastern construction contractor and an engineering services firm) the answer is **none** —
the rows are identical in every evidence field, so there was no "two sites" and the v3 collapse did
not create the contradiction.

Running the same check on the raw June file, before any remap and keeping the old `iir_id`,
confirms it independently: three groups of byte-identical rows already carried both labels in the
June ground truth, with label patterns (0,1), (0,1) and (0,0,1). Those are labelling
self-contradictions, not model artefacts. That directly qualifies the conclusion Benny reached
earlier in the session about the engineering consultancy: "same company at a different site"
describes a real phenomenon in that data, but the actual conflicting pair of rows is identical in
every field including the address, so the contradiction there is noise rather than a defensible
split.

Second finding: the property developer is not the same species as the others and deserves the extra
attention the brief asked for. Its two rows point at an IIR record that is not the developer at all
but its **construction sibling** — a different legal entity in the same conglomerate, not a
different site of the same company. The IIR side is byte-identical across both rows (same address,
same PIN); only the PT address differs, one at a site in the same suburb as the IIR record and one
in a town some distance away. The labeller appears to have been judging geographic co-location
rather than legal identity, marking the same-suburb pairing 1 and the distant one 0. If that
reading is right, both should be 0 and the positive is a label error of exactly the species that
sank the review layer in June.

Third: seven became six because the engineering consultancy drops out entirely. Its IIR name gained
a legal suffix between extracts, so exact canonical lookup fails and the row never reaches the
contradiction stage. Canonicalisation removed a member rather than adding one, which the brief
allowed for.

### What was tricky

The genuinely hard call was whether to relax the IIR lookup from `canon` to `core` (the same
`NameRecord`, legal tokens dropped). I measured it rather than guessing: it recovers exactly 5 of
the 26 `IIR_NAME_NOT_FOUND` rows and 0 of the 3 PT failures — the engineering consultancy's 3 rows,
a steel producer, and a pharmaceutical firm.

I left it off and shipped exact-canon, for two reasons. The v3 identity key is built from `canon`,
so matching on `core` is a relaxation of identity rather than the same canonicalisation the build
uses. And `core` collapses "Private Limited" with "LLP" — the pharmaceutical case is precisely that,
the same base name recorded as Private Limited in one extract and LLP in the other, which is
plausibly a genuine change of legal entity rather than a spelling variant. Recovering it would be a
matching decision, and this deliverable is not allowed to make those. The consequence is real and
worth Benny knowing: it is why the engineering consultancy is absent from the remapped
contradiction set.

The remaining 21 IIR failures are honest drift and not recoverable by any normalisation: a port
authority genuinely renamed from "Trust" to "Authority", a misspelling in the old extract corrected
in the new one, and parenthetical brand annotations on two beverage bottlers (the parent brand in
brackets after the legal name) dropped between extracts. The 3 PT failures are companies simply
absent from the new PT extract — checked directly, neither of the two contractors involved exists
anywhere in the 22,614 identities.

### What warrants review

The confusion matrix is computed at ground-truth **row** grain, deliberately. That is what lets
contradictory pairs be counted without being resolved: each of their rows lands in its own label
column under the same band. A reviewer who expects distinct-pair grain will get different totals
and should understand why before reconciling them.

I re-derived the whole baseline confusion matrix in a throwaway script that shares no code with the
module — AUTO 314/3, REVIEW 124/22, NO_OPINION 79/126, 3,736 distinct baseline pairs, all identical.
Worth knowing that cross-check exists rather than trusting a single implementation.

The 3 AUTO leakers deserve a look and are the weakest part of the precision story in both
directions. One of them is a row of the coalfield operator's contradictory pair, so if Benny rules
that pair a match it stops being a leaker and AUTO precision goes to 315/317. The other two are a
port-services company differing only by "Ltd." against "Limited", and a state government IT
department whose two spellings reorder the same words — both same-name pairs labelled 0, both of
which look like candidates for label error. I have not ruled on them and should not.

One structural oddity found in passing and not acted on: the single unresolvable ambiguity is a case
where **two IIR records carry the same canonical name in the same town**. No geography signal can
separate them because there is no difference to find. That is a duplicate inside IIR itself and will
bite the matcher in Deliverable B regardless of what the ground truth says.

### Future work

Benny's ruling on six contradictory pairs, now with the structural-versus-noise split attached so
they are not all the same question. Two (the coalfield operator, a textile manufacturer) are genuine
same-company-two-sites calls. Two (the construction contractor, the engineering services firm) are
label noise on identical rows and arguably want deleting rather than ruling on. One (a solar energy
company) differs only in PT address within the same city. One (the property developer) is a
group-sibling pairing where the positive label looks wrong.

Separately, the `core`-fallback question is a decision for Benny, not for the builder: 5 recoverable
rows, at the cost of collapsing Private Limited with LLP.

## Step 3: Rulings applied, and Deliverable B commissioned

**Author:** lead

### Prompt Context

**Verbatim prompt:**

> Benny has ruled on all six. Deliverable A is closed. Start B.
>
> [Rulings: drop the two label-noise pairs as unadjudicable, denominator 668 → 663; the coalfield
> operator's nine rows all become positive; the textile group's two rows become positive because
> IIR's only representation of that company is its group record sitting at the company's own
> registered address; the property developer's two rows stay negative but a parent-level match
> becomes a required new output; the solar company's two rows stay negative and become a
> regression case, because IIR holds the correct entity under a slightly different name.]
>
> New rule Benny approved — parent-level matching: when a PT company is NOT found in IIR but its
> declared `PT_GROUP_COMPANY` IS, match to the group record and mark the row as a parent match.
> Scope it exactly there and nowhere wider. [...] Do NOT infer a parent from address or email
> domain: I measured it and both fail hard [...]
>
> New output columns: `match_level` (`exact` | `parent`), `pt_group_company`,
> `pt_group_company_iir_id`. [...] canon vs core: keep it OFF. The tie-break refusal was right.
>
> What B is actually for: Precision is not the problem: the shipped matcher measures 99.1% on AUTO.
> **31% of the labelled set gets no opinion at all, and 79 of those are true matches.** That recall
> gap is the target. [...] Benny's labelling shows signs of having judged geographic co-location
> rather than legal identity [...] Do not silently "correct" for it, but if your calibration hits a
> threshold that only makes sense under a co-location reading, say so explicitly rather than
> fitting to it.

**Interpretation:** Close A, encode six label rulings and one new matching rule into a builder brief,
and re-point the effort from precision to recall.

**Inferred intent:** The gate did its job, so the remaining risk is no longer "is the yardstick
usable" but "will the builder quietly optimise against a yardstick we now know is bent in one
specific way". The brief has to carry that warning without turning it into licence to edit labels.

### What I did

Verified the builder's three load-bearing claims independently before taking them to Benny, then
sized the new parent-matching rule against the real canonicalised universes before briefing it.
Resumed the same builder rather than spawning a fresh one, so the codebase and remap context
carried over intact.

### Why

Two of the builder's claims contradicted things I had told Benny an hour earlier — that there were
seven contradictions rather than six, and that they were uniformly structural. Passing a correction
of my own earlier statement up to Benny without checking it first would have been careless in
whichever direction it turned out.

Sizing the parent rule was the same instinct applied to scope. It is a newly approved feature, and
approving a feature is not the same as knowing how much it does.

### What worked

Every verification held, and two produced sharper reasons than the builder had given. The
"identical evidence" claim only survives when the comparison is restricted to actual evidence
fields — my first pass compared all columns, including derived scores and a project id, and
appeared to refute it.

The one apparent discrepancy resolved into a genuinely interesting finding rather than a bug: a
port-services company looks contradictory under the old key but is not, because its two rows carry
different PT roles, and role is part of the identity key. Two roles, two identities, no
contradiction. The old key had no role in it, so the old world could not see the distinction.

Sizing the parent rule was worth the ten minutes: the ceiling is 111 identities out of 22,614
(0.5%), covering 370 rows, and 77% of it sits in just two conglomerates. No group resolves to more
than one company, so the rule needs no tie-break at all. That is a correct feature and a small one,
and the builder now knows not to let it eat the effort that belongs to the recall gap.

### What didn't work

Nothing failed outright this step. One thing was caught rather than broken: see below.

### What I learned

The ground truth encodes a systematic labeller bias, not just isolated errors. In the clearest case
the same IIR company was scored positive against one PT row and negative against another, and the
only thing that changed was whether the two addresses sat in the same suburb. The labeller was
judging geographic co-location; the matcher is supposed to judge legal identity. Those coincide
often enough that a calibration can fit the bias and still look good.

That is why the brief tells the builder to surface any threshold that only makes sense under a
co-location reading rather than adopting it. A number that is honest about being weaker is worth
more here than a better one that has quietly absorbed the labeller's mistake.

### What was tricky

The builder's diary entry named upwards of thirty real companies from the customer's dataset, and
this repo is public. The June diaries for the same project carry essentially none, so that is a
departure from the project's own precedent rather than a judgement call already settled. The file
is uncommitted, so nothing has been exposed; per this repo's own instruction the question goes to
Benny with a concrete proposal rather than being resolved silently in either direction. My own
entries describe the same companies by role — "a state-owned coalfield operator", "a port-services
company" — which preserves every engineering lesson without publishing the customer's data.

### What warrants review

The parent-match rows are the thing to inspect hardest when B lands. They assert a weaker claim
than an exact match, and the `match_level` column is the only thing preventing a downstream
consumer from reading them as identity.

### Future work

Deliverable B in flight. The public-repo naming question above needs Benny's answer before this
file is committed.

## Step 4: Deliverable B — first run, two defects, and 222 tests

**Author:** builder

### Prompt Context

**Verbatim prompt:** reproduced below with customer company names replaced by role
descriptions in square brackets, for the reason the lead set out in Step 3. Nothing else is
altered.

> Grundfos Projects Today <-> IIR matching, Deliverable B, resumed after a machine crash. You are a FRESH builder; the previous one died mid-task. Read this whole brief before touching anything.
>
> ## Where to work
> Worktree: `C:\claudes_folder\repos\grundfos-iir-matching\.claude\worktrees\v3-matcher`
> Branch: `feat/v3-matcher`, HEAD = `2ed2ab0`. Work ONLY there. Do not touch the shared checkout at `C:\claudes_folder\repos\grundfos-iir-matching\` other than reading.
> Git identity is already configured: `singularity-consult <benny@singularityconsult.dk>`. The repo has NO remote (commit-only, cannot push). NEVER add a Claude co-author trailer or set Claude as author.
>
> ## What you are inheriting, and its exact status
> Commit `2ed2ab0` is a RESCUE commit. It contains `src/matcher_v3/` — nine modules (`__init__, adjudicate, evidence, candidates, rules, parents, crosswalk, validate, runner`, 1,714 lines) written by the previous builder between 20:57 and 21:11 on 7 August, when the machine died. Their status:
>   * all nine import cleanly, so they are syntactically complete
>   * there are ZERO tests for any of them
>   * the matcher has NEVER been run, not once, against anything
>   * nothing else imports the package, so the existing suite is unaffected
>
> CRITICAL: the docstring in `rules.py` claims its thresholds "were chosen against the adjudicated ground truth". No run exists that could have produced that calibration, and no adjudicated calibration set has ever been written to disk. Treat every number, threshold and claim in those docstrings as UNVERIFIED assertion, not measurement. If a threshold turns out to have no evidence behind it, say so plainly in your report rather than back-filling a justification.
>
> ## Environment trap — read before anything else
> `output/` is git-ignored. Everything resolves through the `GRUNDFOS_OUT_DIR` env var (default `<repo>/output`). The worktree already has its own `output/` with `calib/` populated by the previous builder (`gt_v3_remapped.csv`, `gt_v3_contradictions.csv`, `gt_v3_unmapped.csv`, `gt_v3_remap_report.txt`), plus rebuilt v3 universes. Verify what is there before assuming.
>
> Set `GRUNDFOS_OUT_DIR=<worktree>\output` and `PYTHONPATH=<worktree>\src`. NEVER write into the shared checkout's `output/` — main's artifacts and Benny's IRREPLACEABLE hand-labelled files live there (`validation_ground_truth.csv`, `*_LABELLED.csv` and their `.bak`). Those must never be modified, overwritten or regenerated under any circumstance.
>
> Source extracts (READ-ONLY, customer data, never modify): `C:\claudes_folder\projects\grundfos_pd_iir_matching\base_files\` — `pt_company_data.csv`, `iir_company_data.csv`.
>
> Expected universe invariants when rebuilding (`python -m base_build.identity_runner_v3`): PT 22,614 identities (14,561 promoter / 8,053 awardee) over 33,331 projects; IIR India 19,945 companies over 40,141 address rows. If your numbers differ, STOP and report — do not proceed on a different base.
>
> ## Context you need: the v3 identity model
> Grundfos delivered new extracts at a different grain. PT is project grain (65,969 rows), IIR is company x address grain worldwide (910,268 rows, 40,141 in India). Commit `3a767fc` rebuilt both universes:
>   * PT identity = `(role, name_canon)`. NOT name+state+city: geography is what we know ABOUT a company, not who it is.
>   * IIR identity = `COMPANY_ID`, with Account and Plant addresses carried as a location SET.
>   * Geography, addresses, domains and group labels are evidence SETS on both sides. The matcher asks whether the sets INTERSECT, never whether they are equal. 750 PT identities legitimately span more than one state; IIR companies hold a median of 2 locations, up to 92.
>
> Commit `c66bd72` (Deliverable A) remapped the June ground truth onto this model: 670/700 map on both sides, 668 labelled survive. The old `iir_id` is DEAD as a join key (0 of 305 values present in the new extract; 9-digit vs 7-digit, different systems).
>
> ## Benny's rulings — these are FIXED DATA, never re-derived
> Already encoded in `adjudicate.py` as a declarative table. Verify the encoding matches these; do not change the rulings themselves:
>   * [a north-eastern construction firm] and [a rail-signalling engineering firm] — DROPPED as unadjudicable (byte-identical June rows carrying both labels). Denominator 668 -> 663.
>   * [a state-owned coalfield operator] — all 9 rows become 1.
>   * [a textiles manufacturer] — both rows become 1; IIR's "[...] Group" record at the company's own registered address IS the company.
>   * [a conglomerate's real-estate arm] — both rows stay 0. Correct match is the PARENT record, which is a required new match, not a label change.
>   * [a solar-energy company] — both rows stay 0, flagged as a missing-match REGRESSION CASE: IIR holds the right entity under a second record. A correct matcher must produce a match this ground truth cannot reward it for.
>   * canon vs core fallback: stays OFF. The previous builder's refusal to tie-break on lowest company_id was right and stands.
>   * Parent-level matching, approved: when a PT company is NOT found in IIR but its declared `PT_GROUP_COMPANY` IS, match to the group record and mark it. Scope it exactly there and nowhere wider — NEVER infer a parent from address or email domain (both were measured and fail hard). Output columns `match_level` (`exact`|`parent`), `pt_group_company`, `pt_group_company_iir_id`. Measured ceiling: 111 of 22,614 identities (0.5%), 370 rows, 77% concentrated in two conglomerates. It is a small correct feature — do not let it eat the effort that belongs to recall.
>
> ## Hard invariants (violating any of these is a failed delivery)
>   * Determinism: byte-identical output for fixed input. Any tie-break must be deterministic; never randomness, never set-iteration order. Verify by hashing outputs across repeated runs, do not assume.
>   * System keys (`COMPANY_ID`, `PROJECT_ID`, `ORDER_ID`) come from three unrelated systems: they are for output and join-back only. Never compare, score or block on them. This is a rule Benny imposed after a real join-bug class.
>   * No review layer exists in production — matches are never revisited by a human downstream. Auto-precision is everything.
>   * Do not tune anything by editing labels. The rulings above are the only permitted changes to the ground truth, and they are already encoded.
>
> ## What B is actually for
> Precision is NOT the problem: the shipped v2 matcher measures 99.1% on AUTO against the remapped ground truth (314 correct / 3 wrong). The problem is RECALL: **31% of the labelled set gets no opinion at all, and 79 of those are true matches.** That gap is the target.
>
> Warning Benny issued explicitly: his labelling shows signs of having judged geographic CO-LOCATION rather than legal identity (the clearest case: the same IIR company scored 1 against one PT row and 0 against another, the only difference being whether the addresses sat in the same suburb). Do NOT silently correct for it. But if your calibration lands on a threshold that only makes sense under a co-location reading, SAY SO EXPLICITLY rather than fitting to it. A number that is honest about being weaker is worth more than a better one that has absorbed the labeller's mistake.
>
> ## Your task
> 1. Read the nine `matcher_v3` modules critically. They are a dead colleague's unvalidated draft, not a foundation to be trusted. Report anything that looks wrong, unfinished, or asserted without evidence — especially in `rules.py` thresholds and `validate.py`.
> 2. Write full test coverage in the repo's existing pytest style, hermetic, against tiny hand-built universes rather than the 20k-company real one, so tests state contracts rather than re-deriving numbers. Existing suite baseline in this worktree: 676 passed / 27 skipped (the skips are old-data-world tests whose source file no longer exists, plus one that gates on `scratch/out_v2` which exists only in the shared checkout — leave all of them skipped). Do not break the suite.
> 3. Produce the adjudicated calibration set from `adjudicate.py` and RUN the matcher for the first time.
> 4. Report numbers, not adjectives: AUTO / REVIEW / NO_MATCH counts, precision and recall against the adjudicated ground truth (denominator 663), broken down PER ROUTE, and specifically how much of the 79-true-match no-opinion gap gets closed. Report parent-match rows separately. Report whether the [solar-energy company] regression case is now matched correctly.
> 5. Commit on `feat/v3-matcher` when validated. Do NOT merge to main.
>
> Follow the `outer_heaven:python` skill conventions. If you hit something that needs Benny's ruling, stop and report rather than deciding it yourself — that is what the previous builder did correctly with the tie-break, and it was the right call.

**Interpretation:** Take a dead colleague's never-executed draft, distrust every claim in it,
prove what is true by running and testing it, and report measurements rather than adjectives.

**Inferred intent:** Convert an unvalidated artefact into something Benny can stake a delivery
on. The deeper intent is epistemic: separate what has been *measured* from what was merely
*asserted*, because the previous builder's docstrings had blurred the two.

### What I did

Read all nine modules before touching anything, then verified the environment rather than
trusting the brief: the universes matched the stated invariants exactly (22,614 PT identities,
14,561 promoter / 8,053 awardee, 19,945 IIR companies over 40,141 location rows), though only
after reading them with pandas — a naive line count gave 23,008 because `name_raw` contains
embedded newlines inside quoted fields. Baseline suite confirmed at 676 passed / 27 skipped.

Ran `adjudicate.py` against the real remapped ground truth before running anything else, because
it was the cheapest way to test the brief's central warning. It came out exactly right: 668
mapped-and-labelled rows in, 5 dropped, 663 out, all six rulings hitting real rows
(`unmatched_rulings` empty), zero remaining contradictions, 515 label-1 / 148 label-0. The
hand-entered identity keys in that table were correct.

Then ran the matcher for the first time, and afterwards analysed the output rather than
accepting the summary: per-route precision, the regression cases, a preemption audit, and a
determinism check by copying outputs aside and re-running under the same `--run-id`, comparing
md5. Fixed two defects the run exposed, extracted the decision precedence into a pure
`decide_identity()` so it could be tested without I/O, corrected the false docstring claims, and
wrote 222 hermetic tests across eight files. Final suite: 898 passed / 27 skipped, the skip set
unchanged. Committed as `4d6a920`.

### Why

The brief's framing — treat the docstrings as assertion, not measurement — turned out to be
exactly the right instrument. Two of the previous builder's claims were not merely unproven but
false, and both were only visible by running the thing and measuring. Extracting
`decide_identity()` was not gold-plating: the worst defect lived in the middle of a 40-line loop
inside the only module that does file I/O, so there was no way to pin it with a test until it
was pulled out.

### What worked

Running `adjudicate.py` first, before the matcher. It is the cheapest module to validate, it
gates everything downstream, and confirming 668 -> 663 with all six rulings landing meant that
when the matcher numbers looked odd later, the ground truth was already off the suspect list.

Auditing the parent rule for preemption *before* it could be dismissed as a theoretical worry.
Reading `runner.py` suggested the parent branch ran before the ordinary decision and could
therefore override it; rather than assert that, I measured it, and found exactly one identity
affected. The decisive evidence was arithmetic: the code produced 112 parent matches while Benny
had measured the ceiling at 111. That one-row discrepancy was the bug, and it meant the fix
could be justified from Benny's own measurement rather than from my reading of his intent.

### What didn't work

The matcher fails one of the two regression cases, and this is the headline finding. The
[solar-energy company] identity matches the WRONG IIR company and lands in REVIEW rather than
AUTO. Two independent causes, both measured:

Candidate selection picks the wrong company by 0.357 points. PT's canonical name is
`<FIRM> GREEN ENERGY LIMITED`; both candidates share the discriminative key `<FIRM>`, both sit
in the same city and state, so geography cannot separate them and selection falls through to
highest name similarity. Names below are structurally faithful with the firm token masked; the
scores are the real measured ones:

```
IIR record A '<FIRM> ENERGY LIMITED'                 -> 94.643   (chosen, WRONG)
IIR record B '<FIRM> GREEN ENERGY PRIVATE LIMITED'   -> 94.286   (correct)
```

The blend is `0.5*token_set_ratio + 0.5*token_sort_ratio`. Each candidate is a token subset or
superset of PT's name, so both score 100 on `token_set_ratio` and the decision falls entirely to
the length-sensitive `token_sort_ratio` — which penalises the correct candidate for carrying the
legal filler `PRIVATE` more than it penalises the wrong one for dropping the content word
`GREEN`. The scorer cannot tell an identity-bearing token from a legal-form token, so it prefers
the shorter, wronger name.

Even with the right candidate selected it would still not auto-confirm: 94.286 is below
`name_auto = 96`. So the docstring's claim that route 4 "is the route that catches [this pair]"
is false twice over. I pinned the real number in a test so the claim cannot be restored.

I did not fix either cause. The tie-break order is Benny's own documented rule and `name_auto`
is a calibration value; changing either is his call, not mine.

### What I learned

`process.cdist` in the bulk fuzzy path is called with `dtype=np.uint8`, so the block-level argmax
runs on integer-truncated scores while the classifier re-scores the chosen candidate with the
full float `name_score`. The two can disagree by up to about half a point. It does not make the
output inconsistent — the reported score always describes the candidate that was actually chosen
— but it means candidate *selection* is slightly coarser than the decision that follows it, and
in a 0.357-point contest like the one above that is not a comfortable margin.

The three AUTO precision failures are all pairs whose canonical names are byte-identical to the
IIR company's — a port-services company and a chemicals manufacturer, each matched to a record of
exactly the same name and labelled 0. That is worth stating plainly: the entire measured
precision loss of the AUTO band consists of pairs where the legal names agree exactly. It is
consistent with the co-location bias Benny warned about, and it means 99.1% is more likely to be
understating the matcher than flattering it.

### What was tricky

Deciding whether the parent-precedence fix was mine to make. The brief was emphatic that
anything needing Benny's ruling should be escalated, and the parent rule's scope was explicitly
"exactly there and nowhere wider". What resolved it: the fix *narrows* the rule back to Benny's
own precondition rather than widening it. His ruling says "when a PT company is NOT found in
IIR", and a company the matcher auto-confirms has plainly been found — just spelled differently
by IIR, in the case at hand a bracketed acronym appended to the name. The 112-versus-111 count
confirmed it independently. I still flagged it prominently rather than burying it in the diff.

The confidentiality constraint cuts against the diary skill's instruction to record the verbatim
prompt, because the prompt names six customer companies and this repo is public. I sanitised the
prompt block to role descriptions and said so at the top of it. Worth Benny settling as a general
rule, since the tension will recur on every customer-project diary: the skill says verbatim, the
global memory rule says never.

### What warrants review

The two unfixed selection issues are the ones to look at, and both need Benny's ruling rather
than more engineering. First, whether the similarity tie-break should prefer the candidate that
covers all of PT's content tokens over the one that merely scores highest — that is what would
fix the regression case, and it is a change to a rule Benny wrote. Second, whether `name_auto`
at 96 is right when the case Benny himself nominated as the target sits at 94.29.

The parent-precedence change is the only behavioural change to output in this commit: it moves
exactly one identity from a parent match to its own exact match. Worth confirming that reading of
his ruling is what he meant.

One measurement worth Benny's eye: four ground-truth rows labelled 1 are matched by the system as
parent matches (a textiles group against its own group record) and are therefore scored as
NO_OPINION, because parent matches are deliberately excluded from precision. So the recall figure
is conservative by four rows. That the labeller marked a group record as a true match is the same
judgement he made in the ruling on the textiles manufacturer — which suggests "the group record
IS the company" may be a pattern rather than a one-off.

### Future work

The recall gap is real but only partly closed: NO_OPINION rows fell from 202 to 159 and silently
missed true matches from 77 to 67, so about 13% of the gap. Recall moved 85.0% -> 87.0% while
AUTO precision moved 99.4% -> 99.1%. The remaining 67 are where the next iteration's value is,
and the [solar-energy] diagnosis above is probably representative of a whole class: near-twin
names inside one state that the blend cannot rank correctly.

Note also that the brief quotes the gap as 79 true matches; measured directly against the stored
baseline over the same 663 rows I get 77. The difference comes from reconstructing the baseline's
identity keys by re-canonicalising its raw names, which is not guaranteed to reproduce
Deliverable A's own path. Small, but it should be reconciled rather than left as two numbers in
circulation.

## Step 5: Blind holdout of the AUTO band

**Author:** builder

### Prompt Context

**Verbatim prompt:** reproduced with customer names left as-is only where none appear; no
sanitisation was needed beyond the project name.

> Good work. One more deliverable before this is handed over, then stop. Benny asked for it specifically.
>
> ## Generate a blind holdout of the NEW AUTO pairs from RUN_B2
>
> Why: your 99.1% is measured against a ground truth that only covers 324 of the 2,150 AUTO identities. The rest have never been labelled by anyone. Project history says that gap matters — in June a threshold that measured fine against the ground truth collapsed to 34% marginal precision on a blind holdout of the pairs the GT did not cover. That method is Benny's, it has caught a real disaster once, and it is the only thing that can speak for the new population.
>
> Do NOT change any threshold or rule for this. `name_auto`=96 and the [solar-energy company] tie-break are with Benny; leave both exactly as they are. This is measurement plumbing only.
>
> ## Method (follow the established pattern, do not invent one)
> Prior art, read it first, READ-ONLY in the shared checkout: `scratch\gen_holdout_new_auto.py` and `gen_holdout_review.py`. Same shape: generator script, blind sample file, separate hidden key file.
>
> 1. **Population:** the AUTO band of RUN_B2.
> 2. **Exclusions:** every pair whose identity is already covered by the adjudicated ground truth. Note the trap: the June holdout keys are keyed to the DEAD v2 identity space. If you can re-derive their identities by name + geography reliably, exclude them too; if you cannot, say so explicitly in your report and exclude only what you can defend. Do not silently skip an exclusion.
> 3. **Stratify per route**, and prefer a census of the small routes over a sample. Target roughly 450 rows total unless you can argue for a different number.
> 4. **`parent_group` (111) goes in its own stratum and stays visibly marked.** `match_level` is a claim type, not a verdict — keep it visible. Everything else stays hidden.
> 5. **Blind means blind:** the sample file carries PT name + role + raw location, IIR name + raw location, an empty `label` column, and nothing else. ZERO verdict columns. Verify that by listing the emitted columns in your report.
> 6. **Hidden key file** carries route, stratum, scores, and both identities, joined to the sample by `pair_id`.
> 7. **Determinism:** fixed seed, byte-identical across repeat runs, verified by hashing — not assumed.
> 8. **Abort-guard:** the generator must refuse to run if it would overwrite any `*_LABELLED.csv`.
>
> ## Report back
> Population size, what was excluded and how many, per-route strata counts drawn against available, the emitted column list of the blind file, and — explicitly — what the holdout does NOT cover.
>
> One flag for Benny: if he ends up moving `name_auto`, the AUTO population changes and this holdout is stale before he labels it. Say whether you think that risk is real enough to hold the labelling until he has ruled.

**Interpretation:** Build the instrument that can speak for the 85% of AUTO nobody has ever
checked, following an existing method rather than inventing one, and prove the blindness rather
than claiming it.

**Inferred intent:** Guard against the specific failure this project has already suffered once —
a calibration that looks healthy against the labelled slice and is rotten on the unlabelled
remainder.

### What I did

Read both prior-art generators before writing anything, and inherited their shape: whitelist the
blind columns, keep a separate hidden key joined on `pair_id`, fixed seed, abort on a
hand-labelled file. Built it as `src/matcher_v3/holdout.py` with a pure core rather than a
`scratch/` script, because `scratch/` is git-ignored in this repo and the deliverable had to be
committed.

Population 2,150 AUTO; 216 identities excluded as covered by the adjudicated set, 625 by the
June holdout keys, leaving 1,326 fresh. Drew 453 across five strata, weighted by risk rather
than population share: the weakest route got the heaviest sample and the best-covered route was
sized only to detect a collapse. Censused the two small routes. Verified determinism by md5
across repeat runs, verified blindness by construction and by inspecting the emitted file, and
smoke-tested both abort guards live. 34 tests; suite now 932 passed / 27 skipped. Committed as
`84d0d41`.

### Why

The exclusions were the part worth being slow about. A holdout that quietly re-shows Benny
companies he has already judged is worse than no holdout, because it reports a precision number
that has absorbed his earlier opinion and looks blind.

### What worked

Measuring the v2-to-v3 re-derivation instead of guessing at it. The brief flagged the June keys
as belonging to a dead identity space and left it open whether they could be recovered. They
carry `pd_name_canon` but no role, so I checked how many of those canonical names still exist as
a v3 PT `name_canon`: 804 of 808, 99.5%. That turned "we cannot defend this exclusion" into "we
can defend the name half exactly", and the four that do not re-derive turn out to be absent from
the v3 PT universe altogether, so they cannot leak into AUTO even in principle. The exclusion is
therefore complete, not partial — which is a much better answer than the brief anticipated.

Building the blind file by SELECTING a whitelist rather than dropping a blacklist. A column
added upstream later cannot appear in Benny's file by default; it has to be added deliberately.
The test suite asserts the whitelist and the verdict blacklist are disjoint, so the contract
fails loudly rather than leaking quietly.

### What didn't work

One genuine bug, found by a test I had written to be pedantic. `draw()` raised
`KeyError: 'auto_route'` when handed an empty frame with no columns:

```
tests/test_matcher_v3_holdout.py::test_drawing_from_nothing_returns_an_empty_frame
E   KeyError: 'auto_route'
pandas/core/indexes/range.py:525: KeyError
```

Production could not reach it, because the frame always arrives from `select_fresh()` with its
columns intact. I fixed the code rather than only the test: an empty AUTO band should report
"nothing drawn", not raise three frames deep.

### What I learned

The missing role in the June keys is not the obstacle it first looks like. Excluding both roles
of a matched name over-excludes, but the asymmetry of the costs makes that trivially the right
call: over-exclusion costs a few rows of sample out of 1,326 fresh, under-exclusion costs the
one property the entire exercise depends on. Worth stating as a general rule for holdout work —
when an exclusion is uncertain, err toward excluding, and report the over-reach rather than
optimising the sample size.

### What was tricky

Deciding the stratum weights, because the intuitive answer is wrong. Proportional sampling would
have given the largest route the most rows, but that route already has 210 ground-truth rows
behind it at 99.5%, and the point of a holdout is to measure what is NOT measured. So the
weakest route (97.5%, and carrying a rescue condition that is new in v3) got the heaviest weight
and the largest route got enough only to detect a collapse rather than to refine a number we
already trust. I recorded the rationale on each stratum in the code, because a future reader
will otherwise "fix" the weights back to proportional.

The other judgement was how much IIR address text to show. A company can hold up to 92
locations, and truncating to the first few would have looked complete while quietly weakening
Benny's ability to judge. I show all of them, sorted; the location set is exactly the evidence
that decides whether the PT site belongs to that company.

### What warrants review

The staleness risk is the thing to decide before any labelling starts, and I think it is real
enough to hold on. Two open rulings — `name_auto` and the tie-break — both change the AUTO
population directly. Moving `name_auto` down admits new pairs into AUTO and the fresh pool
shifts underneath the sample; the tie-break changes which IIR company some pairs point at, so
rows already labelled could become rows about a different pair. Either would strand part of the
labelling. Since the generator is deterministic and cheap to re-run, the cost of waiting is
close to zero and the cost of not waiting is Benny's own hours.

Worth a second opinion on the stratum weights, since they encode a judgement about where risk
sits rather than a measurement.

### Future work

The holdout covers only the AUTO band. REVIEW (3,446 rows) and NO_MATCH (17,018) are unmeasured
by it entirely, and NO_MATCH is where the remaining recall lives — a false-negative holdout
would need a different sampling frame, because you cannot sample the pairs the matcher never
proposed by looking at what it produced. That is the natural next instrument once AUTO is
settled.

## Step 6: Retiring the v2 labels and drawing a new ground truth

**Author:** builder

### Prompt Context

**Verbatim prompt:** abridged to its operative content; the full brief was a table of
stratum targets plus format and safety requirements. No customer names appeared in it.

> Change of plan from Benny, and it clears the board. Stop costing options. We are building a NEW ground truth from the v3 engine, he labels it, then the engine is tuned against it and produces the final matched and review datasets. Everything from the v2 label world becomes history.
>
> **Deliverable: one blind file, 700 candidate pairs, drawn from the v3 engine.**
>
> **The one requirement that matters most: do not reproduce the June selection effect.** The old ground truth is blind to 271 pairs because v2 only ever proposed candidates within a state, so cross-state pairs could never be labelled. This draw must span everything the v3 engine can decide, including the populations its own rules currently reject. If a stratum is invisible in the new labels, the same trap closes again and we will not find out for months.
>
> [nine strata with targets summing to 700, the last being "candidates the engine generated but rejected to NO_MATCH", to be drawn from the candidate generator's output before the decision rules, not from the decision bands]
>
> Record a deterministic 70/30 calibrate/lock split as a column in the KEY file, never in the blind file. The engine will be tuned on the 70% only, and the 30% stays sealed until the end. Do not mention the split anywhere in the blind file, including column order or row order.
>
> Commit the generator. Do not tune anything yet; that is the next task, after the labels come back.

**Interpretation:** Build the instrument that replaces the June labels, and design it so
the specific blindness that wrecked the old one cannot recur.

**Inferred intent:** Stop arguing about thresholds from evidence that cannot settle them, and
buy evidence that can — while keeping one honest number at the end that the tuning never saw.

### What I did

Sized all nine strata against the live engine before writing the generator, because a target
that cannot be filled is worth knowing about before it is encoded rather than after. All nine
were fillable; the tightest was the smallest AUTO route at 30 of 36 available.

Built `src/matcher_v3/gt_candidates.py`, reusing the drawing and blindness machinery from the
earlier holdout rather than duplicating it. The one change to the existing module was making its
`split_outputs` accept a different hidden-key schema, so the blindness assertion keeps exactly
one implementation and the new draw could carry the calibrate/lock column.

Drew 700, all strata at target. Verified determinism by md5 across repeat runs, verified the
blind file carries no verdict, stratum or split column, verified the strata are mutually
exclusive, and smoke-tested the abort guard live against a sentinel `_LABELLED` file. 34 tests
added; suite 959 passed / 27 skipped. Committed as `7e86693`.

### Why

The recall stratum is the part that justifies the design. Every other stratum could have been
drawn from the two output files, but "candidates the rules rejected" exists only upstream of the
decision, in the generator's output. Drawing it from the bands would have been easy and would
have measured nothing, because a pair the rules rejected is by definition not in either band.

### What worked

Assigning the 70/30 split *before* the global shuffle. It is a one-line ordering decision and it
is the whole reason the split cannot leak: if the split were assigned after numbering, `pair_id`
order would correlate with it and anyone reading the blind file could infer which rows were
sealed. Checked empirically afterwards rather than trusted — the calibrate share across the ten
deciles of `pair_id` runs 0.67 to 0.76 against a target of 0.70, which is what independence
looks like.

Splitting within each stratum rather than globally. A global 70/30 over 700 rows would leave the
smallest stratum's 30 rows allocated by chance, and could seal almost all of one small stratum,
so the final unbiased number would say nothing about that population. Per-stratum gives exactly
70/30 everywhere: 21/9, 42/18, 105/45 and so on.

### What didn't work

Nothing failed outright this time. The one thing I had to correct mid-build was my own reuse
plan: I first intended to copy the blind-file assembly into the new module because the key
schema differed, which would have left two implementations of the blindness contract and
therefore two places for it to rot. Making the existing function take the schema as a parameter
was both smaller and safer.

### What I learned

The instrument has a boundary worth writing down, because it will be misread otherwise: an
identity for which blocking produced no candidate at all cannot appear in this file, since there
is no IIR side to put in front of a labeller. So the recall stratum measures the *rules'* recall
over what blocking found — it cannot measure blocking's own recall. That is a real limit, not a
rounding error, and the labels that come back will not reveal it. I stated it in the module
docstring and the commit rather than leaving it to be discovered later, which is exactly the
mistake the June selection effect was.

### What was tricky

Judging how far to trust the earlier probe. Two of its three claims were wrong when I measured
them — the population attributed to exact-unique names was 271 rather than 282, and the
threshold-band figure of 8 was actually 136 rows with 30 admissible. Neither error changed the
design, but taking either on trust would have put a wrong target in the strata table. The habit
that keeps paying here is measuring the population before encoding a target for it.

### What warrants review

The stratum predicates are where a silent error would hide: they are evaluated in declaration
order and first match wins, so reordering them silently changes which population a pair is
labelled under. There is a test asserting the intended precedence, but the ordering itself is a
judgement worth a second pair of eyes.

Twenty-one of the 700 rows carry an embedded newline in an address field. The June round lost
rows to exactly that in Excel. The file is correctly quoted, so it is well-formed CSV, but
anything that re-saves it can still break those rows apart, and `pair_id` is what recovers them.

### Future work

Tuning is the next task and it must consume only the calibrate 70%. The lock 30% should not be
read, joined, or eyeballed until the tuning is finished, and it would be worth putting that
enforcement in code rather than trusting discipline — a loader that refuses to return locked
rows unless explicitly asked would make the guarantee mechanical instead of procedural.

## Step 7: Redraw at 1,000 and seal the lock in code

**Author:** builder

### Prompt Context

**Verbatim prompt:** abridged to operative content; the full brief was allocation constraints
plus the enforcement requirement. No customer names appeared in it.

> Benny has decided to go bigger up front. Redraw at **1,000 rows with a 500 calibrate / 500 lock split**, replacing the 700 entirely. He has not started labelling, so delete `gt_v3_candidates.csv` and its key and regenerate cleanly — one file, no superset bookkeeping.
>
> Scaling the old targets by 1.43 does not work — several pools are too small. Allocate deliberately and report your reasoning. Census the small, high-value pools rather than sampling them. `review_ge96_state_mismatch` is the population nothing has ever measured — push it toward a census. The weakest measured route deserves more weight than its population share. `auto_name_unique` should be sized to detect a collapse, not to refine a known-good number. `review_lt90` and `no_match_rejected_candidate` should not eat the budget.
>
> Watch the arithmetic on odd numbers: a 50/50 split of an odd stratum cannot be exact. Round deterministically and state the rule you used.
>
> **Also build now, not later: mechanical enforcement of the lock.** You flagged this yourself and you were right. Build the loader so it returns calibrate rows by default and refuses to return locked rows unless an explicit, obviously-named argument asks for them. Any accidental full-set read during tuning should fail loudly rather than quietly hand over the answer sheet. Test it.

**Interpretation:** Reallocate a bigger budget by judgement rather than arithmetic, get the
odd-number rounding right and say what rule was used, and make the sealed half unreachable by
accident rather than by discipline.

**Inferred intent:** Buy enough labels to settle the open questions in one round, and remove
the possibility that the final honest number is quietly contaminated during tuning.

### What I did

Worked the allocation out on paper against the live pool sizes before touching the code, because
four of the nine pools are smaller than a 1.43x scaling would have demanded. Censused the three
small high-value pools, pushed the never-measured population to 220 of 282, over-weighted the
weakest route, and held the two low-information strata to 88 rows between them.

Then the odd-number problem. Two strata have odd targets (125 and 111). Flooring both gives
499/501, which is defensible but contradicts the agreed 500/500. I made the spare row alternate
by rank among the odd strata in sorted name order — first to lock, second to calibrate — which
lands exactly 500/500 while keeping both censuses intact.

Built the lock enforcement, regenerated, verified determinism by md5, verified the split is
50/50 in all nine strata, and smoke-tested both the abort guard and the loader live against the
real key. 19 more tests; suite 978 passed / 27 skipped. Committed as `5158c66`.

### Why

The alternating rule is worth the small extra complexity because a split that does not add up to
the number everyone has agreed on is an invitation for someone to "correct" it later, and any
correction after labelling starts would silently reshuffle which rows are sealed.

### What worked

Designing the loader so the dangerous path is the one that raises. The obvious implementation is
a boolean `include_locked=False`, but a boolean fails badly: `include_locked=1`,
`include_locked="no"` and any truthy typo all silently unseal. Requiring a long explicit token
and raising on anything else non-empty means the only two outcomes are the calibrate half or a
loud error. The convenience wrapper for the tuning path has no unseal parameter at all, so that
call site cannot reach a locked row by any argument.

Checking split leakage empirically again rather than assuming the earlier reasoning still held
after the ratio changed. Calibrate share across the ten deciles of `pair_id` runs 0.44 to 0.57
against a target of 0.50 — that is independence, and it is cheap to confirm.

### What didn't work

Nothing failed outright. Two existing tests broke as intended when the targets and ratio changed
(`test_the_targets_sum_to_the_agreed_size`, `test_the_split_is_seventy_thirty_within_every_stratum`),
which is the tests doing their job — the assertions were pinned to the old agreement, so changing
the agreement had to be visible.

### What I learned

The alternating rounding rule only balances when the NUMBER of odd strata is itself even. With
three odd strata it would give 500/500 minus one again. That is a property of the rule, not of
this allocation, so I added a test asserting the odd count stays even. Without it, a future
target change from 120 to 121 would silently break the headline split and nothing would say so.

### What was tricky

Judging how small the recall stratum could get. It is described as the only recall instrument,
which argues for protecting it, but its population is 17,018 and any affordable sample is a wide
interval. At 48 rows it can detect a large leak and cannot measure a small one. I kept it small
and wrote that limitation into the stratum's own rationale rather than into a report that will be
read once, because the number will be quoted long after this conversation.

### What warrants review

The allocation is a judgement about where risk sits, not a measurement, and it is the part most
worth disagreeing with. Specifically: 120 rows for a route that is 60% of the AUTO band is
deliberately thin, and it rests on the old 99.5% measurement still being roughly right in the new
label world. If that assumption is wrong, this draw will under-measure the largest population in
the system.

Thirty of the 1,000 rows carry an embedded newline in an address field, up from 21 at 700. The
file is correctly quoted, but anything that re-saves it can still split those rows, and `pair_id`
is what makes that recoverable.

### Future work

Tuning is next and must consume only the calibrate half through `load_labels`. The seal is now
structural, but nothing stops a future caller reading the key CSV directly with pandas and
filtering by hand; if that becomes a real pattern, the key file itself should be split into two
files so the locked rows are not even present in the one the tuning code opens.

## Step 8: Tuning on the new labels, and the sealed number

**Author:** builder

### Prompt Context

**Verbatim prompt:** abridged to operative content. Customer names in the original are
replaced with role descriptions in square brackets.

> Labels are back. Tune the engine, then produce the two final datasets. Benny has authorised this.
>
> **The one statistical instruction that matters most:** the strata were deliberately over- and under-sampled, so pooling all 1,000 rows gives a biased precision. Any population-level number must be **weighted by each stratum's sampling fraction**, and you must say so wherever you report one.
>
> **Benny's stated principle:** PT address quality is poor — the address is frequently a local project site or a plant, not the company's registered address. Geography is therefore weak evidence *against* a match. Combined with 218/218, that says the state-mismatch veto on an exact, unique canonical name is wrong and should go.
>
> The residual risk sits on the IIR side: a generic name being unique *in IIR* may only mean IIR knows one of several such companies. If your design can express a distinctiveness condition that keeps [a global engineering contractor] while being honest about [a generic two-word group name], cost it and show it. If it cannot without losing most of the 218, say so and take the simple rule.
>
> **Do not fix labels.** Two of the five failures look like label errors rather than engine errors — [a state public-works department] and [a state irrigation department], same body with the words reordered. Do not correct them, do not exclude them, do not tune around them. Report them and let Benny rule.
>
> **Sequence — the lock is broken once, at the end.** Tune against the calibrate 500 only. Freeze the rules. Then unseal the locked 500, once, and measure. That number is the honest one and it is not permitted to cause further tuning. If it disappoints, report it — do not go back and adjust.

**Interpretation:** Let the labels decide one large question, prove the answer on data the
tuning never saw, and never quote a pooled number from a deliberately unbalanced sample.

**Inferred intent:** Convert months of argument about geography into a measured ruling, and
end with a precision figure that is honest rather than flattering.

### What I did

Ingested the returned file as read-only input — Danish Excel semicolons, a BOM, and a repeated
header row, all handled on read rather than by editing Benny's copy. Verified before trusting
it: every drawn id present exactly once, no unknown ids, zero name drift on either side, every
label usable, and the four previously blank rows filled.

Then tuned strictly on the calibrate half through the gated loader, tested three candidate
changes, adopted one, froze, unsealed once, and produced the datasets. Suite 1,019 passed.

### Why

The sequence was the point. Tuning and measuring on the same labels produces a number that
describes the fitting, not the engine. Splitting the labels and sealing half is the only way to
end with a figure that means what it says.

### What worked

Testing each candidate refinement by its COST rather than its appeal. All three were plausible
and two died on contact with the numbers: tightening the parent rule by requiring a shared
token would have lost 34 measured-correct matches to catch 2 errors, and moving the fuzzy-name
threshold was wrong in both directions — down admits a 60%/46%/20% cascade, up discards 19 true
matches to prevent 2. Only the geography change survived, and it survived overwhelmingly.

The gated loader earned itself. Every tuning read went through it and returned exactly 500 rows;
the sealed half was opened once, deliberately, by an explicit token. Without that the temptation
to "just check" would have been constant and unrecorded.

Splitting the state-mismatch population four ways before believing it. The headline was 110/110,
but the useful question was whether it held in the cell I most distrusted — weak-cored AND
uncorroborated. It did: 39 for 39. That is what justified dropping the corroboration
requirement as well as the veto, and I would not have dropped it on the headline alone.

### What didn't work

The distinctiveness condition the brief asked me to cost could not be built, and the reason is
worth recording: there were ZERO negatives in the measured population to fit one against. Any
condition I invented would have been fitted to a fear rather than to evidence, and would have
cost recall for no measurable benefit. Requiring a non-weak core, the most obvious version,
would have discarded 48 measured-correct pairs in the calibrate half alone to prevent zero
measured errors. So I took the simple rule and wrote the residual risk into the module docstring
instead of pretending to have handled it.

My own parent-rule hypothesis also failed. I predicted the wrong parent matches would be the
ones sharing no token with the group name — and they were, but so were 34 of the correct ones.
A 94% hit rate on the "suspicious" side is not a rule, it is a coincidence with a story attached.

### What I learned

A stratified sample makes the obvious number the wrong one. Pooling all 1,000 rows gives 99.01%;
weighting by each stratum's sampling fraction gives 99.67%. The gap is entirely an artefact of
having deliberately over-sampled the populations most likely to be dirty. Both numbers are
"true" of the sample and only one is true of the population, and the wrong one is the one that
falls out of a naive `mean()`. I made the weighted estimator a tested function rather than a
line in a script, precisely because the naive version is so easy to reach for.

A secondary surprise: the standard error of the all-1,000 estimate is exactly zero, which looks
like a bug and is not. Every stratum containing an error was censused, so the
finite-population correction removes all sampling uncertainty from them, and every sampled
stratum was perfect. Worth explaining wherever it is reported, or someone will "fix" it.

### What was tricky

Verifying the coordinator's label table without breaking the seal. Their table was over all
1,000 rows, and confirming it before freezing would have meant reading the locked half — the one
thing the sequence forbids. I verified on the calibrate half, froze, and only confirmed the full
table after unsealing. Three of their nine counts were slightly off (199 vs 200, 218 vs 220, 107
vs 108) though the error counts were all correct; had I "verified" early I would have learned
nothing extra and contaminated the result.

### What warrants review

Two of the eight AUTO errors are almost certainly label errors, not engine errors: a state
public-works department matched to the same department with the words reordered, and a state
irrigation department likewise. Both score 100.0 on the name blend. I did not correct, exclude
or tune around them, exactly as instructed — but if Benny rules them correct, the approximate-name
route measures 96.8% rather than 96.0%, and the remaining failures are all genuine near-name
collisions at the very bottom of the threshold.

The parent route is the weakest at 97.3%, and all three failures are group-sibling cases,
consistent with Benny's June rule that group units are distinct legal entities. It cannot be
tightened by anything I could measure. It is a distinct claim type and a small population, so it
is his call whether 97.3% clears the bar for a table nobody reviews.

### Future work

Recall is now the whole remaining problem. The rejected-candidate stratum came back 8.3% true,
which extrapolates to roughly 1,400 true matches inside the 17,018 identities the rules discard
— far larger than anything left in the AUTO or REVIEW bands. That population has never been
worked on, and it is where the next iteration's value is. It also cannot be reached by threshold
changes: the missed matches sit at name scores in the 50s and 60s, so it needs a different
signal rather than a looser one.
