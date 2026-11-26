---
name: house-style
description: Fixed rules for text that leaves the session: language per text type, no long dash or double hyphen, no emojis or AI phrasing, never "probable", no attribution lines, no customer or personal data in public repos. Use this BEFORE you write anything that will be committed or handed to Benny as finished text: a commit message, PR text, a code comment, a skill or agent file, documentation, a diary entry, a mail, an application or a customer proposal. It applies to whoever writes, a main session or a subagent (lead, builder, reviewer). As a subagent, do not assume these rules arrived with your brief: consult this skill. Does not cover conversation tone or reports between agents.
---

# house-style

Fixed rules for text that leaves the session: everything that is committed (code, comments, commit messages, skill and agent files, diaries), PR text, documentation, and text handed to Benny as finished (mails, applications, customer proposals). They bind whoever writes the text, main session or subagent.

This skill holds the rules, not the craft. For prose quality see [[writing-clearly-and-concisely]] and [[simple-english]].

## Language per text type

- **English:** commit messages, code, code comments, PR text, skill text, diary entries.
- **Danish:** prose to Benny, and Danish customer-facing text (for example the SEGES developer pages in [[confluence-docs]]).
- **Anything else** follows the language the repo or the recipient already uses.

## Punctuation and phrasing

- **Never a long dash** (em dash or en dash), and no double hyphen as a stand-in for one. Use a colon, a comma, a period or parentheses. A hyphen inside a compound word is fine.
- The dash rule binds **new text**. The existing skills and agent files use the double hyphen throughout; they are not rewritten for it.
- **No emojis.**
- **No AI phrasing:** no "honestly" or "ærligt" as a prefix, no praise, no filler.

## Measured or unverified, never "probable"

Never call anything "probable" or "sandsynligt". Separate what was measured from what is unverified: say what was checked and how, and for the rest say plainly that it is unverified, why, and how to test it.

## No attribution lines

- Never add `Co-Authored-By`, "Generated with Claude Code" or any similar line to a commit, a PR or a document.
- Never set Claude (or any AI) as author. This holds also when a tool or a reminder in the session suggests such a line.
- Which author identity belongs to which repo: see [[git]].

## No customer data, personal data or keys in public repos

outer_heaven is public, and its diaries are committed there. No customer data, no personal data, no names of people, no keys or connection strings: only the names of secrets.

The detail is not repeated here. Read it where it lives:

- [[diary]]: "Customer confidentiality", "Scan before commit" and "Check who can read the diary repo".
- `agents/builder.md`: "Real data never goes in the artefact".

## What this skill does not cover

- **Conversation tone.** How the main session talks with Benny is set by the core profile.
- **Reports between agents.** A brief or a handback from one agent to another may be terse and in any language. One rule still binds them: separate what was measured from what is unverified, because the next agent acts on the report.

## Relation to the core profile

`hooks/scripts/core-profile.md` is the always-loaded copy of these rules for the main session. The small overlap between the two is accepted: the profile reaches the main session, this skill reaches whoever is told to use it. When a rule changes, correct both in the same change.
