// TEMPORARY: give DHBA and CLM nodes proper CURIEs in a KG built before those prefixes
// were added to the curie_map (config/dumps/neo4j2owl-config.yaml, src/utils/prefixes.json).
//
// Without them neo4j2owl assigns generated ns{n}: prefixes, e.g. the BG soma-location
// targets load as `nsN:DHBA_10333` rather than `DHBA:10333`.
//
// Idempotent, and a no-op on any build that picked up the curie_map entries. Delete this
// file once a full rebuild has been done with the updated config.

MATCH (n) WHERE n.iri STARTS WITH 'https://purl.brain-bican.org/ontology/dhbao/DHBA_'
  AND coalesce(n.curie, "") <> 'DHBA:' + substring(n.iri, size('https://purl.brain-bican.org/ontology/dhbao/DHBA_'))
SET n.curie = 'DHBA:' + substring(n.iri, size('https://purl.brain-bican.org/ontology/dhbao/DHBA_'))
RETURN count(n) AS dhba_curies_fixed
;

MATCH (n) WHERE n.iri STARTS WITH 'http://purl.obolibrary.org/obo/CLM_'
  AND coalesce(n.curie, "") <> 'CLM:' + substring(n.iri, size('http://purl.obolibrary.org/obo/CLM_'))
SET n.curie = 'CLM:' + substring(n.iri, size('http://purl.obolibrary.org/obo/CLM_'))
RETURN count(n) AS clm_curies_fixed
;
