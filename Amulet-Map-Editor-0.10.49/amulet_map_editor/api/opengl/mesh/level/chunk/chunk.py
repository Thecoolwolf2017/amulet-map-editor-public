import numpy
from typing import TYPE_CHECKING, Tuple, List, Union
import weakref
import itertools
import logging

from amulet.api.errors import ChunkLoadError, ChunkDoesNotExist
from amulet.api.chunk.blocks import Blocks
from amulet.api.block import Block
from amulet.api.data_types import Dimension
from amulet.api.level import BaseLevel
from amulet.api.selection import SelectionBox
from amulet_nbt import StringTag

from .chunk_builder import RenderChunkBuilder
from amulet_map_editor.api.opengl.resource_pack import OpenGLResourcePack

if TYPE_CHECKING:
    from amulet.api.chunk import Chunk

log = logging.getLogger(__name__)


class RenderChunk(RenderChunkBuilder):
    def __init__(
        self,
        context_identifier: str,
        resource_pack: OpenGLResourcePack,
        level: BaseLevel,
        region_size: int,
        chunk_coords: Tuple[int, int],
        dimension: Dimension,
        draw_floor: bool = False,
        draw_ceil: bool = False,
        limit_bounds: bool = False,
    ):
        # the chunk geometry is stored in chunk space (floating point)
        # at shader time it is transformed by the players transform
        super().__init__(context_identifier, resource_pack)
        self._level_ = weakref.ref(level)
        self._region_size = region_size
        self._coords = chunk_coords
        self._dimension = dimension
        self._draw_floor = draw_floor
        self._draw_ceil = draw_ceil
        self._limit_bounds = limit_bounds
        self._chunk_state = 0  # 0 = chunk does not exist, 1 = chunk exists but failed to load, 2 = chunk exists
        self._changed_time = 0
        self._needs_rebuild = True
        self.verts_translucent = (
            0  # the offset into the above from which the faces can be translucent
        )
        # self.chunk_lod1: numpy.ndarray = self.new_empty_verts()

    def __repr__(self):
        return f"RenderChunk({self._coords[0]}, {self._coords[1]})"

    def _setup(self):
        """Set up the opengl data which cannot be set up in another thread"""
        super()._setup()
        if self._needs_rebuild:
            self.change_verts()
            self._needs_rebuild = False

    @property
    def _level(self) -> BaseLevel:
        return self._level_()

    @property
    def offset(self) -> numpy.ndarray:
        return 16 * (
            numpy.array([self._coords[0], 0, self._coords[1]]) % self._region_size
        )

    @property
    def dimension(self) -> str:
        return self._dimension

    @property
    def cx(self) -> int:
        return self._coords[0]

    @property
    def cz(self) -> int:
        return self._coords[1]

    @property
    def coords(self) -> Tuple[int, int]:
        return self._coords

    @property
    def chunk(self) -> "Chunk":
        return self._level.get_chunk(self.cx, self.cz, self._dimension)

    @property
    def chunk_state(self) -> int:
        return self._chunk_state

    def needs_rebuild(self):
        """has the chunk data changed since the last rebuild"""
        try:
            chunk = self.chunk
        except ChunkDoesNotExist:
            chunk_state = 0
        except ChunkLoadError:
            chunk_state = 1
        else:
            chunk_state = 2
            if chunk.changed_time != self._changed_time:
                return True
        return chunk_state != self._chunk_state

    def _sub_chunks(self, blocks: Blocks) -> List[Tuple[numpy.ndarray, int]]:
        """Create sub-chunk arrays that extend into the neighbour sub-chunks by one block.

        :param blocks: The Blocks array for the chunk.
        :return: A list of tuples containing the larger block array and the location of the sub-chunk
        """
        sub_chunks = []
        neighbour_chunks = {}
        for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            try:
                neighbour_chunks[(dx, dz)] = self._level.get_chunk(
                    self.cx + dx, self.cz + dz, self.dimension
                ).blocks
            except ChunkLoadError:
                continue

        for cy in blocks.sub_chunks:
            sub_chunk = blocks.get_sub_chunk(cy)
            larger_blocks = numpy.zeros(
                sub_chunk.shape + numpy.array((2, 2, 2)), sub_chunk.dtype
            )
            sub_chunk_box = SelectionBox.create_sub_chunk_box(self.cx, cy, self.cz)
            if self._limit_bounds:
                if self._level.bounds(self.dimension).intersects(sub_chunk_box):
                    boxes = self._level.bounds(self.dimension).intersection(
                        sub_chunk_box
                    )
                    for box in boxes.selection_boxes:
                        larger_blocks[1:-1, 1:-1, 1:-1][
                            box.sub_chunk_slice(self.cx, cy, self.cz)
                        ] = sub_chunk[box.sub_chunk_slice(self.cx, cy, self.cz)]
                else:
                    continue
            else:
                larger_blocks[1:-1, 1:-1, 1:-1] = sub_chunk
            for chunk_offset, neighbour_blocks in neighbour_chunks.items():
                if cy not in neighbour_blocks:
                    continue
                if chunk_offset == (-1, 0):
                    larger_blocks[0, 1:-1, 1:-1] = neighbour_blocks.get_sub_chunk(cy)[
                        -1, :, :
                    ]
                elif chunk_offset == (1, 0):
                    larger_blocks[-1, 1:-1, 1:-1] = neighbour_blocks.get_sub_chunk(cy)[
                        0, :, :
                    ]
                elif chunk_offset == (0, -1):
                    larger_blocks[1:-1, 1:-1, 0] = neighbour_blocks.get_sub_chunk(cy)[
                        :, :, -1
                    ]
                elif chunk_offset == (0, 1):
                    larger_blocks[1:-1, 1:-1, -1] = neighbour_blocks.get_sub_chunk(cy)[
                        :, :, 0
                    ]
            if cy - 1 in blocks:
                larger_blocks[1:-1, 0, 1:-1] = blocks.get_sub_chunk(cy - 1)[:, -1, :]
            if cy + 1 in blocks:
                larger_blocks[1:-1, -1, 1:-1] = blocks.get_sub_chunk(cy + 1)[:, 0, :]
            sub_chunks.append((larger_blocks, cy * 16))
        return sub_chunks

    @staticmethod
    def _is_connectable_fence_block(block: Block) -> bool:
        return (
            block.namespace == "universal_minecraft"
            and block.base_name in ("fence", "fence_gate")
        )

    @staticmethod
    def _prop_is_true(value) -> bool:
        return str(value).lower() == "true"

    @staticmethod
    def _set_bool_string_prop(props: dict, key: str, value: bool) -> None:
        existing = props.get(key)
        tag_type = type(existing) if existing is not None else StringTag
        props[key] = tag_type("true" if value else "false")

    def _apply_bedrock_fence_visual_fix(
        self, sub_chunks: List[Tuple[numpy.ndarray, int]], block_palette
    ) -> Tuple[List[Tuple[numpy.ndarray, int]], list]:
        """
        Bedrock does not always persist fence connect states in a way that survives
        translation. Synthesize directional fence states from neighboring blocks for
        rendering only. This does not modify world data on disk.
        """
        mutable_palette = list(block_palette)
        variant_cache: dict[tuple[int, bool, bool, bool, bool], int] = {}
        fixed_sub_chunks: List[Tuple[numpy.ndarray, int]] = []

        for larger_blocks, sub_chunk_y in sub_chunks:
            fixed_blocks = larger_blocks.copy()
            sx, sy, sz = fixed_blocks.shape

            for x in range(1, sx - 1):
                for y in range(1, sy - 1):
                    for z in range(1, sz - 1):
                        block_index = int(fixed_blocks[x, y, z])
                        block = mutable_palette[block_index]
                        if not self._is_connectable_fence_block(block):
                            continue

                        east = self._is_connectable_fence_block(
                            mutable_palette[int(fixed_blocks[x + 1, y, z])]
                        )
                        west = self._is_connectable_fence_block(
                            mutable_palette[int(fixed_blocks[x - 1, y, z])]
                        )
                        south = self._is_connectable_fence_block(
                            mutable_palette[int(fixed_blocks[x, y, z + 1])]
                        )
                        north = self._is_connectable_fence_block(
                            mutable_palette[int(fixed_blocks[x, y, z - 1])]
                        )

                        props = block.properties
                        if (
                            self._prop_is_true(props.get("east", "false")) == east
                            and self._prop_is_true(props.get("west", "false")) == west
                            and self._prop_is_true(props.get("south", "false"))
                            == south
                            and self._prop_is_true(props.get("north", "false"))
                            == north
                        ):
                            continue

                        variant_key = (block_index, east, west, south, north)
                        if variant_key not in variant_cache:
                            new_props = dict(props)
                            self._set_bool_string_prop(new_props, "east", east)
                            self._set_bool_string_prop(new_props, "west", west)
                            self._set_bool_string_prop(new_props, "south", south)
                            self._set_bool_string_prop(new_props, "north", north)
                            new_block = Block(
                                block.namespace,
                                block.base_name,
                                new_props,
                                block.extra_blocks or None,
                            )
                            variant_cache[variant_key] = len(mutable_palette)
                            mutable_palette.append(new_block)

                        fixed_blocks[x, y, z] = variant_cache[variant_key]

            fixed_sub_chunks.append((fixed_blocks, sub_chunk_y))

        return fixed_sub_chunks, mutable_palette

    def create_geometry(self):
        try:
            chunk = self.chunk
        except ChunkDoesNotExist:
            self._create_empty_geometry()
            self._chunk_state = 0
        except ChunkLoadError:
            log.info(f"Error loading chunk {self.coords}", exc_info=True)
            self._create_error_geometry()
            self._chunk_state = 1
        else:
            self._changed_time = chunk.changed_time
            self._chunk_state = 2
            sub_chunks = self._sub_chunks(chunk.blocks)
            block_palette = chunk.block_palette
            if self._level.level_wrapper.platform == "bedrock":
                sub_chunks, block_palette = self._apply_bedrock_fence_visual_fix(
                    sub_chunks, block_palette
                )

            chunk_verts, chunk_verts_translucent = self._create_lod0_multi(
                sub_chunks, block_palette
            )
            self._set_verts(chunk_verts, chunk_verts_translucent)
            if self._draw_floor or self._draw_ceil:
                plane = self._create_grid(
                    "amulet",
                    "amulet_ui/translucent_white",
                    (0.55, 0.5, 0.9) if (self.cx + self.cz) % 2 else (0.4, 0.4, 0.85),
                )
                self.verts = numpy.concatenate([self.verts, plane.ravel()], 0)
                self.draw_count += len(plane)
        self._needs_rebuild = True

    def _create_empty_geometry(self):
        if self._draw_floor:
            plane = self._create_grid(
                "amulet",
                "amulet_ui/translucent_white",
                (0.3, 0.3, 0.3) if (self.cx + self.cz) % 2 else (0.2, 0.2, 0.2),
            )
            self.verts = plane.ravel()
            self.draw_count = len(plane)
        else:
            self.verts = numpy.ones(0, numpy.float32)
            self.draw_count = 0

    def _create_grid(
        self,
        texture_namespace: str,
        texture_path: str,
        tint: Tuple[float, float, float],
    ):
        plane: numpy.ndarray = numpy.ones(
            (self._vert_len * 12 * (self._draw_floor + self._draw_ceil)),
            dtype=numpy.float32,
        ).reshape((-1, self._vert_len))
        bounds = self._level.bounds(self.dimension)
        if self._draw_floor:
            plane[:12, :3], plane[:12, 3:5] = self._create_chunk_plane(
                bounds.min_y - 0.01
            )
            if self._draw_ceil:
                plane[12:, :3], plane[12:, 3:5] = self._create_chunk_plane(
                    bounds.max_y + 0.01
                )
        elif self._draw_ceil:
            plane[:12, :3], plane[:12, 3:5] = self._create_chunk_plane(
                bounds.max_y + 0.01
            )

        plane[:, 5:9] = self.resource_pack.texture_bounds(
            self.resource_pack.get_texture_path(texture_namespace, texture_path)
        )
        plane[:, 9:12] = tint
        return plane

    def _create_chunk_plane(
        self, height: Union[int, float]
    ) -> Tuple[numpy.ndarray, numpy.ndarray]:
        box = numpy.array([(0, height, 0), (16, height, 16)]) + self.offset
        _box_coordinates = numpy.array(list(itertools.product(*box.T.tolist())))
        _cube_face_lut = numpy.array(
            [  # This maps to the verticies used (defined in cube_vert_lut)
                0,
                4,
                5,
                1,
                3,
                7,
                6,
                2,
            ]
        )
        box = box.ravel()
        _texture_index = numpy.array([0, 2, 3, 5, 0, 2, 3, 5], numpy.uint32)
        _uv_slice = numpy.array(
            [0, 1, 2, 1, 2, 3, 0, 3] * 2, dtype=numpy.uint32
        ).reshape((-1, 8)) + numpy.arange(0, 8, 4).reshape((-1, 1))

        _tri_face = numpy.array([0, 1, 2, 0, 2, 3] * 2, numpy.uint32).reshape(
            (-1, 6)
        ) + numpy.arange(0, 8, 4).reshape((-1, 1))
        return (
            _box_coordinates[_cube_face_lut[_tri_face]].reshape((-1, 3)),
            box[_texture_index[_uv_slice]]
            .reshape(-1, 2)[_tri_face, :]
            .reshape((-1, 2)),
        )

    def _create_error_geometry(self):
        if self._draw_floor:
            plane = self._create_grid(
                "amulet",
                "amulet_ui/translucent_white",
                (1, 0.2, 0.2) if (self.cx + self.cz) % 2 else (0.75, 0.2, 0.2),
            )
            self.verts = plane.ravel()
            self.draw_count = len(plane)
        else:
            self.verts = numpy.ones(0, numpy.float32)
            self.draw_count = 0

    def _create_lod1(
        self,
        blocks: numpy.ndarray,
        larger_blocks: numpy.ndarray,
        unique_blocks: numpy.ndarray,
    ):
        # TODO
        self.verts: numpy.ndarray = self.new_empty_verts()
        # self.chunk_lod1: numpy.ndarray = self.new_empty_verts()
