# 0002 · CLI-first, server-optional

- Status: Accepted
- Date: 2026-11-25

## Context

Evaluation tools tend to become platforms: you must deploy a service, provision a
database, and hold an account before you can evaluate anything. That friction
kills adoption in exactly the moment the tool is most valuable — a 30-second
check before merging a prompt change.

## Decision

The CLI is the product. It runs standalone, writes artifacts to disk, and needs no
network beyond the target under test. The server is an optional layer that
persists runs and renders dashboards; nothing in CI depends on it.

## Consequences

- CI needs no infrastructure, credentials, or uptime guarantee from us.
- New users get value in one command.
- History, comparison across a team, and dashboards require the server — a
  deliberate upsell, not a gate.
- Two code paths to test: standalone and pushed. Mitigated by making the server
  consume the same `report.json` the CLI produces.
- Cost control is simpler: no hosted compute to pay for.

## Alternatives considered

- Server-only SaaS — fastest to monetize, slowest to adopt.
- Library-only — no opinions, no dashboard, users rebuild reporting themselves.
