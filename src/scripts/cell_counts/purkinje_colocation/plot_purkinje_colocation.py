#!/usr/bin/env python3
"""Visualise the Purkinje anchor-based co-location analysis.

For each non-Purkinje cell, we already compute:
  - NN distance to the closest Purkinje cell (3D Euclidean, mm)
  - the component of that displacement perpendicular to the local PCL
    sheet ('normal', off-sheet distance, mm)
  - the component within the local PCL sheet ('tangent', lateral
    distance from the nearest Purkinje, mm)

This script re-uses the geometry functions from
compute_purkinje_colocation.py to derive these per-cell quantities, then
makes a panel-grid figure in (tangent, normal) space with one panel per
candidate cell type. Cells of the named type are highlighted in red over
a faint grey background of every candidate cell in the dataset.

Reading the figure:
  - cells at the ORIGIN (0, 0) are sitting essentially on top of a
    Purkinje cell -> in the PCL
  - cells along the X axis (low normal, high tangent) are NEAR the PCL
    but offset laterally - within the sheet
  - cells along the Y axis (high normal) are OFF the sheet
    (molecular layer or granular layer; unsigned, so both directions
    collapse to positive Y)
"""

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# Import geometry from the analysis script so the visualisation matches
# whatever the score uses.
import sys
sys.path.insert(0, str(Path(__file__).parent))
from compute_purkinje_colocation import (  # noqa: E402
    SHEET_K, compute_sheet_normals, decompose_displacement,
    orient_normals_by_polarity,
)

DEFAULT_ANCHOR = "313 CBX Purkinje Gaba"
DEFAULT_POLARITY = "330 VLMC NN"  # pia cells; signed normal becomes (+) = pial side
DEFAULT_PANELS = (
    # PLI variants (expected on the sheet)
    "309 CB PLI Gly-Gaba,"
    "1144 CB PLI Gly-Gaba_1,"
    "1145 CB PLI Gly-Gaba_2,"
    "1146 CB PLI Gly-Gaba_3,"
    "1147 CB PLI Gly-Gaba_4,"
    # Molecular layer (expected on the pial side, signed normal > 0)
    "311 CBX MLI Megf11 Gaba,"
    "312 CBX MLI Cdh22 Gaba,"
    # Granular layer (expected on the WM side, signed normal < 0)
    "310 CBX Golgi Gly-Gaba,"
    "314 CB Granule Glut,"
    "315 DCO UBC Glut"
)
TAXONOMY_COLS = ["subclass", "supertype", "cluster"]


