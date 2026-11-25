# Contributing to Yardstick

Thanks for taking a look. This project is built in public and reviewed in small steps — please keep PRs small enough to review in one sitting.

## Before you start

- Bug or unclear behavior → open an issue with the **Bug** template.
- New metric, target, or integration → open an issue first so we can agree on the interface before you write it.
- Anything in `docs/issues.md` marked `good first issue` is intentionally scoped.

## Setup

> Placeholder until the first package lands. Update this section in the same PR that adds `packages/cli`.

```bash
git clone https://github.com/Danta-Design/yardstick.git
cd yardstick
# python -m venv .venv && source .venv/bin/activate
# pip install -e ".[dev]"
```

## Branches and commits

- Branch from `main`: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, `chore/<slug>`.
- Use Conventional Commits: `feat(cli): add junit export`, `fix(judge): clamp score to rubric range`.
- One logical change per commit. Do not batch unrelated fixes.

## Pull requests

Before opening a PR, make sure:

- [ ] `main` is merged in (rebase, not merge commits, if you can)
- [ ] New behavior has a test or a documented reason it cannot
- [ ] `CHANGELOG.md` has an entry under `Unreleased`
- [ ] Docs updated if the public interface changed
- [ ] No secrets, API keys, or `.env` files in the diff
- [ ] CI is green

The PR template asks for the same things, so this is mostly a reminder.

## What gets rejected

- New runtime dependencies without a short justification in the PR description
- Abstractions added "for future flexibility" with no current caller
- Feature work that expands v0.1 scope (open an issue and let it sit in the backlog instead)
- Reformatting unrelated files

## Testing

- Unit tests live next to the code.
- Anything touching scoring must include a fixture with a known expected value.
- Judge calls in tests are mocked. Never make a paid API call in CI.

## Releasing

Maintainers only. Tag `vX.Y.Z`, update `CHANGELOG.md`, publish, then bump `Unreleased`.

## Code of conduct

Be direct about code, generous about people.
