---
name: ai-engineering
description: Applied judgment for building applications on top of foundation models (LLMs). Covers the central AI-engineering decisions: when to reach for prompt engineering vs RAG vs finetuning (start cheap, climb only when evaluation demands it), how to evaluate AI systems (criteria, AI-as-judge, eval pipelines), defensive prompting against injection and jailbreaks, dataset and synthetic-data practice, inference cost/latency/throughput tradeoffs, and production architecture with user-feedback loops. Use this whenever you design, build, debug, or review anything LLM-backed — a chatbot, RAG pipeline, agent, prompt, eval harness, or a build/buy/finetune model choice — even when the request only says "have the model do X" without naming a technique. Without it you will over-reach for finetuning and under-invest in evaluation, the two most common mistakes.
---

# ai-engineering

AI engineering is building applications on top of foundation models someone else trained. The work moved from *building the model* to *adapting and evaluating an existing one*, which puts it much closer to software and data engineering than classical ML: you rarely touch weights, you mostly shape inputs, retrieve context, and measure outputs.

Two instincts carry most of the value here, and everything below hangs off them:

1. **Evaluate before you trust.** The hard part of shipping AI is not making a demo work once; it is knowing whether it works at all. Evaluation is the discipline, not an afterthought.
2. **Start cheap and climb only when evaluation forces you.** There is a ladder of adaptation techniques from cheap-and-fast to expensive-and-slow. Reach for the lowest rung that clears your bar.

This skill is the decision spine. Each discipline has a reference file with the depth; read the relevant one before doing more than trivial work in that area.

## The model is probabilistic — design for that, do not fight it

A foundation model samples its output from a probability distribution. Same input can give different output (**inconsistency**), and it can be confidently wrong (**hallucination**). This is not a bug to patch out; it is how the thing works, and it shapes every design choice:

- **Never treat raw output as truth** for anything that matters. The more critical the AI is to the app, the higher the reliability bar and the more validation you owe it. Real people have been burned: a lawyer filed AI-hallucinated case citations; Air Canada was ordered to pay for its chatbot's wrong answer.
- **Contain it with structure, not hope**: validate outputs (parse the JSON, check the value is in range), retry on failure (send the request twice in parallel and take the better answer rather than doubling latency), and put guardrails on input and output.
- **Turn the knobs deliberately.** Low temperature (toward 0) for factual and consistent tasks; higher for creative ones. For reproducibility, cache answers and fix the sampling variables and seed — but know you can never make it fully deterministic, hardware alone breaks that.
- **"0 to 60 is easy, 60 to 100 is brutal."** A weekend demo hides the last-mile work. Budget for the long tail of edge cases and hallucinations from the start; that is where the real cost lives.

## The adaptation ladder: start cheap, climb only on evidence

When a model is not good enough for your task, climb this ladder in order. Each rung costs more in data, skill, and maintenance than the one below it:

1. **Prompt engineering** — change the input, not the model. Clear instructions, a persona, output format.
2. **More context in the prompt** — examples (few-shot), and the specific information the task needs.
3. **RAG** — give the model retrieval over your own data so it pulls in the right context per query.
4. **Finetuning** — change the model's weights by training it further on your data.

Do not skip rungs on a hunch. The recurring field story is a team that "needed finetuning" but actually had a sloppy prompt; once the prompt was tightened, it was good enough. Finetuning demands data, ML knowledge, hosting, and ongoing upkeep — and a newer base model can leapfrog your finetuned one next month.

**The rule that settles most RAG-vs-finetuning arguments: RAG is for facts, finetuning is for form.** If the model fails because it *lacks information* (private, outdated, or too large to fit the prompt), that is a knowledge problem → RAG. If it fails because it *behaves wrong* (wrong format, wrong style, cannot produce a rare SQL dialect) and the prompt cannot fix it, that is a behaviour problem → finetuning. Have both problems? Do RAG first — it is the easier, usually bigger lift — and add finetuning later only if form is still off.

Full decision detail, the finetuning memory math (why it needs far more GPU memory than inference), LoRA/QLoRA, and the RAG retrieval and agent choices are in **`references/adaptation-ladder.md`**.

## Evaluation is the most important discipline

The worst state for an AI application is deployed and nobody knows if it works: it costs money to run and may cost more to take down. Evaluation is what keeps you out of that state, and it is genuinely hard for foundation models because open-ended output has no single ground truth — there are infinitely many correct summaries of a document.

Non-negotiable minimum for any LLM feature:

- **Define your evaluation criteria before you build** (evaluation-driven development). If you cannot describe what a bad answer looks like, you cannot catch one.
- **Automate exact/functional checks wherever the task allows** — running generated code against tests, checking a classification against a label. This is the gold standard because it is objective and repeatable.
- **Tie evaluation to a usefulness threshold and to business metrics** — "90% factual consistency" only matters if you can say what it buys ("we can automate 50% of tickets").
- **Evaluate per component and end-to-end**, on a slice of real production data, with a set large enough that the number is stable (bootstrap it to check).

How AI-as-a-judge works and where it deceives you, comparative evaluation, and the full three-step pipeline are in **`references/evaluation.md`**.

## Prompt well, and prompt defensively

Prompting is the first and often only tool you need, but it is easy to underestimate. The craft (clear instructions, personas, examples, output format, chain-of-thought, decomposition, versioning) and — just as important — the security half live in **`references/prompting.md`**. Read it before writing production prompts.

The one thing to internalise up front: **the model does not distinguish your instructions from the user's input** — everything is glued into one text. That is why your app *will* be attacked (prompt injection, jailbreaks, indirect injection through retrieved content and tools), and why a system prompt is not a real security boundary. Defence is layered and never bulletproof; track both **violation rate** and **false refusal rate** so you do not "solve" safety by refusing everything.

## Data is the lever you actually control

You usually cannot change the foundation model, but you can always change your data — for finetuning, and for building evaluation sets. This is the discipline closest to Benny's existing strengths (ETL, dedup, data quality), aimed at a new goal: teaching a model to behave rather than filling a table correctly. Data curation and quality, synthetic data and distillation, and the processing traps (dedup, test-set contamination, model collapse) are in **`references/dataset-engineering.md`**.

## Running it in production

A production AI system is never just "call the model." Inference has real cost/latency/throughput tradeoffs to reason about (even when you only consume an API), and the architecture grows one component at a time — context, guardrails, routing, caching, feedback — each solving a concrete problem the previous layer created. User feedback is not just product polish; it is the data that compounds into a moat. Both are in **`references/production.md`**.

## Note

These are applied conventions, not a substitute for reading the model provider's own docs. When a specific model, API, or repo shows a convention this skill does not capture, follow it and flag it for adding here. The distilled source is Chip Huyen's *AI Engineering*; the judgment here is what to *do*, not the theory behind it.
