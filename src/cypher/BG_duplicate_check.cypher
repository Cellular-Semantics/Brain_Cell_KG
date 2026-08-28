// Post-build check for the HMBA BG duplicated-cell-set problem
// (see src/cypher_updates/01_merge_bg_duplicate_cell_sets.cypher).
//
// Expected after `make update-kg`: ccn_nodes_remaining = 0, and every BG Group that has a
// cell-type class should reach that class's soma locations and marker sets.
// If ccn_nodes_remaining > 0 the merge did not run (or upstream changed the ID bases again).
//
// Relationship names below are neo4j2owl's label-derived names for RO:0015001
// ("has exemplar data"), CLM:0010001 ("some soma located in") and CLM:0010003
// ("has marker set"). If bgo-full renames those properties, update them here --
// the merge itself is relationship-name agnostic and needs no change.

MATCH (n) WHERE n.iri STARTS WITH 'https://purl.brain-bican.org/ontology/CCN20250428/'
RETURN count(n) AS ccn_nodes_remaining
;

// Reachability from BG cell sets to locations / markers via the cell-type class.
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
