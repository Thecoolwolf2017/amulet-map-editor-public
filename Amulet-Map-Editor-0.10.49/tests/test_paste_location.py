import importlib.util
import unittest
from pathlib import Path


def _load_paste_location_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "programs"
        / "edit"
        / "api"
        / "paste_location.py"
    )
    spec = importlib.util.spec_from_file_location("test_paste_location", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paste_location = _load_paste_location_module()


class PasteLocationTests(unittest.TestCase):
    def test_same_world_and_dimension_uses_origin(self):
        location, revision = paste_location.resolve_paste_start_location(
            current_location=(9, 9, 9),
            clipboard_state={
                "revision": 4,
                "origin": (1, 2, 3),
                "world_path": "world_a",
                "dimension": "minecraft:overworld",
            },
            last_clipboard_revision=3,
            target_world_path="world_a",
            target_dimension="minecraft:overworld",
        )
        self.assertEqual((1, 2, 3), location)
        self.assertEqual(4, revision)

    def test_cross_world_uses_origin_when_forced(self):
        location, revision = paste_location.resolve_paste_start_location(
            current_location=(9, 9, 9),
            clipboard_state={
                "revision": 2,
                "origin": [10, 64, -5],
                "world_path": "world_a",
                "dimension": "minecraft:overworld",
            },
            last_clipboard_revision=1,
            target_world_path="world_b",
            target_dimension="minecraft:overworld",
            force_origin_for_cross_context=True,
        )
        self.assertEqual((10, 64, -5), location)
        self.assertEqual(2, revision)

    def test_cross_dimension_uses_origin_when_forced(self):
        location, revision = paste_location.resolve_paste_start_location(
            current_location=(0, 0, 0),
            clipboard_state={
                "revision": 7,
                "origin": (4, 5, 6),
                "world_path": "world_a",
                "dimension": "minecraft:the_nether",
            },
            last_clipboard_revision=6,
            target_world_path="world_a",
            target_dimension="minecraft:overworld",
            force_origin_for_cross_context=True,
        )
        self.assertEqual((4, 5, 6), location)
        self.assertEqual(7, revision)

    def test_cross_context_does_not_use_origin_without_force_flag(self):
        location, revision = paste_location.resolve_paste_start_location(
            current_location=(8, 8, 8),
            clipboard_state={
                "revision": 10,
                "origin": (1, 1, 1),
                "world_path": "world_a",
                "dimension": "minecraft:overworld",
            },
            last_clipboard_revision=9,
            target_world_path="world_b",
            target_dimension="minecraft:overworld",
            force_origin_for_cross_context=False,
        )
        self.assertEqual((8, 8, 8), location)
        self.assertEqual(9, revision)

    def test_same_revision_does_not_reapply_origin(self):
        location, revision = paste_location.resolve_paste_start_location(
            current_location=(8, 8, 8),
            clipboard_state={
                "revision": 3,
                "origin": (1, 1, 1),
                "world_path": "world_a",
                "dimension": "minecraft:overworld",
            },
            last_clipboard_revision=3,
            target_world_path="world_b",
            target_dimension="minecraft:overworld",
            force_origin_for_cross_context=True,
        )
        self.assertEqual((8, 8, 8), location)
        self.assertEqual(3, revision)

    def test_invalid_origin_is_ignored(self):
        location, revision = paste_location.resolve_paste_start_location(
            current_location=(2, 2, 2),
            clipboard_state={
                "revision": 11,
                "origin": ("x", 1, 2),
                "world_path": "world_a",
                "dimension": "minecraft:overworld",
            },
            last_clipboard_revision=10,
            target_world_path="world_b",
            target_dimension="minecraft:overworld",
            force_origin_for_cross_context=True,
        )
        self.assertEqual((2, 2, 2), location)
        self.assertEqual(10, revision)


if __name__ == "__main__":
    unittest.main()
