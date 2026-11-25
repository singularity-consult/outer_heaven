# Diary: curate skill for knowledge files

Goal: add a user-invoked skill (working name `curate`) to the outer_heaven plugin. It reads a configured set of markdown roots, finds six kinds of problems, writes a dated report into the target, and changes nothing until Benny has approved the individual finding. It is the first of three planned skills for a private second-brain project and is meant to run on the existing knowledge files as they are today.

## Step 1: Requirements received, repo blocked by worktree isolation

**Author:** lead

### Prompt Context

**Verbatim prompt:**

> Benny has approved building the curation skill (working name `curate`) in the outer_heaven plugin, with the four recommended design choices below. Run your builder to implement it. Work on a new branch in `C:\claudes_folder\repos\outer_heaven` (own repo; branch name is a kebab dash-sentence without prefix, per the repo's convention). Commit on the branch is fine; do NOT push, do NOT merge to main, do NOT create a release or tag. Follow the `git` skill: identity `singularity-consult <benny@singularityconsult.dk>`, English commit messages, never Co-Authored-By or any Claude attribution. Stage only your own files explicitly.
>
> outer_heaven is a PUBLIC repo: the skill text and any examples in it must contain no customer names, no project knowledge, no content from command-deck or memory. Use generic placeholders in examples.
>
> ## Read first
> - `C:\claudes_folder\repos\outer_heaven\CLAUDE.md` and README (conventions, version bump rule, "Available skills" list), and the existing skills `improve-skill`, `work-style-insight`, `diary` for format and tone.
> - `C:\claudes_folder\repos\command-deck\second-brain\status.md` and `kilde-mlai-bootcamp3.md` for the project context and the reusable patterns. Read-only; do not edit command-deck.
>
> ## Approved requirements
> What it is: a user-invoked skill that reads a set of markdown roots, finds problems, and writes a dated report. It changes nothing until Benny has said yes to the individual finding. It does not fetch new knowledge, does not rewrite content, never touches customer repos, and never edits outer_heaven itself.
>
> - **Input:** a list of roots with an index file per root, plus an exclusion list. No paths in the skill; they live in a configuration file in the target (define its name, location and format, and document it in the skill). Must work unchanged on macOS later: no absolute Windows paths, no Windows-only commands.
> - **Never opened:** anything on the exclusion list. The skill must instruct that excluded files are not read, quoted or summarised, only counted as excluded.
> - **Six checks:** overlap, contradiction, staleness, promotion candidate (recurring fact that should become a general rule), index line over a fixed length limit, pointer without a target.
> - **Per finding:** verbatim quote with file and line, why, proposed action (delete, merge, promote, shorten, fix pointer), confidence 1-5. Only 4-5 are shown as proposals; the rest are counted.
> - **Secrets rule:** never reproduce passwords, keys, tokens or connection strings in the report; replace with a marker and report the location only.
> - **Report:** written in the target (path from config), never in outer_heaven. Ends with: done, skipped, needs attention.
> - **Approval:** one finding at a time. Approved changes in a git target become one commit with explicitly staged files (never `git commit -a`).
> - **State:** hash per file and the list of rejected findings, so they are not proposed again. Stored in the target.
> - **Relation to other skills:** improve-skill fixes skills from the conversation; work-style-insight describes Benny from diaries; this one reads knowledge files and fixes only those. A finding that points into outer_heaven is written as a hand-over to improve-skill, not fixed.
>
> ## The four approved design choices
> 1. Rule duplicated between knowledge files and the plugin's core profile: the skill proposes where the rule should live and removes only the duplicate in the knowledge files; the plugin side is handed to improve-skill.
> 2. Staleness by evidence, not age: flag only time-bound statements whose date has passed and statements that are contradicted elsewhere. Never flag on age alone. When the skill cannot know whether the awaited event happened, it asks.
> 3. Deletion in a target that is not under git: move to an archive folder instead of deleting.
> 4. First-version scope: all six checks on index files and small knowledge files; for long status files only the pointer check, and one project at a time on request.
>
> ## Validation before you hand back
> - Skill directory and SKILL.md frontmatter match the repo's existing skills.
> - Version bump and README "Available skills" entry done per the repo's CLAUDE.md.
> - Grep the new files for customer names and absolute paths; there must be none.
> - Do not run the skill against real targets; a dry read-through against the requirements list is enough.
>
> ## Report back (in Danish, no em dashes, no emojis, max 300 words)
> Branch name, commit hash(es), files changed, the configuration file format you defined, any requirement you could not meet or interpreted, and anything left unverified.

**Interpretation:** Requirements and design choices are already settled, so no refinement round with Benny is needed. The lead's job is to brief one builder, hold the public-repo boundary, and report back.

**Inferred intent:** Close the gap in the "only ever add to the knowledge files" pattern: something has to find the duplicates, contradictions and dead pointers, and it must do so without acting on its own.

### What I did

Read the repo's `CLAUDE.md`, `README.md` and `.claude-plugin/plugin.json` (version `0.20.0`), and the context files for the second-brain project. Tried to inspect the outer_heaven repo with git before creating the branch; every git command aimed at it was refused by the harness. Read `.git/HEAD` as a plain file instead: the checkout is on `main`. Then tried to write this diary into `docs/diary/`; that write was refused as well. Briefed one builder, and after the refused write redirected it to a staging folder inside the lead's own worktree that mirrors the repo layout. This diary file is staged there too.

### Why

One builder is enough: the deliverable is one SKILL.md plus a README line and a version bump, with nothing to parallelise. Staging in the worktree is what the refusal message itself points to, and it keeps the files in one durable place until a session with access can put them on a branch.

### What worked

Reading files in outer_heaven works from the isolated worktree, including `.git/HEAD`, which gave the current branch without a git command.

### What didn't work

The lead was launched in an isolated worktree that belongs to a different repo, and the harness confines both git and file writes to that worktree.

`cd /c/claudes_folder/repos/outer_heaven && git status --short` gave "this command changes directory to the shared checkout [...] before running git. Refusing to run it -- a worktree-isolated agent's git operations must target its own worktree."

`git -C /c/claudes_folder/repos/outer_heaven status --short` gave "this command redirects git to the shared checkout via -C. Refusing to run it".

A compound command mixing `git status` in the own worktree with `cat` and `ls` gave "this command names git in a form too complex to verify that it stays inside the worktree."

Writing `docs/diary/2026-11-25-curate-skill.md` in outer_heaven gave "This agent is isolated in the worktree [...]. Edit the worktree copy of this file instead of the shared-checkout path."

I did not look for a way around either block. The consequence: no branch, no commit, and no file in outer_heaven came out of this team. I also made a wrong call on the way: after the git refusals I assumed file writes would still work and briefed the builder on that assumption before testing it. The first write disproved it, and the builder had to be redirected mid-run.

### What I learned

A lead launched from a worktree of repo A can read repo B but can neither write to it nor run git in it. A task whose deliverable is a branch in another repo has to be launched with the worktree in that repo. And a block on one kind of access says nothing about the next kind; test the write before briefing anyone on it.

### What was tricky

The diary skill requires diaries to live in outer_heaven, and the lead role requires the diary to be started before the builder is kicked off. Neither could be honoured literally from here. The staged copy is the closest available form.

### What warrants review

The staged files have to be copied into the outer_heaven clone by a session that has access. Whether that clone's working tree is clean was not measurable from here; check `git status` there before branching. The staged `README.md` and `plugin.json` are full copies taken from `main` at version `0.20.0`; if `main` has moved since, apply the one-line changes by hand instead of overwriting.

### Future work

Create the branch, copy the staged files in, stage them explicitly, commit. Tag and release are out of scope for this task.

## Step 2: Skill staged and reviewed

**Author:** lead

### Prompt Context

**Verbatim prompt:** Same prompt as Step 1; no new prompt from Benny.
**Interpretation:** Finish the build in the staging folder and review it against the requirement list.
**Inferred intent:** Hand over something that can be committed without rework.

### What I did

The builder staged `skills/curate/SKILL.md` (182 lines), a `README.md` with the new `curate` line between `confluence-docs` and `diary`, and `.claude-plugin/plugin.json` at `0.21.0`. I read the staged skill in full against the requirements and the four design choices, and re-read the original `plugin.json` and `.git/HEAD`.

The builder defined the configuration as `curate.config.json` in the top directory of the knowledge base: JSON, with roots (path plus index file), exclusions, report directory, state file, archive directory, an index line limit of 200 characters and a long-file threshold of 150 lines (both raised to 400 in Step 3). Paths are relative to the config file or start with `~`.

### Why

A read-through is the only validation the task allows; the skill is not to be run against real targets.

### What worked

The builder's greps for absolute paths, repo and project names, and long dashes in the new text came back with zero hits, and its diff of the staged README and `plugin.json` against the originals showed one changed line each.

### What didn't work

The version moved under us. `plugin.json` read `0.20.0` when the lead first read it and `0.20.1` when the builder copied it a few minutes later; the lead's re-read afterwards confirmed `0.20.1` with the checkout still on `main`. Another session changed the repo while this one ran. The staged `0.21.0` is still the right minor bump from either value, but the staged README is a full copy and has not been compared with the original since.

### What I learned

A full-file copy of a shared file is only valid for the moment it was taken. In a repo that other sessions work in, hand over the one-line change, not the file.

### What was tricky

Several details were not in the requirements and were decided by the builder: a third answer "later" that defers a finding without rejecting it, one commit per repository when roots span more than one, a copy of the unedited file to the archive before the first line-removing edit outside git, and a promotion threshold of three places or two unrelated projects. They are reported to Benny as interpretations, not as approved.

### What warrants review

The two defaults (200 characters, 150 lines; now 400 and 400, see Step 3) and the interpretations above. The skill is 182 lines against 89 to 140 for the siblings the builder read. The quote-hash recipe for rejected findings has not been tried on either Windows or macOS, and triggering on `/curate` has not been tried.

### Future work

Apply the staged changes on a branch from a session with access, as one-line edits to `README.md` and `plugin.json` on top of whatever `main` holds then.

## Step 3: Two review rounds on the staged skill

**Author:** lead

### Prompt Context

**Verbatim prompt:** No prompt typed by Benny reached this agent. His feedback arrived as two messages relayed by the main session; the second opened: "Benny corrected one point on the staged curate skill: only the two size limits were too conservative."
**Interpretation:** Adjust the staged `SKILL.md` to match Benny's review, and record what happened.
**Inferred intent:** Loosen the two size limits, and leave the promotion logic strict.

### What I did

Round one, relayed by the main session: both defaults raised to 400 (`index_line_max_chars` and `long_file_min_lines`), the promotion threshold lowered to two places, and an explicit rule added that promotion to a general rule is always reviewed by a human, one at a time, never batched, with a sentence that automating that review is deliberately not built.

Round two: Benny corrected the main session. Only the two size limits had been too conservative; lowering the promotion threshold was a misreading on the main session's side. The threshold went back to three or more places, or two or more unrelated projects. The 400 and 400 limits, the human-review rule and the automation sentence stayed. One sentence was added to check 4 on how overlap and promotion relate: two occurrences are an overlap finding, three or more (or two unrelated projects) a promotion candidate, and the same text is never reported as both.

The builder made the edits in both rounds; the lead read the changed lines afterwards. After round two only line 77 of the staged skill differs from round one.

### Why

The limits decide how much the skill flags on a first run; too tight and the report drowns in index-line findings. The promotion threshold decides how many rule proposals Benny has to judge, and he wanted that left where it was.

### What worked

Resuming the same builder for both rounds: it still had the file and the requirements in context, and each round came back with line numbers, the new text and the same greps as the first delivery.

### What didn't work

The first round carried a change Benny had not asked for. It was built as relayed and had to be reversed in the next round. Nothing failed technically.

### What I learned

When the two thresholds were briefly equal, the builder pointed out that the same pair of passages could then qualify as both overlap and promotion with no rule for which one wins. That observation is what made the relation sentence necessary once the thresholds were apart again.

### What was tricky

The strict split leaves a hole: a project-specific fact repeated three times is not general, so it is no promotion candidate, and if overlap meant exactly two places it would be neither. The builder kept check 1 at "two or more places" and added a clause that a recurrence which does not qualify for promotion stays an overlap finding. That clause goes beyond the one sentence Benny asked for.

### What warrants review

Line 77 of the staged `SKILL.md`, in particular the clause after the semicolon at its end. If Benny wants the strict split without it, the clause is deleted and check 1 on line 74 changes to "in two places".

### Future work

None beyond Step 2: the files still have to be placed on a branch by a session with access.
