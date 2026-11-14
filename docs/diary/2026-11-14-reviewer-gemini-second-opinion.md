# Diary: reviewer agent and second-opinion skill (Gemini second opinion)

Goal: add a "reviewer" link to outer_heaven that gets a second opinion from Google Gemini on code, architecture and decisions. Three layers: a role (`agents/reviewer.md`), a method (`skills/second-opinion/`), and a thin transport (a stdlib Python script in the skill that calls the Gemini REST API). No MCP server, no multi-provider abstraction.

## Step 1: Requirements and hand-off to the builder

**Author:** lead

### Prompt Context

**Verbatim prompt:** Benny wants a new link in outer_heaven (C:\claudes_folder\repos\outer_heaven): a "reviewer" that gets a second opinion from Google Gemini on code, architecture and decisions. Read agents/lead.md, agents/builder.md, .claude-plugin/plugin.json and a couple of existing skills (e.g. skills/pdf, skills/git) first to match conventions. (The prompt continued with four decisions already made with Benny, verified facts about the key and the terms, Benny's rules, and the acceptance criteria. They are restated as requirements below.)
**Interpretation:** The decisions are settled. My job is to turn them into concrete requirements, start this diary, and hand the build to one builder.
**Inferred intent:** Benny wants an independent, non-Claude check on Claude's work, so that Claude's own blind spots do not pass unchallenged, without leaking customer code to a third party.

### What I did

Read `agents/lead.md`, `agents/builder.md`, `CLAUDE.md`, `.claude-plugin/plugin.json` (version 0.18.1), `README.md` and `skills/pdf/SKILL.md`. Repo files are English, so the new files are English. Checked the worktree git identity: `benny@singularityconsult.dk`. Checked whether the key is reachable: the user-level environment variable `GEMINI_API_KEY` exists, but the current process environment does not have it (PowerShell: `process: False`, `user: True`). The session started before the variable was set.

Requirements handed to the builder:

1. `agents/reviewer.md`: the role. Invoked by the lead after builder self-review and on contested decisions. Sends Gemini the raw diff/code plus the requirements, never Claude's conclusions. Returns findings to the lead; the lead decides. The reviewer does not edit code.
2. `skills/second-opinion/SKILL.md`: the method. How to package context, the adversarial prompt, how to weigh disagreement, the data rule, the terms note (EEA paid-service terms: no training on prompts, but Google keeps prompts and responses for a limited period for abuse and legal reasons), and the cost note (thinking tokens are billed).
3. `skills/second-opinion/scripts/` Python script, stdlib only (urllib). Header `x-goog-api-key`, endpoint `v1beta/models/{model}:generateContent`, default model `gemini-pro-latest`. Prints token usage per call (prompt, thought, output, total) and the resolved model version. Structured findings (JSON). Key from `os.environ`, with a Windows fallback to the user environment in the registry (stdlib `winreg`), because of the process/user gap found above. The key never appears in output, logs, repo or diary.
4. Customer-repo guard in the script: refuse unless an explicit flag is given when the working directory or any input path is under a known customer repo.
5. `agents/lead.md`: add the reviewer step. `README.md`: entries for the agent and the skill. `plugin.json`: minor bump to 0.19.0.

### Why

The three-layer split keeps the method (what to send, how to read the answer) separate from the transport, so the prompt can change without touching HTTP code. Sending the raw material and not Claude's conclusion is the core of the design: a reviewer that sees the answer tends to confirm it.

### What worked

The conventions were easy to match: English repo files, one skill folder with `scripts/`, README lists kept alphabetical.

### What didn't work

Nothing failed in this step. One environment gap was found and turned into a requirement: `GEMINI_API_KEY` is set at user level but not visible in this session's process environment.

### What I learned

A Windows user environment variable set after a terminal starts is not inherited by that terminal or its children. Any tool that relies on it must either be started fresh or read the user environment directly.

### What was tricky

Deciding how to detect a "customer repo" without listing customer names in a public repo. That is left to the builder to resolve and is called out for review.

### What warrants review

The guard's detection rule, and whether it names customers in a public file.

### Future work

None yet.

## Step 2: Build the script, skill and agent, and run them live

**Author:** builder

### Prompt Context

**Verbatim prompt:** You are building in the lead's worktree: C:\claudes_folder\repos\outer_heaven\.claude\worktrees\agent-a34ab095ab1662f02 (outer_heaven, Benny's own public plugin repo). Use absolute paths. Current branch is `worktree-agent-a34ab095ab1662f02`; create and work on a new branch `feature/reviewer-gemini-second-opinion` from it. Commit there. Do NOT push, merge, tag or release. (The prompt continued with the goal, five numbered requirements, the acceptance checks, git rules, the diary instruction and the handback list. The requirements are summarised in Step 1.)
**Interpretation:** Build the three layers (agent, skill, stdlib script), the default-deny guard keyed on the main repo folder name, the lead/README/version edits, and prove it with one live call, a guard refusal and unit tests.
**Inferred intent:** A second-opinion link Benny can trust: it really calls Gemini, it cannot leak customer code by accident, and it does not leak the key.

### What I did

Wrote `skills/second-opinion/scripts/second_opinion.py` (stdlib only: `urllib`, `json`, `winreg`), `skills/second-opinion/scripts/test_second_opinion.py` (24 `unittest` tests), `skills/second-opinion/SKILL.md`, `agents/reviewer.md`, one paragraph in `agents/lead.md`, two README entries and the bump to 0.19.0 in `.claude-plugin/plugin.json`.

