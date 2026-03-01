from __future__ import annotations
import wx
from wx.lib.agw import flatnotebook
from typing import Dict, Union, Callable
import traceback
import logging
import sys
import subprocess
from textwrap import dedent

from amulet.api.errors import LoaderNoneMatched
from amulet_map_editor.api.bedrock_open_safety import prepare_bedrock_world_for_open
from amulet_map_editor.api.cubic_chunks_support import (
    is_probably_cubic_chunks_world,
    cubic_chunks_not_supported_message,
)
from amulet_map_editor.api.wx.ui.select_world import (
    WorldSelectAndRecentUI,
)
from amulet_map_editor.api.wx.ui.traceback_dialog import TracebackDialog
from amulet_map_editor import __version__, lang
from amulet_map_editor.api.framework.pages import WorldPageUI
from .pages import AmuletMainMenu, BasePageUI

from amulet_map_editor.api import image
from amulet_map_editor.api.wx.util.ui_preferences import preserve_ui_preferences

log = logging.getLogger(__name__)

NOTEBOOK_MENU_STYLE = (
    flatnotebook.FNB_NO_X_BUTTON
    | flatnotebook.FNB_HIDE_ON_SINGLE_TAB
    | flatnotebook.FNB_NAV_BUTTONS_WHEN_NEEDED
)
NOTEBOOK_STYLE = NOTEBOOK_MENU_STYLE | flatnotebook.FNB_X_ON_TAB

CLOSEABLE_PAGE_TYPE = Union[WorldPageUI]

wx.Image.SetDefaultLoadFlags(0)


def _describe_probe_return_code(return_code: int) -> str:
    unsigned_code = return_code & 0xFFFFFFFF
    if unsigned_code == 0xC0000005:
        return "Probe crashed with access violation (0xC0000005)."
    if unsigned_code == 0xC0000409:
        return "Probe crashed with stack buffer overrun (0xC0000409)."
    if unsigned_code == 0xC000001D:
        return "Probe crashed with illegal instruction (0xC000001D)."
    return f"Probe exited with code {return_code} (0x{unsigned_code:08X})."


def _preflight_world_open(path: str) -> tuple[bool, str]:
    """
    Load/close the world in a subprocess first.
    This prevents native extension crashes from taking down the UI process.
    """
    try:
        if getattr(sys, "frozen", False):
            completed = subprocess.run(
                [sys.executable, "--amulet-world-probe", path],
                capture_output=True,
                text=True,
                timeout=25,
            )
        else:
            script = dedent("""
                import sys
                import traceback

                try:
                    # Match normal app startup: load leveldb before wx/native world APIs.
                    import leveldb  # noqa: F401
                except Exception:
                    leveldb = None

                import amulet

                try:
                    from amulet_map_editor.api.bedrock_open_safety import (
                        prepare_bedrock_world_for_open,
                    )
                except Exception:
                    prepare_bedrock_world_for_open = None

                world = None
                try:
                    if callable(prepare_bedrock_world_for_open):
                        try:
                            prepare_bedrock_world_for_open(sys.argv[1])
                        except Exception:
                            pass
                    world = amulet.load_level(sys.argv[1])
                except BaseException:
                    traceback.print_exc()
                    raise
                finally:
                    if world is not None:
                        close = getattr(world, "close", None)
                        if close is not None:
                            close()
                """)
            completed = subprocess.run(
                [sys.executable, "-c", script, path],
                capture_output=True,
                text=True,
                timeout=25,
            )
    except subprocess.TimeoutExpired:
        return False, "Timed out while probing this world."
    except BaseException as exc:
        return False, f"Failed to start world probe: {exc}"

    if completed.returncode == 0:
        return True, ""

    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    details = stderr or stdout
    lines = details.splitlines() if details else []
    tail = "\n".join(lines[-10:]) if lines else ""
    return False, (
        f"{_describe_probe_return_code(completed.returncode)}"
        + (f"\n{tail}" if tail else "")
    )


