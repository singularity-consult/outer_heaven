---
name: second-opinion
description: Get an independent second opinion from Google Gemini on code, a diff, an architecture or a decision, so Claude's own blind spots do not pass unchallenged. Use this whenever the lead wants an outside review after builder self-review, when a design or technical decision is contested, when Benny asks to "get a second opinion", "ask Gemini", "have another model review this", "cross-check this", or "challenge this design". Covers how to package context (requirements plus raw material, never Claude's conclusions), the adversarial review prompt, how to weigh disagreement (Gemini is not an authority), the data rule (customer repos need Benny's explicit yes per run), Google's terms, cost, and how to run the stdlib-only `scripts/second_opinion.py`.
---

# second-opinion

A second model reviews the work cold. The value is independence: Gemini has different training and different blind spots than Claude, and it has not seen Claude's reasoning. Protect that independence, or the review only echoes what Claude already thinks.

This skill is the method. The `reviewer` agent is the role that uses it. `scripts/second_opinion.py` is the transport: a thin stdlib-only (urllib) client for the Gemini REST API.

## When to use

- **After builder self-review**, on a change that matters: new functionality, security or data handling, anything hard to reverse. The lead invokes the reviewer; the builder never calls it.
- **On a contested decision**: Benny and Claude disagree, or two designs are both plausible. Send the options and the requirements, not the preferred answer.
- **Not** for trivial changes (a typo, a version bump), and not as a replacement for running the tests. A second opinion is a review, not a validation.

## The data rule (check before every call)

Sending material to Gemini sends it to a third party.

- **Benny's own repos may be sent freely.** The script's allowlist: `outer_heaven`, `command-deck`, `datavilla`.
- **Everything else needs Benny's explicit yes, per run.** That includes customer repos (for example SEGES/DLBR, Grundfos, Air Greenland) and anything he does not own. A yes for one run is not a yes for the next.
- The guard in the script is **default-deny**. It matches on the MAIN repo folder name (a git worktree is resolved to its main repo by reading its `.git` file and `commondir`). Who owns the remote is deliberately NOT used: some customer work lives under Benny's GitHub organisation, and some repos have no remote at all.
- The guard checks `--source-repo` (default: the current directory) and every input file. Material outside any git repo is refused too, because its origin is unknown.
- On refusal the script exits with code 2, names the repo that triggered it, and makes no network call. Only after Benny's explicit yes for this run, rerun with `--customer-approved`. Never pass that flag on your own judgment, and never pass it to get past a refusal you did not expect: investigate the refusal first.
- Diff on stdin is attributed to `--source-repo`. Set it to the repo the diff came from, honestly.
- Never put secrets, credentials or personal data in the material. Trim them out first, whatever the repo.

## Packaging context

Send three things, and nothing else:

1. **Requirements**: what the work must do and the constraints it must respect. Use the original requirements, not a summary written after the fact to match the implementation.
2. **Raw material**: the diff, the relevant code files, or the design text. Trim to what matters: the changed files and the code they call, not the whole repo. Large inputs cost money and dilute attention.
3. **Optional focus**: a neutral question ("Is the retry logic correct under partial failure?"). Not a leading one ("Confirm the retry logic is correct").

Never send Claude's conclusion, self-review, chosen option or opinion. A reviewer that sees the answer tends to confirm it. For a contested decision, describe each option with equal care and let Gemini pick.

## The adversarial prompt

The script holds the default system prompt (`SYSTEM_PROMPT` in `scripts/second_opinion.py`). It tells Gemini to:

- act as an independent senior reviewer whose job is to find what is wrong, missing or risky, not to reassure;
- review the material against the requirements: unmet requirements, correctness bugs, edge cases, security and data handling, design choices that will hurt later, weak validation;
- tie every finding to a concrete location, say so when unsure, and not pad (an empty findings list is a valid answer);
- not guess the author's own conclusions.

The answer comes back as JSON, enforced with `responseMimeType: application/json` plus a `responseSchema` (verified against the live API on 2026-11-14; `--no-schema` drops the schema if it ever causes errors). Shape:

```json
{
  "verdict": "approve | approve_with_changes | request_changes | reject",
  "summary": "...",
  "findings": [
    {"severity": "critical | major | minor | nit", "location": "...", "issue": "...",
     "why_it_matters": "...", "suggested_fix": "...", "confidence": "high | medium | low"}
  ],
  "model_version": "..."
}
```

Change the prompt in the script, not per call, so every review uses the same bar.

## Weighing disagreement

Gemini is a second opinion, not an authority.

- **Verify every finding against the code before acting on it.** Read the location it names and check the claim. Gemini can be wrong, can misread a diff, and can report a confident finding about code that does not exist.
- Sort each finding into: confirmed (real, act on it), rejected (checked and wrong, with the reason), or unclear (needs a test or Benny's call).
- **Report disagreements to Benny with both sides**: what Gemini said, what Claude found when checking, and why. Do not resolve a disagreement silently in either direction: neither by dropping Gemini's finding because Claude disagrees, nor by adopting it because a second model said so.
- The reviewer returns findings to the lead. The lead decides what happens; the reviewer does not edit code.

## Terms (verified 2026-11-14)

Source: https://aistudio.google.com/docs/terms. Users in the EEA get the Paid-service data terms. Under those terms Google does not use prompts or responses to train its models. Google does log prompts and responses for a limited period, for abuse monitoring and legal reasons. So material sent here leaves Benny's control for that period. That is why the data rule exists.

## Cost

- The account runs on a prepaid balance.
- **Thinking tokens are billed.** A verified test: a 5-token prompt produced 75 thought tokens. On a real review the ratio is larger: the first live run (a 6,104-token prompt) used 21,254 thought tokens.
- The script prints usage on every call to stderr: `promptTokenCount`, `thoughtsTokenCount`, `candidatesTokenCount`, `totalTokenCount`, plus the resolved model version. Keep the material trimmed, and do not rerun a review just to "see if it changes its mind".

## Running the script

Key: `GEMINI_API_KEY`. The script reads it from the process environment and, on Windows, falls back to the user environment in the registry (`HKCU\Environment`), because a user variable set after a terminal started is not visible in that terminal. The key is sent only in the `x-goog-api-key` header. It never goes in the URL, output, logs or error messages, and it never goes in a repo or a diary.

Default model: `gemini-pro-latest` (on 2026-11-14 it resolved to `gemini-3.1-pro-preview`). Override with `--model`.

PowerShell, with files and a requirements file inside the owned repo:

```powershell
python skills/second-opinion/scripts/second_opinion.py `
  --requirements docs/requirements.md `
  --files src/loader.py src/normalize.py `
  --focus "Is the error handling correct?"
```

Bash, reviewing the branch diff from stdin with inline requirements:

```bash
git diff main | python skills/second-opinion/scripts/second_opinion.py \
  --diff - \
  --requirements-text "The loader must skip empty files."
```

Pipe diffs from Bash, not from Windows PowerShell 5.1: PowerShell 5.1 re-encodes text piped into a native command and can turn non-ASCII characters into `?`. The script reads stdin as UTF-8 bytes.

Options:

- `--requirements FILE` or `--requirements-text TEXT` (one is required). A requirements file must also pass the guard, so keep it inside the owned repo or pass the text inline.
- `--diff FILE` or `--diff -` (stdin), and/or `--files F1 F2 ...`.
- `--focus TEXT`: optional neutral question.
- `--source-repo PATH`: the repo the material comes from (default: current directory).
- `--customer-approved`: only after Benny's explicit yes for this run.
- `--model`, `--timeout` (default 300 s; thinking models can be slow), `--no-schema`.
- `--dry-run`: run the guard and print the exact request body, with no network call. Use it to check what would be sent.

Exit codes: `0` success (findings JSON on stdout), `1` error (missing key, HTTP error with status and Google's message, unreadable input, invalid answer), `2` refused by the data guard.

Tests: `python -m unittest discover -s skills/second-opinion/scripts -v` (no network).
