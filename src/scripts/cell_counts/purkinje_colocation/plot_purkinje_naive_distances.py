#!/usr/bin/env python3
"""Facet plot of the naive (d_PC, d_VLMC) layer view.

Reads the per-cell CSV from compute_purkinje_naive_distances.py and
produces the same panel-grid layout as plot_purkinje_colocation.py so
the two methods can be compared side-by-side.

Axes:
  x = d_VLMC (distance from nearest pia cell, um) - small = pial side
  y = d_PC   (distance from nearest Purkinje cell, um) - small = at PCL
"""

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


DEFAULT_PANELS = (
    "309 CB PLI Gly-Gaba,"
    "1144 CB PLI Gly-Gaba_1,"
    "1145 CB PLI Gly-Gaba_2,"
    "1146 CB PLI Gly-Gaba_3,"
    "1147 CB PLI Gly-Gaba_4,"
    "311 CBX MLI Megf11 Gaba,"
    "312 CBX MLI Cdh22 Gaba,"
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
    parser.add_argument("--cells-csv", required=True, type=Path,
                        help="output of compute_purkinje_naive_distances.py")
    parser.add_argument("--panels", default=DEFAULT_PANELS)
    parser.add_argument("--pcl-reference-label", default="309 CB PLI Gly-Gaba",
                        help="label whose median (d_VLMC, d_PC) marks the "
                             "PCL reference cross")
    parser.add_argument("--n-cols", type=int, default=4)
    parser.add_argument("--max-d-pc-um", type=float, default=400.0)
    parser.add_argument("--max-d-vlmc-um", type=float, default=400.0)
    parser.add_argument("--bg-sample", type=int, default=4000)
    parser.add_argument("--highlight-sample", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    cells = pd.read_csv(args.cells_csv)
    panel_labels = [s.strip() for s in args.panels.split(",") if s.strip()]
    rng = np.random.default_rng(args.seed)

    panel_cols = {}
    for label in panel_labels:
        col = detect_column(label, cells)
        if col is None:
            print(f"WARNING: panel '{label}' not found in cells - skipping")
            continue
        panel_cols[label] = col

    d_pc = cells["d_PC_um"].to_numpy()
    d_vlmc = cells["d_VLMC_um"].to_numpy()

    # Compute PCL reference position from a chosen PLI label.
    ref_col = detect_column(args.pcl_reference_label, cells)
    if ref_col is not None:
        ref_mask = (cells[ref_col] == args.pcl_reference_label).to_numpy()
        pcl_d_vlmc = float(np.median(d_vlmc[ref_mask]))
        pcl_d_pc = float(np.median(d_pc[ref_mask]))
    else:
        pcl_d_vlmc, pcl_d_pc = np.nan, np.nan

    # Per-panel highlight masks.
    panel_masks = {label: (cells[col] == label).to_numpy()
                   for label, col in panel_cols.items()}

    # Subsampled background.
    n = len(d_pc)
    bg_idx = rng.choice(n, size=min(args.bg_sample, n), replace=False)
    bg_x, bg_y = d_vlmc[bg_idx], d_pc[bg_idx]

    n_panels = len(panel_labels) + 1
    n_cols = args.n_cols
    n_rows = math.ceil(n_panels / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(3.4 * n_cols, 3.4 * n_rows),
                             squeeze=False, sharex=True, sharey=True)

    def draw_pcl_ref(ax):
        if not np.isnan(pcl_d_vlmc):
            ax.scatter([pcl_d_vlmc], [pcl_d_pc], marker="x", s=80,
                       c="black", linewidths=2, zorder=10)
            ax.axvline(pcl_d_vlmc, color="black", linestyle="--",
                       linewidth=0.8, alpha=0.4)
            ax.axhline(pcl_d_pc, color="black", linestyle="--",
                       linewidth=0.8, alpha=0.4)

    for i, label in enumerate(panel_labels):
        ax = axes[i // n_cols][i % n_cols]
        if label not in panel_masks:
            ax.set_visible(False)
            continue
        mask = panel_masks[label]
        n_cells = int(mask.sum())

        ax.scatter(bg_x, bg_y, s=3, c="#cccccc", alpha=0.3, linewidths=0)
        hl_x = d_vlmc[mask]
        hl_y = d_pc[mask]
        if len(hl_x) > args.highlight_sample:
            sub = rng.choice(len(hl_x), size=args.highlight_sample,
                             replace=False)
            hl_x, hl_y = hl_x[sub], hl_y[sub]
        ax.scatter(hl_x, hl_y, s=10, c="#d62728", alpha=0.5, linewidths=0)

        if n_cells > 0:
            med_x = float(np.median(d_vlmc[mask]))
            med_y = float(np.median(d_pc[mask]))
            ax.axhline(med_y, color="#7f0000", linestyle=":", linewidth=1.0,
                       alpha=0.7)
            ax.axvline(med_x, color="#7f0000", linestyle=":", linewidth=1.0,
                       alpha=0.7)
            stat = (f"n={n_cells}\n"
                    f"med d_VLMC={med_x:.0f} | med d_PC={med_y:.0f} um")
        else:
            stat = "no cells in universe"

        draw_pcl_ref(ax)
        ax.set_title(f"{label}\n{stat}", fontsize=8.5)
        ax.set_xlim(0, args.max_d_vlmc_um)
        ax.set_ylim(0, args.max_d_pc_um)
        ax.grid(alpha=0.25)
        if i // n_cols == n_rows - 1:
            ax.set_xlabel("d_VLMC (um)\nsmall = pial side")
        if i % n_cols == 0:
            ax.set_ylabel("d_PC (um)\nsmall = at PCL")

    # Overlay panel.
    overlay_ax = axes[len(panel_labels) // n_cols][len(panel_labels) % n_cols]
    overlay_ax.scatter(bg_x, bg_y, s=3, c="#cccccc", alpha=0.3, linewidths=0)
    colours = plt.cm.tab10(np.linspace(0, 1, max(len(panel_labels), 10)))
    for i, label in enumerate(panel_labels):
        if label not in panel_masks:
            continue
        mask = panel_masks[label]
        if mask.sum() == 0:
            continue
        med_x = float(np.median(d_vlmc[mask]))
        med_y = float(np.median(d_pc[mask]))
        overlay_ax.scatter([med_x], [med_y], s=130, color=colours[i],
                           edgecolor="black", linewidths=0.8, zorder=10)
        overlay_ax.annotate(label.split(" ", 1)[0],
                            (med_x, med_y),
                            xytext=(6, 4), textcoords="offset points",
                            fontsize=7, fontweight="bold",
                            bbox=dict(facecolor="white", edgecolor="none",
                                      alpha=0.85, pad=1))
    draw_pcl_ref(overlay_ax)
    overlay_ax.set_xlim(0, args.max_d_vlmc_um)
    overlay_ax.set_ylim(0, args.max_d_pc_um)
    overlay_ax.grid(alpha=0.25)
    overlay_ax.set_title("ALL TYPES: medians overlaid\n"
                         "(X = PCL reference from PLI-subclass median)",
                         fontsize=8.5, fontweight="bold")
    if len(panel_labels) // n_cols == n_rows - 1:
        overlay_ax.set_xlabel("d_VLMC (um)\nsmall = pial side")
    if len(panel_labels) % n_cols == 0:
        overlay_ax.set_ylabel("d_PC (um)\nsmall = at PCL")

    for j in range(n_panels, n_rows * n_cols):
        axes[j // n_cols][j % n_cols].set_visible(False)

    fig.suptitle(
        "Naive two-anchor co-location: distance to nearest Purkinje vs "
        "distance to nearest VLMC\n"
        "red = cells of named type; grey = random sample of all panel cells; "
        "X = PCL reference (median of PLI subclass)",
        fontsize=10, y=1.00,
    )
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, bbox_inches="tight")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
