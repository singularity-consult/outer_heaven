# Diary: Tailor a CV and an accompanying letter to a specific role, in .docx

Benny asked for his English CV to be tailored to a specific role description, then for an accompanying letter in the same visual style. The work was document engineering on an existing Word file: keep the layout, change the content, prove the result by rendering it. This diary is in a public repo, so the target organisation, the role details and the content of the documents are left out on purpose. Prompts are quoted verbatim except where square brackets mark a redaction.

## Step 1: Three first drafts of the CV

**Author:** main

### Prompt Context

**Verbatim prompt:** "tag denne fil: [sti til CV .docx] og tilpas den til dette stillingsforslag:[URL] Du skal fokusere på min dybe forretningsforståelse og store Kimball erfaring, lakehouse erfraring, samt de andre krav i stillingen som jeg opfylder. Giv mig tre udkast, som jeg kan vælge i mellem."
**Interpretation:** Read the role description, read the CV, and produce three differently angled versions of the same CV as separate files, leaving the original untouched.
**Inferred intent:** He wanted to choose a direction by comparing finished documents, not by discussing outlines.

### What I did
Read the role description through the Edge browser tools. Copied the original .docx to the scratchpad and wrote one Python script (python-docx plus lxml) that opens the original, rewrites the profile, a match section, the competency tables and selected experience bullets, and saves three variants next to the original. Rendered each variant to PDF through Word COM automation from PowerShell and read the PDFs to check layout and page count.

### Why
Editing the existing file keeps fonts, the header table, zebra shading and spacing exactly as he designed them. Generating a new document from scratch would have meant recreating the design and getting it slightly wrong.

### What worked
Treating existing paragraphs and table rows as templates: `copy.deepcopy` an element, replace the text of its first run, drop the remaining runs, insert it with `addnext`. A small marker convention (`**Lead: **rest`) gave bold lead-ins without hand-building run properties. Rendering through Word itself gave the true page count, which is the only number that matters for a CV.

### What didn't work
- WebFetch was denied in the session's permission mode, so the role description could not be fetched that way. The browser tools in Edge worked.
- The docx skill's helper scripts failed: `merge_runs.py` and `soffice.py` need `defusedxml`, which is not installed, and there is no LibreOffice or `pdftoppm` on the machine.
- The first Word COM export hung as a background task. Word was waiting on a dialog nobody could see. I stopped the task and killed only the Word process started with `/Automation -Embedding`, leaving Benny's own Word window alone. The retry set `DisplayAlerts = 0` and `AutomationSecurity = 3` and opened the file read-only with the four-argument `Documents.Open(path, $false, $true, $false)`. That worked every time after.

