---
name: work-style-insight
description: Read the diary corpus in docs/diary/ and distil patterns in how Benny works and decides, plus derived suggestions for the skills and agents. Writes a dated insight file to docs/insights/ with two distinct sections (patterns about Benny; derived suggestions). Use when Benny invokes /work-style-insight or asks for a read on his working style across sessions. Not automatic, and never edits skills directly.
---

# Work-style insight

Where `improve-skill` learns from a single conversation, this skill learns from the **corpus**: each run reads the implementation diaries in `docs/diary/` that the previous insight file does not cover (every diary on the first run, so the whole corpus is covered across runs) and distils the patterns that only show up across many sessions -- how Benny works, how he decides, what he repeatedly corrects, what he repeatedly values. The output is a dated insight file in `docs/insights/`, never a memory entry (memory does not travel across machines; this repo does).

The premise: one diary is an anecdote; the corpus is evidence. Friction or a preference that recurs across sessions is a real signal about how to work with Benny, and it deserves to be written down where it can be read in one sweep and carried to other machines.

## When to use

**User-invoked only.** Benny runs `/work-style-insight` or asks for a read on his working style, his patterns, "what have you learned about how I work", or "what should we change across the board". This skill never fires automatically -- it is a deliberate, reflective pass, not a per-session reflex.

## When not to use

- **Single-conversation friction about a specific skill** -- that is [[improve-skill]], driven by the current conversation, not the corpus.
- **Project status or knowledge** -- that lives in command-deck (the private repo `singularity-consult/command-deck`), not here.
- **Sensitive personal matters** (health, finance, private projects) -- these never enter this repo. They are not in the diaries and must not be introduced here.

## Step 1: Measure the corpus, then read it by one of two paths

The corpus does not fit in one context, so measure before reading any diary. Run the commands below in the working clone (see step 4), in Git Bash, on an up-to-date `main`. `$W` is a working directory outside the clone (a temp or scratchpad directory); nothing in it is ever committed.

### 1a. List what is still to read

Find the latest file in `docs/insights/` and look only at its frontmatter for now: `read_at_commit` and `last_diary_covered` (see step 4). Then write the list of diaries to read to `$W/to-read.txt`, by the first case that applies:

- **No insight file, or one with neither field:** every committed diary.

  ```bash
  git ls-tree -r --name-only HEAD -- docs/diary | grep -v '\.gitkeep$' > "$W/to-read.txt"
  ```

- **`read_at_commit` is reachable** (`git cat-file -e "<read_at_commit>^{commit}"` exits 0): every diary added or modified since that commit.

  ```bash
  git diff --no-renames --diff-filter=AM --name-only <read_at_commit> HEAD -- docs/diary > "$W/to-read.txt"
  ```

- **`read_at_commit` is not reachable** (fallback): the filenames that sort after `last_diary_covered`. This misses backfilled diaries and diaries modified after they were covered; say so in the insight file's Notes.

  ```bash
  git ls-tree -r --name-only HEAD -- docs/diary | awk -v last="docs/diary/<last_diary_covered>" '$0 > last' > "$W/to-read.txt"
  ```

The commit is the primary marker because diaries get backfilled with older dates (one commit on `main` added 18 entries dated August to November); a "newer than date X" rule silently skips them, a diff against the commit does not.

### 1b. Measure it

```bash
git ls-tree -r -l HEAD -- docs/diary | grep -F -f "$W/to-read.txt" | awk '{n++; s+=$4} END {printf "%d diaries, %d bytes\n", n, s}'
```

Replace the `awk` program with `'{print $4, $5}'` to get bytes and path per diary, which is what batching needs.

All of this counts **committed** diaries only. `git status --porcelain -- docs/diary` lists the uncommitted ones (untracked or modified). They are not read in this run: name them in the report and in the insight file's Notes. Once committed, the next run's diff picks them up.

Stop here in two cases, and say so plainly with the numbers:

- **Nothing to read:** an insight file exists and the list is empty. There is nothing new since the last run.
- **Thin corpus** (judged on all committed diaries, not on the list): A corpus is too thin to support real patterns if there are only a couple of diaries, or they all describe one piece of work. If so, say plainly that there is not yet enough signal, name how many diaries exist, and stop. Do not manufacture patterns from a single session -- that is `improve-skill`'s job, not this one.

### 1c. Choose the path

Take the **fan-out** when either holds; otherwise take the **rolling window**:

- there is no prior insight file with a readable `read_at_commit` or `last_diary_covered`; or
- the list is more than 12 diaries or more than 250 KB (256,000 bytes), whichever trips first.

These two numbers are a starting value based on an assumed ratio of about 3.5 bytes per token, not a measured one; adjust them after real runs.

### 1d. Fan-out: subagents read raw, the main session synthesises

The form is the one in [[distill-book]]: the main session never loads the raw material.

1. **Batch** the list chronologically by filename. A batch holds at most 12 diaries and 250 KB; a single diary over 250 KB gets a batch of its own.
2. **Spawn one subagent per batch, all in one go** so they run concurrently. Use fresh subagents that do not inherit this session's context. Each prompt is self-contained and holds:
   - the task in one line (find candidate patterns in how Benny works and decides, from these implementation diaries), the working clone path, and the exact diary paths of its batch;
   - the five categories from step 2 (decision style, recurring corrections, what he values or rejects, workflow shape, tooling and stack reality), by name only, as places to look and not as answers;
   - the instruction to return **every** candidate pattern, including one seen in a single diary, with no ranking, filtering or merging away of thin ones;
   - per candidate: the category, one line on what it is, and the evidence as diary filename(s) plus the moment in each diary (step heading and what happened);
   - the rule that sensitive personal matters (health, finance, private projects) are never carried from a diary into the candidates;
   - the instruction to write the candidates to `$W/candidates-<nn>.md` (give the absolute path; the subagent does not have `$W`) and reply with only a short token (for example "done batch 3").
