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
