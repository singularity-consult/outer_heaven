---
date: 2026-11-26
diaries_read: 72 (2026-06-13 to 2026-11-26)
---

# Work-style insight: 2026-11-26

First insight file. No earlier file exists to refine.

Evidence is cited as `MM-DD slug`, which maps to `docs/diary/2026-MM-DD-<slug>...md`. "Direct" means Benny's own words or an act the diary attributes to him. "Relayed" means an agent brief reports his decision.

## Read this first: who is speaking in the diaries

In most diaries the "Verbatim prompt" field holds a brief from the main or lead agent to a sub-agent. It does not hold Benny's words. His decisions arrive as "Benny har besluttet", "Bennys direktiv", "Benny chose Option A". Direct prompts in volume exist in only a handful of files (06-13 bootstrap, 06-17 o90-raw-delete, 06-23 dlbr-shir, 08-03 enriched-serverless, 08-05 governance, 11-24 platformstatus, 11-26 tailored-cv). In 09-18 o90-cdc the deciding person is redacted to "[kunden]" and the text never says if that is Benny.

Every pattern below was checked against that limit. Where a pattern rests only on relayed text, it says so.

## Patterns about Benny

- **Decides from laid-out options, with very short answers.** Options with for and against, one decision at a time, answers of one to five words: "validation = C" (06-24 grundfos-local-pipeline), "billig!" (08-03 drift), "inline" (08-12 o90-integration-view), "YES" (08-03 enriched-serverless), "bekræft årsag" (11-24 platformstatus). Also 06-17 o90-raw-delete step 2, 06-26 grundfos-iir-company-id, 07-01 ingestion-framework, 08-29 guard-c, 09-03 null-watermark, 09-08 enriched-v2 steps 1 and 5, 09-17 kontraktdiff step 1. Counter-example: six numbered questions in one message got six short answers back and the diary records it as working (11-26 tailored-cv step 2).

- **Often answers with an option that was not offered, or adds conditions.** A fourth staleness model beside three offered (08-29 guard-c). "A variant of C, not B or C as asked" (09-08 step 5). Base layer dropped as a physical layer but kept as two code modules (07-01 ingestion-framework step 1). A two-way auto rule in place of the builder's proposed lever (06-22 grundfos-module3 step 2). One shared action group in place of one per environment (10-22 finops step 2). Two extra demands on top of the chosen option (09-17 step 1, direct). Counter-example: took the recommendation as given and added his own evidence (09-03).

- **Wants measurement before a decision and rejects inference.** "Never call anything likely" (06-22 db2-o90-shir). Coverage measured before the rule is set (06-17 grundfos-module1). Proof of concept as decision basis (06-19 address-poc). "Build the probe output first" (08-07 grundfos-v3 step 10, relayed). "byg ikke fixet endnu" until mechanism and delta are on the table (08-31 grundfos-adf-port step 6). "måles ... ikke sluttes" (09-18 step 4, "[kunden]"). "bekræft årsag" (11-24 step 4, direct). Counter-examples, where he knowingly accepts unverified work: unit tests only after the live proof window closed (11-24 step 4); declined a lookup on an answer marked unverified (11-26 step 3); shipped manually reviewed rows from a band measured at low precision (06-28 grundfos-ship-review).

- **Asks to be challenged and changes position when shown numbers.** "jeg kunne godt tønke mig at bruge min lead agent nu", after which two of his ideas were dropped (06-17 o90-raw-delete step 2, direct). Took the encrypted route after pushback on "it is a private repo" (06-15 trin-4-5 step 4). Accepted the challenge on a source and gave the real purpose (07-31 metamask step 1). Two starting premises overturned (08-03 drift step 1). Plan corrected twice by measurement (08-19 o90-delete step 1). The assistant corrected him on what a copy job covers (11-24 step 2). He also holds a decision against a recorded objection: branch placement (09-08 step 2), six pairs ruled as matches (08-07 step 12). In both cases the objection is written down beside the decision.

- **Supplies the meaning that code cannot give.** Matching grain is unique firm with location, never project id (06-23 firm-dedup). The new current-row flag is the correct one, so the finding's direction is reversed (09-17 step 3). "Spørgsmålet om akser er det forkerte spørgsmål", the document is a means to a list (09-22 konsumentaendringer). A dummy date must not appear in a time value (09-08 step 9, direct). "Has the file a consumer?" answered no, so the file is not written (08-31 step 3). Rejections freeze the pair, not the firm (08-07 step 12, direct).

- **Turns a single finding into a standing rule.** Key columns are never changed in enriched v2 (09-10 validering step 3). Learnings go into the rule view or the override table, never into a table's notebook (09-08 step 5). Never join or score on system keys (08-07 step 4, after the join bugs of 06-23 holdout and 06-24). Reviews are never revisited in production (08-07 step 11).

