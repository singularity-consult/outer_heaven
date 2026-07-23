# Adaptation ladder: prompt vs RAG vs finetuning

The central build decision. This file is the depth behind the ladder in SKILL.md: how to choose a rung, and the mechanics you need to act once you have chosen.

- [Choosing the rung](#choosing-the-rung)
- [RAG: how to build retrieval that helps](#rag-how-to-build-retrieval-that-helps)
- [Agents: tools, planning, and where they break](#agents-tools-planning-and-where-they-break)
- [Finetuning: when, and the memory reality](#finetuning-when-and-the-memory-reality)

## Choosing the rung

Climb in this order, and only when your evaluation shows the current rung falls short:

`prompt engineering → more examples/context → RAG → advanced RAG and/or finetuning → combine`

The whole point is cost. Each step up demands more data, more ML skill, more hosting, and more maintenance. A finetuned model is also a liability: it ages, and a stronger base model can make it obsolete. So exhaust the cheap rungs *properly* before climbing: the classic waste is finetuning to fix what a tightened prompt would have fixed.

**RAG is for facts, finetuning is for form.** This resolves most arguments:

| Symptom | Real problem | Fix |
| --- | --- | --- |
| Wrong/outdated/missing facts; needs private or fresh data | knowledge gap | RAG |
| Right facts, wrong format/style/tone; can't produce a rare dialect | behaviour gap | finetuning |
| Both | both | RAG first (bigger, cheaper lift), finetuning later |

Two more judgment calls:

- **RAG does not disappear as context windows grow.** There is always more data than fits, models use long contexts poorly (they attend to the start and end, lose the middle), and every extra token costs money and latency. Longer context is not a substitute for retrieving the *right* context.
- **Start RAG simple.** Begin with term-based retrieval (BM25), not a vector database. Add embeddings, hybrid search, and reranking only when retrieval quality (measured, see below) demands it.

## RAG: how to build retrieval that helps

A RAG system is a **retriever** (finds information) plus a **generator** (the model that writes the answer from it). The whole system is only as good as the retriever: retrieve garbage, generate garbage. This is feature engineering for foundation models: you are constructing the right context per query.

**The retrieval choices that matter:**

- **Chunking.** Split documents into retrievable chunks. Smaller chunks fit more into context but risk losing coherence; use overlap so a fact straddling a boundary is not cut in half. There is no universally best size. Evaluate a couple.
- **Term-based vs embedding-based.** Term-based (BM25, inverted index) matches keywords: fast, cheap, and exact, but blind to meaning ("transformer architecture" also returns electrical transformers). Embedding-based matches meaning via vectors in a vector database, but *slurs precise strings*: error codes like `EADDRNOTAVAIL (99)`, product names, IDs. Neither alone is enough for most real corpora.
- **Hybrid search + reranking.** Combine them: a cheap broad retriever gets candidates, then a precise reranker (or an ensemble fused with reciprocal rank fusion) picks the best. This is the pragmatic default when a single method underperforms.
- **Contextual retrieval.** Enrich each chunk with metadata (tags, error codes, a short generated sentence placing it in its document) so it is easier to find. This rescues the keywords embeddings blur.
- **Query rewriting.** Rewrite ambiguous follow-ups into standalone queries before retrieval ("What about Emily?" → "When did Emily Doe last buy?"). Watch identity lookups: the model must look up, not hallucinate, a name.

**Evaluate the retriever, or you are flying blind:**

- **Context precision** (what fraction of retrieved docs were relevant): cheap, an AI judge can score it.
- **Context recall** (what fraction of relevant docs were retrieved): expensive (needs every doc annotated against the query), so many systems skip it and measure precision only.
- Evaluate on three levels: retrieval quality, the end-to-end answer, and (for semantic search) the embeddings themselves.

**Text-to-SQL** is RAG over tabular data and sits close to Benny's world: model turns the question into SQL from the schema, the SQL runs, the model answers from the result. With many tables, add a step that first predicts which tables are needed.

## Agents: tools, planning, and where they break

An agent perceives an environment and acts on it through **tools**. Tools fall into three kinds: knowledge augmentation (retrievers, SQL, web search: read-only, safe), capability extension (calculator, code interpreter: fixes the model's weak spots cheaply), and **write actions** (send email, write to a DB, move money: powerful and dangerous).

The judgment for building agents:

- **Compound errors are the killer.** Accuracy multiplies across steps: 95% per step is ~60% over 10 steps, ~0.6% over 100. So agents need stronger models than one-shot tasks, and you should keep the step count down.
- **Decouple planning from execution.** Let the agent produce a plan, *validate it* (a bad plan can burn hours and never reach the goal), and only then execute. Plan in natural language at a coarse grain so the plan does not shatter when a tool is renamed.
- **Guard write actions like production access.** You would not give a flaky intern keys to the prod database or the ability to wire money. Automate gradually, require human approval for impactful actions (DELETE/DROP/transfer), and sandbox any code interpreter.
- **Reflection (ReAct: Thought → Act → Observation) is cheap and high-value**: it turns "runs" into "succeeds." Print every tool call and its output, and test each tool in isolation.

**Memory** ties RAG and agents together: internal knowledge (in the weights), short-term (the current context: fast, small, gone between tasks), long-term (external, retrieved, persistent). Info every task needs → bake into the model; rarely needed → long-term store; immediately relevant → short-term. Avoid naive FIFO eviction: the earliest messages often carry the conversation's purpose.

## Finetuning: when, and the memory reality

Finetune for **form/behaviour** (see the table above), on a task where prompting and RAG have genuinely topped out. Prefer PEFT/LoRA on a stronger base model when you have little data (a few hundred to few thousand examples); full finetuning needs far more.

**Why finetuning is memory-hungry (the napkin math that tells you if a model even fits your GPU):**

- Inference memory ≈ parameters × bytes-per-parameter × ~1.2 (activations). A 13B model in 16-bit ≈ 26 GB × 1.2 ≈ 31 GB.
- Full finetuning adds gradients and optimizer state. With Adam that is ~3 extra numbers per *trainable* parameter. A 7B model in 16-bit: 14 GB weights + ~42 GB (7B × 3 × 2 bytes) ≈ 56 GB. It blows past a 24 GB consumer card.
- The fix is to cut *trainable* parameters (**LoRA**: train two small matrices instead of the big weight matrix, under 0.1% of parameters, and it folds back in with no inference latency) or cut *bits* (**quantization**). **QLoRA** does both: 4-bit base weights + LoRA adapters, finetuning a 65B model on a single 48 GB card.
- Keep LoRA rank `r` low (4–64); higher rarely helps and can overfit.

**Serving many finetunes cheaply:** LoRA adapters are tiny and modular, so 100 customer-specific models share one base model: store one big weight matrix plus 100 small adapter pairs, swap the adapter to switch customer.

**Traps:** don't finetune a *knowledge* gap (it won't add facts, and can worsen hallucination on low-quality data: use RAG); FP16 and BF16 are not interchangeable despite equal bit-width (the classic Llama 2 quality drop); narrow finetuning can degrade every other task (train on a mix, or keep separate models and merge them).
