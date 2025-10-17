#!/usr/bin/env python3
"""
Generate additional WMB reports per Claude.md specification:
1. Most general terms report for anatomical & gene mappings
2. Neurotransmission consistency report
"""

import pandas as pd
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add utils to path for neo4j wrapper
sys.path.append(str(Path(__file__).parents[3] / "utils"))
from neo4j_bolt_wrapper import Neo4jBoltQueryWrapper


class WMBAdditionalReports:
    """Generate additional reports for WMB token mapping analysis."""

    def __init__(self, neo4j_host: str = "localhost", neo4j_port: str = "7687",
                 neo4j_user: str = "neo4j", neo4j_password: str = "neo"):
        """Initialize with Neo4j connection."""
        self.neo4j_wrapper = Neo4jBoltQueryWrapper(
            f"bolt://{neo4j_host}:{neo4j_port}", neo4j_user, neo4j_password
        )

    def generate_most_general_terms_report(self, output_dir: str) -> str:
        """
        Generate report of most general terms in WMB with anatomical & gene mappings.

        For each anatomical and gene mapping, find the most general term in WMB taxonomy
        with that mapping. Use labelset hierarchy and subcluster_of relationships.
        """
        print("Generating most general terms report...")

        # Load existing mappings first
        print("Loading existing token mappings...")
        import pandas as pd
        mappings_file = f"{output_dir}/wmb_token_kg_mapping_complete.csv"
        try:
            mappings_df = pd.read_csv(mappings_file)
        except FileNotFoundError:
            print(f"Error: Could not find {mappings_file}")
            print("Please run the main token mapping script first.")
            return ""

        # Get unique anatomical and gene entities from successful mappings
        anatomical_entities = mappings_df[
            (mappings_df['token_simplified_type'] == 'anatomical') &
            (mappings_df['kg_entity_found'] == True)
        ][['kg_entity_curie', 'kg_entity_label']].drop_duplicates()

        gene_entities = mappings_df[
            (mappings_df['token_simplified_type'] == 'gene') &
            (mappings_df['kg_entity_found'] == True)
        ][['kg_entity_curie', 'kg_entity_label']].drop_duplicates()

        print(f"Found {len(anatomical_entities)} unique anatomical entities to analyze")
        print(f"Found {len(gene_entities)} unique gene entities to analyze")

        # Efficient top-down approach: Start from :class level and traverse down
        anatomical_query = """
        // Find all :class level terms
        MATCH (top_class:Cell_cluster:WMB:class)

        // For each anatomical entity, find the most general term with that mapping
        WITH $anatomical_entities as entities, top_class
        UNWIND entities as entity

        // Traverse down from each class, looking for clusters with this anatomical mapping
        MATCH path = (top_class)<-[:subcluster_of*0..10]-(descendant:Cell_cluster:WMB)
        WHERE EXISTS {
            MATCH (descendant_cluster:Cell_cluster:WMB {curie: descendant.curie})
            MATCH (mapping_row) WHERE mapping_row.cc_curie = descendant_cluster.curie
                AND mapping_row.kg_entity_curie = entity.kg_entity_curie
                AND mapping_row.token_simplified_type = 'anatomical'
                AND mapping_row.kg_entity_found = true
        }

        // Find the shortest path (most general term in this branch with the mapping)
        WITH entity, top_class, path, descendant, length(path) as path_length
        ORDER BY path_length
        WITH entity, top_class, collect(descendant)[0] as most_general_with_mapping

        // Get exemplar cell data
        MATCH (most_general_with_mapping)<-[:has_exemplar_data]-(c:Cell)

        RETURN top_class.curie as class_curie,
               top_class.label as class_label,
               most_general_with_mapping.curie as cluster_curie,
               most_general_with_mapping.label as cluster_label,
               labels(most_general_with_mapping) as labelset,
               c.curie as cell_curie,
               c.label as cell_label,
               entity.kg_entity_curie as mapping_curie,
               entity.kg_entity_label as mapping_label,
               'anatomical' as mapping_type
        """

        # Alternative simpler approach - use the mapping data directly
        simplified_anatomical_query = """
        // Get all anatomical mappings and find their class-level ancestors
        WITH $mappings_data as all_mappings

        // Filter for anatomical mappings and get unique entity mappings per class branch
        UNWIND [mapping IN all_mappings WHERE mapping.token_simplified_type = 'anatomical'
                AND mapping.kg_entity_found = 'True'] as mapping

        MATCH (cluster:Cell_cluster:WMB {curie: mapping.cc_curie})
        MATCH (cluster)-[:subcluster_of*0..10]->(ancestor:Cell_cluster:WMB:class)

        // For each anatomical entity and class branch, find the most general term with that mapping
        WITH mapping.kg_entity_curie as entity_curie, mapping.kg_entity_label as entity_label,
             ancestor as class_ancestor, cluster, mapping,
             ancestor.curie as class_curie, ancestor.label as class_label

        // Find all clusters in this class branch with this entity mapping
        MATCH (class_ancestor)<-[:subcluster_of*0..10]-(branch_cluster:Cell_cluster:WMB)
        MATCH (branch_mapping_row) WHERE branch_mapping_row.cc_curie = branch_cluster.curie
                AND branch_mapping_row.kg_entity_curie = entity_curie
                AND branch_mapping_row.token_simplified_type = 'anatomical'
                AND branch_mapping_row.kg_entity_found = 'True'

        // Find the shortest path from class to cluster with this mapping
        MATCH path = (class_ancestor)<-[:subcluster_of*0..10]-(branch_cluster)
        WITH entity_curie, entity_label, class_curie, class_label,
             branch_cluster, length(path) as path_length
        ORDER BY path_length
        WITH entity_curie, entity_label, class_curie, class_label,
             collect(branch_cluster)[0] as most_general_with_mapping

        // Get exemplar cell data
        MATCH (most_general_with_mapping)<-[:has_exemplar_data]-(c:Cell)

        RETURN class_curie, class_label,
               most_general_with_mapping.curie as cluster_curie,
               most_general_with_mapping.label as cluster_label,
               labels(most_general_with_mapping) as labelset,
               c.curie as cell_curie, c.label as cell_label,
               entity_curie as mapping_curie, entity_label as mapping_label,
               'anatomical' as mapping_type
        """

        # Use direct approach with mapping data
        mappings_data = mappings_df.to_dict('records')

        # Step 1: Get all :class level terms
        class_query = "MATCH (c:Cell_cluster:WMB:class) RETURN c.curie as class_curie, c.label as class_label"
        class_results = self.neo4j_wrapper.run_query(class_query, return_type="records")
        print(f"Found {len(class_results)} class-level terms")

        anatomical_results = []
        gene_results = []

        # Step 2: For each anatomical entity, find the first occurrence in each class branch
        unique_anatomical = anatomical_entities['kg_entity_curie'].unique()
        print(f"Processing {len(unique_anatomical)} anatomical entities...")

        for entity_curie in unique_anatomical:
            entity_label = anatomical_entities[anatomical_entities['kg_entity_curie'] == entity_curie]['kg_entity_label'].iloc[0]

            # Get all clusters with this anatomical mapping
            clusters_with_mapping = mappings_df[
                (mappings_df['kg_entity_curie'] == entity_curie) &
                (mappings_df['token_simplified_type'] == 'anatomical') &
                (mappings_df['kg_entity_found'] == True)
            ]['cc_curie'].tolist()

            if not clusters_with_mapping:
                continue

            # For each class, find the most general cluster in that branch with this mapping
            for class_info in class_results:
                class_curie = class_info['class_curie']
                class_label = class_info['class_label']

                # Find the shortest path from class to any cluster with this mapping
                path_query = f"""
                MATCH (class_node:Cell_cluster:WMB {{curie: '{class_curie}'}})
                MATCH path = (class_node)<-[:subcluster_of*0..10]-(descendant:Cell_cluster:WMB)
                WHERE descendant.curie IN {clusters_with_mapping}
                WITH path, descendant, length(path) as path_length
                ORDER BY path_length
                LIMIT 1
                MATCH (descendant)<-[:has_exemplar_data]-(c:Cell)
                RETURN descendant.curie as cluster_curie, descendant.label as cluster_label,
                       labels(descendant) as labelset, c.curie as cell_curie, c.label as cell_label
                """

                path_results = self.neo4j_wrapper.run_query(path_query, return_type="records")
                for result in path_results:
                    anatomical_results.append({
                        'class_curie': class_curie,
                        'class_label': class_label,
                        'cluster_curie': result['cluster_curie'],
                        'cluster_label': result['cluster_label'],
                        'labelset': str(result['labelset']),
                        'cell_curie': result['cell_curie'],
                        'cell_label': result['cell_label'],
                        'mapping_curie': entity_curie,
                        'mapping_label': entity_label,
                        'mapping_type': 'anatomical'
                    })

        print(f"Found {len(anatomical_results)} anatomical results")

        # Step 3: Same for gene entities
        unique_genes = gene_entities['kg_entity_curie'].unique()
        print(f"Processing {len(unique_genes)} gene entities...")

        for entity_curie in unique_genes:
            entity_label = gene_entities[gene_entities['kg_entity_curie'] == entity_curie]['kg_entity_label'].iloc[0]

            clusters_with_mapping = mappings_df[
                (mappings_df['kg_entity_curie'] == entity_curie) &
                (mappings_df['token_simplified_type'] == 'gene') &
                (mappings_df['kg_entity_found'] == True)
            ]['cc_curie'].tolist()

            if not clusters_with_mapping:
                continue

            for class_info in class_results:
                class_curie = class_info['class_curie']
                class_label = class_info['class_label']

                path_query = f"""
                MATCH (class_node:Cell_cluster:WMB {{curie: '{class_curie}'}})
                MATCH path = (class_node)<-[:subcluster_of*0..10]-(descendant:Cell_cluster:WMB)
                WHERE descendant.curie IN {clusters_with_mapping}
                WITH path, descendant, length(path) as path_length
                ORDER BY path_length
                LIMIT 1
                MATCH (descendant)<-[:has_exemplar_data]-(c:Cell)
                RETURN descendant.curie as cluster_curie, descendant.label as cluster_label,
                       labels(descendant) as labelset, c.curie as cell_curie, c.label as cell_label
                """

                path_results = self.neo4j_wrapper.run_query(path_query, return_type="records")
                for result in path_results:
                    gene_results.append({
                        'class_curie': class_curie,
                        'class_label': class_label,
                        'cluster_curie': result['cluster_curie'],
                        'cluster_label': result['cluster_label'],
                        'labelset': str(result['labelset']),
                        'cell_curie': result['cell_curie'],
                        'cell_label': result['cell_label'],
                        'mapping_curie': entity_curie,
                        'mapping_label': entity_label,
                        'mapping_type': 'gene'
                    })

        print(f"Found {len(gene_results)} gene results")

        # Combine results
        all_results = anatomical_results + gene_results

        # Create DataFrame and save
        df = pd.DataFrame(all_results)
        output_file = f"{output_dir}/wmb_most_general_terms_report.csv"
        df.to_csv(output_file, index=False)

        print(f"Most general terms report saved: {output_file}")
        print(f"Found {len(anatomical_results)} anatomical mappings and {len(gene_results)} gene mappings")

        return output_file

    def generate_neurotransmission_consistency_report(self, output_dir: str) -> str:
        """
        Generate report of neurotransmission consistency across taxonomy levels.

        For each :class, :subclass, or :supertype node, determine if ALL clusters
        under it have the same neurotransmission pattern.
        """
        print("Generating neurotransmission consistency report...")

        # Get all hierarchy relationships and NT data in one efficient query
        # Use limited depth to avoid performance issues
        print("  Fetching all hierarchy and NT data...")
        data_query = """
        MATCH (parent:Cell_cluster:WMB)
        WHERE parent:class OR parent:subclass OR parent:supertype
        MATCH (parent)<-[:subcluster_of*1..3]-(child:Cell_cluster:WMB:cluster)
        WHERE child.nt_type_combo_label IS NOT NULL
        RETURN parent.curie as parent_curie,
               parent.label as parent_label,
               labels(parent) as parent_labelset,
               child.curie as child_curie,
               child.nt_type_combo_label[0] as nt_combo
        """

        raw_data = self.neo4j_wrapper.run_query(data_query, return_type="records")
        print(f"  Retrieved {len(raw_data)} parent-child NT relationships")

        # Group data by parent
        parent_data = {}
        for record in raw_data:
            parent_curie = record['parent_curie']
            if parent_curie not in parent_data:
                parent_data[parent_curie] = {
                    'parent_label': record['parent_label'],
                    'parent_labelset': record['parent_labelset'],
                    'children': []
                }
            parent_data[parent_curie]['children'].append({
                'child_curie': record['child_curie'],
                'nt_combo': record['nt_combo']
            })

        # Process each parent to find NT consistency
        all_results = []
        for parent_curie, data in parent_data.items():
            if len(data['children']) <= 1:
                continue  # Skip nodes with 0 or 1 child

            # Extract NT patterns
            combo_patterns = [child['nt_combo'] for child in data['children']]
            total_clusters = len(combo_patterns)

            # Count occurrences of each individual NT
            nt_counts = {}
            for combo in combo_patterns:
                individual_nts = combo.split('-')
                for nt in individual_nts:
                    nt_counts[nt] = nt_counts.get(nt, 0) + 1

            # Find universal NTs (present in ALL clusters)
            consistent_nts = [nt for nt, count in nt_counts.items() if count == total_clusters]

            all_results.append({
                'parent_curie': parent_curie,
                'parent_label': data['parent_label'],
                'parent_labelset': str(data['parent_labelset']),
                'cluster_count': total_clusters,
                'is_consistent': len(consistent_nts) > 0,
                'consistent_nts': consistent_nts,
                'nt_patterns': list(set(combo_patterns)),
                'pattern_variety': len(set(combo_patterns))
            })

        results = all_results

        # Process results
        processed_results = []
        for result in results:
            # Handle neurotransmitter patterns
            nt_patterns = result.get('nt_patterns', [])
            consistent_nts = result.get('consistent_nts', [])

            # Convert arrays to strings for CSV output
            if isinstance(consistent_nts, list):
                consistent_nts_str = '|'.join(consistent_nts)
            else:
                consistent_nts_str = str(consistent_nts) if consistent_nts else ''

            # Convert nt_patterns to strings if needed
            if nt_patterns and isinstance(nt_patterns[0], list):
                nt_patterns_str = [str(p) for p in nt_patterns]
            else:
                nt_patterns_str = [str(p) for p in nt_patterns] if nt_patterns else []

            processed_results.append({
                'parent_curie': result.get('parent_curie'),
                'parent_label': result.get('parent_label'),
                'parent_labelset': str(result.get('parent_labelset')),
                'cluster_count': result.get('cluster_count'),
                'is_consistent': result.get('is_consistent'),
                'consistent_neurotransmitters': consistent_nts_str,
                'pattern_variety': result.get('pattern_variety'),
                'all_patterns': '|'.join(nt_patterns_str) if nt_patterns_str else ''
            })

        # Create DataFrame and save
        df = pd.DataFrame(processed_results)
        output_file = f"{output_dir}/wmb_neurotransmission_consistency_report.csv"
        df.to_csv(output_file, index=False)

        # Generate summary stats
        if 'is_consistent' in df.columns:
            consistent_count = len(df[df['is_consistent'] == True])
        else:
            consistent_count = 0
        total_count = len(df)

        print(f"Neurotransmission consistency report saved: {output_file}")
        print(f"Found {consistent_count}/{total_count} nodes with consistent neurotransmission patterns")
        if 'cluster_count' in df.columns and len(df) > 0:
            print(f"Analyzed {df['cluster_count'].sum()} total clusters across {total_count} parent nodes")
        else:
            print(f"No neurotransmission data found to analyze")

        return output_file

    def generate_all_additional_reports(self, output_dir: str):
        """Generate all additional reports."""
        print("=== Generating Additional WMB Reports ===")

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Generate reports
        general_terms_file = self.generate_most_general_terms_report(output_dir)
        consistency_file = self.generate_neurotransmission_consistency_report(output_dir)

        print(f"\n=== Additional Reports Complete ===")
        print(f"Reports saved to: {output_dir}")
        print(f"- Most general terms: {general_terms_file}")
        print(f"- Neurotransmission consistency: {consistency_file}")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate additional WMB reports")
    parser.add_argument("--output-dir", default="../reports", help="Output directory for reports")
    parser.add_argument("--host", default="localhost", help="Neo4j host")
    parser.add_argument("--port", default="7687", help="Neo4j port")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo", help="Neo4j password")

    args = parser.parse_args()

    # Create reporter and generate reports
    reporter = WMBAdditionalReports(args.host, args.port, args.user, args.password)
    reporter.generate_all_additional_reports(args.output_dir)


if __name__ == "__main__":
    main()