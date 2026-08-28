# Brain Cell Knowledge Graph

A knowledge graph build system for brain cell annotation transfer and reporting using the [OBASK](https://github.com/OBASKTools) framework.

## Quick Start

### Prerequisites
- Python 3.8+
- Docker and Docker Compose
- ROBOT (for OWL generation)

### Setup
1. Create and activate virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

### Running the System

#### Start and Build the Knowledge Graph
```bash
docker compose up
```
This runs the full OBASK pipeline: fetches all source OWL/RDF files, loads them into the triplestore, and builds the Neo4j KG. Wait for all services to complete before proceeding.

#### Update the Knowledge Graph (run after build)
Once the KG is loaded, apply post-build Cypher updates (e.g. adding Neo4j labels from taxonomy links):
```bash
make update-kg
```
To preview what would be executed without making changes:
```bash
make update-kg-dry-run
```
Update statements live in `src/cypher_updates/` and are executed in alphabetical order. These extend or modify the KG in ways not covered by the OWL import (e.g. attaching labels that require traversal of named taxonomy individuals).

#### Generate All Content
```bash
make all
```
This will:
- Process ROBOT templates (`src/templates/*.tsv` → `owl/*.owl`)
- Generate CSV reports (`src/cypher/*.cypher` → `reports/*.csv`)

#### Individual Tasks
- **Template Generation**: `make generate-templates` (creates TSV templates from source data)
- **OWL Generation**: `make owl` (processes TSV templates to OWL files)
- **Report Generation**: `make reports` (requires Neo4j running)

## Adding New Reports

1. **Create Cypher Query**: Add a `.cypher` file to `src/cypher/`
   ```cypher
   // Example: src/cypher/my_report.cypher
   MATCH (n:Cell)-[:MAPS_TO]->(m:Cell)
   RETURN n.id, m.id, n.label, m.label
   ```

2. **Run Report Generation**:
   ```bash
   make reports
   ```
   This automatically creates `reports/my_report.csv`

The Makefile automatically discovers all `.cypher` files and generates corresponding `.csv` files with the same name.

## Adding New Templates

1. **Create Source Data**: Add folder under `src/source_data/my_dataset/`
   ```
   src/source_data/my_dataset/
   ├── data/           # Input CSV/TSV files
   └── code/           # Processing scripts
       └── generate.py # Script to create templates
   ```

2. **Generate Templates**:
   ```bash
   make generate-templates
   ```

3. **Process to OWL**:
   ```bash
   make owl
   ```

## WMB Token Mapping and Reporting

The system includes comprehensive Whole Mouse Brain (WMB) cell cluster analysis with token parsing, knowledge graph mapping, and hierarchical reports.

### Token Mapping Reports

Generate detailed WMB token mapping analysis:

```bash
# Generate comprehensive WMB token mapping reports
make wmb-token-mapping
```

This produces:
- **Token usage analysis**: Parse 6,905 WMB cell clusters into ~29,000 tokens
- **Knowledge graph mapping**: Map tokens to anatomical regions, genes, and cell types (98.4% success rate)
- **Problem token analysis**: Identify unmappable tokens for review
- **Excel consolidation**: Single file with all analyses for easy review

### Hierarchical Analysis Reports

Generate advanced hierarchy and consistency reports:

```bash
# Generate most general terms and neurotransmission consistency reports
make wmb-additional-reports
```

This produces:
- **Most general terms report**: For each anatomical/gene mapping, find the highest level in each WMB class branch
- **Neurotransmission consistency report**: Analyze consistency of neurotransmitter patterns across taxonomy levels (86.5% consistency rate)

### ROBOT Template Generation

Generate ROBOT templates for OWL integration:

```bash
# Generate ROBOT templates from WMB mapping results
make wmb-robot-templates
```

Creates templates linking:
- Cell types to anatomical regions via `CLM_0010001`
- Cell types to genes via `CLM_0010003`

## Allen Brain Cell Atlas Analysis

Comprehensive analysis of MERFISH single-cell spatial transcriptomics data from the Allen Brain Cell Atlas.

### Cell Count and Proportion Analysis

Generate detailed cell count reports and regional distribution analysis:

```bash
# Generate cell count and proportion reports from CCF data
make cell-count-analysis
```

This produces:
- **Cell count report**: Total cells for every taxonomy node (neurotransmitter, class, subclass, supertype, cluster)
- **Proportion reports**: For each cell set, shows the proportion of cells in each brain structure
- **Summary analysis**: Overview with top cell sets and regional specificity metrics

### Complete Taxonomy × Region Matrices

Generate full cross-tabulation matrices:

```bash
# Generate complete taxonomy × brain region matrices
make taxonomy-matrices
```

Creates comprehensive matrices showing cell counts for each taxonomy level across all brain regions with detailed documentation and usage examples.

### Data Caching

- **Automatic download**: First run downloads ~1.5GB MERFISH dataset from Allen Brain Cell Atlas
- **Smart caching**: Data cached locally in `src/scripts/cell_counts/resources/aba_cache/`
- **Git-friendly**: Cache directory excluded from version control
- **Reusable**: Same cached data used by both analysis pipelines

## Knowledge Graph Source Files

The OWL/RDF files loaded into the KG are listed in `config/collectdata/vfb_fullontologies.txt`. All sources are fetched from remote URLs at build time. Current sources:

| Source | Notes |
|---|---|
| `cl.owl` | Cell Ontology |
| `wmbo-full.owl` | Whole Mouse Brain Ontology — tracks `releases/latest` |
| `bgo-full.owl` | HMBA Basal Ganglia Ontology — **not fetched by URL**; pre-processed by `make bgo-local` into `config/collectdata/local_ontologies/` (see note below) |
| `CCN20230722.rdf` | WMB taxonomy (named individuals) |
| `CS20250428.rdf` | BG consensus taxonomy (named individuals) |
| `CS202210140_non_neuronal.owl` | Human Brain Cell Atlas non-neuronal |
| `CS202210140_neurons.owl` | Human Brain Cell Atlas neurons |
| `BG2WMB_AT_map_template.owl` | Generated by this repo — fetched from `main` |
| `scFAIR_WHB2WMB_template.owl` | Generated by this repo — fetched from `main` |
| Location mapping OWLs (×4) | Generated by this repo — fetched from `main` |

> **Note on taxonomy vs ontology imports:** Full ontology files (wmbo-full, bgo-full) do not currently expose named taxonomy individuals in a form usable by the `make update-kg` Cypher updates. Those Cypher statements traverse links that only exist in the raw taxonomy RDF files (CCN20230722.rdf, CS20250428.rdf), so both the ontology and taxonomy must be loaded separately. The taxonomy import can be dropped for a given ontology once its full OWL file exposes equivalent named individual links.

> **Note on duplicated BG cell sets — `bgo-full.owl` needs `make bgo-local` before a rebuild:** upstream asserts every HMBA BG cell set twice, under two ID bases with identical accessions: `…/ontology/CS20250428/CS20250428_GROUP_0052` (the CAS taxonomy export, which the `BG:` prefix maps to) and `…/ontology/CCN20250428/CS20250428_GROUP_0052` (the ontology build). Only the base differs, so the two copies load as separate nodes/subjects with the content split between them — the taxonomy metadata, marker gene symbols and this repo's BG2WMB mappings on the CS copy, and all 178 `has_exemplar_data` links from the cell-type classes (the classes carrying the `CLM:0010001` soma locations and `CLM:0010003` marker sets) on the CCN copy. Loaded as-is, a `BG:` cell set cannot reach its locations or markers.
>
> `make bgo-local` downloads upstream `bgo-full.owl`, rewrites the CCN base onto the CS base with `src/sparql/bgo_unify_id_base.ru` (`robot query --update`), and writes the result to `config/collectdata/local_ontologies/`, which the collectdata container merges from its bind mount. **`bgo-full.owl` is therefore not listed in `vfb_fullontologies.txt`** — if you rebuild without running the target, BG is missing from the KG entirely. Re-run `make bgo-local-refresh` after an upstream release. Verify a build with `src/cypher/BG_duplicate_check.cypher`.
>
> This is a workaround; the fix belongs upstream in `Cellular-Semantics/hmba_basal_ganglia_ontology`. When it lands, delete the target, the `.ru` and the local file, and restore the `bgo-full.owl` URL to `vfb_fullontologies.txt`.

> **Note on generated OWL files:** Because this repo's own OWL outputs are fetched from the remote `main` branch, changes to templates or mapping scripts must be pushed and merged before a KG rebuild will pick them up.

## CURIE Prefix Management

All CURIE prefixes are managed in `src/utils/prefixes.json` (JSON-LD format) as the single source of truth.

### Managing Prefixes

Update Neo4j export configuration after modifying prefixes:
```bash
make update-neo4j-prefixes
```

### Finding Missing Namespaces

Detect missing CURIE prefixes (shown as `ns{n}:` patterns) in the knowledge graph:
```bash
# Generate report of missing namespaces
make detect-missing-namespaces

# Get prefix suggestions via prefix commons (requires internet)
make suggest-missing-prefixes
```

This produces `reports/missing_namespaces_report.csv` showing:
- Missing namespace prefixes and their frequency
- Example CURIEs and IRIs for each missing namespace
- Suggested base IRIs that could be used as prefixes
- Automatic suggestions from prefix commons (when available)

## Configuration

Neo4j connection settings (override with `make VAR=value`):
- `NEO4J_HOST=localhost`
- `NEO4J_PORT=7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASS=neo`

## Directory Structure

```
├── src/
│   ├── cypher/         # Cypher query files (.cypher)
│   ├── templates/      # ROBOT template files (.tsv)
│   ├── utils/          # Shared utilities and tools
│   └── source_data/    # Source datasets with data/ and code/ subfolders
├── reports/            # Generated CSV reports
├── owl/                # Generated OWL files
└── config/             # OBASK configuration (DO NOT EDIT)
```

## Help

```bash
make help
```

For more details, see `CLAUDE.md` for development guidelines.