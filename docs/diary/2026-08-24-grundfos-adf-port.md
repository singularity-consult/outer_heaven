# Diary: Grundfos matching engine — porting the run to Azure Data Factory

The matching engine has run on Benny's workstation since June: he points it at two CSV
extracts in a local folder, runs two Python entry points, and hands the result over. The
customer now wants it inside their own ADF pipeline, where the extracts land as split
Snowflake exports in a blob container and the deliverable has to appear as one file in a
dated output folder.

Three deliverables fell out of that. **1:** produce the 31-column hand-off the destination
Snowflake table expects, from the v3 engine's own rows. **2:** read the new extract shape
and fail loudly when its header is wrong. **3:** package the repo so an ADF Custom Activity
can run it. This file covers 1 and 2; deliverable 3 was built in parallel by another agent
in the same worktree.

A hard constraint shaped everything: **Benny forbade running the engine at all, locally
included.** No `identity_runner_v3`, no `run_decision_store.py`, no runtime or memory
measurement. Only pytest against hand-made fixtures, and reading the shipped baseline file
for structure. That is a real limit on what can be claimed, and the "what warrants review"
section below is where it shows.

## Step 1: The 31-column hand-off and the source contract

**Author:** builder

### Prompt Context

**Verbatim prompt:**

> Du bygger leverance 1 og 2 i porteringen af Grundfos-matching-motoren til ADF.
>
> [... full brief omitted for length: worktree path, the hard no-run constraint, the
> 1188/38 test baseline that must not degrade, the read-only customer data folder, and
> then two deliverables ...]
>
> LEVERANCE 1 — 31-kolonne-projektionen. Definitionen findes allerede i repoet. Dette er
> en PORTERING fra v2 til v3, ikke en nykonstruktion. [...] `crosswalk_firms.csv` er
> ALLEREDE et brugt filnavn i repoet med et ANDET skema. [...] Adskil på MAPPER, ikke på
> navne. [...] ADDR_SCORE — beregnes ingen steder i v3 [...] Dokumentér den eksplicit i
> modul-docstringen som BESKRIVENDE metadata, aldrig beslutningsgrundlag.
>
> LEVERANCE 2 — fil-læsning, skema-mapping, header-validering. [...] Header-validering —
> dette er den egentlige defekt du retter. `_g()` i `sources_v3.py` gør `val = row.get(key)`
> og `if val is None: return ""`. En manglende kolonne og en tom værdi er ikke til at skelne
> fra hinanden. [...] `PT_GROUP_COMPANY` skal ligge i PÅKRÆVET.
>
> [... plus: pt_links.csv decision to make and defend, the suppression mechanism with its
> table deliberately left empty pending keys, and an eight-point reporting requirement
> ending in "Alt i briefen her der IKKE holdt ved eftersyn af koden. Udfordr mig." ...]

**Interpretation:** Port an existing v2 output schema onto the v3 engine's data without
inventing anything, and close a silent-failure hole in the source loader. Verify by unit
test only; say plainly what cannot be verified.

**Inferred intent:** The engine is about to start running somewhere nobody is watching it.
Everything in the brief is really about that: a file that silently ships wrong values, or a
header change nobody notices, is far more expensive in a scheduled pipeline than on a
workstation where Benny eyeballs the output.

### What I did

Read the whole decision path first — the v2 crosswalk builder, the v3 crosswalk, delivery
and runner modules, the decision store's runner and its rulings table, the identity builder
and the source adapters — before writing anything. Then three new modules and three edits.

`matcher_v3/crosswalk_firms.py` is the projection. Twenty-two of the 31 columns come
straight off the crosswalk record the engine already produces; nine are joined in from the
three universe files the run writes; one, the address score, is computed there and nowhere
else. Its header matches the shipped baseline file exactly, order included — checked by
reading that file read-only and comparing the column list.

`base_build/ingest_v3.py` is the loader edge: glob the split extract parts, order them by a
natural sort so part 10 follows part 2, concatenate, rename the incoming headers to the
vocabulary the engine reads, then enforce a declared required/optional contract. A missing
required column raises and names the accepted spellings and the path it searched. A missing
optional column is created blank and warned about with the consequence stated.

`decision_store/suppression.py` is the mechanism for pairs that must never be proposed
again, unioned into the channel candidate generation already reads. Its table is
deliberately empty — see "what was tricky".

The edits: `identity_runner_v3.load_sources()` now goes through the ingest module and stops
writing the link table; `decision_store/runner.py` emits the hand-off as a fourth output
behind two independent guards; `sources_v3.py` got a docstring correction only.

97 new tests, all against hand-made fixtures in temp directories. Suite went from
1188 passed / 38 skipped to 1289 / 38 — skip count unchanged, which was the brief's own
bar for "nothing regressed".

### Why

The projection is a port, so the honest thing was to reuse the v2 definitions rather than
re-derive them: the column list, the mega-owner comparison and the address scorer are all
imported from the v2 modules, and only the parts that genuinely depend on the old data
shape were rewritten. The grain is what changed — the old world had one address and one
city per firm, the new one carries sets — so the same 31 columns now hold sorted
pipe-joined values.

The loader was normalised at the frame level rather than the engine being renamed, because
the runner does not only go through the adapter module: two of its own functions index four
columns straight off the DataFrame. Renaming in the adapter module alone would have left
those four silently pointing at columns that no longer exist — the same class of failure the
whole exercise is about.

