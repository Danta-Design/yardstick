# Examples

Everything here is meant to be run, not read. Each example is small enough to
understand in one sitting — that is the point.

## `rag-demo/`

A deliberately minimal RAG service (one HTTP endpoint, ~20 short documents) used
as the target under evaluation. It exists so the repo has a real thing to measure
and so first-time users see a complete loop:

```
dataset → rag-demo → metrics → report → gate
```

The demo is intentionally *not* good. Some of its answers fail on purpose, so a
first run shows a believable score and a non-empty flip list when you change the
prompt.

## `datasets/`

| File | Cases | Purpose |
|---|---|---|
| `faq-50.jsonl` | 50 | Short factual QA with gold answers — exercises exact match and token F1 |
| `rag-100.jsonl` | 100 | Document QA with `relevant_ids` — exercises retrieval metrics and judge |
| `calibration-100.jsonl` | 100 | Human-labeled, used by `yardstick calibrate` to report κ |

Dataset fields:

| Field | Required | Notes |
|---|---|---|
| `case_key` | yes | Stable across versions; the join key for diffs |
| `input` | yes | What the target receives |
| `expected` | no | Gold answer, when one exists |
| `relevant_ids` | no | Gold document ids, for retrieval metrics |
| `meta` | no | Free-form tags (difficulty, category) for slicing |

## `rubrics/`

Markdown rubric files. One criterion per section, with anchors at 1/3/5. The
file hash is stored on every run, so editing a rubric invalidates comparisons by
design.

## Adding your own

Point `dataset:` at your file and `target:` at your service. If the shape does not
fit, open an issue before writing an adapter — the interface is still cheap to
change now and expensive later.
