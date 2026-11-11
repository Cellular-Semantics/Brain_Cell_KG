"""Tests for the cell_set_map.csv lookup (issue #14: accession-suffixed labels)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "utils"))

from cell_set_map import load_type_curies, strip_accession_suffix  # noqa: E402

HEADER = "dataset,labelset,labelset_rank,label,iri,curie\n"
WMB = "Whole Mouse Brain Taxonomy"


def test_strip_accession_suffix():
    c = "WMB:CS20230722_SUBC_061"
    assert strip_accession_suffix("061 STR D1 Gaba CS20230722_SUBC_061", c) == "061 STR D1 Gaba"
    assert strip_accession_suffix("061 STR D1 Gaba", c) == "061 STR D1 Gaba"
    # a different accession is left alone
    assert strip_accession_suffix("x CS20230722_SUBC_062", c) == "x CS20230722_SUBC_062"


def test_load_type_curies_resolves_suffixed_and_bare(tmp_path):
    p = tmp_path / "cell_set_map.csv"
    p.write_text(
        HEADER
        + f"{WMB},subclass,2,061 STR D1 Gaba CS20230722_SUBC_061,i,WMB:CS20230722_SUBC_061\n"
        + f"{WMB},supertype,1,0270 STR D1 Gaba_6,i,WMB:CS20230722_SUPT_0270\n"
        + "Other,subclass,2,061 STR D1 Gaba,i,X:1\n"
        + f"{WMB},cluster,0,,i,WMB:CS20230722_CLUS_0001\n"
    )
    assert load_type_curies(p) == {
        ("subclass", "061 STR D1 Gaba"): "WMB:CS20230722_SUBC_061",
        ("supertype", "0270 STR D1 Gaba_6"): "WMB:CS20230722_SUPT_0270",
    }


def test_load_type_curies_rejects_collision(tmp_path):
    p = tmp_path / "cell_set_map.csv"
    p.write_text(
        HEADER
        + f"{WMB},subclass,2,061 A CS20230722_SUBC_061,i,WMB:CS20230722_SUBC_061\n"
        + f"{WMB},subclass,2,061 A,i,WMB:CS20230722_SUBC_999\n"
    )
    with pytest.raises(ValueError):
        load_type_curies(p)


def test_committed_map_covers_suffixed_wmb_sets():
    path = REPO / "reports" / "cell_set_map.csv"
    if not path.exists():
        pytest.skip("reports/cell_set_map.csv absent")
    lookup = load_type_curies(path)
    assert lookup[("subclass", "061 STR D1 Gaba")] == "WMB:CS20230722_SUBC_061"
    assert not any(l.endswith(c.split(":")[1]) for (_, l), c in lookup.items())
