import os
import glob
from sys import platform
from typing import List, Dict, Tuple, Callable, TYPE_CHECKING
import traceback
import logging
import zipfile

import wx

from amulet import load_format
from amulet.api.errors import FormatError

from amulet_map_editor import lang, CONFIG
from amulet_map_editor.api.bedrock_open_safety import prepare_bedrock_world_for_open
from amulet_map_editor.api.wx.ui import simple
from amulet_map_editor.api.wx.ui.traceback_dialog import TracebackDialog
from amulet_map_editor.api.wx.ui.open_world_routing import route_open_world_to_tab
from amulet_map_editor.api.wx.util.ui_preferences import preserve_ui_preferences
from amulet_map_editor.api.framework import app

if TYPE_CHECKING:
    from amulet.api.wrapper import WorldFormatWrapper

log = logging.getLogger(__name__)


def _make_tree_writable(path: str) -> None:
    if platform != "win32":
        return

    def _set_mode(target: str, mode: int) -> None:
        try:
            os.chmod(target, mode)
        except OSError:
            pass

    _set_mode(path, 0o777)
    for root, dirs, files in os.walk(path):
        for directory in dirs:
            _set_mode(os.path.join(root, directory), 0o777)
        for file_name in files:
            _set_mode(os.path.join(root, file_name), 0o666)


