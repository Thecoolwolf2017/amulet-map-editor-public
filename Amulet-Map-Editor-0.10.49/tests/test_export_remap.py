import json
import os
import tempfile
import unittest

import numpy

from amulet.api.block import Block
from amulet.api.chunk import Chunk
from amulet.api.registry import BlockManager

from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.export_operations.custom_block_remap import (
    build_export_remap_table_for_selection,
    load_export_block_remap_rules,
    remap_chunk_for_export,
)


class _Selection:
    def __init__(self, locations):
        self._locations = tuple(locations)

    def chunk_locations(self):
        return iter(self._locations)


class _World:
    def __init__(self, chunks):
        self._chunks = dict(chunks)

    def get_chunk(self, cx, cz, _dimension):
        return self._chunks[(cx, cz)]


def _make_chunk_with_custom_block():
    chunk = Chunk(0, 0)
    palette = BlockManager()
    air_id = palette.get_add_block(Block("minecraft", "air"))
    custom_id = palette.get_add_block(Block("myaddon", "machine"))

    section = numpy.full((16, 16, 16), air_id, dtype=numpy.uint32)
    section[:4, :4, :4] = custom_id
    custom_count = int((section == custom_id).sum())

    chunk.blocks.add_sub_chunk(0, section)
    chunk._block_palette = palette
    return chunk, custom_count


class ExportRemapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = self._tmp.name

    def tearDown(self):
        if self._old_data_dir is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = self._old_data_dir

    def test_auto_added_namespace_and_block_remap(self):
        chunk, custom_count = _make_chunk_with_custom_block()
        world = _World({(0, 0): chunk})
        selection = _Selection([(0, 0)])

        rules = build_export_remap_table_for_selection(
            world, "minecraft:overworld", selection
        )
        out_chunk, replaced = remap_chunk_for_export(chunk, rules)

        table_path = os.path.join(self._tmp.name, "custom_block_export_remap.json")
        with open(table_path, "r", encoding="utf-8") as f:
            table = json.load(f)

        self.assertEqual(table.get("auto_block_remap"), True)
        self.assertEqual(table["namespace_remap"].get("myaddon"), "__keep__")
        self.assertIn("myaddon:machine", table.get("block_remap", {}))
        self.assertEqual(replaced, custom_count)

        ids = numpy.unique(out_chunk.blocks.get_sub_chunk(0))
        names = {out_chunk.block_palette[int(i)].namespaced_name for i in ids}
        self.assertNotIn("myaddon:machine", names)

    def test_explicit_namespace_mapping_applies(self):
        table_path = os.path.join(self._tmp.name, "custom_block_export_remap.json")
        with open(table_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "schema_version": 2,
                    "enabled": True,
                    "namespace_remap": {"myaddon": "minecraft:stone"},
                    "block_remap": {},
                },
                f,
            )

        rules = load_export_block_remap_rules()
        chunk, custom_count = _make_chunk_with_custom_block()
        out_chunk, replaced = remap_chunk_for_export(chunk, rules)

        self.assertEqual(replaced, custom_count)
        ids = numpy.unique(out_chunk.blocks.get_sub_chunk(0))
        names = {out_chunk.block_palette[int(i)].namespaced_name for i in ids}
        self.assertIn("minecraft:stone", names)
        self.assertNotIn("myaddon:machine", names)


if __name__ == "__main__":
    unittest.main()
