# Cubic Chunks Amulet-Core Work Plan

Status: draft  
Scope: move from "detect and warn" to real Cubic Chunks read/write support in Amulet-Core, then enable in editor.

## 1) Outcomes

1. Load Cubic Chunks worlds without converting them to a fixed-height dense chunk model.
2. Preserve cube-existence semantics (present cube vs not-generated cube).
3. Keep existing chunk APIs usable for vanilla worlds and most editor paths.
4. Land support in milestones that are independently reviewable and testable.

## 2) Non-Goals (Initial Delivery)

1. Generic support for every modded chunk shape (initial target is Cubic Chunks 16x16x16 cubes).
2. Full binary compatibility with every historical internal API edge case.
3. Renderer/perf parity on day one (functional correctness first, optimize after).

## 3) Column/Cube Storage Model (Core)

### 3.1 Data Structures

1. Introduce a sparse vertical column container:
   - `ColumnData`
   - key: `(dimension_id, cx, cz)`
2. `ColumnData` holds:
   - `sub_chunks: dict[int, SubChunkData]` where key is cube Y index.
   - `present_sub_chunks: set[int]` to preserve "cube exists" information.
   - `column_meta` for 2D/column-level payloads (biomes/heightmap/format extras).
   - `dirty_sub_chunks: set[int]` and `dirty_column_meta: bool`.
3. `SubChunkData` remains a 16x16x16 block container with palette/block entity/entity/tick payload.

### 3.2 Invariants

1. Cube size is fixed at 16x16x16.
2. Y index is signed and unbounded at API level; loader can clamp/validate to format constraints.
3. "Missing sub-chunk" is distinct from "all air sub-chunk".
4. Writing must not silently create/remove sub-chunks unless the edit path requested it.

### 3.3 Coordinate Rules

1. `cube_y = floor(block_y / 16)`
2. `local_y = block_y mod 16` (normalized to 0..15 for negative Y inputs).
3. Same floor/mod rules are used consistently by read, write, selection, and save.

## 4) Chunk API Compatibility Surface

### 4.1 Compatibility Strategy

1. Keep existing public API behavior unchanged for fixed-height vanilla worlds.
2. Add sparse-aware APIs and migrate editor/core call sites to prefer them.
3. Keep compatibility shim for legacy dense access where practical, with explicit limits.

### 4.2 Required New/Extended APIs

1. Presence/introspection:
   - `has_sub_chunk(cy: int) -> bool`
   - `iter_sub_chunk_y() -> Iterable[int]`
   - `get_sub_chunk(cy: int, create: bool = False) -> SubChunkData | None`
2. Block access helpers:
   - `get_block(x, y, z, default=air)`
   - `set_block(x, y, z, block, create_sub_chunk=True)`
3. Column metadata:
   - explicit accessors for per-column biome/surface data when format supports it.
4. Capabilities:
   - `is_sparse_vertical` and `supports_unbounded_y`
   - optional `height_bounds` only for bounded formats

### 4.3 Dense API Behavior Policy

1. Dense-only operations that assume a single contiguous 16xH array must either:
   - accept explicit Y bounds, or
   - raise a clear "unsupported for sparse/unbounded chunk" error.
2. No implicit "materialize infinite air array" behavior.
3. Deprecate ambiguous dense operations in stages with migration notes.

## 5) Loader/Save Path Milestones

### Milestone A - Core Scaffolding (No format IO yet)

1. Add `ColumnData`/sparse sub-chunk model and capability flags.
2. Add unit tests for cube presence semantics and negative-Y indexing.
3. Exit criteria:
   - existing vanilla tests pass.
   - new sparse data model tests pass.

### Milestone B - Cubic Chunks Read-Only Loader

1. Implement world identification and dimension metadata parse (`isCubicWorld`, `cubicChunksData.dat`).
2. Implement `region2d` + `region3d` readers (including ext region fallback).
3. Read block/entities/tile entities/ticks into sparse column model.
4. Exit criteria:
   - open real fixture worlds and browse blocks at positive/negative Y.
   - no crash on partially populated columns.

### Milestone C - Write Path (Lossless Round-Trip First)

1. Implement save for touched columns/cubes only.
2. Preserve unknown/unmodified payload where possible.
3. Handle create/delete cube transitions explicitly via `present_sub_chunks`.
4. Exit criteria:
   - no-op open/save yields binary-stable or semantically equivalent NBT.
   - edit one block in a single cube only dirties expected files/chunks.

### Milestone D - Editing Semantics + API Migration

1. Move core editor operations to sparse-safe APIs:
   - selection fill/replace/copy/paste
   - chunk delete/regenerate helpers
2. Remove direct dense-array assumptions in shared code paths.
3. Exit criteria:
   - operation tests pass on both vanilla and cubic fixtures.
   - no forced dense conversion in hot paths.

### Milestone E - Performance and Caching

1. Add sub-chunk level cache controls (read cache + write-back).
2. Measure memory and IO for large sparse vertical worlds.
3. Exit criteria:
   - baseline perf report committed.
   - no major regression vs current non-cubic workflows.

## 6) PR Slicing (Recommended)

1. PR1: Sparse column/sub-chunk data model + tests.
2. PR2: Compatibility adapters/capability flags + call-site migrations in Core.
3. PR3: Cubic Chunks read-only loader.
4. PR4: Cubic Chunks save path + round-trip tests.
5. PR5: Editor/core operation migration to sparse-safe APIs.
6. PR6: Perf/caching follow-up.

Each PR should be mergeable, documented, and carry fixture-backed tests.

## 7) Test Plan

1. Unit tests:
   - cube presence semantics (missing vs air)
   - negative Y coordinate mapping
   - dirty tracking at cube and column granularity
2. Fixture tests (real sample worlds):
   - load columns at mixed Y ranges
   - round-trip no-op save
   - edit-save-reload consistency
3. Cross-format regression:
   - vanilla Java/Bedrock open, edit, save still pass.
4. Optional fuzz:
   - randomized sparse cube sets and randomized block edits.

## 8) Risks and Mitigations

1. Risk: hidden dense-array assumptions in old code.
   - Mitigation: capability flags + staged migration + test coverage on both formats.
2. Risk: data loss on save due to partial NBT handling.
   - Mitigation: no-op round-trip fixtures before enabling write by default.
3. Risk: large memory overhead from eager cube materialization.
   - Mitigation: lazy sub-chunk load/create and bounded caches.

## 9) Map Editor Integration Gate

1. Keep current detection/warning behavior until Milestone C is complete.
2. Enable Cubic Chunks open in editor behind a feature flag after Milestone C.
3. Remove warning-only path after Milestone D passes regression suite.
