#!/usr/bin/env python3
"""
WMB Token Report Generator - Orchestrate the complete token mapping workflow.

This script coordinates the token mapping and KG matching process to generate
comprehensive reports about WMB cell cluster token composition.
"""

import sys
from pathlib import Path
import argparse

# Import our custom modules
from wmb_token_mapper import WMBTokenMapper
from kg_token_matcher import KGTokenMatcher


def generate_complete_token_report(token_file: str, output_dir: str,
                                 neo4j_host: str = "localhost", neo4j_port: str = "7687",
                                 neo4j_user: str = "neo4j", neo4j_password: str = "neo"):
    """Generate complete token mapping and KG matching reports."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=== WMB Token Mapping and KG Matching Report Generation ===")

    # Step 1: Generate initial token mapping
    print("\n1. Parsing WMB cell cluster labels and mapping to tokens...")
    initial_mapping_file = output_path / "wmb_cell_cluster_token_mapping.csv"

    mapper = WMBTokenMapper(
        token_file, neo4j_host, neo4j_port, neo4j_user, neo4j_password
    )
    mapping_df = mapper.generate_mapping_report(str(initial_mapping_file))

    # Step 2: Match tokens to KG entities
    print("\n2. Matching tokens to knowledge graph entities...")
    final_mapping_file = output_path / "wmb_token_kg_mapping_complete.csv"

    matcher = KGTokenMatcher(neo4j_host, neo4j_port, neo4j_user, neo4j_password)
    enhanced_df = matcher.process_mapping_file(str(initial_mapping_file), str(final_mapping_file))

    # Step 3: Generate additional analysis reports
    print("\n3. Generating analysis reports...")

    # Cluster composition report
    cluster_report_file = output_path / "wmb_cluster_composition_report.csv"
    generate_cluster_composition_report(enhanced_df, str(cluster_report_file))

    # Token usage report
    token_usage_file = output_path / "wmb_token_usage_report.csv"
    generate_token_usage_report(enhanced_df, str(token_usage_file))

    # Problem tokens report
    problem_tokens_file = output_path / "wmb_problem_tokens_report.csv"
    generate_problem_tokens_report(enhanced_df, str(problem_tokens_file))

    # Step 4: Generate consolidated Excel file
    print("\n4. Generating consolidated Excel file...")
    excel_file = output_path / "wmb_token_mapping_complete.xlsx"
    generate_excel_report(output_path, str(excel_file))

    print(f"\n=== Report Generation Complete ===")
    print(f"Output directory: {output_dir}")
    print(f"Main mapping file: {final_mapping_file}")
    print(f"Excel consolidated file: {excel_file}")
    print(f"Additional reports: cluster composition, token usage, problem tokens")


def generate_cluster_composition_report(df, output_file: str):
    """Generate report showing token composition of each cluster."""
    import pandas as pd

    # Group by cluster and summarize token composition
    cluster_summary = []

    for cluster_curie, group in df.groupby('cc_curie'):
        cluster_label = group['cc_label'].iloc[0]

        # Count tokens by type
        token_counts = group['token_simplified_type'].value_counts().to_dict()

        # Count successfully matched tokens
        matched_count = len(group[group['kg_entity_found'] == True])
        total_tokens = len(group)

        summary = {
            'cluster_curie': cluster_curie,
            'cluster_label': cluster_label,
            'total_tokens': total_tokens,
            'matched_tokens': matched_count,
            'match_percentage': matched_count / total_tokens * 100 if total_tokens > 0 else 0,
            'anatomical_tokens': token_counts.get('anatomical', 0),
            'gene_tokens': token_counts.get('gene', 0),
            'cell_type_tokens': token_counts.get('cell type', 0),
            'neurotransmission_tokens': token_counts.get('neurotransmission', 0),
            'unknown_tokens': token_counts.get('unknown', 0)
        }

        cluster_summary.append(summary)

    cluster_df = pd.DataFrame(cluster_summary)
    cluster_df = cluster_df.sort_values('cluster_label')
    cluster_df.to_csv(output_file, index=False)

    print(f"Cluster composition report saved to: {output_file}")
    print(f"  Analyzed {len(cluster_df)} clusters")
    print(f"  Average tokens per cluster: {cluster_df['total_tokens'].mean():.1f}")
    print(f"  Average match rate: {cluster_df['match_percentage'].mean():.1f}%")


def generate_token_usage_report(df, output_file: str):
    """Generate report showing usage frequency of each token."""
    import pandas as pd

    # Group by token and calculate usage statistics
    token_summary = []

    for token_text, group in df.groupby('token_text'):
        token_type = group['token_simplified_type'].iloc[0]
        token_name = group['token_name'].iloc[0]
        primary_id = group['primary_identifier'].iloc[0]

        usage_count = len(group)
        cluster_count = group['cc_curie'].nunique()
        kg_found = group['kg_entity_found'].iloc[0] if not group['kg_entity_found'].isna().all() else False

        summary = {
            'token_text': token_text,
            'token_type': token_type,
            'token_name': token_name,
            'primary_identifier': primary_id,
            'usage_count': usage_count,
            'cluster_count': cluster_count,
            'kg_entity_found': kg_found,
            'kg_entity_curie': group['kg_entity_curie'].iloc[0] if kg_found else None,
            'kg_entity_label': group['kg_entity_label'].iloc[0] if kg_found else None
        }

        token_summary.append(summary)

    token_df = pd.DataFrame(token_summary)
    token_df = token_df.sort_values('usage_count', ascending=False)
    token_df.to_csv(output_file, index=False)

    print(f"Token usage report saved to: {output_file}")
    print(f"  Most used token: {token_df.iloc[0]['token_text']} (used {token_df.iloc[0]['usage_count']} times)")
    print(f"  Tokens with KG matches: {len(token_df[token_df['kg_entity_found'] == True])}/{len(token_df)}")


def generate_problem_tokens_report(df, output_file: str):
    """Generate report focusing on problematic tokens (unknown or unmatched)."""
    import pandas as pd

    # Find problematic tokens
    problem_tokens = df[
        (df['token_simplified_type'] == 'unknown') |
        (df['kg_entity_found'] == False)
    ].copy()

    if len(problem_tokens) == 0:
        print("No problem tokens found!")
        return

    # Group by token and summarize issues
    problem_summary = []

    for token_text, group in problem_tokens.groupby('token_text'):
        token_type = group['token_simplified_type'].iloc[0]
        primary_id = group['primary_identifier'].iloc[0]

        issue_type = "unknown_token" if token_type == 'unknown' else "kg_not_found"
        usage_count = len(group)
        cluster_count = group['cc_curie'].nunique()

        # Get some example clusters
        example_clusters = group['cc_label'].head(3).tolist()

        summary = {
            'token_text': token_text,
            'issue_type': issue_type,
            'token_type': token_type,
            'primary_identifier': primary_id,
            'usage_count': usage_count,
            'cluster_count': cluster_count,
            'example_clusters': ' | '.join(example_clusters)
        }

        problem_summary.append(summary)

    problem_df = pd.DataFrame(problem_summary)
    problem_df = problem_df.sort_values('usage_count', ascending=False)
    problem_df.to_csv(output_file, index=False)

    print(f"Problem tokens report saved to: {output_file}")
    print(f"  Unknown tokens: {len(problem_df[problem_df['issue_type'] == 'unknown_token'])}")
    print(f"  Unmatched KG tokens: {len(problem_df[problem_df['issue_type'] == 'kg_not_found'])}")


def generate_excel_report(reports_dir, excel_file: str):
    """Generate consolidated Excel file with all reports as separate sheets."""
    import pandas as pd
    from pathlib import Path

    reports_path = Path(reports_dir)

    # Define the reports to include and their sheet names
    report_files = {
        'Complete_Mapping': 'wmb_token_kg_mapping_complete.csv',
        'Cluster_Composition': 'wmb_cluster_composition_report.csv',
        'Token_Usage': 'wmb_token_usage_report.csv',
        'Problem_Tokens': 'wmb_problem_tokens_report.csv',
        'Matching_Summary': 'wmb_token_kg_mapping_complete_matching_summary.csv',
        'Initial_Mapping': 'wmb_cell_cluster_token_mapping.csv'
    }

    print(f"Creating Excel file with {len(report_files)} sheets...")

    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:

        for sheet_name, csv_filename in report_files.items():
            csv_path = reports_path / csv_filename

            if csv_path.exists():
                try:
                    # Read CSV and write to Excel sheet
                    df = pd.read_csv(csv_path)

                    # Truncate sheet name if too long (Excel limit is 31 characters)
                    sheet_name_truncated = sheet_name[:31] if len(sheet_name) > 31 else sheet_name

                    df.to_excel(writer, sheet_name=sheet_name_truncated, index=False)

                    # Auto-adjust column widths for better readability
                    worksheet = writer.sheets[sheet_name_truncated]
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter

                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass

                        # Set column width (with reasonable limits)
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width

                    print(f"  ✓ Added sheet '{sheet_name_truncated}' with {len(df)} rows")

                except Exception as e:
                    print(f"  ✗ Error processing {csv_filename}: {e}")
            else:
                print(f"  ⚠ Warning: {csv_filename} not found")

        # Add a summary sheet
        summary_data = {
            'Sheet_Name': list(report_files.keys()),
            'Description': [
                'Complete token-to-KG entity mapping with match results',
                'Token composition breakdown per cell cluster',
                'Token usage frequency across all clusters',
                'Problematic tokens requiring attention',
                'High-level matching success statistics',
                'Initial token parsing results before KG matching'
            ],
            'Source_File': list(report_files.values())
        }

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='README', index=False)

        # Auto-adjust columns for README sheet
        readme_sheet = writer.sheets['README']
        for column in readme_sheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 60)
            readme_sheet.column_dimensions[column_letter].width = adjusted_width

    print(f"Excel file created: {excel_file}")
    print(f"  Contains {len(report_files) + 1} sheets (including README)")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Generate comprehensive WMB token mapping reports")
    parser.add_argument("--token-file", required=True, help="Path to WMB tokens CSV file")
    parser.add_argument("--output-dir", required=True, help="Output directory for reports")
    parser.add_argument("--host", default="localhost", help="Neo4j host")
    parser.add_argument("--port", default="7687", help="Neo4j port")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo", help="Neo4j password")

    args = parser.parse_args()

    generate_complete_token_report(
        args.token_file, args.output_dir,
        args.host, args.port, args.user, args.password
    )


if __name__ == "__main__":
    main()