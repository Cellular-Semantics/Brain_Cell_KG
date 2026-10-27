#!/usr/bin/env python3
"""ROBOT templates putting HMBA BG spatial data on the *taxonomy* nodes.

BGO asserts the basal ganglia taxonomy's spatial proportions on the cell type
*class* (``CLM:0010001`` some soma located in, with the cell fraction on the
reifying axiom). The proportions are a property of the taxonomy Group, so this
script transfers them onto the ``BG:`` cell set via ``has_exemplar_data``.

Two templates are emitted:

``bg_group_location_mappings.tsv``
    One ``PCL:0010063`` edge per (Group, named region), carrying the cell
    fraction as ``PCL:0010065`` (xsd:float), the upstream provenance comment
    and the assay. ``PCL:0010063``/``PCL:0010065`` are used -- not the
    ``CLM:`` terms BGO itself uses -- to stay consistent with this repo's
    existing ``*_location_mappings`` templates for WMB. Both PCL terms are
    obsolete and surface in the KG as ``obsolete_some_soma_located_in`` /
    ``obsolete_cell_ratio``; migrating BG and WMB to ``CLM:`` together is a
    separate job.

``bg_group_adjacent_cell_ratio.tsv``
    One ``n2o:adjacentCellRatio`` data annotation per Group that has one,
    recording the upstream ``Adj`` fraction. This is deliberately *not* a
    location edge -- see the data README.

Sources, and why there are two:

  - named regions: the SPARQL dump of ``bgo-full.owl`` (``--locations``), so
    the acronym -> DHBA mapping stays upstream's and is not re-derived here;
  - ``Adj`` fraction: the vendored consensus CSV (``--consensus``), the only
    source that retains it (upstream drops it to ``root``).

Because the two overlap on the named regions, the script cross-checks them and
fails if they have drifted apart.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

# Expected scale of the upstream data. Asserted so that an upstream change
# (or a run against a non-unified bgo-full.owl, which yields zero rows)
# fails the build loudly rather than quietly emitting a thinner template.
EXPECTED_GROUPS = 61
EXPECTED_LOCATION_ROWS = 86

# Used ONLY to cross-check the consensus CSV against bgo-full.owl. The emitted
# templates take their region CURIEs from the SPARQL dump, never from here.
ACRONYM_TO_DHBA = {
    "STR": "DHBA:10333",   # striatum
    "GPe": "DHBA:10343",   # external segment of globus pallidus
    "GPi": "DHBA:10344",   # internal segment of globus pallidus
    "SN": "DHBA:12251",    # substantia nigra
    "STH": "DHBA:10466",   # subthalamic nucleus
}

# Non-anatomical bucket: tissue adjacent to the dissected nucleus.
ADJACENT_KEY = "Adj"

ADJACENT_COMMENT = (
    "Fraction of cells assigned to the 'Adj' (adjacent) category in the HMBA "
    "basal ganglia consensus annotation: tissue adjacent to the dissected "
    "nucleus, not localised to a named anatomical structure. Not a soma "
    "location assertion."
)

PREFIX_MAP = {
    "https://purl.brain-bican.org/ontology/CS20250428/": "BG:",
    "https://purl.brain-bican.org/ontology/dhbao/DHBA_": "DHBA:",
    "http://www.ebi.ac.uk/efo/EFO_": "EFO:",
    "http://purl.obolibrary.org/obo/CL_": "CL:",
    "http://purl.obolibrary.org/obo/PCL_": "PCL:",
}

LOCATION_HEADER = ["ID", "Type", "PCL:0010063", "cell_ratio", "comment", "evidence"]
LOCATION_TYPES = [
    "ID",
    "TYPE",
    "AI PCL:0010063",
    ">AT PCL:0010065^^xsd:float",
    ">A rdfs:comment",
    ">AI oboInOwl:evidence",
]

ADJACENT_HEADER = ["ID", "Type", "adjacent_cell_ratio", "comment"]
ADJACENT_TYPES = [
    "ID",
    "TYPE",
    "AT n2o:adjacentCellRatio^^xsd:float",
    ">A rdfs:comment",
]


# --------------------------------------------------------------------------- #
# Parsing                                                                     #
# --------------------------------------------------------------------------- #
def curie(term: str) -> str:
    """IRI (bare or <>-wrapped) -> CURIE, using this repo's prefix map."""
    term = term.strip().strip("<>")
    for iri_base, prefix in PREFIX_MAP.items():
        if term.startswith(iri_base):
            return prefix + term[len(iri_base):]
    raise ValueError(f"No prefix registered for IRI: {term}")