def _looks_like_world_root(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    checks = (
        os.path.isdir(os.path.join(path, "db")),
        os.path.isfile(os.path.join(path, "level.dat")),
        os.path.isfile(os.path.join(path, "levelname.txt")),
    )
    return any(checks)


def _resolve_extracted_mcworld_path(extract_dir: str) -> str:
    if _looks_like_world_root(extract_dir):
        return extract_dir

    children = []
    try:
        with os.scandir(extract_dir) as entries:
            for entry in entries:
                if entry.is_dir():
                    children.append(entry.path)
    except OSError:
        return extract_dir

    if len(children) == 1 and _looks_like_world_root(children[0]):
        return children[0]

    return extract_dir


def _is_valid_mcworld_archive(path: str) -> bool:
    """Return True if the selected .mcworld file is a valid zip archive."""
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


# Windows 	%APPDATA%\.minecraft
# macOS 	~/Library/Application Support/minecraft
# Linux 	~/.minecraft

minecraft_world_paths: list[tuple[str, str]] = []

if platform == "win32":
    minecraft_world_paths.append(
        (
            lang.get("world.java_platform"),
            os.path.join(os.getenv("APPDATA"), ".minecraft", "saves"),
        )
    )
    minecraft_world_paths.append(
        (
            lang.get("world.bedrock_uwp"),
            os.path.join(
                os.getenv("LOCALAPPDATA"),
                "Packages",
                "Microsoft.MinecraftUWP_8wekyb3d8bbwe",
                "LocalState",
                "games",
                "com.mojang",
                "minecraftWorlds",
            ),
        )
    )
    minecraft_world_paths.append(
        (
            lang.get("world.bedrock_uwp_beta"),
            os.path.join(
                os.getenv("LOCALAPPDATA"),
                "Packages",
                "Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe",
                "LocalState",
                "games",
                "com.mojang",
                "minecraftWorlds",
            ),
        )
    )
    minecraft_world_paths.append(
        (
            lang.get("world.bedrock_education_store"),
            os.path.join(
                os.getenv("LOCALAPPDATA"),
                "Packages",
                "Microsoft.MinecraftEducationEdition_8wekyb3d8bbwe",
                "LocalState",
                "games",
                "com.mojang",
                "minecraftWorlds",
            ),
        )
    )
    minecraft_world_paths.append(
        (
            lang.get("world.bedrock_education_desktop"),
            os.path.join(
                os.getenv("APPDATA"),
                "Minecraft Education Edition",
                "games",
                "com.mojang",
                "minecraftWorlds",
            ),
        )
    )
    minecraft_world_paths.append(
        (
            lang.get("world.bedrock_netease"),
            os.path.join(
                os.getenv("APPDATA"),
                "MinecraftPE_Netease",
                "minecraftWorlds",
            ),
        )
    )
    for group, key in (
        ("Minecraft Bedrock", "world.bedrock_gdk"),
        ("Minecraft Bedrock Preview", "world.bedrock_gdk_preview"),
    ):
        for worlds_path in glob.glob(
            os.path.join(
                glob.escape(os.getenv("APPDATA")),
                group,
                "Users",
                "*",
                "games",
                "com.mojang",
                "minecraftWorlds",
            )
        ):
            user_id = worlds_path.split(os.sep)[-4]
            minecraft_world_paths.append(
                (
                    f"{lang.get(key)} {user_id}",
                    worlds_path,
                )
            )

elif platform == "darwin":
    minecraft_world_paths.append(
        (
            lang.get("world.java_platform"),
            os.path.join(
                os.path.expanduser("~"),
                "Library",
                "Application Support",
                "minecraft",
                "saves",
            ),
        )
    )
elif platform == "linux":
    minecraft_world_paths.append(
        (
            lang.get("world.java_platform"),
            os.path.join(os.path.expanduser("~"), ".minecraft", "saves"),
        )
    )

world_images: Dict[str, Tuple[int, wx.Bitmap, int]] = {}


def get_world_image(image_path: str) -> Tuple[wx.Bitmap, int]:
    if (
        image_path not in world_images
        or world_images[image_path][0] != os.stat(image_path)[8]
    ):
        img = wx.Image(image_path, wx.BITMAP_TYPE_ANY)
        width = min(int((img.GetWidth() / img.GetHeight()) * 128), 300)

        world_images[image_path] = (
            os.stat(image_path)[8],
            img.Scale(width, 128, wx.IMAGE_QUALITY_NEAREST).ConvertToBitmap(),
            width,
        )

    return world_images[image_path][1:3]


class WorldUI(wx.Panel):
    """A Panel UI element with the world image, name and description"""

    def __init__(self, parent: wx.Window, world_format: "WorldFormatWrapper"):
        super().__init__(parent)
        self.SetWindowStyle(wx.TAB_TRAVERSAL | wx.BORDER_RAISED | wx.WANTS_CHARS)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(sizer)

        img, width = get_world_image(world_format.world_image_path)

        self.img = wx.StaticBitmap(self, wx.ID_ANY, img, (0, 0), (width, 128))
        sizer.Add(self.img)

        self.world_name = wx.StaticText(
            self,
            label="\n".join(
                [
                    world_format.level_name,
                    world_format.game_version_string,
                    os.path.join(
                        *os.path.normpath(world_format.path).split(os.sep)[-3:]
                    ),
                ]
            ),
        )
        sizer.Add(self.world_name, 0, wx.ALL | wx.ALIGN_CENTER, 5)


class WorldUIButton(WorldUI):
    """A Panel UI element that behaves like a button with the world image, name and description"""

    def __init__(
        self,
        parent: wx.Window,
        world_format: "WorldFormatWrapper",
        open_world_callback,
    ):
        super().__init__(parent, world_format)
        self.path = world_format.path
        self.open_world_callback = open_world_callback

        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        self.Bind(wx.EVT_LEFT_DOWN, self._set_focus)
        self.Bind(wx.EVT_LEFT_UP, self._call_callback)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

        self.img.Bind(wx.EVT_LEFT_DOWN, self._set_focus)
        self.img.Bind(wx.EVT_LEFT_UP, self._call_callback)
        self.world_name.Bind(wx.EVT_LEFT_DOWN, self._set_focus)
        self.world_name.Bind(wx.EVT_LEFT_UP, self._call_callback)

    def AcceptsFocusFromKeyboard(self) -> bool:
        return True

    def AcceptsFocus(self) -> bool:
        return True

    def _call_callback(self, evt):
        self.SetFocusIgnoringChildren()
        self.open_world_callback(self.path)

    def _set_focus(self, evt):
        self.SetFocusIgnoringChildren()
        evt.Skip()

    def _on_key_down(self, evt):
        key = evt.GetKeyCode()
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_SPACE):
            self.open_world_callback(self.path)
            return

        world_list = self.GetParent()
        if isinstance(world_list, WorldList):
            if key in (wx.WXK_UP, wx.WXK_NUMPAD_UP):
                world_list.focus_relative(self, -1)
                return
            if key in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN):
                world_list.focus_relative(self, 1)
                return

        evt.Skip()


