// Query to map MBA anatomical regions to their symbols and IRIs

MATCH (a:Class:MBA)
RETURN a.symbol[0] as symbol, a.iri as iri, a.curie as curie
ORDER BY symbol