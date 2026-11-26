# Diary: First work-style insight, a credential in an old diary, and the history rewrite

Benny ran the work-style-insight skill for the first time. Reading the whole diary corpus surfaced a production credential quoted in a June entry in this public repo. The rest of the session removed it from the file and from git history, and changed the diary skill so the same thing is caught earlier. The credential, its parts and the search pattern built from it are not repeated here. Old commit ids are left out on purpose, because the hosting service still serves the old commits by id.

## Step 1: Read 72 diaries and write the first insight file

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** "/outer_heaven:work-style-insight"
**Interpretation:** Read every diary in `docs/diary/`, find patterns that recur across sessions, and write a dated insight file with patterns and derived suggestions kept apart.
**Inferred intent:** A read on how he works that rests on the whole corpus, not on one session.

### What I did
Listed the corpus: 72 files, 1.6 MB, no earlier insight file. That does not fit in one context, so I split the files into six chronological slices of about 270 KB and gave each to a general-purpose agent with the same brief: read every file to the end, report observations about Benny and about recurring friction in six fixed categories, cite file and step for each, mark interpretation as interpretation, and reproduce no sensitive values. I gave the agents no hypothesis. I then wrote `docs/insights/2026-11-26-work-style.md` from the six reports.

### Why
The skill requires the full corpus. Delegating the reading kept the conclusions and left the file contents out of my context.

### What worked
All six agents opened their reports with the same caveat, unprompted: the "Verbatim prompt" field mostly holds a brief from a main or lead agent, not Benny's words. Six independent reads agreeing on that is the strongest finding of the run. Fixed categories and a required per-file one-liner made the six reports easy to merge.

### What didn't work
Nothing failed in the run. The method has a built-in weakness: I read one passage of one diary myself. Every other citation in the insight file is second-hand.

### What I learned
The corpus says less about Benny than its size suggests, because most of it is agents talking to agents. The patterns that hold are the ones backed by his few direct prompts and by acts the diaries attribute to him. The clearest recurring problem is on the assistant side: an unmeasured premise becomes a claim or code. It appears from June to this session.

### What was tricky
Keeping "what is true about Benny" apart from "what an agent wrote in his name". The insight file marks each pattern as direct or relayed where it matters.

### What warrants review
Spot-check citations in the insight file against the diaries. A step number can be wrong without the pattern being wrong. The single-citation hypotheses are listed in the Notes section of the file and should not be read as patterns.

### Future work
Eight of the ten suggestions in the insight file are not acted on. They concern briefs between agents, wording for offline-only proof, join-key checks, and a warning when the installed plugin is older than the working clone.

## Step 2: Remove the credential from the file and from history

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** "lav 2 og 3 nu. Klart at mine prompts skal adskilles tydeligt fra agent-prompts, så det er nememr eat tracke hvad der er mig og hvad der ikke er. commit og push de to filer", then "du må gerne køre ovenstående script på mine vegne", then "push gik igennem. [kunden] skifter [forbindelsesoplysninger] på prod systemet på mandag, så connection bliver obsolete"
**Interpretation:** Step 2 was "remove the value from the file", step 3 "rewrite git history and force-push". Also commit and push today's diary and the insight file.
**Inferred intent:** Close the exposure in the public repo the same day, and keep the two new files from sitting untracked.

### What I did
One of the reading agents reported the credential as a side finding. I read the line myself, confirmed that the commit was on the remote main branch and that the repository is public, and told Benny before doing anything else. On his go I wrote a four-rule `sed` script, tested it on a copy of the file, and applied it. Two commits went to main: the redaction, then the diary and the insight file.

For history I checked what would be touched first: the value entered in June, so the rewrite covered nearly all 100 commits, 7 local branches and 18 tags. `git filter-repo` is not installed, so I used `git filter-branch --tree-filter` with `--tag-name-filter cat` on `--branches --tags`, with `core.autocrlf=false` for the run. Afterwards I verified per ref that the only file differing between old and new was the one diary, that a pickaxe search over all rewritten refs returned nothing, and that commit count, authors and dates on main were unchanged. Benny ran the force-push. I then confirmed remote and local refs matched, deleted the backup refs and the temporary scripts.

### Why
Editing the file fixes the tip only. The old commits keep the value until history is rewritten, and the tags had to move with the branches or each release would keep pointing at the old history.

