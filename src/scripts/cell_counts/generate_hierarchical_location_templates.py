#!/usr/bin/env python3
"""
Hierarchical Location Mapping Script

Generates ROBOT templates for cell type location mappings using hierarchical strategy:
1. Apply 5% cutoff at each granularity level (substructure -> structure -> division)
2. Handle {term}-unassigned by mapping to parent term
3. Use hierarchical fallback if no locations meet cutoff at finer levels
4. Output ROBOT templates with proper CURIEs

Usage:
python generate_hierarchical_location_templates.py --input-dir <proportion_reports_dir> --output-dir <templates_dir>
"""

import argparse
import json
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
import re

class HierarchicalLocationMapper:
    def __init__(self, cell_count_matrices_dir: str, output_dir: str,
                 cutoff: float = 0.05, source_doi: str = None,
                 output_suffix: str = ""):
        self.cell_count_matrices_dir = Path(cell_count_matrices_dir)
        self.output_dir = Path(output_dir)
        self.cutoff = cutoff
        self.source_doi = source_doi
        self.output_suffix = output_suffix

        # Load metadata to understand data structure
        metadata_file = self.cell_count_matrices_dir / "matrix_metadata.json"
        with open(metadata_file, 'r') as f:
            self.metadata = json.load(f)

        # Map taxonomy levels and region levels
        self.taxonomy_levels = ['cluster', 'supertype', 'subclass', 'class', 'neurotransmitter']
        self.region_levels = ['substructure', 'structure', 'division']

        # Load cell set and MBA mappings
        self.cell_set_mappings = self._load_cell_set_mappings()
        self.mba_mappings = self._load_mba_mappings()

        print(f"Initialized HierarchicalLocationMapper:")
        print(f"  Input dir: {self.cell_count_matrices_dir}")
        print(f"  Output dir: {self.output_dir}")
        print(f"  Cutoff: {self.cutoff}")
        print(f"  Source DOI: {self.source_doi or '(none)'}")
        print(f"  Output suffix: {self.output_suffix or '(none)'}")
        print(f"  Found {len(self.metadata)} cell count matrix files")
        print(f"  Loaded {len(self.cell_set_mappings)} cell set mappings")
        print(f"  Loaded {len(self.mba_mappings)} MBA mappings")

    def _load_cell_set_mappings(self) -> Dict[str, str]:
        """Load cell set label to CURIE mappings from reports/cell_set_map.csv"""
        mappings = {}
        cell_set_map_file = Path("reports/cell_set_map.csv")

        if cell_set_map_file.exists():
            df = pd.read_csv(cell_set_map_file)
            # Filter for WMB taxonomy
            wmb_df = df[df['dataset'] == 'Whole Mouse Brain Taxonomy']
            for _, row in wmb_df.iterrows():
                label = row['label']
                curie = row['curie']
                if pd.notna(label) and pd.notna(curie):
                    mappings[label] = curie
        else:
            print(f"Warning: {cell_set_map_file} not found")

        return mappings

    def _load_mba_mappings(self) -> Dict[str, str]:
        """Load MBA symbol to CURIE mappings from reports/mba_symbol_map.csv"""
        mappings = {}
        mba_map_file = Path("reports/mba_symbol_map.csv")

        if mba_map_file.exists():
            df = pd.read_csv(mba_map_file)
            for _, row in df.iterrows():
                symbol = row['symbol']
                curie = row['curie']
                if pd.notna(symbol) and pd.notna(curie):
                    mappings[symbol] = curie
        else:
            print(f"Warning: {mba_map_file} not found")

        return mappings

    def load_cell_count_data(self, taxonomy_level: str) -> Dict[str, pd.DataFrame]:
        """Load cell count data for all region levels for given taxonomy level"""
        data = {}

        # Map region levels to file naming convention
        region_level_mapping = {
            'substructure': 'substructure',
            'structure': 'structure',
            'division': 'division'
        }

        for region_level in self.region_levels:
            filename = f"{taxonomy_level}_by_{region_level_mapping[region_level]}.csv"
            filepath = self.cell_count_matrices_dir / filename

            if filepath.exists():
                df = pd.read_csv(filepath, index_col=0)
                data[region_level] = df
                print(f"Loaded {df.shape[0]} cell sets x {df.shape[1]} regions from {filename}")
            else:
                print(f"Warning: {filename} not found")

        return data

    def apply_cutoff_and_hierarchy(self, data: Dict[str, pd.DataFrame], cell_set: str) -> List[Tuple[str, int, float, str]]:
        """Apply hierarchical cutoff logic for a single cell set"""
        mappings = []

        # Try each region level in order of specificity
        for region_level in self.region_levels:
            if region_level not in data:
                continue

            df = data[region_level]
            if cell_set not in df.index:
                continue

            row = df.loc[cell_set]

            # Calculate total cell count for this cell set to get proportions
            total_cells = row.sum()
            if total_cells == 0:
                continue

            # Calculate proportions and find regions above cutoff
            proportions = row / total_cells
            above_cutoff_mask = proportions >= self.cutoff
            above_cutoff_regions = row[above_cutoff_mask]

            if len(above_cutoff_regions) > 0:
                # Found mappings at this level
                for region, cell_count in above_cutoff_regions.items():
                    if cell_count == 0:
                        continue

                    proportion = cell_count / total_cells

                    # Fold any '<X>-unassigned' substructures back to the
                    # parent region <X> (e.g. 'HY-unassigned' -> 'HY').
                    # The parent acronym is expected to be in mba_symbol_map.
                    mapped_region = region.removesuffix('-unassigned')
                    mappings.append((mapped_region, int(cell_count), proportion, region_level))

                # Stop here - found mappings at this level
                break

        return mappings

    def generate_robot_template(self, taxonomy_level: str, mappings: Dict[str, List[Tuple[str, float, str]]]) -> str:
        """Generate ROBOT template content for location mappings"""

        # Template header. If source_doi is set, add a third axiom annotation
        # (dcterms:source) carrying the publication DOI on every edge.
        # Use >AI so the DOI CURIE is resolved to an IRI rather than stored
        # as a literal string.
        if self.source_doi:
            template_lines = [
                "ID\tType\tPCL:0010063\tcell_count\tcell_ratio\tsource",
                "ID\tTYPE\tAI PCL:0010063\t>AT PCL:0010060^^xsd:integer\t>AT PCL:0010065^^xsd:float\t>AI dcterms:source",
            ]
        else:
            template_lines = [
                "ID\tType\tPCL:0010063\tcell_count\tcell_ratio",
                "ID\tTYPE\tAI PCL:0010063\t>AT PCL:0010060^^xsd:integer\t>AT PCL:0010065^^xsd:float",
            ]

        # Generate data rows
        for cell_set, location_mappings in mappings.items():
            # Look up proper cell set CURIE
            if cell_set in self.cell_set_mappings:
                cell_set_curie = self.cell_set_mappings[cell_set]
            else:
                print(f"Warning: No CURIE found for cell set '{cell_set}', skipping")
                continue

            for region, cell_count, proportion, region_level in location_mappings:
                # Look up proper MBA region CURIE
                if region in self.mba_mappings:
                    region_curie = self.mba_mappings[region]
                else:
                    print(f"Warning: No CURIE found for region '{region}', skipping")
                    continue

                # Use actual cell count and proportion
                cell_ratio = f"{proportion:.6f}"

                row = f"{cell_set_curie}\towl:NamedIndividual\t{region_curie}\t{cell_count}\t{cell_ratio}"
                if self.source_doi:
                    row += f"\t{self.source_doi}"
                template_lines.append(row)

        return "\n".join(template_lines)

    def process_taxonomy_level(self, taxonomy_level: str):
        """Process all cell sets for a given taxonomy level"""
        print(f"\\nProcessing taxonomy level: {taxonomy_level}")

        # Load cell count data for all region levels
        data = self.load_cell_count_data(taxonomy_level)

        if not data:
            print(f"No data found for {taxonomy_level}")
            return

        # Get all cell sets (from finest level data available)
        region_level = next(iter(data.keys()))
        cell_sets = data[region_level].index.tolist()

        print(f"Processing {len(cell_sets)} cell sets...")

        # Process each cell set
        all_mappings = {}
        stats = {'total_cell_sets': len(cell_sets), 'mapped_cell_sets': 0, 'total_mappings': 0}

        for i, cell_set in enumerate(cell_sets):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(cell_sets)} cell sets")

            mappings = self.apply_cutoff_and_hierarchy(data, cell_set)

            if mappings:
                all_mappings[cell_set] = mappings
                stats['mapped_cell_sets'] += 1
                stats['total_mappings'] += len(mappings)

        print(f"\\nMapping statistics for {taxonomy_level}:")
        print(f"  Total cell sets: {stats['total_cell_sets']}")
        print(f"  Mapped cell sets: {stats['mapped_cell_sets']} ({stats['mapped_cell_sets']/stats['total_cell_sets']*100:.1f}%)")
        print(f"  Total mappings: {stats['total_mappings']}")
        print(f"  Avg mappings per mapped cell set: {stats['total_mappings']/max(stats['mapped_cell_sets'], 1):.1f}")

        # Generate ROBOT template
        if all_mappings:
            template_content = self.generate_robot_template(taxonomy_level, all_mappings)

            # Write template file
            output_file = self.output_dir / f"{taxonomy_level}_location_mappings{self.output_suffix}.tsv"
            os.makedirs(self.output_dir, exist_ok=True)

            with open(output_file, 'w') as f:
                f.write(template_content)

            print(f"Generated ROBOT template: {output_file}")
        else:
            print(f"No mappings generated for {taxonomy_level}")

    def run(self, taxonomy_levels: List[str] = None):
        """Run hierarchical mapping for specified taxonomy levels"""
        if taxonomy_levels is None:
            taxonomy_levels = self.taxonomy_levels

        print(f"Running hierarchical location mapping with {self.cutoff*100}% cutoff")
        print(f"Processing taxonomy levels: {taxonomy_levels}")

        for taxonomy_level in taxonomy_levels:
            try:
                self.process_taxonomy_level(taxonomy_level)
            except Exception as e:
                print(f"Error processing {taxonomy_level}: {e}")
                continue

        print("\\nHierarchical location mapping complete!")

