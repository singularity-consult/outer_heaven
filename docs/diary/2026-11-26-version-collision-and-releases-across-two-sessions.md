# Diary: version collision and releases while two sessions shared the repo

The main session shipped three releases of outer_heaven on one day (`v0.22.0`, `v0.23.0`, and the PR behind them) while a second session worked in the same repo. This entry covers what the build diaries from the same day do not: a version collision the main session caused itself, a history rewrite that landed under branches in progress, a review finding that a real run contradicted, and an edit the permission system refused. The build work itself is in the four other entries dated 2026-11-26 and the entry dated 2026-11-25 about `second-opinion`.

## Step 1: Release the `second-opinion` change and collide on the version

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** ja push og opret PR - derefter arkitekturfund ud fra leads forsdlag - et ad gangen
**Interpretation:** Push the branch `second-opinion-cost-and-review-modes` and open the PR. Do not merge yet. Then take the architecture findings one decision at a time.
**Inferred intent:** Get the finished work out for review without committing to a release, and keep each later decision small.

### What I did

I fetched, saw that `main` had one new commit and still carried `0.20.1`, pushed the branch and opened PR #12 with version `0.21.0`. A second session then rewrote the history of the repo (step 2) and merged PR #13, which moved `main` to `0.20.3` and gave PR #12 a conflict in `.claude-plugin/plugin.json`. Benny said yes to resolving it. I merged `origin/main` into the branch, kept `0.21.0`, ran the 81 tests and pushed.

Benny then said yes to merge, tag and release. I ran one chained command: fetch, print the version on `origin/main`, check that the tag `v0.21.0` did not exist, merge PR #12, read back the merge commit.

### Why

The version check before merge was the lesson from an earlier collision in the same session, when a hook commit took `0.19.0` under a branch that carried the same number.

### What worked

- `git merge-tree --write-tree origin/main <branch>` showed the conflict, and that it was the only one, before any merge was started.
- Reading the merge commit back with `gh pr view <n> --json mergeCommit` gave the exact commit to tag.

### What didn't work

The chained command printed this as its first line:

```
  "version": "0.21.0"
```

That was the version on `main` before my merge. The other session had merged PR #14 (the `curate` skill, also `0.21.0`) at 15:03:40 UTC. My command had no stop between the check and the merge, so it printed the warning and merged PR #12 at 15:04:46 UTC anyway. `main` then held two features under one version number, and installed copies are cached by version.

### What I learned

- A check that only prints is not a check. The value has to gate the next command: compare it, and exit when it is not the expected one.
- The window was one minute. Two sessions that both follow "check the version, then merge" still collide if either of them does it as one step.

### What was tricky

The tag `v0.21.0` did not exist after both merges, so the tag check passed. Only the version in `plugin.json` on `main` showed the collision, and that was the line I did not act on.

### What warrants review

- PR #15 changes only the version line, `0.21.0` to `0.22.0`. The tag `v0.22.0` sits on its merge commit `10443b4`.
- `main` carries version `0.21.0` at merge commit `20b7c45` with no tag. That number belongs to the other session's PR.

### Future work

- Tag `v0.21.0`, or decide that the number stays untagged.
- The version check in `improve-skill` catches a number that is taken. It does not catch two merges inside the same minute unless the check and the merge are separate steps with a stop between them. The skill text says so; no run has tested it.

## Step 2: A history rewrite under branches in progress

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** ja ret dette
**Interpretation:** Fix the contradiction between the lead prompt and the `diary` skill on the branch `fix-architecture-review-findings`. This step records what happened to that branch while the fixes were being built.
**Inferred intent:** Work through the review findings without stopping for each commit.

### What I did

The lead agent reported that every hash from its three earlier reports was gone. I checked the reflog of the branch and found `filter-branch: rewrite` at 14:41:28, between two builder runs. The second session had removed a quoted credential from a diary entry from June and force-pushed. I verified the result before doing anything else:

- every tag was still reachable from `origin/main`, and local and remote tags were equal;
- the local and remote tip of the PR #12 branch were the same commit;
- the content difference between the old and new tip of the fix branch was one line in one diary file.

