#!/usr/bin/env python3
"""
Generate taxonomy x brain-region cell-count matrices from the Zhuang lab
ABCA MERFISH datasets (Zhang et al. 2023, doi:10.1038/s41586-023-06808-9).

Output is a sibling directory to the existing Yao matrices (produced by
generate_full_matrices.py) with the same file shape, so it can be fed into
generate_hierarchical_location_templates.py without modification.

Steps:
  1. For each of the four Zhuang-ABCA-N datasets:
     - Download (or reuse cached) cell_metadata_with_cluster_annotation.csv
     - Download (or reuse cached) ccf_coordinates.csv
     - Inner-join on cell_label
     - Drop rows with parcellation_index = 0 (cell coordinate falls outside
       any parcellated region; truly unmappable)
  2. Use the Allen-CCF-2020 parcellation membership table to map every
     parcellation_index to its (division, structure, substructure) acronyms.
  3. Concatenate all four datasets into a single aggregate frame.
  4. Emit one (taxonomy_level x region_level) cross-tab matrix per CSV,
     plus matrix_metadata.json and matrix_summary.csv.

Cache and output paths follow the existing aba_cache convention.
"""

import argparse
import csv
import json
import os
import shutil
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

import certifi
import numpy as np
import pandas as pd

# Build a single SSL context using the certifi CA bundle so downloads work
# on systems without a system-level CA bundle (e.g. fresh python.org Python).
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

S3 = "https://allen-brain-cell-atlas.s3.us-west-2.amazonaws.com"
DATASETS = ["Zhuang-ABCA-1", "Zhuang-ABCA-2", "Zhuang-ABCA-3", "Zhuang-ABCA-4"]
TAXONOMY_LEVELS = ["neurotransmitter", "class", "subclass", "supertype", "cluster"]
REGION_LEVELS = ["division", "structure", "substructure"]
CLUSTER_RELEASE = "20231215"
CCF_RELEASE = "20230830"
PARCELLATION_RELEASE = "20230630"


