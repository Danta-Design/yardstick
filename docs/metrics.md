# Metrics

Every number this tool prints must have a written definition. If a metric is
ambiguous, two runs will disagree and nobody will trust the gate.

## Philosophy

- **Layered, not a single score.** A drop in retrieval recall and a drop in answer
  quality need different fixes. Collapsing them into one number hides the cause.
- **Per-case is the source of truth.** Aggregates are derived. Every aggregate
  must be drillable to the cases that produced it.
- **Nondeterminism is disclosed.** Judged metrics carry their sampling settings
  and calibration results in the report.

---

## Retrieval metrics

Let `R` be the retrieved list (ranked), `G` the set of relevant ids, `k` the cutoff.

| Metric | Definition | Reads as |
|---|---|---|
| `recall@k` | `|R[:k] ∩ G| / |G|` | Did we find the needed documents at all? |
| `precision@k` | `|R[:k] ∩ G| / k` | How much of what we fetched was useful? |
| `mrr` | mean of `1/rank(first relevant)` | Did the right document rank near the top? |
| `ndcg@k` | DCG@k / IDCG@k, graded relevance | Same, but credits partial relevance |

Requires gold `relevant_ids` per case. Cases without them are excluded from these
metrics and counted as `missing_gold`, never as zero.

---

## Generation metrics

| Metric | Definition | When to use |
|---|---|---|
| `exact_match` | normalized string equality | Short factual answers |
| `token_f1` | F1 over normalized token multisets | Extractive QA |
| `rouge_l` | longest common subsequence F1 | Summaries (use with care) |

Normalization: lowercase, strip punctuation, collapse whitespace. Document any
change to normalization — it silently moves every historical score.

---

## Judged metrics

### Rubric format

A rubric is a Markdown file with:

1. The task framing (one paragraph).
2. 2–4 criteria, each with anchors at score 1, 3, and 5.
3. An explicit "what counts as a failure" list.

The rubric file's SHA-256 is stored on the run. Changing the rubric invalidates
comparisons — the report says so.

### Scoring protocol

1. Temperature 0, fixed max tokens.
2. `samples: n` independent calls per case (default 3); take the **median**, not
   the mean — one outlier should not move a score.
3. Output is JSON: `{ "score": int, "reason": str, "failed_criteria": [str] }`.
   Malformed output gets one repair attempt, then the case is `indeterminate`.
4. Optional second judge model. If `|score_a - score_b| >= 1`, flag
   `needs_review` — do not average away a disagreement.

### Caching

Key: `sha256(model | rubric_hash | prompt_input | target_output)`.

The cache is content-addressed and persistent. Re-running an unchanged dataset
against an unchanged target should cost nothing. Report the hit rate; a low hit
rate in CI usually means the target is nondeterministic.

### Calibration

Ship a 100-case human-labeled set (`examples/datasets/calibration-100.jsonl`).
`yardstick calibrate` computes:

- Cohen's κ between judge and human labels (the headline number).
- Per-criterion agreement, to find which rubric clause is fuzzy.
- Confusion counts, especially false passes — the ones that hide regressions.

Interpretation: `< 0.4` poor, `0.4–0.6` fair, `0.6–0.8` substantial, `> 0.8` strong.

**v0.1 acceptance: κ ≥ 0.7 on the calibration set.** Publish the number in the
README. If it drops, that is a regression like any other.

---

## System metrics

| Metric | Definition |
|---|---|
| `latency_p50` / `latency_p95` | Per-case target latency, errors included in the percentile input |
| `cost_per_case` | Priced from provider usage tables; unknown models fall back to `null`, never `0` |
| `error_rate` | `error_items / total_items` |

---

## Aggregation and significance

- Default aggregate is the **macro average over scored cases**, so a long case
  cannot outweigh a short one.
- `indeterminate` and `error` are excluded from the score and reported beside it.
- Comparison reports `Δ` with a **bootstrap 95% CI** (1,000 resamples).
  **If the CI crosses zero, the report says "no significant change"** — even if
  the raw delta looks impressive. This single rule prevents most bad decisions.

---

## Gate rules

Evaluated in order; first failure wins and is reported.

| Rule | Behavior |
|---|---|
| `min_score` | Absolute floor on the primary metric |
| `max_regression` | Allowed drop vs. baseline, with significance check |
| `max_error_rate` | Infrastructure health, not quality |
| `max_latency_p95` | Optional, for latency-sensitive products |

A gate failure prints the failing rule, the involved cases, and the report path.
An override label skips the gate but leaves a comment on the PR — overrides must
be visible.

---

## Anti-patterns

- **Optimizing the aggregate.** A 2% overall gain that breaks the 20 hardest
  cases is a regression. Always read the flip list.
- **Changing the dataset and the prompt in the same commit.** Then you cannot
  attribute the change.
- **Judging without a rubric file.** Inline rubrics drift and are unversioned.
- **Reporting a score without `indeterminate` counts.** It is the most common way
  evaluation tools quietly lie.
