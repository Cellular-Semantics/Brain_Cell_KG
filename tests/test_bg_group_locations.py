"""Unit tests for the BG Group location template generator.

Exercises the pure pieces directly (CURIE/literal parsing, proportion
parsing, template emission) plus the two guards that exist to stop upstream
drift reaching the KG silently: the scale assertion and the bgo-full.owl vs
vendored-CSV cross-check.

An integration test runs the generator over the real vendored CSV and a real
`robot query` dump if that dump is present in build/; it is skipped otherwise.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "source_data" / "bg_group_locations" / "code"))

import generate_bg_group_location_templates as gen  # noqa: E402


CONSENSUS_CSV = (
    REPO / "src" / "source_data" / "bg_group_locations" / "data"
    / "HMBA_BG_consensus_annotation.csv"
)
LOCATIONS_DUMP = REPO / "build" / "bg_group_locations.tsv"


# --------------------------------------------------------------------------- #
# Parsing                                                                     #
# --------------------------------------------------------------------------- #
def test_curie_maps_all_registered_prefixes() -> None:
    assert gen.curie(
        "<https://purl.brain-bican.org/ontology/CS20250428/CS20250428_GROUP_0016>"
    ) == "BG:CS20250428_GROUP_0016"
    assert gen.curie(
        "https://purl.brain-bican.org/ontology/dhbao/DHBA_10344"
    ) == "DHBA:10344"
    assert gen.curie("<http://www.ebi.ac.uk/efo/EFO_0008992>") == "EFO:0008992"
    assert gen.curie("<http://purl.obolibrary.org/obo/PCL_0160090>") == "PCL:0160090"


def test_curie_rejects_unregistered_iri() -> None:
    """A new IRI base must fail loudly rather than reach the template raw."""
    with pytest.raises(ValueError, match="No prefix registered"):
        gen.curie("<http://example.org/Thing_1>")


def test_literal_strips_quoting_and_datatype() -> None:
    assert gen.literal('"0.6"') == "0.6"
    assert gen.literal('"0.6"^^<http://www.w3.org/2001/XMLSchema#float>') == "0.6"
    assert gen.literal('"a label"@en') == "a label"
    assert gen.literal("") == ""


def test_parse_proportions() -> None:
    assert gen.parse_proportions("STR:0.3, SN:0.1, STH:0.1, Adj:0.4") == {
        "STR": 0.3, "SN": 0.1, "STH": 0.1, "Adj": 0.4,
    }
    assert gen.parse_proportions("STR:1.0") == {"STR": 1.0}


def test_parse_proportions_rejects_repeats() -> None:
    with pytest.raises(ValueError, match="Repeated region"):
        gen.parse_proportions("STR:0.3, STR:0.4")


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
def _location(cell_set: str, region: str, ratio: float) -> dict:
    return {
        "cell_set": f"BG:{cell_set}",
        "region": region,
        "ratio": ratio,
        "comment": "Location assignment based on CCF broad region.",
        "evidence": "EFO:0008992",
        "exemplar_class": "CL:4310096",
    }


# --------------------------------------------------------------------------- #
# Guards                                                                      #
# --------------------------------------------------------------------------- #
def test_check_scale_rejects_empty_dump() -> None:
    """The commonest failure: running before `make bgo-local`."""
    with pytest.raises(SystemExit, match="make bgo-local"):
        gen.check_scale([])


def test_check_scale_rejects_wrong_row_count() -> None:
    with pytest.raises(SystemExit, match="Unexpected scale"):
        gen.check_scale([_location("CS20250428_GROUP_0016", "DHBA:10344", 0.6)])


def test_cross_check_passes_when_sources_agree() -> None:
    locations = [
        _location("CS20250428_GROUP_0016", "DHBA:10333", 0.1),
        _location("CS20250428_GROUP_0016", "DHBA:10344", 0.6),
    ]
    consensus = {"CS20250428_GROUP_0016": {"STR": 0.1, "GPi": 0.6, "Adj": 0.3}}
    gen.cross_check(locations, consensus)  # must not raise


def test_cross_check_detects_changed_ratio() -> None:
    locations = [_location("CS20250428_GROUP_0016", "DHBA:10333", 0.1)]
    consensus = {"CS20250428_GROUP_0016": {"STR": 0.4, "Adj": 0.6}}
    with pytest.raises(SystemExit, match="Source drift"):
        gen.cross_check(locations, consensus)


def test_cross_check_detects_unmapped_acronym() -> None:
    """A new region acronym upstream must stop the build, not be skipped."""
    locations = [_location("CS20250428_GROUP_0016", "DHBA:10333", 0.1)]
    consensus = {"CS20250428_GROUP_0016": {"STR": 0.1, "NEW": 0.5, "Adj": 0.4}}
    with pytest.raises(SystemExit, match="unmapped region acronym"):
        gen.cross_check(locations, consensus)


def test_cross_check_detects_group_missing_from_csv() -> None:
    locations = [_location("CS20250428_GROUP_9999", "DHBA:10333", 0.1)]
    with pytest.raises(SystemExit, match="not in the consensus CSV"):
        gen.cross_check(locations, {})


def test_adjacent_is_never_treated_as_a_region() -> None:
    """`Adj` must not be looked up in ACRONYM_TO_DHBA or it would be flagged."""
    assert gen.ADJACENT_KEY not in gen.ACRONYM_TO_DHBA
    locations = [_location("CS20250428_GROUP_0016", "DHBA:10333", 0.1)]
    gen.cross_check(locations, {"CS20250428_GROUP_0016": {"STR": 0.1, "Adj": 0.9}})


# --------------------------------------------------------------------------- #
# Emission                                                                    #
# --------------------------------------------------------------------------- #
def test_location_rows_shape_and_order() -> None:
    rows = gen.location_rows(
        [
            _location("CS20250428_GROUP_0016", "DHBA:10344", 0.6),
            _location("CS20250428_GROUP_0016", "DHBA:10333", 0.1),
        ]
    )
    assert [r[2] for r in rows] == ["DHBA:10333", "DHBA:10344"]
    assert rows[0][0] == "BG:CS20250428_GROUP_0016"
    assert rows[0][1] == "owl:NamedIndividual"
    assert rows[0][3] == "0.1"
    assert rows[0][5] == "EFO:0008992"


def test_adjacent_rows_emitted_only_where_adj_present() -> None:
    locations = [
        _location("CS20250428_GROUP_0016", "DHBA:10344", 0.6),
        _location("CS20250428_GROUP_0049", "DHBA:10333", 1.0),
    ]
    consensus = {
        "CS20250428_GROUP_0016": {"GPi": 0.6, "Adj": 0.4},
        "CS20250428_GROUP_0049": {"STR": 1.0},  # no Adj -> no row
    }
    rows = gen.adjacent_rows(locations, consensus)
    assert [r[0] for r in rows] == ["BG:CS20250428_GROUP_0016"]
    assert rows[0][2] == "0.4"
    assert "Not a soma location assertion." in rows[0][3]


def test_adjacent_ratio_is_read_not_derived_from_residual() -> None:
    """Upstream rounds to 1dp, so 1 - sum(named) is not a safe proxy for Adj.

    Here the named regions sum to 0.5 but Adj is 0.4: the emitted value must
    be the 0.4 that upstream recorded, not the 0.5 residual.
    """
    locations = [_location("CS20250428_GROUP_0047", "DHBA:10333", 0.5)]
    consensus = {"CS20250428_GROUP_0047": {"STR": 0.5, "Adj": 0.4}}
    assert gen.adjacent_rows(locations, consensus)[0][2] == "0.4"


def test_template_headers_declare_float_ratios(tmp_path: Path) -> None:
    """Both templates must type the ratio as xsd:float, not a bare string."""
    path = tmp_path / "loc.tsv"
    gen.write_template(path, gen.LOCATION_HEADER, gen.LOCATION_TYPES, [])
    header, types = list(csv.reader(path.open(), delimiter="\t"))
    assert header[2] == "PCL:0010063"
    assert types[2] == "AI PCL:0010063"
    assert types[3] == ">AT PCL:0010065^^xsd:float"
    assert types[4] == ">A rdfs:comment"
    assert types[5] == ">AI oboInOwl:evidence"
    assert gen.ADJACENT_TYPES[2] == "AT n2o:adjacentCellRatio^^xsd:float"


def test_adjacent_template_asserts_no_location() -> None:
    """Guard the core modelling decision of this transfer."""
    assert not any(
        "0010063" in column or "0010001" in column for column in gen.ADJACENT_TYPES
    )


# --------------------------------------------------------------------------- #
# Integration                                                                 #
# --------------------------------------------------------------------------- #
def test_vendored_csv_covers_every_group() -> None:
    consensus = gen.read_consensus(CONSENSUS_CSV)
    assert len(consensus) == gen.EXPECTED_GROUPS
    assert all(proportions for proportions in consensus.values())


@pytest.mark.skipif(
    not LOCATIONS_DUMP.exists(),
    reason="run `make bg-location-templates` to produce build/bg_group_locations.tsv",
)
def test_real_sources_agree() -> None:
    """The real ontology dump and the real vendored CSV must stay in step."""
    locations = gen.read_locations(LOCATIONS_DUMP)
    consensus = gen.read_consensus(CONSENSUS_CSV)
    gen.check_scale(locations)
    gen.cross_check(locations, consensus)
    assert len(gen.adjacent_rows(locations, consensus)) == 53