def detect_column(label: str, df: pd.DataFrame) -> str | None:
    for col in TAXONOMY_COLS:
        if (df[col] == label).any():
            return col
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yao-csv", required=True, type=Path)
    parser.add_argument("--anchor", default=DEFAULT_ANCHOR,
                        help="anchor cell-type label (subclass)")
    parser.add_argument("--polarity-anchor", default=DEFAULT_POLARITY,
                        help="cell type used to orient the PCL sheet normal; "
                             "after orientation, positive signed normal = "
                             "toward this anchor (default: VLMC = pia). "
                             "Pass empty string to disable and use unsigned.")
    parser.add_argument("--panels", default=DEFAULT_PANELS,
                        help="comma-separated cell-type labels, one panel each")
    parser.add_argument("--universe-radius-mm", type=float, default=1.0,
                        help="only show cells within this distance of any anchor")
    parser.add_argument("--n-cols", type=int, default=4)
    parser.add_argument("--max-tangent-um", type=float, default=300.0,
                        help="x-axis clip for legibility")
    parser.add_argument("--max-normal-um", type=float, default=250.0,
                        help="y-axis range (used as +/- when signed)")
    parser.add_argument("--bg-sample", type=int, default=3000,
                        help="random sample size for grey background")
    parser.add_argument("--highlight-sample", type=int, default=2000,
                        help="max red dots per panel; medians always use ALL "
                             "cells of the type, this is purely visual")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    panel_labels = [s.strip() for s in args.panels.split(",") if s.strip()]
    polarity_label = args.polarity_anchor.strip() or None
    use_signed = polarity_label is not None

    # Load all relevant cells in one pass (anchor + panel labels + polarity).
    print(f"Loading Yao cells from {args.yao_csv} ...", flush=True)
    cols = ["x_ccf", "y_ccf", "z_ccf"] + TAXONOMY_COLS
    df_full = pd.read_csv(args.yao_csv, usecols=cols, low_memory=False)
    df_full = df_full.rename(columns={"x_ccf": "x", "y_ccf": "y", "z_ccf": "z"})

    # Resolve anchor & panel columns.
    anchor_col = detect_column(args.anchor, df_full)
    if anchor_col is None:
        raise SystemExit(f"anchor '{args.anchor}' not found")
    panel_cols = {}
    for label in panel_labels:
        col = detect_column(label, df_full)
        if col is None:
            print(f"WARNING: panel '{label}' not found - skipping")
            continue
        panel_cols[label] = col

    polarity_col = None
    polarity_xyz = None
    if polarity_label:
        polarity_col = detect_column(polarity_label, df_full)
        if polarity_col is None:
            print(f"WARNING: polarity anchor '{polarity_label}' not found - "
                  f"falling back to unsigned normal")
            use_signed = False
        else:
            polarity_xyz = (df_full.loc[df_full[polarity_col] == polarity_label,
                                        ["x", "y", "z"]].to_numpy())
            print(f"  polarity anchor '{polarity_label}': "
                  f"{len(polarity_xyz):,} cells - normals will be SIGNED "
                  f"(+ = toward polarity)")

    # Build a single mask of "kept" cells: anchor + any panel label match.
    anchor_mask = df_full[anchor_col] == args.anchor
    panel_mask = np.zeros(len(df_full), dtype=bool)
    for label, col in panel_cols.items():
        panel_mask |= (df_full[col] == label).to_numpy()
    df = df_full.loc[anchor_mask | panel_mask].reset_index(drop=True)
    print(f"  kept {len(df):,} cells (anchor + panel labels)")

    anchor_df = df[df[anchor_col] == args.anchor].reset_index(drop=True)
    other_df = df[df[anchor_col] != args.anchor].reset_index(drop=True)
    print(f"  anchor={len(anchor_df):,}  others={len(other_df):,}")

    anchor_xyz = anchor_df[["x", "y", "z"]].to_numpy()
    other_xyz = other_df[["x", "y", "z"]].to_numpy()

    print(f"Computing local PCL normals (k={SHEET_K}) ...", flush=True)
    normals = compute_sheet_normals(anchor_xyz, k=SHEET_K)

    if use_signed and polarity_xyz is not None:
        print(f"Orienting normals toward '{polarity_label}' ...", flush=True)
        normals = orient_normals_by_polarity(anchor_xyz, normals, polarity_xyz)

    print("Querying NN distance + decomposing displacements ...", flush=True)
    tree = cKDTree(anchor_xyz)
    nn_dist, nn_idx = tree.query(other_xyz, k=1)
    normal_mm, tangent_mm = decompose_displacement(
        other_xyz, anchor_xyz, normals, nn_idx, signed=use_signed
    )

    # Restrict universe and convert to micrometres for plotting.
    in_universe = nn_dist <= args.universe_radius_mm
    other_df = other_df.loc[in_universe].reset_index(drop=True)
    nn_dist = nn_dist[in_universe]
    normal_um = normal_mm[in_universe] * 1000.0
    tangent_um = tangent_mm[in_universe] * 1000.0
    print(f"Universe (NN <= {args.universe_radius_mm} mm): "
          f"{len(other_df):,} cells")

    # Per-panel highlight masks. A cell counts if its label in the relevant
    # column matches the panel label.
    panel_masks = {}
    for label, col in panel_cols.items():
        panel_masks[label] = (other_df[col] == label).to_numpy()

    # The background is a uniform random sample so it doesn't get dominated
    # by whichever candidate type happens to be most populous (MLI Megf11
    # in this dataset; 76k of 99k universe cells).
    rng = np.random.default_rng(args.seed)
    n_universe = len(tangent_um)
    bg_idx = rng.choice(n_universe,
                        size=min(args.bg_sample, n_universe),
                        replace=False)
    bg_x = tangent_um[bg_idx]
    bg_y = normal_um[bg_idx]

    # Layout: one panel per type, plus a final overlay panel for direct
    # comparison of medians across all types.
    n_panels = len(panel_labels) + 1  # +1 for the overlay panel
    n_cols = args.n_cols
    n_rows = math.ceil(n_panels / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(3.4 * n_cols, 3.4 * n_rows),
                             squeeze=False, sharex=True, sharey=True)

    for i, label in enumerate(panel_labels):
        ax = axes[i // n_cols][i % n_cols]
        if label not in panel_masks:
            ax.set_visible(False)
            continue
        mask = panel_masks[label]
        n_cells = int(mask.sum())

        ax.scatter(bg_x, bg_y, s=3, c="#cccccc", alpha=0.3, linewidths=0)
        # Cap red dots so density remains visible in large populations.
        hl_t = tangent_um[mask]
        hl_n = normal_um[mask]
        if len(hl_t) > args.highlight_sample:
            sub = rng.choice(len(hl_t), size=args.highlight_sample, replace=False)
            hl_t, hl_n = hl_t[sub], hl_n[sub]
        ax.scatter(hl_t, hl_n, s=10, c="#d62728", alpha=0.5, linewidths=0)

        # Headline statistics for the highlighted type. We report MEAN for
        # the normal axis because, with a signed polarity, the median is
        # dominated by the (large, near-zero) PCL-adjacent population and
        # hides the layer-side asymmetry that the mean exposes. Tangent
        # uses median (robust, no sign issue).
        if n_cells > 0:
            med_t = float(np.median(tangent_um[mask]))
            mean_n = float(np.mean(normal_um[mask]))
            med_n = float(np.median(normal_um[mask]))
            ax.axhline(mean_n, color="#7f0000", linestyle="-", linewidth=1.2,
                       alpha=0.8)
            ax.axvline(med_t, color="#7f0000", linestyle=":", linewidth=1.0,
                       alpha=0.7)
            if use_signed:
                pos_pct = 100 * float(np.mean(normal_um[mask] > 0))
                stat = (f"med_tan={med_t:.0f} | mean_nor={mean_n:+.0f}\n"
                        f"med_nor={med_n:+.0f} | {pos_pct:.0f}% pial side")
            else:
                stat = (f"med_tan={med_t:.0f} um\n"
                        f"mean_nor={mean_n:.0f} um")
        else:
            stat = "no cells in universe"
        ax.set_title(f"{label}\n(n={n_cells})  {stat}",
                     fontsize=8.5)

        # Origin marker (where a 'perfect Purkinje layer' cell sits).
        ax.scatter([0], [0], marker="x", s=70, c="black", linewidths=2,
                   zorder=10)
        ax.set_xlim(0, args.max_tangent_um)
        if use_signed:
            ax.set_ylim(-args.max_normal_um, args.max_normal_um)
            ax.axhline(0, color="black", linewidth=0.6, alpha=0.6)
        else:
            ax.set_ylim(0, args.max_normal_um)
        ax.grid(alpha=0.25)
        if i // n_cols == n_rows - 1:
            ax.set_xlabel("tangent (um)\nlateral distance within PCL sheet")
        if i % n_cols == 0:
            if use_signed:
                ax.set_ylabel("signed normal (um)\n(+) pial side / (-) WM side")
            else:
                ax.set_ylabel("normal (um)\noff-PCL-sheet distance")

    # Overlay panel: medians of every type plotted together, coloured.
    overlay_ax = axes[len(panel_labels) // n_cols][len(panel_labels) % n_cols]
    overlay_ax.scatter(bg_x, bg_y, s=3, c="#cccccc", alpha=0.3, linewidths=0)
    colours = plt.cm.tab10(np.linspace(0, 1, max(len(panel_labels), 10)))
    for i, label in enumerate(panel_labels):
        if label not in panel_masks:
            continue
        mask = panel_masks[label]
        if mask.sum() == 0:
            continue
        med_t = float(np.median(tangent_um[mask]))
        # Mean for normal (sensitive to polarity asymmetry), median for tangent.
        plot_n = (float(np.mean(normal_um[mask])) if use_signed
                  else float(np.median(normal_um[mask])))
        overlay_ax.scatter([med_t], [plot_n], s=120, color=colours[i],
                           edgecolor="black", linewidths=0.8, zorder=10)
        overlay_ax.annotate(label.split(" ", 1)[0],  # short prefix only
                            (med_t, plot_n),
                            xytext=(6, 4), textcoords="offset points",
                            fontsize=7, fontweight="bold",
                            bbox=dict(facecolor="white", edgecolor="none",
                                      alpha=0.85, pad=1))
    overlay_ax.scatter([0], [0], marker="x", s=80, c="black", linewidths=2.5,
                       zorder=11)
    overlay_ax.set_xlim(0, args.max_tangent_um)
    if use_signed:
        overlay_ax.set_ylim(-args.max_normal_um, args.max_normal_um)
        overlay_ax.axhline(0, color="black", linewidth=0.6, alpha=0.6)
    else:
        overlay_ax.set_ylim(0, args.max_normal_um)
    overlay_ax.grid(alpha=0.25)
    overlay_ax.set_title("ALL TYPES: medians overlaid\n(numeric prefix labels each type)",
                         fontsize=8.5, fontweight="bold")
    if len(panel_labels) // n_cols == n_rows - 1:
        overlay_ax.set_xlabel("tangent (um)\nlateral distance within PCL sheet")
    if len(panel_labels) % n_cols == 0:
        overlay_ax.set_ylabel("normal (um)\noff-PCL-sheet distance")

    for j in range(n_panels, n_rows * n_cols):
        axes[j // n_cols][j % n_cols].set_visible(False)

    polarity_msg = (f"signed normal: (+) = pial side, (-) = WM side; "
                    f"polarity ref = '{polarity_label}'") if use_signed else (
        "unsigned normal (no polarity ref)")
    fig.suptitle(
        f"Cell-type position relative to the Purkinje sheet (Yao MERFISH)\n"
        f"red = cells of the named subclass/supertype; grey = random sample "
        f"of universe cells; X = sheet origin (a Purkinje cell)\n"
        f"{polarity_msg}",
        fontsize=10, y=1.00,
    )
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, bbox_inches="tight")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