def literal(value: str) -> str:
    """Strip SPARQL TSV literal quoting/datatype, e.g. '\"0.6\"' -> '0.6'."""
    value = value.strip()
    if not value:
        return ""
    match = re.match(r'^"(.*)"(?:\^\^\S+|@\S+)?$', value, flags=re.DOTALL)
    if match:
        return match.group(1).replace('\\"', '"').replace("\\n", " ")
    return value


def read_locations(path: Path) -> list[dict]:
    """Read the `robot query` TSV dump of src/sparql/bg_group_locations.sparql."""
    rows = []
    with path.open(newline="") as handle:
        for record in csv.DictReader(handle, delimiter="\t"):
            ratio = literal(record["?ratio"])
            if not ratio:
                raise ValueError(
                    f"Missing cell ratio for {record['?cell_set']} / {record['?region']}"
                )
            rows.append(
                {
                    "cell_set": curie(record["?cell_set"]),
                    "region": curie(record["?region"]),
                    "ratio": float(ratio),
                    "comment": literal(record["?comment"]),
                    "evidence": curie(record["?evidence"]) if record["?evidence"].strip() else "",
                    "exemplar_class": curie(record["?exemplar_class"]),
                }
            )
    return rows


def parse_proportions(text: str) -> dict[str, float]:
    """'STR:0.3, SN:0.1, Adj:0.4' -> {'STR': 0.3, 'SN': 0.1, 'Adj': 0.4}."""
    out: dict[str, float] = {}
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        key, _, value = item.partition(":")
        key = key.strip()
        if key in out:
            raise ValueError(f"Repeated region {key!r} in {text!r}")
        out[key] = float(value.strip())
    return out


def read_consensus(path: Path) -> dict[str, dict[str, float]]:
    """accession_group -> parsed spatial_regional_proportions."""
    with path.open(newline="") as handle:
        return {
            record["accession_group"]: parse_proportions(record["spatial_regional_proportions"])
            for record in csv.DictReader(handle)
            if record.get("accession_group")
        }


# --------------------------------------------------------------------------- #
# Validation                                                                  #
# --------------------------------------------------------------------------- #
def cross_check(locations: list[dict], consensus: dict[str, dict[str, float]]) -> None:
    """Fail if bgo-full.owl and the vendored CSV disagree on the named regions.

    The CSV is only trusted for the `Adj` fraction, but it overlaps the
    ontology on everything else -- so the overlap is a free integrity check on
    the vendored copy being in step with the ingested ontology.
    """
    from_owl: dict[str, dict[str, float]] = defaultdict(dict)
    for row in locations:
        accession = row["cell_set"].split(":", 1)[1]
        from_owl[accession][row["region"]] = row["ratio"]

    problems = []
    for accession, owl_regions in sorted(from_owl.items()):
        if accession not in consensus:
            problems.append(f"{accession}: in bgo-full.owl but not in the consensus CSV")
            continue
        csv_regions = {
            ACRONYM_TO_DHBA[acronym]: ratio
            for acronym, ratio in consensus[accession].items()
            if acronym != ADJACENT_KEY and acronym in ACRONYM_TO_DHBA
        }
        unknown = [
            acronym
            for acronym in consensus[accession]
            if acronym != ADJACENT_KEY and acronym not in ACRONYM_TO_DHBA
        ]
        if unknown:
            problems.append(
                f"{accession}: consensus CSV has unmapped region acronym(s) "
                f"{sorted(unknown)} -- extend ACRONYM_TO_DHBA"
            )
        if owl_regions != csv_regions:
            problems.append(
                f"{accession}: bgo-full.owl {owl_regions} != consensus CSV {csv_regions}"
            )

    if problems:
        raise SystemExit(
            "Source drift between bgo-full.owl and the vendored consensus CSV:\n  "
            + "\n  ".join(problems)
            + "\nRe-vendor src/source_data/bg_group_locations/data/ from upstream."
        )


