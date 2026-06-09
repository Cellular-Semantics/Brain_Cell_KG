#!/usr/bin/env python3
"""Anchor-conditioned spatial co-location score: Purkinje as proof of concept.

For each candidate cell-type, measures how spatially close its cells sit to
anchor (Purkinje) cells, relative to an anchor-defined "universe" of nearby
cells, with a permutation p-value. Also decomposes displacement into
normal-to-PCL-sheet and within-sheet components so we can tell "in the
Purkinje layer" (PLI) from "off the sheet" (MLI/Golgi).

Universe: all non-anchor cells whose 3D nearest-neighbour distance to any
anchor cell is <= R. Defined anchor-conditionally (not via parcellation
labels) so CCF registration noise doesn't bias the background.

Score statistic per candidate c at radius R:

    score_c(R) = exp( mean_log_NN_universe(R) - mean_log_NN_c(R) )

Score > 1 = candidate sits closer to anchor than universe average.

Local sheet decomposition: at each anchor, the PCL normal is the
smallest-eigenvalue eigenvector of the local 3D covariance of the k nearest
anchor cells. For each universe cell, the displacement to its nearest
anchor is split into:
  - normal_um:   |displacement . normal|      off-sheet distance
  - tangent_um:  sqrt(|displacement|^2 - normal^2)   in-sheet distance

Candidate columns are auto-detected per label (subclass / supertype /
cluster), so a single run can mix levels (e.g. compare PLI supertypes
against other subclasses).
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# Yao MERFISH taxonomy columns in coarse->fine order.
TAXONOMY_COLS = ["subclass", "supertype", "cluster"]
DEFAULT_ANCHOR = "313 CBX Purkinje Gaba"  # subclass-level
# Default mixes subclass-level contrasts with the four PLI supertypes.
DEFAULT_CANDIDATES = (
    "309 CB PLI Gly-Gaba,"
    "311 CBX MLI Megf11 Gaba,"
    "312 CBX MLI Cdh22 Gaba,"
    "310 CBX Golgi Gly-Gaba,"
    "1144 CB PLI Gly-Gaba_1,"
    "1145 CB PLI Gly-Gaba_2,"
    "1146 CB PLI Gly-Gaba_3,"
    "1147 CB PLI Gly-Gaba_4"
)
# CCF mm floor for log distance: 1 um. Avoids log(0) on registration ties.
MIN_DISTANCE_MM = 0.001
# Number of nearest-anchor neighbours used to estimate local sheet normals.
# 20 is enough for a stable plane fit even where PCs are sparse along a folium.
SHEET_K = 20


def detect_column(label: str, df: pd.DataFrame) -> str | None:
    """Find which taxonomy column (subclass / supertype / cluster) contains a label."""
    for col in TAXONOMY_COLS:
        if (df[col] == label).any():
            return col
    return None


def load_yao(path: Path, anchor_label: str) -> pd.DataFrame:
    """Load Yao cells with coords, all taxonomy levels, and parcellation."""
    cols = ["x_ccf", "y_ccf", "z_ccf", "parcellation_substructure"] + TAXONOMY_COLS
    df = pd.read_csv(path, usecols=cols, low_memory=False)
    df = df.rename(columns={"x_ccf": "x", "y_ccf": "y", "z_ccf": "z"})
    return df


def compute_sheet_normals(anchor_xyz: np.ndarray, k: int = SHEET_K) -> np.ndarray:
    """Per-anchor unit normal to the local PCL sheet via PCA on k-NN.

    Smallest-eigenvalue eigenvector of the local point covariance is the
    normal to the locally-flat sheet. Sign is arbitrary from PCA alone -
    use orient_normals_by_polarity to fix sign with a reference cell type.
    """
    tree = cKDTree(anchor_xyz)
    _, neigh = tree.query(anchor_xyz, k=k + 1)
    n_anchor = len(anchor_xyz)
    normals = np.empty_like(anchor_xyz)
    for i in range(n_anchor):
        pts = anchor_xyz[neigh[i, 1:]]
        centred = pts - pts.mean(axis=0)
        cov = centred.T @ centred
        eigvals, eigvecs = np.linalg.eigh(cov)
        normals[i] = eigvecs[:, 0]
    return normals


def orient_normals_by_polarity(
    anchor_xyz: np.ndarray,
    normals: np.ndarray,
    polarity_xyz: np.ndarray,
    k: int = 5,
) -> np.ndarray:
    """Flip each anchor normal so it points toward nearby polarity cells.

    Polarity cells (e.g. VLMC for pia) act as a reference for which side
    of the sheet is 'positive'. After orientation, a positive signed
    normal means 'toward polarity reference' and negative means 'away'.

    Uses the *mean* direction to k nearest polarity cells rather than
    just the single nearest, so a wrong-side polarity reference (e.g. an
    adjacent-folium VLMC in a deep cerebellar fold) doesn't dominate.
    """
    tree = cKDTree(polarity_xyz)
    k_use = min(k, len(polarity_xyz))
    _, idx = tree.query(anchor_xyz, k=k_use)
    if k_use == 1:
        idx = idx[:, None]
    # Mean direction from each anchor to its k nearest polarity cells.
    # axis 0: anchor i; axis 1: k; axis 2: xyz
    nearest = polarity_xyz[idx]  # (n_anchor, k, 3)
    direction = nearest.mean(axis=1) - anchor_xyz  # (n_anchor, 3)
    dot = np.einsum("ij,ij->i", normals, direction)
    out = normals.copy()
    flip = dot < 0
    out[flip] = -out[flip]
    return out


def decompose_displacement(
    other_xyz: np.ndarray,
    anchor_xyz: np.ndarray,
    anchor_normals: np.ndarray,
    nn_idx: np.ndarray,
    signed: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Split each other cell's displacement to its nearest anchor into
    (off-sheet, in-sheet) components in mm.

    If signed=False, the normal component is the absolute value
    (interpretation: 'distance off the sheet, ignoring side'). If
    signed=True, the sign of the normal component is retained -
    interpretable as 'toward polarity reference (+) or away (-)' only if
    the anchor normals have been oriented via orient_normals_by_polarity.
    """
    disp = other_xyz - anchor_xyz[nn_idx]
    n_local = anchor_normals[nn_idx]
    n_dot = np.einsum("ij,ij->i", disp, n_local)
    normal_mm = n_dot if signed else np.abs(n_dot)
    total_mm = np.linalg.norm(disp, axis=1)
    # Tangent uses unsigned normal-squared either way: it's the in-plane
    # length, sign of the normal doesn't matter for it.
    tangent_mm = np.sqrt(np.maximum(total_mm**2 - n_dot**2, 0.0))
    return normal_mm, tangent_mm


