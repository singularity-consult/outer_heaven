# Diary: say where the diary goes when the work is in another repo

A second finding from the same architecture review, built on the same branch `fix-architecture-review-findings`. The lead agent, the builder agent and the `diary` skill disagree about where a diary lives when the work happens outside outer_heaven. Benny has approved the fix; this diary covers building it.

## Step 1: Pin down the contradiction and hand it to a builder

**Author:** lead

### Prompt Context

**Verbatim prompt:** (from the main agent, relaying a solution Benny approved; git and reporting instructions left out)

> Modsigelse (verificeret på origin/main):
> - `agents/lead.md` linje 9 og 17: alle commits og dagbogsindlæg bor i lead-agentens worktree; dagbogen startes "in the worktree".
> - `skills/diary/SKILL.md` linje 12 og 15: alle dagbøger bor i outer_heaven, aldrig i en kundes repo.
> - `agents/builder.md` linje 44: "writing into the same diary file the lead started". Linje 46 har allerede en korrekt regel for tilfældet uden lead (skriv ikke i det repo du arbejder i; aflever som tekst).
> - `skills/diary/SKILL.md` linje 101: "Commit together ... Include the diary file alongside the work it documents" kan ikke lade sig gøre, når dagbog og arbejde ligger i to repos.
>
> Besluttet løsning
> 1. `agents/lead.md`: dagbogen bor altid i outer_heaven-klonen. Kun når arbejdet selv foregår i outer_heaven, ligger dagbogsfilen i worktree'et. Arbejder lead i et andet repo (kunderepo eller andet), skrives dagbogen ALDRIG i det repo; lead (og builder) afleverer dagbogstrinnene som tekst i `diary`-skillens format i rapporten til hovedsessionen, som skriver og committer dem i outer_heaven. Grund der skal stå i teksten: en worktree-isoleret agent kan ikke køre git i outer_heaven-klonen. Følg samme mønster og ordvalg som den eksisterende regel i `agents/builder.md` linje 46, så de to ikke divergerer.
> 2. `agents/builder.md` linje 44: gør den konsistent med punkt 1 (samme fil som lead startede, når den findes i worktree'et; ellers aflevering som tekst). Undgå at duplikere linje 46; flet eller henvis.
> 3. `skills/diary/SKILL.md` linje 101: samme commit når dagbog og arbejde ligger i samme repo; ellers to commits i hver sit repo, hvor dagbogen henviser til arbejdets commit-hash (og repo). Dataværnet for det offentlige repo (ingen kundedata i dagbogen) bevares uændret.
> 4. Småting fra forrige runde, samme branch: indledningen i `skills/work-style-insight/SKILL.md` siger "reads every implementation diary"; ret den, så den er sand pr. kørsel (hele korpusset dækkes på tværs af kørsler).
>
> Hold ændringerne små; det er tekstrettelser, ikke en omskrivning.

**Interpretation:** Four small text corrections in three agent and skill files plus one sentence in `work-style-insight`. The solution is decided; nothing to refine with Benny.

**Inferred intent:** An agent working in a customer repo should not be able to read its instructions as permission to write a diary there, and the commit rule should describe something that can actually be done.

### What I did

Read `agents/lead.md`, `agents/builder.md` and the two relevant parts of `skills/diary/SKILL.md` in the worktree and confirmed the four quoted places at the stated lines. Grepped `agents/` for other mentions of diary and worktree. Started this diary as a new file, since it is a different topic from the reading-path change earlier today, and handed the requirements to a builder.

### Why

The lead text was written for the case where the feature is in outer_heaven, and there it is right: the worktree is a checkout of the diary repo. It becomes wrong the moment the worktree belongs to another repo, and that is exactly the case where a misplaced diary does harm.

### What worked

The builder file already has the correct rule for one variant of the case (no lead, isolated worktree of a customer repo). Reusing its wording for the lead keeps the two from drifting.

### What didn't work

Nothing failed in this step.

### What I learned

The lead's worktree isolation is the real reason for the handover-as-text rule: one of my own compound git commands was refused earlier today because the harness could not verify it stayed inside the worktree. An isolated agent cannot commit into a second repo even when it can see the files.

### What was tricky

`skills/diary/SKILL.md` also says to write into the working clone at its main path, not into a worktree of it. For work in outer_heaven the lead writes into the worktree, which is a checkout of the same repo. That sentence is not on the approved list, so the builder reports it rather than changing it.

### What warrants review

That the lead and builder rules now say the same thing in the same words, and that nothing in the customer-confidentiality section of the `diary` skill changed.

### Future work

Any remaining place that still says the diary lives in the worktree or the project repo is reported, not fixed, in the builder's step.

## Step 2: Make the three rules agree and correct the insight intro

**Author:** builder

### Prompt Context

**Verbatim prompt:** (from the lead; the restated contradiction, the grep, diary, git and reporting instructions are left out)

> The product owner (Benny) has approved the solution below. Build exactly that. These are text corrections, not a rewrite: change as few sentences as possible and keep each file's voice.
>
> 1. `agents/lead.md` (lines 9 and 17, and nowhere else unless needed for consistency):
>    - The diary always lives in the outer_heaven clone.
>    - Only when the work itself is in outer_heaven does the diary file sit in the worktree (the worktree is then a checkout of the diary repo).
>    - When the lead works in any other repo (a customer repo or anything else), the diary is NEVER written into that repo. The lead, and its builders, hand the diary steps over as text in the `diary` skill's format in the report to the main session, which writes and commits them in outer_heaven.
>    - The reason must be in the text: a worktree-isolated agent cannot run git in the outer_heaven clone.
>    - Follow the pattern and wording of the existing rule in `agents/builder.md` line 46 [...] so the two do not diverge.
>
> 2. `agents/builder.md` line 44: make it consistent with 1. Same file the lead started when that file exists in the worktree; otherwise hand over as text. Do not duplicate line 46: merge the two paragraphs or have one refer to the other. Do not weaken line 46's content.
>
> 3. `skills/diary/SKILL.md` line 101 (working loop, item 3): one commit when diary and work are in the same repo; otherwise two commits, one in each repo, and the diary entry refers to the work's commit hash and repo. [...] The sections "Customer confidentiality", "Scan before commit" and "Check who can read the diary repo" must stay byte-identical [...]
>
> 4. `skills/work-style-insight/SKILL.md`, intro paragraph (line 8): it says the skill "reads every implementation diary in `docs/diary/`". Make it true per run: one run reads what the previous insight file does not cover; the whole corpus is covered across runs. One sentence's worth of change.

**Interpretation:** Four sentence-level corrections in four files, committed as two work commits plus this diary.

**Inferred intent:** One rule, stated the same way in all three places, so no agent can read its instructions as leave to put a diary in a repo that is not outer_heaven.

### What I did

In `agents/lead.md` I took "and diary entries" out of the sentence about the shared worktree and added one sentence saying the diary always lives in the outer_heaven clone and sits in the worktree only when the work is in outer_heaven. I removed "in the worktree" from the sentence that starts the diary and added one paragraph right after it with the handover-as-text rule, in the words of the builder's existing rule. In `agents/builder.md` the "same diary file the lead started" clause became a conditional sentence, and the opening of the following paragraph was widened from "no lead" to "no diary file in the worktree", with the reason added; the instruction sentences of that paragraph are unchanged. In `skills/diary/SKILL.md` only item 3 of the working loop changed. In `skills/work-style-insight/SKILL.md` only the "reads every implementation diary" clause changed. The work is in commits `24bc457` (the diary-location rule) and `ad46158` (the insight intro) on `fix-architecture-review-findings` in outer_heaven.

### Why

The lead text was only true for work in outer_heaven. Putting the condition and the reason next to each other is what lets an agent in another repo see that the rule applies to it.

### What worked

`git diff --cached` showed exactly one hunk in `skills/diary/SKILL.md`, at item 3 of the working loop, which is the proof that the three protected sections are untouched.

### What didn't work

Nothing failed. The `git` skill is not in the list of skills the session can invoke, so I read `skills/git/SKILL.md` from the worktree instead.

### What I learned

The handover goes through two hands when there is a lead: builder to lead, lead to main. The lead text therefore has to say that the lead passes the builders' steps on in full, otherwise a step can be summarised away on the way.

### What was tricky

The lead file says "handback" and "main agent"; the requirement said "report" and "main session". I kept the builder rule's words and used "main session" once for who writes and commits. Whether a commit hash from a customer repo may stand in a public diary: the confidentiality section lists identifiers of one person or one resource and does not name repos or commits, and it asks for the project to be named, so I read it as allowed. The scan's "long digit runs" pattern can still hit on a hash; that is a hit to judge, not a ban.

### What warrants review

Read the new lead paragraph next to the builder paragraph and check they give the same four instructions. Check that the item 3 heading "Commit together" still reads right now that the two-repo case is two commits. Not changed, only reported: the `diary` skill's sentence about writing into the working clone at its main path, and the builder's "committed to this repo" in the real-data section.

### Future work

The plugin version is not bumped, so installed copies do not get the new text until a bump. The two reported sentences are a decision for the product owner.
