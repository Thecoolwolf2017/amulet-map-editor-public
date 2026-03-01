from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple


Point3 = Tuple[int, int, int]


def _coerce_origin(origin: Any) -> Optional[Point3]:
    if not isinstance(origin, (tuple, list)) or len(origin) != 3:
        return None
    try:
        return int(origin[0]), int(origin[1]), int(origin[2])
    except (TypeError, ValueError):
        return None


def resolve_paste_start_location(
    *,
    current_location: Point3,
    clipboard_state: Optional[Mapping[str, Any]],
    last_clipboard_revision: Optional[int],
    target_world_path: Optional[str],
    target_dimension: Optional[str],
    force_origin_for_cross_context: bool = True,
) -> Tuple[Point3, Optional[int]]:
    """Resolve initial paste location from clipboard state.

    The origin is applied once for each clipboard revision.
    """

    if not isinstance(clipboard_state, Mapping):
        return current_location, last_clipboard_revision

    revision = clipboard_state.get("revision")
    if not isinstance(revision, int) or revision == last_clipboard_revision:
        return current_location, last_clipboard_revision

    origin = _coerce_origin(clipboard_state.get("origin"))
    if origin is None:
        return current_location, last_clipboard_revision

    same_world = clipboard_state.get("world_path") == target_world_path
    same_dimension = clipboard_state.get("dimension") == target_dimension

    if same_world and same_dimension:
        return origin, revision

    if force_origin_for_cross_context:
        return origin, revision

    return current_location, last_clipboard_revision
