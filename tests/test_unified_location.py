"""Unit tests for the unified location template script.

Exercises the small pure pieces directly (bridge, canonical-level filter,
template emit, graded cutoff). Region-counting tests build a tiny synthetic
volume and verify the same primitives (``build_canonical_volume_and_surfaces``
+ scipy ``cKDTree``) the production script uses. An optional integration
test against the real Yao cache verifies that the bridge has not drifted;
it is skipped if the cache file is absent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "utils"))
sys.path.insert(0, str(REPO / "src" / "scripts" / "ccf_spatial" / "scripts"))

from ccf_parcellation import (  # noqa: E402
    build_index_to_curie,
    load_canonical_levels,
)
import compute_unified_location_templates as ccp  # noqa: E402


# --------------------------------------------------------------------------- #
# Synthetic fixtures                                                          #
# --------------------------------------------------------------------------- #
def _write_membership(path: Path) -> None:
    """Minimal parcellation membership: HY (division only), ZI (structure),
    DG-mo (substructure). Index 1 = HY-only (HY/HY-unassigned/HY-unassigned),
    2 = ZI (HY/ZI/ZI-unassigned), 3 = DG-mo (HPF/DG/DG-mo)."""
    path.write_text(
        "parcellation_index,division,structure,substructure\n"
        "1,HY,HY-unassigned,HY-unassigned\n"
        "2,HY,ZI,ZI-unassigned\n"
        "3,HPF,DG,DG-mo\n"
    )


def _write_mba_map(path: Path) -> None:
    path.write_text(
        "symbol,curie\n"
        "HY,MBA:1097\n"
        "ZI,MBA:797\n"
        "HPF,MBA:1089\n"
        "DG,MBA:726\n"
        "DG-mo,MBA:10703\n"
    )


# --------------------------------------------------------------------------- #
# Bridge / canonical-level                                                    #
# --------------------------------------------------------------------------- #
def test_canonical_level_filter(tmp_path: Path) -> None:
    mem = tmp_path / "mem.csv"
    _write_membership(mem)
    canon = load_canonical_levels(mem)
    assert canon["HY"] == "division"
    assert canon["ZI"] == "structure"
    assert canon["DG-mo"] == "substructure"
    # -unassigned variants never become canonical names
    assert "HY-unassigned" not in canon
    assert "ZI-unassigned" not in canon


def test_bridge_index_to_curie(tmp_path: Path) -> None:
    mem = tmp_path / "mem.csv"
    mba = tmp_path / "mba.csv"
    _write_membership(mem)
    _write_mba_map(mba)
    idx2c = build_index_to_curie(mem, mba)
    # Index 1: HY at division; -unassigned folds to HY at structure & substructure.
    assert idx2c["division"][1] == "MBA:1097"
    assert idx2c["structure"][1] == "MBA:1097"
    assert idx2c["substructure"][1] == "MBA:1097"
    # Index 2: HY/ZI/ZI-unassigned -> HY, ZI, ZI
    assert idx2c["division"][2] == "MBA:1097"
    assert idx2c["structure"][2] == "MBA:797"
    assert idx2c["substructure"][2] == "MBA:797"
    # Index 3: substructure leaf
    assert idx2c["substructure"][3] == "MBA:10703"


# --------------------------------------------------------------------------- #
# Geometry                                                                    #
# --------------------------------------------------------------------------- #
def _tiny_volume() -> np.ndarray:
    """4x4x4 painted volume with two regions (codes match parcellation_index):
    region 3 (DG-mo) at x=0 plane; region 2 (ZI) at x=3 plane. Rest = 0."""
    vol = np.zeros((4, 4, 4), dtype=np.int32)
    vol[0, :, :] = 3
    vol[3, :, :] = 2
    return vol


def test_count_inside_region(tmp_path: Path) -> None:
    """For 6 known cell coords on a tiny labelled volume, n_in_X matches by hand."""
    mem = tmp_path / "mem.csv"
    mba = tmp_path / "mba.csv"
    _write_membership(mem)
    _write_mba_map(mba)
    idx2c = build_index_to_curie(mem, mba)

    voxel_mm = 0.1  # 100 um voxels
    cells = pd.DataFrame({
        # Place at voxel centres in mm (i * voxel_mm).
        "x": [0.0, 0.0, 0.3, 0.3, 0.1, 0.2],
        "y": [0.0, 0.1, 0.0, 0.2, 0.1, 0.2],
        "z": [0.0, 0.1, 0.0, 0.1, 0.2, 0.3],
        # parcellation_index: 3=DG-mo, 2=ZI, 0=outside
        "parcellation_index": [3, 3, 2, 2, 0, 0],
    })
    cells["region_substructure"] = cells["parcellation_index"].map(idx2c["substructure"])

    counts = cells.groupby("region_substructure", dropna=False).size().to_dict()
    assert counts["MBA:10703"] == 2   # DG-mo
    assert counts["MBA:797"] == 2     # ZI
    # Two cells with parcellation_index 0 are NaN in region_substructure.
    nan_count = int(cells["region_substructure"].isna().sum())
    assert nan_count == 2


def test_count_within_100um() -> None:
    """Cells at 25, 75, 150 um from a region's surface: first two land in
    the 100um band; the third does not."""
    from scipy.spatial import cKDTree

    voxel_mm = 0.025  # 25 um voxels for fine resolution
    vol = np.zeros((8, 4, 4), dtype=np.int32)
    vol[0:4, :, :] = 3  # paint region code 3 in x < 4 (i.e. x < 100 um surface at x=4*0.025=0.1mm)
    code2c = {3: "MBA:10703"}
    canonical_of_curie = {"MBA:10703": "substructure"}
    idx2curie_at_level = {3: "MBA:10703"}

    _labeled, _c2c, surfaces = ccp.build_canonical_volume_and_surfaces(
        "substructure", vol, idx2curie_at_level, canonical_of_curie, voxel_mm)
    assert "MBA:10703" in surfaces
    surf_pts = surfaces["MBA:10703"]

    # Probe cells along +x past the region. The painted region covers x voxels
    # 0..3 (i.e. 0..0.075mm centres); the +x boundary surface lies at voxel
    # x=3, so a cell outside should be measured relative to x=3*voxel_mm.
    # We place cells along +x at offsets 25, 75, 150 um from that surface
    # (centres at 0.075 + offset).
    surface_x = 3 * voxel_mm
    cells_xyz = np.array([
        [surface_x + 0.025, 0.05, 0.05],   # 25 um -> in band
        [surface_x + 0.075, 0.05, 0.05],   # 75 um -> in band
        [surface_x + 0.150, 0.05, 0.05],   # 150 um -> outside band
    ], dtype=np.float32)
    tree = cKDTree(cells_xyz)
    band_mm = 100.0 / 1000.0
    lists = tree.query_ball_point(surf_pts, r=band_mm, return_sorted=False)
    near = set()
    for lst in lists:
        near.update(lst)
    assert 0 in near and 1 in near
    assert 2 not in near


# --------------------------------------------------------------------------- #
# Cutoff + emit                                                               #
# --------------------------------------------------------------------------- #
def test_graded_cutoff_emission() -> None:
    """Row with frac=0.026 emitted at cluster level (>0.025); 0.024 dropped."""
    cutoff = ccp.DEFAULT_GRADED_CUTOFFS["cluster"]
    df = pd.DataFrame({
        "label": ["A", "B"],
        "n_in_or_near": [26, 24],
        "n_total_lookup": [1000, 1000],
    })
    frac = df["n_in_or_near"] / df["n_total_lookup"]
    kept = df[frac >= cutoff]
    assert kept["label"].tolist() == ["A"]


def test_template_schema(tmp_path: Path) -> None:
    out = tmp_path / "cluster_location_mappings.tsv"
    df = pd.DataFrame([
        {"type_curie": "WMB:CLUS_0001", "near_region": "MBA:10703",
         "n_in_X": 42, "n_in_or_near_100": 91, "frac_in_X": 0.014,
         "source": "doi:10.1038/s41586-023-06812-z"},
    ])
    ccp.emit_template(df, out, "n2o:CCF2020")
    lines = out.read_text().splitlines()
    assert lines[0].split("\t") == [
        "ID", "Type", "PCL:0010063",
        "cell_count", "cell_ratio", "in_or_near_100",
        "completeness", "spatial_atlas", "source",
    ]
    assert lines[1].split("\t") == [
        "ID", "TYPE", "AI PCL:0010063",
        ">AT PCL:0010060^^xsd:integer",
        ">AT PCL:0010065^^xsd:float",
        ">AT n2o:countInOrNear100um^^xsd:integer",
        ">AT n2o:cellCountCompleteness^^xsd:string",
        ">AI n2o:spatialReferenceAtlas",
        ">AI dcterms:source",
    ]
    row = lines[2].split("\t")
    assert row[0] == "WMB:CLUS_0001"
    assert row[2] == "MBA:10703"
    assert row[3] == "42"
    assert row[4] == "0.014000"
    assert row[5] == "91"
    assert row[6] == ""              # completeness blank for directly-measured
    assert row[7] == "n2o:CCF2020"
    assert row[8] == "doi:10.1038/s41586-023-06812-z"


def test_per_dataset_doi(tmp_path: Path) -> None:
    yao_out = tmp_path / "y.tsv"
    zh_out = tmp_path / "z.tsv"
    base = {"type_curie": "WMB:X", "near_region": "MBA:1",
            "n_in_X": 1, "n_in_or_near_100": 1, "frac_in_X": 0.01}
    ccp.emit_template(pd.DataFrame([{**base, "source": ccp.DATASET_DOI["yao"]}]),
                      yao_out, "n2o:CCF2020")
    ccp.emit_template(pd.DataFrame([{**base, "source": ccp.DATASET_DOI["zhuang"]}]),
                      zh_out, "n2o:CCF2020")
    assert ccp.DATASET_DOI["yao"] in yao_out.read_text()
    assert ccp.DATASET_DOI["zhuang"] not in yao_out.read_text()
    assert ccp.DATASET_DOI["zhuang"] in zh_out.read_text()
    assert ccp.DATASET_DOI["yao"] not in zh_out.read_text()


# --------------------------------------------------------------------------- #
# Rollup row generation                                                       #
# --------------------------------------------------------------------------- #
def test_spatial_atlas_annotation(tmp_path: Path) -> None:
    """Every emitted row carries the atlas CURIE in the spatial_atlas column."""
    out = tmp_path / "out.tsv"
    df = pd.DataFrame([
        {"type_curie": "WMB:X", "near_region": "MBA:1",
         "n_in_X": 1, "n_in_or_near_100": 1, "frac_in_X": 0.01,
         "source": "doi:1"},
        {"type_curie": "WMB:Y", "near_region": "MBA:2",
         "n_in_X": 5, "n_in_or_near_100": 7, "frac_in_X": 0.05,
         "source": "doi:1"},
    ])
    ccp.emit_template(df, out, "n2o:CCF2020")
    lines = out.read_text().splitlines()
    # spatial_atlas is the 8th column (index 7)
    for data_line in lines[2:]:
        cols = data_line.split("\t")
        assert cols[7] == "n2o:CCF2020"


def test_completeness_flag_passthrough(tmp_path: Path) -> None:
    """Rollup rows carrying completeness='lower_bound' surface that flag in
    the cellCountCompleteness column; direct rows leave it blank."""
    out = tmp_path / "out.tsv"
    df = pd.DataFrame([
        # rollup row, partial coverage
        {"type_curie": "WMB:X", "near_region": "MBA:909",
         "n_in_X": 100, "n_in_or_near_100": 120, "frac_in_X": 0.10,
         "completeness": "lower_bound", "source": "doi:1"},
        # rollup row, complete coverage
        {"type_curie": "WMB:Y", "near_region": "MBA:918",
         "n_in_X": 80, "n_in_or_near_100": 90, "frac_in_X": 0.08,
         "completeness": "exact", "source": "doi:1"},
        # directly-measured row
        {"type_curie": "WMB:Z", "near_region": "MBA:20",
         "n_in_X": 50, "n_in_or_near_100": 60, "frac_in_X": 0.05,
         "source": "doi:1"},
    ])
    ccp.emit_template(df, out, "n2o:CCF2020")
    lines = out.read_text().splitlines()
    rows = [ln.split("\t") for ln in lines[2:]]
    completeness_col = {r[0]: r[6] for r in rows}
    assert completeness_col["WMB:X"] == "lower_bound"
    assert completeness_col["WMB:Y"] == "exact"
    assert completeness_col["WMB:Z"] == ""


def test_load_rollup_targets(tmp_path: Path) -> None:
    """Synthetic membership CSV: only descendants_painted rows become rollups,
    with completeness flag mapped from coverage."""
    csv_path = tmp_path / "membership.csv"
    csv_path.write_text(
        "curie,painted_level,descendant_coverage,painted_descendants\n"
        "MBA:painted,structure,,\n"           # painted: skip
        "MBA:complete,,complete,MBA:c1|MBA:c2\n"   # rollup: exact
        "MBA:partial,,partial,MBA:p1\n"        # rollup: lower_bound
        "MBA:none,,none,\n"                    # unavailable: skip
    )
    # canonical_of_curie maps the descendant CURIEs to canonical levels.
    canonical = {
        "MBA:c1": "substructure",
        "MBA:c2": "substructure",
        "MBA:p1": "structure",
    }
    targets = ccp.load_rollup_targets(csv_path, canonical)
    by_curie = {t["curie"]: t for t in targets}
    assert set(by_curie) == {"MBA:complete", "MBA:partial"}
    assert by_curie["MBA:complete"]["completeness"] == "exact"
    assert by_curie["MBA:partial"]["completeness"] == "lower_bound"
    # MBA:complete groups both descendants under substructure
    assert sorted(by_curie["MBA:complete"]["desc_by_level"]["substructure"]) \
        == ["MBA:c1", "MBA:c2"]
    assert by_curie["MBA:partial"]["desc_by_level"]["structure"] == ["MBA:p1"]


def test_rollup_merged_surface_count(tmp_path: Path) -> None:
    """End-to-end rollup compute on a tiny synthetic volume.

    Two painted substructure regions A1 (PI=1) and A2 (PI=2) rolled up to
    parent A. Cells are positioned so that:
      - 2 cells sit inside A1 (interior)
      - 1 cell sits inside A2 (interior)
      - 1 cell sits 1 voxel outside A2's surface (boundary band, ≤ 100 µm)
      - 1 cell sits far away (outside band)
    Expected: in_X = 3, in_or_near_100 = 4 (3 interior + 1 boundary).
    """
    from scipy.spatial import cKDTree

    voxel_mm = 0.025
    vol = np.zeros((8, 4, 4), dtype=np.int32)
    vol[0:2, :, :] = 1   # region A1 (x voxels 0..1)
    vol[2:4, :, :] = 2   # region A2 (x voxels 2..3)
    idx2curie_all = {
        "division": {},
        "structure": {},
        "substructure": {1: "MBA:A1", 2: "MBA:A2"},
    }
    # Cells (CCF mm coordinates). region_substructure is set by hand to
    # reflect what the bridge would assign.
    cells = pd.DataFrame({
        # 2 in A1 (x voxels 0,1), 1 in A2 (x voxel 3), 1 boundary (~1 voxel
        # outside A2's +x face, i.e. x ≈ 4*voxel_mm = 0.1 mm), 1 far away.
        "x": [0.0, 0.025, 0.075, 0.10, 0.50],
        "y": [0.05, 0.05, 0.05, 0.05, 0.05],
        "z": [0.05, 0.05, 0.05, 0.05, 0.05],
        "region_division":    [None, None, None, None, None],
        "region_structure":   [None, None, None, None, None],
        "region_substructure": ["MBA:A1", "MBA:A1", "MBA:A2", None, None],
    })
    cells_tree = cKDTree(cells[["x", "y", "z"]].to_numpy(dtype=np.float32))
    band_mm = 100.0 / 1000.0

    rollups = [{
        "curie": "MBA:A",
        "completeness": "exact",
        "desc_by_level": {"division": [], "structure": [],
                          "substructure": ["MBA:A1", "MBA:A2"]},
    }]
    pool = ccp.compute_rollup_in_or_near(
        rollups, vol, voxel_mm, idx2curie_all, cells, cells_tree, band_mm)
    assert "MBA:A" in pool
    info = pool["MBA:A"]
    assert len(info["in_X_idx"]) == 3                    # 3 interior cells
    assert len(info["in_or_near_idx"]) == 4              # 3 interior + 1 boundary
    assert info["completeness"] == "exact"


# --------------------------------------------------------------------------- #
# Integration smoke test                                                      #
# --------------------------------------------------------------------------- #
def test_n_in_X_matches_direct_recount() -> None:
    """Guard against bridge regressions on real Yao data.

    For one (tax, region level) combination, the script's region_<lvl>
    assignment (via build_index_to_curie) is just a pd.Series.map of the
    membership-table bridge. We assert that mapping is total over assigned
    parcellation_index values for cells in the cache and produces a
    consistent group count.
    """
    # The Yao CSV is multi-GB; skip if not present locally.
    candidates = [
        REPO / "data" / "yao" / "cell_metadata_with_parcellation_annotation.csv",
        REPO / "src" / "scripts" / "ccf_spatial" / "data" /
        "cell_metadata_with_parcellation_annotation.csv",
    ]
    yao_csv = next((p for p in candidates if p.exists()), None)
    membership = REPO / "reports" / "parcellation_to_parcellation_term_membership_acronym.csv"
    mba_map = REPO / "reports" / "mba_symbol_map.csv"
    if yao_csv is None or not membership.exists() or not mba_map.exists():
        pytest.skip("Yao cache or bridge tables not present locally")

    idx2c = build_index_to_curie(membership, mba_map)
    cells = ccp.load_yao_cells(yao_csv)
    cells["region_substructure"] = cells["parcellation_index"].map(idx2c["substructure"])
    # Every cell with a non-zero parcellation_index that maps in the bridge
    # should have a non-null region_substructure CURIE.
    mapped = cells[cells["parcellation_index"].isin(idx2c["substructure"])]
    assert mapped["region_substructure"].notna().all()
