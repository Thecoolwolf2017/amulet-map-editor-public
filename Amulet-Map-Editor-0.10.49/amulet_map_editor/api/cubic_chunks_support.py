from __future__ import annotations

import os


def is_probably_cubic_chunks_world(path: str) -> bool:
    """
    Heuristic detection for legacy Cubic Chunks Java worlds.

    The mod format commonly includes one or more of:
    - region2d/ and region3d/ directories
    - data/cubicChunksData.dat
    """
    world_path = os.path.abspath(path)
    if not os.path.isdir(world_path):
        return False
    if not os.path.isfile(os.path.join(world_path, "level.dat")):
        return False

    marker_rel_paths = (
        "region2d",
        "region3d",
        os.path.join("data", "cubicChunksData.dat"),
        os.path.join("data", "cubicchunksdata.dat"),
    )
    for marker in marker_rel_paths:
        marker_path = os.path.join(world_path, marker)
        if os.path.isdir(marker_path) or os.path.isfile(marker_path):
            return True

    # Some worlds place format folders under per-dimension directories.
    try:
        children = os.listdir(world_path)
    except OSError:
        return False

    for child_name in children:
        child_path = os.path.join(world_path, child_name)
        if not os.path.isdir(child_path):
            continue
        if os.path.isdir(os.path.join(child_path, "region2d")):
            return True
        if os.path.isdir(os.path.join(child_path, "region3d")):
            return True

    return False


def cubic_chunks_not_supported_message(path: str) -> str:
    return (
        "This world appears to use the Cubic Chunks format.\n\n"
        "Cubic Chunks world loading is not supported in this Amulet build.\n"
        "Support requires format-loader changes in Amulet-Core.\n\n"
        f"Path:\n{os.path.abspath(path)}"
    )
