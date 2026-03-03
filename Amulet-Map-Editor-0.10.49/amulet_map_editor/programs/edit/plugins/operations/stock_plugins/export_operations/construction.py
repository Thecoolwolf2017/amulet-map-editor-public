from typing import TYPE_CHECKING
import logging
import wx
import os

from amulet.api.selection import SelectionGroup
from amulet.api.errors import ChunkLoadError
from amulet.api.data_types import Dimension, OperationReturnType
from amulet.level.formats.construction import ConstructionFormatWrapper

from amulet_map_editor.api.wx.ui.version_select import VersionSelect
from amulet_map_editor.programs.edit.api.operations import (
    SimpleOperationPanel,
    OperationError,
)
from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.export_operations.custom_block_remap import (
    remap_chunk_for_export,
)
from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.export_operations.remap_ui import (
    ExportRemapWorkflowMixin,
)

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


log = logging.getLogger(__name__)


class ExportConstruction(ExportRemapWorkflowMixin, SimpleOperationPanel):
    def __init__(
        self,
        parent: wx.Window,
        canvas: "EditCanvas",
        world: "BaseLevel",
        options_path: str,
    ):
        SimpleOperationPanel.__init__(self, parent, canvas, world, options_path)

        options = self._load_options({})

        self._path = options.get("path", "")

        self._version_define = VersionSelect(
            self,
            world.translation_manager,
            options.get("platform", None) or world.level_wrapper.platform,
            allow_universal=False,
        )
        self._sizer.Add(self._version_define, 0, wx.ALL | wx.EXPAND, 5)

        self._init_export_remap_workflow()
        self._add_run_button("Export")
        self.Layout()

    def disable(self):
        self._save_options(
            {
                "path": self._path,
                "platform": self._version_define.platform,
                "version": self._version_define.version_number,
            }
        )

    def _pre_operation(self) -> bool:
        try:
            path = os.path.realpath(self._path)
            fname = os.path.basename(path)
            fdir = os.path.dirname(path)
        except:
            fname = ""
            fdir = ""
        with wx.FileDialog(
            self,
            "Select Save Location",
            defaultDir=fdir,
            defaultFile=fname,
            wildcard="Construction file (*.construction)|*.construction",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return False
            self._path = file_dialog.GetPath()
        return self._confirm_pre_export_preview()

    def _operation(
        self, world: "BaseLevel", dimension: Dimension, selection: SelectionGroup
    ) -> OperationReturnType:
        path = self._path
        platform = self._version_define.platform
        version = self._version_define.version_number
        if isinstance(path, str) and platform and version:
            wrapper = ConstructionFormatWrapper(path)
            wrapper.create_and_open(platform, version, selection, True)
            wrapper.translation_manager = world.translation_manager
            wrapper_dimension = wrapper.dimensions[0]
            chunk_count = len(list(selection.chunk_locations()))
            remap_rules = self._consume_prepared_remap_rules(dimension, selection)
            remap_total = 0
            remap_chunks = 0
            yield 0, f"Exporting {os.path.basename(path)}"
            for chunk_index, (cx, cz) in enumerate(selection.chunk_locations()):
                try:
                    chunk = world.get_chunk(cx, cz, dimension)
                    export_chunk, replaced = remap_chunk_for_export(chunk, remap_rules)
                    if replaced:
                        remap_total += replaced
                        remap_chunks += 1
                    wrapper.commit_chunk(export_chunk, wrapper_dimension)
                except ChunkLoadError:
                    continue
                yield (chunk_index + 1) / chunk_count
            if remap_total:
                log.info(
                    "Export block remap replaced %s blocks across %s chunk(s). Table: %s",
                    remap_total,
                    remap_chunks,
                    remap_rules.path,
                )
            wrapper.save()
            wrapper.close()
        else:
            raise OperationError(
                "Please specify a save location and version in the options before running."
            )


export = {
    "name": "\tExport Construction",  # the name of the plugin
    "operation": ExportConstruction,  # the UI class to display
}
