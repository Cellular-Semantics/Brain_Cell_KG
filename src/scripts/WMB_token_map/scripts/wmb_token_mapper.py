#!/usr/bin/env python3
"""
WMB Token Mapper - Parse WMB cell cluster labels and map tokens to knowledge graph entities.

This script implements the WMB cell cluster label grammar to parse cluster names into
component tokens and map them to entities in the knowledge graph.
"""

import pandas as pd
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add utils to path for neo4j wrapper
sys.path.append(str(Path(__file__).parents[3] / "utils"))
from neo4j_bolt_wrapper import Neo4jBoltQueryWrapper


class WMBTokenMapper:
    """Parse WMB cell cluster labels and map tokens to knowledge graph entities."""

    def __init__(self, token_mapping_file: str, neo4j_host: str = "localhost",
                 neo4j_port: str = "7687", neo4j_user: str = "neo4j", neo4j_password: str = "neo"):
        """Initialize with token mapping data and Neo4j connection."""
        self.token_df = pd.read_csv(token_mapping_file)
        self.neo4j_wrapper = Neo4jBoltQueryWrapper(
            f"bolt://{neo4j_host}:{neo4j_port}", neo4j_user, neo4j_password
        )

        # Create token lookup dictionary
        self.token_lookup = {}
        for _, row in self.token_df.iterrows():
            self.token_lookup[row['token']] = {
                'simplified_type': row['simplified_type'],
                'type': row['type'],
                'name': row['name'],
                'primary_identifier': row['primary_identifier'],
                'secondary_identifier': row.get('secondary_identifier', ''),
                'tertiary_identifier': row.get('tertiary_identifier', '')
            }

    def get_wmb_cell_clusters(self) -> List[Dict]:
        """Query knowledge graph for all WMB cell clusters."""
        query = """
        MATCH (cc:Cell_cluster:WMB)
        RETURN cc.curie as curie, cc.label as label
        ORDER BY cc.label
        """

        result = self.neo4j_wrapper.run_query(query, return_type="records")
        return result

    def parse_cluster_label(self, label: str) -> List[Dict]:
        """
        Parse a cell cluster label into component tokens according to WMB grammar.

        Grammar:
        - Number at start (mandatory)
        - 0-many anatomical tokens (capitalized, separated by -)
        - 0-many cell_type tokens (separated by space)
        - 0-many gene tokens (separated by space, start with capital)
        - 0-many neurotransmission tokens (start with capital, separated by -)
        - Optional _{number} suffix

        Returns list of token dictionaries with position and type information.
        """
        tokens = []

        # Remove leading/trailing whitespace
        label = label.strip()

        # Extract and remove leading number
        number_match = re.match(r'^(\d+)\s+', label)
        if not number_match:
            print(f"Warning: No leading number found in label: {label}")
            return tokens

        number = number_match.group(1)
        remaining = label[number_match.end():]

        # Remove optional trailing _{number} suffix
        suffix_match = re.search(r'_(\d+)$', remaining)
        suffix = None
        if suffix_match:
            suffix = suffix_match.group(1)
            remaining = remaining[:suffix_match.start()]

        # Split remaining text into potential tokens
        parts = remaining.split()
        position = 1  # Start after the number

        for part in parts:
            # Handle hyphenated tokens - but NOT genes with hyphens or neurotransmitter compounds
            if ('-' in part and
                not self._is_neurotransmitter_compound(part) and
                not self._is_gene_with_hyphen(part)):
                # Split hyphenated anatomical tokens (e.g., SI-MA-ACB)
                subparts = part.split('-')
                for subpart in subparts:
                    if subpart in self.token_lookup:
                        token_info = self.token_lookup[subpart].copy()
                        token_info.update({
                            'token_text': subpart,
                            'position': position,
                            'original_part': part
                        })
                        tokens.append(token_info)
                    else:
                        # Unknown token
                        tokens.append({
                            'token_text': subpart,
                            'position': position,
                            'original_part': part,
                            'simplified_type': 'unknown',
                            'type': 'unknown',
                            'name': f'Unknown token: {subpart}',
                            'primary_identifier': None
                        })
                    position += 1
            else:
                # Single token or neurotransmitter compound
                if part in self.token_lookup:
                    token_info = self.token_lookup[part].copy()
                    token_info.update({
                        'token_text': part,
                        'position': position,
                        'original_part': part
                    })
                    tokens.append(token_info)
                elif '-' in part and self._is_neurotransmitter_compound(part):
                    # Split neurotransmitter compounds (e.g., Gly-Gaba, Dopa-Gaba)
                    subparts = part.split('-')
                    for subpart in subparts:
                        if subpart in self.token_lookup:
                            token_info = self.token_lookup[subpart].copy()
                            token_info.update({
                                'token_text': subpart,
                                'position': position,
                                'original_part': part
                            })
                            tokens.append(token_info)
                        else:
                            # Unknown neurotransmitter subpart
                            tokens.append({
                                'token_text': subpart,
                                'position': position,
                                'original_part': part,
                                'simplified_type': 'unknown',
                                'type': 'unknown',
                                'name': f'Unknown token: {subpart}',
                                'primary_identifier': None
                            })
                        position += 1
                else:
                    # Unknown token
                    tokens.append({
                        'token_text': part,
                        'position': position,
                        'original_part': part,
                        'simplified_type': 'unknown',
                        'type': 'unknown',
                        'name': f'Unknown token: {part}',
                        'primary_identifier': None
                    })
                    position += 1

        return tokens

    def _is_neurotransmitter_compound(self, token: str) -> bool:
        """Check if a hyphenated token is a neurotransmitter compound (e.g., Gly-Gaba)."""
        # Check if the whole token exists in our lookup
        if token in self.token_lookup:
            return self.token_lookup[token]['simplified_type'] == 'neurotransmission'

        # Check if it contains known neurotransmitter patterns
        nt_patterns = ['Gaba', 'GABA', 'Gly', 'Glut', 'Dopa', 'Chol', 'Sero', 'Hist', 'Nora', 'Glyc']
        return any(pattern in token for pattern in nt_patterns)

    def _is_gene_with_hyphen(self, token: str) -> bool:
        """Check if a hyphenated token is actually a gene name (e.g., Nkx2-1)."""
        # Check if the whole token exists in our lookup as a gene
        if token in self.token_lookup:
            return self.token_lookup[token]['simplified_type'] == 'gene'

        # Check if it matches common gene naming patterns with hyphens
        # Common patterns: Nkx2-1, Nkx6-1, etc. (alphanumeric-number)
        import re
        gene_pattern = r'^[A-Z][a-z0-9]+\-[0-9]+$'
        return bool(re.match(gene_pattern, token))

    def map_all_clusters(self) -> List[Dict]:
        """Map all WMB cell clusters to their component tokens."""
        clusters = self.get_wmb_cell_clusters()
        all_mappings = []

        print(f"Processing {len(clusters)} WMB cell clusters...")

        for cluster in clusters:
            curie = cluster['curie']
            label = cluster['label']

            tokens = self.parse_cluster_label(label)

            for token in tokens:
                mapping = {
                    'cc_curie': curie,
                    'cc_label': label,
                    'token_position': token['position'],
                    'token_text': token['token_text'],
                    'token_simplified_type': token['simplified_type'],
                    'token_type': token['type'],
                    'token_name': token['name'],
                    'primary_identifier': token['primary_identifier'],
                    'secondary_identifier': token.get('secondary_identifier', ''),
                    'tertiary_identifier': token.get('tertiary_identifier', ''),
                    'original_part': token.get('original_part', token['token_text'])
                }
                all_mappings.append(mapping)

        return all_mappings

    def generate_mapping_report(self, output_file: str):
        """Generate comprehensive token mapping report."""
        mappings = self.map_all_clusters()

        # Convert to DataFrame for easy manipulation
        df = pd.DataFrame(mappings)

        # Save to CSV
        df.to_csv(output_file, index=False)

        # Print summary statistics
        print(f"\nMapping Report Generated: {output_file}")
        print(f"Total mappings: {len(df)}")
        print(f"Unique cell clusters: {df['cc_curie'].nunique()}")
        print(f"Unique tokens: {df['token_text'].nunique()}")

        print("\nToken type distribution:")
        print(df['token_simplified_type'].value_counts())

        print(f"\nUnknown tokens: {len(df[df['token_simplified_type'] == 'unknown'])}")
        if len(df[df['token_simplified_type'] == 'unknown']) > 0:
            print("Unknown tokens found:")
            unknown_tokens = df[df['token_simplified_type'] == 'unknown']['token_text'].unique()
            for token in sorted(unknown_tokens)[:10]:  # Show first 10
                print(f"  - {token}")
            if len(unknown_tokens) > 10:
                print(f"  ... and {len(unknown_tokens) - 10} more")

        return df


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Map WMB cell cluster tokens to knowledge graph entities")
    parser.add_argument("--token-file", required=True, help="Path to WMB tokens CSV file")
    parser.add_argument("--output", required=True, help="Output CSV file path")
    parser.add_argument("--host", default="localhost", help="Neo4j host")
    parser.add_argument("--port", default="7687", help="Neo4j port")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo", help="Neo4j password")

    args = parser.parse_args()

    # Create mapper and generate report
    mapper = WMBTokenMapper(
        args.token_file, args.host, args.port, args.user, args.password
    )

    mapper.generate_mapping_report(args.output)


if __name__ == "__main__":
    main()