---
name: diary
description: Write and maintain an implementation diary in the outer_heaven repo, capturing what changed, why, what worked, what failed (with exact errors and commands), what was tricky, and how to review. Activates proactively during non-trivial work (features, bug fixes, refactors, research spikes) and at session-end moments (after a PR merges, a feature ships, or a work chunk wraps up), and on /diary. Does not activate for trivial tasks like one-line fixes, config tweaks, or quick questions.
---

# diary

An implementation diary captures the narrative of work: what you did, why, what worked, what broke, what was tricky, and what needs review. The model already knows what a diary is; this skill points that behavior at one consistent location and format.

## Where diaries live

All diaries live in the **outer_heaven repo**, under `docs/diary/`, never in the project you happen to be working in.

- This is deliberate. Centralizing diaries in one synced repo means they travel across machines via git and can be read in a single sweep by the `work-style-insight` skill. Diaries scattered per project cannot be aggregated.
- It keeps customer repos clean: never write a diary into a customer's repo.
- Write into the git **working clone** (the one you commit and push from), not the installed plugin copy. On this machine the working clone is `C:\claudes_folder\repos\outer_heaven`; the path is environment-specific and recorded in memory (`project-outer-heaven`). On a machine where it differs, locate the working clone first, and if you cannot find it, ask rather than writing elsewhere.

## Customer confidentiality

Diaries about customer work stay at delivery level: name the project and describe what was built, what was decided, and what failed in the process. Keep customer-confidential detail out: data values, secrets, credentials, and proprietary business logic that is not yours to store. When in doubt, leave it out.

## File location and naming

`docs/diary/YYYY-MM-DD-<slug>.md` in the outer_heaven repo.

- The date is when work on the task started.
- The slug is free-form: a feature name, a ticket reference, or whatever describes the task.
- One file per task or feature. If work spans multiple days, steps accumulate in the same file.

## Diary file structure

```markdown
# Diary: <task description>

Brief description of the goal and context for this task.

## Step 1: <short description>

**Author:** <agent name, "main" if written by the main agent, otherwise the sub-agent name>

### Prompt Context

**Verbatim prompt:** <the exact user prompt that initiated this step>
**Interpretation:** <what the assistant understood from the prompt>
**Inferred intent:** <the underlying goal behind the prompt>

### What I did
<factual description of actions taken, files touched, commands run>

### Why
<connects the actions to the goal>

### What worked
<positive signals worth replicating>

### What didn't work
<failures recorded immediately with verbatim errors and commands>

### What I learned
<tacit knowledge that is not obvious from the code>

### What was tricky
<friction points, hidden complexity, sharp edges>

### What warrants review
<tells a reviewer where to look and how to validate>

### Future work
<implied follow-ups that fell out of the work, not a wishlist>

## Step 2: <short description>

...
```

## Working loop

1. **Implement** the change.
2. **Update the diary** with the current step.
3. **Commit together, when asked.** Include the diary file alongside the work it documents. Invoking this skill is not itself a commit request: wait for the user to ask before running `git commit`.

A "step" is a logical chunk of work, not necessarily a single commit (for example "wire up the hook", "debug the flaky test").

## Writing rules

- **Prose-first.** A narrative, not a log dump. Technical details (paths, hashes, errors) are included inline but wrapped in readable prose.
- **All sections, every step.** Never skip a section. If "What didn't work" is genuinely empty, say so explicitly.
- **Failures are gold.** Record them immediately with verbatim error messages and the exact commands that produced them. These are the most valuable parts of the diary.
- **Prompt Context is verbatim.** Copy the user's prompt exactly. Do not paraphrase that section.
- **Identify authorship.** Put an `**Author:**` line under each step heading: your sub-agent name if you are a named sub-agent, or `main` if you are the main agent.
- **Do not modify old diary entries.** Only edit a diary file created in the current session. Later work creates a new file. Diaries are a historical narrative, not a living document.

## When to activate

Activates proactively during non-trivial work: new features, bug fixes, refactors, research spikes, and at natural session-end moments while the narrative is still fresh.

Does not activate for one-line fixes, config tweaks, quick questions, or trivial changes that do not warrant narration.
