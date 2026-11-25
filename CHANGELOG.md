# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository skeleton: architecture, metrics, ADRs, backlog, issue templates.
- CLI `run` command with YAML config validation and exit codes (0 pass, 1 gate, 2 error).
- Dataset loading for JSONL and CSV, with duplicate-key, empty-input, and format validation.
- Content-addressed dataset versions: the SHA-256 of normalized cases, snapshotted into every report.
- Targets: `http` (JSON body templating, dotted response extraction, env-based headers)
  and `python` (sync or async callable).
- Deterministic metrics: `exact_match` and `token_f1`, with documented normalization.
- Bounded-concurrency runner with retries, per-case latency, and error isolation.
- Gate checks (`min_score`, `max_error_rate`) that drive the process exit code.
- JSON run reports under `runs/<run_id>/report.json`, plus a terminal summary.
- `examples/datasets/faq-50.jsonl`: 50 cases against a fictional product FAQ.
- 27 tests, including end-to-end runs against a fake target with no network.

### Changed

### Fixed

## [0.0.1] - 2026-11-25

### Added

- Initial public scaffold.
