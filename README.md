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
- Process ROBOT templates (`templates/*.tsv` → `build/*.owl`)
- Generate CSV reports (`src/cypher/*.cypher` → `reports/*.csv`)

#### Individual Tasks
- **OWL Generation**: `make templates`
- **Report Generation**: `make reports` (requires Neo4j running)
- **Template Generation**: `make generate-templates`

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
   make templates
   ```

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
├── build/              # Generated OWL files
└── config/             # OBASK configuration (DO NOT EDIT)
```

## Help

```bash
make help
```

For more details, see `CLAUDE.md` for development guidelines.