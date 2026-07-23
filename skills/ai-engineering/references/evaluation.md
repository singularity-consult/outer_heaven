# Evaluating AI systems

Evaluation is the largest bottleneck to shipping AI, and often the largest share of the real work. It is hard because open-ended output has no single ground truth. This file is how to do it well enough to make decisions you can defend.

- [What to measure: evaluation criteria](#what-to-measure-evaluation-criteria)
- [How to measure: methods, cheapest-reliable first](#how-to-measure-methods-cheapest-reliable-first)
- [AI as a judge, and where it deceives you](#ai-as-a-judge-and-where-it-deceives-you)
- [Building the evaluation pipeline](#building-the-evaluation-pipeline)
- [Selecting a model](#selecting-a-model)

## What to measure: evaluation criteria

Decide the criteria *before* building (evaluation-driven development), and beware the streetlight trap: measuring only what is easy to measure means you may skip the most valuable applications precisely because they are hard to evaluate.

The criteria that matter for most applications:

- **Domain capability** — can the model do the underlying task at all (code, the relevant language, the domain)? If this is missing, nothing else helps. For code, use functional correctness. Note that correct is not the same as usable: a correct SQL query that is too slow is useless.
- **Generation quality** — fluency and coherence are largely solved by modern models; the pressing ones now are **factual consistency** and **safety**.
  - *Local* factual consistency: is the output consistent with a given context (a summary faithful to its source)? Matters for summarisation, support bots, data analysis.
  - *Global* factual consistency: is it consistent with open, accepted knowledge? Matters for general chatbots and fact-checking. The hard part is often deciding *what a fact even is*.
- **Instruction-following** — does it follow *your* instructions (return `A/B/C`, emit JSON), independent of whether it can do the task? A model can nail the task and still break your pipeline by answering "That's correct" instead of "A". Separate this failure from a domain failure — the cause is different.
- **Cost and latency** — a brilliant model that is too slow or too expensive is unusable. Treat this as **Pareto optimization**: decide what you cannot compromise on, filter out models that miss it, then pick the best of the rest.

Beware: **high MCQ/multiple-choice accuracy measures recognition, not generation.** A model can pick the best summary from a list without being able to write a good one. Do not infer generation quality from a recognition benchmark.

## How to measure: methods, cheapest-reliable first

- **Exact / functional correctness** — objectively right or wrong, and where possible automated (run the code against tests; check the label). This is gold: repeatable and cheap. Reach for it whenever the task allows (code, SQL, math, anything measurable).
- **Similarity to reference data** — when there is a ground truth. Three flavours, weakest to strongest: exact match (only for short unambiguous answers), lexical similarity (BLEU/ROUGE — n-gram overlap, and a correct answer can score low while wrong-but-similar scores high), semantic similarity (embeddings + cosine — catches "What's up?" ≈ "How are you?"). Reference data is the bottleneck: expensive to make and sometimes just wrong.
- **AI as a judge** — no reference data needed, flexible to any criterion, fast and cheap. Now the most common production method — and the most abused. See below.
- **Comparative evaluation** — rank models by pairwise "A beats B" preference instead of absolute scores. Good for subjective quality and hard to game (it powers Chatbot Arena). But a 55% win rate tells you B beats A, not whether *either* is good enough — always pair it with an absolute evaluation against your threshold.

## AI as a judge, and where it deceives you

Use it, because it is fast, cheap, reference-free, and can explain itself — but treat it as a system, not an oracle.

**Prompt the judge properly:** state (1) the task, (2) the criteria in as much detail as you can, (3) the scoring system. Models judge text better than numbers, so prefer classification (good/bad) over scores; if you need numbers use a small discrete range (1–5) and give an example of what a 1, 3, and 5 look like — that lifts both quality and consistency.

**The failure modes that will bite you:**

- **A judge is model + prompt + sampling params.** Change any part and it is a different judge; its scores are not comparable to another judge's. Never trust a judge score whose model and prompt you cannot see.
- **The judge drifts under you.** It is itself an AI application that changes over time. A coherence score moving 90%→92% might mean the app improved or someone fixed a typo in the judge prompt. Especially dangerous when app and judge are owned by different teams — version and freeze the judge.
- **Criteria are not standardised.** "Faithfulness" scored 1–5 (MLflow), 0/1 (Ragas), and YES/NO (LlamaIndex) are not comparable.
- **Known biases:** self-bias (a model favours its own output), first-position bias (favours the first of two — mitigate by swapping order and repeating), verbosity bias (favours longer answers even when wrong).
- **Consistency is not correctness.** A judge can be reliably wrong the same way every time.

Cut cost with weaker judge models and **spot-checking** (score a sample, not everything). Consider specialised small judges — reward models, reference-based judges, preference models — over a big general one.

## Building the evaluation pipeline

Three steps:

1. **Evaluate every component and end-to-end.** Break the system up and measure each link (extract-employer-from-CV = PDF→text, then text→employer); without per-component measurement you cannot tell where it failed. Distinguish turn-based quality (each response) from task-based (did the whole task get solved, in how many turns) — task-based matters most to the user.
2. **Write an evaluation guideline — the most important step.** Define what the app must do *and must not*. Correct is not the same as good ("You're a terrible fit for this job" can be true and useless). Build scoring rubrics with concrete examples, validate them with real people, and tie scores to business metrics with a **usefulness threshold** (the minimum score at which the app is worth anything).
3. **Pick methods and data per criterion.** A small fast classifier for safety, semantic similarity for relevance, an AI judge for factual consistency — mix them (a cheap classifier on 100% plus an expensive judge on 1%). Annotate real production data. **Slice** it (evaluate subgroups) to catch bias and avoid Simpson's paradox, where a model wins every subgroup but loses overall. Use **bootstrapping** to check the set is big enough: resample it many times, and if the score swings from 70% to 90%, the set is too small to trust.

Then evaluate the pipeline itself: is it reproducible (judge temperature 0), how correlated are its metrics, how much cost/latency does it add? Iterate — but keep it consistent, or the results cannot steer development.

## Selecting a model

Four steps: (1) filter on **hard attributes** you cannot change (license, size, your own privacy rules) — but be slow to write a model off on a soft attribute like accuracy, which prompting or decomposition can lift a lot; (2) narrow with public benchmarks/leaderboards — but only to *screen out* weak models, never to pick the winner, because they are likely contaminated (trained on the test data) and rarely match your use case; (3) run your own evaluation pipeline to find the winner; (4) monitor in production.

**Build vs buy** turns on data privacy, data lineage/copyright, performance, cost (API vs engineering), control/transparency (open models expose logprobs — the model's per-token confidence, which is genuinely useful for classification), and on-device needs. The strongest models will likely stay proprietary; open models are often good enough and give you control.
