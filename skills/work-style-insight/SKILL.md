---
name: work-style-insight
description: Read the diary corpus in docs/diary/ and distil patterns in how Benny works and decides, plus derived suggestions for the skills and agents. Writes a dated insight file to docs/insights/ with two distinct sections (patterns about Benny; derived suggestions). Use when Benny invokes /work-style-insight or asks for a read on his working style across sessions. Not automatic, and never edits skills directly.
---

# Work-style insight

Where `improve-skill` learns from a single conversation, this skill learns from the **corpus**: it reads every implementation diary in `docs/diary/` and distils the patterns that only show up across many sessions -- how Benny works, how he decides, what he repeatedly corrects, what he repeatedly values. The output is a dated insight file in `docs/insights/`, never a memory entry (memory does not travel across machines; this repo does).

The premise: one diary is an anecdote; the corpus is evidence. Friction or a preference that recurs across sessions is a real signal about how to work with Benny, and it deserves to be written down where it can be read in one sweep and carried to other machines.

## When to use

**User-invoked only.** Benny runs `/work-style-insight` or asks for a read on his working style, his patterns, "what have you learned about how I work", or "what should we change across the board". This skill never fires automatically -- it is a deliberate, reflective pass, not a per-session reflex.

## When not to use

- **Single-conversation friction about a specific skill** -- that is [[improve-skill]], driven by the current conversation, not the corpus.
- **Project status or knowledge** -- that lives in memory, not here.
- **Sensitive personal matters** (health, finance, private projects) -- these never enter this repo. They are not in the diaries and must not be introduced here.

## Step 1: Check the corpus is worth reading

Read `docs/insights/` for prior insight files (so this run refines rather than repeats them), then read every file in `docs/diary/`.

A corpus is too thin to support real patterns if there are only a couple of diaries, or they all describe one piece of work. If so, say plainly that there is not yet enough signal, name how many diaries exist, and stop. Do not manufacture patterns from a single session -- that is `improve-skill`'s job, not this one.

## Step 2: Find patterns, not anecdotes

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

A later run supersedes earlier files by refining them; it does not delete them (the dated trail shows how the read evolved). Use this shape:

```markdown
---
date: <YYYY-MM-DD>
diaries_read: <count, and the date range covered>
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
