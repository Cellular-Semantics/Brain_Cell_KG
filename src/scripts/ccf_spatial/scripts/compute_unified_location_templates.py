#!/usr/bin/env python3
"""Per-type unified location templates from registered single-cell coordinates.

Emits one ``PCL:0010063`` "has soma location" edge per (cell type T, region B)
pair, carrying:

  - ``cell_count``         cells of T whose resident region IS B
  - ``cell_ratio``         ``cell_count`` / total cells of T (per dataset)
  - ``in_or_near_100``     cells of T inside B OR within 100 um of B's painted
                           surface (= ``cell_count`` plus the boundary band)

A row is emitted when ``in_or_near_100 / total >=`` the per-taxonomy graded
cutoff (neurotransmitter 0.5%, class 0.75%, subclass 1%, supertype 1.5%,
cluster 2.5%). This unifies what used to be two parallel edge types
(``PCL:0010063`` location + ``n2o:locatedInOrNear`` proximity) into a single
fact per (T, B) - the boundary-band count captures the registration-noise
'or near' aspect while the interior count keeps the strict soma-location
semantics.

Each region appears in exactly one level's output: the first level where its
acronym is named in the membership table without ``-unassigned`` (its
'canonical level'). So coarse regions like ``HY`` do not leak into structure
or substructure tables, and ``ZI`` does not leak into the substructure table.

Distance is measured to the *dense* painted surface (KD-tree of B's boundary
voxels in CCF mm); cells are queried against a single global KD-tree.

Runs per-dataset (``--dataset yao`` or ``--dataset zhuang``) so the source DOI
on each emitted edge is unambiguous.

Outputs, per taxonomy level (5 of each):
  * ``<reports>/cell_proximity_<taxlevel>.csv``                      inspection CSV
  * ``<templates>/<taxlevel>_location_mappings[_zhuang].tsv``        ROBOT template

Paths are explicit args so the Makefile owns I/O paths.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "utils"))
from ccf_parcellation import (  # noqa: E402
    REGION_LEVELS,
    build_index_to_curie,
    load_canonical_levels,
)

TAXONOMY_LEVELS = ["neurotransmitter", "class", "subclass", "supertype", "cluster"]
PROXIMITY_BAND_UM = 100.0

# Per-taxonomy emit cutoffs applied to frac_in_or_near_100. Coarser levels
# spread across more regions so use a lower floor; a flat cutoff would
# over-prune broad types (a broad subclass's hippocampal share can fall below
# the cluster floor even when its child clusters are clearly hippocampal).
DEFAULT_GRADED_CUTOFFS = {
    "neurotransmitter": 0.005,
    "class": 0.0075,
    "subclass": 0.01,
    "supertype": 0.015,
    "cluster": 0.025,
}

DATASET_DOI = {
    "yao": "doi:10.1038/s41586-023-06812-z",
    "zhuang": "doi:10.1038/s41586-023-06808-9",
}


# --------------------------------------------------------------------------- #
# Cell loading                                                                #
# --------------------------------------------------------------------------- #
def load_yao_cells(path: Path) -> pd.DataFrame:
    """Yao WMB cells: x/y/z (CCF mm), parcellation_index, taxonomy labels."""
    cols = (["x_ccf", "y_ccf", "z_ccf", "parcellation_index"] + TAXONOMY_LEVELS)
    df = pd.read_csv(path, usecols=cols, low_memory=False)
    df = df.rename(columns={"x_ccf": "x", "y_ccf": "y", "z_ccf": "z"})
    df["dataset"] = "yao"
    return df


def load_zhuang_cells(cache_dir: Path, datasets, cluster_release, ccf_release) -> pd.DataFrame:
    """Zhuang ABCA cells: join cluster annotation + ccf_coordinates on cell_label."""
    frames = []
    for ds in datasets:
        meta = cache_dir / "metadata" / ds / cluster_release / "views" / \
            "cell_metadata_with_cluster_annotation.csv"
        ccf = cache_dir / "metadata" / f"{ds}-CCF" / ccf_release / "ccf_coordinates.csv"
        if not meta.exists() or not ccf.exists():
            print(f"  skip {ds}: missing cached files")
            continue
        m = pd.read_csv(meta, usecols=["cell_label"] + TAXONOMY_LEVELS, low_memory=False)
        c = pd.read_csv(ccf, usecols=["cell_label", "x", "y", "z", "parcellation_index"],
                        low_memory=False)
        frames.append(m.merge(c, on="cell_label", how="inner"))
        print(f"  {ds}: {len(frames[-1]):,} cells")
    if not frames:
        return pd.DataFrame(columns=["x", "y", "z", "parcellation_index"]
                            + TAXONOMY_LEVELS + ["dataset"])
    out = pd.concat(frames, ignore_index=True)
    out["dataset"] = "zhuang"
    return out


# --------------------------------------------------------------------------- #
# Geometry / volume                                                           #
# --------------------------------------------------------------------------- #
def build_canonical_volume_and_surfaces(level, vol, idx2curie_at_level,
                                        canonical_of_curie, voxel_mm):
    """Relabel ``vol`` at this level keeping only canonical-at-level regions.

    Returns ``(labeled_vol, code2curie, surface_pts_mm_by_curie)``. Voxels of
    regions whose canonical home is a coarser level become 0 (background) at
    this level, which is exactly what suppresses fold-through of e.g. HY into
    the structure table.
    """
    from scipy import ndimage

    idx2c = {pi: c for pi, c in idx2curie_at_level.items()
             if canonical_of_curie.get(c) == level}
    if not idx2c:
        return np.zeros_like(vol), {}, {}
    curies = sorted(set(idx2c.values()))
    c2code = {c: i + 1 for i, c in enumerate(curies)}
    code2c = {i + 1: c for i, c in enumerate(curies)}
    max_pi = int(vol.max())
    remap = np.zeros(max_pi + 1, dtype=np.int32)
    for pi, c in idx2c.items():
        if 0 < pi <= max_pi:
            remap[pi] = c2code[c]
    labeled = remap[vol]

    slices = ndimage.find_objects(labeled, max_label=len(curies))
    surfaces: dict[str, np.ndarray] = {}
    for code, cur in code2c.items():
        sl = slices[code - 1]
        if sl is None:
            continue
        # pad by 1 so erosion sees the true border
        crop = tuple(slice(max(0, s.start - 1), s.stop + 1) for s in sl)
        mask = labeled[crop] == code
        boundary = mask & ~ndimage.binary_erosion(mask)
        if not boundary.any():
            boundary = mask
        idx = np.argwhere(boundary) + np.array([crop[ax].start for ax in range(3)])
        surfaces[cur] = idx.astype(np.float32) * voxel_mm
    return labeled, code2c, surfaces


# --------------------------------------------------------------------------- #
# Template emission                                                           #
# --------------------------------------------------------------------------- #
def emit_template(df: pd.DataFrame, out_path: Path):
    """ROBOT template: type -> PCL:0010063 "has soma location" with cell_count
    / cell_ratio / in_or_near_100 axiom annotations plus per-edge
    dcterms:source DOI. The in_or_near_100 column (n2o:countInOrNear100um)
    carries the boundary-band count alongside the strict interior count.
    """
    header = ["ID", "Type", "PCL:0010063",
              "cell_count", "cell_ratio", "in_or_near_100", "source"]
    types = ["ID", "TYPE", "AI PCL:0010063",
             ">AT PCL:0010060^^xsd:integer",
             ">AT PCL:0010065^^xsd:float",
             ">AT n2o:countInOrNear100um^^xsd:integer",
             ">AI dcterms:source"]
    lines = ["\t".join(header), "\t".join(types)]
    for _, r in df.iterrows():
        lines.append("\t".join([
            r["type_curie"], "owl:NamedIndividual", r["near_region"],
            str(int(r["n_in_X"])),
            f"{float(r['frac_in_X']):.6f}",
            str(int(r["n_in_or_near_100"])),
            str(r.get("source", "") or ""),
        ]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, choices=["yao", "zhuang"],
                    help="Single dataset to process. The matching DOI is "
                         "attached as dcterms:source on every emitted edge.")
    ap.add_argument("--annotation", required=True, type=Path)
    ap.add_argument("--membership", required=True, type=Path)
    ap.add_argument("--mba-map", required=True, type=Path)
    ap.add_argument("--cell-set-map", required=True, type=Path,
                    help="reports/cell_set_map.csv ((labelset,label) -> CURIE)")
    ap.add_argument("--yao-csv", type=Path,
                    help="cell_metadata_with_parcellation_annotation.csv "
                         "(required for --dataset yao)")
    ap.add_argument("--aba-cache", type=Path,
                    help="aba_cache dir for Zhuang (required for --dataset zhuang)")
    ap.add_argument("--reports-dir", required=True, type=Path)
    ap.add_argument("--templates-dir", required=True, type=Path)
    ap.add_argument("--zhuang-datasets", nargs="+",
                    default=["Zhuang-ABCA-1", "Zhuang-ABCA-2",
                             "Zhuang-ABCA-3", "Zhuang-ABCA-4"])
    ap.add_argument("--zhuang-cluster-release", default="20231215")
    ap.add_argument("--zhuang-ccf-release", default="20230830")
    args = ap.parse_args()

    import nibabel as nib
    from scipy.spatial import cKDTree

    # --- canonical level per region CURIE ---
    canonical_acro = load_canonical_levels(args.membership)
    mba = pd.read_csv(args.mba_map)
    curie_of = dict(zip(mba["symbol"], mba["curie"]))
    canonical_of_curie = {curie_of[a]: lvl for a, lvl in canonical_acro.items()
                          if a in curie_of}

    # --- bridge per level (parcellation_index -> CURIE at level) ---
    idx2curie_all = build_index_to_curie(args.membership, args.mba_map)

    # --- volume ---
    print(f"Loading annotation volume: {args.annotation}")
    img = nib.load(str(args.annotation))
    vol = np.asarray(img.dataobj).astype(np.int32)
    zooms = np.asarray(img.header.get_zooms()[:3], dtype=float)
    voxel_mm = float(zooms.mean())
    print(f"  shape {vol.shape}, voxel {voxel_mm*1000:.1f} um")

    # --- load cells for the selected dataset ---
    print(f"Loading cells (dataset={args.dataset})...")
    if args.dataset == "yao":
        if not (args.yao_csv and args.yao_csv.exists()):
            ap.error("--yao-csv is required (and must exist) for --dataset yao")
        cells = load_yao_cells(args.yao_csv)
        print(f"  yao: {len(cells):,} cells")
    else:
        if not args.aba_cache:
            ap.error("--aba-cache is required for --dataset zhuang")
        cells = load_zhuang_cells(args.aba_cache, args.zhuang_datasets,
                                  args.zhuang_cluster_release, args.zhuang_ccf_release)
        if not len(cells):
            ap.error("no Zhuang cells loaded from --aba-cache")
    source_doi = DATASET_DOI[args.dataset]
    # Cells with parcellation_index == 0 are inside the CCF coordinate frame but
    # outside any parcellated region (~1.8% of WMB MERFISH cells, mostly at the
    # brain boundary). Keep them: their `region_<lvl>` becomes NaN so they never
    # match `in_B` (n_in_X stays 0) but they still contribute to n_total and to
    # n_in_or_near_100 when they fall within 100 um of a region's surface.
    for lvl in REGION_LEVELS:
        cells[f"region_{lvl}"] = cells["parcellation_index"].map(idx2curie_all[lvl])
    cells = cells.dropna(subset=["x", "y", "z"]).reset_index(drop=True)
    n_outside = int((cells["parcellation_index"] == 0).sum())
    print(f"  pooled & coord-valid: {len(cells):,} cells "
          f"({n_outside:,} of these have no CCF region assignment)")
    cells_xyz = cells[["x", "y", "z"]].to_numpy(dtype=np.float32)

    # --- alignment self-check at substructure level (clearest signal) ---
    sub_lvl = "substructure"
    sub_idx2 = idx2curie_all[sub_lvl]
    ncodes_check = 0
    code2c_check: dict[int, str] = {}
    # Build a quick remap for self-check
    if sub_idx2:
        curies = sorted(set(sub_idx2.values()))
        c2code = {c: i + 1 for i, c in enumerate(curies)}
        code2c_check = {i + 1: c for i, c in enumerate(curies)}
        ncodes_check = len(curies)
        max_pi = int(vol.max())
        remap = np.zeros(max_pi + 1, dtype=np.int32)
        for pi, c in sub_idx2.items():
            if 0 < pi <= max_pi:
                remap[pi] = c2code[c]
        labeled_check = remap[vol]
        chk = cells.sample(min(20000, len(cells)), random_state=0)
        vijk = np.rint(chk[["x", "y", "z"]].to_numpy() / voxel_mm).astype(int)
        inb = np.all((vijk >= 0) & (vijk < np.array(labeled_check.shape)), axis=1)
        sampled = np.zeros(len(chk), dtype=np.int32)
        sampled[inb] = labeled_check[vijk[inb, 0], vijk[inb, 1], vijk[inb, 2]]
        sampled_curie = pd.Series(sampled).map(code2c_check).to_numpy()
        match = (sampled_curie == chk[f"region_{sub_lvl}"].to_numpy()).mean()
        print(f"Alignment self-check ({sub_lvl}): "
              f"{match*100:.1f}% of {len(chk)} sampled cells land in their assigned region "
              f"(expect high; low => axis/affine mismatch)")
        del labeled_check, remap

    # --- type CURIE lookup ((labelset,label) -> CURIE), WMB ---
    csmap = pd.read_csv(args.cell_set_map)
    csmap = csmap[csmap["dataset"] == "Whole Mouse Brain Taxonomy"]
    type_curie = {(r["labelset"], r["label"]): r["curie"]
                  for _, r in csmap.iterrows()
                  if pd.notna(r["label"]) and pd.notna(r["curie"])}

    # --- global cells KD-tree (queried with each region's surface points) ---
    # Building once and querying with surface points is cheaper than building a
    # tree per region: surface counts (hundreds to thousands per region) are
    # smaller than the candidate-cell set at coarse levels (millions).
    print("Building global cells KD-tree...")
    cells_tree = cKDTree(cells_xyz)

    # n_total per type per taxonomy level
    n_total_per_tax = {tax: cells.groupby(tax).size().to_dict()
                       for tax in TAXONOMY_LEVELS}

    # region_to_idx per level (cells whose resident region at level L is r)
    region_to_idx_per_level = {
        lvl: {r: np.asarray(g.index, dtype=np.int64)
              for r, g in cells.groupby(f"region_{lvl}", sort=False)}
        for lvl in REGION_LEVELS
    }

    band_mm = PROXIMITY_BAND_UM / 1000.0

    # --- accumulator: per-taxonomy-level list of edge rows ---
    rows_per_tax: dict[str, list] = {tax: [] for tax in TAXONOMY_LEVELS}

    for lvl in REGION_LEVELS:
        print(f"\nProcessing region level: {lvl}")
        _labeled, code2c, surfaces = build_canonical_volume_and_surfaces(
            lvl, vol, idx2curie_all[lvl], canonical_of_curie, voxel_mm)
        print(f"  {len(surfaces)} canonical regions")
        region_col = f"region_{lvl}"
        ridx = region_to_idx_per_level[lvl]

        for n, (B, surf_pts) in enumerate(surfaces.items()):
            if n % 50 == 0:
                print(f"    {n}/{len(surfaces)}")
            # cells within 100um of any surface point of B
            ball_idx_lists = cells_tree.query_ball_point(surf_pts, r=band_mm,
                                                         return_sorted=False)
            near_set: set = set()
            for lst in ball_idx_lists:
                near_set.update(lst)
            in_set: set = set(ridx.get(B, np.empty(0, dtype=np.int64)).tolist())
            in_or_near = in_set | near_set
            if not in_or_near:
                continue
            ion_idx = np.fromiter(in_or_near, dtype=np.int64)
            sub = cells.iloc[ion_idx]
            in_B = (sub[region_col].to_numpy() == B).astype(np.int64)

            # group by taxonomy
            for tax in TAXONOMY_LEVELS:
                cutoff = DEFAULT_GRADED_CUTOFFS[tax]
                labels = sub[tax].to_numpy()
                df = pd.DataFrame({"label": labels, "in_B": in_B}) \
                    .dropna(subset=["label"]) \
                    .groupby("label", sort=False, observed=True) \
                    .agg(n_in_X=("in_B", "sum"),
                         n_in_or_near=("in_B", "count")) \
                    .reset_index()
                tot = n_total_per_tax[tax]
                # Graded-cutoff filter: keep row if the fractional share of
                # this type's cells inside or within 100um of B clears the
                # per-taxonomy floor.
                df["n_total_lookup"] = df["label"].map(tot).fillna(0).astype(int)
                with np.errstate(divide="ignore", invalid="ignore"):
                    frac = np.where(df["n_total_lookup"] > 0,
                                    df["n_in_or_near"] / df["n_total_lookup"],
                                    0.0)
                df = df[frac >= cutoff]
                if df.empty:
                    continue
                for _, r in df.iterrows():
                    label = r["label"]
                    curie = type_curie.get((tax, label))
                    if curie is None:
                        continue
                    n_total = tot.get(label, 0)
                    if n_total == 0:
                        continue
                    n_in_X = int(r["n_in_X"])
                    n_in_or_near = int(r["n_in_or_near"])
                    rows_per_tax[tax].append({
                        "type_curie": curie,
                        "type_label": label,
                        "near_region": B,
                        "region_level": lvl,
                        "n_total": int(n_total),
                        "n_in_X": n_in_X,
                        "n_in_or_near_100": n_in_or_near,
                        "frac_in_X": n_in_X / n_total,
                        "frac_in_or_near_100": n_in_or_near / n_total,
                        "source": source_doi,
                    })

    # --- write per-taxonomy outputs ---
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    args.templates_dir.mkdir(parents=True, exist_ok=True)
    template_suffix = "_zhuang" if args.dataset == "zhuang" else ""
    for tax in TAXONOMY_LEVELS:
        df = pd.DataFrame(rows_per_tax[tax])
        # Stable order helps diffs and review
        if not df.empty:
            df = df.sort_values(["type_label", "region_level", "near_region"])
        df.to_csv(args.reports_dir / f"cell_proximity_{tax}.csv", index=False)
        emit_template(df,
                      args.templates_dir / f"{tax}_location_mappings{template_suffix}.tsv")
        print(f"{tax}: {len(df)} location edges")

    print("\nUnified location templates complete.")


if __name__ == "__main__":
    main()
