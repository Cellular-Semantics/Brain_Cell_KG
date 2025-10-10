#!/usr/bin/env python3
"""
Generic report generator that executes Cypher queries and outputs CSV reports.
Used by Makefile to generate standardized reports from the knowledge graph.
"""

import argparse
import sys
from pathlib import Path
from neo4j_bolt_wrapper import Neo4jBoltQueryWrapper


def load_cypher_query(query_file):
    """Load Cypher query from file."""
    with open(query_file, 'r') as f:
        return f.read().strip()


def generate_report(query_file, output_file, host, port, user, password):
    """Generate CSV report from Cypher query."""
    try:
        # Load query
        query = load_cypher_query(query_file)
        if not query:
            raise ValueError(f"Empty query file: {query_file}")

        # Connect to Neo4j
        endpoint = f"bolt://{host}:{port}"
        wrapper = Neo4jBoltQueryWrapper(endpoint, user, password)

        # Execute query and get CSV output
        csv_result = wrapper.run_query(query, return_type="csv")

        # Write to output file
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(csv_result)

        print(f"Report generated: {output_file}")
        return True

    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate CSV reports from Cypher queries")
    parser.add_argument("--query", required=True, help="Path to Cypher query file")
    parser.add_argument("--output", required=True, help="Output CSV file path")
    parser.add_argument("--host", default="localhost", help="Neo4j host")
    parser.add_argument("--port", default="7687", help="Neo4j port")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo", help="Neo4j password")

    args = parser.parse_args()

    success = generate_report(
        args.query, args.output, args.host, args.port, args.user, args.password
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()