def check_scale(locations: list[dict]) -> None:
    groups = {row["cell_set"] for row in locations}
    if not locations:
        raise SystemExit(
            "No location rows found. Run `make bgo-local` first -- on the raw "
            "upstream bgo-full.owl the has_exemplar_data links sit on the "
            "CCN20250428 copy and the query returns nothing."
        )
    if len(locations) != EXPECTED_LOCATION_ROWS or len(groups) != EXPECTED_GROUPS:
        raise SystemExit(
            f"Unexpected scale: {len(locations)} rows over {len(groups)} Groups "
            f"(expected {EXPECTED_LOCATION_ROWS} over {EXPECTED_GROUPS}). "
            "If upstream has genuinely changed, update EXPECTED_* in this script."
        )


# --------------------------------------------------------------------------- #
# Emit                                                                        #
# --------------------------------------------------------------------------- #
def write_template(path: Path, header: list[str], types: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerow(types)
        writer.writerows(rows)


def location_rows(locations: list[dict]) -> list[list[str]]:
    rows = [
        [
            row["cell_set"],
            "owl:NamedIndividual",
            row["region"],
            f"{row['ratio']:g}",
            row["comment"],
            row["evidence"],
        ]
        for row in locations
    ]
    rows.sort(key=lambda r: (r[0], r[2]))
    return rows


def adjacent_rows(
    locations: list[dict], consensus: dict[str, dict[str, float]]
) -> list[list[str]]:
    """One row per Group that has an `Adj` fraction, in cell-set order."""
    rows = []
    for cell_set in sorted({row["cell_set"] for row in locations}):
        accession = cell_set.split(":", 1)[1]
        adjacent = consensus.get(accession, {}).get(ADJACENT_KEY)
        if adjacent is None:
            continue
        rows.append([cell_set, "owl:NamedIndividual", f"{adjacent:g}", ADJACENT_COMMENT])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--locations",
        required=True,
        type=Path,
        help="TSV from `robot query` over src/sparql/bg_group_locations.sparql",
    )
    parser.add_argument(
        "--consensus",
        required=True,
        type=Path,
        help="Vendored HMBA_BG_consensus_annotation.csv",
    )
    parser.add_argument(
        "--templates-dir", required=True, type=Path, help="Output directory for the TSVs"
    )
    args = parser.parse_args()

    locations = read_locations(args.locations)
    consensus = read_consensus(args.consensus)

    check_scale(locations)
    cross_check(locations, consensus)

    loc_rows = location_rows(locations)
    adj_rows = adjacent_rows(locations, consensus)

    write_template(
        args.templates_dir / "bg_group_location_mappings.tsv",
        LOCATION_HEADER,
        LOCATION_TYPES,
        loc_rows,
    )
    write_template(
        args.templates_dir / "bg_group_adjacent_cell_ratio.tsv",
        ADJACENT_HEADER,
        ADJACENT_TYPES,
        adj_rows,
    )

    groups = {row["cell_set"] for row in locations}
    # Upstream rounds to 1dp, so named + Adj does not always reach 1.0.
    short = sum(
        1
        for cell_set in groups
        if abs(sum(consensus[cell_set.split(":", 1)[1]].values()) - 1.0) > 1e-9
    )
    print(
        f"bg_group_location_mappings.tsv: {len(loc_rows)} location edges "
        f"over {len(groups)} Groups\n"
        f"bg_group_adjacent_cell_ratio.tsv: {len(adj_rows)} adjacent-fraction "
        f"annotations\n"
        f"note: {short} Group(s) have source proportions summing to <1.0 "
        f"(upstream 1dp rounding); the shortfall is left unassigned",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
