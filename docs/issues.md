# Backlog

Source of truth for scope. Anything not here is not in v0.1.

Estimates are hours at ~20h/week. Total ≈ 125h against a 120h budget — the
overage is the buffer, do not add to it.

## Milestones

| Milestone | Week | Epics | Exit criterion |
|---|---|---|---|
| M1 Skeleton | W1–W2 | E1, E2 | End-to-end run on the bundled dataset |
| M2 Judge | W3 | E3 | κ ≥ 0.7 on calibration set |
| M3 Platform | W4 | E4, E5 | `docker compose up` serves the dashboard |
| M4 CI | W5 | E6 | A real PR is gated and commented |
| M5 Release | W6 | E7, E8 | Stranger runs it in 5 minutes; v0.1.0 tagged |

## Definition of done

A task is done when: code merged, test added, docs updated if the interface
changed, `CHANGELOG.md` entry written, and CI green.

---

## E1 · Datasets and versions (12h)

- **EV-01** Import JSONL/CSV with field mapping — 4h
  _Accept: a messy CSV with 3 aliased fields imports and round-trips to JSONL._
- **EV-02** Immutable dataset versions + tag — 3h
  _Accept: re-importing identical content yields the same hash; changed content yields a new version._
- **EV-03** Bundle two seed datasets — 3h
  _Accept: `examples/datasets/faq-50.jsonl` and `rag-100.jsonl` load with no config._
- **EV-04** Dataset validation — 2h
  _Accept: duplicate `case_key`, empty input, and oversized field each produce a specific error._

## E2 · Runner and targets (22h)

- **EV-05** Target interface + registry — 3h
  _Accept: a new adapter can be added without touching the runner._
- **EV-06** HTTP target (OpenAI-compatible) — 4h
- **EV-07** CLI target — 3h
- **EV-08** Python callable target — 3h
  _Accept (06–08): each passes the shared adapter conformance test._
- **EV-09** Concurrency, timeout, retry, rate limit — 6h
  _Accept: 429s are retried with backoff; a hanging target times out at the configured limit._
- **EV-10** Checkpoint and `--resume` — 3h
  _Accept: killing the process at 50% and resuming produces the same report as an uninterrupted run._

## E3 · Metrics and judge (28h)

- **EV-11** Exact match + token F1 — 4h
- **EV-12** Retrieval metrics: recall@k, precision@k, MRR, nDCG@k — 5h
  _Accept: golden fixtures taken from published examples._
- **EV-13** Judge core: rubric loading, call, parse, repair — 6h
- **EV-14** Sampling + dual-model crossover + `needs_review` — 4h
- **EV-15** Judge cache — 3h
  _Accept: second identical run makes zero paid calls._
- **EV-16** Calibration toolkit: 100 labeled cases, κ, per-criterion report — 6h
  _Accept: `yardstick calibrate` prints κ and the failing criteria; κ ≥ 0.7 documented in README._

## E4 · Storage and comparison (14h)

- **EV-17** Local run persistence + `--push` — 4h
- **EV-18** `compare` with Δ, bootstrap CI, "no significant change" — 5h
- **EV-19** Per-case flip list (pass→fail / fail→pass) — 3h
  _Accept: a reordered dataset produces an identical flip list._
- **EV-20** JUnit XML export — 2h

## E5 · Dashboard (18h)

- **EV-21** Run list with filters — 3h
- **EV-22** Score trend by metric — 4h
- **EV-23** Case detail: input, expected, actual, judge rationale, diff vs baseline — 6h
- **EV-24** Responsive layout, works at 375px — 5h

## E6 · CI integration (12h)

- **EV-25** GitHub Action wrapper — 4h
- **EV-26** Gate config + non-zero exit — 3h
- **EV-27** PR comment renderer (table + link) — 4h
- **EV-28** `skip-eval` override label — 1h
  _Accept (E6): a PR that lowers the score is blocked, commented, and can be overridden visibly._

## E7 · Engineering (12h)

- **EV-29** Unit tests, ≥ 80% on scoring and config — 4h
- **EV-30** CI matrix: lint, test, build — 3h
- **EV-31** `docker compose` for server + db + web — 3h
- **EV-32** pre-commit + gitleaks — 2h

## E8 · Examples and outreach (8h)

- **EV-33** `examples/rag-demo` — a deliberately small RAG service to evaluate — 4h
- **EV-34** Blog post: "why evaluation belongs in CI" — 2h
- **EV-35** Onboard 3 external users, log feedback in `docs/feedback.md` — 2h

---

## Explicitly out of scope

- Annotation UI, multi-tenant auth, billing, online A/B, prompt editing UI.
- Revisit after v0.3, and only with a user asking for it.
