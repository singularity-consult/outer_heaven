# Diary: one skill for the rules on text that leaves the session

Fourth piece of work on the branch `fix-architecture-review-findings`. The rules on language, punctuation, attribution lines and data in written output live in the always-loaded core profile, mixed with conversation rules, and it has not been shown that the profile reaches subagents. The lead and builder agent files name none of them. This diary covers moving those rules into a skill the agents are told to use.

## Step 1: Check the brief against the files and hand it to a builder

**Author:** lead

### Prompt Context

**Verbatim prompt:** (from the main agent, relaying Benny's reasoning; git and reporting instructions left out, the list of contents shortened to its headings)

> Regler om dansk, tone og forbudte udtryk gælder kun det output Benny ser, og tekst der forlader sessionen (dokumentation, commits, PR-tekst, dagbog, ansøgninger, mails, kundeoplæg). Det agenter sender til hinanden behøver ikke følge dem. Kerneprofilen (`hooks/scripts/core-profile.md`) blander i dag samtaleregler og regler for tekst der forlader sessionen, og det er ikke vist at profilen når subagenter. `agents/lead.md` og `agents/builder.md` nævner hverken `git`-skillen, Co-Authored-By eller lang tankestreg; reglerne er kun blevet overholdt fordi main skrev dem i hver brief.
>
> 1. Ny skill `skills/writing/SKILL.md` (foreslå et bedre navn hvis det kolliderer eller er for bredt): regler for tekst der forlader sessionen, uanset hvem der skriver. Kort. Indhold, hentet fra kerneprofilen og eksisterende skills, ikke opfundet.
> 2. `agents/lead.md` og `agents/builder.md`: én kort linje hver: brug `git`-skillen før første commit, og `writing`-skillen før du skriver noget der committes eller afleveres til Benny som færdig tekst.
> 3. `agents/reviewer.md`: tilføj reglen om aldrig at kalde noget "probable".
> 4. `hooks/scripts/core-profile.md`: FJERN INTET. Tilføj kun en pegepind til den nye skill under "Værktøjer".
> 5. `README.md`: tilføj skillen på listen, hvis README har en skill-liste.
> 6. `skills/git/SKILL.md` linje 55 fra forrige runde: "Most PRs are squash-merged" er en umålt påstand. Skriv den om til det kendte.

**Interpretation:** A new, short skill that collects existing rules and points at the skills that already hold the detail, plus one line in each agent file so the rules no longer depend on the main agent repeating them in every brief.

**Inferred intent:** Rules that protect what gets published should hold for whoever writes, without loading conversation rules onto messages between agents.

### What I did

Read `hooks/scripts/core-profile.md`, `agents/reviewer.md` and the skill list in `README.md`, listed the existing skills, and grepped skills, agents and hooks for where language and punctuation rules are stated today. Three things came out of that and went into the builder's brief:

1. The name `writing` sits too close to the existing skill `writing-clearly-and-concisely`, which is about prose quality. I chose `house-style` for the new one.
2. `agents/reviewer.md` already has the rule in its hand-back list: "Never call a finding "probably" right or wrong: check it, or say it is unchecked." The brief said it was missing. It covers findings only, so the builder widens it to the whole report instead of adding a second rule.
3. Several language rules in the brief have no written source in the repo today. The `git` skill says English for commits and code artifacts, and `confluence-docs` says Danish. Nothing states a language for diaries or skill text. The builder marks which rules are sourced and which are new with this change.

### Why

"Taken from the core profile and existing skills, not invented" is checkable, so I checked it before handing over rather than letting a new rule slip in looking like an old one.

### What worked

Reading the reviewer file before repeating the brief's claim about it.

### What didn't work

Nothing failed in this step.

### What I learned

The repo's own skills use a double hyphen throughout, while the core profile tells the assistant to avoid it. A rule for new text therefore cannot be applied backwards to the existing files without a large rewrite, and the skill has to say that it binds new text only.

### What was tricky

`hooks/scripts/core-profile.md` is injected into every main session. I treated a one-line pointer on an unpushed branch as a change to the product's source, which Benny reviews before merge, and not as a change to my own configuration. That is a judgement and it is flagged in the report.

### What warrants review

Whether a subagent actually loads the skill when its agent file tells it to. That cannot be settled by reading the text.

### Future work

If the first real lead and builder runs show the skill is not loaded, the rules have to go into the agent files after all.

## Step 2: Write the `house-style` skill and the pointers to it

**Author:** builder

### Prompt Context

**Verbatim prompt:** (from the lead; the reading list, git and reporting instructions left out, the content bullets of point 1 shortened to the opening sentence)

> You are the builder for one new skill and a few small text edits in the public repo outer_heaven.
>
> 1. NEW SKILL `skills/house-style/SKILL.md`. Rules for text that leaves the session, whoever writes it. SHORT: aim for well under 80 lines. Content must be TAKEN from the core profile and existing skills, not invented. Point at the other skills instead of repeating them.
> 2. `agents/lead.md` and `agents/builder.md`: ONE short line each: use `outer_heaven:git` before the first commit, and `outer_heaven:house-style` before writing anything that is committed or handed to Benny as finished text.
> 3. `agents/reviewer.md`: Widen it minimally so it covers everything in the reviewer's report (separate measured from unverified). Do not add a second, parallel rule.
> 4. `hooks/scripts/core-profile.md`: REMOVE NOTHING, change no existing line. Add exactly one pointer line to the new skill under "## Værktøjer".
> 5. `README.md`: add the skill to "Available skills", alphabetical.
> 6. `skills/git/SKILL.md` line 55: "Most PRs are squash-merged (...)" is an unmeasured claim. Rewrite to what is known.

**Interpretation:** Collect existing rules in one short skill, add pointers, and say for each rule whether it had a written source before.

**Inferred intent:** The rules should hold for a subagent without the main agent copying them into every brief.

### What I did

Wrote `skills/house-style/SKILL.md` (51 lines), added its entry to `README.md`, one pointer line under "Værktøjer" in `hooks/scripts/core-profile.md`, one line at the end of `agents/lead.md`, and reworked the skill sentence in `agents/builder.md` so `git` is named once, with its full name, next to the new skill. That is commit `28fc3d9`. Widened the existing sentence in the hand-back list of `agents/reviewer.md` to cover the whole report (`95ea318`). Rewrote the squash-merge sentence in `skills/git/SKILL.md` (`d9267b7`).

I read `skills/diary/SKILL.md` in the worktree for this entry and did not invoke the skill through the Skill tool.

### Why

Each rule in the skill was traced to a file before it was written down. Sourced: English for commits and code artifacts and Danish for prose (`git`), Danish for the customer's developer pages (`confluence-docs`), no long dash (`confluence-docs`, `writing-clearly-and-concisely`), no double hyphen, no emojis, no "ærligt" prefix, no praise and never "sandsynligt" (core profile), no Co-Authored-By and no Claude as author (`git`), no "Generated with Claude Code" (`improve-skill`, for PR bodies). Stated for the first time by this skill: English for PR text, skill text and diary entries, the fallback to the language of the repo or recipient, Danish for customer-facing text in general, "filler" as a named ban, and the sentence that the attribution rule holds when a tool or a reminder suggests such a line.

### What worked

The merge claim could be measured from the worktree: `git log --merges --oneline` shows "Merge pull request" commits for PR 1 to 11, so "outer_heaven merges PRs with a merge commit" describes the history so far.

### What didn't work

The first scan for long dashes failed on the locale:

```
grep -nP "\x{2014}|\x{2013}|--" skills/house-style/SKILL.md
grep: -P supports only unibyte and UTF-8 locales
```

It ran after `export LC_ALL=C.UTF-8`. Without the exit code the empty output would have read as a clean scan.

A late addition to the task asked for one more edit: the bullet in `skills/improve-skill/SKILL.md` that says project knowledge lives in memory should say command-deck. The session's permission classifier denied that edit, so it is not made and the bullet still reads as before.

### What I learned

The core profile bans the double hyphen and says nothing about the long dash. The long dash rule comes from `confluence-docs` and `writing-clearly-and-concisely`. The skill is the first place that states both together for all text.

### What was tricky

The sentence in `agents/builder.md` that lists skills contains a double hyphen in its first clause. I changed the end of the sentence and left the first clause alone, since the rule binds new text only. The skill itself describes the double hyphen in words so the file contains none outside the frontmatter delimiters.

### What warrants review

The rules listed above as new: they are in the brief, but no file stated them before. The frontmatter `description` of the new skill, since it decides whether an agent picks the skill. Whether `outer_heaven:house-style` resolves at all is untested: the plugin version is not bumped on this branch and the installed copy does not contain the skill.

### Future work

The minor version bump in `.claude-plugin/plugin.json` is deferred until the merge order with two other branches is known. The `improve-skill` bullet about memory still needs its correction.
