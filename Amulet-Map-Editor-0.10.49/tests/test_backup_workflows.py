import os
import tempfile
import unittest
from unittest import mock
import importlib.util
import types
from pathlib import Path
import sys


class _MemoryConfig:
    def __init__(self):
        self._store = {}

    def get(self, identifier, default=None):
        return self._store.get(identifier, default)

    def put(self, identifier, data):
        self._store[identifier] = data


def _load_backup_module():
    backup_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "programs"
        / "edit"
        / "api"
        / "backup.py"
    )
    spec = importlib.util.spec_from_file_location("test_backup_module", backup_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load backup module spec from {backup_path}")

    module = importlib.util.module_from_spec(spec)

    fake_root_module = types.ModuleType("amulet_map_editor")
    fake_root_module.CONFIG = _MemoryConfig()

    old_root_module = sys.modules.get("amulet_map_editor")
    sys.modules["amulet_map_editor"] = fake_root_module
    try:
        spec.loader.exec_module(module)
    finally:
        if old_root_module is None:
            del sys.modules["amulet_map_editor"]
        else:
            sys.modules["amulet_map_editor"] = old_root_module
    return module


try:
    backup_module = _load_backup_module()
except Exception as exc:  # pragma: no cover - dependency guard
    backup_module = None
    _BACKUP_IMPORT_ERROR = exc
else:
    _BACKUP_IMPORT_ERROR = None


def _exhaust(generator):
    while True:
        try:
            next(generator)
        except StopIteration as exc:
            return exc.value


class BackupWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _BACKUP_IMPORT_ERROR is not None:
            raise unittest.SkipTest(
                f"backup module dependencies unavailable: {_BACKUP_IMPORT_ERROR}"
            )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

        self._old_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = self._tmp.name

        self._old_config = backup_module.CONFIG
        backup_module.CONFIG = _MemoryConfig()
        self.addCleanup(self._restore_state)

    def _restore_state(self):
        backup_module.CONFIG = self._old_config
        if self._old_data_dir is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = self._old_data_dir

    def _make_world(self, world_name: str, file_name: str, content: str) -> str:
        world_path = os.path.join(self._tmp.name, world_name)
        file_path = os.path.join(world_path, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return world_path

    def _read_world_file(self, world_path: str, file_name: str) -> str:
        with open(os.path.join(world_path, file_name), encoding="utf-8") as f:
            return f.read()

    def test_backup_index_and_retention(self):
        backup_root = os.path.join(self._tmp.name, "backups")
        backup_module.set_backup_settings(
            enabled=True,
            backup_root=backup_root,
            retention_count=2,
        )

        world_path = self._make_world("java_world", "level.dat", "version_1")
        for idx in range(1, 4):
            with open(
                os.path.join(world_path, "level.dat"), "w", encoding="utf-8"
            ) as f:
                f.write(f"version_{idx}")
            _exhaust(backup_module.iter_backup(world_path, f"backup_{idx}"))

        backups = backup_module.list_backups(world_path)
        self.assertEqual(len(backups), 2)
        self.assertTrue(all(os.path.exists(entry["backup_path"]) for entry in backups))

    def test_restore_latest_backup_java_and_bedrock_style_worlds(self):
        backup_module.set_backup_settings(
            enabled=True,
            backup_root=os.path.join(self._tmp.name, "backups"),
            retention_count=5,
        )

        java_world = self._make_world("java_world", "region/r.0.0.mca", "java_original")
        bedrock_world = self._make_world(
            "bedrock_world", "db/CURRENT", "bedrock_original"
        )

        java_backup_path = _exhaust(backup_module.iter_backup(java_world, "java_test"))
        bedrock_backup_path = _exhaust(
            backup_module.iter_backup(bedrock_world, "bedrock_test")
        )

        with open(
            os.path.join(java_world, "region/r.0.0.mca"), "w", encoding="utf-8"
        ) as f:
            f.write("java_modified")
        with open(
            os.path.join(bedrock_world, "db/CURRENT"), "w", encoding="utf-8"
        ) as f:
            f.write("bedrock_modified")

        java_restore = backup_module.restore_latest_backup(java_world)
        bedrock_restore = backup_module.restore_latest_backup(bedrock_world)

        self.assertEqual(
            self._read_world_file(java_world, "region/r.0.0.mca"), "java_original"
        )
        self.assertEqual(
            self._read_world_file(bedrock_world, "db/CURRENT"), "bedrock_original"
        )
        self.assertEqual(java_restore["backup_path"], java_backup_path)
        self.assertEqual(bedrock_restore["backup_path"], bedrock_backup_path)

    def test_crash_safe_write_failure_does_not_corrupt_existing_world(self):
        output_world = self._make_world("output_world", "data/chunk.dat", "stable")
        source_world = self._make_world("source_world", "data/chunk.dat", "source")

        def failing_writer(staging_path: str):
            with open(
                os.path.join(staging_path, "data/chunk.dat"), "w", encoding="utf-8"
            ) as f:
                f.write("corrupted")
            raise RuntimeError("forced failure")

        with self.assertRaises(RuntimeError):
            backup_module.run_crash_safe_write(output_world, failing_writer, "test")

        self.assertEqual(
            self._read_world_file(output_world, "data/chunk.dat"),
            "stable",
        )
        self.assertEqual(
            self._read_world_file(source_world, "data/chunk.dat"),
            "source",
        )

        def successful_writer(staging_path: str):
            with open(
                os.path.join(staging_path, "data/chunk.dat"), "w", encoding="utf-8"
            ) as f:
                f.write("updated")

        backup_module.run_crash_safe_write(output_world, successful_writer, "test")
        self.assertEqual(
            self._read_world_file(output_world, "data/chunk.dat"),
            "updated",
        )

    def test_backup_skips_locked_files_instead_of_failing(self):
        backup_module.set_backup_settings(
            enabled=True,
            backup_root=os.path.join(self._tmp.name, "backups"),
            retention_count=5,
        )

        world_path = self._make_world("bedrock_world", "db/CURRENT", "current")
        lock_file = os.path.join(world_path, "db/LOCK")
        with open(lock_file, "w", encoding="utf-8") as f:
            f.write("lock")

        original_copy2 = backup_module.shutil.copy2

        def _copy2_with_locked_file(src, dst, *args, **kwargs):
            norm_src = os.path.normcase(os.path.normpath(src))
            norm_lock = os.path.normcase(os.path.normpath(lock_file))
            if norm_src == norm_lock:
                raise PermissionError(13, "Permission denied")
            return original_copy2(src, dst, *args, **kwargs)

        with mock.patch.object(
            backup_module.shutil, "copy2", side_effect=_copy2_with_locked_file
        ):
            backup_path = _exhaust(backup_module.iter_backup(world_path, "pre-save"))

        self.assertTrue(backup_path)
        self.assertTrue(os.path.exists(os.path.join(backup_path, "db/CURRENT")))
        self.assertFalse(os.path.exists(os.path.join(backup_path, "db/LOCK")))
        self.assertFalse(
            os.path.exists(os.path.join(backup_path, ".amulet_backup_warnings.txt"))
        )
        self.assertEqual(len(backup_module.list_backups(world_path)), 1)

    def test_backup_ignores_locked_java_session_lock(self):
        backup_module.set_backup_settings(
            enabled=True,
            backup_root=os.path.join(self._tmp.name, "backups"),
            retention_count=5,
        )

        world_path = self._make_world("java_world_lock", "level.dat", "current")
        session_lock = os.path.join(world_path, "session.lock")
        with open(session_lock, "w", encoding="utf-8") as f:
            f.write("lock")

        original_copy2 = backup_module.shutil.copy2

        def _copy2_with_locked_session(src, dst, *args, **kwargs):
            norm_src = os.path.normcase(os.path.normpath(src))
            norm_lock = os.path.normcase(os.path.normpath(session_lock))
            if norm_src == norm_lock:
                raise PermissionError(13, "Permission denied")
            return original_copy2(src, dst, *args, **kwargs)

        with mock.patch.object(
            backup_module.shutil, "copy2", side_effect=_copy2_with_locked_session
        ):
            backup_path = _exhaust(backup_module.iter_backup(world_path, "pre-save"))

        self.assertTrue(backup_path)
        self.assertTrue(os.path.exists(os.path.join(backup_path, "level.dat")))
        self.assertFalse(os.path.exists(os.path.join(backup_path, "session.lock")))
        self.assertFalse(
            os.path.exists(os.path.join(backup_path, ".amulet_backup_warnings.txt"))
        )

    def test_backup_repairs_locked_leveldb_current(self):
        backup_module.set_backup_settings(
            enabled=True,
            backup_root=os.path.join(self._tmp.name, "backups"),
            retention_count=5,
        )

        world_path = self._make_world("bedrock_world_current", "db/CURRENT", "MANIFEST-000001\n")
        manifest_path = os.path.join(world_path, "db/MANIFEST-000001")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("manifest-data")

        locked_current = os.path.join(world_path, "db/CURRENT")
        original_copy2 = backup_module.shutil.copy2

        def _copy2_with_locked_current(src, dst, *args, **kwargs):
            norm_src = os.path.normcase(os.path.normpath(src))
            norm_current = os.path.normcase(os.path.normpath(locked_current))
            if norm_src == norm_current:
                raise PermissionError(13, "Permission denied")
            return original_copy2(src, dst, *args, **kwargs)

        with mock.patch.object(
            backup_module.shutil, "copy2", side_effect=_copy2_with_locked_current
        ):
            backup_path = _exhaust(backup_module.iter_backup(world_path, "pre-save"))

        self.assertTrue(backup_path)
        repaired_current = os.path.join(backup_path, "db/CURRENT")
        self.assertTrue(os.path.exists(repaired_current))
        with open(repaired_current, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "MANIFEST-000001\n")
        self.assertFalse(
            os.path.exists(os.path.join(backup_path, ".amulet_backup_warnings.txt"))
        )

    def test_backup_uses_copyfile_fallback_for_leveldb_current(self):
        backup_module.set_backup_settings(
            enabled=True,
            backup_root=os.path.join(self._tmp.name, "backups"),
            retention_count=5,
        )

        world_path = self._make_world(
            "bedrock_world_copyfile",
            "db/CURRENT",
            "MANIFEST-000001\n",
        )
        with open(
            os.path.join(world_path, "db/MANIFEST-000001"), "w", encoding="utf-8"
        ) as f:
            f.write("manifest-data")

        current_path = os.path.join(world_path, "db/CURRENT")
        original_copy2 = backup_module.shutil.copy2

        def _copy2_with_permission_denied(src, dst, *args, **kwargs):
            norm_src = os.path.normcase(os.path.normpath(src))
            norm_current = os.path.normcase(os.path.normpath(current_path))
            if norm_src == norm_current:
                raise PermissionError(13, "Permission denied")
            return original_copy2(src, dst, *args, **kwargs)

        with mock.patch.object(
            backup_module.shutil, "copy2", side_effect=_copy2_with_permission_denied
        ):
            backup_path = _exhaust(backup_module.iter_backup(world_path, "pre-save"))

        self.assertTrue(backup_path)
        copied_current = os.path.join(backup_path, "db/CURRENT")
        self.assertTrue(os.path.exists(copied_current))
        with open(copied_current, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "MANIFEST-000001\n")
        self.assertFalse(
            os.path.exists(os.path.join(backup_path, ".amulet_backup_warnings.txt"))
        )

    def test_backup_repairs_leveldb_current_with_lowercase_manifest_name(self):
        backup_module.set_backup_settings(
            enabled=True,
            backup_root=os.path.join(self._tmp.name, "backups"),
            retention_count=5,
        )

        world_path = self._make_world(
            "bedrock_world_lower_manifest",
            "db/CURRENT",
            "manifest-000001\n",
        )
        manifest_name = "manifest-000001"
        with open(
            os.path.join(world_path, f"db/{manifest_name}"), "w", encoding="utf-8"
        ) as f:
            f.write("manifest-data")

        current_path = os.path.join(world_path, "db/CURRENT")
        original_copy2 = backup_module.shutil.copy2

        def _copy2_with_locked_current(src, dst, *args, **kwargs):
            norm_src = os.path.normcase(os.path.normpath(src))
            norm_current = os.path.normcase(os.path.normpath(current_path))
            if norm_src == norm_current:
                raise PermissionError(13, "Permission denied")
            return original_copy2(src, dst, *args, **kwargs)

        with mock.patch.object(
            backup_module.shutil, "copy2", side_effect=_copy2_with_locked_current
        ):
            backup_path = _exhaust(backup_module.iter_backup(world_path, "pre-save"))

        self.assertTrue(backup_path)
        repaired_current = os.path.join(backup_path, "db/CURRENT")
        self.assertTrue(os.path.exists(repaired_current))
        with open(repaired_current, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), f"{manifest_name}\n")
        self.assertFalse(
            os.path.exists(os.path.join(backup_path, ".amulet_backup_warnings.txt"))
        )


if __name__ == "__main__":
    unittest.main()
