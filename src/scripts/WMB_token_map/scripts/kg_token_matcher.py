#!/usr/bin/env python3
"""
Knowledge Graph Token Matcher - Map WMB tokens to actual entities in the knowledge graph.

This script takes token primary identifiers and attempts to find corresponding entities
in the knowledge graph based on their type (Gene, WMB anatomical, Cell types).
"""

import pandas as pd
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add utils to path for neo4j wrapper
sys.path.append(str(Path(__file__).parents[3] / "utils"))
from neo4j_bolt_wrapper import Neo4jBoltQueryWrapper


class KGTokenMatcher:
    """Match WMB tokens to knowledge graph entities."""

    def __init__(self, neo4j_host: str = "localhost", neo4j_port: str = "7687",
                 neo4j_user: str = "neo4j", neo4j_password: str = "neo"):
        """Initialize with Neo4j connection."""
        self.neo4j_wrapper = Neo4jBoltQueryWrapper(
            f"bolt://{neo4j_host}:{neo4j_port}", neo4j_user, neo4j_password
        )

    def find_gene_entity(self, primary_identifier: str) -> Optional[Dict]:
        """Find Gene entity in knowledge graph by primary identifier."""
        if not primary_identifier or pd.isna(primary_identifier):
            return None

        # Create corrected curie format (lowercase ensembl:)
        corrected_curie = primary_identifier.replace('ENSEMBL:', 'ensembl:') if primary_identifier.startswith('ENSEMBL:') else primary_identifier

        # Create short_form version by replacing ':' with '_'
        short_form = primary_identifier.replace(':', '_') if ':' in primary_identifier else None

        # Try different patterns for gene identifiers
        queries = [
            # Corrected curie match on Gene nodes (lowercase ensembl:)
            f"MATCH (g:Gene) WHERE g.curie = '{corrected_curie}' RETURN g.curie as curie, g.label as label, 'curie_match' as match_type LIMIT 1",
            # Direct curie match on Gene nodes
            f"MATCH (g:Gene) WHERE g.curie = '{primary_identifier}' RETURN g.curie as curie, g.label as label, 'curie_match' as match_type LIMIT 1",
            # ID match on Gene nodes
            f"MATCH (g:Gene) WHERE g.id = '{primary_identifier}' RETURN g.curie as curie, g.label as label, 'id_match' as match_type LIMIT 1",
            # IRI match on Gene nodes
            f"MATCH (g:Gene) WHERE g.iri = '{primary_identifier}' RETURN g.curie as curie, g.label as label, 'iri_match' as match_type LIMIT 1",
            # Short form match on Gene nodes
            f"MATCH (g:Gene) WHERE g.short_form = '{short_form}' RETURN g.curie as curie, g.label as label, 'short_form_match' as match_type LIMIT 1" if short_form else None,
            # Fallback to Class nodes with curie match
            f"MATCH (c:Class) WHERE c.curie = '{corrected_curie}' RETURN c.curie as curie, c.label as label, 'class_curie_match' as match_type LIMIT 1",
            f"MATCH (c:Class) WHERE c.curie = '{primary_identifier}' RETURN c.curie as curie, c.label as label, 'class_curie_match' as match_type LIMIT 1",
            # Fallback to Class nodes with ID match
            f"MATCH (c:Class) WHERE c.id = '{primary_identifier}' RETURN c.curie as curie, c.label as label, 'class_id_match' as match_type LIMIT 1",
            # Fallback to Class nodes with short form
            f"MATCH (c:Class) WHERE c.short_form = '{short_form}' RETURN c.curie as curie, c.label as label, 'class_short_form_match' as match_type LIMIT 1" if short_form else None,
        ]

        for query in queries:
            if query is None:  # Skip None queries from short_form conditionals
                continue
            try:
                result = self.neo4j_wrapper.run_query(query, return_type="records")
                if result and len(result) > 0:
                    return result[0]
            except Exception as e:
                continue

        # If no match found with identifiers, try symbol matching as last resort
        # Extract gene symbol from token_text (passed via context from match_token)
        if hasattr(self, '_current_token_text') and self._current_token_text:
            symbol_query = f"MATCH (g:Gene) WHERE g.label CONTAINS '{self._current_token_text}' RETURN g.curie as curie, g.label as label, 'symbol_match' as match_type LIMIT 1"
            try:
                result = self.neo4j_wrapper.run_query(symbol_query, return_type="records")
                if result and len(result) > 0:
                    return result[0]
            except Exception as e:
                pass

        return None

    def find_anatomical_entity(self, primary_identifier: str) -> Optional[Dict]:
        """Find MBA anatomical entity in knowledge graph by primary identifier."""
        if not primary_identifier or pd.isna(primary_identifier):
            return None

        # Create short_form version by replacing ':' with '_'
        short_form = primary_identifier.replace(':', '_') if ':' in primary_identifier else None

        # Try different patterns for anatomical identifiers
        queries = [
            # Direct curie match on MBA nodes
            f"MATCH (w:MBA) WHERE w.curie = '{primary_identifier}' RETURN w.curie as curie, w.label as label LIMIT 1",
            # ID match on MBA nodes
            f"MATCH (w:MBA) WHERE w.id = '{primary_identifier}' RETURN w.curie as curie, w.label as label LIMIT 1",
            # Short form match on MBA nodes
            f"MATCH (w:MBA) WHERE w.short_form = '{short_form}' RETURN w.curie as curie, w.label as label LIMIT 1" if short_form else None,
            # Fallback to Class nodes with curie match
            f"MATCH (c:Class) WHERE c.curie = '{primary_identifier}' RETURN c.curie as curie, c.label as label LIMIT 1",
            # Fallback to Class nodes with ID match
            f"MATCH (c:Class) WHERE c.id = '{primary_identifier}' RETURN c.curie as curie, c.label as label LIMIT 1",
            # Fallback to Class nodes with short form
            f"MATCH (c:Class) WHERE c.short_form = '{short_form}' RETURN c.curie as curie, c.label as label LIMIT 1" if short_form else None,
        ]

        for query in queries:
            if query is None:  # Skip None queries from short_form conditionals
                continue
            try:
                result = self.neo4j_wrapper.run_query(query, return_type="records")
                if result and len(result) > 0:
                    return result[0]
            except Exception as e:
                continue

        return None

    def find_cell_entity(self, primary_identifier: str) -> Optional[Dict]:
        """Find Cell entity in knowledge graph by primary identifier."""
        if not primary_identifier or pd.isna(primary_identifier):
            return None

        # Create short_form version by replacing ':' with '_'
        short_form = primary_identifier.replace(':', '_') if ':' in primary_identifier else None

        # Try different patterns for cell type identifiers
        queries = [
            # Direct curie match on Cell nodes
            f"MATCH (c:Cell) WHERE c.curie = '{primary_identifier}' RETURN c.curie as curie, c.label as label LIMIT 1",
            # ID match on Cell nodes
            f"MATCH (c:Cell) WHERE c.id = '{primary_identifier}' RETURN c.curie as curie, c.label as label LIMIT 1",
            # IRI match on Cell nodes
            f"MATCH (c:Cell) WHERE c.iri = '{primary_identifier}' RETURN c.curie as curie, c.label as label LIMIT 1",
            # Short form match on Cell nodes
            f"MATCH (c:Cell) WHERE c.short_form = '{short_form}' RETURN c.curie as curie, c.label as label LIMIT 1" if short_form else None,
            # Fallback to Class nodes with curie match
            f"MATCH (cl:Class) WHERE cl.curie = '{primary_identifier}' RETURN cl.curie as curie, cl.label as label LIMIT 1",
            # Fallback to Class nodes with ID match
            f"MATCH (cl:Class) WHERE cl.id = '{primary_identifier}' RETURN cl.curie as curie, cl.label as label LIMIT 1",
            # Fallback to Class nodes with short form
            f"MATCH (cl:Class) WHERE cl.short_form = '{short_form}' RETURN cl.curie as curie, cl.label as label LIMIT 1" if short_form else None,
        ]

        for query in queries:
            if query is None:  # Skip None queries from short_form conditionals
                continue
            try:
                result = self.neo4j_wrapper.run_query(query, return_type="records")
                if result and len(result) > 0:
                    return result[0]
            except Exception as e:
                continue

        return None

    def match_token(self, token_info: Dict) -> Dict:
        """Match a single token to knowledge graph entity based on its type."""
        simplified_type = token_info.get('token_simplified_type', '')
        primary_identifier = token_info.get('primary_identifier', '')
        token_text = token_info.get('token_text', '')

        # Initialize result
        match_result = {
            'kg_entity_found': False,
            'kg_entity_curie': None,
            'kg_entity_label': None,
            'match_method': None
        }

        if simplified_type == 'unknown' or not primary_identifier:
            return match_result

        # Match based on simplified type
        entity = None
        if simplified_type == 'gene':
            # Pass token text for potential symbol matching
            self._current_token_text = token_text
            entity = self.find_gene_entity(primary_identifier)
            match_result['match_method'] = 'gene_lookup'
            # Add match type info if available
            if entity and 'match_type' in entity:
                match_result['match_method'] = f"gene_{entity['match_type']}"
        elif simplified_type == 'anatomical':
            entity = self.find_anatomical_entity(primary_identifier)
            match_result['match_method'] = 'anatomical_lookup'
        elif simplified_type in ['cell type', 'neurotransmission']:
            entity = self.find_cell_entity(primary_identifier)
            match_result['match_method'] = 'cell_lookup'

        if entity:
            match_result.update({
                'kg_entity_found': True,
                'kg_entity_curie': entity.get('curie'),
                'kg_entity_label': entity.get('label')
            })

        return match_result

    def process_mapping_file(self, mapping_file: str, output_file: str):
        """Process a token mapping file and add KG entity matching results."""
        # Load the mapping file
        df = pd.read_csv(mapping_file)

        print(f"Processing {len(df)} token mappings...")

        # Add new columns for KG matching results
        kg_columns = ['kg_entity_found', 'kg_entity_curie', 'kg_entity_label', 'match_method']
        for col in kg_columns:
            df[col] = None

        # Process each unique token to avoid redundant queries
        unique_tokens = df.drop_duplicates(subset=['token_text', 'token_simplified_type', 'primary_identifier'])

        print(f"Matching {len(unique_tokens)} unique tokens to KG entities...")

        # Create a lookup dictionary for matched tokens
        token_matches = {}

        for idx, row in unique_tokens.iterrows():
            token_key = (row['token_text'], row['token_simplified_type'], row['primary_identifier'])

            match_result = self.match_token(row.to_dict())
            token_matches[token_key] = match_result

            # Progress reporting
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{len(unique_tokens)} unique tokens...")

        # Apply matches back to full dataframe
        for idx, row in df.iterrows():
            token_key = (row['token_text'], row['token_simplified_type'], row['primary_identifier'])
            if token_key in token_matches:
                match_result = token_matches[token_key]
                for col in kg_columns:
                    df.at[idx, col] = match_result[col]

        # Save enhanced dataframe
        df.to_csv(output_file, index=False)

        # Generate matching report
        self._generate_matching_report(df, output_file)

        return df

    def _generate_matching_report(self, df: pd.DataFrame, output_file: str):
        """Generate and print matching statistics report."""
        print(f"\nKG Matching Report Generated: {output_file}")
        print(f"Total token mappings: {len(df)}")

        # Overall matching stats
        found_count = len(df[df['kg_entity_found'] == True])
        total_count = len(df[df['token_simplified_type'] != 'unknown'])

        print(f"Successfully matched to KG: {found_count}/{total_count} ({found_count/total_count*100:.1f}%)")

        # Matching by token type
        print("\nMatching success by token type:")
        for token_type in df['token_simplified_type'].unique():
            if token_type == 'unknown':
                continue

            type_df = df[df['token_simplified_type'] == token_type]
            type_found = len(type_df[type_df['kg_entity_found'] == True])
            type_total = len(type_df)

            print(f"  {token_type}: {type_found}/{type_total} ({type_found/type_total*100:.1f}%)")

        # Show some unmatched tokens
        unmatched = df[(df['kg_entity_found'] == False) & (df['token_simplified_type'] != 'unknown')]
        if len(unmatched) > 0:
            print(f"\nSample unmatched tokens (showing first 10):")
            unmatched_sample = unmatched[['token_text', 'token_simplified_type', 'primary_identifier']].drop_duplicates().head(10)
            for _, row in unmatched_sample.iterrows():
                print(f"  {row['token_text']} ({row['token_simplified_type']}): {row['primary_identifier']}")

        # Generate separate matching summary file
        summary_file = output_file.replace('.csv', '_matching_summary.csv')
        summary_data = []

        for token_type in df['token_simplified_type'].unique():
            type_df = df[df['token_simplified_type'] == token_type]
            type_found = len(type_df[type_df['kg_entity_found'] == True])
            type_total = len(type_df)
            unique_tokens = type_df['token_text'].nunique()

            summary_data.append({
                'token_type': token_type,
                'total_mappings': type_total,
                'successful_matches': type_found,
                'match_percentage': type_found/type_total*100 if type_total > 0 else 0,
                'unique_tokens': unique_tokens
            })

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv(summary_file, index=False)
        print(f"Matching summary saved to: {summary_file}")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Match WMB tokens to knowledge graph entities")
    parser.add_argument("--mapping-file", required=True, help="Path to token mapping CSV file")
    parser.add_argument("--output", required=True, help="Output CSV file path")
    parser.add_argument("--host", default="localhost", help="Neo4j host")
    parser.add_argument("--port", default="7687", help="Neo4j port")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo", help="Neo4j password")

    args = parser.parse_args()

    # Create matcher and process file
    matcher = KGTokenMatcher(args.host, args.port, args.user, args.password)
    matcher.process_mapping_file(args.mapping_file, args.output)


if __name__ == "__main__":
    main()