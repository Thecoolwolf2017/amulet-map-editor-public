import wx
import logging
from typing import TYPE_CHECKING, Type, Dict, Optional

try:
    from importlib import metadata as importlib_metadata
except Exception:  # pragma: no cover - backport fallback
    import importlib_metadata

from amulet_map_editor.programs.edit.api import EditCanvasContainer
from amulet_map_editor.programs.edit.api.ui.tool.base_tool_ui import (
    BaseToolUI,
    BaseToolUIType,
)
from amulet_map_editor.programs.edit.api.ui.tool.base_operation_choice import (
    BaseOperationChoiceToolUI,
)
from amulet_map_editor.programs.edit.api.events import (
    ToolChangeEvent,
    EVT_TOOL_CHANGE,
)

from amulet_map_editor.programs.edit.plugins.tools import (
    ImportTool,
    ExportTool,
    OperationTool,
    SelectTool,
    ChunkTool,
    PasteTool,
)

if TYPE_CHECKING:
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

log = logging.getLogger(__name__)

_MODE_HINTS = (
    ("Ctrl+S", "Select"),
    ("Ctrl+V", "Paste"),
    ("Ctrl+O", "Operation"),
)

_QUICK_OPERATION_HINTS = (
    ("Ctrl+W", "Waterlog"),
    ("Ctrl+Q", "Clone"),
    ("Ctrl+E", "Fill"),
    ("Ctrl+R", "Replace"),
    ("Ctrl+B", "Set Biome"),
    ("Ctrl+F", "Find"),
)


