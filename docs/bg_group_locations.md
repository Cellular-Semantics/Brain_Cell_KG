# HMBA basal ganglia Group locations on taxonomy nodes

Transfers the HMBA basal ganglia taxonomy's spatial data from the cell type
*class*, where BGO asserts it, onto the *taxonomy node* (the `BG:` cell set),
where it belongs.

Build target: `make bg-location-templates`.

## Why the transfer is needed

The HMBA BG taxonomy assigns each Group a breakdown of where its cells sit,
e.g. for `GPi Shell`:

    striatum (STR, 0.1), external globus pallidus (GPe, 0.1),
    internal globus pallidus (GPi, 0.6)

BGO pushes this onto the cell type class (`CL:4310096` here) as `CLM:0010001`
*some soma located in* annotation assertions, with the cell fraction, a
provenance comment and the assay on the reifying `owl:Axiom`. The proportions
are properties of the *taxonomy Group*, though, not of the cell type: they are
"what fraction of the cells in this cluster came from where". The `BG:` cell
set carried none of it, so nothing downstream could ask "where are the cells
of this Group?" without hopping to the class.

## What is emitted

Two ROBOT templates, both keyed on the `BG:` cell set.

### `templates/bg_group_location_mappings.tsv` — 86 edges over 61 Groups

One `PCL:0010063` edge per (Group, named region):

| column | meaning |
| --- | --- |
| `AI PCL:0010063` | DHBA region |
| `>AT PCL:0010065^^xsd:float` | fraction of the Group's cells in that region |
| `>A rdfs:comment` | upstream provenance note |
| `>AI oboInOwl:evidence` | assay (`EFO:0008992`, MERFISH) |

Regions used: `DHBA:10333` striatum (53), `DHBA:10343` GPe (17),
`DHBA:12251` substantia nigra (11), `DHBA:10466` subthalamic nucleus (3),
`DHBA:10344` GPi (2).

**On `PCL:` vs `CLM:`.** BGO uses `CLM:0010001`/`CLM:0010002`. This repo's
existing WMB `*_location_mappings` templates use `PCL:0010063`/`PCL:0010065`,
and these follow suit so that BG and WMB taxonomy nodes answer to one query
pattern. Both PCL terms are **obsolete**, and neo4j2owl names them
`obsolete_some_soma_located_in` and `obsolete_cell_ratio` in the KG — so BG
*cell sets* carry `obsolete_some_soma_located_in` while BG *classes* carry
`some_soma_located_in` from BGO. Migrating BG and WMB to `CLM:` together is
deferred, deliberately; it touches ~19k existing WMB edges.

### `templates/bg_group_adjacent_cell_ratio.tsv` — 53 annotations

One `n2o:adjacentCellRatio` data annotation (xsd:float) per Group that has
one, recording the upstream `Adj` fraction.

## The `Adj` fraction, and why it is not a location

The named regions above do not account for all the cells. The upstream source
(`spatial_regional_proportions` in `HMBA_BG_consensus_annotation.csv`) has a
sixth key, `Adj` — "adjacent" — present on 53 of 61 Groups and reaching 0.9 on
some. BGO drops it:

```python
# hmba_basal_ganglia_ontology/src/scripts/template_generation_tools.py
if region_label.lower() in ["na", "adj"]:
    region_label = 'root'  # handle NA as brain
```

`root` is absent from the DHBA symbol map, so the fraction silently vanishes
and the surviving proportions no longer sum to 1.

It is **not** recorded as a soma location here, for two reasons:

1. It means tissue *adjacent to* the dissected nucleus — cells the dissection
   caught that are not localised to a named structure. Asserting a location
   from it would invent an anatomical claim the source does not make.
2. It could not be "the rest of the basal ganglia" anyway. For the 12 Groups
   whose named regions are substantia nigra or subthalamic nucleus, neither
   region has a path to `DHBA:10332` ("basal nuclei (basal ganglia)") in the
   DHBA hierarchy — they are midbrain and diencephalon.

