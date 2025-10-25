// Set taxonomy and labelset labels as :labels (may be better to code for spaces in labels?

MATCH (tax:Individual)-[:annotations]->(cc:Cell_cluster)-[:has_labelset]-(ls:Individual)
CALL apoc.create.addLabels(cc, [tax.label + '_' + ls.label, tax.label]) YIELD node RETURN count(distinct cc)
;

//
MATCH (a:Class) WHERE a.symbol[0] IN
["CB","CTXsp","HIP","HY","Isocortex","LSX","MB","MY",
  "OLF","P","PAL","RHPHow ","STRd","STRv","TH","sAMY"]
AND a.iri =~ "https://purl.brain-bican.org/ontology/mbao/.+"
SET a:Broad_CCF
;

//
MATCH (a:Class) WHERE a.iri =~ 'https://purl.brain-bican.org/ontology/mbao/.+'
SET a:MBA
;

// Add Cell number on Clusters
//MATCH (cc:Cell_cluster:WMB:cluster)
//SET cc.cell_number= coalesce(toInteger(cc.CCN20230722_v2_size[0]),0)
//  + coalesce(toInteger(cc.CCN20230722_v3_size[0]),0)
// ;

// Add Cell number ON subsuming cell sets
// MATCH (cc_up:Cell_cluster)<-[:subcluster_of*..3]-(cc:Cell_cluster:WMB:cluster)
// WITH DISTINCT cc_up, sum(cc.cell_number) AS cc_up_cell_number
//  SET cc_up.cell_number = cc_up_cell_number
// ;


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





// Add granularity labels for MBA anatomical hierarchy

// Add Division granularity label
MATCH (a:Class) WHERE a.symbol[0] IN
["AQ","CB","CTXsp","HPF","HY","Isocortex","MB","MY","OLF","P","PAL","STR","TH","V3","V4","VL","cbf","cm","eps","lfbs","mfbs","scwm"]
AND a.iri =~ "https://purl.brain-bican.org/ontology/mbao/.+"
SET a:Division
;

// Add Structure granularity label
MATCH (a:Class) WHERE a.symbol[0] IN
["AAA","ACAd","ACAv","ACB","ACVII","AD","ADP","AHN","AId","AIp","AIv","AM","AMB","AN","AOB","AON","AP","APN","APr","AQ","ARH","ASO","AT","AUDd","AUDp","AUDpo","AUDv","AV","AVP","AVPV","Acs5","B","BA","BLA","BMA","BST","CA1","CA2","CA3","CEA","CENT","CL","CLA","CLI","CM","COAa","COAp","COPY","CP","CS","CU","CUL","CUN","DCO","DEC","DG","DMH","DMX","DN","DP","DR","DT","DTN","ECT","ECU","ENTl","ENTm","EPd","EPv","EW","Eth","FC","FL","FN","FOTU","FRP","FS","GPe","GPi","GRN","GU","HATA","I5","IA","IAD","IAM","IC","ICB","IF","IG","IGL","III","IIIn","IIn","ILA","IMD","IO","IP","IPN","IRN","ISN","IV","IVn","In","IntG","LA","LAV","LC","LD","LDT","LGd","LGv","LH","LHA","LIN","LING","LM","LP","LPO","LRN","LSc","LSr","LSv","LT","MA","MA3","MARN","MD","MDRN","ME","MEA","MEPO","MG","MH","MM","MOB","MOp","MOs","MPN","MPO","MPT","MRN","MS","MT","MV","NB","NDB","NI","NLL","NLOT","NOD","NOT","NPC","NR","NTB","NTS","OP","ORBl","ORBm","ORBvl","OT","OV","P5","PA","PAA","PAG","PAR","PARN","PAS","PB","PBG","PC5","PCG","PCN","PD","PDTg","PERI","PF","PFL","PG","PGRNd","PGRNl","PH","PIL","PIR","PL","PMd","PMv","PN","PO","POL","POST","PP","PPN","PPT","PPY","PR","PRE","PRM","PRNc","PRNr","PRP","PS","PST","PSTN","PSV","PT","PVH","PVHd","PVT","PVa","PVi","PVp","PVpo","PYR","Pa4","Pa5","PeF","PoT","ProS","RCH","RE","RH","RL","RM","RN","RO","RPA","RPF","RPO","RR","RSPagl","RSPd","RSPv","RT","SAG","SBPV","SCH","SCO","SCm","SCs","SEZ","SF","SFO","SG","SGN","SH","SI","SIM","SLC","SLD","SMT","SNc","SNr","SO","SOC","SPA","SPFm","SPFp","SPIV","SPVC","SPVI","SPVO","SSp-bfd","SSp-ll","SSp-m","SSp-n","SSp-tr","SSp-ul","SSp-un","SSs","STN","SUB","SUM","SUT","SUV","SubG","TEa","TMd","TMv","TR","TRN","TRS","TT","TU","UVU","V","V4r","VAL","VCO","VI","VII","VIIIn","VIIn","VISC","VISa","VISal","VISam","VISl","VISli","VISp","VISpl","VISpm","VISpor","VISrl","VLPO","VM","VMH","VMPO","VPL","VPLpc","VPM","VPMpc","VTA","VTN","VeCB","Vn","XII","Xi","Xn","ZI","arb","cbc","cbp","cc","chpl","cst","drt","epsc","lfbst","mfbc","mfsbshy","rust","tsp"]
AND a.iri =~ "https://purl.brain-bican.org/ontology/mbao/.+"
SET a:Structure
;

