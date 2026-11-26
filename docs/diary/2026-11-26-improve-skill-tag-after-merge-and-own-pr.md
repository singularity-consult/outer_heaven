# Diary: `improve-skill` tags after merge and opens its own PR

A third finding from the same architecture review, built on the branch `fix-architecture-review-findings`. The shipping steps in `skills/improve-skill/SKILL.md` tag the version on the branch before merge and tell the agent not to open the PR. Both are out of date. Benny has approved the replacement flow; this diary covers building it.

## Step 1: Read the current flow and hand the change to a builder

**Author:** lead

### Prompt Context

**Verbatim prompt:** (from the main agent, relaying what Benny approved; git and reporting instructions and the follow-up to the previous finding are left out)

> A. `skills/improve-skill/SKILL.md`: tag efter merge
> - Branchen bumper stadig versionen i `.claude-plugin/plugin.json`.
> - Lige før merge: `git fetch` og tjek versionen på `origin/main`. Er nummeret taget (en anden branch er merget først), rettes bumpet til næste ledige i en ny commit, før der merges. Baggrund der gerne må stå kort: to branches har i praksis bumpet til samme nummer to gange.
> - Tagget sættes IKKE på branchen og pushes ikke med branchen. Efter merge sættes `vX.Y.Z` på merge-committen på `main`, pushes, og GitHub-releasen laves derfra.
> - Merge sker med merge-commit (`gh pr merge --merge`), ikke squash.
> - Merge, tag og release kræver stadig Bennys ja; skillen må ikke gøre det på egen hånd. Men skillen skal slutte med at spørge om det (ét spørgsmål), så tag-trinnet ikke bliver glemt efter merge. Skriv også et tjek: en version på `main` uden tilsvarende tag er en fejltilstand, der skal nævnes for Benny.
>
> B. `skills/improve-skill/SKILL.md`: skillen opretter selv PR'en
> - Efter push: `gh auth switch -u singularity-consult`, `gh pr create` (base main), derefter `gh auth switch -u bechseges` tilbage, også hvis PR-oprettelsen fejler. Rapportér PR-URL'en.
> - PR-tekst: ingen "Generated with Claude Code"-linje.
> - Compare-URL'en beholdes kun som fallback, hvis `gh` fejler.
> - Ret også linje 10 og 99 ("a PR Benny opens and merges", "hand Benny the PR URL") og linje 132, så hele filen er konsistent.
> - `skills/git/SKILL.md` har en sætning "This is why the improve-skill flow avoids `gh pr create` and hands back a compare URL." Den bliver usand; ret den.
> - Tjek med grep om `skills/work-style-insight/SKILL.md` trin 5, `README.md`, `CLAUDE.md` eller andre skills beskriver samme forældede flow (tag før merge, compare-URL som eneste vej). Ret det, der direkte modsiger A/B; rapportér resten.

**Interpretation:** Rewrite the shipping part of one skill (steps 4 and 5 and the places that summarise them), correct one sentence in the `git` skill, and sweep the rest of the repo for the same outdated flow.

**Inferred intent:** Two branches should not be able to claim the same version number, a tag should always sit on a commit that is on `main`, and the PR should not depend on Benny pasting a URL into a browser.

### What I did

Read `skills/improve-skill/SKILL.md` in full and grepped the `git` skill, `README.md`, `CLAUDE.md`, the hooks and the agents for tag, compare URL and `gh` mentions. Found the outdated flow at the lines the brief names, the sentence in `skills/git/SKILL.md` line 26, the compare URL in step 5 of `skills/work-style-insight/SKILL.md`, and one more: `CLAUDE.md` line 47 says the tag goes "on the version-bump commit". Started this diary and handed the requirements to a builder.

### Why

The tag-on-branch rule fails in exactly the situation the repo is in now: more than one open branch has bumped to the same version. A tag set before merge then either collides or points at a commit that is not on `main`.

### What worked

Grepping before briefing. The `CLAUDE.md` line was not in the brief and contradicts the new rule directly.

### What didn't work

Nothing failed in this step.

### What I learned

The instruction file of the repo states the old tag rule too, so correcting only the skills leaves the contradiction one level up.

### What was tricky

`CLAUDE.md` is the repo's instruction file. My standing rules do not let a message from another agent authorise a change to it, and the approval for this finding reached me through the main agent. I therefore left `CLAUDE.md` line 47 out of the builder's scope and report it for Benny's own yes.

### What warrants review

That the skill still stops and asks before merge, tag and release, and that the account switch back happens on the failure path as well.

### Future work

`CLAUDE.md` line 47 needs the same correction once Benny has said yes to it himself.

## Step 2: Rewrite the shipping steps and sweep for the old flow

**Author:** builder

### Prompt Context

**Verbatim prompt:** (from the lead; the follow-up to the previous finding, the hard limits, and the diary, git and reporting instructions are left out)

