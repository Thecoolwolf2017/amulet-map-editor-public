import logging
import os
import shutil
import warnings
import wx
from typing import Callable, TYPE_CHECKING, Any, Generator, Optional
from types import GeneratorType
from threading import RLock, Thread

from .base_edit_canvas import BaseEditCanvas
from ...edit import EDIT_CONFIG_ID
from ..key_config import (
    DefaultKeys,
    DefaultKeybindGroupId,
    PresetKeybinds,
    KeybindGroup,
)

import time
import traceback

from amulet.api.data_types import OperationReturnType, OperationYieldType, Dimension
from amulet.api.structure import structure_cache
from amulet.api.level import BaseLevel

from amulet_map_editor import CONFIG
from amulet_map_editor import close_level
from amulet_map_editor.api.wx.ui.traceback_dialog import TracebackDialog
from amulet_map_editor.programs.edit.api.ui.goto import show_goto
from amulet_map_editor.programs.edit.api.ui.tool_manager import ToolManagerSizer
from amulet_map_editor.programs.edit.api.operations.errors import (
    OperationError,
    OperationSilentAbort,
    BaseLoudException,
    BaseSilentException,
)
from amulet_map_editor.programs.edit.api.task_worker import TaskWorker
from amulet_map_editor.programs.edit.api.backup import (
    backup_root_dir,
    backups_enabled,
    iter_backup,
)
from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.internal_operations import (
    cut,
    copy,
    delete,
)

from amulet_map_editor.programs.edit.api.events import (
    UndoEvent,
    RedoEvent,
    CreateUndoEvent,
    SaveEvent,
    ToolChangeEvent,
    EVT_EDIT_CLOSE,
)
from amulet_map_editor.programs.edit.api.ui.file import FilePanel

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel

log = logging.getLogger(__name__)
OperationType = Callable[[], OperationReturnType]


def show_loading_dialog(
    run: OperationType, title: str, message: str, parent: wx.Window
) -> Any:
    warnings.warn("show_loading_dialog is depreciated.", DeprecationWarning)
    dialog = wx.ProgressDialog(
        title,
        message,
        maximum=10_000,
        parent=parent,
        style=wx.PD_APP_MODAL
        | wx.PD_ELAPSED_TIME
        | wx.PD_REMAINING_TIME
        | wx.PD_AUTO_HIDE,
    )
    dialog.Fit()
    t = time.time()
    try:
        obj = run()
        if isinstance(obj, GeneratorType):
            try:
                while True:
                    progress = next(obj)
                    if isinstance(progress, (list, tuple)):
                        if len(progress) >= 2:
                            message = progress[1]
                        if len(progress) >= 1:
                            progress = progress[0]
                    if isinstance(progress, (int, float)) and isinstance(message, str):
                        dialog.Update(
                            min(9999, max(0, int(progress * 10_000))), message
                        )
                    wx.Yield()
            except StopIteration as e:
                obj = e.value
    except Exception as e:
        dialog.Update(10_000)
        raise e
    time.sleep(max(0.2 - time.time() + t, 0))
    dialog.Update(10_000)
    return obj


class OperationThread(Thread):
    # The operation to run
    _operation: OperationType

    # Should the operation be stopped. Set externally
    stop: bool
    # The starting message for the progress dialog
    message: str
    # The operation progress (from 0-1)
    progress: float
    # The return value from the operation
    out: Any
    # The error raised if any
    error: Optional[BaseException]

    def __init__(self, operation: OperationType, message: str):
        super().__init__()
        self._operation = operation
        self.stop = False
        self.message = message
        self.progress = 0.0
        self.out = None
        self.error = None

    def run(self) -> None:
        t = time.time()
        try:
            obj = self._operation()
            if isinstance(obj, GeneratorType):
                try:
                    while True:
                        if self.stop:
                            raise OperationSilentAbort
                        progress = next(obj)
                        if isinstance(progress, (list, tuple)):
                            if len(progress) >= 2:
                                self.message = progress[1]
                            if len(progress) >= 1:
                                self.progress = progress[0]
                        elif isinstance(progress, (int, float)):
                            self.progress = progress
                except StopIteration as e:
                    self.out = e.value
        except BaseException as e:
            self.error = e
        time.sleep(max(0.2 - time.time() + t, 0))