### What worked
Listing branches, tags and worktrees before the rewrite. It showed four agent worktrees on branches that would be rewritten. After the rewrite each of them had the old version of the file staged, exactly as expected, and a later `git add -A` in any of them would have committed the credential back in. I restored that one file from the new HEAD in each worktree. Verifying by per-ref tree diff, not by trusting the tool's "was rewritten" lines.

### What didn't work
The session's auto mode classifier denied the rewrite on the first attempt:

`Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Destructive or Unwanted Actions].`

I did not work around it. I did everything that did not depend on it, put the scripts in a stable folder and gave Benny the commands as short PowerShell lines. After he wrote that I could run it for him, `git filter-branch` went through. `git push --force-with-lease` and `git push --force` were denied again with the same message, also after his approval, so he ran the push himself.

### What I learned
- A force-push does not remove the old commits from the hosting service. Pull request refs keep them reachable, and the old commit was still served by id after the push. Only a purge by the service's support, or deleting and recreating the repo, removes them. Rotating the credential is the only step that closes the exposure. The rewrite is cleanup.
- In this harness, explicit user approval is enough for a local history rewrite and not enough for a force-push. Plan for the user to run the push.
- A history rewrite leaves every other worktree with the pre-rewrite file staged. Check and restore them before anyone commits there.

### What was tricky
Redacting the description of a redaction. The original sentence held the value, a table row with two more identifying fields, and two search patterns that contained the value's prefix. A blanket replace of the value would have left the row and mangled the patterns, so the script rewrites the three passages as prose first and uses the blanket replace only as a fallback.

### What warrants review
Whether the credential is still valid. Benny reported that the customer replaces the connection details of the production system on Monday. That retires the connection string. It does not retire the password if the same user and password move to the new system or are reused elsewhere. I do not know either, and said so. Two other June diaries were reported by a reading agent to contain internal network detail and secret names. I have not read them and they are unchanged.

### Future work
Ask the customer about the password. Ask the hosting service to purge unreachable commits, or recreate the repo. Review the two other June diaries. The installed plugin's own clone of this repo may fail to update after the rewrite; that is untested.

## Step 3: Change the diary skill and release it

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** "Klart at mine prompts skal adskilles tydeligt fra agent-prompts, så det er nememr eat tracke hvad der er mig og hvad der ikke er.", then "ja" to "Skal jeg lægge kodeord, forbindelsesstrenge og tokens ind i scan-listen på samme gren?", then "merge og release for mig"
**Interpretation:** Act on the first suggestion from the insight file, extend the pre-commit scan to secrets, then merge and publish.
**Inferred intent:** Make the next corpus read able to tell him apart from the agents, and make the leak class from step 2 something the skill checks for.

### What I did
On a branch off main I added a `Speaker` line and a `Benny's own words` field to the Prompt Context template in `skills/diary/SKILL.md`, a writing rule that explains both, and a rule that an agent writing a brief must quote his sentence verbatim. A second commit added secrets and internal network detail to the scan list, with the rule that a diary never quotes a secret or a pattern built from it. Version went to 0.20.2 and then 0.20.3, each tagged. I opened pull request 13, merged it with a merge commit and created the release.

### Why
Without the speaker line the work-style-insight skill attributes agent wording to Benny. Without the scan entry the one class of leak that has reached this repo stays unchecked.

### What worked
Using `gh auth token -u <account>` as `GH_TOKEN` for single commands. The pull request, merge and release ran as the repo owner's account without `gh auth switch`, so the active account, which another terminal of his depends on, did not change.

### What didn't work
The session ran plugin 0.18.1 while the working clone was at 0.20.1. The improve-skill text I was given said `gh` cannot reach this repo on this machine; that was stale and both accounts are stored. The diary entry I wrote earlier today followed the 0.18.1 diary skill, so it got neither the pre-commit scan nor the commit question that later versions require.

### What I learned
Read the skill in the working clone before editing it. The installed copy can be several versions behind, and the working clone already had a scan section that the installed text did not mention.

### What was tricky
The second commit came after the first tag was pushed. Moving a pushed tag needs a force-push, so I bumped the version again and left `v0.20.2` as a tag without a release.

### What warrants review
The new `Benny's own words` field is only as good as the briefs. Nothing in `agents/lead.md` tells the lead to quote him; the rule sits in the diary skill alone. This entry is the first written in the new format.

### Future work
Add the quoting rule to the lead agent. Update the installed plugin. Decide whether `v0.20.1` and `v0.20.2` should have releases or be deleted.
