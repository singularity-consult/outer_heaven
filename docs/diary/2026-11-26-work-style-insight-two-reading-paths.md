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