### What I learned
On this machine the reliable render path for .docx is Word COM, not LibreOffice. `SaveAs2(pdf, 17)` exports and `ComputeStatistics(2)` returns the page count. `pdftotext.exe` ships with Git for Windows under `C:\Program Files\Git\mingw64\bin\`, which is enough for text checks.

### What was tricky
Word splits visible text across several runs, so "replace this sentence" is never a string replace. Rewriting the first run and deleting the rest is simpler and safer than trying to merge runs.

### What warrants review
Whether the three variants really differ in angle or only in wording. I checked by reading the rendered PDFs side by side.

### Future work
The docx skill assumes LibreOffice. A note for Windows machines without it (use Word COM) would have saved the failed attempts.

## Step 2: Second round on the chosen draft

**Author:** main

### Prompt Context

**Verbatim prompt:** "2 arbejder vi videre med. into tekst er fin. Kan vi kigge på mine konkrete tidligere erfaringer og vinkle dem mere mod stillingen?" followed by "[rettelser pr. engagement: kilder og teknologier for seks tidligere opgaver] Tag også de tre amnglende opgaver med. Jeg har lukket dokumentet", then "[svar på seks nummererede afklaringsspørgsmål]" and "skift til expert i PySpark. Slutdato er fin."
**Interpretation:** Keep the introduction, rewrite the experience entries with the facts he supplied, add the engagements missing from the English CV, and apply two small corrections.
**Inferred intent:** The experience section had to carry the argument with concrete, true detail, and only he had the facts.

### What I did
Wrote a second script with helpers for replacing bullet groups, rebuilding the shaded tables and inserting whole new experience entries cloned from an existing one. Took dates and details for the older engagements from an older Danish PDF version of the CV and from the project status files in command-deck. Asked six numbered questions where the sources disagreed or were silent, and applied his answers. Added a pass that replaces long dashes, and `w:keepNext` on headings and table rows.

### Why
Facts about his own career cannot be inferred. Every claim in the document had to trace to something he wrote or confirmed.

### What worked
Asking the six questions in one numbered list got six short answers back in one message. Cloning a complete experience entry as a unit kept the spacing of new entries identical to the old ones.

### What didn't work
- I attributed a modelling technique to one former employer because the old CV listed it there. The old entry turned out to be a copy-paste of another engagement's bullets. I had flagged it as a question, he confirmed it was wrong, and it was removed. Without the question it would have gone out as a false claim.
- The document overflowed to five pages twice. I cut words in the match section and shortened bullets, and reported what was cut, instead of shrinking type or margins.
- A heading was orphaned at the bottom of a page and a table split across pages until `keepNext` was added.

### What I learned
An old CV is not a reliable source about its owner. Entries get copied between jobs and never corrected. Treat it as a lead and confirm each reused fact.

### What was tricky
One date was written in a form that could be read as a single day or as a month range. I stated my reading in the reply and he did not contradict it. That is weaker than a confirmation and the status file says so.

### What warrants review
The added engagements: dates, and that each technology named is one he actually used there.

### Future work
None fell out of this step.

## Step 3: Three accompanying letters

**Author:** main

### Prompt Context

**Verbatim prompt:** "godt, den er accepteret. Giv mig 3 versioner af et cover letter jeg kan sende med stillingen. Læs om [organisationen] her: [URL] [redigeret: ønsket argumentationsvinkel og praktiske oplysninger om fremmøde]"
**Interpretation:** Research the organisation from its own site, then write three one-page letters with different structure, sharing one practical paragraph with the facts he dictated.
**Inferred intent:** Same as step 1: choose by comparing finished documents.

### What I did
Read the organisation's site through the browser tools. Wrote a third script that reuses the CV file as a letterhead: keep the header table, name and title line, remove the body elements between them and the section properties, then add paragraphs from two cloned templates (body and bullet). Built a structured letter, a short one and a narrative one. Rendered, fixed spacing after bullet groups, confirmed one page each.

### Why
Reusing the CV as the template makes the two documents look like one set with no design work.

### What worked
Slicing the body element list (`b[4:-1]`) to strip content while keeping the header and `sectPr` was a five-line solution. Keeping the practical paragraph as one shared constant guaranteed the three letters said the same thing about the facts.

### What didn't work
`javascript_tool` returned `[BLOCKED: Cookie/query string data]` when I collected links from the site. Re-running it to return text only, without URLs, worked.

### What I learned
The browser tools block output that carries query strings. Ask for text content, not hrefs, when all that is needed is what the page says.

### What was tricky
One letter contains a claim about his tooling experience whose evidence is a course project. It is true, but thin. I told him which sentence it was so he can back it up if asked.

### What warrants review
Every claim about the organisation in the letters traces to its own site as read on 2026-11-26. Nothing about it came from memory. A question about its ownership came up afterwards; I answered from memory, marked it unverified, and he declined a lookup.

### Future work
None.

## Step 4: Saving status, and a reminder that never fired

**Author:** main

### Prompt Context

**Verbatim prompt:** "don. gem status" and later "hvorfor startede du ikke diary-skill? den burde blive aktiveret af "gem status"?" and "nej vi har lavet en reminder på at "gem status" skal resultere i et spørgmål om jeg vil bruge diary skill også"
**Interpretation:** Save the state of the work somewhere durable. Then: explain why the diary question was not asked.
**Inferred intent:** He expects "gem status" to behave the same in every session, including the follow-up question about a diary.

### What I did
Saved status to the local memory directory, not to command-deck, because the subject is personal and should not be in git. Updated it as he made decisions. When he asked about the diary skill, I first answered from the one-line skill description in my context and told him "gem status" was not a trigger. He corrected me. I then searched the working clone and found the prompt hook in `hooks/scripts/user-prompt-submit.sh` and the trigger in `skills/diary/SKILL.md`.

### Why
The claim "there is no such trigger" was checkable with one grep, and I made it without checking.

### What worked
The grep settled it in one call and also showed the cause: the session start banner said `outer_heaven v0.18.1`, and the hook shipped in 0.19.0. The session was running an installed plugin older than the working clone, so the hook did not exist in it.

### What didn't work
My first answer. I reasoned from the skill listing, which only shows the short description, and presented the conclusion as fact. The skill body in the working clone says otherwise. This breaks the standing rule to verify before concluding.

### What I learned
The skill listing in context reflects the installed plugin version, not the working clone, and shows descriptions only. When Benny says a behaviour exists in outer_heaven, check the working clone and compare its version to the session banner before disagreeing. A version gap between banner and clone explains "the hook did not fire" without any bug in the hook.

### What was tricky
The diary skill loaded for this entry came from the 0.18.1 cache, so even this skill text is the old one.

### What warrants review
Why the installed plugin is at 0.18.1 while the clone has 0.19.0. I did not look, because the plugin cache is outside the folder I read freely. Until it is updated, "gem status" will not trigger the diary question in any session.

### Future work
Update the installed plugin to the current version. Consider naming the "gem status" trigger in the diary skill's short description, so a session can see it without the hook.
