# Public Launch Checklist

Goal: ship a public release of `Amulet Map Editor` with consistent positioning as `World Migration & Conversion`.

## Product Positioning
- Keep product name as `Amulet Map Editor`.
- Use subtitle `World Migration & Conversion` in release notes, README, app title, and social copy.
- Keep package identifiers and data directories unchanged (`AmuletMapEditor`) for compatibility.

## Release Quality
- Run unit tests:
  - `python -m pytest tests/test_export_remap.py tests/test_backup_workflows.py`
  - `python -m pytest tests/test_lasso_selection.py tests/test_edit_workflows.py`
- Run smoke test:
  - `python scripts/release_smoke_test.py`
- Manual checks:
  - open Bedrock and Java worlds,
  - lasso selection and live preview,
  - export remap preview/wizard,
  - in-world migration with forced safety backup,
  - save/undo/redo after migration.

## Security and Trust
- Publish SHA256 checksums with artifacts.
- Sign binaries when signing secrets are available.
- Keep crash and backup logs enabled for support diagnostics.

## Public Docs and Support
- Update README and release notes with migration/remap workflows.
- Publish a short "first-run safety" note: always keep backups.
- Link issue tracker and Discord in release announcement.

## Go/No-Go
- No failing tests.
- No known data-loss bug in migration/export/save paths.
- Built executable hash recorded and attached to release.