- **Reverses his own earlier decisions when the inputs change.** One combined output file on 06-24, split on 06-25, merged again on 06-28 after his manual review (grundfos-local-pipeline, grundfos-split-output, grundfos-ship-review). Append-only history replaced by full rebuild (06-17 to 06-24). Minimum-cost compute overturned with "det skal virke" after a quota measurement (08-02 enriched-remaining step 4). Multi-environment dropped: "Jeg er jo eneste bruger" (08-05 governance step 1, direct). A June rule on group units revised knowingly (08-07 step 10). A hard "do not change the shared loader" lifted by his own prompt (06-17 o90-raw-delete step 6). "Locked" in a brief binds the agent. It does not bind him.

- **Keeps raw faithful and pushes modelling downstream.** Append-only raw and source strings kept verbatim (07-01 step 3, 07-20 koinly step 1). Business split made later in curated (07-28 enablebanking). Enriched is not per-domain modelling (07-31 enriched-engine). Type conversion deferred to enriched (06-17 o90-raw-delete).

- **Does not touch what others depend on.** Existing enriched schema left alone because solutions use it (09-08 step 1). The framework folder stays identical to the owner team's version (08-12, 09-08 step 7). "DB2/Ø90-indlæsningen må IKKE påvirkes", proven before any change (11-13 o90-69573, relayed). "ÆNDRE INTET I MAIN" (06-23 dlbr-shir step 2, direct). Additive changes around live data (07-19 kraken-privat).

- **Prefers loud failure to a silent wrong value, and an honest weaker number to a polished one.** Empty folders skipped but logged (06-17 o90-raw-delete step 6, direct). Hard fail on auth errors, no zero-row loads (07-23 corpayone, 07-28). Unknown override names must fail or warn (08-29). No coalesce that hides a failed query (09-03). Volume not bought with precision (06-24 step 3). A weighted number reported as weighted (08-07 step 8). Mostly relayed.

- **Works in small gated steps and executes customer-side actions himself.** Lead refines, builder implements, main verifies, and he deploys, releases and runs against customer environments (06-23 dlbr-shir, 08-19, 09-08 steps 6 to 10, 09-23 adf-katalog, 10-08 guard-f, 10-26 dlbr-tmp, 11-13 o90-69573). One table at a time with his verification between (09-08 step 5). He is the human labeller (06-20, 06-23 holdout, 08-07 steps 6 to 12). Exceptions: inline fix after two stranded agent runs (08-12); status and operations work done inline by main, including a job start and a merge on his word (11-24); document work inline (11-26).

- **Parks decisions explicitly and expects parked points to stay parked.** "Noter det og remind mig om tre måneder" (08-05 step 1, direct). Two open points parked on purpose (08-12 step 2). A dismissed finding and eleven kept worktrees noted "så spørgsmålet ikke stilles igen" (11-24 steps 3 and 5). A closed question that must not be "undersøges, rettes eller nævnes igen" (09-18 step 5, "[kunden]").

- **Draws the privacy line at data, not at relationships, and makes that call himself.** Institution names may stay in the public repo, values and identifiers may not: "Den vurdering er Bennys, ikke min" (08-05 step 2). Customer names sanitised to roles in public diaries (08-07 step 3 onward, 08-31, 09-17 onward). No real values even as format examples (07-15 economic step 2).

## Recurring friction: what goes wrong on the assistant side

These recur across the whole period. They are the most useful findings in the corpus.

- **An unmeasured premise becomes a claim or code.** Three wrong root-cause hypotheses (06-22 db2-o90-shir). "Zero shared accounts (verified)" false on the live run (07-28). An assumed API field (07-31 metamask step 2). Views "created", concluded from a truncated log (08-12). Wrong layer and a miscalculated deadline (08-19). A scheduler setting prescribed without measurement (09-08 step 6). A regression that broke ten tables overnight, built on a reconstructed premise: "Det er tredje gang på en uge at en umålt præmis er blevet til kode" (09-18 steps 3 and 7). A measurement on the wrong column reported as an interim status (11-24 step 2). "There is no such trigger", answered without a grep (11-26 step 4).

- **Briefs carry wrong facts from agent to agent.** The builder corrects the brief in nearly every slice: row counts (07-15), schema and server name (07-01), decimal format (07-20), branch name and case (08-29), three points (08-24 grundfos-adf-port), three of nine counts (08-07 step 8), validation frame (09-10 step 1), spec values against the legacy database (06-19 o90-15). A fabricated calibration claim survived in a dead builder's docstring (08-07 step 4).

- **Green offline, broken live.** There is no local Spark, so runtime behaviour is unproven until Benny runs it. Three Spark-only bugs (07-15 steps 8 to 10). Cache call rejected on serverless, every source failed (08-02 step 5). "Tredje gang i denne opgave at noget deployer grønt uden at virke" (08-03 drift steps 3 to 5). Watermark precision bug pinned in place by a test that copied the implementation's output (09-08 step 7). 121 green tests before ten tables broke (09-18 step 3).

- **Joins on non-unique keys.** Three times in one week (06-20 validation-candidates, 06-23 holdout step 2, 06-24 step 4). In the second case the builder had seen a mismatched pair and explained it away as engine error.

- **Text that states something false.** Docstrings, comments, runbook numbers and commit subjects that disagree with the code (08-29 step 3, 08-31 step 2, 09-08 steps 6 to 10, 09-17 step 4, 09-23 step 3). The 08-29 diary names the mechanism: flagging a problem in a report feels like handling it.

