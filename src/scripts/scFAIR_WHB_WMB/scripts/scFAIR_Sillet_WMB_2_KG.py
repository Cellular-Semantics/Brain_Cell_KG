import pandas as pd
import argparse
from pathlib import Path


def generate_robot_template(input_path: str, output_path: str):
    """Generate ROBOT template from scFAIR annotation transfer mapping."""

    # Read the input annotation transfer file
    df = pd.read_csv(input_path, sep='\t')

    # Filter for rows that have both Human and Mouse accessions
    df_filtered = df.dropna(subset=['Human_cell_set_accession', 'Mouse_accession'])

    # Create ROBOT template format
    template_data = []

    # Add header row
    template_data.append({
        'ID': 'ID',
        'Type': 'TYPE',
        'skos:exactMatch': 'AI skos:exactMatch',
        'score': '>AT n2o:Confidence^^xsd:float'
    })

    # Process each mapping
    for _, row in df_filtered.iterrows():
        template_data.append({
            'ID': f"WHB:{row['Human_cell_set_accession']}",
            'Type': 'owl:NamedIndividual',
            'skos:exactMatch': f"WMB:{row['Mouse_accession']}",
            'score': row['score']
        })

    # Create DataFrame and save
    template_df = pd.DataFrame(template_data)
    template_df.to_csv(output_path, sep='\t', index=False)
    print(f"Generated ROBOT template: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate ROBOT template from scFAIR annotation transfer data')
    parser.add_argument('--input', required=True, help='Input scFAIR annotation transfer TSV file')
    parser.add_argument('--output', required=True, help='Output ROBOT template TSV file')

    args = parser.parse_args()

    generate_robot_template(args.input, args.output)


if __name__ == '__main__':
    main()
