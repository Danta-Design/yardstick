# Architecture

Status: draft · applies to `v0.1`

## Goals

1. One command evaluates an LLM application and produces a report a human can read and a machine can gate on.
2. Two runs of the same dataset version are strictly comparable.
3. The common path (CI) needs no server, no database, no network beyond the target under test.
4. Adding a target or a metric is a small, documented change — not a fork.

## Non-goals

- Online traffic splitting or A/B testing.
- Hosted multi-tenant service.
- Human annotation workflows.
- Prompt authoring or version control (delegate to git).

---

## System shape

There are deliberately two shapes, sharing one core:

```
┌─────────────────────────────────────────────────────────┐
│ CLI (primary)                                           │
│  config → runner → targets → metrics → judge → report   │
│                                   │                     │
│                          runs/<id>/report.json           │
│                          runs/<id>/report.junit.xml     │
└───────────────────────────────┬─────────────────────────┘
                                │ --push (optional)
                                ▼
┌─────────────────────────────────────────────────────────┐
│ Server (optional)                                       │
│  FastAPI  →  Postgres  →  React dashboard               │
└─────────────────────────────────────────────────────────┘
```

The CLI is the product. The server exists so a team can look at history together.

---

## Components

### CLI

Entry point and orchestration. Responsibilities:

- Parse `eval.yml`, resolve relative paths, merge defaults.
- Resolve the dataset version and verify its content hash.
- Construct the target adapter, the metric set, and the judge.
- Drive the runner, write artifacts, print the report.
- Compute the exit code from the gate.

It must remain usable with zero configuration beyond a dataset and a target.

### Runner

Executes cases with bounded concurrency. Owns:

- A worker pool with a configurable concurrency limit (default 8).
- Per-case timeout and retry with exponential backoff + jitter on 429/5xx.
- A checkpoint file written every N cases, enabling `--resume`.
- Per-case capture of output, latency, token usage, and estimated cost.

The runner never decides whether a result is good — that is the metric layer's job.

### Targets

A target is "the thing being evaluated". v0.1 ships three adapters behind one interface:

| Adapter | Input | Typical use |
|---|---|---|
| `http` | POST JSON to a URL | Any OpenAI-compatible service or your own API |
| `cli` | argv + stdin | Wrapping an existing script or binary |
| `python` | a callable in a module path | Local experiments, unit-style evaluation |

Interface contract: takes a case, returns `{output, latency_ms, usage}` or raises a typed error. Adapters translate provider-specific shapes into that contract — nothing downstream should know which provider was used.

### Metrics

Split into deterministic and judged:

- **Deterministic** — exact match, token F1, retrieval recall@k / precision@k / MRR / nDCG@k. Pure functions, trivially testable, no model calls.
- **Judged** — rubric-based scoring by an LLM. Isolated behind a cache and a calibration harness because it is the only nondeterministic part of the system.

### Judge

Wraps a model call with the variance controls described in `docs/metrics.md`:

- Rubric is a file; its hash is part of the cache key and is stored on the run.
- `samples: n` independent scorings, median taken.
- Optional second model; disagreement above a threshold flags the case for human review.
- Every judgement is cached by `sha256(model | rubric_hash | input | output)`.

### Report

Three artifacts per run, all written under `runs/<run_id>/`:

| File | Audience |
|---|---|
| `report.json` | tooling, the server, diffs |
| `report.junit.xml` | CI systems that already parse JUnit |
| stdout summary | humans in a terminal |

The report embeds the full config snapshot and the dataset version hash. Without those, comparison is meaningless.

### Server

FastAPI + Postgres. Small surface:

- `POST /runs` — push a report
- `GET /projects/{slug}/runs` — list, filter by dataset version
- `GET /runs/{id}` — detail with per-case scores
- `GET /runs/{a}/diff/{b}` — server-side comparison

No auth in v0.1 beyond an optional shared token. It is a team tool behind a VPN, not a public API.

### Dashboard

React + Vite + TanStack Query + Recharts. Three screens:

1. Run list with score and delta vs baseline.
2. Score trend over time, split by metric.
3. Case detail with input, expected, actual, judge rationale, and diff against baseline.

---

## Data model

| Table | Key columns | Notes |
|---|---|---|
| `projects` | `id`, `slug`, `name` | |
| `datasets` | `id`, `project_id`, `name` | |
| `dataset_versions` | `id`, `dataset_id`, `version`, `content_hash`, `case_count` | immutable |
| `cases` | `id`, `dataset_version_id`, `case_key`, `input`, `expected`, `context`, `meta` | `case_key` is stable across versions |
| `targets` | `id`, `project_id`, `type`, `config` | |
| `runs` | `id`, `project_id`, `dataset_version_id`, `target_id`, `config_snapshot`, `git_sha`, `status`, `started_at`, `finished_at` | |
| `run_items` | `id`, `run_id`, `case_id`, `output`, `latency_ms`, `cost_usd`, `error` | one row per case |
| `scores` | `id`, `run_item_id`, `metric`, `value`, `detail` | |
| `judges` | `id`, `run_id`, `model`, `rubric_hash`, `temperature`, `samples` | |
| `baselines` | `id`, `project_id`, `run_id` | one baseline per project |

`case_key` + `dataset_version_id` is the join that makes per-case diff possible. Reordering cases between versions must not change the diff.

---

## Run lifecycle

1. Load config; resolve dataset path and verify `content_hash` against the version.
2. Create the run row (`status=running`) — locally as a JSON file, remotely via `--push` later.
3. For each case: call target, capture output/latency/usage, or record a typed error.
4. Compute deterministic metrics.
5. Run the judge over judged cases, hitting cache first.
6. Aggregate, apply the gate, write artifacts.
7. Exit code: `0` pass, `1` gate failed, `2` run error (target unreachable, dataset invalid).

A failed case is not a failed run. Only the gate and infrastructure errors affect the exit code.

---

## Failure handling

| Failure | Behavior |
|---|---|
| Target timeout | Mark item `error`, exclude from score, count toward `error_rate` |
| Target 429 / 5xx | Backoff + jitter, up to 3 retries, then mark item `error` |
| Judge returns unparseable output | One repair attempt, then mark `indeterminate` and exclude from aggregate |
| Process killed mid-run | `--resume` reads the checkpoint and continues from the first incomplete case |
| Dataset content changed | Hash mismatch — refuse to run or compare, exit `2` |
| Judge budget exceeded | Stop judging, mark remaining `indeterminate`, report partial with a loud warning |

`indeterminate` is always reported separately. Silently folding it into the score is how evaluation tools lose trust.

---

## Performance budget

| Scenario | Target |
|---|---|
| 1,000 cases, 8-way concurrency, no judge | < 4 min |
| 1,000 cases with judge, 60% cache hit | < 10 min |
| Single case overhead (excl. target latency) | < 50 ms |
| Dashboard list query p95 | < 300 ms |
| `compare` of two 1,000-case runs | < 2 s |

Concurrency is capped by the target's rate limit, not by our ambition.

---

## Security notes

- Config references environment variables; literal keys in `eval.yml` are rejected.
- The judge sees case input and output — treat datasets as potentially sensitive; never send them to a third-party judge without consent.
- The server is single-tenant by design. Do not expose it publicly without a proxy and auth.

---

## Open questions

- Should the CLI write directly to Postgres when a DSN is present, or always go through the API? (Leaning: API only, to keep one write path.)
- Where does cost estimation live — target adapter or runner? (Leaning: adapter returns usage, runner prices it, so pricing tables stay in one place.)
- Is JUnit XML enough for GitLab/Buildkite, or do we need a second exporter in v0.1? (Probably enough.)
