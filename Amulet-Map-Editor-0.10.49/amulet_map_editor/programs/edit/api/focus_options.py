from __future__ import annotations


def should_focus_canvas_on_mouse_motion(
    focus_follows_mouse: bool, camera_rotating: bool
) -> bool:
    """Return True when mouse motion should move keyboard focus to the canvas."""

    return bool(focus_follows_mouse or camera_rotating)