> ## A. `skills/improve-skill/SKILL.md`: tag after merge
> - The branch still bumps the version in `.claude-plugin/plugin.json`.
> - Just before merge: `git fetch` and check the version on `origin/main`. If the number is taken (another branch merged first), correct the bump to the next free number in a NEW commit before merging. [...]
> - The tag is NOT set on the branch and not pushed with the branch. After merge, `vX.Y.Z` goes on the merge commit on `main`, is pushed, and the GitHub release is made from there.
> - Merge is a merge commit (`gh pr merge --merge`), not squash.
> - Merge, tag and release still need Benny's yes; the skill never does them on its own. But the skill must END by asking for it, as ONE question, so the tag step is not forgotten after merge. [...]
> - Add a check: a version on `main` with no matching tag is an error state that must be named to Benny. Give a concrete way to see it [...]; test the commands you write here read-only and report their output. Do NOT create, push or delete any tag.
>
> ## B. `skills/improve-skill/SKILL.md`: the skill opens the PR itself
> - After push: `gh auth switch -u singularity-consult`, `gh pr create` (base main), then `gh auth switch -u bechseges` back, ALSO when PR creation fails. Report the PR URL. The same switch-and-switch-back applies to the later `gh pr merge` and `gh release create`.
> - PR body: no "Generated with Claude Code" line (and no Co-Authored-By anywhere). [...]
> - The compare URL stays only as a fallback when `gh` fails.
> - Also fix line 10 [...], line 99 [...] and line 132 so the whole file is consistent. [...]
> - `skills/git/SKILL.md` line 26 [...] becomes untrue; correct that sentence only.
> - Grep the whole repo [...] for the same outdated flow [...]. Fix what directly contradicts A/B, minimally; report the rest with file and line.
>
> HARD EXCEPTION: do NOT edit `CLAUDE.md` at all. [...]

**Interpretation:** Rewrite items 3 and 4 of step 5 in `improve-skill`, add an item 5 that asks the one question and spells out the yes and no paths, and correct the five summary places in the same file plus the sentences in the `git` skill and `work-style-insight` that restate the old flow.

**Inferred intent:** Someone running the skill cold should not be able to tag before merge, forget the tag after merge, or stop at a URL for Benny to paste.

### What I did

In `skills/improve-skill/SKILL.md`: the intro sentence, the tag bullet in step 4, the one-line summary of step 5, items 3 and 4, a new item 5, the PR body lead-in, the closing report sentence and the last tone note. Item 5 holds the yes path as four numbered sub-steps (fetch and version check, merge with a merge commit, tag the merge commit and push the tag, release and switch back) and the no path as one sentence. In `skills/git/SKILL.md` the last sentence of the push bullet now says the flow switches account only around its `gh` calls, and the worktree bullet no longer says every PR is squash-merged. In `skills/work-style-insight/SKILL.md` step 5 refers to the PR flow in `improve-skill` instead of giving a compare URL. The work is commit `16a182f`.

### Why

The tag has to sit on a commit that is on `main`, and the only moment that is knowable is after merge. Putting the question at the end of the skill is what ties the tag to the merge.

### What worked

Testing each read-only command before writing it down. Reading the version on `origin/main`, listing remote tags, looking up one tag by name (one line for an existing tag, empty output for a missing one) and reading the merge commit of an already merged PR with `gh pr view --json mergeCommit` all returned what the skill text says they return. The version on `origin/main` and the newest remote tag matched, so the error state the new check describes is not present today.

### What didn't work

`git show origin/main:.claude-plugin/plugin.json` failed in Git Bash:

```
fatal: ambiguous argument 'origin\main;.claude-plugin\plugin.json': unknown revision or path not in the working tree.
```

Git Bash rewrites the `rev:path` argument as if it were a path list. The same command works in PowerShell. The skill tells the reader to invoke git through bash, so I wrote the check as `git grep -h '"version"' origin/main -- .claude-plugin/plugin.json`, which has no colon and works in both shells, and kept the `git show` form as a PowerShell note.

A compound command (`cd ... && VAR=1 git ... | grep`) was refused by the worktree isolation, as the brief warned; plain separate commands went through.

### What I learned

A command copied from a brief is not tested until it has run in the shell the skill names. The brief's own example was the one that failed.

### What was tricky

Tagging "the merge commit on `main`" by checking out `main` and tagging `HEAD` is wrong if another PR merges in between. The skill therefore reads the merge commit hash back from the PR and tags that hash. The account stays switched from the merge to the release, so the switch back is written once, after the release, with "also when a step above failed".

### What warrants review

Read step 5 of `improve-skill` top to bottom as a cold reader. Not run, because they write: `gh auth switch`, `gh pr create`, `gh pr merge`, `git tag`, the tag push and `gh release create`. Their flags are from the tools' documented interface and have not been exercised here; the first real run of the skill is the test. The `-C` form of the read-only commands was tested without `-C` from inside the worktree. The squash sentence in the `git` skill was not named in the brief; I changed it because it stated squash as universal.

### Future work

`CLAUDE.md` line 47 still says the tag goes on the version-bump commit. It was left alone on instruction and needs Benny's own yes. The plugin version is not bumped on this branch.