- **Infrastructure friction in almost every diary.** Worktree isolation blocks cross-repo work, worktrees vanish overnight, agents die mid-task and leave half-built modules, and Windows shell quirks break heredocs and paths. Present in all six slices of the corpus, from 06-17 to 11-14.

- **Real data and secrets reach artefacts.** A real value used as a format example and missed by a scan that never probed amounts (07-15 step 2). A second incident cited in later briefs (07-20). Thirty real company names in a diary draft, caught before commit (08-07 step 3). A password exposed in session (06-28 db2-o90-connector). A diary entry that quotes a production credential while describing its redaction (06-15 trin-4-5 step 3). See Notes.

## Derived suggestions

- **diary skill: record who is speaking.** Add a `Source` line to Prompt Context with three values: Benny direct, Benny relayed, agent brief. Follows from the attribution limit above. Without it this skill cannot separate his preferences from the lead's wording, and most of the corpus is the lead's wording.

- **diary skill: scan for secrets by pattern before the file is saved.** Passwords, connection strings, tokens, IP and port pairs. A diary must describe a leak without quoting it. Follows from the 06-15 entry and the 07-15 scan that used the wrong probe set.

- **lead agent: mark every fact in a brief as measured or assumed, with its source.** The builder verifies the load-bearing ones before building and reports mismatches first. Follows from the wrong-brief pattern. Builders already do this unprompted; making it a required section removes the luck.

- **lead agent: ask for constraints before offering options.** He picks off the menu often enough that the option space is the weak point, not the recommendation. One line before the options: "what must this not break, and who consumes it". Follows from the off-menu pattern and from "has the file a consumer?" (08-31).

- **lead agent: date every "locked" decision and say who locked it.** A brief should not mark an earlier framing as critical unless Benny said so. Follows from the reversals pattern and from 06-24, where a carried-forward "append" turned out to be "an assumption, not a locked requirement".

- **builder agent: fixed wording for offline-only proof.** "Structure verified, values unverified" in place of "validated" or "green" when nothing ran on a cluster, plus a list of what only a live run can prove. Follows from green-offline-broken-live. The 08-03 drift diary already proposes the wording.

- **builder agent and python skill: assert key uniqueness before any enrichment join.** Follows from three join bugs in one week and from the rule he imposed afterwards.

- **builder agent: fix a false statement when it is found, then report it.** No "known latent inconsistency" notes. Follows from the false-text pattern and from the two corrections in 08-19 step 4 and 08-29 step 3.

- **agent launch convention: start the builder with the target repo as working directory, commit small and push early, poll without blocking.** Follows from the infrastructure friction. Each of these is already recorded as a local workaround in several diaries. None is written down in one place.

- **session-start hook: warn when the installed plugin version is older than the working clone.** Follows from 11-26 step 4 and 11-14 step 6, where a hook and an agent type were missing for that reason and the session reasoned from stale skill text.

## Notes

- **Method.** The corpus is 72 files and 1.6 MB. Six agents each read one chronological slice in full and reported observations with file and step references. This file is a synthesis of those six reports. I read only one passage of one diary myself. A citation here can be wrong in its step number without the pattern being wrong, and the reverse is not excluded.

- **Open credential in a public repo.** `docs/diary/2026-06-15-trin-4-5-learning-loop-and-command-deck.md`, step 3, "What didn't work", quotes a production database credential with port and user while describing how it was redacted elsewhere. I confirmed the line, that the commit is on `origin/main`, and that the repository is public. The value is not repeated here. The diary skill's rule against editing old entries does not cover this. Two more June diaries carry internal addresses, ports and secret names (06-19 o90-15, 06-22 db2-o90-shir).

- **Single-citation hypotheses.**
  - He settles a problem fastest when it is framed as a collision between two of his own requirements (09-08 steps 1 and 5 only).
  - Numbered batches of independent factual questions work as well as one question at a time (11-26 only). This sits against the standing one-question rule.
  - His attention is treated as the scarce resource (08-12, as the assistant's reasoning, never in his words).

- **Contradictions inside the corpus.**
  - "Do not redo verified work" and "verify this yourself, do not take my numbers on trust" both appear, sometimes in the same brief (08-12, 08-07 step 10). The working reading: no repeated analysis, but a cheap check of each load-bearing fact.
  - Manually reviewed rows went into the production file on 06-28 and were kept out of the reference table on 06-29. The diaries give no reason.
  - The diary skill says prompts are verbatim. The memory rule says customer detail never enters a public repo. Diaries from 08-07 onward resolve it by redacting. The skill text has not been changed to say so.

- **Gaps.** Nothing in the corpus records his preferences on reply length or tone in his own words. Those rules live in memory and in the session-start hook, and the diaries only show them enforced (long dashes removed in 07-23, 10-21, 11-13, 11-14). The decision trail for 09-18 cannot be attributed while "[kunden]" stays ambiguous.

- **Diary text quality.** 08-07 steps 11 and 12 contain mojibake. 07-15 step 2 reads as nonsense after a redaction that replaced a value with itself.
