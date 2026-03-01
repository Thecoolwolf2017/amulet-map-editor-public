import numpy


def chunk_is_effectively_empty(world, chunk) -> bool:
    """Return True when a chunk only contains air and no entities."""
    if getattr(chunk, "block_entities", None):
        return False
    if getattr(chunk, "entities", None):
        return False

    air_namespaced = {
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "universal_minecraft:air",
        "universal_minecraft:cave_air",
        "universal_minecraft:void_air",
    }
    for block_id in numpy.unique(chunk.blocks):
        block = world.block_palette[int(block_id)]
        if getattr(block, "extra_blocks", None):
            return False
        if getattr(block, "namespaced_name", None) not in air_namespaced:
            return False
    return True
