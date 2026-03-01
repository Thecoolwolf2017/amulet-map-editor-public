import importlib.util
import unittest
from pathlib import Path


def _load_focus_options_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "programs"
        / "edit"
        / "api"
        / "focus_options.py"
    )
    spec = importlib.util.spec_from_file_location("test_focus_options", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


focus_options = _load_focus_options_module()


class FocusOptionsTests(unittest.TestCase):
    def test_focus_follows_mouse_enabled(self):
        self.assertTrue(
            focus_options.should_focus_canvas_on_mouse_motion(True, False)
        )

    def test_focus_when_camera_rotating(self):
        self.assertTrue(
            focus_options.should_focus_canvas_on_mouse_motion(False, True)
        )

    def test_focus_disabled_when_not_rotating_and_toggle_off(self):
        self.assertFalse(
            focus_options.should_focus_canvas_on_mouse_motion(False, False)
        )


if __name__ == "__main__":
    unittest.main()
