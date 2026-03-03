import importlib.util
import unittest
from pathlib import Path


def _load_lasso_selection_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "programs"
        / "edit"
        / "api"
        / "behaviour"
        / "lasso_selection.py"
    )
    spec = importlib.util.spec_from_file_location("test_lasso_selection", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lasso_selection = _load_lasso_selection_module()


class LassoSelectionTests(unittest.TestCase):
    def test_interpolate_grid_line_is_contiguous(self):
        points = lasso_selection.interpolate_grid_line((0, 0), (5, 3))
        self.assertEqual((0, 0), points[0])
        self.assertEqual((5, 3), points[-1])

        for (x1, z1), (x2, z2) in zip(points, points[1:]):
            self.assertLessEqual(abs(x2 - x1), 1)
            self.assertLessEqual(abs(z2 - z1), 1)

    def test_single_point_creates_single_column(self):
        group = lasso_selection.lasso_points_to_selection_group([(5, -3)], 10, 10)
        self.assertEqual(1, len(group.selection_boxes))
        self.assertTrue(group.contains_block((5, 10, -3)))
        self.assertFalse(group.contains_block((6, 10, -3)))

    def test_triangle_contains_interior(self):
        group = lasso_selection.lasso_points_to_selection_group(
            [(0, 0), (6, 0), (0, 6)],
            0,
            5,
        )
        self.assertTrue(group.contains_block((1, 0, 1)))
        self.assertTrue(group.contains_block((0, 0, 0)))
        self.assertFalse(group.contains_block((6, 0, 6)))

    def test_rows_to_selection_boxes_merges_identical_runs(self):
        boxes = lasso_selection.rows_to_selection_boxes(
            {
                0: [(0, 2)],
                1: [(0, 2)],
                2: [(1, 3)],
            },
            10,
            20,
        )
        self.assertEqual(2, len(boxes))
        self.assertEqual((0, 10, 0), tuple(boxes[0].min))
        self.assertEqual((2, 20, 2), tuple(boxes[0].max))
        self.assertEqual((1, 10, 2), tuple(boxes[1].min))
        self.assertEqual((3, 20, 3), tuple(boxes[1].max))


if __name__ == "__main__":
    unittest.main()
