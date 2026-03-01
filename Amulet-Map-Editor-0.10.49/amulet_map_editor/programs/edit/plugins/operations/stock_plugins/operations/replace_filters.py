import numpy


MATCH_MODE_ANY_OF = "any_of"
MATCH_MODE_NONE_OF = "none_of"


def match_mode_replace_mask(blocks, matching_ids, match_mode: str):
    """Build a replace mask for the given mode."""
    return numpy.isin(blocks, matching_ids, invert=match_mode == MATCH_MODE_NONE_OF)
