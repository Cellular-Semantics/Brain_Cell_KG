MATCH (tax:Individual)-[:annotations]->(WMB_cc:Cell_cluster)-[:composed_primarily_of]->(WMB_CL:Cell)
WHERE tax.title=['Whole Mouse Brain Taxonomy']
MATCH (WMB_cc)-[:has_labelset]->(WMB_ls)
MATCH (WMB_cc)<-[:subcluster_of*0..]-(WMB_cc2:Cell_cluster)<-[rm:exactMatch]-(BG_cc:Cell_cluster)<-[:annotations]-(tax2:Individual)
MATCH (WMB_cc2)-[:has_labelset]->(WMB_ls2)
WHERE tax2.title = ['HMBA Basal Ganglia Consensus Taxonomy']
MATCH (BG_cc)-[:has_labelset]->(BG_ls)
MATCH p=(BG_cc)-[:subcluster_of*..3]->(n:Cell_cluster)
WHERE (n)-[:has_labelset]->(:Individual { label_rdfs: ['Neighborhood']})
AND NOT (n.label_rdfs[0] = 'Nonneuron')
OPTIONAL MATCH (BG_cc)-[:subcluster_of*0..3]->(BG_cc2:Cell_cluster)-[:composed_primarily_of]->(BG_CL:Cell)
OPTIONAL MATCH (BG_cc2)-[:has_labelset]->(BG_ls2)
RETURN
BG_ls.label_rdfs[0] + ': ' +  BG_cc.label_rdfs[0] + ' --> ' + WMB_ls2.label_rdfs[0] + ': ' + WMB_cc2.label_rdfs[0]  AS BG2WMB_mapping,
BG_cc.rationale_dois AS refs,
reverse([n IN nodes(p) | n.label_rdfs[0]]) AS BG_path,
BG_ls2.label_rdfs[0] + ': ' + BG_cc2.label_rdfs[0] AS BG_mapped_2_CL,
BG_CL.label_rdfs[0] AS BG_CL_mapping,
WMB_ls.label_rdfs[0] + ': ' + WMB_cc.label_rdfs[0] AS WMB_mapped_2_CL,
WMB_CL.label_rdfs[0] AS WMB_CL_mapping,
SIZE([x IN COLLECT(BG_cc2.curie) WHERE x IS NOT NULL]) = 0 AS no_bg_cl_mapping
ORDER BY no_bg_cl_mapping, BG_path