@preserve_ui_preferences
class AmuletUI(wx.Frame):
    """This is the top level frame that Amulet exists within."""

    # The notebook to hold world pages
    _level_notebook: AmuletLevelNotebook

    def __init__(self, parent):
        title = f"Amulet {__version__}"
        if not getattr(sys, "frozen", False):
            title += " (source)"
        wx.Frame.__init__(
            self,
            parent,
            id=wx.ID_ANY,
            title=title,
            pos=wx.DefaultPosition,
            size=wx.Size(1000, 600),
            style=wx.CAPTION
            | wx.CLOSE_BOX
            | wx.MINIMIZE_BOX
            | wx.MAXIMIZE_BOX
            | wx.SYSTEM_MENU
            | wx.TAB_TRAVERSAL
            | wx.CLIP_CHILDREN
            | wx.RESIZE_BORDER,
        )
        self.SetMinSize((625, 440))
        icon = wx.Icon()
        icon.CopyFromBitmap(image.logo.amulet_logo.bitmap())
        self.SetIcon(icon)

        self._level_notebook = AmuletLevelNotebook(self, agwStyle=NOTEBOOK_MENU_STYLE)
        self._level_notebook.init()

        self.Bind(wx.EVT_CLOSE, self._level_notebook.on_app_close)

    def open_level(self, path: str):
        """Open a level. You should use the method in the app."""
        self._level_notebook.open_level(path)

    def close_level(self, path: str):
        """Close a given level. You should use the method in the app."""
        self._level_notebook.close_level(path)

    def show_open_world(self):
        """Show the reusable world-select tab."""
        self._level_notebook.show_open_world_tab()

    def create_menu(self):
        """
        Create the UI menu.

        Adds the top level menu items then extends it from the active page
        """
        menu_dict = {}
        menu_dict.setdefault(lang.get("menu_bar.file.menu_name"), {}).setdefault(
            "system", {}
        ).setdefault(
            lang.get("menu_bar.file.open_world"),
            lambda evt: self.show_open_world(),
        )
        # menu_dict.setdefault(lang.get('menu_bar.file.menu_name'), {}).setdefault('system', {}).setdefault('Create World', lambda: self.world.save())
        menu_dict.setdefault(lang.get("menu_bar.file.menu_name"), {}).setdefault(
            "exit", {}
        ).setdefault(lang.get("menu_bar.file.quit"), lambda evt: self.Close())
        menu_dict = self._level_notebook.extend_menu(menu_dict)
        menu_bar = wx.MenuBar()
        for menu_name, menu_data in menu_dict.items():
            menu = wx.Menu()
            separator = False
            for menu_section in menu_data.values():
                if separator:
                    menu.AppendSeparator()
                separator = True
                for menu_item_name, menu_item_options in menu_section.items():
                    callback = None
                    menu_item_description = None
                    wx_id = None
                    if callable(menu_item_options):
                        callback = menu_item_options
                    elif isinstance(menu_item_options, tuple):
                        if len(menu_item_options) >= 1:
                            callback = menu_item_options[0]
                        if len(menu_item_options) >= 2:
                            menu_item_description = menu_item_options[1]
                        if len(menu_item_options) >= 3:
                            wx_id = menu_item_options[2]
                    else:
                        continue

                    if not menu_item_description:
                        menu_item_description = ""
                    if not wx_id:
                        wx_id = wx.ID_ANY

                    menu_item: wx.MenuItem = menu.Append(
                        wx_id, menu_item_name, menu_item_description
                    )
                    self.Bind(wx.EVT_MENU, callback, menu_item)
            menu_bar.Append(menu, menu_name)
        self.SetMenuBar(menu_bar)


class OpenWorldPageUI(wx.Panel, BasePageUI):
    def __init__(
        self, parent: wx.Window, open_world_callback: Callable[[str], None]
    ) -> None:
        super().__init__(parent)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        self._world_select = WorldSelectAndRecentUI(self, open_world_callback)
        sizer.Add(self._world_select, 1, wx.EXPAND)

    def enable(self):
        self.GetTopLevelParent().create_menu()
        wx.CallAfter(self._world_select.focus_default_control)


