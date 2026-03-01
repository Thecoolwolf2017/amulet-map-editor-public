import importlib.util
import unittest
from pathlib import Path


def _load_update_check_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "api"
        / "framework"
        / "update_check.py"
    )
    spec = importlib.util.spec_from_file_location("test_update_check", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


update_check = _load_update_check_module()


class UpdateCheckTests(unittest.TestCase):
    def test_shows_when_meta_config_missing(self):
        self.assertTrue(update_check.should_show_update_dialog({}, "2.0.0"))

    def test_does_not_show_same_version_twice(self):
        self.assertFalse(
            update_check.should_show_update_dialog(
                {"last_update_notified_version": "2.0.0"},
                "2.0.0",
            )
        )

    def test_shows_when_new_release_differs(self):
        self.assertTrue(
            update_check.should_show_update_dialog(
                {"last_update_notified_version": "2.0.0"},
                "2.0.1",
            )
        )


if __name__ == "__main__":
    unittest.main()
