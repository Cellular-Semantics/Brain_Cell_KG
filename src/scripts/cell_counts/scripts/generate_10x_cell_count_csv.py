#!/usr/bin/env python3
"""
Generate per-taxonomy-node cell counts from the WMB-10X reference dataset.

Source: Allen Brain Cell Atlas, WMB-10X (combined 10Xv2 + 10Xv3) — the
~4M-cell single-cell RNA-seq reference that defines the WMB taxonomy
(Yao et al. 2023, doi:10.1038/s41586-023-06812-z).

Output is a drop-in for cell_counts_by_taxonomy.csv consumed by
generate_total_cell_count_template.py:
  taxonomy_level, cell_set, cell_count, percentage_of_total

This is intentionally separate from generate_cell_proportion_reports.py
which uses MERFISH-CCF data (needed for spatial / per-region work).
For the total cell counts attached to WMB cell-type individuals, we want
the larger 10x reference, not the spatially-resolved MERFISH subset.
"""

import argparse
import shutil
import ssl
import urllib.request
from pathlib import Path

import certifi
import pandas as pd

URL = ("https://allen-brain-cell-atlas.s3.us-west-2.amazonaws.com/"
       "metadata/WMB-10X/20231215/views/cell_metadata_with_cluster_annotation.csv")
TAXONOMY_LEVELS = ["neurotransmitter", "class", "subclass", "supertype", "cluster"]

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def download_to_cache(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        size_mb = target.stat().st_size / (1024 * 1024)
        print(f"cached: {target} ({size_mb:.1f} MB)")
        return target

    print(f"downloading: {url}")
    print(f"          -> {target}")
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
                        print(f"\r  {pct}% ({mb:.1f}/{tot:.1f} MB)", end="", flush=True)
        shutil.move(tmp, target)
    print()
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default="src/scripts/cell_counts/resources/aba_cache")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_path = (cache_dir / "metadata/WMB-10X/20231215/views"
                  / "cell_metadata_with_cluster_annotation.csv")
    download_to_cache(URL, cache_path)

    print("reading 10x cluster annotations...")
    df = pd.read_csv(cache_path, usecols=TAXONOMY_LEVELS, low_memory=False)
    total_cells = len(df)
    print(f"  {total_cells:,} cells")

    rows = []
    for level in TAXONOMY_LEVELS:
        counts = df[level].dropna().value_counts()
        for cell_set, n in counts.items():
            rows.append({
                "taxonomy_level": level,
                "cell_set": cell_set,
                "cell_count": int(n),
                "percentage_of_total": round(n / total_cells * 100, 3),
            })
        print(f"  {level}: {len(counts)} nodes, {int(counts.sum()):,} cells")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