The guard resolves each path to its repo by walking up to a `.git` entry. A `.git` directory is a main repo. A `.git` file is read for `gitdir:`; if that gitdir has a `commondir` file (git writes `../..` there for linked worktrees) the main repo is the parent of the resolved common `.git`. Without `commondir` it falls back to the `<main>/.git/worktrees/<name>` path shape. No `git` subprocess. The allowlist is `outer_heaven`, `command-deck`, `datavilla`, case-insensitive. The guard runs on `--source-repo` and every input file, before the key is read and before any request is built.

Live run, reviewing the script's own diff (`git add -N` first so `git diff` shows the new file):

```
git diff -- skills/second-opinion/scripts/second_opinion.py | python skills/second-opinion/scripts/second_opinion.py --diff - --requirements-text "<requirements 3 and 4, paraphrased>" --focus "Correctness of the data guard and of key handling."
```

stderr, verbatim:

```
request: model=gemini-pro-latest prompt_chars=20363
model version: gemini-3.1-pro-preview
usage: promptTokenCount=6104 thoughtsTokenCount=21254 candidatesTokenCount=360 totalTokenCount=27718
```

Verdict `approve_with_changes`, one `minor` finding: `--requirements-text ""` is falsy, so `args.requirements_text or args.requirements.read_text(...)` calls `.read_text` on `None` and crashes with `AttributeError`. I read the line and confirmed it, fixed it with an explicit `is not None`, and added a test. The key was not in the process environment (`process: False user: True`), so the run also proved the `HKCU\Environment` fallback.

Guard refusal, with `HTTPS_PROXY=http://127.0.0.1:9` so any network attempt would have surfaced as a network error, and `--source-repo` pointing at a customer repo folder (path only, no files read):

```
data guard: REFUSED, nothing was sent. Material is not from an owned repo:
  - --source-repo <customer repo path> belongs to repo '<customer repo>' (...), which is not on the owned allowlist
Customer or unknown material needs Benny's explicit yes for this run; only then rerun with --customer-approved.
exit=2
```

The scratchpad (outside any repo) is refused the same way with "is not inside any git repo (unknown provenance)". This worktree resolves `...\worktrees\agent-a34ab095ab1662f02 -> C:\claudes_folder\repos\outer_heaven | name = outer_heaven | owned = True`. A unit test patches `urllib.request.urlopen` and `get_api_key` and asserts neither is called on refusal.

HTTP error path, checked with a model that does not exist (no tokens billed): `error: HTTP 404 from Gemini: NOT_FOUND models/no-such-model-xyz is not found for API version v1beta, or is not supported for generateContent. ...`, exit 1.

### Why

Default-deny by main-repo folder name is the rule the lead measured: remote owner does not tell owned from customer work. Resolving worktrees matters because agents work in worktrees whose folder names (`agent-...`) are never on any allowlist, so without it every agent run would be refused, and a crude name match on the worktree folder would be trivially wrong.

### What worked

`responseSchema` (uppercase OpenAPI-subset types, enums, `propertyOrdering`) together with `responseMimeType: application/json` was accepted by the live API on the first try and the answer parsed as JSON. `--no-schema` stays as a fallback but was not needed. Reviewing the tool with itself found a real bug.

### What didn't work

- First test run: `FileExistsError: [WinError 183] ... \outer_heaven` in `test_worktree_named_like_owned_but_main_is_not`, because `setUp` had already created a folder of that name. Moved the fake worktree under a `wts/` subfolder.
- `grep -rnP '[\x{2013}\x{2014}]'` failed in Git Bash with `grep: -P supports only unibyte and UTF-8 locales`; did the dash/emoji check with a short Python loop instead (no hits).
- A Python heredoc edit turned the `\` line continuations in the SKILL.md Bash example into nothing (the line came out joined). Fixed by inserting `chr(92)` explicitly.

### What I learned

The thinking cost dominates: 21,254 thought tokens against a 6,104-token prompt and a 360-token answer, about 3.5 times the input. Trimming material matters less than expected; the thinking budget is the lever.

On Windows, two encoding traps sit at the edges: a piped stdin is decoded with the locale codepage (a UTF-8 diff can fail or turn into mojibake), and printing `ensure_ascii=False` JSON to a cp1252 console can raise `UnicodeEncodeError`. The script reads `sys.stdin.buffer` as UTF-8 and reconfigures stdout/stderr to UTF-8.

### What was tricky

Files outside any repo. The requirement says unknown provenance is refused, which also refuses a requirements file written to a temp folder. I kept it strict and added `--requirements-text` so the normal flow (diff on stdin, requirements inline) needs no temp files. Stdin is attributed to `--source-repo`; the script cannot verify that, so the skill and agent tell the caller to set it honestly.

### What warrants review

- `find_repo` and `_main_repo_root_from_gitdir` in `second_opinion.py`: the guard's whole correctness rests on them. Submodules are treated as their own repo, named after their working tree folder.
- The guard is a name match: any repo whose main folder happens to be called `outer_heaven`, `command-deck` or `datavilla` passes. Accepted by design, but it is not an ownership proof.
- Branch name `feature/...` follows the lead's instruction; the `git` skill says own repos use a plain dash-sentence without prefix.

### Future work

- A `--thinking-level` option (Gemini 3 `thinkingConfig`) to cap thought tokens on small reviews. Not built: it would need another paid live call to verify the field name and values.
- The reviewer agent has not yet been exercised end to end by a lead; only the script was run live.
