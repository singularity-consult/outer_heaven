---
name: improve-skill
description: Review the current conversation for outer_heaven skills that could be improved (corrections, friction Benny had to flag manually, missed triggers, anything else worth flagging) and ship the improvements back to the outer_heaven repo via a lightweight branch-and-push flow. Use when Benny invokes /improve-skill or asks to make a skill better, smarter, or less friction-prone. May also be suggested at end of session when there is concrete signal that a skill underperformed; otherwise stay silent.
---

# Improve skill

A skill for incrementally improving other outer_heaven skills based on what just happened in the current conversation. The premise: every real session is a free user study. If a skill underperformed -- gave incomplete advice, missed something Benny had to ask for manually, did not trigger when it should have -- that is signal worth turning into a concrete improvement.

This skill harvests that signal and ships it back to the `outer_heaven` repo (https://github.com/singularity-consult/outer_heaven) as a branch you push, then a PR Benny opens and merges.

## When to use

**Primarily user-invoked.** Benny runs `/improve-skill` or says things like "make the X skill better", "the git skill should also cover Y", "this skill missed something". He may bring his own idea about what to fix; that idea joins the findings list rather than replacing it.

**Proactively suggest at end-of-session moments only when there is concrete signal.** Examples of concrete signal:

- Benny corrected output that came from a skill's guidance
- Benny asked manually for something the invoked skill should have done unprompted
- The assistant supplemented with knowledge that is literally another skill's job (a missed trigger)
- An invoked skill produced something out of date, contradicted another skill, or confused the assistant

No signal, no suggestion. Be quiet by default. Only speak up when there is something specific to point at.

## When not to use

- **Writing a brand-new skill from scratch** -- that is a build task, not this.
- **Fixing code bugs in Benny's projects or customer repos** -- those are normal edits.
- **Editing project knowledge or status** -- that lives in memory, not in this repo.

This skill only edits `skills/*/SKILL.md`, the subfiles those skills reference, and `agents/*.md`. It **only ever touches the outer_heaven repo.** Never a customer repo, never the fabrik clone (`_analyze_fabrik` is read-only inspiration).

## Step 1: Gather signals from the conversation

Read back over the current conversation. The candidate set is *any outer_heaven skill the conversation gives signal about*, whether it was invoked or not. A skill ends up on the list one of two ways:

- **It was invoked**, and something was off.
- **It should have been invoked but was not**, inferred from the assistant supplementing with knowledge that is literally another skill's job.

For each candidate skill, look for these signal types:

1. **Corrections.** Places where Benny pushed back on output that came from the skill's guidance ("nej", "stop", "ikke sådan"), or where the assistant changed approach mid-task because of feedback.
2. **Manual asks the skill should have covered.** Moments where Benny explicitly requested something within the skill's stated scope but the skill did not do it unprompted. If the skill had simply done the thing, Benny would not have had to interrupt.
3. **Missed triggers.** A skill that obviously should have fired did not, inferred from the assistant supplementing with knowledge already documented in another skill.
4. **Anything else worth flagging.** Outdated examples, confusing phrasing, contradictions with another skill, missing cross-references, stale tool names, stale paths. If it would clearly improve the skill, flag it. Do not omit a real observation because it does not fit a category.

Skills get better over time only if friction translates into edits. The model is the witness to its own confusion and to Benny's corrections; this skill is the mechanism for turning that into a diff.

## Step 2: Present findings to Benny

Summarise each finding as a one-line entry:

```
[skill-name]: [what was observed in the conversation] -> [proposed change type: trigger / content / structure / redesign]
```

Show the full list, ask which to act on, and accept any extras Benny wants to add. If he invoked with a specific idea, fold it into the same list as another finding -- do not drop the conversation-derived ones in favour of his idea.

If after the pass there are no findings, say so plainly and stop. Do not manufacture work.

## Step 3: Classify each accepted finding

Classify each finding Benny wants to act on as one of:

- **Concrete fix** -- the right change is clear (description tweak, added example, rule clarification, missing cross-reference, fixing a stale fact or path). Goes straight into the branch.
- **Fuzzy / redesign** -- the signal is real but the right fix is not obvious, or the change is structural enough to deserve discussion before code ("split this skill in two", "the trigger model is wrong"). Discuss in chat first; if the discussion converges on a concrete change, ship it on the branch; if it does not, write the thinking into `docs/insights/` so it is not lost. Do not default to "park it" just because the finding started fuzzy.

A single invocation may produce several concrete fixes across one or more skills on one branch. That is fine.

## Step 4: Make the edits in the working clone

The skill almost always runs from the **installed** plugin copy, but it must **write to the git working clone**, not the plugin cache:

- **Working clone:** `C:\claudes_folder\repos\outer_heaven` (this path is machine-specific; on other machines it is wherever the clone lives).

Before editing:

1. Confirm the working tree is clean (`git -C C:/claudes_folder/repos/outer_heaven status -s`). If there is unrelated in-progress work, stop and ask Benny how to proceed rather than mixing changes.
2. Create a branch off `main`. **Branch naming for own repos is a kebab-case dash sentence with no prefix** (the `feature/`, `hotfix/`, `fix/`, `release/` prefixes are for customer repos only). Example: `improve-git-skill-identity-lookup`.

   ```bash
   git -C C:/claudes_folder/repos/outer_heaven checkout main
   git -C C:/claudes_folder/repos/outer_heaven pull
   git -C C:/claudes_folder/repos/outer_heaven checkout -b improve-<slug>
   ```

   Use forward slashes in git paths when invoking through bash; backslashes get eaten.

Make the edits. Keep them surgical: if a finding is "the example is stale", change the example; do not rewrite the section. Big rewrites belong in a `docs/insights/` note for discussion first.

Follow the repo conventions in `C:\claudes_folder\repos\outer_heaven\CLAUDE.md`:

- **README.md:** add or update the one-line entry (skills under "Available skills", sub-agents under "Available sub-agents"), alphabetical, in the same commit.
- **Version bump** in `.claude-plugin/plugin.json`: a change to existing functionality is a **patch** bump; a new skill or sub-agent is a **minor** bump.
- **Git tag** `vX.Y.Z` on the version-bump commit.

## Step 5: Self-review, then ship

This is a lightweight flow: branch, self-review, push, hand Benny the PR URL.

1. **Self-review the diff** before committing. Read `git diff` end to end. Check: does the edit generalise to *every future invocation* of the skill, not just this conversation? Is anything left half-changed? Does the description still match the body?
2. **Commit** using the [[git]] skill's conventions (commit subject and body in English; never Co-Authored-By or Claude as author; identity in this repo is `singularity-consult <benny@singularityconsult.dk>`, already set locally). One commit per invocation is fine even when several skills are touched.
3. **Push the branch and the tag.** Push works as singularity-consult via the stored credential; no login prompt.

   ```bash
   git -C C:/claudes_folder/repos/outer_heaven push -u origin improve-<slug>
   git -C C:/claudes_folder/repos/outer_heaven push origin vX.Y.Z
   ```

4. **Do not use `gh` to open the PR.** On this machine `gh` is authenticated as `bechseges`, who has no access to the singularity-consult repo, so `gh pr create` fails. Instead, give Benny the compare URL so he opens and merges the PR in the browser as singularity-consult:

   `https://github.com/singularity-consult/outer_heaven/compare/main...improve-<slug>`

   (If `gh` has been set up with the singularity-consult account via `gh auth switch -u singularity-consult`, opening the PR with `gh pr create` is fine too. Default to the URL.)

**PR body shape** (paste into the web form). The framing is "findings from a conversation", not "feature work":

```markdown
## What was observed

<short summary of the friction or gap, drawn from the current conversation>

## What changed

<per-skill bullet of the actual edits, e.g. "git: added identity-lookup table for the singularity-consult account">

## Why

<the reasoning, so a future reader can judge whether the change still makes sense>
```

Report the branch name and compare URL back when done. Merging, the version-bump review, and creating the GitHub release are Benny's call.

## Notes on tone

- Be specific. "The git skill could mention identity" is useless without pointing at where in the conversation that mattered. Cite the moment.
- Generalise from the example. The change affects every future invocation of the skill -- write it for that universe, not just this conversation.
- Keep edits surgical. Big rewrites belong in a `docs/insights/` note first.
- Do not pad. If there is one finding, the diff has one bullet under "What changed". That is fine.
- Never assume the change reached the installed copies. Without a version bump, remote installs stay cached on the old version -- bump and tag every time.
