from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, Set, Tuple, TYPE_CHECKING

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

_DEFAULT_REMAP_TABLE = {
    "enabled": True,
    "namespace_remap": {
        "better_on_bedrock": "minecraft:stone",
        "ecbl_bs": "minecraft:iron_block",
        "f": "minecraft:white_wool",
        "ftb": "minecraft:oak_planks",
        "ftb_tc": "minecraft:stone",
        "vtng_rt": "minecraft:redstone_block",
    },
    "block_remap": {
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
    },
    "notes": [
        "This table is used only during export.",
        "Keys in block_remap are exact namespace:block ids.",
        "namespace_remap applies when there is no exact block_remap match.",
        "Values are fallback vanilla blockstates, eg minecraft:stone or minecraft:oak_planks.",
    ],
}


@dataclass(frozen=True)
class ExportBlockRemapRules:
    enabled: bool
    namespace_remap: Dict[str, Block]
    block_remap: Dict[str, Block]
    path: str


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


def _load_raw_rules_data(path: str) -> dict:
    _ensure_default_file(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Rules file must contain a JSON object.")
        return data
    except Exception:
        log.exception("Could not parse export block remap table at %s", path)
        return dict(_DEFAULT_REMAP_TABLE)


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
    for palette_id in _used_palette_ids(chunk):
        block = chunk.block_palette[palette_id]
        for block_part in _iter_blocks(block):
            namespace = _normalise_key(block_part.namespace)
            if namespace and namespace not in {"minecraft", "universal"}:
                namespaces.add(namespace)
    return namespaces


def _append_missing_namespaces(path: str, namespaces: Iterable[str]) -> int:
    data = _load_raw_rules_data(path)
    namespace_remap = data.get("namespace_remap")
    if not isinstance(namespace_remap, dict):
        namespace_remap = {}

    existing = {_normalise_key(key) for key in namespace_remap.keys()}
    added = 0
    for namespace in sorted({_normalise_key(n) for n in namespaces if n}):
        if namespace not in existing:
            namespace_remap[namespace] = _DEFAULT_NAMESPACE_FALLBACK
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

    for cx, cz in selection.chunk_locations():
        try:
            chunk = world.get_chunk(cx, cz, dimension)
            custom_namespaces.update(_collect_chunk_custom_namespaces(chunk))
        except Exception:
            # Ignore unreadable chunks and keep export moving.
            continue

    added = _append_missing_namespaces(rules.path, custom_namespaces)
    if added:
        log.info(
            "Added %s custom namespace remap entries to export table: %s",
            added,
            rules.path,
        )
        rules = load_export_block_remap_rules()
    return rules


def load_export_block_remap_rules() -> ExportBlockRemapRules:
    path = _default_remap_path()
    data = _load_raw_rules_data(path)

    enabled = bool(data.get("enabled", True))

    namespace_remap: Dict[str, Block] = {}
    for namespace, replacement in data.get("namespace_remap", {}).items():
        try:
            namespace_remap[_normalise_key(namespace)] = _parse_blockstate(replacement)
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
    if replacement is None:
        replacement = rules.namespace_remap.get(_normalise_key(block.namespace))

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
