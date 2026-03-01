import unittest


try:
    from amulet_map_editor.programs.edit.api import key_config
except Exception as exc:  # pragma: no cover - dependency guard
    key_config = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class CursorKeybindTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"key_config import unavailable: {_IMPORT_ERROR}")

    def test_cursor_offset_uses_action_ids(self):
        actions = {
            key_config.ACT_CURSOR_INCREASE_X,
            key_config.ACT_CURSOR_DECREASE_Y,
            key_config.ACT_CURSOR_INCREASE_Z,
        }
        self.assertEqual(key_config.get_cursor_key_offset(actions), (1, -1, 1))

    def test_cursor_offset_cancels_when_opposites_pressed(self):
        actions = {
            key_config.ACT_CURSOR_DECREASE_X,
            key_config.ACT_CURSOR_INCREASE_X,
            key_config.ACT_CURSOR_DECREASE_Z,
            key_config.ACT_CURSOR_INCREASE_Z,
        }
        self.assertEqual(key_config.get_cursor_key_offset(actions), (0, 0, 0))

    def test_merge_with_defaults_keeps_new_actions(self):
        merged = key_config.merge_with_default_keybinds(
            {key_config.ACT_MOVE_FORWARDS: ((), "I")}
        )
        self.assertIn(key_config.ACT_CURSOR_INCREASE_X, merged)
        self.assertEqual(merged[key_config.ACT_MOVE_FORWARDS], ((), "I"))


if __name__ == "__main__":
    unittest.main()
