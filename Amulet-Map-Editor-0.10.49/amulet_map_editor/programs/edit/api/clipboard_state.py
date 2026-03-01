from __future__ import annotations

from typing import Optional, Tuple, TypedDict

from amulet.api.data_types import Dimension
from amulet.api.selection import SelectionGroup


class ClipboardState(TypedDict):
    revision: int
    origin: Optional[Tuple[int, int, int]]
    world_path: Optional[str]
    dimension: Optional[Dimension]


_clipboard_state: ClipboardState = {
    "revision": 0,
    "origin": None,
    "world_path": None,
    "dimension": None,
}


def _selection_origin(selection: SelectionGroup) -> Optional[Tuple[int, int, int]]:
    boxes = selection.selection_boxes
    if not boxes:
        return None

    min_x = min(int(box.min[0]) for box in boxes)
    min_y = min(int(box.min[1]) for box in boxes)
    min_z = min(int(box.min[2]) for box in boxes)
    return min_x, min_y, min_z


def record_clipboard_origin(
    world_path: Optional[str], dimension: Dimension, selection: SelectionGroup
) -> None:
    origin = _selection_origin(selection)
    if origin is None:
        return

    _clipboard_state["revision"] += 1
    _clipboard_state["origin"] = origin
    _clipboard_state["world_path"] = world_path
    _clipboard_state["dimension"] = dimension


def get_clipboard_state() -> ClipboardState:
    return dict(_clipboard_state)

