from typing import TYPE_CHECKING

from amulet.api.structure import structure_cache
from amulet.api.data_types import Dimension, OperationReturnType
from amulet.api.selection import SelectionGroup
from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.internal_operations.delete import (
    delete,
)
from amulet_map_editor.programs.edit.api.operations import OperationError
from amulet_map_editor.programs.edit.api.clipboard_state import record_clipboard_origin

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel


def cut(
    world: "BaseLevel", dimension: Dimension, selection: SelectionGroup
) -> OperationReturnType:
    if selection:
        record_clipboard_origin(getattr(world, "level_path", None), dimension, selection)
        structure = world.extract_structure(selection, dimension)
        structure_cache.add_structure(structure, structure.dimensions[0])
        yield from delete(
            world,
            dimension,
            selection,
        )
    else:
        raise OperationError(
            "At least one selection is required for the copy operation."
        )
