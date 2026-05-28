#!/usr/bin/env python3
"""Shared CCF parcellation bridge: parcellation_index -> acronym -> MBA CURIE.

The Allen-CCF-2020 painted annotation volume labels every voxel with a
``parcellation_index``. Two tables already in this repo turn that index into a
knowledge-graph CURIE:

    parcellation_index --(membership table)--> acronym at each region level
    acronym            --(mba_symbol_map.csv)--> MBA:nnn CURIE

Centralising both lookups here lets the cell-count matrix scripts and the
spatial-proximity scripts share one implementation. Functions take explicit
file paths (no hard-wired locations) so callers / the Makefile own I/O paths.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

# Region granularities present in the Allen-CCF-2020 membership table, finest last.
REGION_LEVELS = ("division", "structure", "substructure")

_UNASSIGNED = "unassigned"
_UNASSIGNED_SUFFIX = "-unassigned"


def load_parcellation_lookup(membership_csv: Path) -> Dict[int, Dict[str, str]]:
    """``parcellation_index`` -> ``{division, structure, substructure}`` acronyms.

    Pure read of the cached
    ``parcellation_to_parcellation_term_membership_acronym.csv`` view. The
    caller is responsible for ensuring the file exists (download it first if
    needed).
    """
    lookup: Dict[int, Dict[str, str]] = {}
    with open(membership_csv) as f:
        for row in csv.DictReader(f):
            try:
                pi = int(row["parcellation_index"])
            except (KeyError, ValueError):
                continue
            lookup[pi] = {lvl: (row.get(lvl) or "") for lvl in REGION_LEVELS}
    return lookup


def load_canonical_levels(membership_csv: Path) -> Dict[str, str]:
    """Acronym -> the first region level it appears in unsuffixed.

    The membership table writes ``<X>-unassigned`` in finer columns when the
    region has no further subdivision; this picks the first column (division ->
    structure -> substructure) where the bare acronym appears, i.e. its native
    home in the Allen hierarchy. ``MB`` is a division; ``ZI`` a structure;
    ``DG-mo`` a substructure. Used to keep each region in exactly one level's
    proximity table - without this, coarse regions fold-bleed into finer
    tables via the ``<X>-unassigned`` -> ``<X>`` rule applied by
    :func:`build_index_to_curie`.
    """
    out: Dict[str, str] = {}
    with open(membership_csv) as f:
        for row in csv.DictReader(f):
            for lvl in REGION_LEVELS:
                v = row.get(lvl) or ""
                if not v or v == _UNASSIGNED or v.endswith(_UNASSIGNED_SUFFIX):
                    continue
                if v not in out:
                    out[v] = lvl
    return out


def load_acronym_to_curie(mba_symbol_map_csv: Path) -> Dict[str, str]:
    """Region acronym (``symbol``) -> MBA CURIE, from ``reports/mba_symbol_map.csv``."""
    import pandas as pd

    df = pd.read_csv(mba_symbol_map_csv)
    return {
        str(sym): str(curie)
        for sym, curie in zip(df["symbol"], df["curie"])
        if pd.notna(sym) and pd.notna(curie)
    }


def build_index_to_curie(
    membership_csv: Path, mba_symbol_map_csv: Path
) -> Dict[str, Dict[int, str]]:
    """Per region level, map ``parcellation_index`` -> MBA CURIE.

    ``<X>-unassigned`` acronyms are folded back to the parent ``<X>`` before the
    CURIE lookup (mirrors the location-template logic). Index 0, empty/unassigned
    acronyms, and acronyms with no CURIE are omitted at the relevant level.

    Returns ``{level: {parcellation_index: curie}}``.
    """
    parc = load_parcellation_lookup(membership_csv)
    acro2curie = load_acronym_to_curie(mba_symbol_map_csv)

    out: Dict[str, Dict[int, str]] = {lvl: {} for lvl in REGION_LEVELS}
    for pi, levels in parc.items():
        if pi == 0:  # outside any parcellated region
            continue
        for lvl in REGION_LEVELS:
            acro = levels[lvl]
            if not acro or acro == _UNASSIGNED:
                continue
            if acro.endswith(_UNASSIGNED_SUFFIX):
                acro = acro[: -len(_UNASSIGNED_SUFFIX)]
            curie = acro2curie.get(acro)
            if curie:
                out[lvl][pi] = curie
    return out
