// BG Group spatial annotation transfer: coverage and agreement check.
//
// Verifies that owl/bg_group_location_mappings.owl and
// owl/bg_group_adjacent_cell_ratio.owl landed correctly, by comparing each
// Group cell set's transferred soma locations against those still asserted on
// its exemplar cell type class in BGO.
//
// Expected after a rebuild that ingests both OWL files: 61 rows, every row
// with regions_agree = true and class_regions non-empty.
//
// Note the transferred edges use PCL:0010063 / PCL:0010065 for consistency
// with this repo's WMB *_location_mappings templates. Both PCL terms are
// obsolete, so neo4j2owl names them obsolete_some_soma_located_in and
// obsolete_cell_ratio. BGO's own class-level edges use the CLM: equivalents.
// Migrating BG and WMB to CLM: together will change both halves of this query.
//
// named_ratio_sum is the fraction of cells placed in named anatomical
// regions. adjacent_cell_ratio is the upstream 'Adj' fraction -- tissue
// adjacent to the dissected nucleus, deliberately NOT asserted as a location.
// The two need not sum to 1.0: upstream rounds to one decimal place and 15 of
// the 61 Groups fall 0.1 short.

MATCH (g:CS20250428_Group)
OPTIONAL MATCH (cls:Class)-[:has_exemplar_data]->(g)
OPTIONAL MATCH (cls)-[cr]->(creg:Class)
  WHERE cr.short_form = 'CLM_0010001'
WITH g, cls, collect(DISTINCT creg.curie) AS class_regions
OPTIONAL MATCH (g)-[gr]->(greg:Class)
  WHERE gr.short_form = 'PCL_0010063'
WITH g, cls, class_regions,
     collect(DISTINCT greg.curie) AS group_regions,
     sum(toFloat(coalesce(gr.obsolete_cell_ratio[0], gr.cell_ratio[0], 0.0)))
       AS named_ratio_sum
RETURN g.curie                                   AS group_curie,
       g.label                                   AS group_label,
       cls.curie                                 AS exemplar_class,
       size(group_regions)                       AS n_transferred_regions,
       apoc.text.join(apoc.coll.sort(group_regions), '|') AS transferred_regions,
       apoc.text.join(apoc.coll.sort(class_regions), '|') AS class_regions,
       apoc.coll.sort(group_regions) = apoc.coll.sort(class_regions)
                                                 AS regions_agree,
       round(named_ratio_sum * 1000) / 1000       AS named_ratio_sum,
       g.adjacentCellRatio[0]                    AS adjacent_cell_ratio
ORDER BY group_curie
