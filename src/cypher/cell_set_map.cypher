// Cypher query to map cell sets to their labels and IRIs

MATCH (ds:Individual)-[:annotations]->(cc:Cell_cluster)
-[:has_labelset]-(ls:Individual) 
return ds.title[0] as dataset,
 ls.label as labelset, ls.rank[0] as labelset_rank, 
 cc.label as label,  cc.iri as iri
  order by dataset, labelset_rank DESC