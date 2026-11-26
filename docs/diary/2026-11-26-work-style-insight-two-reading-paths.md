# Diary: give `work-style-insight` two reading paths that fit in a context

An architecture review found that step 1 of `skills/work-style-insight/SKILL.md` says "read every file in `docs/diary/`". The corpus has outgrown that instruction, and `docs/insights/` holds only `.gitkeep`: the skill has never produced an insight file. Benny decided the skill gets both a fan-out path (subagents per batch, then synthesis) and a rolling window path (latest insight file plus newer diaries). This diary covers shaping that decision into requirements and building it on the branch `fix-architecture-review-findings`.

## Step 1: Measure the corpus and turn the decision into requirements

**Author:** lead

### Prompt Context

**Verbatim prompt:** (from the main agent, relaying Benny's decision; the git and reporting instructions are left out here, the requirement text is verbatim)

> Et arkitekturreview (Gemini, verificeret) fandt, at `skills/work-style-insight/SKILL.md` trin 1 siger "read every file in `docs/diary/`". På origin/main er `docs/diary` nu 72 filer og 1,54 MB (snit 21 KB pr. dagbog). Det kan ikke læses i én kontekst. `docs/insights/` indeholder kun `.gitkeep`: skillen har aldrig leveret en indsigtsfil.
>
> Bennys beslutning: "begge". Skillen skal have to læseveje:
> 1. Delagenter pr. bunke, derefter syntese. Bruges når der ingen tidligere indsigtsfil findes, eller når mængden af dagbøger, der skal læses, er for stor til én kontekst. Hver delagent får en bunke dagbøger og returnerer kandidatmønstre med dagbogsfilnavn/dato som belæg. Hovedsessionen syntetiserer. Mønsteret findes allerede i `skills/distill-book/SKILL.md`; læs den og genbrug formen, ikke en ny opfindelse.
> 2. Rullende vindue. Når der findes en indsigtsfil: læs seneste indsigtsfil plus kun dagbøger, der er nyere end det interval, filen dækker (frontmatter `diaries_read` har interval; gør det entydigt maskinlæsbart hvis det ikke er det, fx et felt med seneste dækkede dagbogsdato/-filnavn).
>
> Krav jeg har lovet Benny:
> - Delagenterne skal returnere ALLE kandidater, også dem med ét belæg. Det er syntesen, ikke delagenten, der afgør om noget går igen. Ellers kasseres et mønster, der optræder én gang i hver bunke.
> - Giv en konkret, målbar tærskel for hvornår vej 1 vælges frem for vej 2 (fx antal filer eller samlet størrelse, målt med en kommando skillen angiver), ikke "hvis det er for stort".
> - Delagenter må ikke få hovedsessionens konklusioner eller tidligere indsigtsfil som facit; de skal læse råt.
> - Reglen om følsomme emner og "skriver aldrig i skills" bevares uændret.
>
> I samme commit-serie: Sætningen "Project status or knowledge -- that lives in memory, not here." i `skills/work-style-insight/SKILL.md` er forældet: projektstatus bor i command-deck (privat repo `singularity-consult/command-deck`), jf. kerneprofilen. Ret den i denne fil. Rør IKKE samme sætning i `CLAUDE.md` og `skills/improve-skill/SKILL.md`.

**Interpretation:** The decision is made and is not to be reopened. My job is to make it concrete enough to build: pick a measurable threshold, make the coverage of an insight file machine-readable, and hand a builder a requirement text with acceptance criteria. The corpus pass itself is out of scope; the first real run is Benny's.

**Inferred intent:** A skill that can actually be run on the corpus as it is today and that stays cheap on later runs, without losing patterns that are thin in each batch but recur across batches.

### What I did

Read `skills/work-style-insight/SKILL.md` and `skills/distill-book/SKILL.md`. Ran `git fetch origin` and created `fix-architecture-review-findings` from `origin/main` in the lead worktree. Measured the committed corpus with `git ls-tree -r -l origin/main -- docs/diary`: 72 entries including `.gitkeep`, 1,612,387 bytes in total, median diary 13.5 KB, largest 105 KB. Confirmed the local git identity is the company identity.

Then fixed three things the decision left open and wrote them into the builder's requirements:

1. The threshold. The fan-out path is taken when no insight file with a readable coverage field exists, or when the diaries still to be read number more than 12 or total more than 250 KB, whichever trips first. The same two numbers cap one subagent batch.
2. The coverage field. Besides the human-readable `diaries_read`, the insight file records the commit the corpus was read at and the last diary filename covered. New diaries are then found with a `git diff` against that commit rather than by comparing dates.
3. The batching. Batches are chronological by filename, and a single diary over the size cap gets a batch of its own.

### Why

A byte cap alone is not enough because diary size is very uneven: the largest diary is about eight times the median, so "12 files" can mean anything from 150 KB to well over 400 KB. A file cap alone has the same problem from the other side. Both, whichever trips first, is the cheapest rule that holds for both shapes.

The commit-based coverage field exists because this repo backfills diaries. The newest commit on `main` adds 18 entries dated August to November in one go. A "newer than the last covered date" rule would have silently skipped any backfilled diary dated inside an interval that an insight file already claimed to cover. A diff against the commit the corpus was read at catches those.

### What worked

Measuring before choosing. The size spread (median 13.5 KB, max 105 KB) only showed up in the per-file listing; the average of 21 KB in the brief hid it, and it is the reason for a double threshold.

### What didn't work

Nothing failed in this step. One thing to note: the brief gave the corpus as 1.54 MB, the byte count is 1,612,387. That is the same number in MiB, not a discrepancy.

### What I learned

The 250 KB figure rests on an assumed ratio of roughly 3.5 bytes per token for mixed Danish and English markdown, which puts a full batch at around 70,000 tokens. That ratio has not been measured on these diaries. The threshold is therefore a starting value, and the first real run is the measurement.

### What was tricky

"No earlier insight file means fan-out" is literal in the decision, and for a small unread set it means spawning a single subagent for one batch. I kept it literal rather than adding a third case, because the alternative is a rule with an exception before the skill has run even once.

### What warrants review

The threshold numbers and the choice of a commit hash as the primary coverage marker are choices made on Benny's behalf. Both are stated in the skill text and both are easy to change.

### Future work

The same outdated sentence about project status living in memory also sits in `CLAUDE.md` and `skills/improve-skill/SKILL.md`. It is deliberately left alone here; Benny decides on it separately.

## Step 2: Rewrite step 1 of the skill around a measured list and two paths

**Author:** builder

### Prompt Context

**Verbatim prompt:** (from the lead; excerpt, the ten numbered requirements and the git and reporting instructions are left out, the quoted text is verbatim)

> You are the builder for one change in the public repo outer_heaven. [...] `skills/work-style-insight/SKILL.md` step 1 says "read every file in `docs/diary/`". Measured on origin/main with `git ls-tree -r -l origin/main -- docs/diary`: 71 diaries plus `.gitkeep`, 1,612,387 bytes, median 13.5 KB, largest 105 KB. That does not fit in one context. `docs/insights/` holds only `.gitkeep`; the skill has never produced an insight file. The product owner (Benny) has decided the skill gets TWO reading paths. That decision is final; build it, do not redesign it.

**Interpretation:** Rewrite steps 1 and 4 of the one skill file so the reading is measured, the path choice is a number, and an insight file says in machine-readable form what it covers. Fix the outdated project-status sentence in a commit of its own. Do not run the corpus pass.

**Inferred intent:** A skill that someone can run cold on today's corpus, where every command in it has been seen to work.

### What I did

Rewrote step 1 of `skills/work-style-insight/SKILL.md` into five short parts: list what is still to read, measure it, choose the path, fan-out, rolling window. Added a paragraph to step 2 saying the recurrence judgement is made in the main session over everything read in the run. Extended the step 4 template with `read_at_commit` and `last_diary_covered` and made the "supersedes by refining" sentence say that each insight file is complete on its own. Corrected the project-status bullet to point at command-deck. Three commits on `fix-architecture-review-findings` for the skill, one for this diary.

Every command in the skill was run in this worktree. The list of all committed diaries measured 71 diaries and 1,612,387 bytes, matching the lead's numbers. The diff against the parent of `24b6e62` listed 18 diaries (408,954 bytes), and a diff against the parent of `e79b01e` listed 18 added and 1 modified, so both statuses come through.

### Why

The list goes to a file in a working directory because three different sources can produce it (everything, a git diff, a filename comparison) and one measuring command should serve all three. The same file is what the batching works from.

### What worked

`--no-renames --diff-filter=AM` on the diff: a renamed diary then shows up as an added file and is read, instead of being filtered out as a rename.

### What didn't work

My first measuring command for the uncovered set piped the diff into `xargs git ls-tree -l HEAD --`. The agent harness refused to run it:

> this command feeds git its arguments from stdin at runtime (xargs/parallel), so the repository it targets cannot be verified. Refusing to run it

A command I cannot run does not go in the skill, so I replaced it with `grep -F -f "$W/to-read.txt"` over the full `git ls-tree -r -l` listing. That turned out better on its own terms: with an empty list `xargs` would have run `git ls-tree` with no path and listed the repo root, while the `grep` form prints "0 diaries, 0 bytes". A compound command with `cd`, a shell variable and several git calls was refused the same way ("names git in a form too complex to verify"), so each command was tested as a separate call.

### What I learned

The fan-out must use fresh subagents, not a fork of the session. A fork inherits the whole conversation, including a prior insight file the main session has read, which defeats "the subagents read raw". The skill now says so.

### What was tricky

The thin-corpus stop and the new "nothing to read" stop look alike but are judged on different sets: thin corpus on all committed diaries, nothing to read on the list. Two new diaries after an insight file are not a thin corpus. The skill states which set each stop uses.

### What warrants review

The commands were tested with literal paths, not with a `$W` variable, because of the harness limit above; the text is otherwise identical. The fallback (`awk` filename comparison) was tested against one filename only. No subagent was spawned and no insight file was written, so the prompt checklist in 1d and the whole synthesis are untested by design. The field names `read_at_commit` and `last_diary_covered` are my choice.

### Future work

The intro still says the skill "reads every implementation diary"; that holds across runs but not per run, and was left alone as outside the listed changes. A diary that is modified but uncommitted is left out of the run even though an older version of it is committed; the first real run will show whether that matters. The threshold numbers wait for a measured token ratio.

## Step 3: A fallback for an insight file written without coverage fields

**Author:** builder

### Prompt Context

**Verbatim prompt:** (from the main session; excerpt, the measured facts, the limits and the git and reporting instructions are left out, the quoted text is verbatim)

> With the current skill text (step 1a, first case: "No insight file, or one with neither field: every committed diary", and step 1c first bullet), such a file sends the next run through the fan-out over the whole corpus again. Change that:
>
> - When the latest insight file has no `read_at_commit`, the fallback is the commit that ADDED the insight file, used as `read_at_commit`. Give the command (`git log --diff-filter=A -1 --format=%H -- docs/insights/<file>`, run on up-to-date `main` like the other commands in step 1) and then the existing diff command applies unchanged.
> - Only when that commit cannot be found either does the skill fall back further: to `last_diary_covered` if present (existing fallback), and otherwise to reading every committed diary.
> - State the weakness in the text [...]

**Interpretation:** Add one case and one command to step 1a, keep the order of fallbacks explicit, and make 1c agree with it. No restructure.

**Inferred intent:** The first insight file exists on `main` and has neither coverage field. The next run should read what came after it, not the whole corpus a second time.

### What I did

In `skills/work-style-insight/SKILL.md` step 1a the first case now covers only "no insight file". A new case after the reachable `read_at_commit` case handles a file without that field: look up the commit that added the file and use it in the existing diff command. The filename fallback now also takes over when no such commit exists, and says that a file with no `last_diary_covered` either means every committed diary is read. One sentence states that a new insight file is always written with both fields. The first bullet in 1c now reads "no prior insight file, or no coverage point can be established for it".

Both commands were run against `origin/main`, because the insight file is not on this branch. The lookup returned `c96b0faf1e14bcb7213f2c143086d21098f4b262`. The diff from that commit to `origin/main` over `docs/diary` returned one line: one added diary. On this branch, where the file does not exist, the lookup printed nothing and exited 0, which is the "go to the next case" condition in the text.

In the same series, the last section of `skills/house-style/SKILL.md` was corrected: the core profile carries some of the rules and the skill is the complete set, instead of the profile being called a copy of them.

### Why

With the old first case, one diary added after the first insight file would have cost a fan-out over more than seventy diaries. The commit that added the file is the nearest thing git holds to the point the corpus was read at.

### What worked

Running the lookup where the file is absent. It showed the empty-output behaviour the text relies on, without needing a constructed case.

### What didn't work

Nothing failed in this step.

### What I learned

The add commit is a weaker marker than `read_at_commit`. The commit that added the first insight file also added a diary. Whether that diary was read before the insight file was written cannot be determined from git, and the diff from that commit leaves it out. The skill text now states this and tells the run to put it in the insight file's Notes.

### What was tricky

The cases in 1a are taken by "the first that applies", so the new case needed an explicit hand-over ("if the command prints nothing, go to the next case") to keep the chain readable in that form.

### What warrants review

A file whose `read_at_commit` is present but unreachable still goes to the filename fallback, not to the add commit. The brief asked for the add commit only when the field is missing; using it in the unreachable case too would be a further change. The `1b` "Nothing to read" stop and the step 4 template were read against the new text and left unchanged. No run of the skill was made, so the new case is untested end to end.

### Future work

The diary that shares a commit with the first insight file is the concrete instance of the stated weakness. The next real run will not list it; whoever runs it decides whether to read it by hand.

## Step 4: Unreachable `read_at_commit`, merge of main, version bump

**Author:** builder

### Prompt Context

**Speaker:** agent brief
**Verbatim prompt:** (from the main session; excerpt, the measured facts, the limits and the git and reporting instructions are left out, the quoted text is verbatim)

> In step 1a today: a file with NO `read_at_commit` falls back to the commit that added the insight file; a `read_at_commit` that EXISTS BUT IS NOT REACHABLE (for example after a history rewrite) goes straight to the filename fallback (`last_diary_covered`). Change that: an unreachable `read_at_commit` also goes to the add commit of the insight file first, and only then to the filename fallback. [...] Add one sentence that `-1` gives the most recent add if the file was deleted and re-added.
>
> Step 2: merge `origin/main` into the branch (merge, NOT rebase) [...] On a conflict in `skills/diary/SKILL.md`, `README.md`, `agents/lead.md` or `agents/reviewer.md`: keep BOTH sides' changes. [...]
>
> Step 3: version bump, separate commit AFTER the merge. Only if BOTH hold: the version on `origin/main` is exactly `0.22.0` [...] and `git ls-remote origin "refs/tags/v0.23.0"` prints nothing.

**Benny's own words:** none quoted in the brief
**Interpretation:** Three small pieces in a fixed order: one more hand-over in the 1a chain, a merge commit that keeps both sides, and a minor bump on top of the merged tree. Then checks that nothing from main was lost.
**Inferred intent:** Close the gap Step 3 left under "What warrants review", and make the branch mergeable on top of what main got in the meantime.

### What I did

In `skills/work-style-insight/SKILL.md` step 1a the add-commit case now reads "The file has no `read_at_commit`, or it is not reachable", and the filename fallback is headed "No commit added the insight file". One sentence says that `-1` gives the most recent add if the file was deleted and added again. Commit `39b5e78`.

`git fetch origin` left `origin/main` at `10443b4`, as measured in the brief. `git log origin/main..HEAD --stat` gave the branch's own file list before the merge. Then `git merge --no-ff --no-commit origin/main`. The method is the one in `skills/merge-conflict-safety/SKILL.md`, read from the worktree; the skill was not invoked through the plugin.

One conflict, in the hand-back list of `agents/reviewer.md`. Main had added two bullets (non-code mode, images sent) directly above the last bullet and left that bullet as it was. The branch had rewritten that last bullet to cover the whole report. The resolution keeps main's two bullets and the branch's wording of the last one. Merge commit `b8a5eb1`.

`README.md`, `agents/lead.md` and `skills/diary/SKILL.md` merged without conflict. Each was read against both sides' diffs: `README.md` has `curate` and `house-style` in the skills list and the list sorts cleanly; `agents/lead.md` has the review-mode paragraph from main and the diary-location and `house-style` paragraphs from the branch; `skills/diary/SKILL.md` has the branch's working-clone bullet and working-loop item 3 and main's secrets scan and `Speaker` lines.

The version on `origin/main` was `0.22.0` and the remote had no `v0.23.0` tag, so `.claude-plugin/plugin.json` went to `0.23.0`. Commit `4573a9c`. No other file carries the version: `marketplace.json` has none, and `hooks/scripts/session-start.sh` reads it from `plugin.json`.

### Why

An unreachable hash and a missing field leave the run in the same position: no usable `read_at_commit`. The add commit is found by walking from `HEAD`, so it is reachable by construction and a better coverage point than a filename comparison.

### What worked

`--no-commit` on the merge. It stopped before the commit, so the three auto-merged files could be read while the merge was still open.

### What didn't work

The merge stopped on one file:

```
Auto-merging README.md
Auto-merging agents/lead.md
Auto-merging agents/reviewer.md
CONFLICT (content): Merge conflict in agents/reviewer.md
Auto-merging skills/diary/SKILL.md
Automatic merge failed; fix conflicts and then commit the result.
```

A check command that chained several git calls with pipes and process substitution was refused by the worktree isolation ("this command names git in a form too complex to verify that it stays inside the worktree"). The calls were then run one at a time.

### What I learned

The conflict was one of adjacency, not of content. Main did not change the "probably" bullet; it added lines that touch it, and that is enough for git to stop.

### What was tricky

The brief expected conflicts in up to four files and named `agents/reviewer.md` as one that auto-merged. It was the other way round: that file was the only conflict.

### What warrants review

`python skills/second-opinion/scripts/test_second_opinion.py` printed `Ran 81 tests in 0.280s` and `OK`; the tests mock the key and the network call. `git diff --stat origin/main...HEAD` and `git diff --stat origin/main HEAD` list the same 16 files, all of them the branch's own. No long dash in any line the branch adds. Not verified: the new 1a wording has not been exercised by a run of the skill, and no unreachable `read_at_commit` was constructed to test it.

### Future work

The tag `v0.23.0` and the release belong on the merge commit on `main`, after the PR is merged. Nothing was tagged here.
