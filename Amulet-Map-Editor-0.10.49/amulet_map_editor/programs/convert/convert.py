import wx
import os
import shutil
from threading import Thread
import webbrowser
import logging
from typing import TYPE_CHECKING, Optional

from amulet import load_format
from amulet.api.level import BaseLevel

from amulet_map_editor import lang
from amulet_map_editor.api.wx.ui.simple import SimplePanel, SimpleScrollablePanel
from amulet_map_editor.api.wx.ui.select_world import WorldSelectDialog, WorldUI
from amulet_map_editor.api.datatypes import MenuData
from amulet_map_editor.api.framework.programs import BaseProgram
from amulet_map_editor import close_level
from amulet_map_editor.programs.edit.api.backup import (
    commit_staging_path,
    create_staging_copy,
    iter_backup,
)
from amulet_map_editor.programs.edit.api.task_worker import TaskWorker

if TYPE_CHECKING:
    from amulet.api.wrapper import WorldFormatWrapper

log = logging.getLogger(__name__)


class ConvertExtension(SimpleScrollablePanel, BaseProgram):
    def __init__(self, container, world: BaseLevel):
        super().__init__(container)
        self._thread: Optional[Thread] = None
        self.world = world

        self._close_world_button = wx.Button(
            self, wx.ID_ANY, label=lang.get("world.close_world")
        )
        self._close_world_button.Bind(wx.EVT_BUTTON, self._close_world)
        self.add_object(self._close_world_button, 0, wx.ALL | wx.CENTER)

        self._input = SimplePanel(self, wx.HORIZONTAL)
        self.add_object(self._input, 0, wx.ALL | wx.CENTER)
        self._input.add_object(
            wx.StaticText(
                self._input,
                wx.ID_ANY,
                lang.get("program_convert.input_world"),
                wx.DefaultPosition,
                wx.DefaultSize,
                0,
            ),
            0,
            wx.ALL | wx.CENTER,
        )
        self._input.add_object(
            WorldUI(self._input, self.world.level_wrapper), 0, wx.ALL | wx.CENTER
        )

        self._output = SimplePanel(self, wx.HORIZONTAL)
        self.add_object(self._output, 0, wx.ALL | wx.CENTER)
        self._output.add_object(
            wx.StaticText(
                self._output,
                wx.ID_ANY,
                lang.get("program_convert.output_world"),
                wx.DefaultPosition,
                wx.DefaultSize,
                0,
            ),
            0,
            wx.ALL | wx.CENTER,
        )

        self._select_output_button = wx.Button(
            self, wx.ID_ANY, label=lang.get("program_convert.select_output_world")
        )
        self._select_output_button.Bind(wx.EVT_BUTTON, self._show_world_select)
        self.add_object(self._select_output_button, 0, wx.ALL | wx.CENTER)

        self._convert_bar = SimplePanel(self, wx.HORIZONTAL)
        self.add_object(self._convert_bar, 0, wx.ALL | wx.CENTER)

        self.loading_bar = wx.Gauge(
            self._convert_bar,
            wx.ID_ANY,
            100,
            wx.DefaultPosition,
            wx.DefaultSize,
            wx.GA_HORIZONTAL,
        )
        self._convert_bar.add_object(self.loading_bar, options=wx.ALL | wx.EXPAND)
        self.loading_bar.SetValue(0)

        self.convert_button = wx.Button(
            self._convert_bar,
            wx.ID_ANY,
            label=lang.get("program_convert.convert_button"),
        )
        self._convert_bar.add_object(self.convert_button)
        self.convert_button.Bind(wx.EVT_BUTTON, self._convert_event)

        self.preview_button = wx.Button(
            self._convert_bar, wx.ID_ANY, label="Preview Conversion"
        )
        self._convert_bar.add_object(self.preview_button)
        self.preview_button.Bind(wx.EVT_BUTTON, self._preview_event)

        self.out_world_path = None

    def menu(self, menu: MenuData) -> MenuData:
        menu.setdefault(lang.get("menu_bar.help.menu_name"), {}).setdefault(
            "control", {}
        ).setdefault(
            lang.get("program_convert.menu_bar.help.user_guide"),
            lambda evt: self._help_controls(),
        )
        return menu

    def _help_controls(self):
        webbrowser.open(
            "https://github.com/Amulet-Team/Amulet-Map-Editor/blob/master/amulet_map_editor/programs/convert/readme.md"
        )

    def _show_world_select(self, evt):
        select_world = WorldSelectDialog(self, self._output_world_callback)
        select_world.ShowModal()
        select_world.Destroy()

    def _output_world_callback(self, path):
        if path == self.world.level_path:
            wx.MessageBox(lang.get("program_convert.input_output_must_different"))
            return
        try:
            out_world_format = load_format(path)
            self.out_world_path = path

        except Exception:
            return

        for child in list(self._output.GetChildren())[1:]:
            child.Destroy()
        self._output.add_object(WorldUI(self._output, out_world_format), 0)
        self._output.Layout()
        self._output.Fit()
        self.Layout()
        # self.Fit()

    def _update_loading_bar(self, chunk_index, chunk_total):
        wx.CallAfter(self.loading_bar.SetValue, int(100 * chunk_index / chunk_total))

    def _convert_event(self, evt):
        if self.out_world_path is None:
            wx.MessageBox(lang.get("program_convert.select_before_converting"))
            return
        confirm = wx.MessageDialog(
            self,
            "This will write to the output world.\nA backup will be created if it exists.\nContinue?",
            "Confirm Conversion",
            style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        if confirm.ShowModal() != wx.ID_YES:
            confirm.Destroy()
            return
        confirm.Destroy()
        self.convert_button.Disable()
        self._thread = Thread(target=self._convert_method)
        self._thread.start()

    def _preview_event(self, evt):
        if self.out_world_path is None:
            wx.MessageBox(lang.get("program_convert.select_before_converting"))
            return

        def build_preview():
            summary = []
            summary.append(f"Input: {self.world.level_path}")
            summary.append(f"Output: {self.out_world_path}")
            summary.append("")
            summary.append("Dimensions:")
            dims = list(self.world.dimensions)
            total_chunks = 0
            for index, dim in enumerate(dims, start=1):
                coords = list(self.world.all_chunk_coords(dim))
                count = len(coords)
                total_chunks += count
                yield index / max(len(dims), 1), f"Scanning {dim}"
                summary.append(f"- {dim}: {count} chunks")
            summary.append("")
            summary.append(f"Total chunks: {total_chunks}")
            summary.append("No changes were made. This is a dry-run preview.")
            return "\n".join(summary)

        dialog = wx.ProgressDialog(
            "Building Preview",
            "Please wait.",
            maximum=10_000,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_AUTO_HIDE,
        )
        dialog.Fit()
        task = TaskWorker.shared().submit(build_preview, "Preview")
        while not task.done:
            dialog.Update(max(0, min(int(task.progress * 10_000), 9999)), task.message)
            wx.Yield()
        dialog.Destroy()

        if task.error is not None:
            wx.MessageBox(f"Preview failed:\n{task.error}")
            return
        wx.MessageBox(task.result)

    def _convert_method(self):
        staging_out_world_path = None

        def _save_into_output(output_path: str):
            out_world = load_format(output_path)
            log.info(f"Converting world {self.world.level_path} to {out_world.path}")
            out_world: WorldFormatWrapper
            out_world.open()
            try:
                self.world.save(out_world, self._update_loading_bar)
            finally:
                out_world.close()

        try:
            if os.path.exists(self.out_world_path):
                for progress, _ in iter_backup(
                    self.out_world_path, "pre-convert output"
                ):
                    self._update_loading_bar(int(progress * 100), 100)

            if os.path.exists(self.out_world_path):
                # Convert in a staged copy first so failed writes do not touch the live output world.
                staging_out_world_path = create_staging_copy(
                    self.out_world_path, "convert"
                )
                _save_into_output(staging_out_world_path)
                commit_staging_path(staging_out_world_path, self.out_world_path)
                staging_out_world_path = None
            else:
                _save_into_output(self.out_world_path)

            message = lang.get("program_convert.conversion_completed")
            log.info(
                f"Finished converting world {self.world.level_path} to {self.out_world_path}"
            )
        except Exception as e:
            message = f"Error during conversion\n{e}"
            log.error(message, exc_info=True)
        finally:
            if staging_out_world_path and os.path.exists(staging_out_world_path):
                if os.path.isdir(staging_out_world_path):
                    shutil.rmtree(staging_out_world_path, ignore_errors=True)
                else:
                    try:
                        os.remove(staging_out_world_path)
                    except OSError:
                        pass
        self._update_loading_bar(0, 100)
        self._thread = None
        self.convert_button.Enable()
        wx.MessageBox(message)

    def can_close(self):
        if self._thread is not None:
            log.info(
                f"World {self.world.level_path} is still being converted. Please let it finish before closing"
            )
            return False
        return True

    def _close_world(self, evt):
        close_level(self.world.level_path)
