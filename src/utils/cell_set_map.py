"""Load reports/cell_set_map.csv as a (labelset, label) -> CURIE lookup.

Source data (MERFISH cell metadata, cell-count tables) names WMB cell sets by
their bare label, e.g. ``061 STR D1 Gaba``. In the KG some cell sets carry
the accession appended to the label (``061 STR D1 Gaba CS20230722_SUBC_061``),
so an exact label match silently drops them (issue #14). The suffix is
stripped here, keyed off the CURIE's local id, so both forms resolve.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

WMB_DATASET = "Whole Mouse Brain Taxonomy"


def strip_accession_suffix(label: str, curie: str) -> str:
    """Return ``label`` without a trailing `` <accession>`` taken from ``curie``."""
    suffix = " " + curie.split(":", 1)[-1]
    return label[: -len(suffix)] if label.endswith(suffix) else label


def load_type_curies(path: Path | str, dataset: str = WMB_DATASET) -> dict:
    """``{(labelset, bare_label): curie}`` for one dataset in cell_set_map.csv.

    Raises ValueError if stripping makes two cell sets share a key, rather
    than letting one silently overwrite the other.
    """
    csmap = pd.read_csv(path)
    csmap = csmap[csmap["dataset"] == dataset].dropna(subset=["label", "curie"])
    lookup: dict = {}
    for _, r in csmap.iterrows():
        key = (r["labelset"], strip_accession_suffix(r["label"], r["curie"]))
        if key in lookup and lookup[key] != r["curie"]:
            raise ValueError(
                f"{path}: {key} maps to both {lookup[key]} and {r['curie']}")
        lookup[key] = r["curie"]
    return lookup
