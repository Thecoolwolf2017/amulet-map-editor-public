from typing import List, Set, Tuple
from amulet_map_editor.api.wx.util.key_config import (
    KeybindContainer,
    KeybindGroup,
    KeybindGroupIdType,
    KeyActionType,
    Space,
    Shift,
    MouseLeft,
    MouseRight,
    MouseWheelScrollUp,
    MouseWheelScrollDown,
    Control,
    Alt,
    Tab,
    Left,
    Right,
    Up,
    Down,
    PageUp,
    PageDown,
)

ACT_MOVE_UP = "ACT_MOVE_UP"
ACT_MOVE_DOWN = "ACT_MOVE_DOWN"
ACT_MOVE_FORWARDS = "ACT_MOVE_FORWARDS"
ACT_MOVE_BACKWARDS = "ACT_MOVE_BACKWARDS"
ACT_MOVE_LEFT = "ACT_MOVE_LEFT"
ACT_MOVE_RIGHT = "ACT_MOVE_RIGHT"
ACT_BOX_CLICK = "ACT_BOX_CLICK"
ACT_BOX_CLICK_ADD = "ACT_BOX_CLICK_ADD"
ACT_CHANGE_MOUSE_MODE = "ACT_CHANGE_MOUSE_MODE"
ACT_INCR_SPEED = "ACT_INCR_SPEED"
ACT_DECR_SPEED = "ACT_DECR_SPEED"
ACT_ZOOM_IN = "ACT_ZOOM_IN"
ACT_ZOOM_OUT = "ACT_ZOOM_OUT"
ACT_INCR_SELECT_DISTANCE = "ACT_INCR_SELECT_DISTANCE"
ACT_DECR_SELECT_DISTANCE = "ACT_DECR_SELECT_DISTANCE"
ACT_DESELECT_ALL_BOXES = "ACT_DESELECT_ALL_BOXES"
ACT_DESELECT_BOX = "ACT_DESELECT_BOX"
ACT_INSPECT_BLOCK = "ACT_INSPECT_BLOCK"
ACT_CHANGE_PROJECTION = "ACT_CHANGE_PROJECTION"
ACT_CURSOR_DECREASE_X = "ACT_CURSOR_DECREASE_X"
ACT_CURSOR_INCREASE_X = "ACT_CURSOR_INCREASE_X"
ACT_CURSOR_DECREASE_Y = "ACT_CURSOR_DECREASE_Y"
ACT_CURSOR_INCREASE_Y = "ACT_CURSOR_INCREASE_Y"
ACT_CURSOR_DECREASE_Z = "ACT_CURSOR_DECREASE_Z"
ACT_CURSOR_INCREASE_Z = "ACT_CURSOR_INCREASE_Z"

KeybindKeys: List[KeyActionType] = [
    ACT_MOVE_UP,
    ACT_MOVE_DOWN,
    ACT_MOVE_FORWARDS,
    ACT_MOVE_BACKWARDS,
    ACT_MOVE_LEFT,
    ACT_MOVE_RIGHT,
    ACT_BOX_CLICK,
    ACT_BOX_CLICK_ADD,
    ACT_CHANGE_MOUSE_MODE,
    ACT_INCR_SPEED,
    ACT_DECR_SPEED,
    ACT_ZOOM_IN,
    ACT_ZOOM_OUT,
    ACT_INCR_SELECT_DISTANCE,
    ACT_DECR_SELECT_DISTANCE,
    ACT_DESELECT_ALL_BOXES,
    ACT_DESELECT_BOX,
    ACT_INSPECT_BLOCK,
    ACT_CHANGE_PROJECTION,
    ACT_CURSOR_DECREASE_X,
    ACT_CURSOR_INCREASE_X,
    ACT_CURSOR_DECREASE_Y,
    ACT_CURSOR_INCREASE_Y,
    ACT_CURSOR_DECREASE_Z,
    ACT_CURSOR_INCREASE_Z,
]