### What worked

Reading before writing paid for itself twice. The existing end-to-end test for the
store-driven run turned out to be a complete hermetic four-firm world on disk, which meant
the fourth output could be tested through the real runner rather than in isolation — no new
fixture scaffolding at all.

The parallel agent working deliverable 3 in the same worktree had, by the time I looked,
already wired its node launcher to an environment variable with exactly the precedence I had
just written into the delivery-directory function, including the fallback order. It had been
reading my code as it landed. Two independent workstreams converging on the same contract
without a conversation is a good sign for the contract.

### What didn't work

One test I wrote was simply wrong and the suite said so:

```
$ python -m pytest tests/test_matcher_v3_crosswalk_firms.py -q
E       AssertionError: assert '4' == '0'
E         - 0
E         + 4
tests\test_matcher_v3_crosswalk_firms.py:340: AssertionError
1 failed, 30 passed
```

I had asserted that an identity absent from the universe gets an occurrence count of zero,
forgetting that the count is carried on the record itself and only *falls back* to the
universe row. The fix was to the test, not the code — but it is worth recording that the
first version of that test would have passed for the wrong reason if the fallback had been
written the other way round.

The other stumble was procedural. I tried to chain a heredoc append and a Python rewrite in
one shell call and the harness refused it:

```
This agent is isolated in the worktree [...] but this command is too complex to verify
that it stays inside the worktree. Refusing to run it
```

Fair, and the right default. Split into an editor call and a separate command.

The same isolation blocked the last step of this skill: the diary could not be written
directly into the outer_heaven clone, because a worktree-isolated agent may not write
outside its worktree. The file was handed to the lead to place instead.

### What I learned

**The delivery frame cannot be the source for the hand-off, and the reason is one
expression.** `new_delivery_rows` builds its rows with `str(rec.get(c, "") or "")`. For a
boolean `False` that evaluates to `str("")` — an empty string. The same expression appears
where the store snapshot is built. So a genuine `False` in four columns the destination
table types BOOLEAN arrives as a blank, and the load's `EMPTY_FIELD_AS_NULL` turns a blank
into NULL. "We computed this and it was false" and "we never computed this" become the same
value. I built the hand-off from the raw split frames instead, where the booleans are still
booleans, and pinned it with a test whose docstring says why, so nobody "simplifies" it back.

That is a pre-existing defect in the shipped delivery file, not something I introduced, and
I deliberately did not fix it — it changes the bytes of a file the customer already has.
Reported up instead.

**A guard that reads the file it protects beats a guard that reasons about paths.** The new
deliverable has the same filename as an irreplaceable baseline the repo still reads. I
separated them by directory as instructed, but also added a second guard that opens whatever
file is about to be replaced and refuses if its header is the old lower-case schema. The two
guards fail independently, which is the only reason either is worth having.

### What was tricky

**The suppression table has to ship empty, and arguing for that took longer than building
it.** Three pairs need permanent suppression. The table is keyed on two opaque identifiers,
and neither is known — the pairs come from a run later than the baseline file, and searching
that baseline for them returns nothing. The instinct is to guess one half and move on. The
reason not to is specific: the guard treats an identity the universe has never heard of as
*inert by design*, because a hermetic test world is a different universe rather than a
drifted table. So a wrong key produces a row that does nothing, silently, while everyone
believes the pair is suppressed. Worse than no suppression. The table ships empty with the
three pairs written out in prose, an entry template, and a test asserting it is empty so
that filling it is a visible act in a reviewable commit.

**The brief was measurably wrong in three places, and the baseline file settled all three.**
It said eleven columns needed joining in; there are nine. It said the baseline held 2,429
auto-confirmed rows against 785 in review with 49 others; the file actually holds 2,438,
785, and 40. And the destination table's own DDL comment claims the state-match column is
three-valued `true`/`equiv`/`false` — the engine and the file both say
`exact`/`equiv`/`mismatch`/`missing`. Measuring beat both the brief and the DDL comment.

**Address scoring exists in the codebase but is not part of the v3 decision, and the column
has to say so loudly.** The v2 engine fed it into its classifier; v3 does not call it at all.
Reconstructing it for the hand-off means writing a number next to a decision that never saw
it. The module docstring says that in capitals, and there is a test asserting the rules
module still contains no address signal — so the day someone wires it into a gate, a test
fails and the conversation happens.

### What warrants review

Everything that can only be confirmed by running. The engine was never executed, so nothing
here is evidence that the hand-off has the right *content* on the real data — only that it
has the right shape, types and blanks on constructed data. Specifically unverified: the
address score against real addresses, the row count, whether the occurrence-count assumption
holds (it rests on the new extract really being one row per firm-and-location, which is
stated but not measured), and the cost of the address comparison, which is a cartesian
product per row and is only cheap if both address sets stay small.

Also worth a look: the parallel agent's runbook still lists the link table among the files
the run produces, and I stopped writing it. One line, in their file, so I left it alone
rather than editing under a concurrent writer.

### Future work

The boolean-flattening defect in the delivery writer should be fixed on its own terms, with
its own decision about changing a file the customer already holds. The three suppression
keys need to come from Benny before that table does anything. And there is a sharp edge
worth closing: the baseline-comparison helper in the calibration runner reads a file by the
same name and indexes it by lower-case column, so pointing the delivery directory at the
output root would make it raise a key error rather than say what happened.
