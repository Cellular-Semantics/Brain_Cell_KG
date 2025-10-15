// Set taxonomy and labelset labels as :labels (may be better to code for spaces in labels?

MATCH (tax:Individual)-[:annotations]->(cc:Cell_cluster)-[:has_labelset]-(ls:Individual)
CALL apoc.create.addLabels(cc, [ls.label, tax.label]) YIELD node RETURN count(distinct cc)
;

//
MATCH (a:Class) WHERE a.symbol[0] IN
["CB","CTXsp","HIP","HY","Isocortex","LSX","MB","MY",
  "OLF","P","PAL","RHP","STRd","STRv","TH","sAMY"]
AND a.iri =~ "https://purl.brain-bican.org/ontology/mbao/.+"
SET a:Broad_CCF
;

//
MATCH (a:Class) WHERE a.iri =~ 'https://purl.brain-bican.org/ontology/mbao/.+'
SET a:MBA
;

// Add Cell number on Clusters
MATCH (cc:Cell_cluster:WMB:cluster)
SET cc.cell_number= coalesce(toInteger(cc.CCN20230722_v2_size[0]),0)
  + coalesce(toInteger(cc.CCN20230722_v3_size[0]),0)
 ;

// Add Cell number ON subsuming cell sets
MATCH (cc_up:Cell_cluster)<-[:subcluster_of*..3]-(cc:Cell_cluster:WMB:cluster)
WITH DISTINCT cc_up, sum(cc.cell_number) AS cc_up_cell_number
 SET cc_up.cell_number = cc_up_cell_number
;


// Add cell counts per brain region on clusters
//MATCH (cc:Cell_cluster:WMB:cluster)<-[:has_exemplar_data]-(c:Cell)
//        -[r:obsolete_some_soma_located_in]->(a:Class)
//WHERE NOT ('Broad_CCF' in labels(a))
// RETURN cc.cell_number, r.ratio
//SET r.cell_number =  toInteger(cc.cell_number * toFloat(r.cell_ratio[0]))

// Add up those cell counts up the hierarchy and calc cell_ratios
// TODO Add filter for gross regions (?)
//MATCH (cc_up)-[:subcluster_of*1..3]-(cc:Cell_cluster:WMB:cluster)<-[:has_exemplar_data]-(c:Cell)
//        -[r:obsolete_some_soma_located_in]->(a:Class)
//WHERE cc.cell_number is not null and cc.cell_number > 0 and toFloat(r.cell_ratio[0]) > 0.2
// WITH DISTINCT cc_up, a, sum(r.cell_number) as tot_num,
//               (round(toFloat(tot_num)/toFloat(cc.cell_number), 2)) as ratio
// return cc_up.label, a.label, tot_num, ratio

// MERGE (cc_up)-[r2:obsolete_some_soma_located_in]->(a)
// SET r2.cell_number = tot_num
// SET r2.cell_ratio = [tot_num/cc.cell_number]

// Add check for NTs

// Add in mapping from tokens?





