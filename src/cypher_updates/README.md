# Knowledge Graph Update Cypher Statements

This directory contains Cypher statements that modify or extend the knowledge graph, distinct from the read-only queries in `src/cypher/` that generate reports.

## Usage

Execute all update statements:
```bash
make update-kg
```

## File Naming Convention

- `*.cypher` - Update/modification statements
- Files are executed in alphabetical order
- Use prefixes for ordering if needed (e.g., `01_`, `02_`, etc.)

## Guidelines

- Each file should contain idempotent operations where possible
- Use `MERGE` instead of `CREATE` to avoid duplicates
- Include comments explaining the purpose of each update
- Test queries on a copy of the database first

## Examples

```cypher
// Create new relationship types
MERGE (a:Node {id: 'example'})
MERGE (b:Node {id: 'target'})
MERGE (a)-[:NEW_RELATIONSHIP]->(b)
```