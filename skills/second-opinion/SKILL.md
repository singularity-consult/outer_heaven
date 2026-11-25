---
name: second-opinion
description: Get an independent second opinion from Google Gemini on code, a diff, an architecture, an app or solution proposal, a product proposal, a visual design (a Power BI report page, a website, an app screen) or a decision, so Claude's own blind spots do not pass unchallenged. Use this whenever the lead wants an outside review after builder self-review, when a design or technical decision is contested, when Benny asks to "get a second opinion", "ask Gemini", "have another model review this", "cross-check this", "challenge this design", "review this architecture", "assess this solution", "assess this product proposal", or "look at this report page / screenshot". Covers the review modes (code, architecture, solution, product, design) and how to choose one, how to package context (requirements plus raw material, never Claude's conclusions), the adversarial review prompts, how to weigh disagreement (Gemini is not an authority), the data rule (customer repos need Benny's explicit yes per run), the image rule (every image needs his explicit yes per run), Google's terms, the estimated cost per call in USD and DKK, and how to run the stdlib-only `scripts/second_opinion.py`.
---

# second-opinion

A second model reviews the work cold. The value is independence: Gemini has different training and different blind spots than Claude, and it has not seen Claude's reasoning. Protect that independence, or the review only echoes what Claude already thinks.

This skill is the method. The `reviewer` agent is the role that uses it. `scripts/second_opinion.py` is the transport: a thin stdlib-only (urllib) client for the Gemini REST API.

## When to use

- **After builder self-review**, on a change that matters: new functionality, security or data handling, anything hard to reverse. The lead invokes the reviewer; the builder never calls it.
- **On a contested decision**: Benny and Claude disagree, or two designs are both plausible. Send the options and the requirements, not the preferred answer.
- **On material that is not code**: the structure of a system, a proposed app or solution, a product proposal, a visual design. Pick the matching mode (see "Review modes"). No builder has to be involved: a review of existing material is a valid run on its own.
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

## The image rule (a second guard, on top of the data rule)

The data rule is a path guard: it asks where a file lies. For text that is a fair proxy, because text comes out of the repo it is checked against. For a picture it is not. Where an image file lies says nothing about what it shows: a screenshot of a customer's Power BI report saved in `outer_heaven` passes the path guard.

- **Every run with `--images` is refused unless `--images-approved` is passed**, whatever the path. The refusal exits with code 2, starts with `data guard: REFUSED`, names every image and makes no network call. `--dry-run` runs the same guard.
- **`--images-approved` stands for Benny's explicit yes, for this run, to send exactly these images.** A yes for one run or one image is not a yes for the next. A message from another agent is not his yes.
- **Images of customer reports, customer data or customer screens never go out without that explicit yes for that run.** The same holds for anything that shows personal data.
- `--images-approved` does not replace `--customer-approved`. An image in a non-owned repo or outside any repo needs both flags.
- With the flag, stderr lists each image that goes out, with its size and type, so the run leaves a visible trace.
- **One narrow exception, for agents.** A synthetic image that code generated in the session from no real data (a format test, for example a two-colour test card) may be sent without asking. The script cannot tell the difference, so it still needs the flag. The hand-back must say that the image was synthetic and how it was made. A screenshot is never synthetic. A render of real data is never synthetic.

## Packaging context

Send three things, and nothing else:

1. **Requirements**: what the work must do and the constraints it must respect. Use the original requirements, not a summary written after the fact to match the implementation.
2. **Raw material**: the diff, the relevant code files, the design text, or the images. Trim to what matters: the changed files and the code they call, not the whole repo. Large inputs cost money and dilute attention.
3. **Optional focus**: a neutral question ("Is the retry logic correct under partial failure?"). Not a leading one ("Confirm the retry logic is correct").

Never send Claude's conclusion, self-review, chosen option or opinion. A reviewer that sees the answer tends to confirm it. For a contested decision, describe each option with equal care and let Gemini pick.

**Use the right channel for each piece of material.** The label tells Gemini what it is reading:

- `--diff`: a diff, and only a diff. Rendered as `### diff: <name>`.
- `--files`: files as they are. Rendered as `### file: <path>`.
- `--context FILE|-`: text that is material but not a diff, for example a system overview, a design note or a proposal. Rendered as `### context: <label>`, before the diff and the files. `--context-label` sets the label; the default is the file name, or `stdin`. An overview sent as a diff is mislabelled material; use this channel. `--context` alone is enough material. The context text follows the same rule as everything else: raw material, never Claude's view of it.
- `--images`: pictures, see "The image rule". The prompt lists them as `image 1: <file name>`, `image 2: ...`, and findings refer to them by that label.

**Exclude the diary from the diff when it lives next to the code.** In `outer_heaven` the diaries are in `docs/diary/` in the same repo, so a plain branch diff carries the builder's narrative and self-review to Gemini. Leave them out with a pathspec: `git diff main -- . ':(exclude)docs/diary'`.

## Review modes

`--mode` picks the kind of review. Each mode has its own system prompt and, outside `code`, its own response schema. Choose by what the material is, not by what the repo holds:

| Mode | Use it for | It asks about (the dimensions) |
|---|---|---|
| `code` (default) | Code, a diff, a script, a config | Unmet requirements, bugs, edge cases, security and data handling, design choices, weak validation |
| `architecture` | How ONE system is structured | `layering`, `responsibilities`, `coupling`, `scalability`, `redundancy` (what is superfluous or duplicated), `gaps` (what is missing), `operability`, `requirements_fit` |
| `solution` | Whether a proposed app or solution meets a stated need end to end | `requirements_coverage`, `user_flow`, `data_model`, `integration`, `security_privacy`, `operation_and_cost`, `simpler_alternative`, `delivery_risk` |
| `product` | A product proposal | `target_user`, `problem`, `unsupported_assumptions`, `scope_boundary`, `value_and_differentiation`, `risks`, `success_measure` |
| `design` | A visual design: a report page, a website, an app screen. Needs `--images` to judge what the eye meets | `task_support`, `hierarchy`, `readability`, `consistency`, `accessibility` (contrast, colour as the only signal, text size), `data_presentation` (chart choice, labels, units) |

**Architecture or solution?** Architecture takes a system as given and judges its structure: are the layers, the split of responsibilities and the dependencies right. Solution takes a need as given and judges whether the proposal meets it: functions, data, integration, security, operation, cost, and whether something simpler would do. A review of how the agents, skills and hooks of a plugin fit together is architecture. A review of "we propose to build this app for that customer need" is solution. When both questions matter, they are two runs with two sets of requirements, not one.

**Choose the mode per call. Change a mode's prompt in the script, not per call**, so every review of that kind uses the same bar. `--focus` narrows a review; it does not replace the mode.

A non-code mode reviews at the level of the material. Line-level bugs in a single file are out of scope there unless they show a structural problem. That is the reason the modes exist: a structure sent to the code prompt comes back as procedural findings in single files.

### The code prompt

The script holds the code-mode system prompt (`SYSTEM_PROMPT` in `scripts/second_opinion.py`). Without `--mode`, the request body is byte-identical to what the script sent before modes existed; a test pins it. It tells Gemini to:

- act as an independent senior reviewer whose job is to find what is wrong, missing or risky, not to reassure;
- review the material against the requirements: unmet requirements, correctness bugs, edge cases, security and data handling, design choices that will hurt later, weak validation;
- tie every finding to a concrete location, say so when unsure, and not pad (an empty findings list is a valid answer);
- not guess the author's own conclusions.

### The other prompts

The prompts for `architecture`, `solution`, `product` and `design` are built in the script from one frame plus the mode's rubric (`MODE_DIMENSIONS`). They keep the adversarial stance and the honesty rules of the code prompt, and add:

- the dimensions of the mode, each with the question it asks;
- what `location` means in that mode (a component, layer, file or section; in design mode the image label and the screen region);
- `evidence` on every finding: a verbatim quote from the material, or the named element that shows the issue. It makes a finding checkable when there is no file and line;
- a `coverage` list with exactly one item per dimension: `problems_found`, `no_problems_found` or `not_assessable`, each with a `basis`. `not_assessable` is a valid and expected answer when the material does not show enough;
- the rule that the summary must not call anything sound unless the coverage item for that dimension says `no_problems_found` with a basis;
- the rule that a focus, when given, is answered in the summary, or the summary says the material does not let it be answered.

### What comes back

The answer is JSON, enforced with `responseMimeType: application/json` plus a `responseSchema` (`--no-schema` drops the schema if it ever causes errors). The output on stdout has two parts that must not be confused.

**Part 1: what Gemini writes, enforced by the `responseSchema`.** Code mode:

```json
{
  "verdict": "approve | approve_with_changes | request_changes | reject",
  "summary": "...",
  "findings": [
    {"severity": "critical | major | minor | nit", "location": "...", "issue": "...",
     "why_it_matters": "...", "suggested_fix": "...", "confidence": "high | medium | low"}
  ]
}
```

Architecture, solution, product and design mode (the enums hold that mode's dimension ids):

```json
{
  "coverage": [
    {"dimension": "<dimension id>",
     "assessment": "problems_found | no_problems_found | not_assessable", "basis": "..."}
  ],
  "findings": [
    {"severity": "critical | major | minor | nit", "category": "<dimension id>", "location": "...",
     "evidence": "...", "issue": "...", "why_it_matters": "...", "suggested_fix": "...",
     "confidence": "high | medium | low"}
  ],
  "summary": "...",
  "verdict": "approve | approve_with_changes | request_changes | reject"
}
```

In these modes the schema orders `coverage` and `findings` before `summary` and `verdict`, so the conclusion is written after the assessment it must rest on. Whether that ordering changes the quality of an answer is not measured.

**Part 2: what the script adds afterwards, from the API's metadata and its own arguments.** These keys are NOT in the `responseSchema` and Gemini never writes them:

```json
{
  "mode": "code | architecture | solution | product | design",
  "model_version": "...",
  "usage": {"promptTokenCount": 0, "thoughtsTokenCount": 0, "candidatesTokenCount": 0, "totalTokenCount": 0},
  "cost": {"usd": 0.0, "dkk": 0.0, "estimate": true, "model_version": "...", "prices_as_of": "...",
           "tier": "...", "usd_dkk_rate": 0.0, "usd_dkk_rate_source": "...",
           "cached_tokens_at_full_rate": false, "note": "..."}
}
```

The script is tolerant when it parses: a non-code answer with no `coverage` list gets an empty one instead of an error. An empty `coverage` list in a non-code answer therefore means Gemini did not deliver it, not that every dimension is fine.

### What is verified live, and what is not

- **Code mode**: the schema was verified against the live API on 2026-11-14 and has been used live since.
- **Design mode with one image**: one live call on 2026-11-25. HTTP 200 on `gemini-pro-latest` (resolved to `gemini-3.1-pro-preview`) with `--thinking-level low`, the extended schema, and one PNG sent as an `inlineData` part with base64 data. The answer held one coverage item for each of the six dimensions: one said `no_problems_found` and five said `not_assessable`. So the wire format for an image and the extended schema are accepted by the API. Usage on that call: 1,819 prompt tokens, 0 thought tokens, 321 answer tokens.
- **Not verified by that call: that the model reads the pixels.** The image was a synthetic test card with a red left half and a blue right half, and the answer named those colours on those sides. The requirement text named the same colours, so the answer does not tell a model that saw the image from one that repeated the requirement. A test that settles it uses an image that contradicts the requirement text.
- **Not run live when this was written**: the `architecture`, `solution` and `product` prompts, JPEG and WEBP images, more than one image, `--context`, and whether the two modes `architecture` and `solution` give usefully different answers on the same material.

## Weighing disagreement

Gemini is a second opinion, not an authority.

- **Verify every finding against the code before acting on it.** Read the location it names and check the claim. Gemini can be wrong, can misread a diff, and can report a confident finding about code that does not exist.
- Sort each finding into: confirmed (real, act on it), rejected (checked and wrong, with the reason), or unclear (needs a test or Benny's call).
- **Report disagreements to Benny with both sides**: what Gemini said, what Claude found when checking, and why. Do not resolve a disagreement silently in either direction: neither by dropping Gemini's finding because Claude disagrees, nor by adopting it because a second model said so.
- The reviewer returns findings to the lead. The lead decides what happens; the reviewer does not edit code.

## Terms (verified 2026-11-14)

Source: https://aistudio.google.com/docs/terms. Users in the EEA get the Paid-service data terms. Under those terms Google does not use prompts or responses to train its models. Google does log prompts and responses for a limited period, for abuse monitoring and legal reasons. So material sent here leaves Benny's control for that period. That is why the data rule exists.

## Cost

### The price per call

Every call prints one cost line on stderr after the usage line, and the same figures go in the `cost` object of the JSON:

```
cost (estimate): 0.2019 USD = 1.38 DKK | prices as of 2026-11-25 (table), tier <=200k | 1 USD = 6.8178 DKK (fixed, 2026-11-24)
```

Read it as an estimate, never as an invoice:

- **It comes from a price table in the script, dated `PRICES_AS_OF` (2026-11-25).** The table is keyed on the resolved model version in the API response (`modelVersion`), never on the alias given with `--model`, and it matches exactly: no prefix matching, no guessing. Prices are USD per 1 million tokens, paid tier, Standard, from https://aistudio.google.com/docs/pricing.
- **Provenance of the prices.** The pricing page was read through a summarising fetch tool on 2026-11-25. The `gemini-3.1-pro-preview` numbers came from verbatim text. The other rows were not seen verbatim. Check a row against the page before relying on it for a decision about money.
- **Thought tokens are priced at the output price** (the page names that row "Output price (including thinking tokens)"): `prompt x input price + (thoughts + answer) x output price`.
- **`gemini-3.1-pro-preview` has two tiers**, chosen by the prompt token count and applied to both input and output of that call: up to and including 200,000 prompt tokens, and above. The line names the tier.
- **`gemini-3.6-flash` and `gemini-3.8-flash` change price on 2027-01-01.** The row is picked by the date of the call, in UTC.
- **Cached tokens: the figure is an upper bound.** The cache discount is not modelled. When the API reports cached prompt tokens, all prompt tokens are still priced at the full input rate and the line says so.
- **DKK uses a fixed, dated rate**: 6.8178 DKK per USD, the rate of 2026-11-24 from api.frankfurter.dev. The script makes no network call for the rate. Override it with `--usd-dkk RATE`, or with the environment variable `SECOND_OPINION_USD_DKK` (the flag wins). The line then says the rate came from the flag or from the environment variable, with no date. A rate that is not a number above zero is a usage error (exit 2), not a silent fallback.
- **An unknown model version gets no number.** The usage line is printed as always, and the cost line says the price is unknown for that model version. In the JSON, `usd` and `dkk` are `null` and `reason` says why. This happens the day `gemini-pro-latest` moves to a model the table does not hold.
- **`--price-in USD --price-out USD`** (per 1 million tokens, both together, flat, no tier) price a model the table does not hold, or a price that has changed. They win over the table and the line says `override`. The lasting fix is a new row in `PRICE_TABLE` and a new `PRICES_AS_OF`.
- The estimate is not checked against Google's billing.
- Images are priced through the prompt token count the API reports, at the same input price as text. That Google bills image input at the text input price for every model in the table is not verified.
- When the API response holds no usage metadata, all counts are 0 and the line shows a cost of 0. Read the usage line next to the cost line.

### What drives it

- The account runs on a prepaid balance.
- **Thinking tokens are billed.** A verified test: a 5-token prompt produced 75 thought tokens. On a real review the ratio is larger: the first live run (a 6,104-token prompt) used 21,254 thought tokens.
- The script prints usage on every call to stderr: `promptTokenCount`, `thoughtsTokenCount`, `candidatesTokenCount`, `totalTokenCount`, plus the resolved model version and the cost line. Keep the material trimmed, and do not rerun a review just to "see if it changes its mind".
- A non-code mode makes the answer longer: the coverage list is one item per dimension on every run, and it is billed as output tokens.
- Images cost prompt tokens. Google's image guide (read 2026-11-25) gives 258 tokens for an image with both sides at or under 384 px, and 258 tokens per 768x768 tile for larger images.
- **`--thinking-level` is the lever on thought tokens.** It sends `generationConfig.thinkingConfig.thinkingLevel`, which Google describes as the maximum depth of the model's internal reasoning. Without the option nothing is sent and the model default applies (for `gemini-3.1-pro-preview` the documented default is high). The field name and its values are verified in Google's documentation on 2026-11-25 (API reference for `generateContent`: https://aistudio.google.com/api-reference/generate-content).
- **Live result (one call, 2026-11-25):** the API accepted `thinkingLevel` `LOW` on `gemini-pro-latest` (resolved to `gemini-3.1-pro-preview`) with HTTP 200, together with `responseSchema`. That call used 4,254 thought tokens on a 15,757-token prompt. This is not a controlled comparison with the 21,254 thought tokens above: the two runs reviewed different material, so the numbers do not measure how much the option saves.
- **Not tested live:** `minimal`, `medium`, `high` and `xhigh`. What the API does with a level a model does not support (an HTTP error or a silent fallback) is not verified either.
- A lower level buys fewer thought tokens with a shallower review. When the option is set, the `request:` line on stderr shows `thinking_level=<level>`, so the usage line can be read against it. Say in the hand-back which level a review ran with.

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
git diff main -- . ':(exclude)docs/diary' | python skills/second-opinion/scripts/second_opinion.py \
  --diff - \
  --requirements-text "The loader must skip empty files."
```

The `':(exclude)docs/diary'` pathspec keeps the diary out of the diff (see "Packaging context"). Drop it in a repo that holds no diary.

Pipe diffs from Bash, not from Windows PowerShell 5.1: PowerShell 5.1 re-encodes text piped into a native command and can turn non-ASCII characters into `?`. The script reads stdin as UTF-8 bytes.

When a pipe is not possible (some agent harnesses refuse a compound git command), do it in two plain commands in Bash: write the diff to a file, then feed that file to stdin and name the repo it came from.

```bash
git diff main -- . ':(exclude)docs/diary' > /path/outside/the/repo/review.diff
```

```bash
python skills/second-opinion/scripts/second_opinion.py \
  --diff - \
  --source-repo . \
  --requirements-text "The loader must skip empty files." \
  < /path/outside/the/repo/review.diff
```

`--diff FILE` does not work for such a file: every input file must pass the guard, and a file outside any git repo is refused as unknown provenance. On stdin the material is attributed to `--source-repo` instead, so set that to the repo the diff really came from. Writing the diff file inside the repo would pass the guard, but it leaves an untracked file to clean up.

Options:

- `--requirements FILE` or `--requirements-text TEXT` (one is required). A requirements file must also pass the guard, so keep it inside the owned repo or pass the text inline.
- `--mode {code,architecture,solution,product,design}`: the kind of review. Default `code`. See "Review modes".
- `--diff FILE` or `--diff -` (stdin), and/or `--files F1 F2 ...`, and/or `--context FILE` or `--context -` (stdin), and/or `--images F1 F2 ...`. At least one of them must hold material. `--diff -` and `--context -` together is a usage error: stdin can feed only one.
- `--context-label TEXT`: label of the context block. Default: the file name, or `stdin`.
- `--images F1 F2 ...`: PNG, JPEG or WEBP. The type is decided from the file's magic bytes, and the extension must agree with it; anything else is an error before any network call. Each image is sent as inline data after the text, in the order given. A request body over 20,000,000 bytes is refused before the network call, and the error names the size (Google's image guide gives 20 MB for the whole request with inline images).
- `--images-approved`: only after Benny's explicit yes to send exactly these images, for this run. See "The image rule".
- `--focus TEXT`: optional neutral question.
- `--source-repo PATH`: the repo the material comes from (default: current directory).
- `--customer-approved`: only after Benny's explicit yes for this run.
- `--model`, `--timeout` (default 300 s; thinking models can be slow), `--no-schema`.
- `--thinking-level {minimal,low,medium,high,xhigh}`: cap the reasoning depth, and with it the thought tokens. Default: not sent, so the model default applies. The script does not check the level against the model, because `gemini-pro-latest` moves between models. What the API does with a level the resolved model does not support is not verified. Google's thinking guide lists low, medium and high for `gemini-3.1-pro-preview`; only `low` is tested live. See "Cost".
- `--usd-dkk RATE`, `--price-in USD`, `--price-out USD`: overrides for the cost estimate. See "Cost".
- `--dry-run`: run the guards and print the exact request body, with no network call. Use it to check what would be sent. Image data is shown as `<base64 omitted, N bytes>` (N is the size of the image file), so a dry run never dumps megabytes.

An architecture review of an owned repo, with an overview as context and the files that carry the structure:

```powershell
python skills/second-opinion/scripts/second_opinion.py `
  --mode architecture `
  --requirements docs/requirements.md `
  --context docs/overview.md --context-label "system overview" `
  --files agents/lead.md agents/builder.md `
  --focus "Is the split of responsibilities between the agents clear?"
```

A design review of one screen, after Benny's explicit yes to send that image for this run:

```powershell
python skills/second-opinion/scripts/second_opinion.py `
  --mode design `
  --requirements-text "The page must let a manager see this month's result against budget at a glance." `
  --images docs/mockups/overview-page.png `
  --images-approved
```

The `request:` line on stderr names the model, the mode, the prompt size, the number of images and the thinking level, so each run can be read against what was asked for.

Exit codes: `0` success (findings JSON on stdout), `1` error (missing key, HTTP error with status and Google's message, unreadable input, invalid answer, an image of the wrong type, a request body over the size limit), `2` refused by the data guard or the image guard, or a usage error from the argument parser (for example an invalid `--thinking-level` or `--mode`, a bad `--usd-dkk`, `--price-in` without `--price-out`). The code alone does not tell the two apart: a guard refusal is the one whose stderr starts with `data guard: REFUSED`.

Tests: `python -m unittest discover -s skills/second-opinion/scripts -v` (no network).