class WorldList(wx.Panel):
    """A Panel containing zero or more `WorldUIButton`s."""

    def __init__(self, parent: wx.Window, world_dirs, open_world_callback, sort=True):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        self.worlds = []

        world_formats = []
        for world_path in world_dirs:
            if os.path.isdir(world_path):
                try:
                    world_formats.append(load_format(world_path))
                except FormatError as e:
                    log.debug(f"Could not find loader for {world_path} {e}")
                except Exception:
                    log.error(
                        f"Error loading format wrapper for {world_path} {traceback.format_exc()}"
                    )
        if sort:
            world_formats = reversed(sorted(world_formats, key=lambda f: f.last_played))

        for world_format in world_formats:
            try:
                world_button = WorldUIButton(self, world_format, open_world_callback)
                sizer.Add(
                    world_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5
                )
                self.worlds.append(world_button)
            except Exception as e:
                log.info(f"Failed to display world button for {world_format.path} {e}")

        self.Layout()

    def focus_relative(self, world_button: WorldUIButton, offset: int):
        if not self.worlds:
            return
        try:
            index = self.worlds.index(world_button)
        except ValueError:
            return
        new_index = max(0, min(len(self.worlds) - 1, index + offset))
        self.worlds[new_index].SetFocusIgnoringChildren()


class CollapsibleWorldListUI(wx.CollapsiblePane):
    """a drop down list of `WorldUIButton`s for a given directory"""

    def __init__(self, parent, paths: List[str], group_name: str, open_world_callback):
        super().__init__(parent, label=group_name)
        self.parent = parent
        self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.eval_layout)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

        panel = self.GetPane()
        panel.sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(panel.sizer)
        panel.sizer.Add(WorldList(panel, paths, open_world_callback), 0, wx.EXPAND)

    def eval_layout(self, evt):
        self.Layout()
        self.parent.FitInside()
        evt.Skip()


class ScrollableWorldsUI(simple.SimpleScrollablePanel):
    # a frame to allow scrolling
    def __init__(self, parent, open_world_callback):
        super(ScrollableWorldsUI, self).__init__(parent)
        self.open_world_callback = open_world_callback

        self.dirs: Dict[str, CollapsibleWorldListUI] = {}
        self.reload()

        self.Layout()

    def reload(self):
        for val in self.dirs.values():
            val.Destroy()
        self.dirs.clear()
        for group_name, directory in sorted(minecraft_world_paths, key=lambda x: x[0]):
            if os.path.isdir(directory):
                world_list = CollapsibleWorldListUI(
                    self,
                    glob.glob(os.path.join(glob.escape(directory), "*")),
                    group_name,
                    self.open_world_callback,
                )
                self.add_object(world_list, 0, wx.EXPAND)
                self.dirs[directory] = world_list

    def OnChildFocus(self, event):
        event.Skip()