I did not rebase. The fix branch was later merged with `origin/main` by a merge commit.

### Why

A rewrite that touches all refs can lose work or strand tags. Both had to be ruled out by measurement before the branch was pushed.

### What worked

The rewrite ran over all local branches and worktrees at once, so the branches in progress moved with `main`. Nothing had to be replayed by hand.

### What didn't work

Nothing failed. The cost was in the records: the diary entries written on the branch before 14:41 quote commit hashes that no longer exist, and so did my reports to Benny up to that point.

### What I learned

- Hashes in a diary are only as stable as the history. After a rewrite they point at nothing, and the entries are not corrected, because old entries are not modified.
- The lead agent first described the rewrite as something done "outside my work" without a cause. The cause was in the commit log of `main`: a commit that removes a quoted credential from a diary entry.

### What was tricky

`git rev-parse --short` with two arguments failed with `fatal: Needed a single revision` in the middle of a chained check, and the remaining output still looked complete. I reran the comparison as two separate calls.

### What warrants review

`git reflog show <branch> --date=iso` on any branch that existed on 2026-11-26 shows the rewrite entry.

### Future work

A session that rewrites history has no way to tell another session that it did. Benny is the only link between them.

## Step 3: A finding that a real run contradicted, and a refused edit

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** begge
**Interpretation:** Give `work-style-insight` both reading paths: subagents per batch, and a rolling window from the last insight file.
**Inferred intent:** Make the skill able to read a corpus that keeps growing.

### What I did

The architecture review had found that `work-style-insight` reads the whole diary corpus in one pass and cannot fit it in a context. I measured the corpus at 72 files and 1.54 MB and told Benny the skill had never delivered an insight file. The lead agent rewrote the skill on the fix branch.

While that work was under way, the second session ran the skill and committed `docs/insights/2026-11-26-work-style.md` to `main`, with `diaries_read: 72`. I told Benny that the finding had not held in practice and that I had not examined how that session read the corpus.

The new skill text looked for a field `read_at_commit` that the existing insight file did not have, so the next run would have read all 72 diaries again. The lead agent added a fallback: the commit that added the insight file. Measured against `main`, that left 1 diary to read.

Separately, Benny approved correcting three stale lines that said project status "stays in memory". The lead agent declined to edit `CLAUDE.md` on a relayed approval, so I made those two lines myself. The third line, in `skills/improve-skill/SKILL.md`, was refused for the builder by the permission system with the label "Undermining Oversight". I did not make that edit by another route and reported it to Benny.

### Why

A refusal from the permission system in a subagent is not something the main session should work around, even when the user has approved the content of the edit.

### What worked

Asking the lead agent to run the fallback command against the real repo and report the number turned a design claim into a measurement.

### What didn't work

- "The skill has never delivered an insight file" was true when I said it and false a few hours later.
- "The skill cannot read its own corpus" was a conclusion from file sizes, by the external reviewer and by me. Neither of us ran the skill.
- My table of which agent files carried the rule against "probable" said the reviewer file lacked it. It had the rule for findings. I had searched for one spelling.

### What I learned

- A finding about capacity should be tested by running the thing, when a run is cheap enough. This one was.
- Benny separated two kinds of rules that the core profile mixes: rules for the conversation he reads, and rules for text that leaves the session. Reports between agents need neither, except the rule that separates measured from unverified. That reasoning produced the `house-style` skill.

### What was tricky

The line the permission system refused is the mildest of the three: one sentence in a skill about where project knowledge lives. The two lines in `CLAUDE.md` went through in the main session. I do not know why the classifier treated them differently.

### What warrants review

- `skills/improve-skill/SKILL.md` still says project knowledge "lives in memory". It is the only stale occurrence left.
- `skills/work-style-insight/SKILL.md`, step 1a: the order of the fallbacks.

### Future work

- First real run of `work-style-insight` with the new text, of `improve-skill` with tag after merge, and of a lead or builder that is told to call `house-style`.
- The hardcoded Windows paths in the core profile, `diary` and `improve-skill` are still there. The external reviewer did not raise them.
