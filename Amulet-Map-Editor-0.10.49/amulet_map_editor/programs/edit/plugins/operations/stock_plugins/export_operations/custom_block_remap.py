from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set, Tuple, TYPE_CHECKING

import numpy

from amulet.api.block import Block
from amulet.api.chunk import Chunk
from amulet.api.registry import BlockManager

if TYPE_CHECKING:
    from amulet.api.data_types import Dimension
    from amulet.api.level import BaseLevel
    from amulet.api.selection import SelectionGroup

log = logging.getLogger(__name__)
_DEFAULT_NAMESPACE_FALLBACK = "minecraft:stone"
_KEEP_SENTINEL = "__keep__"
_SCHEMA_VERSION = 2

_LEGACY_NAMESPACE_REMAP = {
    "better_on_bedrock": "minecraft:stone",
    "ecbl_bs": "minecraft:iron_block",
    "f": "minecraft:white_wool",
    "ftb": "minecraft:oak_planks",
    "ftb_tc": "minecraft:stone",
    "vtng_rt": "minecraft:redstone_block",
}

_LEGACY_BLOCK_REMAP = {
    "better_on_bedrock:alluminum_ore": "minecraft:iron_ore",
    "better_on_bedrock:anenome": "minecraft:dandelion",
    "better_on_bedrock:barley_crop": "minecraft:wheat",
    "better_on_bedrock:blueberry_block": "minecraft:sweet_berry_bush",
    "better_on_bedrock:cabbage_crop": "minecraft:wheat",
    "better_on_bedrock:eggplant_crop": "minecraft:wheat",
    "better_on_bedrock:lilax_heads": "minecraft:lilac",
    "better_on_bedrock:stardust_ore": "minecraft:diamond_ore",
    "better_on_bedrock:tin_ore": "minecraft:iron_ore",
    "better_on_bedrock:tomato_crop": "minecraft:wheat",
    "better_on_bedrock:wild_carrot": "minecraft:carrots",
    "ftb_tc:tin_ore": "minecraft:iron_ore",
}

_DEFAULT_REMAP_TABLE = {
    "schema_version": _SCHEMA_VERSION,
    "enabled": True,
    "auto_block_remap": True,
    "namespace_remap": {},
    "block_remap": {},
    "notes": [
        "This table is used only during export.",
        "New custom namespaces are auto-added as '__keep__'.",
        "If auto_block_remap is true, missing custom blocks get auto-mapped to vanilla guesses.",
        "Keys in block_remap are exact namespace:block ids.",
        "namespace_remap applies when there is no exact block_remap match.",
        "Set values to vanilla blockstates to force fallback mappings.",
        "Use '__keep__' to avoid remapping a namespace entry.",
    ],
}


@dataclass(frozen=True)
class ExportBlockRemapRules:
    enabled: bool
    namespace_remap: Dict[str, Optional[Block]]
    block_remap: Dict[str, Block]
    path: str


@dataclass(frozen=True)
class ExportRemapPreviewEntry:
    source_block: str
    replacement_block: str
    block_count: int


@dataclass(frozen=True)
class ExportRemapPreview:
    rules_path: str
    remap_enabled: bool
    auto_block_remap: bool
    total_chunks: int
    scanned_chunks: int
    failed_chunks: int
    custom_namespace_count: int
    custom_block_count: int
    custom_block_total: int
    remapped_block_total: int
    entries: Tuple[ExportRemapPreviewEntry, ...]


def _normalise_key(key: str) -> str:
    return str(key).strip().lower()


def _parse_blockstate(value: str) -> Block:
    text = str(value).strip()
    if not text:
        raise ValueError("Blockstate cannot be empty.")
    try:
        return Block.from_string_blockstate(text)
    except Exception:
        return Block.from_snbt_blockstate(text)


def _default_remap_path() -> str:
    data_dir = os.environ.get("DATA_DIR") or os.getcwd()
    return os.path.join(data_dir, "custom_block_export_remap.json")