class WorldSelectUI(wx.Panel):
    # a frame containing a refresh button for the UI, a sort order for the worlds
    # and a vertical list of `WorldDirectoryUI`s for each directory
    # perhaps also a select directory option
    def __init__(self, parent, open_world_callback):
        super().__init__(parent)
        self.open_world_callback = open_world_callback

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Wrap controls so both buttons remain reachable on narrow layouts.
        header_sizer = wx.WrapSizer(wx.HORIZONTAL)
        sizer.Add(header_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 2)

        self.header_open_world = wx.Button(
            self, label=lang.get("select_world.open_world_button")
        )
        font = self.header_open_world.GetFont()
        font.SetPointSize(16)
        self.header_open_world.SetFont(font)
        self.header_open_world.Bind(wx.EVT_BUTTON, self._open_world)
        header_sizer.Add(self.header_open_world, 0, wx.ALL, 4)

        self.header_open_mcworld = wx.Button(
            self, label=lang.get("select_world.open_mcworld_button")
        )
        font = self.header_open_mcworld.GetFont()
        font.SetPointSize(16)
        self.header_open_mcworld.SetFont(font)
        self.header_open_mcworld.Bind(wx.EVT_BUTTON, self._open_mcworld)
        header_sizer.Add(self.header_open_mcworld, 0, wx.ALL, 4)

        content = ScrollableWorldsUI(self, open_world_callback)
        sizer.Add(content, 1, wx.EXPAND)

    def focus_default_control(self):
        self.header_open_world.SetFocus()

    def _open_world(self, evt):
        dir_dialog = wx.DirDialog(
            None,
            lang.get("select_world.open_world_dialogue"),
            "",
            wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        try:
            if dir_dialog.ShowModal() == wx.ID_CANCEL:
                return
            path = dir_dialog.GetPath()
        except Exception:
            wx.LogError(lang.get("select_world.select_directory_failed"))
            return
        finally:
            dir_dialog.Destroy()
        self.open_world_callback(path)

    def _open_mcworld(self, evt):
        mcworld_dialog = wx.FileDialog(
            None,
            lang.get("select_world.open_mcworld_dialogue"),
            "",
            style=wx.FD_DEFAULT_STYLE | wx.FD_FILE_MUST_EXIST,
            wildcard="Bedrock world archive (*.mcworld)|*.mcworld",
        )
        try:
            if mcworld_dialog.ShowModal() == wx.ID_CANCEL:
                return
            mcworld_path = mcworld_dialog.GetPath()
        except Exception:
            wx.LogError(lang.get("select_world.select_directory_failed"))
            return
        finally:
            mcworld_dialog.Destroy()

        if not _is_valid_mcworld_archive(mcworld_path):
            wx.MessageBox(
                "The selected .mcworld file is not a valid archive. "
                "Please choose a valid Bedrock .mcworld export file.",
                "Invalid .mcworld file",
                wx.OK | wx.ICON_ERROR,
            )
            return

        dir_dialog = wx.DirDialog(
            None,
            lang.get("select_world.extract_mcworld_dialogue"),
            "",
            wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        try:
            if dir_dialog.ShowModal() == wx.ID_CANCEL:
                return
            extract_dir = dir_dialog.GetPath()
        except Exception:
            wx.LogError(lang.get("select_world.select_directory_failed"))
            return
        finally:
            dir_dialog.Destroy()

        if next(os.scandir(extract_dir), None) is not None:
            wx.LogError(lang.get("select_world.extracting_world_not_empty"))
            return

        busy_msg = wx.BusyInfo(lang.get("select_world.extracting_world_wait"))

        try:
            with zipfile.ZipFile(mcworld_path) as archive:
                archive.extractall(extract_dir)
            _make_tree_writable(extract_dir)
        except zipfile.BadZipFile:
            del busy_msg
            wx.MessageBox(
                "The selected .mcworld file is corrupted or not a zip archive.",
                "Invalid .mcworld file",
                wx.OK | wx.ICON_ERROR,
            )
            return
        except Exception as e:
            del busy_msg
            dialog = TracebackDialog(
                self,
                lang.get("select_world.extracting_world_failed"),
                str(e),
                traceback.format_exc(),
            )
            dialog.ShowModal()
            dialog.Destroy()
            return
        else:
            del busy_msg

        wx.MessageBox(lang.get("select_world.extracting_world_finished"), "Info", wx.OK)

        world_path = _resolve_extracted_mcworld_path(extract_dir)
        try:
            prepare_bedrock_world_for_open(world_path)
        except Exception:
            log.debug("Bedrock post-extract repair failed for %s", world_path, exc_info=True)
        self.open_world_callback(world_path)


class RecentWorldUI(wx.Panel):
    def __init__(self, parent, open_world_callback):
        super().__init__(parent)
        self._open_world_callback = open_world_callback

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        text = wx.StaticText(
            self,
            wx.ID_ANY,
            lang.get("select_world.recent_worlds"),
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        text.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self._sizer.Add(
            text,
            0,
            wx.ALL | wx.ALIGN_CENTER,
            5,
        )

        self._world_list = None
        self.rebuild()

    def rebuild(self, new_world: str = None):
        if new_world is not None:
            self._update_recent_worlds_config(new_world)

        meta: dict = CONFIG.get("amulet_meta", {})
        recent_worlds: list = meta.setdefault("recent_worlds", [])
        if self._world_list is not None:
            self._world_list.Destroy()
        self._world_list = WorldList(
            self, recent_worlds, self._open_world_callback, sort=False
        )
        self._sizer.Add(self._world_list, 1, wx.EXPAND, 5)
        self.Layout()

    @staticmethod
    def _update_recent_worlds_config(new_world: str):
        meta: dict = CONFIG.get("amulet_meta", {})
        recent_worlds: list = meta.setdefault("recent_worlds", [])
        while new_world in recent_worlds:
            recent_worlds.remove(new_world)
        recent_worlds.insert(0, new_world)
        while len(recent_worlds) > 5:
            recent_worlds.pop(5)
        CONFIG.put("amulet_meta", meta)


class WorldSelectAndRecentUI(wx.Panel):
    def __init__(self, parent, open_world_callback):
        super(WorldSelectAndRecentUI, self).__init__(parent, wx.HORIZONTAL)
        self._open_world_callback = open_world_callback

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        warning_text = wx.StaticText(
            self,
            label=lang.get("select_world.open_world_warning"),
        )
        warning_text.SetFont(wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        sizer.Add(warning_text, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 5)
        # bar

        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(bottom_sizer, 1, wx.EXPAND)

        left_sizer = wx.BoxSizer(wx.VERTICAL)
        bottom_sizer.Add(left_sizer, 1, wx.EXPAND)
        self._select_world = WorldSelectUI(self, self._update_recent)
        left_sizer.Add(self._select_world, 1, wx.ALL | wx.EXPAND, 5)

        right_sizer = wx.BoxSizer(wx.VERTICAL)
        bottom_sizer.Add(right_sizer, 1, wx.EXPAND)
        self._recent_worlds = RecentWorldUI(self, self._update_recent)
        right_sizer.Add(self._recent_worlds, 1, wx.EXPAND, 5)

    def _update_recent(self, path):
        # Avoid rebuilding the recent-world UI while opening a world.
        # Rebuild triggers load_format calls which can conflict with LevelDB world open.
        RecentWorldUI._update_recent_worlds_config(path)
        self._open_world_callback(path)

    def focus_default_control(self):
        self._select_world.focus_default_control()


@preserve_ui_preferences
class WorldSelectDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, open_world_callback: Callable[[str], None]):
        super().__init__(
            parent,
            title=lang.get("select_world.title"),
            pos=wx.Point(50, 50),
            size=wx.Size(*[int(s * 0.95) for s in parent.GetSize()]),
            style=wx.CAPTION | wx.CLOSE_BOX | wx.MAXIMIZE_BOX
            # | wx.MAXIMIZE
            | wx.SYSTEM_MENU | wx.TAB_TRAVERSAL | wx.CLIP_CHILDREN | wx.RESIZE_BORDER,
        )
        self.Bind(wx.EVT_CLOSE, self._hide_event)

        self._open_world_callback = open_world_callback
        self.world_select = WorldSelectAndRecentUI(self, self._run_callback)

    def _run_callback(self, path):
        self._close()
        self._open_world_callback(path)

    def _hide_event(self, evt):
        self._close()
        evt.Skip()

    def _close(self):
        if self.IsModal():
            self.EndModal(0)
        else:
            self.Close()


def open_level_from_dialog(parent: wx.Window):
    """Show the open-world tab when possible, otherwise fall back to a dialog."""
    if route_open_world_to_tab(parent):
        return

    select_world = WorldSelectDialog(parent, app.open_level)
    select_world.ShowModal()
    select_world.Destroy()
