# 0003 · Postgres only, no vector database

- Status: Accepted
- Date: 2026-11-25

## Context

The obvious storage choice for "AI tooling" is to bolt on a vector database. But
Yardstick stores **scores and metadata about evaluations** — it does not store
embeddings. Retrieval evaluation consumes a list of document ids the target
already retrieved; we never embed anything ourselves.

## Decision

A single Postgres instance is the only datastore. No vector DB, no document store,
no time-series DB in v0.1.

## Consequences

- One dependency to run and back up; `docker compose up` is believable.
- Cross-run comparison is a join, not an application-side merge.
- Aggregations and percentiles use plain SQL.
- If a future feature genuinely needs embeddings (semantic dedupe of datasets,
  say), that is a new ADR with evidence, not a default.

## Alternatives considered

- SQLite — great for the CLI, poor for concurrent writes from the dashboard.
- Vector DB for "similar cases" search — no v0.1 feature requires it; adding it
  now would be speculative complexity.
