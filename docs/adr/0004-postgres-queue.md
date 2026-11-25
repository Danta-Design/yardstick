# 0004 · Postgres-backed queue instead of a broker

- Status: Accepted
- Date: 2026-11-25

## Context

A run can take minutes and thousands of target calls. The instinct is to reach for
Kafka, RabbitMQ, or Redis. But a single run is ~1,000 cases at 8-way concurrency;
the whole workload is one writer and a handful of workers.

## Decision

Use a Postgres table with `FOR UPDATE SKIP LOCKED` as the job queue. No broker.

## Consequences

- One less service to deploy, monitor, and explain.
- Throughput ceiling is roughly tens of runs per minute — far above any realistic
  usage of this tool.
- Retries, visibility timeouts, and dead-letter handling must be implemented
  explicitly rather than inherited from a broker.
- The CLI path does not use the queue at all; it runs in-process. The queue only
  exists for server-side scheduled runs.

## Alternatives considered

- Redis + RQ/Celery — a second datastore for a feature that may not ship in v0.1.
- Kafka — operationally absurd at this scale.

## Revisit trigger

Sustained > 100 concurrent runs, or a need for cross-region workers.
