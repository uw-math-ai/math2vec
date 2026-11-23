**Lean Statement Diversity Dataset** *A project to generate a dataset of Lean 4 theorem statements that are semantically similar but mathematically distinct, and evaluate its quality and potential for training formal math embeddings.*

*GitHub: leoca42/DALAB-May-2026-Lean-wiggle-wiggle* *Dataset: FrenzyMath/mathlib\_informal\_v4.19.0*

**Priorities:** Goals 1 (dataset generation) and 2 (evaluation) are the primary deliverables. Goal 3 (embedder training) is a nice-to-have if time permits.

---

**Motivation**

This project was inspired by two ongoing projects at the UW Math AI Lab: TheoremSearch, which does semantic retrieval over 9 million mathematical theorems from ArXiv and The Stacks Project, and Math2Vec, which is building a universal math embedder for both natural language and Lean statements. A synthetic dataset of perturbed Lean theorems could be used to train text embedders for Lean theorem retrieval using contrastive loss, directly contributing to theorem search on Lean.

*Related Work*

Existing work on synthetic Lean generation (LeanDojo, lean-error-correction, Synthetic Theorem Generation in Lean, Lean Finder) has focused on perturbing Lean proof states rather than full theorem statements, and has used LLMs to generate perturbations rather than Lean's own tactics and typechecker. This project differs in both respects: we perturb full theorem statements, and we use Lean tactics and the Lean compilation to guarantee validity.

---

**What This Project Does**

We perturb Lean theorem statements to create semantically similar but mathematically distinct variants. Perturbations are implemented as Lean tactics, primarily by traversing Mathlib's typeclass hierarchy to mutate typeclasses in theorems, and by computing negations, contrapositives, and converses. The negation tactic embeds the negation deep into the statement itself rather than prepending a negation sign. All perturbation logic runs in Lean; Python handles file I/O and orchestration. Perturbed statements are validated using Lean's typechecker as a validity oracle. Perturbations may or may not be mathematically true, but they are all valid Lean statements.

---

**Goal 1: Dataset Generation**

Start from a corpus of real Lean 4 theorem statements from Mathlib. Apply one or more perturbation rules to produce a variant, verify it in Lean, and record the result. The final dataset is a set of (anchor, variant, perturbations\_applied, truth\_value) tuples.

*Perturbation Types*

* **Negation** — negate the conclusion deeply within the statement (not just prepending ¬). Always produces a false statement from a true anchor.  
* **Contrapositive** — rewrite P → Q as ¬Q → ¬P. Logically equivalent to the anchor; always true.  
* **Converse** — rewrite P → Q as Q → P. Truth value is unknown.  
* **Generalization** — remove an unused or weakly-used hypothesis, making the statement stronger or unprovable. Statement remains true if the hypothesis was redundant.  
* **Typeclass weakening in hypothesis** — replace a typeclass in the hypothesis with a parent class (e.g. Field → CommRing). Statement remains true since the weaker assumption still suffices.  
* **Typeclass strengthening in hypothesis** — replace a typeclass in the hypothesis with a child class (e.g. CommRing → Field). Statement remains true since stronger assumptions also suffice.  
* **Typeclass strengthening in conclusion** — replace a typeclass in the conclusion with a child class (e.g. Ring → Field). Truth value is unknown; the conclusion becomes harder to satisfy.  
* **Typeclass weakening in conclusion** — replace a typeclass in the conclusion with a parent class. Statement remains true.  
* **Bound flipping** — flip the direction of an inequality (≥ → ≤, \> → \<). Truth value is always unknown; depends entirely on the specific statement.

*Truth Value Propagation*

Each perturbation has a known effect on truth value given the truth of the anchor. Since all anchors come from Mathlib they are known to be true. Truth is propagated symbolically through the perturbation chain according to the following rules:

| Perturbation | True anchor → | False anchor → |
| ----- | ----- | ----- |
| Negation | False | True |
| Contrapositive | True | False |
| Converse | Unknown | Unknown |
| Generalization | Unknown | False |
| TC weaken hypothesis | True | Unknown |
| TC strengthen hypothesis | True | Unknown |
| TC strengthen conclusion | Unknown | Unknown |
| TC weaken conclusion | True | Unknown |
| Bound flip | Unknown | Unknown |

*Perturbation Chains*

Rather than applying a single perturbation per anchor, the pipeline applies perturbations in sequence, compiling after each step. Each successfully compiled intermediate is saved as a separate datapoint. A chain stops when compilation fails or the maximum chain depth is reached. Multiple random orderings of perturbations are tried per anchor.

*Lean Verification Step*

After each perturbation, the variant is run through Lean's typechecker to confirm it is a well-formed statement. Variants that fail to compile are discarded and stop the current chain.

---

**Goal 2: Evaluation** *(Next Steps)*

Two complementary axes: semantic similarity (are anchor and variant still about the same thing?) and mathematical diversity (how varied is the full dataset?). Mathematical distinctness is also verified per pair as a hard filter.

*Semantic Similarity Score (per pair)*

* **Embedding cosine similarity** — embed both statements with a general-purpose code or math language model (CodeBERT, text-embedding-ada-002, or a Lean-aware model). Cosine similarity in \[0,1\] is the primary per-pair score. Target threshold ≥ 0.70.  
* **NL docstring overlap** — if statements have /- \-/ comments, compute BLEU or BERTScore between docstrings as a secondary signal.  
* **AST overlap** — tokenize both Lean expressions and compute token-level Jaccard or edit distance. High overlap indicates good semantic preservation.  
* **Human spot-check** — for a sample of \~50 pairs, manually rate "same topic" on a 1–3 scale for calibration.

