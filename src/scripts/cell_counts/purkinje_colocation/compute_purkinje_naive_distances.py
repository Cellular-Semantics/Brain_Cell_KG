#!/usr/bin/env python3
"""Naive two-anchor co-location: distance to nearest Purkinje + nearest VLMC.

Parallel experiment to the sheet-frame anchor method
(compute_purkinje_colocation.py). The simpler approach: for each non-anchor
cell, return two scalars

  d_PC   = 3D distance to the nearest Purkinje cell  (mm)
  d_VLMC = 3D distance to the nearest VLMC (pia) cell (mm)

No PCA on Purkinje neighbourhoods, no polarity orientation, no sheet
normal. Each per-cell measurement is one cKDTree query.

In the (d_VLMC, d_PC) plane a cell's anatomical layer reads as a
position:

  pial-side molecular layer  -> small  d_VLMC, moderate d_PC
  PCL                        -> moderate d_VLMC, ~0      d_PC
  granular layer             -> large  d_VLMC, moderate d_PC

A perfect perpendicular section of cerebellar cortex traces out a
V-shape: from (0, ~175) at the pia, down to (~175, 0) at the PCL,
back up to (~325, ~150) at the white matter.

Writes:
  - per-cell CSV with d_PC, d_VLMC, taxonomy labels
  - per-type summary TSV with median d_PC, median d_VLMC, cell counts
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

TAXONOMY_COLS = ["subclass", "supertype", "cluster"]
DEFAULT_ANCHOR = "313 CBX Purkinje Gaba"
DEFAULT_POLARITY = "330 VLMC NN"
DEFAULT_PANELS = (
    # PLI variants (expected in/near PCL)
    "309 CB PLI Gly-Gaba,"
    "1144 CB PLI Gly-Gaba_1,"
    "1145 CB PLI Gly-Gaba_2,"
    "1146 CB PLI Gly-Gaba_3,"
    "1147 CB PLI Gly-Gaba_4,"
    # Molecular layer (expected pial side)
    "311 CBX MLI Megf11 Gaba,"
    "312 CBX MLI Cdh22 Gaba,"
    # Granular layer (expected WM side)
    "310 CBX Golgi Gly-Gaba,"
    "314 CB Granule Glut,"
    "315 DCO UBC Glut"
)


def detect_column(label: str, df: pd.DataFrame) -> str | None:
    for col in TAXONOMY_COLS:
        if (df[col] == label).any():
            return col
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yao-csv", required=True, type=Path)
    parser.add_argument("--anchor", default=DEFAULT_ANCHOR,
                        help="cell type whose distance becomes d_PC")
    parser.add_argument("--pia-anchor", default=DEFAULT_POLARITY,
                        help="cell type whose distance becomes d_VLMC")
    parser.add_argument("--panels", default=DEFAULT_PANELS,
                        help="comma-separated cell-type labels to summarise")
    parser.add_argument("--universe-radius-mm", type=float, default=1.0,
                        help="restrict to cells within this radius of an anchor")
    parser.add_argument("--out-cells", required=True, type=Path,
                        help="per-cell CSV (xyz + taxonomy + d_PC + d_VLMC)")
    parser.add_argument("--out-summary", required=True, type=Path,
                        help="per-type summary TSV")
    args = parser.parse_args()

    panel_labels = [s.strip() for s in args.panels.split(",") if s.strip()]

    print(f"Loading Yao cells from {args.yao_csv} ...", flush=True)
    cols = (["x_ccf", "y_ccf", "z_ccf", "parcellation_substructure"]
            + TAXONOMY_COLS)
    df_full = pd.read_csv(args.yao_csv, usecols=cols, low_memory=False)
    df_full = df_full.rename(columns={"x_ccf": "x", "y_ccf": "y", "z_ccf": "z"})
    print(f"  {len(df_full):,} total cells")

    # Identify anchor + pia cell positions.
    anchor_col = detect_column(args.anchor, df_full)
    pia_col = detect_column(args.pia_anchor, df_full)
    if anchor_col is None or pia_col is None:
        raise SystemExit(f"anchor or pia label not found")
    anchor_xyz = df_full.loc[df_full[anchor_col] == args.anchor,
                             ["x", "y", "z"]].to_numpy()
    pia_xyz = df_full.loc[df_full[pia_col] == args.pia_anchor,
                          ["x", "y", "z"]].to_numpy()
    print(f"  anchor '{args.anchor}': {len(anchor_xyz):,} cells")
    print(f"  pia    '{args.pia_anchor}': {len(pia_xyz):,} cells")

    # Restrict to candidate cells in panels.
    panel_cols = {}
    for label in panel_labels:
        col = detect_column(label, df_full)
        if col is None:
            print(f"WARNING: panel '{label}' not found - skipping")
            continue
        panel_cols[label] = col
    panel_mask = np.zeros(len(df_full), dtype=bool)
    for label, col in panel_cols.items():
        panel_mask |= (df_full[col] == label).to_numpy()
    df = df_full.loc[panel_mask].reset_index(drop=True)
    print(f"  candidate cells across panel labels: {len(df):,}")

    # Compute d_PC and d_VLMC for every candidate cell.
    t = time.time()
    print("Building KD-trees and querying nearest distances ...", flush=True)
    tree_pc = cKDTree(anchor_xyz)
    tree_pia = cKDTree(pia_xyz)
    candidate_xyz = df[["x", "y", "z"]].to_numpy()
    d_pc, _ = tree_pc.query(candidate_xyz, k=1)
    d_pia, _ = tree_pia.query(candidate_xyz, k=1)
    print(f"  {time.time()-t:.1f}s")

    df["d_PC_um"] = d_pc * 1000.0
    df["d_VLMC_um"] = d_pia * 1000.0

    # Restrict to universe (within R mm of nearest Purkinje).
    in_universe = d_pc <= args.universe_radius_mm
    df = df.loc[in_universe].reset_index(drop=True)
    print(f"  universe (d_PC <= {args.universe_radius_mm} mm): "
          f"{len(df):,} cells")

    # Write per-cell CSV.
    args.out_cells.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_cells, index=False, float_format="%.4f")
    print(f"Wrote per-cell CSV {args.out_cells}")

    # Per-type summary TSV.
    rows = []
    for label, col in panel_cols.items():
        mask = (df[col] == label).to_numpy()
        n = int(mask.sum())
        if n == 0:
            continue
        rows.append({
            "label": label,
            "level": col,
            "n_in_universe": n,
            "median_d_PC_um": float(np.median(df.loc[mask, "d_PC_um"])),
            "median_d_VLMC_um": float(np.median(df.loc[mask, "d_VLMC_um"])),
            "mean_d_PC_um": float(np.mean(df.loc[mask, "d_PC_um"])),
            "mean_d_VLMC_um": float(np.mean(df.loc[mask, "d_VLMC_um"])),
        })
    summary = (pd.DataFrame(rows)
               .sort_values("median_d_PC_um")
               .reset_index(drop=True))
    args.out_summary.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out_summary, sep="\t", index=False, float_format="%.1f")
    print(f"Wrote per-type summary {args.out_summary}")
    print()
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
