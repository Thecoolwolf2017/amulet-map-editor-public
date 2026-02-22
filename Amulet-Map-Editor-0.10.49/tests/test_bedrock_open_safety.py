import os
import tempfile
import unittest
import importlib.util
from pathlib import Path


def _load_bedrock_safety_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "api"
        / "bedrock_open_safety.py"
    )
    spec = importlib.util.spec_from_file_location("test_bedrock_open_safety", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bedrock_safety = _load_bedrock_safety_module()


class BedrockOpenSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _make_world(self, name: str) -> str:
        world_path = os.path.join(self._tmp.name, name)
        os.makedirs(os.path.join(world_path, "db"), exist_ok=True)
        with open(os.path.join(world_path, "level.dat"), "wb") as f:
            f.write(b"\x00")
        with open(os.path.join(world_path, "levelname.txt"), "w", encoding="utf-8") as f:
            f.write("Test World")
        return world_path

    def test_non_bedrock_world_no_actions(self):
        path = os.path.join(self._tmp.name, "not_a_world")
        os.makedirs(path, exist_ok=True)
        self.assertFalse(bedrock_safety.is_probably_bedrock_world(path))
        self.assertEqual(bedrock_safety.prepare_bedrock_world_for_open(path), [])

    def test_repairs_missing_current_from_latest_manifest(self):
        world_path = self._make_world("world_missing_current")
        with open(os.path.join(world_path, "db", "MANIFEST-000001"), "w", encoding="utf-8") as f:
            f.write("a")
        with open(os.path.join(world_path, "db", "MANIFEST-000003"), "w", encoding="utf-8") as f:
            f.write("b")

        actions = bedrock_safety.prepare_bedrock_world_for_open(world_path)
        self.assertIn("repaired_db_current", actions)
        with open(os.path.join(world_path, "db", "CURRENT"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "MANIFEST-000003\n")

    def test_repairs_case_mismatched_current(self):
        world_path = self._make_world("world_case_mismatch")
        with open(os.path.join(world_path, "db", "manifest-000001"), "w", encoding="utf-8") as f:
            f.write("a")
        with open(os.path.join(world_path, "db", "CURRENT"), "w", encoding="utf-8") as f:
            f.write("MANIFEST-000001\n")

        actions = bedrock_safety.prepare_bedrock_world_for_open(world_path)
        self.assertTrue(actions)
        with open(os.path.join(world_path, "db", "CURRENT"), "r", encoding="utf-8") as f:
            current_value = f.read().strip()
        self.assertTrue(
            os.path.exists(os.path.join(world_path, "db", current_value)),
            msg=f"CURRENT points to missing manifest: {current_value}",
        )

    def test_removes_stale_lock_file(self):
        world_path = self._make_world("world_with_lock")
        with open(os.path.join(world_path, "db", "MANIFEST-000001"), "w", encoding="utf-8") as f:
            f.write("a")
        lock_path = os.path.join(world_path, "db", "LOCK")
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write("lock")

        actions = bedrock_safety.prepare_bedrock_world_for_open(world_path)
        self.assertIn("removed_db_lock", actions)
        self.assertFalse(os.path.exists(lock_path))


if __name__ == "__main__":
    unittest.main()
