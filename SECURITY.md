# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private
vulnerability reporting (Security → Report a vulnerability) or email the
maintainer listed in `README.md`.

Include reproduction steps and the affected version. Expect an acknowledgement
within 72 hours.

## Secrets

This project never requires credentials in the repository. Evaluation configs
reference environment variables, never literal keys.

If you find a committed secret:

1. Rotate it immediately — assume it is public.
2. Report it via the private channel above.
3. Do not open a PR that only removes the string; history still contains it.

## Scope

In scope: the CLI, the optional server, the GitHub Action, and the published
container images.

Out of scope: third-party model providers, and any prompt or dataset content
you choose to evaluate.
