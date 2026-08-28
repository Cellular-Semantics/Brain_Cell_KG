// Post-build check that the HMBA BG ID-base fix took effect.
//
// bgo-full.owl asserts every BG cell set twice, under two ID bases with identical
// accessions. `make bgo-local` rewrites the CCN20250428 base onto CS20250428 before
// ingest (src/sparql/bgo_unify_id_base.ru); bgo-full.owl is not in
// config/collectdata/vfb_fullontologies.txt, so it reaches the KG only via that target.
//
// Two failure modes to look for:
//   ccn_nodes_remaining > 0  -- the unprocessed upstream file was loaded (URL restored to
//                               vfb_fullontologies.txt?), so BG cell sets are duplicated
//                               and cannot reach their locations or markers
//   bg_cell_sets = 0         -- `make bgo-local` was never run, so BG is missing entirely
//
// Relationship names below are neo4j2owl's label-derived names for RO:0015001
// ("has exemplar data"), CLM:0010001 ("some soma located in") and CLM:0010003
// ("has marker set"). Update them here if bgo-full renames those properties.

MATCH (n) WHERE n.iri STARTS WITH 'https://purl.brain-bican.org/ontology/CCN20250428/'
RETURN count(n) AS ccn_nodes_remaining
;

// Reachability from BG cell sets to locations / markers via the cell-type class.
// Reference figures for the 2026-04-20 release: 113 cell sets, 89 with a cell type,
// of which 61 carry locations and 42 carry marker sets.
MATCH (cc:Cell_cluster) WHERE cc.iri STARTS WITH 'https://purl.brain-bican.org/ontology/CS20250428/'
OPTIONAL MATCH (cc)<-[:has_exemplar_data]-(c)
OPTIONAL MATCH (c)-[:some_soma_located_in]->(a)
OPTIONAL MATCH (c)-[:has_marker_set]->(m)
WITH cc, count(DISTINCT c) AS cell_types, count(DISTINCT a) AS locations, count(DISTINCT m) AS marker_sets
RETURN
  count(cc) AS bg_cell_sets,
  sum(CASE WHEN cell_types > 0 THEN 1 ELSE 0 END) AS with_cell_type,
  sum(CASE WHEN locations > 0 THEN 1 ELSE 0 END) AS with_location,
  sum(CASE WHEN marker_sets > 0 THEN 1 ELSE 0 END) AS with_marker_set
;

// Every cell set should have exactly one rdfs:label. Two labels means the CCN copy's
// accession-suffixed label survived the rewrite (step 1 of the .ru).
MATCH (cc:Cell_cluster) WHERE cc.iri STARTS WITH 'https://purl.brain-bican.org/ontology/CS20250428/'
  AND size(cc.label_rdfs) <> 1
RETURN cc.curie AS cell_set, cc.label_rdfs AS labels
;
