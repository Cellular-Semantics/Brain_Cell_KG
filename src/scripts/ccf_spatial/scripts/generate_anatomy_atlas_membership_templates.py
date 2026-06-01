#!/usr/bin/env python3
"""Emit per-anatomy-term ROBOT templates declaring atlas membership.

For each anatomy ontology term the input CSV records its relationship to a
single named spatial reference atlas (e.g. Allen CCF 2020):

  - **paintedIn**           term is directly painted in the atlas (with level)
  - **descendantsPaintedIn** term has CCF-canonical descendants but is not
                             itself painted (coverage = complete | partial)
  - **notRepresentedIn**    term has no painted descendants anywhere in its
                             subtree → no spatial signal possible

Exactly one of these three edges is emitted per (term, atlas) pair, so the
downstream agent can distinguish "no cells of type X observed here" (a
measurement statement) from "no spatial information available for region Y"
(a coverage statement).

Script is ontology-agnostic: filenames and TSV contents are driven entirely
by the input CSV plus the ``--ontology-prefix`` / ``--atlas-prefix`` /
``--atlas-curie`` flags.

Input CSV schema:
    curie                ontology term CURIE
    painted_level        ``division``|``structure``|``substructure`` or empty
    descendant_coverage  ``complete``|``partial``|``none`` or empty
    painted_descendants  pipe-joined CCF-canonical descendant CURIE list
                         (not used here; consumed by rollup row generation)

Output (in ``--templates-dir``):
    {ontology}_painted_in_{atlas}.tsv
    {ontology}_descendants_painted_in_{atlas}.tsv
    {ontology}_not_represented_in_{atlas}.tsv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _write_template(rows: list[tuple], header: list[str], types: list[str],
                    out_path: Path) -> None:
    """Write a ROBOT template TSV with header + types row + data rows."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(header), "\t".join(types)]
    for r in rows:
        lines.append("\t".join(r))
    out_path.write_text("\n".join(lines) + "\n")


def emit_painted(df: pd.DataFrame, atlas_curie: str, out_path: Path) -> int:
    """Emit a row per term whose painted_level is set."""
    header = ["ID", "Type", "n2o:paintedIn", "atlas_level"]
    types = ["ID", "TYPE", "AI n2o:paintedIn",
             ">AT n2o:atlasLevel^^xsd:string"]
    sel = df[df["painted_level"].notna() & (df["painted_level"].astype(str) != "")]
    rows = [(r["curie"], "owl:NamedIndividual", atlas_curie, str(r["painted_level"]))
            for _, r in sel.iterrows()]
    _write_template(rows, header, types, out_path)
    return len(rows)


def emit_descendants_painted(df: pd.DataFrame, atlas_curie: str,
                             out_path: Path) -> int:
    """Emit a row per term with descendant_coverage in {complete, partial}."""
    header = ["ID", "Type", "n2o:descendantsPaintedIn", "coverage"]
    types = ["ID", "TYPE", "AI n2o:descendantsPaintedIn",
             ">AT n2o:descendantCoverage^^xsd:string"]
    sel = df[df["descendant_coverage"].isin(["complete", "partial"])]
    rows = [(r["curie"], "owl:NamedIndividual", atlas_curie,
             str(r["descendant_coverage"])) for _, r in sel.iterrows()]
    _write_template(rows, header, types, out_path)
    return len(rows)


def emit_not_represented(df: pd.DataFrame, atlas_curie: str,
                         out_path: Path) -> int:
    """Emit a row per term with descendant_coverage == 'none'."""
    header = ["ID", "Type", "n2o:notRepresentedIn"]
    types = ["ID", "TYPE", "AI n2o:notRepresentedIn"]
    sel = df[df["descendant_coverage"] == "none"]
    rows = [(r["curie"], "owl:NamedIndividual", atlas_curie)
            for _, r in sel.iterrows()]
    _write_template(rows, header, types, out_path)
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--membership-csv", required=True, type=Path,
                    help="Per-term × atlas membership CSV produced by the "
                         "corresponding cypher query.")
    ap.add_argument("--atlas-curie", required=True,
                    help="Atlas individual CURIE, e.g. n2o:CCF2020")
    ap.add_argument("--ontology-prefix", required=True,
                    help="Filename token for the anatomy ontology, e.g. 'mba'")
    ap.add_argument("--atlas-prefix", required=True,
                    help="Filename token for the atlas, e.g. 'ccf2020'")
    ap.add_argument("--templates-dir", required=True, type=Path)
    args = ap.parse_args()

    df = pd.read_csv(args.membership_csv, dtype=str, keep_default_na=False)
    if not {"curie", "painted_level", "descendant_coverage"}.issubset(df.columns):
        print(f"Missing required columns in {args.membership_csv}; "
              f"have {list(df.columns)}", file=sys.stderr)
        return 1

    base = f"{args.ontology_prefix}_{{rel}}_in_{args.atlas_prefix}.tsv"
    n_painted = emit_painted(df, args.atlas_curie,
                             args.templates_dir / base.format(rel="painted"))
    n_desc = emit_descendants_painted(df, args.atlas_curie,
                                      args.templates_dir / base.format(rel="descendants_painted"))
    n_none = emit_not_represented(df, args.atlas_curie,
                                  args.templates_dir / base.format(rel="not_represented"))

    print(f"{args.ontology_prefix} × {args.atlas_prefix}: "
          f"painted={n_painted}, descendants_painted={n_desc}, "
          f"not_represented={n_none}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
