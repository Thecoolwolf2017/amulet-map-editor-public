# Changelog

## v2.0.0-rc3 (2026-03-03)

### Added
- Top-down lasso selection mode with a freehand polygon workflow in the Select tool.
- Live lasso selection preview while dragging, including additive lasso behavior with `Ctrl`.
- Export remap table support for custom namespaces/blocks via `custom_block_export_remap.json`.
- Automatic pre-export namespace discovery that appends missing custom namespaces to the local remap table.
- Export remap preview report in the export UI (`Preview Remap`) with chunk/block impact totals.
- Export remap wizard in the export UI for editing custom block remaps without leaving the app.
- Lasso selection unit tests (`tests/test_lasso_selection.py`).

### Fixed
- Local log spam reduction for repeated PyMCTranslate custom block translation warnings.
- World open hardening for Bedrock and `.mcworld` workflows:
  - better preflight probe stability on Windows,
  - safer retry behavior with sanitized child environment,
  - clearer handling for invalid `.mcworld` archives.
- Rendering and UX fixes from the RC2 burn-in window:
  - Bedrock fence connection synthesis for rendering,
  - foliage tint sentinel normalization,
  - responsive world-select behavior after probe failures.

### Changed
- Export operations now apply remap rules before chunk commit for:
  - Construction,
  - Schematic (legacy),
  - Sponge Schematic,
  - Bedrock `.mcstructure`.
- Export dialogs now show a remap confirmation summary when custom blocks are detected before writing files.
- Custom fork behavior now suppresses upstream update popups by default.
- Build pipeline supports fallback self-signed executable signing when signing secrets are unavailable.

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