def download_to_cache(url: str, target: Path) -> Path:
    """Download URL to target path if missing; emit progress."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        size_mb = target.stat().st_size / (1024 * 1024)
        print(f"  cached: {target} ({size_mb:.1f} MB)")
        return target

    print(f"  downloading: {url}")
    print(f"             -> {target}")

    last_pct = -1
    with urllib.request.urlopen(url, context=_SSL_CTX) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        tmp = target.with_suffix(target.suffix + ".part")
        downloaded = 0
        with open(tmp, "wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    if pct != last_pct:
                        last_pct = pct
                        mb = downloaded / (1024 * 1024)
                        tot = total / (1024 * 1024)
                        print(f"\r    {pct}% ({mb:.1f}/{tot:.1f} MB)", end="", flush=True)
        shutil.move(tmp, target)
    print()
    return target


def load_parcellation_lookup(cache_dir: Path) -> dict:
    """parcellation_index -> {division, structure, substructure} acronyms."""
    base = f"{S3}/metadata/Allen-CCF-2020/{PARCELLATION_RELEASE}"
    rel = Path("metadata/Allen-CCF-2020") / PARCELLATION_RELEASE / "views"
    acro_path = cache_dir / rel / "parcellation_to_parcellation_term_membership_acronym.csv"
    download_to_cache(
        f"{base}/views/parcellation_to_parcellation_term_membership_acronym.csv",
        acro_path,
    )

    lookup: dict[int, dict[str, str]] = {}
    with open(acro_path) as f:
        for row in csv.DictReader(f):
            try:
                pi = int(row["parcellation_index"])
            except (KeyError, ValueError):
                continue
            lookup[pi] = {
                "division": row.get("division") or "",
                "structure": row.get("structure") or "",
                "substructure": row.get("substructure") or "",
            }
    return lookup


def load_zhuang_dataset(dataset: str, cache_dir: Path) -> pd.DataFrame:
    """Return per-cell taxonomy + parcellation_index for one Zhuang dataset."""
    cluster_url = f"{S3}/metadata/{dataset}/{CLUSTER_RELEASE}/views/cell_metadata_with_cluster_annotation.csv"
    cluster_path = (
        cache_dir / "metadata" / dataset / CLUSTER_RELEASE / "views"
        / "cell_metadata_with_cluster_annotation.csv"
    )
    download_to_cache(cluster_url, cluster_path)

    ccf_url = f"{S3}/metadata/{dataset}-CCF/{CCF_RELEASE}/ccf_coordinates.csv"
    ccf_path = (
        cache_dir / "metadata" / f"{dataset}-CCF" / CCF_RELEASE / "ccf_coordinates.csv"
    )
    download_to_cache(ccf_url, ccf_path)

    print(f"  reading cluster annotations...")
    cluster_cols = ["cell_label"] + TAXONOMY_LEVELS
    cluster_df = pd.read_csv(cluster_path, usecols=cluster_cols, low_memory=False)
    print(f"    {len(cluster_df):,} rows")

    print(f"  reading CCF coordinates...")
    ccf_df = pd.read_csv(
        ccf_path, usecols=["cell_label", "parcellation_index"], low_memory=False
    )
    print(f"    {len(ccf_df):,} rows")

    merged = cluster_df.merge(ccf_df, on="cell_label", how="inner")
    print(f"  joined: {len(merged):,} cells")

    before = len(merged)
    merged = merged[merged["parcellation_index"] != 0].reset_index(drop=True)
    print(f"  after drop parcellation_index=0: {len(merged):,} (dropped {before - len(merged):,})")

    return merged


def build_matrices(
    merged_df: pd.DataFrame,
    parcellation: dict,
    output_dir: Path,
) -> list[dict]:
    """Generate one cross-tab CSV per (taxonomy_level, region_level)."""
    region_series = {}
    for reg_level in REGION_LEVELS:
        region_series[reg_level] = (
            merged_df["parcellation_index"]
            .map(lambda pi, lvl=reg_level: parcellation.get(pi, {}).get(lvl, ""))
        )

    metadata = []
    for tax_level in TAXONOMY_LEVELS:
        if tax_level not in merged_df.columns:
            print(f"  skipping {tax_level} (column missing)")
            continue
        tax_col = merged_df[tax_level]
        for reg_level in REGION_LEVELS:
            reg_col = region_series[reg_level]
            mask = tax_col.notna() & (reg_col != "")
            crosstab = pd.crosstab(tax_col[mask], reg_col[mask])

            filename = f"{tax_level}_by_{reg_level}.csv"
            filepath = output_dir / filename
            crosstab.to_csv(filepath)

            non_zero = int(np.sum(crosstab.values > 0))
            shape = list(crosstab.shape)
            metadata.append({
                "filename": filename,
                "taxonomy_level": tax_level,
                "region_level": reg_level,
                "matrix_shape": shape,
                "total_cells": int(crosstab.sum().sum()),
                "non_zero_combinations": non_zero,
                "file_size_mb": round(os.path.getsize(filepath) / (1024 * 1024), 2),
                "sparsity": round(1 - non_zero / max(shape[0] * shape[1], 1), 3),
            })
            print(f"    {filename}: {shape[0]} x {shape[1]}, {metadata[-1]['total_cells']:,} cells")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir", default="src/scripts/cell_counts/resources/aba_cache",
        help="Directory for downloaded source CSVs",
    )
    parser.add_argument(
        "--output-dir",
        default="src/scripts/cell_counts/reports/zhuang_taxonomy_by_region_matrices",
        help="Directory for matrix outputs",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Loading parcellation lookup ===")
    parcellation = load_parcellation_lookup(cache_dir)
    print(f"  {len(parcellation):,} parcellation indices")

    per_dataset = []
    for dataset in DATASETS:
        print(f"\n=== {dataset} ===")
        df = load_zhuang_dataset(dataset, cache_dir)
        df["source_dataset"] = dataset
        per_dataset.append(df)

    merged = pd.concat(per_dataset, ignore_index=True)
    print(f"\n=== Aggregate ===")
    print(f"  {len(merged):,} cells across {len(DATASETS)} datasets")

    print(f"\n=== Generating matrices in {output_dir} ===")
    metadata = build_matrices(merged, parcellation, output_dir)

    with open(output_dir / "matrix_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    pd.DataFrame(metadata).to_csv(output_dir / "matrix_summary.csv", index=False)

    readme = output_dir / "README.md"
    with open(readme, "w") as f:
        f.write(
            "# Zhuang Taxonomy x Brain Region Cross-Tabulation Matrices\n\n"
            "Cell counts from the Zhuang lab ABCA MERFISH datasets "
            "(Zhang et al. 2023, doi:10.1038/s41586-023-06808-9), aggregated "
            f"across {', '.join(DATASETS)}.\n\n"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Total cells: {len(merged):,} (after dropping parcellation_index=0)\n\n"
            "Each CSV is a cross-tabulation matrix (taxonomy node x brain region "
            "acronym) at one (taxonomy_level x region_level) combination.\n"
        )
    print(f"\nDone. Output: {output_dir}")


if __name__ == "__main__":
    main()
