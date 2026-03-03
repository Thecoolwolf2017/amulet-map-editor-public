# Workspace Layout and Cleanup

This repository intentionally keeps source under `Amulet-Map-Editor-0.10.49/`.

## Canonical Paths

- Source code: `amulet_map_editor/`
- Tests: `tests/`
- Docs: `docs/`
- Remote/release repo record: `docs/repository-remotes.md`
- Build spec: `Amulet.spec`
- Runtime executable: `dist/Amulet/amulet_app.exe`
- Release artifacts: `dist/Amulet-v*-Windows-x64.zip`, `dist/SHA256SUMS.txt`

## Disposable Paths

The following are generated and safe to delete when cleaning up local workspace state:

- `build/`
- `*.egg-info/`
- temporary virtual envs such as `.venv_rc_*`
- transient logs such as `test_run.log`

Keep your active environment `.venv/` unless you explicitly want to recreate it.

## Recommended Cleanup Command (Windows)

From the repository root:

```powershell
cmd /c "rmdir /s /q Amulet-Map-Editor-0.10.49\build & rmdir /s /q Amulet-Map-Editor-0.10.49\*.egg-info & del /f /q Amulet-Map-Editor-0.10.49\test_run.log"
```

Adjust paths as needed if you intentionally keep additional local artifacts.