PresetKeybinds: KeybindContainer = {
    "right": {
        ACT_MOVE_UP: ((), Space),
        ACT_MOVE_DOWN: ((), Shift),
        ACT_MOVE_FORWARDS: ((), "W"),
        ACT_MOVE_BACKWARDS: ((), "S"),
        ACT_MOVE_LEFT: ((), "A"),
        ACT_MOVE_RIGHT: ((), "D"),
        ACT_BOX_CLICK: ((), MouseLeft),
        ACT_BOX_CLICK_ADD: ((Control,), MouseLeft),
        ACT_CHANGE_MOUSE_MODE: ((), MouseRight),
        ACT_INCR_SPEED: ((), MouseWheelScrollUp),
        ACT_DECR_SPEED: ((), MouseWheelScrollDown),
        ACT_ZOOM_IN: ((), MouseWheelScrollUp),
        ACT_ZOOM_OUT: ((), MouseWheelScrollDown),
        ACT_INCR_SELECT_DISTANCE: ((), "R"),
        ACT_DECR_SELECT_DISTANCE: ((), "F"),
        ACT_DESELECT_ALL_BOXES: ((Control, Shift), "D"),
        ACT_DESELECT_BOX: ((Control,), "D"),
        ACT_INSPECT_BLOCK: ((), Alt),
        ACT_CHANGE_PROJECTION: ((), Tab),
        ACT_CURSOR_DECREASE_X: ((), Left),
        ACT_CURSOR_INCREASE_X: ((), Right),
        ACT_CURSOR_DECREASE_Y: ((), PageDown),
        ACT_CURSOR_INCREASE_Y: ((), PageUp),
        ACT_CURSOR_DECREASE_Z: ((), Up),
        ACT_CURSOR_INCREASE_Z: ((), Down),
    },
    "right_laptop": {
        ACT_MOVE_UP: ((), Space),
        ACT_MOVE_DOWN: ((), Shift),
        ACT_MOVE_FORWARDS: ((), "W"),
        ACT_MOVE_BACKWARDS: ((), "S"),
        ACT_MOVE_LEFT: ((), "A"),
        ACT_MOVE_RIGHT: ((), "D"),
        ACT_BOX_CLICK: ((), MouseLeft),
        ACT_BOX_CLICK_ADD: ((Control,), MouseLeft),
        ACT_CHANGE_MOUSE_MODE: ((), MouseRight),
        ACT_INCR_SPEED: ((), "."),
        ACT_DECR_SPEED: ((), ","),
        ACT_ZOOM_IN: ((), "."),
        ACT_ZOOM_OUT: ((), ","),
        ACT_INCR_SELECT_DISTANCE: ((), "R"),
        ACT_DECR_SELECT_DISTANCE: ((), "F"),
        ACT_DESELECT_ALL_BOXES: ((Control, Shift), "D"),
        ACT_DESELECT_BOX: ((Control,), "D"),
        ACT_INSPECT_BLOCK: ((), Alt),
        ACT_CHANGE_PROJECTION: ((), Tab),
        ACT_CURSOR_DECREASE_X: ((), Left),
        ACT_CURSOR_INCREASE_X: ((), Right),
        ACT_CURSOR_DECREASE_Y: ((), PageDown),
        ACT_CURSOR_INCREASE_Y: ((), PageUp),
        ACT_CURSOR_DECREASE_Z: ((), Up),
        ACT_CURSOR_INCREASE_Z: ((), Down),
    },
    "left": {
        ACT_MOVE_UP: ((), Space),
        ACT_MOVE_DOWN: ((), ";"),
        ACT_MOVE_FORWARDS: ((), "I"),
        ACT_MOVE_BACKWARDS: ((), "K"),
        ACT_MOVE_LEFT: ((), "J"),
        ACT_MOVE_RIGHT: ((), "L"),
        ACT_BOX_CLICK: ((), MouseLeft),
        ACT_BOX_CLICK_ADD: ((Control,), MouseLeft),
        ACT_CHANGE_MOUSE_MODE: ((), MouseRight),
        ACT_INCR_SPEED: ((), MouseWheelScrollUp),
        ACT_DECR_SPEED: ((), MouseWheelScrollDown),
        ACT_ZOOM_IN: ((), MouseWheelScrollUp),
        ACT_ZOOM_OUT: ((), MouseWheelScrollDown),
        ACT_INCR_SELECT_DISTANCE: ((), "Y"),
        ACT_DECR_SELECT_DISTANCE: ((), "H"),
        ACT_DESELECT_ALL_BOXES: ((Control, Shift), "D"),
        ACT_DESELECT_BOX: ((Control,), "D"),
        ACT_INSPECT_BLOCK: ((), Alt),
        ACT_CHANGE_PROJECTION: ((), Tab),
        ACT_CURSOR_DECREASE_X: ((), Left),
        ACT_CURSOR_INCREASE_X: ((), Right),
        ACT_CURSOR_DECREASE_Y: ((), PageDown),
        ACT_CURSOR_INCREASE_Y: ((), PageUp),
        ACT_CURSOR_DECREASE_Z: ((), Up),
        ACT_CURSOR_INCREASE_Z: ((), Down),
    },
    "left_laptop": {
        ACT_MOVE_UP: ((), Space),
        ACT_MOVE_DOWN: ((), ";"),
        ACT_MOVE_FORWARDS: ((), "I"),
        ACT_MOVE_BACKWARDS: ((), "K"),
        ACT_MOVE_LEFT: ((), "J"),
        ACT_MOVE_RIGHT: ((), "L"),
        ACT_BOX_CLICK: ((), MouseLeft),
        ACT_BOX_CLICK_ADD: ((Control,), MouseLeft),
        ACT_CHANGE_MOUSE_MODE: ((), MouseRight),
        ACT_INCR_SPEED: ((), "."),
        ACT_DECR_SPEED: ((), ","),
        ACT_ZOOM_IN: ((), "."),
        ACT_ZOOM_OUT: ((), ","),
        ACT_INCR_SELECT_DISTANCE: ((), "Y"),
        ACT_DECR_SELECT_DISTANCE: ((), "H"),
        ACT_DESELECT_ALL_BOXES: ((Control, Shift), "D"),
        ACT_DESELECT_BOX: ((Control,), "D"),
        ACT_INSPECT_BLOCK: ((), Alt),
        ACT_CHANGE_PROJECTION: ((), Tab),
        ACT_CURSOR_DECREASE_X: ((), Left),
        ACT_CURSOR_INCREASE_X: ((), Right),
        ACT_CURSOR_DECREASE_Y: ((), PageDown),
        ACT_CURSOR_INCREASE_Y: ((), PageUp),
        ACT_CURSOR_DECREASE_Z: ((), Up),
        ACT_CURSOR_INCREASE_Z: ((), Down),
    },
}

DefaultKeybindGroupId: KeybindGroupIdType = "right"
DefaultKeys: KeybindGroup = PresetKeybinds[DefaultKeybindGroupId]


def merge_with_default_keybinds(keybinds: KeybindGroup) -> KeybindGroup:
    """Return a keybind group with missing actions filled from defaults."""
    merged = DefaultKeys.copy()
    merged.update(keybinds)
    return merged


def get_cursor_key_offset(pressed_actions: Set[KeyActionType]) -> Tuple[int, int, int]:
    """Get the world-axis cursor delta from held cursor movement actions.

    Mapping:
    - left/right: x axis
    - page down/page up: y axis
    - up/down: z axis
    """

    x = int(ACT_CURSOR_INCREASE_X in pressed_actions) - int(
        ACT_CURSOR_DECREASE_X in pressed_actions
    )
    y = int(ACT_CURSOR_INCREASE_Y in pressed_actions) - int(
        ACT_CURSOR_DECREASE_Y in pressed_actions
    )
    z = int(ACT_CURSOR_INCREASE_Z in pressed_actions) - int(
        ACT_CURSOR_DECREASE_Z in pressed_actions
    )
    return x, y, z
