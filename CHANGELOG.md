# Changelog

## [0.2.16] - 2026-05-19

- fix(siyuan): retry delete_doc verify probe to avoid index-race false positive (CDI-1092 follow-up)


## [0.2.14] - 2026-05-13

- fix(docker): replace broken HEALTHCHECK one-liner with healthcheck.py script


## [0.2.13] - 2026-05-13

- fix(health): cap upstream probe at 2s, accept 503 in Docker HEALTHCHECK


## [0.2.11] - 2026-05-08

- fix(release): sync __version__ to 0.2.9, harden CI version bump, fix README health path


## [0.2.10] - 2026-05-07

- chore(openspec): archive 4 completed changes, sync delta specs to main (#15)


## [0.2.9] - 2026-05-07

- fix(config): resolve audit findings — env mismatch, zombie vars, settings purity, delete idempotency (#14)


## [0.2.8] - 2026-05-07

- chore(maintenance): sync __version__, fix API key config path, release CI fix, lint cleanup (#13)


## [0.2.6] - 2026-04-30

- feat(reliability): correlation IDs, write idempotency, diag endpoint, README rewrite (#10)


## [0.2.5] - 2026-04-20

- ci(deps): enable Dependabot weekly updates


## [0.2.4] - 2026-04-18

- chore: sync __init__.__version__ with pyproject (0.2.3)


## [0.2.3] - 2026-04-18

- feat(reliability): FastMCP 3.2.4, stateless_http, /health endpoint, fail-fast auth


## [0.2.2] - 2026-04-09

- fix: lowercase Docker image tags in release CI


## [0.2.0] - 2026-04-09

### Changed
- Bumped FastMCP dependency to >=3.2.2
- Clarified get_block vs get_block_attrs usage in docstrings

### Added
- Automated version bump and release CI via GitHub Actions
- CHANGELOG.md for tracking changes
