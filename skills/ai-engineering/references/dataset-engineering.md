# Dataset engineering

You rarely get to change the foundation model, but you can always change your data — the data-centric lever. This is the discipline closest to Benny's existing strengths (ETL, dedup, data quality), redirected: instead of feeding a report correct numbers, you are teaching a model to behave. That shifts what "quality" and "enough" mean. Relevant whenever you finetune, or build evaluation/annotation sets.

- [Curation: quality, coverage, quantity](#curation-quality-coverage-quantity)
- [Synthetic data and distillation](#synthetic-data-and-distillation)
- [Processing: the part that looks like your day job](#processing-the-part-that-looks-like-your-day-job)

## Curation: quality, coverage, quantity

Think ingredients: quality is freshness, coverage is the right mix, quantity is enough of it. Curation is not only adding data — it is removing data so the model *un-learns* bad behaviour.

- **Quality beats quantity, and it is not close.** A little high-quality data usually beats a lot of noisy data. The LIMA paper finetuned on 1,000 curated examples and matched or beat GPT-4 in 43% of cases; the Yi team's 10,000 careful instructions beat hundreds of thousands of noisy ones. Six practical quality traits: relevant, aligned with the task (factual if the task needs facts, creative if it needs creativity), consistent (two annotators agree), correctly formatted, sufficiently unique (few duplicates), compliant (no PII, legal). These are your familiar data-quality dimensions aimed at behaviour.
- **Coverage/diversity: cover the whole range of how your users actually behave.** If some users write long detailed prompts and others short typo-ridden ones, both belong in the data. A model trained on data that is *both* high-quality and diverse beats one that is only one of the two — but more heterogeneous data can *hurt* (the Data Addition Dilemma). More is not automatically better.
- **Quantity: start small, read the curve.** Beyond quality and diversity, the amount you need depends on the finetuning technique (full finetuning needs orders of magnitude more than PEFT/LoRA), task complexity, and how close the base model already is. Start with ~50 well-curated examples. See improvement → more data will help. See none → a big dataset rarely rescues it (check hyperparameters and prompts first — with 50–100 examples you should normally see *something*). Finetune on 25/50/100% and plot the curve to estimate the payoff of doubling; expect diminishing returns.

**The best data source is your own application.** A **data flywheel** — user data continuously improving the product — is a moat competitors cannot easily copy, because it matches exactly the distribution you care about. Otherwise check public datasets, but always check the license *and* the lineage (even a commercially-licensed set can contain unlicensed parts).

**Annotation guidelines are the hard part**, not the annotating itself — what makes a 3 versus a 4, can an answer be correct but unhelpful. Good news: these are the same guidelines you write for evaluation (`references/evaluation.md`), so the work counts twice.

## Synthetic data and distillation

- **Augmentation vs synthesis.** Augmentation derives new data from real data (synonym swap, flip an image); synthesis generates data that mimics real data without being derived from it. AI makes sophisticated synthesis practical (code, contracts, records).
- **Why code is the favourite thing to synthesise:** it can be *verified programmatically* — run it, check the tests pass. Llama 3 generated 2.7M+ code examples by generating, translating between languages, and back-translating, keeping only code that passed parsers, linters, and unit tests. Verify synthetic data the same way you verify any AI output: functional correctness or AI judges (watch first-position bias — ask twice with swapped order and keep only examples where the same winner wins both times, as NVIDIA did).
- **Reverse instruction** is a sharp trick: take an existing high-quality long text (a book, Wikipedia) and have AI generate the *prompt* that would elicit it — so the answer is human-written and hallucination-free.
- **Distillation** trains a small student to imitate a large teacher (DistilBERT: 40% smaller, 60% faster, 97% of the understanding). But watch **superficial imitation** — a weak student trained on a teacher's math solutions learns to *look like* it reasons, i.e. to hallucinate confidently. Style transfers; capability does not. Real reasoning gains need a better base model.

## Processing: the part that looks like your day job

- **Inspect the data by eye.** Plot distributions (token counts, input/output lengths, topics, languages, per-annotator scores). Fifteen minutes of looking saves hours of debugging. Compute inter-annotator disagreement and resolve it.
- **Deduplicate** — this is your identity-resolution toolkit (pairwise similarity, MinHash, Bloom filters). Duplicates hurt twice: they skew the distribution, *and* they cause **test-set contamination** (the same example in train and test makes your evaluation a lie). Repeating 0.1% of data 100× degraded an 800M model to 400M-level.
- **Clean and filter.** Strip HTML/Markdown (Databricks got +20% accuracy and −60% input length from that alone), remove PII and non-compliant fields, drop low-quality data.
- **Format to the model's exact chat template and tokenizer.** After finetuning, your prompts must match the training format exactly or the model fails.

**Pitfalls that end projects:**

- **Model collapse.** Train recursively on AI-generated data and rare events vanish until the model degrades irreversibly. Fully synthetic makes collapse inevitable; mixing synthetic with real data avoids it (nobody knows the right ratio).
- **Obscure data lineage.** Generate data with model X and you inherit X's problems — its copyright exposure, its benchmark contamination — invisibly.
- **Changing data in place.** Always keep a copy of raw data. Other teams may need different processing, and a script bug can corrupt it (the classic: floats saved as integers and rounded).
- **Concluding too early that finetuning "doesn't work."** The cause is often a wrong learning rate or a bad prompt, not the data volume.
