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

#### Start Neo4j Database (Required for Reports)
```bash
docker compose up
```
This starts the Neo4j database on localhost:7687 required for report generation.

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