def _ensure_default_file(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_REMAP_TABLE, f, indent=2, sort_keys=True)


def _migrate_legacy_rules(path: str, data: dict) -> dict:
    if not isinstance(data, dict):
        return deepcopy(_DEFAULT_REMAP_TABLE)

    legacy_mode = data.get("schema_version") is None
    if not legacy_mode:
        return data

    changed = False
    namespace_remap = data.get("namespace_remap")
    if not isinstance(namespace_remap, dict):
        namespace_remap = {}
        data["namespace_remap"] = namespace_remap
        changed = True

    for namespace, replacement in list(namespace_remap.items()):
        if not isinstance(replacement, str):
            continue
        namespace_key = _normalise_key(namespace)
        replacement_key = _normalise_key(replacement)
        legacy_value = _LEGACY_NAMESPACE_REMAP.get(namespace_key)

        if (
            replacement_key == _normalise_key(_DEFAULT_NAMESPACE_FALLBACK)
            or (
                legacy_value is not None
                and replacement_key == _normalise_key(legacy_value)
            )
        ):
            namespace_remap[namespace] = _KEEP_SENTINEL
            changed = True

    block_remap = data.get("block_remap")
    if not isinstance(block_remap, dict):
        block_remap = {}
        data["block_remap"] = block_remap
        changed = True

    for block_id, replacement in list(block_remap.items()):
        if not isinstance(replacement, str):
            continue
        legacy_value = _LEGACY_BLOCK_REMAP.get(_normalise_key(block_id))
        if legacy_value is not None and _normalise_key(replacement) == _normalise_key(
            legacy_value
        ):
            del block_remap[block_id]
            changed = True

    if data.get("schema_version") != _SCHEMA_VERSION:
        data["schema_version"] = _SCHEMA_VERSION
        changed = True

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        log.info(
            "Migrated export remap table to safe keep-by-default behavior: %s",
            path,
        )

    return data


