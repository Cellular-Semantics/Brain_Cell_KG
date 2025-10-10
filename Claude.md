You build sustainable, extensible code bases for generating knowledge graph content and generating reports from knoweldge graphs.

This repository defines:

* An [OBASK](https://github.com/OBASKTools) knowledge graph that loads a set of standard ontologies as taxonomies, as well as content generated on this repo (mostly annotation transfer)
* A set of tools for generating content for that knowledge graph
* A set of tools for generating standardised reports from that knowledge graph.

Unless explicitly instructed DO NOT EDIT ANYTHING UNDER CONFIG or touch  docker_compose.yml.  This is for the OBASK KG build.

Content and reports are built by a Makefile that lives at the top level. 
This drives ROBOT template commands and scripts that explicitly require input and output paths so that these can be set as Makefile goals and dependencies. 
i.e. No script should hard-wire input or output paths.

Knowledge graph content is generated via [ROBOT templates](https://robot.obolibrary.org/template) that live in the /templates folder.  
Output is added to the owl folder at the top leve.

The following two examples show standard ROBOT template structure for generating RDF representing cell set to cell set annotation transfer:

Group | Type | accession_group     | WMB_exact_match                                | WMB_related_match | WMB_broad_match 
 -- |------|---------------------|------------------------------------------------| -- | -- 
Group | ID   | TYPE                | AI skos:exactMatch SPLIT=\| | AI skos:relatedMatch SPLIT=\| | AI skos:broadMatch SPLIT=\|
Astrocyte | BG:CS20250428_GROUP_0039   | owl:NamedIndividual | WMB:CS20230722_SUBC_318\|WMB:CS20230722_SUBC_319 

ID | Type | skos:exactMatch | exactMatch_score
-- | -- | -- | --
ID | TYPE | AI skos:exactMatch | >AT n2o:Confidence^^xsd:float
WHB:CS202210140_3 | owl:NamedIndividual | WMB:CS20230722_SUBC_338 | 1

The second example shows a case where we have a column recording some confidence score for the annotation transfer mapping.

Given that the templates have a standard structure, generic code should drive the final steps of template generation.  This can live in src/utils. 

The templates are generated from heterogeneous tabular sources. The modelling decisions involved are not always straightforward and so any code generation for this step needs to be guided.  In each case source tables and code should live together in a folder with an informative name under src/source_data.  Subfolders under this should cleanly separate data and code.

Reports will be generated using the makefile by querying the knowledge graph via neo4j/bolt (code in utils).  A generic query wrapper will used queries stored under src/cypher to generate tabular (csv) content and place it in 'reports'.  Default connection to neo4j database should be localhost - set as Make var.

