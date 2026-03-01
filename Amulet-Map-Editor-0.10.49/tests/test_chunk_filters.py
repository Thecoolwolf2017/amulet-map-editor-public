import importlib.util
import unittest
from pathlib import Path

import numpy


def _load_chunk_filters_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "amulet_map_editor"
        / "programs"
        / "edit"
        / "plugins"
        / "tools"
        / "chunk_filters.py"
    )
    spec = importlib.util.spec_from_file_location("test_chunk_filters", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


chunk_filters = _load_chunk_filters_module()


class _Block:
    def __init__(self, namespaced_name: str, extra_blocks=()):
        self.namespaced_name = namespaced_name
        self.extra_blocks = tuple(extra_blocks)


class _Chunk:
    def __init__(self, blocks, block_entities=None, entities=None):
        self.blocks = numpy.array(blocks)
        self.block_entities = {} if block_entities is None else block_entities
        self.entities = [] if entities is None else entities


class _World:
    def __init__(self, palette):
        self.block_palette = palette


class ChunkFiltersTests(unittest.TestCase):
    def test_air_only_chunk_is_empty(self):
        world = _World([_Block("universal_minecraft:air")])
        chunk = _Chunk([[0, 0], [0, 0]])
        self.assertTrue(chunk_filters.chunk_is_effectively_empty(world, chunk))

    def test_non_air_chunk_is_not_empty(self):
        world = _World(
            [
                _Block("universal_minecraft:air"),
                _Block("universal_minecraft:stone"),
            ]
        )
        chunk = _Chunk([[0, 1], [0, 0]])
        self.assertFalse(chunk_filters.chunk_is_effectively_empty(world, chunk))

    def test_chunk_with_entities_is_not_empty(self):
        world = _World([_Block("universal_minecraft:air")])
        chunk = _Chunk([[0, 0], [0, 0]], entities=[object()])
        self.assertFalse(chunk_filters.chunk_is_effectively_empty(world, chunk))

    def test_chunk_with_extra_blocks_is_not_empty(self):
        world = _World(
            [
                _Block("universal_minecraft:air", extra_blocks=(_Block("universal_minecraft:water"),)),
            ]
        )
        chunk = _Chunk([[0, 0], [0, 0]])
        self.assertFalse(chunk_filters.chunk_is_effectively_empty(world, chunk))


if __name__ == "__main__":
    unittest.main()