def per_candidate_rows(
    candidate_spec: list[tuple[str, str]],
    universe_df: pd.DataFrame,
    u_dist_mm: np.ndarray,
    u_normal_mm: np.ndarray,
    u_tangent_mm: np.ndarray,
    radius_mm: float,
    n_permutations: int,
    rng: np.random.Generator,
) -> list[dict]:
    mask = u_dist_mm <= radius_mm
    u_df = universe_df.loc[mask].reset_index(drop=True)
    u_d = u_dist_mm[mask]
    u_norm = u_normal_mm[mask]
    u_tan = u_tangent_mm[mask]
    u_log = np.log(np.maximum(u_d, MIN_DISTANCE_MM))
    universe_mean_log = float(np.mean(u_log))
    n_universe = len(u_log)

    candidate_indices = {}
    for label, col in candidate_spec:
        candidate_indices[label] = np.where(u_df[col].to_numpy() == label)[0]

    observed = {
        label: (float(np.mean(u_log[idx])) if len(idx) > 0 else np.nan)
        for label, idx in candidate_indices.items()
    }

    # Permutation null per candidate: draw N_c indices uniformly without
    # replacement from the universe and recompute the mean-log statistic.
    # Cheaper than permuting the whole universe when most candidates are
    # small fractions of N_universe.
    perm_counts = {label: 0 for label in candidate_indices}
    sizes = {label: len(idx) for label, idx in candidate_indices.items()}
    for label, size in sizes.items():
        if size == 0:
            continue
        for _ in range(n_permutations):
            sample_idx = rng.choice(n_universe, size=size, replace=False)
            shuf_mean = float(np.mean(u_log[sample_idx]))
            if shuf_mean <= observed[label]:
                perm_counts[label] += 1

    rows = []
    for label, col in candidate_spec:
        idx = candidate_indices[label]
        n_c = len(idx)
        if n_c == 0:
            rows.append({
                "candidate": label,
                "level": col,
                "radius_mm": radius_mm,
                "n_universe": n_universe,
                "n_in_universe": 0,
                "median_nn_um": np.nan,
                "mean_log_nn_mm": np.nan,
                "score": np.nan,
                "p_value": np.nan,
                "median_normal_um": np.nan,
                "median_tangent_um": np.nan,
                "top_substructures": "",
            })
            continue
        c_d = u_d[idx]
        c_norm = u_norm[idx]
        c_tan = u_tan[idx]
        top_sub = (u_df.iloc[idx]["parcellation_substructure"]
                   .value_counts().head(3))
        rows.append({
            "candidate": label,
            "level": col,
            "radius_mm": radius_mm,
            "n_universe": n_universe,
            "n_in_universe": n_c,
            "median_nn_um": float(np.median(c_d)) * 1000.0,
            "mean_log_nn_mm": observed[label],
            "score": float(np.exp(universe_mean_log - observed[label])),
            "p_value": (perm_counts[label] + 1) / (n_permutations + 1),
            "median_normal_um": float(np.median(c_norm)) * 1000.0,
            "median_tangent_um": float(np.median(c_tan)) * 1000.0,
            "top_substructures": "; ".join(f"{a}:{c}" for a, c in top_sub.items()),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yao-csv", required=True, type=Path)
    parser.add_argument("--anchor", default=DEFAULT_ANCHOR,
                        help="anchor subclass label (default: Purkinje)")
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES,
                        help="comma-separated candidate labels; column "
                             "(subclass/supertype/cluster) auto-detected per label")
    parser.add_argument("--radii-mm", default="0.1,0.3,1.0",
                        help="comma-separated universe radii in mm")
    parser.add_argument("--n-permutations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    candidate_labels = [s.strip() for s in args.candidates.split(",") if s.strip()]
    radii = sorted(float(r) for r in args.radii_mm.split(","))
    r_max = radii[-1]

    t0 = time.time()
    print(f"Loading Yao cells from {args.yao_csv} ...", flush=True)
    df = load_yao(args.yao_csv, args.anchor)
    print(f"  {len(df):,} cells in {time.time()-t0:.1f}s", flush=True)

    # Resolve anchor & candidate columns.
    anchor_col = detect_column(args.anchor, df)
    if anchor_col is None:
        print(f"ERROR: anchor '{args.anchor}' not found in any taxonomy column",
              file=sys.stderr)
        return 1
    print(f"Anchor '{args.anchor}' found in column '{anchor_col}'")

    candidate_spec: list[tuple[str, str]] = []
    for label in candidate_labels:
        col = detect_column(label, df)
        if col is None:
            print(f"WARNING: candidate '{label}' not found - skipping",
                  file=sys.stderr)
            continue
        candidate_spec.append((label, col))
    if not candidate_spec:
        print("ERROR: no candidates resolved", file=sys.stderr)
        return 1

    # Split anchor / non-anchor BEFORE filtering, so the universe is "all
    # non-anchor cells within R of Purkinje" - a true cerebellar-cortex
    # background, not just the candidate subclasses.
    anchor_mask = df[anchor_col] == args.anchor
    anchor_df = df.loc[anchor_mask].reset_index(drop=True)
    other_df = df.loc[~anchor_mask].reset_index(drop=True)
    print(f"Anchor cells: {len(anchor_df):,}  Other cells: {len(other_df):,}")

    anchor_xyz = anchor_df[["x", "y", "z"]].to_numpy()
    other_xyz = other_df[["x", "y", "z"]].to_numpy()

    print(f"Estimating local PCL sheet normals (k={SHEET_K}) ...", flush=True)
    t = time.time()
    normals = compute_sheet_normals(anchor_xyz, k=SHEET_K)
    print(f"  {time.time()-t:.1f}s")

    print(f"Querying NN distance for {len(other_xyz):,} cells ...", flush=True)
    t = time.time()
    tree = cKDTree(anchor_xyz)
    nn_dist, nn_idx = tree.query(other_xyz, k=1)
    print(f"  {time.time()-t:.1f}s")

    print("Decomposing displacements into sheet-normal / tangent ...", flush=True)
    normal_mm, tangent_mm = decompose_displacement(
        other_xyz, anchor_xyz, normals, nn_idx
    )

    # Pre-filter at r_max to avoid carrying ~3.7M cells through permutation.
    in_max = nn_dist <= r_max
    universe_df = other_df.loc[in_max].reset_index(drop=True)
    u_dist = nn_dist[in_max]
    u_normal = normal_mm[in_max]
    u_tangent = tangent_mm[in_max]
    print(f"Universe at R<={r_max} mm: {len(universe_df):,} cells")

    rng = np.random.default_rng(args.seed)
    all_rows: list[dict] = []
    for r in radii:
        print(f"Scoring at R={r} mm (n_perm={args.n_permutations}) ...", flush=True)
        t = time.time()
        all_rows.extend(per_candidate_rows(
            candidate_spec=candidate_spec,
            universe_df=universe_df,
            u_dist_mm=u_dist,
            u_normal_mm=u_normal,
            u_tangent_mm=u_tangent,
            radius_mm=r,
            n_permutations=args.n_permutations,
            rng=rng,
        ))
        print(f"  {time.time()-t:.1f}s")

    out = pd.DataFrame(all_rows)
    out = out.sort_values(["radius_mm", "score"], ascending=[True, False])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, sep="\t", index=False, float_format="%.4g")
    print(f"Wrote {len(out)} rows to {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
