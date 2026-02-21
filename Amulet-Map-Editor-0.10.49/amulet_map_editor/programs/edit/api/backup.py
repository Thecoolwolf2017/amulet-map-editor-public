import os
import shutil
import time
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, Tuple

from amulet_map_editor import CONFIG

BACKUP_CONFIG_ID = "backup_settings"
DEFAULT_RETENTION_COUNT = 20
MAX_RETENTION_COUNT = 1_000
MAX_INDEX_ENTRIES = 5_000
_COPY_RETRY_DELAYS_SECONDS = (0.02, 0.05, 0.1)

log = logging.getLogger(__name__)


def _default_backup_root() -> str:
    return os.path.join(os.environ["DATA_DIR"], "backups")


def _normalise_world_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def _normalise_backup_root(path: str) -> str:
    if not path:
        path = _default_backup_root()
    return os.path.abspath(os.path.expanduser(path))


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)


def _iter_files(path: str) -> Iterable[str]:
    for root, _, files in os.walk(path):
        for file in files:
            yield os.path.join(root, file)


def _rel_path_key(path: str) -> str:
    return path.replace("\\", "/").lower()


def _is_expected_locked_file(rel_path: str) -> bool:
    key = _rel_path_key(rel_path)
    return key in {"session.lock", "db/lock"}


