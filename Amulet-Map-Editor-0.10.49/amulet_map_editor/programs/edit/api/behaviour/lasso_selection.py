from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple

from amulet.api.selection import SelectionBox, SelectionGroup

LassoPoint = Tuple[int, int]
RowInterval = Tuple[int, int]
RowIntervals = Dict[int, List[RowInterval]]


def interpolate_grid_line(start: LassoPoint, end: LassoPoint) -> List[LassoPoint]:
    """Return integer grid points between start and end inclusive."""
    x0, z0 = start
    x1, z1 = end

    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dz = -abs(z1 - z0)
    sz = 1 if z0 < z1 else -1
    err = dx + dz

    points = [(x0, z0)]
    while x0 != x1 or z0 != z1:
        err2 = 2 * err
        if err2 >= dz:
            err += dz
            x0 += sx
        if err2 <= dx:
            err += dx
            z0 += sz
        points.append((x0, z0))
    return points


def merge_row_intervals(intervals: Iterable[RowInterval]) -> List[RowInterval]:
    """Merge overlapping and touching row intervals."""
    sorted_intervals = sorted(intervals)
    if not sorted_intervals:
        return []

    merged = [sorted_intervals[0]]
    for start, end in sorted_intervals[1:]:
        if end <= start:
            continue
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def rasterize_lasso_rows(points: Sequence[LassoPoint]) -> RowIntervals:
    """Rasterize lasso points into x-intervals for each z row."""
    if not points:
        return {}

    points = [(int(x), int(z)) for x, z in points]
    row_intervals: RowIntervals = {}

    boundary_points = set()
    for start, end in zip(points, points[1:]):
        boundary_points.update(interpolate_grid_line(start, end))
    if len(points) >= 2 and points[0] != points[-1]:
        boundary_points.update(interpolate_grid_line(points[-1], points[0]))
    if not boundary_points:
        boundary_points.add(points[0])

    # Always include the drawn boundary.
    for x, z in boundary_points:
        row_intervals.setdefault(z, []).append((x, x + 1))

    unique_points = list(dict.fromkeys(points))
    if len(unique_points) >= 3:
        vertices = [(x + 0.5, z + 0.5) for x, z in unique_points]
        if vertices[0] != vertices[-1]:
            vertices.append(vertices[0])

        min_row = min(z for _, z in boundary_points)
        max_row = max(z for _, z in boundary_points)

        # Even-odd scanline fill using cell-center sampling.
        for row in range(min_row, max_row + 1):
            scan_z = row + 0.5
            intersections: List[float] = []
            for (x1, z1), (x2, z2) in zip(vertices, vertices[1:]):
                if z1 == z2:
                    continue
                if (z1 <= scan_z < z2) or (z2 <= scan_z < z1):
                    x = x1 + (scan_z - z1) * (x2 - x1) / (z2 - z1)
                    intersections.append(x)

            intersections.sort()
            for left, right in zip(intersections[0::2], intersections[1::2]):
                if right <= left:
                    continue
                x_start = int(math.ceil(left - 0.5))
                x_stop = int(math.ceil(right - 0.5))
                if x_stop > x_start:
                    row_intervals.setdefault(row, []).append((x_start, x_stop))

    return {
        row: merge_row_intervals(intervals) for row, intervals in row_intervals.items()
    }


def rows_to_selection_boxes(
    row_intervals: RowIntervals, min_y: int, max_y: int
) -> List[SelectionBox]:
    """Convert row intervals to vertical selection boxes."""
    if not row_intervals:
        return []

    min_y = int(min_y)
    max_y = int(max_y)
    if max_y <= min_y:
        max_y = min_y + 1

    boxes: List[SelectionBox] = []

    def flush(
        run_start: int, run_end: int, run_intervals: Tuple[RowInterval, ...]
    ) -> None:
        for x_start, x_stop in run_intervals:
            boxes.append(
                SelectionBox((x_start, min_y, run_start), (x_stop, max_y, run_end + 1))
            )

    rows = sorted(row_intervals)
    run_start = rows[0]
    run_end = rows[0]
    run_intervals = tuple(merge_row_intervals(row_intervals[rows[0]]))

    for row in rows[1:]:
        intervals = tuple(merge_row_intervals(row_intervals[row]))
        if row == run_end + 1 and intervals == run_intervals:
            run_end = row
            continue

        flush(run_start, run_end, run_intervals)
        run_start = row
        run_end = row
        run_intervals = intervals

    flush(run_start, run_end, run_intervals)
    return boxes


def lasso_points_to_selection_group(
    points: Sequence[LassoPoint], min_y: int, max_y: int
) -> SelectionGroup:
    """Convert lasso points to a SelectionGroup."""
    row_intervals = rasterize_lasso_rows(points)
    boxes = rows_to_selection_boxes(row_intervals, min_y, max_y)
    if not boxes:
        return SelectionGroup()
    return SelectionGroup(boxes).merge_boxes()