*Mathematical Distinctness Verification (per pair)*

This is a hard filter — pairs that fail are discarded from the dataset entirely.

* **Lean unprovability check** — for negations and generalizations, attempt to prove the variant using Lean's decide tactic or an automated prover (aesop, omega). If the variant is provable by the same proof as the anchor, it is not genuinely distinct and is dropped.  
* **Proof term comparison** — if both statements are provable, compare their proof terms. Identical or alpha-equivalent proof terms indicate the variant is not mathematically different.  
* **Contrapositive flagging** — contrapositives are logically equivalent by definition and should be labeled "equivalent but syntactically distinct" rather than "mathematically different." They are useful as hard negatives for an embedder but should not count toward mathematical diversity metrics.  
* **Type signature diff** — check that the elaborated type of the variant is not definitionally equal to the anchor's type using Lean's \#check or kernel reduction.

*Mathematical Diversity Metrics (dataset-level)*

* **Transformation entropy** — Shannon entropy over the transformation type distribution. Higher is better; a balanced mix across perturbation types is the goal. Target ≥ 1.5 bits.  
* **Pairwise cosine dispersion** — mean and standard deviation of cosine distances between all variant embeddings. Higher standard deviation means variants are spread across the embedding space.  
* **Provability label coverage** — fraction of pairs labeled true / false / unknown. Broad coverage across all three is ideal.  
* **Topic diversity (clustering)** — number of distinct k-means clusters in embedding space. More clusters means the dataset covers diverse math domains.

Targets: cosine similarity ≥ 0.70 per pair; transformation entropy ≥ 1.5 bits across the dataset.

---

**Goal 3: Embedder Training** *(Next Steps)*

Use the generated (anchor, variant) pairs as a contrastive training signal. Anchors and same-topic variants are positives; negated or over-generalized variants are hard negatives. Fine-tune a base model (e.g. CodeBERT or a small LLaMA variant) with a contrastive loss such as SimCSE or NT-Xent. Evaluate against existing Lean and formal-math embedders on retrieval benchmarks such as theorem retrieval from Mathlib.

---

**Scaling to 200k Datapoints**

*Pipeline Architecture*

A local script pulls the source dataset from Hugging Face as JSON and sends it to an API server. The server handles all heavy processing and writes the output back to Hugging Face as a new JSON dataset. Inside the server, processing happens in four steps: parse the input JSON, batch it into chunks, run perturbation chains in parallel across batches, and periodically push completed results to Hugging Face.

*User-Configurable Parameters*

* **Batch size** — number of datapoints processed together. Default 32, chosen to keep memory usage bounded without being too small to benefit from parallelism.  
* **Max chain depth** — maximum number of perturbations applied in a single chain. Limits combinatorial explosion.  
* **Number of permutations** — how many random orderings of perturbations to try per datapoint.  
* **Push frequency (N)** — push results to Hugging Face every N batches. Default N \= 50, meaning a checkpoint roughly every 1,600 datapoints, avoiding rate limiting while ensuring partial progress is saved if the job crashes.

*Time Estimates*

| Mode | Time per batch | Total time (batch size 32, 200k datapoints) |
| ----- | ----- | ----- |
| Sequential | 32 minutes | \~139 days |
| Parallel | 1 minute | \~4.3 days |

Assumptions: 1 minute per datapoint, 6,250 total batches (200k / 32).

Sequential processing is infeasible at this scale. Parallel processing across batches brings total runtime down to approximately 4.3 days, which is acceptable for a research dataset.

*Chain Stopping Rules*

A perturbation chain stops early under two conditions: the compiled variant is identical to the current statement (no real change), or compile\_lean returns false. In both cases the chain halts immediately and the pipeline moves on to the next permutation for that anchor. There is no retry logic since a failed compilation is a dead end for that chain.

*Temp File Handling*

Each batch gets its own uniquely named temporary Lean file to avoid race conditions when batches run in parallel. Temp files are cleaned up after each batch completes, including in the event of a crash, using a finally block to guarantee cleanup.

*Writing Results to Hugging Face*

Rather than accumulating all results in memory until the end, completed batches are pushed to the Hugging Face dataset repository every N batches. This keeps memory usage flat regardless of total dataset size and ensures partial progress is saved if the job crashes. Each push is a commit to the HF repo so N should be large enough to avoid rate limiting — 50 batches is the recommended default.

---

**Known Limitations and Bottlenecks**

* Lean elaboration is slow: 5–30 seconds per perturbation on a laptop. There is no clear path to GPU acceleration for this step.  
* Frontier LLMs can produce perturbations faster, but without Lean's typechecker as a validity oracle, correctness is not guaranteed.  
* The negation tactic regex assumes the Lean output always contains the word "extracted" — if tactic naming changes across Lean or Mathlib versions, negation will silently return nothing.  
* The perturbation name used in the chain (e.g. "negate") must match the key used in the truth propagation table exactly, or truth values will silently default to "unknown."  
* Different permutations of the same perturbations can produce identical (anchor, variant) pairs. Deduplication on (anchor\_type, variant\_type) before saving is recommended.

---

**Open Questions**

* Which embedding model is most appropriate as the similarity judge given Lean's syntax? A general code model versus a math-tuned model may behave very differently.  
* How should contrapositives be treated in diversity metrics given they are logically equivalent to the anchor?  
* What is the right N for Hugging Face push frequency given API rate limits in practice?
