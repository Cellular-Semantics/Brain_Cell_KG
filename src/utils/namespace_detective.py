#!/usr/bin/env python3
"""
Namespace Detective - Find missing CURIE prefixes in the knowledge graph.

This script identifies ns{n}: prefixes assigned by neo4j2owl when no proper
CURIE prefix is defined, and attempts to find proper prefixes via prefix commons.
"""

import sys
import re
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

# Add utils to path for neo4j wrapper
sys.path.append(str(Path(__file__).parent))
from neo4j_bolt_wrapper import Neo4jBoltQueryWrapper


class NamespaceDetective:
    """Detect and resolve missing CURIE prefixes in the knowledge graph."""

    def __init__(self, neo4j_host: str = "localhost", neo4j_port: str = "7687",
                 neo4j_user: str = "neo4j", neo4j_password: str = "neo"):
        """Initialize with Neo4j connection."""
        self.neo4j_wrapper = Neo4jBoltQueryWrapper(
            f"bolt://{neo4j_host}:{neo4j_port}", neo4j_user, neo4j_password
        )

    def find_missing_namespaces(self) -> List[Dict]:
        """Find all ns{n}: prefixes in the knowledge graph."""
        print("Scanning knowledge graph for missing namespaces (ns{n}: patterns)...")

        query = """
        // Find all nodes with ns{n}: CURIEs
        MATCH (n)
        WHERE n.curie =~ 'ns\\d+:.*'
        WITH n.curie as curie, n.iri as iri, n.short_form as short_form, n.label as label
        ORDER BY curie
        WITH curie, iri, short_form, label
        // Extract the namespace prefix (e.g., 'ns3' from 'ns3:MBA_583')
        WITH split(curie, ':')[0] as namespace_prefix,
             curie, iri, short_form, label
        // Get one example per namespace
        WITH namespace_prefix,
             collect({curie: curie, iri: iri, short_form: short_form, label: label})[0] as example,
             count(*) as occurrence_count
        ORDER BY namespace_prefix
        RETURN namespace_prefix, example.curie as example_curie,
               example.iri as example_iri, example.short_form as example_short_form,
               example.label as example_label, occurrence_count
        """

        results = self.neo4j_wrapper.run_query(query, return_type="records")

        missing_namespaces = []
        for result in results:
            missing_namespaces.append({
                'namespace_prefix': result.get('namespace_prefix'),
                'example_curie': result.get('example_curie'),
                'example_iri': result.get('example_iri'),
                'example_short_form': result.get('example_short_form'),
                'example_label': result.get('example_label'),
                'occurrence_count': result.get('occurrence_count')
            })

        return missing_namespaces

    def extract_iri_base(self, iri: str) -> Optional[str]:
        """Extract the base IRI that could be used as a prefix."""
        if not iri:
            return None

        # Common patterns for extracting base IRIs
        patterns = [
            # Pattern: http://example.com/path/ID -> http://example.com/path/
            r'^(https?://[^/]+/[^/]+/)([^/]+)/?$',
            # Pattern: http://example.com/path#ID -> http://example.com/path#
            r'^(https?://[^#]+#)(.+)$',
            # Pattern: http://example.com/ID -> http://example.com/
            r'^(https?://[^/]+/)([^/]+)/?$',
            # Pattern: http://example.com/path_ID -> http://example.com/path_
            r'^(.*[/_])([^/_]+)$'
        ]

        for pattern in patterns:
            match = re.match(pattern, iri)
            if match:
                return match.group(1)

        return None

    def lookup_prefix_commons(self, iri_base: str) -> Optional[Dict]:
        """Look up a potential prefix on prefix commons."""
        if not iri_base:
            return None

        try:
            # Try the prefix commons API
            api_url = f"https://prefixcommons.org/api/uri_to_curie/{iri_base}"
            response = requests.get(api_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'prefixes' in data:
                    # Return the first valid prefix found
                    for prefix_info in data['prefixes']:
                        if 'prefix' in prefix_info and 'uri' in prefix_info:
                            return {
                                'suggested_prefix': prefix_info['prefix'],
                                'suggested_uri': prefix_info['uri'],
                                'source': 'prefix_commons_api'
                            }

            # Fallback: try searching by base URI
            search_url = f"https://prefixcommons.org/api/search/{iri_base}"
            response = requests.get(search_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    first_result = data[0]
                    if 'prefix' in first_result and 'uri' in first_result:
                        return {
                            'suggested_prefix': first_result['prefix'],
                            'suggested_uri': first_result['uri'],
                            'source': 'prefix_commons_search'
                        }

        except Exception as e:
            print(f"Warning: Could not query prefix commons for {iri_base}: {e}")

        return None

    def generate_namespace_report(self, output_file: str) -> str:
        """Generate a comprehensive report of missing namespaces."""
        print("=== Namespace Detective Report ===")

        # Find missing namespaces
        missing_namespaces = self.find_missing_namespaces()

        if not missing_namespaces:
            print("✅ No missing namespaces found! All CURIEs have proper prefixes.")
            # Still create an empty report
            df = pd.DataFrame(columns=[
                'namespace_prefix', 'example_curie', 'example_iri', 'example_short_form',
                'example_label', 'occurrence_count', 'suggested_iri_base',
                'suggested_prefix', 'suggested_uri', 'lookup_source', 'status'
            ])
            df.to_csv(output_file, index=False)
            return output_file

        print(f"Found {len(missing_namespaces)} missing namespace prefixes")

        # Analyze each missing namespace
        enhanced_results = []
        for ns in missing_namespaces:
            print(f"Analyzing {ns['namespace_prefix']}: {ns['example_curie']} ({ns['occurrence_count']} occurrences)")

            # Extract potential base IRI
            iri_base = self.extract_iri_base(ns['example_iri'])

            # Look up on prefix commons
            prefix_suggestion = self.lookup_prefix_commons(iri_base) if iri_base else None

            result = {
                **ns,
                'suggested_iri_base': iri_base,
                'suggested_prefix': prefix_suggestion.get('suggested_prefix') if prefix_suggestion else None,
                'suggested_uri': prefix_suggestion.get('suggested_uri') if prefix_suggestion else None,
                'lookup_source': prefix_suggestion.get('source') if prefix_suggestion else None,
                'status': 'suggestion_found' if prefix_suggestion else 'needs_manual_review'
            }
            enhanced_results.append(result)

        # Create DataFrame and save
        df = pd.DataFrame(enhanced_results)
        df.to_csv(output_file, index=False)

        # Summary
        total_occurrences = sum(ns['occurrence_count'] for ns in missing_namespaces)
        suggestions_found = len([r for r in enhanced_results if r['status'] == 'suggestion_found'])

        print(f"\n=== Summary ===")
        print(f"Missing namespace prefixes: {len(missing_namespaces)}")
        print(f"Total affected entities: {total_occurrences}")
        print(f"Suggestions found: {suggestions_found}/{len(missing_namespaces)}")
        print(f"Report saved: {output_file}")

        return output_file

    def suggest_prefix_additions(self, namespace_report_file: str) -> str:
        """Generate suggested additions to prefixes.json based on the namespace report."""
        print("Generating prefix suggestions...")

        # Load the namespace report
        df = pd.read_csv(namespace_report_file)

        # Filter for suggestions found
        suggestions = df[df['status'] == 'suggestion_found']

        if suggestions.empty:
            print("No automatic suggestions available.")
            return ""

        # Load current prefixes
        prefixes_file = Path(__file__).parent / "prefixes.json"
        with open(prefixes_file, 'r') as f:
            current_prefixes = json.load(f)['@context']

        # Generate suggestions
        new_suggestions = {}
        for _, row in suggestions.iterrows():
            prefix = row['suggested_prefix']
            uri = row['suggested_uri']

            # Check if not already defined
            if prefix not in current_prefixes:
                new_suggestions[prefix] = uri

        if new_suggestions:
            print(f"\nSuggested additions to src/utils/prefixes.json:")
            for prefix, uri in new_suggestions.items():
                print(f'    "{prefix}": "{uri}",')
        else:
            print("All suggested prefixes are already defined.")

        return json.dumps(new_suggestions, indent=2)


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Detect missing CURIE namespaces in the KG")
    parser.add_argument("--output", default="reports/missing_namespaces_report.csv",
                       help="Output file for the namespace report")
    parser.add_argument("--host", default="localhost", help="Neo4j host")
    parser.add_argument("--port", default="7687", help="Neo4j port")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo", help="Neo4j password")
    parser.add_argument("--suggest", action="store_true",
                       help="Generate prefix suggestions for prefixes.json")

    args = parser.parse_args()

    # Create detective and generate report
    detective = NamespaceDetective(args.host, args.port, args.user, args.password)
    report_file = detective.generate_namespace_report(args.output)

    if args.suggest:
        detective.suggest_prefix_additions(report_file)


if __name__ == "__main__":
    main()