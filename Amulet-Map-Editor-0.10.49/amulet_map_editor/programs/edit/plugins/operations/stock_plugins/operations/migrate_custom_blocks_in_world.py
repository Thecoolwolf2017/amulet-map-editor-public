from typing import TYPE_CHECKING
import logging
import os
import wx

from amulet.api.selection import SelectionGroup
from amulet.api.data_types import Dimension, OperationReturnType

from amulet_map_editor.programs.edit.api.backup import iter_backup
from amulet_map_editor.programs.edit.api.operations import (
    OperationError,
    SimpleOperationPanel,
)
from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.export_operations.custom_block_remap import (
    migrate_selection_in_world,
)
from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.export_operations.remap_ui import (
    ExportRemapWorkflowMixin,
)

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


log = logging.getLogger(__name__)


class MigrateCustomBlocksInWorld(ExportRemapWorkflowMixin, SimpleOperationPanel):
    def __init__(
        self,
        parent: wx.Window,
        canvas: "EditCanvas",
        world: "BaseLevel",
        options_path: str,
    ):
        SimpleOperationPanel.__init__(self, parent, canvas, world, options_path)

        self._sizer.Add(
            wx.StaticText(
                self,
                label=(
                    "Apply custom-block remaps directly to the current world selection.\n"
                    "A safety backup is created automatically before migration."
                ),
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            5,
        )

        self._init_export_remap_workflow()
        self._add_run_button("Migrate In-World")
        self.Layout()

    def _remap_preview_title(self) -> str:
        return "In-World Remap Preview"

    def _remap_confirm_title(self) -> str:
        return "Confirm In-World Migration"

    def _remap_primary_action_label(self) -> str:
        return "Apply Migration"

    def _pre_operation(self) -> bool:
        if not self.world.level_path:
            wx.MessageBox(
                "Migration requires a world with a valid path.",
                "Migration Blocked",
                wx.OK | wx.ICON_ERROR,
            )
            return False
        if len(self.canvas.selection.selection_group.selection_boxes) == 0:
            wx.MessageBox(
                "Select an area before running in-world migration.",
                "No Selection",
                wx.OK | wx.ICON_WARNING,
            )
            return False
        return self._confirm_pre_export_preview()

    def _operation(
        self, world: "BaseLevel", dimension: Dimension, selection: SelectionGroup
    ) -> OperationReturnType:
        if len(selection.selection_boxes) == 0:
            raise OperationError("No selection was given.")

        world_path = os.path.abspath(world.level_path or "")
        if not world_path or not os.path.exists(world_path):
            raise OperationError(
                "World path is not available or no longer exists. Migration aborted."
            )

        backup_status = "Backup did not run."
        backup_path = ""
        backup_iter = iter_backup(world_path, "pre-in-world-remap", force=True)
        try:
            while True:
                progress, message = next(backup_iter)
                backup_status = message
                yield (max(0.0, min(progress, 1.0)) * 0.25, message)
        except StopIteration as stop:
            backup_path = stop.value or ""

        if not backup_path:
            raise OperationError(
                "Migration aborted because a safety backup could not be created."
            )

        yield 0.25, "Preparing remap rules"
        remap_rules = self._consume_prepared_remap_rules(dimension, selection)

        yield 0.3, "Applying remaps to selected chunks"
        result = migrate_selection_in_world(world, dimension, selection, remap_rules)
        yield 1.0, "Migration complete"

        log.info(
            "In-world migration complete. remapped_blocks=%s remapped_chunks=%s "
            "scanned_chunks=%s failed_chunks=%s backup=%s backup_status=%s remap_table=%s",
            result.remapped_blocks,
            result.remapped_chunks,
            result.scanned_chunks,
            result.failed_chunks,
            backup_path,
            backup_status,
            remap_rules.path,
        )


export = {
    "name": "Migrate Custom Blocks In-World",
    "operation": MigrateCustomBlocksInWorld,
}