def _load_raw_rules_data(path: str) -> dict:
    _ensure_default_file(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Rules file must contain a JSON object.")
        data = _migrate_legacy_rules(path, data)
        if "auto_block_remap" not in data:
            data["auto_block_remap"] = True
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
        return data
    except Exception:
        log.exception("Could not parse export block remap table at %s", path)
        return deepcopy(_DEFAULT_REMAP_TABLE)


def _iter_blocks(block: Block) -> Iterable[Block]:
    yield block.base_block
    for extra in block.extra_blocks:
        yield from _iter_blocks(extra)


def _used_palette_ids(chunk: Chunk) -> Set[int]:
    used_palette_ids = set()
    for cy in chunk.blocks.sub_chunks:
        used_palette_ids.update(
            int(v) for v in numpy.unique(chunk.blocks.get_sub_chunk(cy))
        )
    return used_palette_ids


def _collect_chunk_custom_namespaces(chunk: Chunk) -> Set[str]:
    namespaces: Set[str] = set()
    for block in _collect_chunk_custom_blocks(chunk):
        namespace = _normalise_key(block.namespace)
        if namespace:
            namespaces.add(namespace)
    return namespaces


def _collect_chunk_custom_blocks(chunk: Chunk) -> Set[Block]:
    blocks: Set[Block] = set()
    for palette_id in _used_palette_ids(chunk):
        block = chunk.block_palette[palette_id]
        for block_part in _iter_blocks(block):
            namespace = _normalise_key(block_part.namespace)
            if namespace and namespace not in {
                "minecraft",
                "universal",
                "universal_minecraft",
            }:
                blocks.add(block_part.base_block)
    return blocks


def _custom_namespaces_in_block(block: Block) -> Set[str]:
    namespaces: Set[str] = set()
    for block_part in _iter_blocks(block):
        namespace = _normalise_key(block_part.namespace)
        if namespace and namespace not in {"minecraft", "universal", "universal_minecraft"}:
            namespaces.add(namespace)
    return namespaces


def _chunk_palette_usage_counts(chunk: Chunk) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    for cy in chunk.blocks.sub_chunks:
        palette_ids, palette_counts = numpy.unique(
            chunk.blocks.get_sub_chunk(cy), return_counts=True
        )
        for palette_id, palette_count in zip(palette_ids, palette_counts):
            key = int(palette_id)
            counts[key] = counts.get(key, 0) + int(palette_count)
    return counts


def _guess_vanilla_blockstate_for_custom(block: Block) -> str:
    name = _normalise_key(block.base_name)

    ore_map = [
        ("diamond", "minecraft:diamond_ore"),
        ("emerald", "minecraft:emerald_ore"),
        ("gold", "minecraft:gold_ore"),
        ("iron", "minecraft:iron_ore"),
        ("copper", "minecraft:copper_ore"),
        ("coal", "minecraft:coal_ore"),
        ("redstone", "minecraft:redstone_ore"),
        ("lapis", "minecraft:lapis_ore"),
        ("tin", "minecraft:iron_ore"),
        ("aluminum", "minecraft:iron_ore"),
        ("alluminum", "minecraft:iron_ore"),
        ("stardust", "minecraft:diamond_ore"),
    ]
    if "ore" in name:
        for keyword, fallback in ore_map:
            if keyword in name:
                return fallback
        return "minecraft:iron_ore"

    keyword_map = [
        ("carrot", "minecraft:carrots"),
        ("potato", "minecraft:potatoes"),
        ("crop", "minecraft:wheat"),
        ("berry", "minecraft:sweet_berry_bush"),
        ("anenome", "minecraft:dandelion"),
        ("lilax", "minecraft:lilac"),
        ("flower", "minecraft:dandelion"),
        ("barrel", "minecraft:barrel"),
        ("crate", "minecraft:barrel"),
        ("table", "minecraft:crafting_table"),
        ("leaves", "minecraft:oak_leaves"),
        ("log", "minecraft:oak_log"),
        ("plank", "minecraft:oak_planks"),
        ("wood", "minecraft:oak_planks"),
        ("grass", "minecraft:grass_block"),
        ("dirt", "minecraft:dirt"),
        ("stone", "minecraft:stone"),
        ("gravel", "minecraft:gravel"),
        ("sand", "minecraft:sand"),
        ("glass", "minecraft:glass"),
        ("torch", "minecraft:torch"),
        ("lamp", "minecraft:sea_lantern"),
        ("light", "minecraft:sea_lantern"),
        ("door", "minecraft:oak_door"),
        ("trapdoor", "minecraft:oak_trapdoor"),
        ("slab", "minecraft:stone_slab"),
        ("stair", "minecraft:oak_stairs"),
        ("sofa", "minecraft:oak_stairs"),
        ("chair", "minecraft:oak_stairs"),
        ("fence", "minecraft:oak_fence"),
        ("wall", "minecraft:stone_brick_wall"),
        ("lever", "minecraft:lever"),
        ("hopper", "minecraft:hopper"),
        ("chest", "minecraft:chest"),
        ("wireless", "minecraft:redstone_block"),
        ("receiver", "minecraft:redstone_block"),
        ("transmitter", "minecraft:redstone_block"),
        ("camera", "minecraft:redstone_block"),
        ("laser", "minecraft:redstone_block"),
        ("turret", "minecraft:redstone_block"),
        ("duct", "minecraft:redstone_block"),
        ("cable", "minecraft:redstone_block"),
        ("redstone", "minecraft:redstone_block"),
        ("elevator", "minecraft:iron_block"),
        ("waystone", "minecraft:lodestone"),
    ]

    for keyword, fallback in keyword_map:
        if keyword in name:
            return fallback

    return _DEFAULT_NAMESPACE_FALLBACK


def update_export_block_remap_table(
    path: Optional[str] = None,
    *,
    block_remap_updates: Optional[Dict[str, Optional[str]]] = None,
    auto_block_remap: Optional[bool] = None,
    enabled: Optional[bool] = None,
) -> int:
    if path is None:
        path = _default_remap_path()
    data = _load_raw_rules_data(path)
    changed = 0

    if enabled is not None:
        enabled_bool = bool(enabled)
        if bool(data.get("enabled", True)) != enabled_bool:
            data["enabled"] = enabled_bool
            changed += 1

    if auto_block_remap is not None:
        auto_block_remap_bool = bool(auto_block_remap)
        if bool(data.get("auto_block_remap", True)) != auto_block_remap_bool:
            data["auto_block_remap"] = auto_block_remap_bool
            changed += 1

    if block_remap_updates is not None:
        block_remap = data.get("block_remap")
        if not isinstance(block_remap, dict):
            block_remap = {}

        existing_key_lookup = {
            _normalise_key(existing_key): existing_key for existing_key in block_remap.keys()
        }

        for source_block_id, replacement in block_remap_updates.items():
            source_key = _normalise_key(source_block_id)
            if ":" not in source_key:
                raise ValueError(f"Block remap key must be namespace:block. Got {source_block_id!r}")

            existing_key = existing_key_lookup.get(source_key, source_key)
            if existing_key != source_key and existing_key in block_remap:
                del block_remap[existing_key]
                changed += 1

            replacement_text = None
            if replacement is not None:
                replacement_text = str(replacement).strip()
            if not replacement_text:
                if source_key in block_remap:
                    del block_remap[source_key]
                    changed += 1
                continue

            replacement_block = _parse_blockstate(replacement_text)
            replacement_blockstate = replacement_block.blockstate

            if block_remap.get(source_key) != replacement_blockstate:
                block_remap[source_key] = replacement_blockstate
                changed += 1

            existing_key_lookup[source_key] = source_key

        data["block_remap"] = block_remap

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    return changed


def _append_missing_block_remaps(path: str, blocks: Iterable[Block]) -> int:
    data = _load_raw_rules_data(path)
    block_remap = data.get("block_remap")
    if not isinstance(block_remap, dict):
        block_remap = {}

    namespace_remap = data.get("namespace_remap")
    if not isinstance(namespace_remap, dict):
        namespace_remap = {}

    explicit_namespace_remap = {
        _normalise_key(ns)
        for ns, value in namespace_remap.items()
        if isinstance(value, str)
        and _normalise_key(value) not in {"", _KEEP_SENTINEL}
    }

    existing = {_normalise_key(key) for key in block_remap.keys()}
    added = 0
    for block in sorted(
        set(blocks),
        key=lambda b: (_normalise_key(b.namespace), _normalise_key(b.base_name)),
    ):
        block_id = _normalise_key(block.namespaced_name)
        if block_id in existing:
            continue
        if _normalise_key(block.namespace) in explicit_namespace_remap:
            continue
        block_remap[block.namespaced_name] = _guess_vanilla_blockstate_for_custom(
            block
        )
        existing.add(block_id)
        added += 1

    if added:
        data["block_remap"] = block_remap
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    return added


def _append_missing_namespaces(path: str, namespaces: Iterable[str]) -> int:
    data = _load_raw_rules_data(path)
    namespace_remap = data.get("namespace_remap")
    if not isinstance(namespace_remap, dict):
        namespace_remap = {}

    existing = {_normalise_key(key) for key in namespace_remap.keys()}
    added = 0
    for namespace in sorted({_normalise_key(n) for n in namespaces if n}):
        if namespace not in existing:
            namespace_remap[namespace] = _KEEP_SENTINEL
            existing.add(namespace)
            added += 1

    if added:
        data["namespace_remap"] = namespace_remap
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    return added


def build_export_remap_table_for_selection(
    world: "BaseLevel", dimension: "Dimension", selection: "SelectionGroup"
) -> ExportBlockRemapRules:
    """Ensure the remap table includes each custom namespace found in the selection."""
    rules = load_export_block_remap_rules()
    custom_namespaces: Set[str] = set()
    custom_blocks: Set[Block] = set()

    for cx, cz in selection.chunk_locations():
        try:
            chunk = world.get_chunk(cx, cz, dimension)
            custom_namespaces.update(_collect_chunk_custom_namespaces(chunk))
            custom_blocks.update(_collect_chunk_custom_blocks(chunk))
        except Exception:
            # Ignore unreadable chunks and keep export moving.
            continue

    added_namespaces = _append_missing_namespaces(rules.path, custom_namespaces)

    raw_data = _load_raw_rules_data(rules.path)
    auto_block_remap = bool(raw_data.get("auto_block_remap", True))
    added_block_remaps = 0
    if auto_block_remap:
        added_block_remaps = _append_missing_block_remaps(rules.path, custom_blocks)

    if added_namespaces or added_block_remaps:
        log.info(
            "Updated export remap table (+%s namespaces, +%s block mappings): %s",
            added_namespaces,
            added_block_remaps,
            rules.path,
        )
        rules = load_export_block_remap_rules()
    return rules


def collect_export_remap_preview(
    world: "BaseLevel",
    dimension: "Dimension",
    selection: "SelectionGroup",
    rules: Optional[ExportBlockRemapRules] = None,
) -> ExportRemapPreview:
    if rules is None:
        rules = load_export_block_remap_rules()

    raw_data = _load_raw_rules_data(rules.path)
    chunk_locations = list(selection.chunk_locations())
    total_chunks = len(chunk_locations)
    scanned_chunks = 0
    failed_chunks = 0
    custom_namespaces: Set[str] = set()
    custom_blocks: Set[str] = set()
    custom_block_total = 0
    remapped_block_total = 0
    remap_counts: Dict[Tuple[str, str], int] = {}
    remap_cache: Dict[Block, Block] = {}

    for cx, cz in chunk_locations:
        try:
            chunk = world.get_chunk(cx, cz, dimension)
            usage_counts = _chunk_palette_usage_counts(chunk)
        except Exception:
            failed_chunks += 1
            continue

        scanned_chunks += 1
        for palette_id, placed_count in usage_counts.items():
            block = chunk.block_palette[palette_id]
            namespaces_in_block = _custom_namespaces_in_block(block)
            if not namespaces_in_block:
                continue

            custom_namespaces.update(namespaces_in_block)
            custom_blocks.add(_normalise_key(block.namespaced_name))
            custom_block_total += placed_count

            replacement = _remap_block(block, rules, remap_cache)
            source_name = _normalise_key(block.namespaced_name)
            replacement_name = _normalise_key(replacement.namespaced_name)
            remap_counts[(source_name, replacement_name)] = (
                remap_counts.get((source_name, replacement_name), 0) + placed_count
            )
            if replacement != block:
                remapped_block_total += placed_count

    entries = tuple(
        ExportRemapPreviewEntry(
            source_block=source_block,
            replacement_block=replacement_block,
            block_count=block_count,
        )
        for (source_block, replacement_block), block_count in sorted(
            remap_counts.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )
    )

    return ExportRemapPreview(
        rules_path=rules.path,
        remap_enabled=rules.enabled,
        auto_block_remap=bool(raw_data.get("auto_block_remap", True)),
        total_chunks=total_chunks,
        scanned_chunks=scanned_chunks,
        failed_chunks=failed_chunks,
        custom_namespace_count=len(custom_namespaces),
        custom_block_count=len(custom_blocks),
        custom_block_total=custom_block_total,
        remapped_block_total=remapped_block_total,
        entries=entries,
    )


def load_export_block_remap_rules() -> ExportBlockRemapRules:
    path = _default_remap_path()
    data = _load_raw_rules_data(path)

    enabled = bool(data.get("enabled", True))

    namespace_remap: Dict[str, Optional[Block]] = {}
    for namespace, replacement in data.get("namespace_remap", {}).items():
        try:
            key = _normalise_key(namespace)
            if replacement is None:
                namespace_remap[key] = None
                continue
            replacement_text = str(replacement).strip()
            if (
                not replacement_text
                or _normalise_key(replacement_text) == _KEEP_SENTINEL
            ):
                namespace_remap[key] = None
                continue
            namespace_remap[key] = _parse_blockstate(replacement_text)
        except Exception:
            log.warning(
                "Invalid namespace remap entry for %s in %s", namespace, path
            )

    block_remap: Dict[str, Block] = {}
    for block_id, replacement in data.get("block_remap", {}).items():
        try:
            key = _normalise_key(block_id)
            if ":" not in key:
                raise ValueError("Remap key must be namespace:block")
            block_remap[key] = _parse_blockstate(replacement)
        except Exception:
            log.warning("Invalid block remap entry for %s in %s", block_id, path)

    return ExportBlockRemapRules(
        enabled=enabled,
        namespace_remap=namespace_remap,
        block_remap=block_remap,
        path=path,
    )


def _remap_block(block: Block, rules: ExportBlockRemapRules, cache: Dict[Block, Block]) -> Block:
    if block in cache:
        return cache[block]

    replacement = rules.block_remap.get(_normalise_key(block.namespaced_name))
    if replacement is None and _normalise_key(block.namespace) in rules.namespace_remap:
        replacement = rules.namespace_remap[_normalise_key(block.namespace)]

    base_block = replacement if replacement is not None else block.base_block
    remapped_extras = tuple(_remap_block(extra, rules, cache) for extra in block.extra_blocks)

    if remapped_extras:
        remapped = Block(
            base_block.namespace,
            base_block.base_name,
            base_block.properties,
            remapped_extras,
        )
    else:
        remapped = base_block

    cache[block] = remapped
    return remapped


def remap_chunk_for_export(
    chunk: Chunk, rules: ExportBlockRemapRules
) -> Tuple[Chunk, int]:
    """Return (chunk_to_export, replaced_block_count)."""
    if not rules.enabled:
        return chunk, 0

    try:
        used_palette_ids = _used_palette_ids(chunk)
    except Exception:
        log.exception("Failed reading chunk palette usage for export remap.")
        return chunk, 0

    if not used_palette_ids:
        return chunk, 0

    cache: Dict[Block, Block] = {}
    old_to_new_id: Dict[int, int] = {}
    changed_old_ids = set()
    new_palette = BlockManager()

    for old_id in sorted(used_palette_ids):
        old_block = chunk.block_palette[old_id]
        new_block = _remap_block(old_block, rules, cache)
        old_to_new_id[old_id] = new_palette.get_add_block(new_block)
        if new_block != old_block:
            changed_old_ids.add(old_id)

    if not changed_old_ids:
        return chunk, 0

    chunk_copy = Chunk.unpickle(chunk.pickle(), chunk.block_palette, chunk.biome_palette)
    replaced_blocks = 0

    for cy in chunk_copy.blocks.sub_chunks:
        section = chunk_copy.blocks.get_sub_chunk(cy).copy()
        for old_id, new_id in old_to_new_id.items():
            mask = section == old_id
            if numpy.any(mask):
                if old_id in changed_old_ids:
                    replaced_blocks += int(mask.sum())
                section[mask] = new_id
        chunk_copy.blocks.add_sub_chunk(cy, section)

    chunk_copy._block_palette = new_palette
    chunk_copy.changed = True
    return chunk_copy, replaced_blocks


# Helper module only; keep plugin autoloader quiet by exposing an empty export list.
export = []
