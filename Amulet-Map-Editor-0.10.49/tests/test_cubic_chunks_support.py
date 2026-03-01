import os
import tempfile
import unittest
import importlib.util
from pathlib import Path


def _load_cubic_chunks_support_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "api"
        / "cubic_chunks_support.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_cubic_chunks_support", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cubic_chunks_support = _load_cubic_chunks_support_module()


class CubicChunksSupportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _make_world_root(self, name: str) -> str:
        world_path = os.path.join(self._tmp.name, name)
        os.makedirs(world_path, exist_ok=True)
        with open(os.path.join(world_path, "level.dat"), "wb") as f:
            f.write(b"\x00")
        return world_path

    def test_non_world_is_not_detected(self):
        path = os.path.join(self._tmp.name, "not_world")
        os.makedirs(path, exist_ok=True)
        self.assertFalse(cubic_chunks_support.is_probably_cubic_chunks_world(path))

    def test_region3d_marker_detected(self):
        world_path = self._make_world_root("with_region3d")
        os.makedirs(os.path.join(world_path, "region3d"), exist_ok=True)
        self.assertTrue(cubic_chunks_support.is_probably_cubic_chunks_world(world_path))

    def test_region2d_marker_detected(self):
        world_path = self._make_world_root("with_region2d")
        os.makedirs(os.path.join(world_path, "region2d"), exist_ok=True)
        self.assertTrue(cubic_chunks_support.is_probably_cubic_chunks_world(world_path))

    def test_cubic_chunks_data_file_detected(self):
        world_path = self._make_world_root("with_data_marker")
        os.makedirs(os.path.join(world_path, "data"), exist_ok=True)
        with open(
            os.path.join(world_path, "data", "cubicChunksData.dat"), "wb"
        ) as f:
            f.write(b"\x00")
        self.assertTrue(cubic_chunks_support.is_probably_cubic_chunks_world(world_path))

    def test_dimension_nested_marker_detected(self):
        world_path = self._make_world_root("nested_marker")
        os.makedirs(os.path.join(world_path, "DIM-1", "region3d"), exist_ok=True)
        self.assertTrue(cubic_chunks_support.is_probably_cubic_chunks_world(world_path))

    def test_message_contains_world_path(self):
        world_path = self._make_world_root("message_world")
        msg = cubic_chunks_support.cubic_chunks_not_supported_message(world_path)
        self.assertIn("Cubic Chunks", msg)
        self.assertIn(os.path.abspath(world_path), msg)


if __name__ == "__main__":
    unittest.main()
