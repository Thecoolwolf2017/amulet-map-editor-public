import importlib.util
import unittest
from pathlib import Path

import numpy


def _load_replace_filters_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "programs"
        / "edit"
        / "plugins"
        / "operations"
        / "stock_plugins"
        / "operations"
        / "replace_filters.py"
    )
    spec = importlib.util.spec_from_file_location("test_replace_filters", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


replace_filters = _load_replace_filters_module()


class ReplaceFiltersTests(unittest.TestCase):
    def test_any_of_matches_only_listed_ids(self):
        blocks = numpy.array([[1, 2], [3, 4]])
        mask = replace_filters.match_mode_replace_mask(
            blocks,
            [2, 4],
            replace_filters.MATCH_MODE_ANY_OF,
        )
        expected = numpy.array([[False, True], [False, True]])
        self.assertTrue(numpy.array_equal(mask, expected))

    def test_none_of_matches_everything_except_listed_ids(self):
        blocks = numpy.array([[1, 2], [3, 4]])
        mask = replace_filters.match_mode_replace_mask(
            blocks,
            [2, 4],
            replace_filters.MATCH_MODE_NONE_OF,
        )
        expected = numpy.array([[True, False], [True, False]])
        self.assertTrue(numpy.array_equal(mask, expected))

    def test_unknown_mode_defaults_to_any_of_behavior(self):
        blocks = numpy.array([[1, 2], [3, 4]])
        mask = replace_filters.match_mode_replace_mask(blocks, [2, 4], "unknown")
        expected = numpy.array([[False, True], [False, True]])
        self.assertTrue(numpy.array_equal(mask, expected))


if __name__ == "__main__":
    unittest.main()
