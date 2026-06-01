// One row per MBA term describing its relationship to the Allen CCF 2020
// painted parcellation, derived from CCF-level labels (Division / Structure /
// Substructure) already attached to MBA nodes by the upstream KG build.
//
// Columns:
//   curie               MBA term CURIE
//   painted_level       "division" | "structure" | "substructure" | NULL
//                       (NULL ⇒ term is not directly painted in CCF 2020)
//   descendant_coverage "complete" | "partial" | "none" | NULL
//                       (NULL ⇒ term is painted directly; coverage is moot)
//   painted_descendants pipe-joined list of CCF-canonical descendant CURIEs
//                       (empty when painted_level is set OR coverage = "none")
//
// "complete" coverage: every MBA leaf in the term's part_of subtree is itself
// CCF-canonical. A rollup over painted_descendants captures every painted
// voxel of the term's anatomical territory.
//
// "partial" coverage: the subtree contains ≥1 CCF-canonical descendant AND
// ≥1 unpainted leaf (an MBA leaf with no CCF label, whose cells live in some
// ancestor's <ancestor>-unassigned bucket and are not attributable to a named
// child). Rollup under-counts the term's true territory.
//
// "none" coverage: no CCF-canonical descendant exists anywhere in the
// subtree → no spatial signal possible for this term at any granularity.
MATCH (x:Class:MBA)
WITH x,
     CASE
       WHEN x:Division     THEN "division"
       WHEN x:Structure    THEN "structure"
       WHEN x:Substructure THEN "substructure"
       ELSE NULL
     END AS painted_level
OPTIONAL MATCH (ccf_desc:MBA)-[:part_of*1..]->(x)
  WHERE ccf_desc:Division OR ccf_desc:Structure OR ccf_desc:Substructure
WITH x, painted_level, collect(DISTINCT ccf_desc.curie) AS painted_desc_list
OPTIONAL MATCH (unpainted_leaf:MBA)-[:part_of*1..]->(x)
  WHERE NOT EXISTS { (:MBA)-[:part_of]->(unpainted_leaf) }
    AND NOT (unpainted_leaf:Division OR unpainted_leaf:Structure OR unpainted_leaf:Substructure)
WITH x, painted_level, painted_desc_list,
     count(DISTINCT unpainted_leaf) AS n_unpainted_leaves
RETURN x.curie AS curie,
       painted_level,
       CASE
         WHEN painted_level IS NOT NULL                    THEN NULL
         WHEN size(painted_desc_list) = 0                  THEN "none"
         WHEN n_unpainted_leaves = 0                       THEN "complete"
         ELSE                                                   "partial"
       END AS descendant_coverage,
       reduce(s = '', c IN painted_desc_list |
              CASE WHEN s = '' THEN c ELSE s + '|' + c END) AS painted_descendants
ORDER BY curie
