# Architecture Decision Records

One file per decision that is expensive to reverse. Format: `NNNN-short-title.md`.

Write an ADR when:

- You pick a datastore, a protocol, or a deployment shape.
- You say "no" to something a reasonable person would expect.
- You change a decision recorded here (supersede, never delete).

Template: [0001-record-architecture-decisions.md](0001-record-architecture-decisions.md).

| ID | Title | Status |
|---|---|---|
| 0001 | Record architecture decisions | Accepted |
| 0002 | CLI-first, server-optional | Accepted |
| 0003 | Postgres only, no vector database | Accepted |
| 0004 | Postgres-backed queue instead of a broker | Accepted |
