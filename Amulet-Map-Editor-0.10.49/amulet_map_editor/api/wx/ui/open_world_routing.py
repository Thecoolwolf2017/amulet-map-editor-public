from typing import Any


def route_open_world_to_tab(parent: Any) -> bool:
    """
    Route an open-world action to the reusable open-world tab when supported.

    Returns True when routing succeeded; otherwise False so callers can
    fall back to the modal dialog path.
    """
    top_level_parent = parent.GetTopLevelParent() if parent is not None else None
    show_open_world = getattr(top_level_parent, "show_open_world", None)
    if callable(show_open_world):
        show_open_world()
        return True
    return False
