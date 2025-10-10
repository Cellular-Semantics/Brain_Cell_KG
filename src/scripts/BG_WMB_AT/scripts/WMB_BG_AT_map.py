import requests
import json
import pandas as pd
import argparse
from pathlib import Path


def fetch_wmb_taxonomy():
    """Fetch WMB taxonomy data from GitHub."""
    wmb = requests.get("https://github.com/brain-bican/whole_mouse_brain_taxonomy/raw/refs/heads/main/CCN20230722.json")
    wmb_json = wmb.text
    return json.loads(wmb_json)


def generate_bg2wmb_template(input_csv_path: str, output_template_path: str):
    """Generate ROBOT template from BG2WMB mapping CSV."""

    # Load WMB taxonomy data
    wmb_data = fetch_wmb_taxonomy()

    # Load input CSV
    WMB_AT = pd.read_csv(input_csv_path, sep=',').dropna(how='all')

    # Build label to accession mapping from wmb_data['annotations']
    label_to_accession = {entry['cell_label']: entry['cell_set_accession'] for entry in wmb_data['annotations']}

    # Build subclass label to accession mapping (strip leading digits/whitespace, only labelset == 'subclass')
    import re
    subclass_label_to_accession = {}
    for entry in wmb_data['annotations']:
        if entry.get('labelset') == 'subclass':
            label = entry['cell_label']
            # Strip leading digits and whitespace
            norm_label = re.sub(r'^\d+\s*', '', label)
            subclass_label_to_accession[norm_label] = entry['cell_set_accession']

    def subclass_labels_to_accessions(label_str):
        labels = [re.sub(r'^\d+\s*', '', lbl.strip()) for lbl in label_str.split('|') if lbl.strip()]
        accessions = [subclass_label_to_accession.get(lbl, '') for lbl in labels]
        accessions = [f"WMB:{acc}" if acc and not acc.startswith("WMB:") else acc for acc in accessions]
        return '|'.join([acc for acc in accessions if acc])

    def labels_to_accessions(label_str):
        labels = [lbl.strip() for lbl in label_str.split('|') if lbl.strip()]
        accessions = [label_to_accession.get(lbl, '') for lbl in labels]
        # Add WMB: prefix to each accession if not empty
        accessions = [f"WMB:{acc}" if acc and not acc.startswith("WMB:") else acc for acc in accessions]
        return '|'.join([acc for acc in accessions if acc])

    new_rows = []
    robot_template_header = {
        'Group': '',
        'Type': 'TYPE',
        'accession_group': 'ID',
        'WMB_exact_match': 'AI skos:exactMatch SPLIT=| ',
        'WMB_related_match': 'AI skos:relatedMatch SPLIT=| ',
        'WMB_broad_match': 'AI skos:broadMatch SPLIT=| '
    }

    new_rows.append(robot_template_header)

    for idx, row in WMB_AT.iterrows():
        group = row.get('Group', '')
        accession_group = row.get('accession_group', '')
        supertype_labels = str(row.get('curated_ABC_WMB_supertype', ''))
        cluster_labels = str(row.get('curated_ABC_WMB_cluster', ''))
        subclass_labels = str(row.get('curated_ABC_WMB_subclass', ''))
        supertype_accessions = labels_to_accessions(supertype_labels)
        cluster_accessions = labels_to_accessions(cluster_labels)
        subclass_accessions = subclass_labels_to_accessions(subclass_labels)

        supertype_split = [s for s in supertype_accessions.split('|') if s]
        subclass_split = [s for s in subclass_accessions.split('|') if s]

        WMB_exact_match = ''
        WMB_related_match = ''
        WMB_broad_match = ''

        # If supertype is multi and subclass is single, put subclass accession in WMB_exact_match
        if len(supertype_split) > 1 and len(subclass_split) == 1:
            WMB_exact_match = subclass_accessions
            WMB_related_match = supertype_accessions
        else:
            # Supertype mapping
            if len(supertype_split) == 1:
                WMB_exact_match = supertype_accessions
                WMB_related_match = ''
            elif len(supertype_split) > 1:
                WMB_exact_match = ''
                WMB_related_match = supertype_accessions
            else:
                WMB_exact_match = ''
                WMB_related_match = ''

        # Subclass mapping
        if len(subclass_split) > 1:
            # If both supertype and subclass multi, append subclass to relatedMatch
            if WMB_related_match:
                WMB_related_match = WMB_related_match + '|' + subclass_accessions
            else:
                WMB_related_match = subclass_accessions
            WMB_broad_match = ''
        elif len(subclass_split) == 1 and not (len(supertype_split) > 1):
            # Only put in broad_match if not already handled above
            WMB_broad_match = subclass_accessions
        else:
            WMB_broad_match = ''

        new_rows.append({
            'Group': group,
            'Type': 'owl:NamedIndividual',
            'accession_group': f"BG:{accession_group}",
            'WMB_exact_match': WMB_exact_match,
            'WMB_related_match': WMB_related_match,
            'WMB_broad_match': WMB_broad_match
        })

    new_table = pd.DataFrame(new_rows)
    print(f"Generated template with {len(new_table)-1} rows")

    new_table.to_csv(output_template_path, sep='\t', index=False)
    print(f"Saved ROBOT template to: {output_template_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate BG2WMB ROBOT template from CSV mapping')
    parser.add_argument('--input', required=True, help='Input CSV file with BG2WMB mappings')
    parser.add_argument('--output', required=True, help='Output ROBOT template TSV file')

    args = parser.parse_args()

    generate_bg2wmb_template(args.input, args.output)


if __name__ == "__main__":
    main()