class AmuletLevelNotebook(flatnotebook.FlatNotebook):
    """A notebook to hold all world tabs."""

    # The main menu tab
    _main_menu: AmuletMainMenu

    # Storage of open world tabs for easy lookup
    _open_worlds: Dict[str, CLOSEABLE_PAGE_TYPE]
    _open_world_page: OpenWorldPageUI

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.Bind(flatnotebook.EVT_FLATNOTEBOOK_PAGE_CLOSING, self._on_page_closing)
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self._page_changing, self)
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._page_changed, self)

        self._main_menu = AmuletMainMenu(self)
        self._open_world_page = OpenWorldPageUI(self, self.open_level)
        self._open_worlds = {}

    def init(self):
        self._add_world_tab(self._main_menu, lang.get("main_menu.tab_name"), True)
        self._add_world_tab(self._open_world_page, lang.get("select_world.title"), False)

    def show_open_world_tab(self):
        self.SetSelection(self.GetPageIndex(self._open_world_page))

    def open_level(self, path: str):
        """Open a world panel add it to the notebook"""
        if path in self._open_worlds:
            self.SetSelection(self.GetPageIndex(self._open_worlds[path]))
        else:
            likely_cubic_chunks = is_probably_cubic_chunks_world(path)
            try:
                applied_actions = prepare_bedrock_world_for_open(path)
                if applied_actions:
                    log.debug(
                        "Applied Bedrock pre-open repairs for %s: %s",
                        path,
                        ", ".join(applied_actions),
                    )
            except Exception:
                log.debug("Bedrock pre-open repair failed for %s", path, exc_info=True)

            ok, error = _preflight_world_open(path)
            if not ok:
                if likely_cubic_chunks:
                    error = (
                        f"{error}\n\n{cubic_chunks_not_supported_message(path)}"
                    ).strip()
                log.error(f"World preflight failed for {path}\n{error}")
                wx.MessageBox(
                    "Amulet could not safely open this world.\n\n"
                    "The world loader crashed during preflight.\n\n"
                    f"Path:\n{path}\n\n"
                    f"Details:\n{error}",
                    "World Open Failed",
                    style=wx.OK | wx.ICON_ERROR,
                )
                return

            try:
                world = WorldPageUI(self, path)
            except LoaderNoneMatched as e:
                log.error(f"Could not find a loader for this world.\n{e}")
                if likely_cubic_chunks:
                    wx.MessageBox(
                        cubic_chunks_not_supported_message(path),
                        "Cubic Chunks Not Supported",
                        style=wx.OK | wx.ICON_ERROR,
                    )
                else:
                    wx.MessageBox(f"{lang.get('select_world.no_loader_found')}\n{e}")
            except Exception as e:
                log.error(lang.get("select_world.loading_world_failed"), exc_info=True)
                dialog = TracebackDialog(
                    self,
                    lang.get("select_world.loading_world_failed"),
                    str(e),
                    traceback.format_exc(),
                )
                dialog.ShowModal()
                dialog.Destroy()
            else:
                self._open_worlds[path] = world
                self._add_world_tab(world, world.world_name)

    def _add_world_tab(self, page: BasePageUI, obj_name: str, select: bool = True):
        """Add a tab and enable it."""
        self.AddPage(page, obj_name, select)

    def close_level(self, path: str):
        """Close a given world and remove it from the notebook"""
        if path in self._open_worlds:
            world = self._open_worlds[path]
            # note we don't remove it from the dictionary here
            # delete page starts the deletion but it can be vetoed
            # it is deleted from the dictionary in _on_page_closing
            self.DeletePage(self.GetPageIndex(world))

    def _on_page_closing(self, evt: flatnotebook.EVT_FLATNOTEBOOK_PAGE_CLOSING):
        """Handle the page closing."""
        page = self.GetPage(evt.GetSelection())
        if page in (self._main_menu, self._open_world_page):
            evt.Veto()
            return

        if page.can_disable() and page.can_close():
            path = page.path
            page.disable()
            page.close()
            del self._open_worlds[path]
        else:
            evt.Veto()

    def _page_changing(self, evt: wx.BookCtrlEvent):
        old_selection_index = evt.GetOldSelection()
        if old_selection_index != wx.NOT_FOUND:
            old_page = self.GetPage(old_selection_index)
            if old_page is not None and not old_page.can_disable():
                evt.Veto()

    def _page_changed(self, evt: wx.BookCtrlEvent):
        """Handle the page changing."""
        if evt.GetOldSelection() != evt.GetSelection():
            if evt.GetOldSelection() != wx.NOT_FOUND:
                # self.GetPage(evt.GetOldSelection()).disable()
                old_page = self.GetPage(evt.GetOldSelection())
                if old_page is not None:
                    old_page.disable()

            if self.GetCurrentPage() is self._main_menu:
                self.SetAGWWindowStyleFlag(NOTEBOOK_MENU_STYLE)
            elif self.GetCurrentPage() is self._open_world_page:
                self.SetAGWWindowStyleFlag(NOTEBOOK_MENU_STYLE)
            else:
                self.SetAGWWindowStyleFlag(NOTEBOOK_STYLE)

        if self.GetCurrentPage() is not None:
            self.GetCurrentPage().enable()

    def on_app_close(self, evt: wx.CloseEvent):
        for path, page in list(self._open_worlds.items()):
            self.close_level(path)
        if self._open_worlds:
            wx.MessageBox(lang.get("app.world_still_used"))
        else:
            evt.Skip()

    def extend_menu(self, menu_dict: dict) -> dict:
        return self.GetCurrentPage().menu(menu_dict)
