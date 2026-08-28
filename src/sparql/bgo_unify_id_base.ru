# Unify the two ID bases that bgo-full.owl uses for HMBA BG cell sets.
#
# Upstream asserts all 113 cell sets twice, with identical accessions but different bases:
#   https://purl.brain-bican.org/ontology/CS20250428/CS20250428_GROUP_0052   (CAS taxonomy export; BG: curie)
#   https://purl.brain-bican.org/ontology/CCN20250428/CS20250428_GROUP_0052  (bgo ontology build)
# The properties split between them -- notably all 178 has_exemplar_data edges from the
# CL/PCL cell-type classes (which carry the CLM:0010001 soma locations and CLM:0010003
# marker sets) attach to the CCN copy, while the taxonomy metadata, markers and this
# repo's BG2WMB mappings attach to the CS copy. Loaded as-is they become two unconnected
# nodes/subjects, so BG: cell sets cannot reach their locations or markers.
#
# Applied by `make bgo-local` before the file is handed to the OBASK pipeline. Rewriting
# the CCN base onto the CS base collapses the two copies (RDF set semantics dedups the
# shared triples on merge). Remove this whole step once upstream emits one base:
# https://github.com/Cellular-Semantics/hmba_basal_ganglia_ontology

PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

# 1. Drop the CCN copies' rdfs:labels before unifying. They are the CS label with the
#    accession appended ("STRd D2 Matrix MSN CS20250428_GROUP_0052"), so keeping them
#    would leave every cell set with two labels and make label_rdfs[0] arbitrary.
DELETE { ?s rdfs:label ?l }
WHERE {
  ?s rdfs:label ?l .
  FILTER(STRSTARTS(STR(?s), "https://purl.brain-bican.org/ontology/CCN20250428/"))
};

# 2. Rewrite CCN-based subjects onto the CS base.
DELETE { ?s ?p ?o }
INSERT { ?new ?p ?o }
WHERE {
  ?s ?p ?o .
  FILTER(STRSTARTS(STR(?s), "https://purl.brain-bican.org/ontology/CCN20250428/"))
  BIND(IRI(REPLACE(STR(?s), "CCN20250428", "CS20250428")) AS ?new)
};

# 3. Rewrite CCN-based objects onto the CS base. Also catches the owl:Axiom reifications
#    (annotatedSource / annotatedTarget) and the has_exemplar_data restriction fillers.
DELETE { ?s ?p ?o }
INSERT { ?s ?p ?new }
WHERE {
  ?s ?p ?o .
  FILTER(isIRI(?o) && STRSTARTS(STR(?o), "https://purl.brain-bican.org/ontology/CCN20250428/"))
  BIND(IRI(REPLACE(STR(?o), "CCN20250428", "CS20250428")) AS ?new)
};
