#!/usr/bin/env python3
"""
Generate ROBOT template attaching total cell counts to WMB cell-type individuals.

Reads cell_counts_by_taxonomy.csv (per-taxonomy-node total cell counts from the
Allen MERFISH dataset, produced by generate_cell_proportion_reports.py) and
cell_set_map.csv (label -> CURIE mapping queried from the KG), and emits a TSV
template that ROBOT will turn into OWL annotations on the WMB cell-type
NamedIndividuals.

The cell_count is attached as a direct annotation (PCL:0010060) on the
individual, distinct from the per-region cell_count annotations on
location-mapping axioms produced by generate_hierarchical_location_templates.py.
"""

import argparse
import sys
import pandas as pd

WMB_DATASET = "Whole Mouse Brain Taxonomy"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", required=True,
                        help="cell_counts_by_taxonomy.csv path")
    parser.add_argument("--cell-set-map", required=True,
                        help="cell_set_map.csv path")
    parser.add_argument("--output", required=True,
                        help="Output ROBOT template TSV path")
    args = parser.parse_args()

    counts = pd.read_csv(args.counts)
    cell_map = pd.read_csv(args.cell_set_map)

    wmb_map = cell_map[cell_map["dataset"] == WMB_DATASET]
    label_to_curie = {
        (row["labelset"], row["label"]): row["curie"]
        for _, row in wmb_map.iterrows()
        if pd.notna(row["label"]) and pd.notna(row["curie"])
    }

    header = ["ID", "Type", "cell_count"]
    types = ["ID", "TYPE", "AT PCL:0010060^^xsd:integer"]
    rows = [header, types]

    missing = []
    for _, row in counts.iterrows():
        key = (row["taxonomy_level"], row["cell_set"])
        curie = label_to_curie.get(key)
        if curie is None:
            missing.append(key)
            continue
        rows.append([curie, "owl:NamedIndividual", str(int(row["cell_count"]))])

    with open(args.output, "w") as f:
        for r in rows:
            f.write("\t".join(r) + "\n")

    written = len(rows) - 2
    print(f"Wrote {written} cell-count annotations to {args.output}")
    if missing:
        print(f"Skipped {len(missing)} rows with no WMB CURIE in cell_set_map.csv",
              file=sys.stderr)
        for m in missing[:10]:
            print(f"  {m}", file=sys.stderr)
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more", file=sys.stderr)


if __name__ == "__main__":
    main()
