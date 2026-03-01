"""
This license applies to this file only.
-- begin license --
MIT License
Copyright (c) 2021 Amulet-Team
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-- end license --
"""

from typing import TYPE_CHECKING, Tuple, List
import wx
import numpy

from amulet.api.block import Block

from amulet_map_editor.api.wx.ui.base_select import EVT_PICK
from amulet_map_editor.api.wx.ui.block_select import BlockDefine, MultiBlockDefine
from amulet_map_editor.api.wx.ui.simple import SimpleScrollablePanel
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from .replace_filters import (
    MATCH_MODE_ANY_OF,
    MATCH_MODE_NONE_OF,
    match_mode_replace_mask,
)

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


MATCH_MODE_LABELS = {
    MATCH_MODE_ANY_OF: "Any Of (replace listed blocks)",
    MATCH_MODE_NONE_OF: "None Of (replace blocks not listed)",
}
MATCH_MODE_FROM_LABEL = {label: mode for mode, label in MATCH_MODE_LABELS.items()}


class Replace(SimpleScrollablePanel, DefaultOperationUI):
    def __init__(
        self,
        parent: wx.Window,
        canvas: "EditCanvas",
        world: "BaseLevel",
        options_path: str,
    ):
        SimpleScrollablePanel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()
        options = self._load_options({})
        self._original_pick_target = None

        original_blocks_options = options.get("original_blocks_options")
        if not original_blocks_options:
            legacy_original_block = options.get("original_block_options")
            if legacy_original_block:
                original_blocks_options = [legacy_original_block]

        self._match_mode = wx.Choice(
            self, choices=[MATCH_MODE_LABELS[mode] for mode in MATCH_MODE_LABELS]
        )
        self._match_mode.SetStringSelection(
            MATCH_MODE_LABELS.get(
                options.get("match_mode", MATCH_MODE_ANY_OF),
                MATCH_MODE_LABELS[MATCH_MODE_ANY_OF],
            )
        )
        self._sizer.Add(
            self._match_mode, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 5
        )

        self._original_blocks = MultiBlockDefine(
            self,
            world.level_wrapper.translation_manager,
            block_define_kwargs={
                "platform": world.level_wrapper.platform,
                "wildcard_properties": True,
                "show_pick_block": True,
            },
        )
        self._load_original_blocks_options(original_blocks_options)
        self._sizer.Add(self._original_blocks, 1, wx.ALL | wx.EXPAND, 5)
        self._original_blocks.Bind(EVT_PICK, self._on_pick_original_block)
        self._replacement_block = BlockDefine(
            self,
            world.level_wrapper.translation_manager,
            wx.VERTICAL,
            *(
                options.get("replacement_block_options", [])
                or [world.level_wrapper.platform]
            ),
            show_pick_block=True
        )
        self._sizer.Add(self._replacement_block, 1, wx.ALL | wx.EXPAND, 5)
        self._replacement_block.Bind(
            EVT_PICK, lambda evt: self._on_pick_block_button(2)
        )

        self._run_button = wx.Button(self, label="Run Operation")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        self._sizer.Add(
            self._run_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5
        )

        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (1,)

    def _get_original_blocks_options(self) -> List[tuple]:
        return [
            (
                block_define.platform,
                block_define.version_number,
                block_define.force_blockstate,
                block_define.namespace,
                block_define.block_name,
                block_define.str_properties,
            )
            for block_define in self._original_blocks.get_block_defines()
        ]

    def _load_original_blocks_options(self, original_blocks_options):
        if not original_blocks_options:
            return
        while len(self._original_blocks.get_block_defines()) < len(original_blocks_options):
            self._original_blocks.add_block_define()
        for block_define, block_options in zip(
            self._original_blocks.get_block_defines(), original_blocks_options
        ):
            if not isinstance(block_options, (list, tuple)) or len(block_options) != 6:
                continue
            (
                platform,
                version_number,
                force_blockstate,
                namespace,
                block_name,
                str_properties,
            ) = block_options
            block_define.platform = platform
            if isinstance(version_number, (list, tuple)):
                block_define.version_number = tuple(version_number)
            block_define.force_blockstate = bool(force_blockstate)
            block_define.namespace = namespace
            block_define.block_name = block_name
            block_define.str_properties = str_properties

    def _get_match_mode(self) -> str:
        return MATCH_MODE_FROM_LABEL.get(
            self._match_mode.GetString(self._match_mode.GetSelection()),
            MATCH_MODE_ANY_OF,
        )

    def _on_pick_original_block(self, evt):
        widget = getattr(evt, "widget", None)
        block_define = widget.GetParent() if widget is not None else None
        if isinstance(block_define, BlockDefine):
            self._original_pick_target = block_define
        self._show_pointer = 1
        evt.Skip()

    def _on_pick_block_button(self, code):
        """Set up listening for the block click"""
        self._show_pointer = code

    def _on_box_click(self):
        if self._show_pointer:
            x, y, z = self._pointer.pointer_base
            if self._show_pointer == 1:
                target = self._original_pick_target
                if target is None:
                    block_defines = self._original_blocks.get_block_defines()
                    target = block_defines[0] if block_defines else None
                if target is not None:
                    target.universal_block = (
                        self.world.get_block(x, y, z, self.canvas.dimension),
                        None,
                    )
                self._original_pick_target = None
            elif self._show_pointer == 2:
                self._replacement_block.universal_block = (
                    self.world.get_block(x, y, z, self.canvas.dimension),
                    None,
                )
            self._show_pointer = False

    def _get_replacement_block(self) -> Block:
        return self._replacement_block.universal_block[0]

    def disable(self):
        original_blocks_options = self._get_original_blocks_options()
        options = {
            "original_blocks_options": original_blocks_options,
            "match_mode": self._get_match_mode(),
            "replacement_block": self._get_replacement_block(),
            "replacement_block_options": (
                self._replacement_block.platform,
                self._replacement_block.version_number,
                self._replacement_block.force_blockstate,
                self._replacement_block.namespace,
                self._replacement_block.block_name,
                self._replacement_block.str_properties,
            ),
        }
        if original_blocks_options:
            # Keep the legacy key for backwards compatibility with older option readers.
            options["original_block_options"] = original_blocks_options[0]
        self._save_options(options)

    def _run_operation(self, _):
        self.canvas.run_operation(self._replace)

    def _replace(self):
        world = self.world
        selection = self.canvas.selection.selection_group
        dimension = self.canvas.dimension

        match_mode = self._get_match_mode()
        original_blocks_options = self._get_original_blocks_options()
        replacement_block, block_entity = self._replacement_block.universal_block

        replacement_block_id = world.block_palette.get_add_block(replacement_block)

        original_block_matches = []
        universal_block_count = 0

        iter_count = len(list(world.get_coord_box(dimension, selection)))
        count = 0

        for chunk, slices, _ in world.get_chunk_slice_box(dimension, selection):
            if universal_block_count < len(world.block_palette):
                for universal_block_id in range(
                    universal_block_count, len(world.block_palette)
                ):
                    if self._block_matches_any(
                        world,
                        world.block_palette[universal_block_id],
                        original_blocks_options,
                    ):
                        original_block_matches.append(universal_block_id)

                universal_block_count = len(world.block_palette)
            blocks = chunk.blocks[slices]
            replace_mask = match_mode_replace_mask(
                blocks, original_block_matches, match_mode
            )
            blocks[replace_mask] = replacement_block_id
            chunk.blocks[slices] = blocks

            chunk_x, chunk_z = chunk.coordinates
            chunk_x *= 16
            chunk_z *= 16
            x_min = chunk_x + slices[0].start
            y_min = slices[1].start
            z_min = chunk_z + slices[2].start

            for dx, dy, dz in numpy.argwhere(replace_mask):
                x = int(x_min * dx)
                y = int(y_min * dy)
                z = int(z_min * dz)
                coord = (x, y, z)

                if block_entity is not None:
                    chunk.block_entities[coord] = block_entity
                elif coord in chunk.block_entities:
                    chunk.block_entities.pop(coord)

            chunk.changed = True

            count += 1
            yield count / iter_count

    @staticmethod
    def _block_matches_any(world, universal_block, original_blocks_options) -> bool:
        for (
            original_platform,
            original_version,
            original_blockstate,
            original_namespace,
            original_base_name,
            original_properties,
        ) in original_blocks_options:
            version_block = world.translation_manager.get_version(
                original_platform, original_version
            ).block.from_universal(
                universal_block,
                force_blockstate=original_blockstate,
            )[0]
            if (
                version_block.namespace == original_namespace
                and version_block.base_name == original_base_name
                and all(
                    original_properties.get(prop) in ["*", val.to_snbt()]
                    for prop, val in version_block.properties.items()
                )
            ):
                return True
        return False

    def DoGetBestClientSize(self):
        sizer = self.GetSizer()
        if sizer is None:
            return -1, -1
        else:
            sx, sy = self.GetSizer().CalcMin()
            return (
                sx + wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X),
                sy + wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y),
            )


export = {
    "name": "Replace",  # the name of the plugin
    "operation": Replace,  # the actual function to call when running the plugin
}
