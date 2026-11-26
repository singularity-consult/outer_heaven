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
- Write into the git **working clone** (the one you commit and push from) or, when the work itself is in outer_heaven, a worktree of that clone, which is the same repo; never the installed plugin copy. On this machine the working clone is `C:\claudes_folder\repos\outer_heaven`; the path is environment-specific and recorded in memory (`project-outer-heaven`). On a machine where it differs, locate the working clone first, and if you cannot find it, ask rather than writing elsewhere.

## Customer confidentiality

Diaries about customer work stay at delivery level: name the project and describe what was built, what was decided, and what failed in the process. Keep customer-confidential detail out: data values, secrets, credentials, and proprietary business logic that is not yours to store. When in doubt, leave it out.

Names of people never appear, and that includes colleagues at the customer: write "a colleague", "a reviewer", "the product owner". The same goes for identifiers that point at one person or one resource: user logins, e-mail addresses, run and job ids, tenant and subscription ids, storage account names, and row counts from customer tables.

### Scan before commit

Reading the entry is not enough; a name in a quoted error or a pasted command is easy to miss. Before a diary file is committed, grep it and fix every hit:

- the names and logins of everyone who appeared in the session (colleagues, reviewers, PR authors);
- long digit runs (run ids, job ids, row counts) and GUIDs;
- resource names from the customer's cloud (storage accounts, workspaces, key vaults);
- e-mail addresses;
- secrets: passwords, connection strings, tokens, API keys and SAS URLs. Search for the words (`password`, `pwd`, `secret`, `token`, `key=`, `AccountKey`, `sig=`) and for every secret value that appeared in the session, including its recognisable prefix;
- internal network detail: IP addresses, and host and port pairs.

A diary may say that a secret leaked and how it was found. It never quotes the secret, a part of it, or the search pattern that was built from it. An entry about redacting a password once quoted that password in a public repo, and the history had to be rewritten.

Report the scan result (what was searched for, how many hits) when you hand the entry over, so Benny can see it was done.

## Check who can read the diary repo

**`outer_heaven` is a public repo.** Centralizing diaries there is right for the aggregation reasons above, but it means every diary is world-readable under Benny's company name. That is fine for skills, tooling, and customer work kept at delivery level. It is not automatically fine for projects about Benny himself.

Before writing a diary for a project that touches personal data -- private finances, health, family, anything he would not publish -- check what the diary would expose, not just whether it names the project. Institution names, account structures, and which systems he holds data in are a profile even when no values, credentials, or identifiers appear.

Do not assume the project repo is the less private of the two. It is often the opposite: a private project repo holding personal data, and a public diary repo. If the diary would expose more than Benny has already accepted publishing, say what it would expose and let him decide before writing it. His call, made with the specifics in front of him -- not a judgement to make silently in either direction.

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

**Speaker:** <`Benny` if he typed the prompt himself, `agent brief` if a main or lead agent wrote it for you>
**Verbatim prompt:** <the exact prompt that initiated this step>
**Benny's own words:** <only when the speaker is `agent brief`: the passages in the brief that quote Benny word for word, or "none quoted in the brief">
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
3. **Commit with the work, when asked.** When the diary and the work are in the same repo, include the diary file alongside the work it documents in one commit. When they are in different repos, that is two commits, one in each repo, and the diary entry refers to the work by the project name at delivery level plus the commit hash, not by the repo name: outer_heaven is public, and a customer repo's name is customer data. For work in Benny's own repos the repo name may be given. Invoking this skill is not itself a commit request: wait for the user to ask before running `git commit`.
4. **Ask about the commit; do not leave it hanging.** When the entry is written, end with one question: commit and push it now? An entry nobody asks about stays untracked, and untracked entries do not travel across machines or reach `work-style-insight`. Entries have piled up uncommitted for months this way. If earlier entries are still untracked in `docs/diary/`, say how many, but commit only the ones Benny names: older entries may not have been scanned yet.

A "step" is a logical chunk of work, not necessarily a single commit (for example "wire up the hook", "debug the flaky test").

## Writing rules

- **Prose-first.** A narrative, not a log dump. Technical details (paths, hashes, errors) are included inline but wrapped in readable prose.
- **All sections, every step.** Never skip a section. If "What didn't work" is genuinely empty, say so explicitly.
- **Failures are gold.** Record them immediately with verbatim error messages and the exact commands that produced them. These are the most valuable parts of the diary.
- **Prompt Context is verbatim.** Copy the prompt exactly. Do not paraphrase that section.
- **Say who is speaking.** Every step has a `**Speaker:**` line. Write `Benny` only when he typed the prompt himself in the session you are in. If a main or lead agent wrote the prompt, write `agent brief`, even when the brief says "Benny har besluttet" or "Bennys direktiv": that is the other agent's wording of his decision, not his words. In that case fill `**Benny's own words:**` with the passages the brief quotes from him word for word, and write "none quoted in the brief" when there are none. Never move a relayed decision into his mouth. `work-style-insight` reads these lines to tell his preferences apart from an agent's phrasing, and most of the corpus could not be attributed because the line did not exist.
- **Quote Benny when you write a brief.** If you are the one handing work to another agent and the brief carries a decision of his, include his sentence verbatim and mark it `Benny:`. Your summary of it goes beside the quote, not in place of it. The agent that receives the brief has no other way to fill `**Benny's own words:**`.
- **Identify authorship.** Put an `**Author:**` line under each step heading: your sub-agent name if you are a named sub-agent, or `main` if you are the main agent.
- **Do not modify old diary entries.** Only edit a diary file created in the current session. Later work creates a new file. Diaries are a historical narrative, not a living document.

## When to activate

Activates proactively during non-trivial work: new features, bug fixes, refactors, research spikes, and at natural session-end moments while the narrative is still fresh.

Offer the entry yourself at these moments; do not wait to be asked. One line is enough ("Skal jeg skrive dagbog for dette?"):

- a PR from the session was merged;
- a release or deploy the session worked towards went out;
- an incident was diagnosed and closed (a red environment made green again);
- Benny writes "gem status" (the plugin's prompt hook also reminds you).

A session that started as a question can still earn an entry. A status check that turns into an incident, a fix, and a merge is non-trivial work even though nobody called it a feature.

Does not activate for one-line fixes, config tweaks, quick questions, or trivial changes that do not warrant narration.