// Add Substructure granularity label
MATCH (a:Class) WHERE a.symbol[0] IN
["AAA","ACAd1","ACAd2/3","ACAd5","ACAd6a","ACAd6b","ACAv1","ACAv2/3","ACAv5","ACAv6a","ACAv6b","ACB","ACVII","AD","ADP","AHN","AId1","AId2/3","AId5","AId6a","AId6b","AIp1","AIp2/3","AIp5","AIp6a","AIp6b","AIv1","AIv2/3","AIv5","AIv6a","AIv6b","AMBd","AMBv","AMd","AMv","ANcr1","ANcr2","AOBgl","AOBgr","AOBmi","AON","AP","APN","APr","AQ","ARH","ASO","AT","AUDd1","AUDd2/3","AUDd4","AUDd5","AUDd6a","AUDd6b","AUDp1","AUDp2/3","AUDp4","AUDp5","AUDp6a","AUDp6b","AUDpo1","AUDpo2/3","AUDpo4","AUDpo5","AUDpo6a","AUDpo6b","AUDv1","AUDv2/3","AUDv4","AUDv5","AUDv6a","AUDv6b","AV","AVP","AVPV","Acs5","B","BA","BLAa","BLAp","BLAv","BMAa","BMAp","BST","CA1slm","CA1so","CA1sp","CA1sr","CA2slm","CA2so","CA2sp","CA2sr","CA3slm","CA3slu","CA3so","CA3sp","CA3sr","CEAc","CEAl","CEAm","CENT2","CENT3","CL","CLA","CLI","CM","COAa","COApl","COApm","COPY","CP","CS","CU","CUN","DCO","DEC","DG-mo","DG-po","DG-sg","DMH","DMX","DN","DP","DR","DT","DTN","ECT1","ECT2/3","ECT5","ECT6a","ECT6b","ECU","ENTl1","ENTl2","ENTl3","ENTl5","ENTl6a","ENTm1","ENTm2","ENTm3","ENTm5","ENTm6","EPd","EPv","EW","Eth","FC","FF","FL","FN","FOTU","FRP2/3","FRP5","FRP6a","FRP6b","FS","GPe","GPi","GRN","GU1","GU2/3","GU4","GU5","GU6a","GU6b","HATA","I5","IA","IAD","IAM","ICB","ICc","ICd","ICe","IF","IG","IGL","III","ILA1","ILA2/3","ILA5","ILA6a","ILA6b","IMD","INC","IO","IP","IPA","IPC","IPDL","IPDM","IPI","IPL","IPR","IPRL","IRN","ISN","IV","IVn","IntG","KF","LA","LAV","LC","LD","LDT","LGd-co","LGd-ip","LGd-sh","LGv","LH","LHA","LIN","LING","LM","LP","LPO","LRNm","LRNp","LSc","LSr","LSv","LT","MA","MA3","MARN","MD","MDRNd","MDRNv","ME","MEA","MEPO","MGd","MGm","MGv","MH","MMd","MMl","MMm","MMme","MMp","MOBgr","MOBipl","MOBmi","MOBopl","MOp1","MOp2/3","MOp5","MOp6a","MOp6b","MOs1","MOs2/3","MOs5","MOs6a","MOs6b","MPN","MPO","MPT","MRN","MS","MT","MV","NB","ND","NDB","NI","NLL","NLOT1","NLOT2","NLOT3","NOD","NOT","NPC","NR","NTB","NTS","OP","ORBl1","ORBl2/3","ORBl5","ORBl6a","ORBl6b","ORBm1","ORBm2/3","ORBm5","ORBm6a","ORBm6b","ORBvl1","ORBvl2/3","ORBvl5","ORBvl6a","ORBvl6b","OT","OV","P5","PA","PAA","PAR","PARN","PAS","PBG","PC5","PCG","PCN","PD","PDTg","PERI1","PERI2/3","PERI5","PERI6a","PERI6b","PF","PFL","PG","PGRNd","PGRNl","PH","PIL","PIR","PL1","PL2/3","PL5","PL6a","PL6b","PMd","PMv","PN","PO","POL","POR","POST","PP","PPN","PPT","PPY","PR","PRC","PRE","PRM","PRNc","PRNr","PRP","PS","PST","PSTN","PSV","PT","PVH","PVHd","PVT","PVa","PVi","PVp","PVpo","PYR","Pa4","Pa5","PeF","PoT","ProS","RCH","RE","RH","RL","RM","RN","RO","RPA","RPF","RPO","RR","RSPagl1","RSPagl2/3","RSPagl5","RSPagl6a","RSPagl6b","RSPd1","RSPd2/3","RSPd5","RSPd6a","RSPd6b","RSPv1","RSPv2/3","RSPv5","RSPv6a","RSPv6b","RT","SAG","SBPV","SCH","SCO","SCdg","SCdw","SCig","SCiw","SCop","SCsg","SCzo","SEZ","SF","SFO","SG","SGN","SH","SI","SIM","SLC","SLD","SMT","SNc","SNr","SO","SOCl","SOCm","SPA","SPFm","SPFp","SPIV","SPVC","SPVI","SPVO","SSp-bfd1","SSp-bfd2/3","SSp-bfd4","SSp-bfd5","SSp-bfd6a","SSp-bfd6b","SSp-ll1","SSp-ll2/3","SSp-ll4","SSp-ll5","SSp-ll6a","SSp-ll6b","SSp-m1","SSp-m2/3","SSp-m4","SSp-m5","SSp-m6a","SSp-m6b","SSp-n1","SSp-n2/3","SSp-n4","SSp-n5","SSp-n6a","SSp-n6b","SSp-tr1","SSp-tr2/3","SSp-tr4","SSp-tr5","SSp-tr6a","SSp-tr6b","SSp-ul1","SSp-ul2/3","SSp-ul4","SSp-ul5","SSp-ul6a","SSp-ul6b","SSp-un1","SSp-un2/3","SSp-un4","SSp-un5","SSp-un6a","SSp-un6b","SSs1","SSs2/3","SSs4","SSs5","SSs6a","SSs6b","STN","SUB","SUM","SUT","SUV","Su3","SubG","TEa1","TEa2/3","TEa4","TEa5","TEa6a","TEa6b","TMd","TMv","TR","TRN","TRS","TTd","TTv","TU","UVU","V","V4r","VAL","VCO","VI","VII","VISC1","VISC2/3","VISC4","VISC5","VISC6a","VISC6b","VISa1","VISa2/3","VISa4","VISa5","VISa6a","VISa6b","VISal1","VISal2/3","VISal4","VISal5","VISal6a","VISal6b","VISam1","VISam2/3","VISam4","VISam5","VISam6a","VISam6b","VISl1","VISl2/3","VISl4","VISl5","VISl6a","VISl6b","VISli1","VISli2/3","VISli4","VISli5","VISli6a","VISli6b","VISp1","VISp2/3","VISp4","VISp5","VISp6a","VISp6b","VISpl1","VISpl2/3","VISpl4","VISpl5","VISpl6a","VISpl6b","VISpm1","VISpm2/3","VISpm4","VISpm5","VISpm6a","VISpm6b","VISpor1","VISpor2/3","VISpor4","VISpor5","VISpor6a","VISpor6b","VISrl1","VISrl2/3","VISrl4","VISrl5","VISrl6a","VISrl6b","VLPO","VM","VMH","VMPO","VPL","VPLpc","VPM","VPMpc","VTA","VTN","VeCB","XII","Xi","aco","act","alv","amc","ar","arb","bic","bsc","cbc","ccb","ccg","ccs","chpl","cic","cing","cpd","csc","das","df","dhc","dtd","ee","em","fa","fi","fp","fr","fx","gVIIn","hbc","icp","int","ll","lot","lotd","mcp","mct","mfb","ml","mlf","moV","mp","mtg","mtt","nst","och","onl","opt","or","pc","pm","py","sV","scp","sm","st","sup","tb","ts","tspc","vVIIIn","vhc","vtd"]
AND a.iri =~ "https://purl.brain-bican.org/ontology/mbao/.+"
SET a:Substructure
;
