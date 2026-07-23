# Diary: Build the ai-engineering skill from the Chip Huyen distillation

A new `ai-engineering` skill lands in outer_heaven: applied judgment for building
on top of foundation models. The raw material was Chip Huyen's *AI Engineering*,
distilled chapter by chapter via 10 parallel subagents into a study pack living in
a separate project folder (`C:\claudes_folder\projects\ai-engineer-learning`), not
in this repo. From those notes the skill was written as a decision spine — a
`SKILL.md` plus five reference files — that says what to *do*, not what the book
theorises. This entry covers finishing and integrating it.

## Step 1: Write the missing reference file and integrate the skill

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Opgave: Færdiggør en delvist bygget skill i outer_heaven
(`C:\claudes_folder\repos\outer_heaven`, Bennys eget repo) og send den som branch +
PR. En tidligere builder byggede det meste men døde af en API-fejl midt i.
COMMIT-identitet: `singularity-consult <benny@singularityconsult.dk>`, INGEN
Co-Authored-By. [...] HVAD DER MANGLER (din primære opgave): 1. Skriv den ene
manglende reference-fil `skills/ai-engineering/references/production.md`. SKILL.md
henviser til den (sektionen 'Running it in production'): den skal dække inference
optimization [...] OG production-arkitektur der vokser komponent for komponent [...]
OG user feedback loops [...]. Kilde-noter at destillere fra: [...] ch09.md
(Inference Optimization) og ch10.md (Architecture and User Feedback). Læs også de
eksisterende reference-filer [...] FØRST for at matche stil, længde og format
PRÆCIST [...]. Tjek at eventuelle krydsreferencer passer: prompting.md henviser til
at violation rate / false refusal rate 'recur at the architecture level; see
references/production.md'. [...] 2. Tilføj alfabetisk entry i README.md [...] 3.
Versionsbump [...] 0.15.0 -> 0.16.0. 4. Skriv en diary-entry [...] 5. Opret branch
`add-ai-engineering-skill` [...] commit, push, åbn PR mod main via gh. MERGE IKKE."

**Interpretation:** The four SKILL.md reference files and SKILL.md itself are done
and approved; do not touch them. Write only the fifth reference, `production.md`,
by distilling ch09 and ch10 of the study pack, matching the existing files' style
(English, tight, decision-oriented, ~40-77 lines, bold key terms, concrete
tradeoffs, em dash not double hyphen, no emojis, clean ending). Make sure it
actually delivers the guardrails metrics that `prompting.md` forward-references.
Then integrate: alphabetical README entry (ai-engineering sorts first), minor
version bump, a diary entry, and ship as a branch + PR without merging or tagging.

**Inferred intent:** Recover a build that a previous builder left one file short of
complete (it died mid-run on an API error after SKILL.md + four references), close
that gap in the same voice so the skill reads as one coherent piece, and land it as
a reviewable PR — not a merge — so Benny controls when it goes in.

### What I did

Read all five existing skill files first (`SKILL.md` and the four references:
`adaptation-ladder`, `evaluation`, `prompting`, `dataset-engineering`) to lock onto
the format before writing a word — the TOC-with-anchor-links pattern, the bold
**term** convention, the em dash (`—`, never `--`), and the "judgment not summary"
altitude. Then read the two source chapters (`ch09.md` inference optimization,
`ch10.md` architecture and user feedback) from the study pack.

Wrote `skills/ai-engineering/references/production.md` in three sections mirroring
SKILL.md's "Running it in production" pointer: inference cost/latency/throughput
(framed for an API consumer — prefill/decode, TTFT/TPOT, percentiles over means,
goodput, prompt caching, service- vs model-level optimisation), the architecture
that grows one component at a time (context, guardrails, router+gateway, caching,
agents, observability), and user feedback as the data moat (flywheel, the three
feedback kinds, user edits as free preference data, degenerate loops and
sycophancy). Deliberately made the guardrails item carry **violation rate** and
**false refusal rate** as system-level metrics, since `prompting.md` line 52
forward-references exactly that ("These same two metrics recur at the architecture
level; see `references/production.md`").

Integration: added `- **ai-engineering**: ...` as the first entry under README's
"Available skills" (it sorts before `caf-analytics`), matching the existing
`- **name**: description` shape; bumped `.claude-plugin/plugin.json` 0.15.0 →
0.16.0; wrote this diary. Then branch, stage, commit, push, PR.

### Why

The version bump is a minor because outer_heaven's CLAUDE.md is explicit that a new
skill is new functionality, and new functionality is a minor bump: 0.15.0 → 0.16.0.
Not a patch. The PR-not-merge and no-tag choices follow the brief: remote installs
are cached by version, and Benny controls when a release actually ships.
`production.md` was structured to satisfy two constraints at once — cover the three
required topics *and* honour the cross-reference already written into `prompting.md`
— so the skill has no dangling pointer once merged.

### What worked

The existing four references gave an unusually precise template, so matching voice
and structure was mechanical rather than guesswork. The forward-reference in
`prompting.md` also acted as a spec: it named the exact two metrics `production.md`
had to land, which removed ambiguity about what the guardrails section must contain.
Branch, commit under the correct identity, push, and `gh pr create` all ran green
first try.

### What didn't work

Nothing failed in this run. The write, the two edits, and the git/gh flow were all
clean on the first attempt, and `git status --short` showed only the expected files
with no `__pycache__` or `.pyc`. Recording that honestly rather than inventing
friction.

The failure worth carrying forward belongs to the *previous* attempt, not this one:
the first skill-builder wrote `SKILL.md` and four references, then died on an API
error partway through — before writing the fifth reference (`production.md`) and
before any repo integration. That is why SKILL.md already pointed at a
`references/production.md` that did not yet exist, and why `prompting.md` already
carried a cross-reference to it. This run wrote that fifth file and did the
integration the dead run never reached.

### What I learned

`production.md` came out at 38 lines against a ~40-77 target — slightly under, but
by design: the corpus prizes "stramt" (tight) prose, and the content is packed into
long dense bullets rather than padded out. Line count is a weak proxy here; the
judgment density matches the other references, which is what actually matters. The
three source topics (a whole chapter on inference, a whole chapter split between
architecture and feedback) compress hard because most of ch09's hardware detail
(kernels, PagedAttention, tensor parallelism internals) is irrelevant to an API
consumer and was deliberately dropped — the skill keeps only what changes a
decision.

### What was tricky

Two details needed care rather than reflex. First, the em dash: the brief said avoid
"dobbelt-tankestreg" (the `--` double hyphen), and the whole corpus uses the single
`—` character — so every dash in the new file is `—`, consistent with the siblings,
not `--`. Second, the README list is alphabetical and `ai-engineering` sorts to the
*top*, so it had to go before `caf-analytics`, not appended.

### What warrants review

Benny should confirm: (1) `production.md` reads at the right altitude and length —
it is the densest of the six files and sits just under the line target; (2) the
0.16.0 minor bump is right for one new skill (I argue it is, per CLAUDE.md); (3) the
README one-liner is a faithful summary he is happy to publish; and (4) that the PR
is meant to stay open for his review — this run did not merge and did not tag or cut
a GitHub release, per the brief. The `v0.16.0` tag and release remain a separate
deliberate act. Commit author is `singularity-consult <benny@singularityconsult.dk>`,
no Co-Authored-By.

### Future work

The skill cross-references itself well internally, but nothing exercises it — there
is no eval that the skill triggers on the intended prompts (the description leans on
"even when the request only says 'have the model do X'"). If Benny wants triggering
confidence, `skill-creator`'s eval flow could measure that without touching the
prose.