3. **Keep the subagents blind.** Do not give them this session's conclusions or expectations, example patterns, or any prior insight file. They read raw.
4. **Synthesise** in the main session from the candidate files (step 2), then delete `$W`.

Why every candidate is returned: recurrence is judged in synthesis, across batches. A pattern that shows up once in each batch would otherwise be dropped by every subagent as a one-off.

### 1e. Rolling window: latest insight file plus what it does not cover

Read the latest insight file in full, then read the diaries in the list directly in the main session.

If the list trips the threshold in 1c, send it through the fan-out in 1d instead of reading it directly. The subagents still read raw and never see the insight file; only the main session combines their candidates with it.

## Step 2: Find patterns, not anecdotes

This judgement is made in the main session, over everything read in this run together: all batches at once on the fan-out path, and together with the prior insight file on the rolling window path. A prior pattern counts as evidence already cited; new diaries can strengthen it, contradict it, or lift a hypothesis from its Notes into a pattern.

A finding qualifies only if it **recurs across multiple diaries** or is a single but unmistakable standing preference. For each, hold the evidence: which diaries, which moments. Look for:

- **Decision style.** How Benny reaches decisions (for example: wants the trade-offs spelled out before choosing; rejects anything called "probable" without verification; prefers verifying over assuming).
- **Recurring corrections.** The same kind of pushback in more than one session -- a sign the standing guidance or a skill is misaligned, not a one-off.
- **What he consistently values or rejects.** Tone, verbosity, where he wants full paths, where he wants to be asked versus where he wants the obvious default taken.
- **Workflow shape.** How work tends to flow (incremental one-step-at-a-time builds, branch and verify before push, test green before triggers).
- **Tooling and stack reality.** Recurring constraints worth encoding (auth/account boundaries, prod-safety rules, repo-ownership lines).

Cite the evidence. "Benny prefers X" is useless without "(diaries 2026-06-13, 2026-06-15)". A pattern with one citation is a hypothesis; say so.

## Step 3: Derive suggestions, kept separate

For each pattern that implies a change, write a **derived suggestion**: what the skills, agents, or core profile could do differently to fit the pattern. Keep these strictly in their own section -- the reader must be able to tell "here is what is true about Benny" apart from "here is what we might change about the agent".

This skill **does not make those changes.** It only records them. Acting on a suggestion is a separate, deliberate step: a concrete skill edit goes through [[improve-skill]]; an agent or profile change is its own task. Keeping the analysis and the edit apart is the point -- it stops a fuzzy corpus-level read from silently rewriting a skill.

## Step 4: Write the insight file

Write to `docs/insights/<YYYY-MM-DD>-work-style.md` in the working clone:

- **Working clone:** `C:\claudes_folder\repos\outer_heaven` (machine-specific path; wherever the clone lives on other machines). The skill runs from the installed plugin copy but must write to the git clone, not the plugin cache.

A later run supersedes earlier files by refining them: its file is complete on its own, carrying forward the patterns from the latest file that still hold together with what the newly read diaries add, so the next run needs only that one file. It does not delete earlier files (the dated trail shows how the read evolved). Use this shape:

```markdown
---
date: <YYYY-MM-DD>
diaries_read: <count read in this run, count covered in total, and the date range covered>
read_at_commit: <full hash from `git rev-parse HEAD` when the list in step 1a was made>
last_diary_covered: <filename only, the last committed diary by filename at that commit>
---

# Work-style insight -- <date>

## Patterns about Benny

- **<pattern>** -- <what it is> (evidence: <diary dates / moments>)
- ...

## Derived suggestions

- **<target: skill / agent / profile>** -- <what could change, and why it follows from the pattern above>
- ...

## Notes

<anything provisional: single-citation hypotheses, contradictions between diaries, gaps where more diaries would help>
```

Keep both lists tight. A pattern with no evidence does not go in. A suggestion that does not follow from a listed pattern does not go in.

## Step 5: Ship it

Commit and push using the [[git]] skill's conventions (English commit message; identity `singularity-consult <benny@singularityconsult.dk>`, already set locally; never Co-Authored-By or Claude as author). Adding an insight file is content, not new plugin functionality, so it does **not** need a version bump -- insight files are artifacts, not capability. Push to `main` (or, if Benny prefers review, a kebab-case dash-sentence branch with no prefix, then the compare URL: `https://github.com/singularity-consult/outer_heaven/compare/main...<branch>`).

Report the file path back, summarise the headline patterns in two or three lines, and name any suggestion worth acting on now. Whether to act on a suggestion is Benny's call.

## Notes on tone

- Patterns, not flattery. This is a mirror, not praise. State what the diaries show, including the awkward bits (recurring corrections are the most useful findings).
- Evidence or it did not happen. Every pattern cites diaries. No citation, no claim.
- Hold the line between observation and action. Section 1 describes Benny; section 2 proposes changes; this skill performs neither edit.
