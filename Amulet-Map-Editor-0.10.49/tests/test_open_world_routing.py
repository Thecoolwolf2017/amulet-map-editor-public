import importlib.util
import unittest
from pathlib import Path


def _load_open_world_routing_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "api"
        / "wx"
        / "ui"
        / "open_world_routing.py"
    )
    spec = importlib.util.spec_from_file_location("test_open_world_routing", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


open_world_routing = _load_open_world_routing_module()


class _DummyParent:
    def __init__(self, top_level_parent):
        self._top_level_parent = top_level_parent

    def GetTopLevelParent(self):
        return self._top_level_parent


class _TopLevelWithOpenWorld:
    def __init__(self):
        self.calls = 0

    def show_open_world(self):
        self.calls += 1


class OpenWorldRoutingTests(unittest.TestCase):
    def test_routes_to_tab_when_supported(self):
        top_level_parent = _TopLevelWithOpenWorld()
        parent = _DummyParent(top_level_parent)

        routed = open_world_routing.route_open_world_to_tab(parent)

        self.assertTrue(routed)
        self.assertEqual(top_level_parent.calls, 1)

    def test_returns_false_when_parent_is_none(self):
        self.assertFalse(open_world_routing.route_open_world_to_tab(None))

    def test_returns_false_when_top_level_has_no_show_open_world(self):
        parent = _DummyParent(object())
        self.assertFalse(open_world_routing.route_open_world_to_tab(parent))

    def test_returns_false_when_show_open_world_is_not_callable(self):
        class _TopLevel:
            show_open_world = "not-callable"

        parent = _DummyParent(_TopLevel())
        self.assertFalse(open_world_routing.route_open_world_to_tab(parent))


if __name__ == "__main__":
    unittest.main()