class ToolManagerSizer(wx.BoxSizer, EditCanvasContainer):
    def __init__(self, canvas: "EditCanvas"):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        EditCanvasContainer.__init__(self, canvas)

        self._tools: Dict[str, BaseToolUIType] = {}
        self._active_tool: Optional[BaseToolUIType] = None

        self._tool_option_sizer = wx.BoxSizer(wx.VERTICAL)
        self.Add(
            self._tool_option_sizer, 1, wx.EXPAND | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 0
        )

        tool_select_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tool_select_sizer.AddStretchSpacer(1)
        self._tool_select = ToolSelect(canvas)
        tool_select_sizer.Add(self._tool_select, 0, wx.EXPAND, 0)
        tool_select_sizer.AddStretchSpacer(1)
        self.Add(tool_select_sizer, 0, wx.EXPAND, 0)

        hint_sizer = wx.BoxSizer(wx.HORIZONTAL)
        hint_sizer.AddStretchSpacer(1)
        mode_hint_label = wx.StaticText(self.canvas, label=self._mode_hint_text())
        hint_sizer.Add(mode_hint_label, 0, wx.TOP | wx.BOTTOM, 4)
        hint_sizer.AddStretchSpacer(1)
        self.Add(hint_sizer, 0, wx.EXPAND, 0)

        quick_hint_sizer = wx.BoxSizer(wx.HORIZONTAL)
        quick_hint_sizer.AddStretchSpacer(1)
        quick_hint_label = wx.StaticText(
            self.canvas, label=self._quick_operation_hint_text()
        )
        quick_font = quick_hint_label.GetFont()
        quick_font.SetPointSize(max(7, quick_font.GetPointSize() - 1))
        quick_hint_label.SetFont(quick_font)
        quick_hint_sizer.Add(quick_hint_label, 0, wx.BOTTOM, 3)
        quick_hint_sizer.AddStretchSpacer(1)
        self.Add(quick_hint_sizer, 0, wx.EXPAND, 0)

        self.register_tool(SelectTool)
        self.register_tool(PasteTool)
        self.register_tool(OperationTool)
        self.register_tool(ImportTool)
        self.register_tool(ExportTool)
        self.register_tool(ChunkTool)
        self._register_entry_point_tools()

    @property
    def tools(self):
        return self._tools.copy()

    def bind_events(self):
        if self._active_tool is not None:
            self._active_tool.bind_events()
        self.canvas.Bind(EVT_TOOL_CHANGE, self._enable_tool_event)
        self.canvas.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def register_tool(self, tool_cls: Type[BaseToolUIType]):
        assert issubclass(tool_cls, (wx.Window, wx.Sizer)) and issubclass(
            tool_cls, BaseToolUI
        )
        tool = tool_cls(self.canvas)
        self._tool_select.register_tool(tool.name)
        if isinstance(tool, wx.Window):
            tool.Hide()
        elif isinstance(tool, wx.Sizer):
            tool.ShowItems(show=False)
        self._tools[tool.name] = tool
        self._tool_option_sizer.Add(tool, 1, wx.EXPAND, 0)

    def _iter_entry_points(self, group: str):
        try:
            eps = importlib_metadata.entry_points()
            if hasattr(eps, "select"):
                return eps.select(group=group)
            return eps.get(group, [])
        except Exception:
            return []

    def _register_entry_point_tools(self):
        for ep in self._iter_entry_points("amulet_map_editor.edit_tools"):
            try:
                tool_cls = ep.load()
            except BaseException:
                log.warning(
                    f"Failed loading tool entry point {ep.name} from {ep.value}."
                )
                continue
            try:
                self.register_tool(tool_cls)
            except Exception as exc:
                log.warning(
                    f"Entry point tool {ep.name} is invalid and was skipped: {exc}"
                )

    def _enable_tool_event(self, evt: ToolChangeEvent):
        self._enable_tool(evt.tool, evt.state)

    def enable(self):
        if isinstance(self._active_tool, SelectTool):
            self._active_tool.enable()
            self.canvas.reset_bound_events()
            self.canvas.Layout()
        else:
            self._enable_tool("Select")

    def disable(self):
        """Disable the active tool."""
        if self._active_tool is not None:
            self._active_tool.disable()

    def enable_default_tool(self):
        """
        Enables the default tool (the select tool)
        """
        if not isinstance(self._active_tool, SelectTool):
            self._enable_tool("Select")

    def _enable_tool(self, tool: str, state=None):
        if tool in self._tools:
            if self._active_tool is not None:
                self._active_tool.disable()
                if isinstance(self._active_tool, wx.Window):
                    self._active_tool.Hide()
                elif isinstance(self._active_tool, wx.Sizer):
                    self._active_tool.ShowItems(show=False)
            self._active_tool = self._tools[tool]
            if isinstance(self._active_tool, wx.Window):
                self._active_tool.Show()
            elif isinstance(self._active_tool, wx.Sizer):
                self._active_tool.ShowItems(show=True)
            self._active_tool.enable()
            self._active_tool.set_state(state)
            self.canvas.reset_bound_events()
            self.canvas.Layout()

    @staticmethod
    def _normalise_ctrl_letter(evt: wx.KeyEvent) -> Optional[str]:
        key_code = evt.GetKeyCode()
        if 1 <= key_code <= 26:
            return chr(ord("A") + key_code - 1)
        if 65 <= key_code <= 90:
            return chr(key_code)

        unicode_key = evt.GetUnicodeKey()
        if 65 <= unicode_key <= 90:
            return chr(unicode_key)
        if 97 <= unicode_key <= 122:
            return chr(unicode_key - 32)

        return None

    def _text_entry_has_focus(self) -> bool:
        focused = wx.Window.FindFocus()
        if focused is None:
            return False
        # Let standard text-edit shortcuts continue to work while typing.
        return isinstance(focused, wx.TextCtrl)

    def _select_operation_by_shortcut(self, *keywords: str):
        self._enable_tool("Operation")
        tool = self._tools.get("Operation")
        if isinstance(tool, BaseOperationChoiceToolUI):
            tool.select_operation_from_keywords(*keywords)

    def _focus_operation_selector(self):
        self._enable_tool("Operation")
        tool = self._tools.get("Operation")
        if isinstance(tool, BaseOperationChoiceToolUI):
            tool.focus_operation_choice()

    @staticmethod
    def _mode_hint_text() -> str:
        hint_text = " | ".join(
            f"{shortcut} {mode_name}" for shortcut, mode_name in _MODE_HINTS
        )
        return f"Mode Hotkeys: {hint_text}"

    @staticmethod
    def _quick_operation_hint_text() -> str:
        hint_text = " | ".join(
            f"{shortcut} {operation}" for shortcut, operation in _QUICK_OPERATION_HINTS
        )
        return f"Quick Ops: {hint_text}"

    def _on_char_hook(self, evt: wx.KeyEvent):
        if not evt.ControlDown() or evt.AltDown() or evt.ShiftDown():
            evt.Skip()
            return

        if self._text_entry_has_focus():
            evt.Skip()
            return

        key = self._normalise_ctrl_letter(evt)
        if key is None:
            evt.Skip()
            return

        if key == "S":
            self._enable_tool("Select")
            return
        if key == "V":
            self.canvas.paste_from_cache()
            return
        if key == "O":
            self._enable_tool("Operation")
            return
        if key == "W":
            self._select_operation_by_shortcut("waterlog")
            return
        if key == "Q":
            self._select_operation_by_shortcut("clone")
            return
        if key == "E":
            self._select_operation_by_shortcut("fill")
            return
        if key == "R":
            self._select_operation_by_shortcut("replace")
            return
        if key == "B":
            self._select_operation_by_shortcut("biome")
            return
        if key == "F":
            self._focus_operation_selector()
            return

        evt.Skip()


class ToolSelect(wx.Panel, EditCanvasContainer):
    def __init__(self, canvas: "EditCanvas"):
        wx.Panel.__init__(self, canvas)
        EditCanvasContainer.__init__(self, canvas)

        self._sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self._sizer)

    def register_tool(self, name: str):
        button = wx.Button(self, label=name)
        self._sizer.Add(button)
        self._sizer.Fit(self)
        self.Layout()

        button.Bind(
            wx.EVT_BUTTON,
            lambda evt: wx.PostEvent(self.canvas, ToolChangeEvent(tool=name)),
        )