class EditCanvas(BaseEditCanvas):
    def __init__(self, parent: wx.Window, world: "BaseLevel"):
        super().__init__(parent, world)
        self._file_panel: Optional[FilePanel] = None
        self._tool_sizer: Optional[ToolManagerSizer] = None
        self.buttons.register_actions(self.key_binds)

        self._canvas_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._canvas_sizer)

        # Tracks if an operation has been started and not finished.
        self._operation_running = False
        # This lock stops two threads from editing the world simultaneously
        # call run_operation to acquire it.
        self._edit_lock = RLock()

    def _init_opengl(self):
        super()._init_opengl()
        self._file_panel = FilePanel(self)
        self._canvas_sizer.Add(self._file_panel, 0, wx.EXPAND, 0)
        self._tool_sizer = ToolManagerSizer(self)
        self._canvas_sizer.Add(self._tool_sizer, 1, wx.EXPAND, 0)

    def bind_events(self):
        """Set up all events required to run.
        Note this will also bind subclass events."""
        self._tool_sizer.bind_events()
        # binding the tool events first will run them last so they can't accidentally block UI events.
        super().bind_events()
        self._file_panel.bind_events()
        self.Bind(EVT_EDIT_CLOSE, self._on_close)

    def enable(self):
        super().enable()
        self._tool_sizer.enable()

    def disable(self):
        super().disable()
        self._tool_sizer.disable()

    def _on_close(self, _):
        close_level(self.world.level_path)

    @property
    def tools(self):
        return self._tool_sizer.tools

    @property
    def key_binds(self) -> KeybindGroup:
        config_ = CONFIG.get(EDIT_CONFIG_ID, {})
        user_keybinds = config_.get("user_keybinds", {})
        group = config_.get("keybind_group", DefaultKeybindGroupId)
        if group in user_keybinds:
            return user_keybinds[group]
        elif group in PresetKeybinds:
            return PresetKeybinds[group]
        else:
            return DefaultKeys

    def _deselect(self):
        # TODO: Re-implement this
        self._tool_sizer.enable_default_tool()

    def run_operation(
        self,
        operation: OperationType,
        title="Amulet",
        msg="Running Operation",
        throw_exceptions=False,
    ) -> Any:
        try:
            out = self._run_operation(operation, title, msg, True)
        except BaseException as e:
            if throw_exceptions:
                raise e
        else:
            # If there were no errors create an undo point
            def create_undo():
                yield 0, "Creating Undo Point"
                yield from self.create_undo_point_iter()

            self._run_operation(create_undo, title, msg, False)

            return out

    def _run_operation(
        self,
        operation: OperationType,
        title: str,
        msg: str,
        cancelable: bool,
    ) -> Any:
        with self._edit_lock:
            if self._operation_running:
                raise Exception(
                    "run_operation cannot be called from within itself. "
                    "This function has already been called by parent code so you cannot run it again"
                )
            self._operation_running = True

            self.renderer.disable_threads()

            style = (
                wx.PD_APP_MODAL
                | wx.PD_ELAPSED_TIME
                | wx.PD_REMAINING_TIME
                | wx.PD_AUTO_HIDE
                | (wx.PD_CAN_ABORT * cancelable)
            )
            dialog = wx.ProgressDialog(
                title,
                msg,
                maximum=10_000,
                parent=self,
                style=style,
            )
            dialog.Fit()

            # Use shared worker to keep heavy work off the UI thread.
            task = TaskWorker.shared().submit(operation, msg)
            while not task.done:
                dialog.Update(
                    max(0, min(int(task.progress * 10_000), 9999)), task.message
                )
                wx.Yield()
                if dialog.WasCancelled():
                    task.cancel()
            # Ensure we reflect the final state.
            dialog.Update(max(0, min(int(task.progress * 10_000), 9999)), task.message)

            dialog.Destroy()
            wx.Yield()

            if task.error is not None:
                # If there is any kind of error restore the last undo point
                self.world.restore_last_undo_point()

                if isinstance(task.error, BaseLoudException):
                    msg = str(task.error)
                    if isinstance(task.error, OperationError):
                        msg = f"Error running operation: {msg}"
                    log.info(msg)
                    wx.MessageDialog(self, msg, style=wx.OK).ShowModal()
                elif isinstance(task.error, BaseSilentException):
                    pass
                elif isinstance(task.error, BaseException):
                    tb = "".join(
                        traceback.format_exception(
                            type(task.error), task.error, task.error.__traceback__
                        )
                    )
                    log.error(tb)
                    dialog = TracebackDialog(
                        self,
                        "Exception while running operation",
                        str(task.error),
                        tb,
                    )
                    dialog.ShowModal()
                    dialog.Destroy()
                    self.world.restore_last_undo_point()

            self.renderer.enable_threads()
            self.renderer.render_world.rebuild_changed()
            self._operation_running = False
            if task.error is not None:
                raise task.error
            return task.result

    def create_undo_point(self, world=True, non_world=True):
        self.world.create_undo_point(world, non_world)
        wx.PostEvent(self, CreateUndoEvent())

    def create_undo_point_iter(
        self, world=True, non_world=True
    ) -> Generator[float, None, bool]:
        result = yield from self.world.create_undo_point_iter(world, non_world)
        wx.PostEvent(self, CreateUndoEvent())
        return result

    def undo(self):
        self.world.undo()
        self.renderer.render_world.rebuild_changed()
        wx.PostEvent(self, UndoEvent())

    def redo(self):
        self.world.redo()
        self.renderer.render_world.rebuild_changed()
        wx.PostEvent(self, RedoEvent())

    def cut(self):
        self.run_operation(
            lambda: cut(self.world, self.dimension, self.selection.selection_group)
        )

    def copy(self):
        self.run_operation(
            lambda: copy(self.world, self.dimension, self.selection.selection_group)
        )

    def paste(self, structure: BaseLevel, dimension: Dimension):
        assert isinstance(
            structure, BaseLevel
        ), "Structure given is not a subclass of BaseLevel."
        assert (
            dimension in structure.dimensions
        ), "The requested dimension does not exist for this object."
        wx.PostEvent(
            self,
            ToolChangeEvent(
                tool="Paste", state={"structure": structure, "dimension": dimension}
            ),
        )

    def paste_from_cache(self):
        if structure_cache:
            self.paste(*structure_cache.get_structure())
        else:
            wx.MessageBox("A structure needs to be copied before one can be pasted.")

    def delete(self):
        self.run_operation(
            lambda: delete(self.world, self.dimension, self.selection.selection_group)
        )

    def goto(self):
        location = show_goto(self, *self.camera.location)
        if location:
            self.camera.location = location

    def select_all(self):
        all_chunk_coords = tuple(self.world.all_chunk_coords(self.dimension))
        if all_chunk_coords:
            min_x, min_z = max_x, max_z = all_chunk_coords[0]
            for x, z in all_chunk_coords:
                if x < min_x:
                    min_x = x
                elif x > max_x:
                    max_x = x
                if z < min_z:
                    min_z = z
                elif z > max_z:
                    max_z = z

            self.selection.selection_corners = [
                (
                    (
                        min_x * self.world.sub_chunk_size,
                        self.world.bounds(self.dimension).min[1],
                        min_z * self.world.sub_chunk_size,
                    ),
                    (
                        (max_x + 1) * self.world.sub_chunk_size,
                        self.world.bounds(self.dimension).max[1],
                        (max_z + 1) * self.world.sub_chunk_size,
                    ),
                )
            ]

        else:
            self.selection.selection_corners = []

    @staticmethod
    def _can_write_to_directory(path: str) -> bool:
        os.makedirs(path, exist_ok=True)
        probe_path = os.path.join(path, f".write_probe_{os.getpid()}")
        with open(probe_path, "w", encoding="utf-8") as probe:
            probe.write("ok")
        os.remove(probe_path)
        return True

    def _pre_save_validation_errors(self) -> list[str]:
        errors: list[str] = []
        world_path = self.world.level_path

        if not world_path:
            errors.append("The world path is missing.")
            return errors

        world_path = os.path.abspath(world_path)
        if not os.path.exists(world_path):
            errors.append(f"World path does not exist: {world_path}")
            return errors

        try:
            if not tuple(self.world.dimensions):
                errors.append("World has no dimensions available to save.")
        except Exception as exc:
            errors.append(f"Could not read world dimensions: {exc}")

        write_dir = (
            world_path if os.path.isdir(world_path) else os.path.dirname(world_path)
        )
        if not write_dir:
            write_dir = "."
        try:
            self._can_write_to_directory(write_dir)
        except Exception as exc:
            errors.append(f"No write access to world directory: {exc}")

        try:
            disk_info = shutil.disk_usage(write_dir)
            if disk_info.free < 128 * 1024 * 1024:
                errors.append("Not enough free disk space (minimum 128MB required).")
        except Exception as exc:
            errors.append(f"Could not check disk space: {exc}")

        if backups_enabled():
            try:
                self._can_write_to_directory(backup_root_dir())
            except Exception as exc:
                errors.append(f"Backup directory is not writable: {exc}")

        return errors

    def _show_validation_errors(self, errors: list[str]) -> None:
        msg = "Save was blocked because validation failed:\n\n" + "\n".join(
            f"- {entry}" for entry in errors
        )
        dialog = wx.MessageDialog(
            self,
            msg,
            "Save Validation Failed",
            style=wx.OK | wx.ICON_ERROR,
        )
        dialog.ShowModal()
        dialog.Destroy()

    def _show_save_error(self, error: BaseException) -> None:
        message = str(error).strip() or type(error).__name__
        dialog = wx.MessageDialog(
            self,
            f"Saving failed:\n{message}\n\nNo changes were committed without an explicit save.",
            "Save Failed",
            style=wx.OK | wx.ICON_ERROR,
        )
        dialog.ShowModal()
        dialog.Destroy()

    def _show_save_success(
        self, world_path: str, backup_path: str, backup_status: str
    ) -> None:
        details = [f"World saved successfully.\n\nPath:\n{world_path}"]

        if backups_enabled():
            details.append(f"Backup status:\n{backup_status}")
            if backup_path:
                details.append(f"Backup path:\n{backup_path}")
            else:
                details.append("Backup path:\nNo backup path was recorded.")
        else:
            details.append("Backup status:\nBackups are disabled in settings.")

        dialog = wx.MessageDialog(
            self,
            "\n\n".join(details),
            "Save Complete",
            style=wx.OK | wx.ICON_INFORMATION,
        )
        dialog.ShowModal()
        dialog.Destroy()

    def save(self):
        validation_errors = self._pre_save_validation_errors()
        if validation_errors:
            self._show_validation_errors(validation_errors)
            return

        backup_message = (
            "A backup will be created first."
            if backups_enabled()
            else "Backups are currently disabled in settings."
        )

        confirm = wx.MessageDialog(
            self,
            f"Saving will write changes to disk. {backup_message}\nContinue?",
            "Confirm Save",
            style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        if confirm.ShowModal() != wx.ID_YES:
            confirm.Destroy()
            return
        confirm.Destroy()

        backup_path = ""
        backup_status = "Backups are disabled in settings."
        if self.world.level_path:
            if backups_enabled():
                backup_status_result = {"message": "Backup did not run."}

                def backup_operation() -> Generator[OperationYieldType, None, str]:
                    backup_iter = iter_backup(self.world.level_path, "pre-save")
                    try:
                        while True:
                            progress = next(backup_iter)
                            if (
                                isinstance(progress, (tuple, list))
                                and len(progress) >= 2
                                and isinstance(progress[1], str)
                            ):
                                backup_status_result["message"] = progress[1]
                            yield progress
                    except StopIteration as stop:
                        return stop.value

                try:
                    backup_path = self._run_operation(
                        backup_operation,
                        "Creating Backup",
                        "Please wait.",
                        True,
                    )
                    backup_status = backup_status_result["message"]
                except OperationSilentAbort:
                    return
                except BaseException as exc:
                    self._show_save_error(exc)
                    return
            else:
                backup_status = "Backups are disabled in settings."

        def pre_save() -> Generator[OperationYieldType, None, Any]:
            yield 0, "Running Pre-Save Operations."
            pre_save_op = self.world.pre_save_operation()
            try:
                while True:
                    yield next(pre_save_op)
            except StopIteration as e:
                if e.value:
                    yield from self.create_undo_point_iter()
                else:
                    self.world.restore_last_undo_point()

        def save() -> Generator[OperationYieldType, None, Any]:
            yield 0, "Saving Chunks."
            for chunk_index, chunk_count in self.world.save_iter():
                yield chunk_index / chunk_count

        try:
            self._run_operation(
                pre_save, "Running Pre-Save Operations.", "Please wait.", False
            )
            self._run_operation(save, "Saving world.", "Please wait.", False)
            wx.PostEvent(self, SaveEvent())
            self._show_save_success(self.world.level_path, backup_path, backup_status)
        except BaseException as exc:
            if backup_path:
                log.error(
                    "Save failed after backup creation. Latest backup path: %s",
                    backup_path,
                )
            self._show_save_error(exc)