So it is carried as a plain data annotation on the cell set: visible and
queryable, asserting nothing about anatomy.

**Do not reconstruct it as `1 - sum(named)`.** Upstream rounds to one decimal
place; 46 of 61 Groups sum to 1.0 and the other 15 sum to 0.9. The generator
reads `Adj` directly and leaves that 0.1 slack unassigned.

## Why Group level only

Only Group rows carry spatial data upstream. Rolling up to Subclass / Class /
Neighborhood would need per-Group **cell counts** to weight the means — a
parent's ratio is the count-weighted mean of its children's — and no available
source has them (not the KG cell set nodes, not the CAS `CCN20250428.json`,
not the consensus CSV).

Without weights the only sound statement is a bound: a weighted mean lies
between its children's min and max, so a parent's ratio for region R is at
most `max(child ratios)`. The matching lower bound collapses to 0 whenever any
child lacks R, which makes the pair near-useless. Not worth the modelling
noise; revisit if per-Group cell counts become available, at which point the
real weighted roll-up is short work.

## Sources, and the cross-check

Two sources, because neither alone is sufficient:

| source | supplies | why |
| --- | --- | --- |
| `config/collectdata/local_ontologies/bgo-full.owl` via `src/sparql/bg_group_locations.sparql` | named regions + ratios | keeps upstream's acronym → DHBA mapping authoritative instead of re-deriving it |
| `src/source_data/bg_group_locations/data/HMBA_BG_consensus_annotation.csv` | the `Adj` fraction | the only source that still has it |

They overlap on the named regions, so the generator compares them per Group
and **fails the build** on any disagreement — a free integrity check that the
vendored CSV has not drifted from the ingested ontology. A new region acronym
upstream also fails the build rather than being skipped.

The SPARQL depends on `make bgo-local` having run: on the raw upstream
`bgo-full.owl` the `has_exemplar_data` links sit on the `CCN20250428` copy of
each cell set and the query returns nothing. The generator says so explicitly
if it gets an empty dump.

Note `has_exemplar_data` (`RO:0015001`) is asserted as an OWL `hasValue`
restriction, not a plain triple — hence the `subClassOf`/`onProperty` pattern
in the query.

## Verifying after a rebuild

`src/cypher/BG_group_location_report.cypher` (→
`reports/BG_group_location_report.csv`) compares each Group's transferred
locations against those still on its exemplar class. Expect 61 rows, all with
`regions_agree = true`.

## Ingest

Both OWL outputs need listing in `config/collectdata/vfb_fullontologies.txt`
and only take effect once pushed to `main` (that file holds raw-GitHub URLs):

```
https://raw.githubusercontent.com/Cellular-Semantics/Brain_Cell_KG/refs/heads/main/owl/bg_group_location_mappings.owl
https://raw.githubusercontent.com/Cellular-Semantics/Brain_Cell_KG/refs/heads/main/owl/bg_group_adjacent_cell_ratio.owl
```

`EFO` and `n2o:adjacentCellRatio` also want to resolve cleanly in Neo4j. `EFO`
has been added to `src/utils/prefixes.json`; propagating it to the KG curie_map
(`config/dumps/neo4j2owl-config.yaml`) is the same pending job as the `DHBA`/
`CLM` entries covered by `src/cypher_updates/tmp_dhba_clm_curies.cypher` —
without it `EFO:0008992` loads as `ns{n}:EFO_0008992`.

## Refreshing after an upstream release

```bash
make bgo-local-refresh
cp ../hmba_basal_ganglia_ontology/src/dendrograms/28082024/HMBA_BG_consensus_annotation.csv \
   src/source_data/bg_group_locations/data/
make bg-location-templates
```

If upstream genuinely changes scale, the 61/86 assertions in the generator
need updating — they exist to make such a change a conscious decision.
