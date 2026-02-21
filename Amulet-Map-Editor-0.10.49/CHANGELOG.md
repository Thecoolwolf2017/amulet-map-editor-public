# Changelog

## v2.0.0-rc1 (2026-02-21)

### Added
- Save result UX after successful saves with world path, backup status, and backup path.
- Release smoke-test command: `python scripts/release_smoke_test.py`.
- Regression tests for locked backup files (`db/CURRENT`, `db/LOCK`, `session.lock`).

### Fixed
- Bedrock world open crash on Windows caused by native module import ordering (`leveldb` now preloaded before `wx`).
- Backup workflow resilience for locked files during save; backups now continue safely.
- Auto-repair for skipped Bedrock `db/CURRENT` by reconstructing it from copied `MANIFEST-*` files.

### Changed
- Reduced log spam in normal runs:
  - Invalid-world scan messages downgraded from `INFO` to `DEBUG`.
  - Expected lock-file skip messages (`session.lock`, `db/LOCK`) downgraded from `WARNING` to `DEBUG`.
  - Bedrock `db/CURRENT` auto-repair message downgraded from `INFO` to `DEBUG`.