def _repair_leveldb_current_if_needed(backup_path: str) -> bool:
    """
    Ensure db/CURRENT exists and points at an existing MANIFEST file.
    Returns True when CURRENT is valid after this call.
    """
    db_path = os.path.join(backup_path, "db")
    if not os.path.isdir(db_path):
        return False

    current_path = os.path.join(db_path, "CURRENT")
    if os.path.isfile(current_path):
        try:
            with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
                current_value = f.read().strip()
            if current_value and os.path.exists(os.path.join(db_path, current_value)):
                return True
        except OSError:
            pass

    manifests = sorted(
        name for name in os.listdir(db_path) if name.startswith("MANIFEST-")
    )
    if not manifests:
        return False

    manifest_name = manifests[-1]
    try:
        with open(current_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{manifest_name}\n")
    except OSError:
        return False

    return os.path.exists(os.path.join(db_path, manifest_name))


def _copy_file_with_retries(source_path: str, destination_path: str) -> Optional[str]:
    """
    Copy a file while tolerating transient sharing violations.
    Returns None on success, otherwise a human-readable skip reason.
    """
    last_error: Optional[BaseException] = None
    for attempt in range(len(_COPY_RETRY_DELAYS_SECONDS) + 1):
        try:
            shutil.copy2(source_path, destination_path)
            return None
        except FileNotFoundError:
            return "Source file disappeared during backup."
        except PermissionError as exc:
            last_error = exc
        except OSError as exc:
            # Common Windows sharing/access failures.
            if getattr(exc, "winerror", None) in (5, 32, 33):
                last_error = exc
            else:
                raise

        if attempt < len(_COPY_RETRY_DELAYS_SECONDS):
            time.sleep(_COPY_RETRY_DELAYS_SECONDS[attempt])

    return (
        f"{type(last_error).__name__}: {last_error}"
        if last_error is not None
        else "Unknown file copy failure."
    )


def _remove_path(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=False)
    elif os.path.exists(path):
        os.remove(path)


def _new_temp_sibling_path(target_path: str, label: str) -> str:
    target_path = os.path.abspath(os.path.normpath(target_path))
    parent = os.path.dirname(target_path)
    os.makedirs(parent, exist_ok=True)
    base_name = os.path.basename(target_path) or "world"
    for _ in range(100):
        token = f"{int(time.time() * 1000)}_{os.getpid()}_{time.time_ns() % 1_000_000}"
        out = os.path.join(parent, f".{base_name}.{label}.{token}")
        if not os.path.exists(out):
            return out
    raise FileExistsError("Unable to allocate unique temp path for staging write.")


def _copy_path(source_path: str, destination_path: str) -> None:
    if os.path.isdir(source_path):
        shutil.copytree(source_path, destination_path)
    elif os.path.isfile(source_path):
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        shutil.copy2(source_path, destination_path)
    else:
        raise FileNotFoundError(f"Source path does not exist: {source_path}")


def _path_within(child_path: str, parent_path: str) -> bool:
    child = os.path.abspath(child_path)
    parent = os.path.abspath(parent_path)
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def _backup_config() -> dict:
    cfg = CONFIG.get(BACKUP_CONFIG_ID, {})
    return cfg if isinstance(cfg, dict) else {}


def _save_backup_config(cfg: dict) -> None:
    CONFIG.put(BACKUP_CONFIG_ID, cfg)


def backups_enabled() -> bool:
    cfg = _backup_config()
    return bool(cfg.get("enabled", True))


def backup_root_dir() -> str:
    cfg = _backup_config()
    return _normalise_backup_root(cfg.get("backup_root", _default_backup_root()))


def backup_retention_count() -> int:
    cfg = _backup_config()
    value = cfg.get("retention_count", DEFAULT_RETENTION_COUNT)
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = DEFAULT_RETENTION_COUNT
    return min(MAX_RETENTION_COUNT, max(1, value))


def set_backup_settings(
    enabled: bool, backup_root: str, retention_count: int
) -> Dict[str, Any]:
    cfg = _backup_config()
    cfg["enabled"] = bool(enabled)
    cfg["backup_root"] = _normalise_backup_root(backup_root)
    try:
        parsed_retention = int(retention_count)
    except (TypeError, ValueError):
        parsed_retention = DEFAULT_RETENTION_COUNT
    cfg["retention_count"] = min(MAX_RETENTION_COUNT, max(1, parsed_retention))
    _save_backup_config(cfg)
    return cfg


def _backup_index() -> List[Dict[str, Any]]:
    cfg = _backup_config()
    raw_index = cfg.get("index", [])
    if not isinstance(raw_index, list):
        return []

    index = []
    for entry in raw_index:
        if not isinstance(entry, dict):
            continue
        world_path = entry.get("world_path")
        backup_path = entry.get("backup_path")
        if not isinstance(world_path, str) or not isinstance(backup_path, str):
            continue
        created_ts = entry.get("created_ts", 0.0)
        try:
            created_ts = float(created_ts)
        except (TypeError, ValueError):
            created_ts = 0.0
        index.append(
            {
                "id": str(entry.get("id", "")),
                "world_path": _normalise_world_path(world_path),
                "backup_path": os.path.abspath(backup_path),
                "reason": str(entry.get("reason", "")),
                "created_ts": created_ts,
                "created_at": str(entry.get("created_at", "")),
            }
        )
    return index


def _save_backup_index(entries: List[Dict[str, Any]]) -> None:
    cfg = _backup_config()
    cfg["index"] = entries[-MAX_INDEX_ENTRIES:]
    _save_backup_config(cfg)


def _cleanup_missing_index_entries(
    entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cleaned = [entry for entry in entries if os.path.exists(entry["backup_path"])]
    if len(cleaned) != len(entries):
        _save_backup_index(cleaned)
    return cleaned


def _apply_retention(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    root = backup_root_dir()
    retention = backup_retention_count()
    kept: List[Dict[str, Any]] = []
    kept_count: Dict[str, int] = {}
    sorted_entries = sorted(
        entries, key=lambda e: e.get("created_ts", 0.0), reverse=True
    )

    for entry in sorted_entries:
        world_path = entry["world_path"]
        kept_for_world = kept_count.get(world_path, 0)
        if kept_for_world < retention:
            kept.append(entry)
            kept_count[world_path] = kept_for_world + 1
            continue

        backup_path = entry["backup_path"]
        if os.path.exists(backup_path) and _path_within(backup_path, root):
            try:
                _remove_path(backup_path)
            except OSError:
                # If cleanup fails, keep the entry so we do not lose track of it.
                kept.append(entry)

    kept.sort(key=lambda e: e.get("created_ts", 0.0))
    return kept


def _record_backup(world_path: str, backup_path: str, reason: str) -> Dict[str, Any]:
    world_path = _normalise_world_path(world_path)
    backup_path = os.path.abspath(backup_path)
    created_ts = time.time()
    entry = {
        "id": f"{int(created_ts * 1000)}_{os.getpid()}_{int(created_ts * 1_000_000) % 10_000}",
        "world_path": world_path,
        "backup_path": backup_path,
        "reason": reason,
        "created_ts": created_ts,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    index = _cleanup_missing_index_entries(_backup_index())
    index.append(entry)
    index = _apply_retention(index)
    _save_backup_index(index)
    return entry


def list_backups(world_path: Optional[str] = None) -> List[Dict[str, Any]]:
    index = _cleanup_missing_index_entries(_backup_index())
    if world_path:
        world_path = _normalise_world_path(world_path)
        index = [entry for entry in index if entry["world_path"] == world_path]
    return sorted(index, key=lambda entry: entry.get("created_ts", 0.0), reverse=True)


def get_latest_backup(world_path: str) -> Optional[Dict[str, Any]]:
    backups = list_backups(world_path)
    return backups[0] if backups else None


def create_staging_copy(source_path: str, label: str = "staging") -> str:
    source_path = os.path.abspath(source_path)
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source path does not exist: {source_path}")
    staging_path = _new_temp_sibling_path(source_path, label)
    _copy_path(source_path, staging_path)
    return staging_path


def commit_staging_path(staging_path: str, target_path: str) -> None:
    staging_path = os.path.abspath(staging_path)
    target_path = os.path.abspath(target_path)
    if not os.path.exists(staging_path):
        raise FileNotFoundError(f"Staging path does not exist: {staging_path}")

    target_exists = os.path.exists(target_path)
    rollback_path = (
        _new_temp_sibling_path(target_path, "rollback") if target_exists else ""
    )

    try:
        if target_exists:
            os.replace(target_path, rollback_path)
        os.replace(staging_path, target_path)
    except BaseException:
        if os.path.exists(staging_path):
            try:
                _remove_path(staging_path)
            except OSError:
                pass
        if target_exists and os.path.exists(rollback_path):
            if os.path.exists(target_path):
                try:
                    _remove_path(target_path)
                except OSError:
                    pass
            os.replace(rollback_path, target_path)
        raise
    else:
        if target_exists and os.path.exists(rollback_path):
            _remove_path(rollback_path)


def run_crash_safe_write(
    target_path: str, writer: Callable[[str], Any], label: str = "write"
) -> Any:
    if not callable(writer):
        raise TypeError("writer must be callable")

    target_path = os.path.abspath(target_path)
    staging_path = _new_temp_sibling_path(target_path, label)

    if os.path.exists(target_path):
        _copy_path(target_path, staging_path)

    try:
        result = writer(staging_path)
        if not os.path.exists(staging_path):
            raise FileNotFoundError(
                "Crash-safe writer did not create a staging path to commit."
            )
        commit_staging_path(staging_path, target_path)
        return result
    except BaseException:
        if os.path.exists(staging_path):
            try:
                _remove_path(staging_path)
            except OSError:
                pass
        raise


def restore_backup(backup_path: str, world_path: str) -> str:
    backup_path = os.path.abspath(backup_path)
    world_path = os.path.abspath(world_path)
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup does not exist: {backup_path}")

    staging_path = create_staging_copy(backup_path, "restore")
    commit_staging_path(staging_path, world_path)
    return world_path


def restore_latest_backup(world_path: str) -> Dict[str, Any]:
    latest = get_latest_backup(world_path)
    if latest is None:
        raise FileNotFoundError("No backup was found for this world.")
    restore_backup(latest["backup_path"], world_path)
    return latest


def iter_backup(
    world_path: str, reason: str
) -> Generator[Tuple[float, str], None, str]:
    """
    Create a backup of a world directory or file.
    Yields (progress, message) and returns backup path.
    """
    if not backups_enabled():
        return ""

    world_path = os.path.abspath(world_path)
    if not os.path.exists(world_path):
        return ""

    root = backup_root_dir()
    os.makedirs(root, exist_ok=True)

    base_name = _safe_name(os.path.basename(os.path.normpath(world_path)) or "world")
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = os.path.join(root, f"{base_name}_{timestamp}")

    if os.path.isfile(world_path):
        target = backup_path + os.path.splitext(world_path)[1]
        yield 0.0, f"Backing up {base_name}"
        shutil.copy2(world_path, target)
        _record_backup(world_path, target, reason)
        yield 1.0, "Backup complete"
        return target

    files = list(_iter_files(world_path))
    total = max(len(files), 1)
    copied = 0
    skipped: List[Tuple[str, str]] = []
    yield 0.0, f"Backing up {base_name} ({reason})"

    for idx, src in enumerate(files, start=1):
        rel = os.path.relpath(src, world_path)
        dest = os.path.join(backup_path, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        skip_reason = _copy_file_with_retries(src, dest)
        if skip_reason is not None:
            skipped.append((rel, skip_reason))
            yield idx / total, f"Backing up {base_name} ({idx}/{total})"
            continue

        copied += 1
        yield idx / total, f"Backing up {base_name} ({idx}/{total})"

    if copied == 0:
        if os.path.exists(backup_path):
            _remove_path(backup_path)
        log.warning(
            "Backup skipped because no files were readable. world=%s reason=%s",
            world_path,
            reason,
        )
        yield 1.0, "Backup skipped (all files were locked/unreadable)"
        return ""

    repaired_current = False
    if any(_rel_path_key(rel) == "db/current" for rel, _ in skipped):
        repaired_current = _repair_leveldb_current_if_needed(backup_path)
        if repaired_current:
            skipped = [
                (rel, reason)
                for rel, reason in skipped
                if _rel_path_key(rel) != "db/current"
            ]
            log.debug(
                "Repaired skipped LevelDB CURRENT file in backup: %s", backup_path
            )

    expected_locked = [(rel, reason) for rel, reason in skipped if _is_expected_locked_file(rel)]
    skipped = [(rel, reason) for rel, reason in skipped if not _is_expected_locked_file(rel)]

    for rel, skip_reason in expected_locked:
        log.debug(
            "Skipped expected locked file during backup. world=%s file=%s reason=%s",
            world_path,
            rel,
            skip_reason,
        )

    if skipped:
        for rel, skip_reason in skipped:
            log.warning(
                "Skipped backup file due to copy error. world=%s file=%s reason=%s",
                world_path,
                rel,
                skip_reason,
            )
        warning_path = os.path.join(backup_path, ".amulet_backup_warnings.txt")
        with open(warning_path, "w", encoding="utf-8") as warning_file:
            warning_file.write("Some files were skipped during backup:\n")
            for rel, skip_reason in skipped:
                warning_file.write(f"- {rel}: {skip_reason}\n")
            if repaired_current:
                warning_file.write("- db/CURRENT: auto-repaired from MANIFEST file(s)\n")

    _record_backup(world_path, backup_path, reason)
    if skipped:
        yield 1.0, f"Backup complete (skipped {len(skipped)} locked/unreadable files)"
    else:
        yield 1.0, "Backup complete"
    return backup_path