def main():
    parser = argparse.ArgumentParser(description='Generate hierarchical location mapping ROBOT templates')
    parser.add_argument('--input-dir', required=True,
                      help='Directory containing cell count matrices')
    parser.add_argument('--output-dir', required=True,
                      help='Directory to write ROBOT templates')
    parser.add_argument('--cutoff', type=float, default=0.05,
                      help='Proportion cutoff threshold (default: 0.05)')
    parser.add_argument('--taxonomy-levels', nargs='+',
                      choices=['cluster', 'supertype', 'subclass', 'class', 'neurotransmitter'],
                      help='Taxonomy levels to process (default: all)')
    parser.add_argument('--source-doi', default=None,
                      help='Publication DOI (CURIE form, e.g. doi:10.1038/...) '
                           'to attach as dcterms:source axiom annotation on every edge')
    parser.add_argument('--output-suffix', default="",
                      help='Suffix appended to output template filenames before .tsv '
                           '(e.g. "_zhuang"). Default: "" (no suffix).')

    args = parser.parse_args()

    mapper = HierarchicalLocationMapper(
        cell_count_matrices_dir=args.input_dir,
        output_dir=args.output_dir,
        cutoff=args.cutoff,
        source_doi=args.source_doi,
        output_suffix=args.output_suffix,
    )

    mapper.run(taxonomy_levels=args.taxonomy_levels)

if __name__ == "__main__":
    main()