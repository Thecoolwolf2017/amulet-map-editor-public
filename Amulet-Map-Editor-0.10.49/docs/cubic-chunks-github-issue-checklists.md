# Cubic Chunks GitHub Issue Checklists

Use this file to create one GitHub issue per milestone from `docs/cubic-chunks-core-work-plan.md`.

## Issue 1: Milestone A - Core Scaffolding (No format IO yet)

Suggested labels: `type: enhancement`, `area: core`, `modded`, `priority: medium`

Body:

```md
## Goal
Introduce sparse vertical column/sub-chunk scaffolding in Amulet-Core without changing format IO yet.

## Checklist
- [ ] Add sparse `ColumnData` container keyed by `(dimension_id, cx, cz)`.
- [ ] Add `sub_chunks: dict[int, SubChunkData]` storage keyed by cube Y.
- [ ] Add `present_sub_chunks: set[int]` to preserve cube-existence semantics.
- [ ] Add column/cube dirty tracking (`dirty_sub_chunks`, `dirty_column_meta`).
- [ ] Add capability flags for sparse/unbounded vertical models.
- [ ] Add coordinate mapping helpers for signed Y (`cube_y`, `local_y`).
- [ ] Add unit tests for negative-Y indexing behavior.
- [ ] Add unit tests for "missing cube" vs "all-air cube" behavior.
- [ ] Run existing vanilla test suite and confirm no regressions.
- [ ] Add migration notes in Core docs/changelog.

## Acceptance Criteria
- [ ] Existing vanilla tests pass unchanged.
- [ ] New sparse model tests pass.
- [ ] No format loader/save behavior changes in this milestone.
```

## Issue 2: Milestone B - Cubic Chunks Read-Only Loader

Suggested labels: `type: enhancement`, `area: core`, `modded`, `priority: medium`

Body:

```md
## Goal
Load Cubic Chunks worlds into the sparse model as read-only.

## Depends On
- Milestone A (core scaffolding)

## Checklist
- [ ] Implement world/dimension detection parse (`isCubicWorld`, `cubicChunksData.dat`).
- [ ] Implement `region2d` reader for column-level payload.
- [ ] Implement `region3d` reader for cube-level payload.
- [ ] Implement ext-region fallback reads for oversized entries.
- [ ] Map loaded cubes into `sub_chunks` and `present_sub_chunks`.
- [ ] Parse block data + entities + tile entities + ticks required for viewing/edit-prep.
- [ ] Add fixture worlds covering positive + negative Y cubes.
- [ ] Add loader tests for partially populated columns.
- [ ] Verify editor browse/read paths can inspect loaded cube data.
- [ ] Keep save path disabled for Cubic Chunks in this milestone.

## Acceptance Criteria
- [ ] Fixture worlds open without crash.
- [ ] Positive and negative Y cube content is readable.
- [ ] Missing cubes remain missing (not materialized as dense air).
```

## Issue 3: Milestone C - Write Path (Lossless Round-Trip First)

Suggested labels: `type: enhancement`, `area: core`, `modded`, `priority: high`

Body:

```md
## Goal
Enable Cubic Chunks save with lossless/semantically equivalent round-trip behavior.

## Depends On
- Milestone B (read-only loader)

## Checklist
- [ ] Implement save path for touched columns/cubes only.
- [ ] Preserve unknown/unmodified NBT payload where possible.
- [ ] Respect `present_sub_chunks` for explicit cube create/delete transitions.
- [ ] Implement writer support for `region2d` and `region3d`.
- [ ] Implement ext-region write handling as needed for oversized entries.
- [ ] Add no-op open/save fixture tests (round-trip).
- [ ] Add targeted edit/save/reload tests (single block in single cube).
- [ ] Verify only expected files/entries become dirty on targeted edits.
- [ ] Add corruption-safety/error-path tests for interrupted writes.
- [ ] Gate feature behind flag until tests are stable.

## Acceptance Criteria
- [ ] No-op open/save is binary-stable or semantically equivalent.
- [ ] Single-cube edit only mutates expected persisted data.
- [ ] No known data-loss paths remain in core write flow.
```

## Issue 4: Milestone D - Editing Semantics + API Migration

Suggested labels: `type: enhancement`, `area: core`, `area: editor`, `priority: high`

Body:

```md
## Goal
Migrate dense-assuming editor/core operations to sparse-safe APIs so Cubic Chunks editing is practical.

## Depends On
- Milestone C (write path)

## Checklist
- [ ] Add/extend chunk APIs:
  - [ ] `has_sub_chunk(cy)`
  - [ ] `iter_sub_chunk_y()`
  - [ ] `get_sub_chunk(cy, create=False)`
  - [ ] sparse-safe `get_block`/`set_block` behavior
- [ ] Define dense API policy for sparse worlds (bounded-only or explicit error).
- [ ] Migrate selection fill path to sparse-safe access.
- [ ] Migrate replace path to sparse-safe access.
- [ ] Migrate copy/paste paths to sparse-safe access.
- [ ] Migrate chunk delete/regenerate helper paths where needed.
- [ ] Add cross-format operation tests (vanilla + cubic fixtures).
- [ ] Remove/guard dense-only assumptions in hot paths.
- [ ] Update docs for plugin/API behavior changes.

## Acceptance Criteria
- [ ] Core edit operations pass on vanilla + cubic fixtures.
- [ ] No forced dense conversion in common edit paths.
- [ ] Dense-only API behavior is explicit and documented.
```

## Issue 5: Milestone E - Performance and Caching

Suggested labels: `type: enhancement`, `area: performance`, `area: core`, `priority: medium`

Body:

```md
## Goal
Stabilize memory/IO performance for sparse vertical worlds.

## Depends On
- Milestone D (editing semantics)

## Checklist
- [ ] Add sub-chunk level read cache controls.
- [ ] Add sub-chunk/column write-back cache controls.
- [ ] Ensure lazy materialization (no eager cube creation).
- [ ] Add benchmark scenarios for large sparse vertical worlds.
- [ ] Add benchmark scenarios for existing vanilla workflows.
- [ ] Measure memory profile and IO throughput before/after.
- [ ] Tune default cache settings based on benchmark data.
- [ ] Document tunables and recommended defaults.
- [ ] Publish perf report in repo docs.

## Acceptance Criteria
- [ ] Perf baseline report committed.
- [ ] No major regressions for non-cubic workflows.
- [ ] Cubic workflows remain stable under large sparse test worlds.
```

## Optional Tracking Epic

Suggested title: `Epic: Cubic Chunks format support (A->E milestones)`

Suggested checklist:

```md
- [ ] Milestone A - Core Scaffolding
- [ ] Milestone B - Read-Only Loader
- [ ] Milestone C - Write Path
- [ ] Milestone D - Editing + API Migration
- [ ] Milestone E - Performance + Caching
```
