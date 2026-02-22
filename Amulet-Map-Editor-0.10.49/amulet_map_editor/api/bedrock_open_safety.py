from __future__ import annotations

import os
import sys
from typing import List


def _set_writable(path: str, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _normalise_current_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if value.startswith("./"):
        value = value[2:]
    return value.replace("\\", "/")


def _repair_leveldb_current(world_path: str) -> bool:
    db_path = os.path.join(world_path, "db")
    if not os.path.isdir(db_path):
        return False

    try:
        entries = os.listdir(db_path)
    except OSError:
        return False

    manifest_lookup = {
        name.upper(): name for name in entries if name.upper().startswith("MANIFEST-")
    }
    if not manifest_lookup:
        return False

    current_path = os.path.join(db_path, "CURRENT")
    _set_writable(current_path, 0o666)

    current_manifest = ""
    if os.path.isfile(current_path):
        try:
            with open(current_path, "r", encoding="utf-8", errors="ignore") as current_file:
                current_manifest = _normalise_current_value(current_file.read())
        except OSError:
            current_manifest = ""

    if current_manifest:
        if os.path.exists(os.path.join(db_path, current_manifest)):
            return False
        normalised = manifest_lookup.get(current_manifest.upper(), "")
        if normalised and os.path.exists(os.path.join(db_path, normalised)):
            try:
                with open(current_path, "w", encoding="utf-8", newline="\n") as current_file:
                    current_file.write(f"{normalised}\n")
                return True
            except OSError:
                return False

    manifest_name = sorted(manifest_lookup.values())[-1]
    try:
        with open(current_path, "w", encoding="utf-8", newline="\n") as current_file:
            current_file.write(f"{manifest_name}\n")
    except OSError:
        return False
    return True


def _clear_stale_lock(world_path: str) -> bool:
    lock_path = os.path.join(world_path, "db", "LOCK")
    if not os.path.isfile(lock_path):
        return False
    _set_writable(lock_path, 0o666)
    try:
        os.remove(lock_path)
        return True
    except OSError:
        return False


def _normalise_db_file_permissions(world_path: str) -> bool:
    if sys.platform != "win32":
        return False
    db_path = os.path.join(world_path, "db")
    if not os.path.isdir(db_path):
        return False

    changed = False
    for root, dirs, files in os.walk(db_path):
        _set_writable(root, 0o777)
        for directory in dirs:
            _set_writable(os.path.join(root, directory), 0o777)
        for file_name in files:
            _set_writable(os.path.join(root, file_name), 0o666)
        changed = True
    return changed


def is_probably_bedrock_world(path: str) -> bool:
    return (
        os.path.isdir(path)
        and os.path.isdir(os.path.join(path, "db"))
        and os.path.isfile(os.path.join(path, "level.dat"))
    )


def prepare_bedrock_world_for_open(path: str) -> List[str]:
    """
    Apply defensive, in-place repairs for Bedrock worlds before opening.
    Returns a list of actions that were applied.
    """
    world_path = os.path.abspath(path)
    if not is_probably_bedrock_world(world_path):
        return []

    actions: List[str] = []
    if _normalise_db_file_permissions(world_path):
        actions.append("normalised_db_permissions")
    if _clear_stale_lock(world_path):
        actions.append("removed_db_lock")
    if _repair_leveldb_current(world_path):
        actions.append("repaired_db_current")
    return actions
