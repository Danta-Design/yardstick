# 0001 · Record architecture decisions

- Status: Accepted
- Date: 2026-11-25

## Context

Most evaluation tools are a pile of scripts whose design intent is lost after a
month. Questions like "why Postgres and not SQLite?" and "why not a queue?" get
re-litigated every time someone new joins.

## Decision

Every decision that is expensive to reverse gets a short ADR in `docs/adr/`.
Each record has: context, decision, consequences, and alternatives considered.

## Consequences

- Cheap to write (~15 minutes), high value during interviews and onboarding.
- Superseded decisions stay in history instead of being overwritten.
- Adds one file per significant change; if this becomes friction, the decision
  probably wasn't significant.

## Alternatives considered

- Comments in code — invisible until you read that file.
- A wiki — goes stale and is not versioned with the code.
