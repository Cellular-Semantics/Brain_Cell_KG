#!/usr/bin/env python3
"""
Generate cell count and proportion reports from CCF data.

This script creates:
1. Cell count report: Total cells for each taxonomy node (cell set)
2. Proportion reports: For each cell set, shows the proportion of cells in each brain structure

Data Source: Allen Brain Cell Atlas MERFISH data
- Automatically downloads and caches CCF data if not present
- Uses the same caching system as generate_full_matrices.py
"""

import pandas as pd
import os
import json
from datetime import datetime
import urllib.request
import urllib.error
from pathlib import Path


def create_output_directory():
    """Create directory for proportion report outputs."""

    output_dir = "src/scripts/cell_counts/reports/cell_counts_and_proportions"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"✅ Created output directory: {output_dir}")
    return output_dir


def load_full_ccf_data():
    """Load the complete CCF dataset, downloading if necessary."""

    # Define cache configuration (same as generate_full_matrices.py)
    aba_cache = 'src/scripts/cell_counts/resources/aba_cache'
    cache_path = f'{aba_cache}/metadata/MERFISH-C57BL6J-638850-CCF/20231215/views'
    ccf_filename = 'cell_metadata_with_parcellation_annotation.csv'
    ccf_path = os.path.join(cache_path, ccf_filename)

    # URL for the data file
    data_url = 'https://allen-brain-cell-atlas.s3-us-west-2.amazonaws.com/metadata/MERFISH-C57BL6J-638850-CCF/20231215/views/cell_metadata_with_parcellation_annotation.csv'

    # Create cache directory if it doesn't exist
    cache_dir = Path(cache_path)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Check if file exists in cache
    if not os.path.exists(ccf_path):
        print(f"📥 Data file not found in cache. Downloading from Allen Brain Cell Atlas...")
        print(f"Source: {data_url}")
        print(f"Target: {ccf_path}")
        print(f"⚠️  This is a large file (~1.5GB) and may take several minutes to download...")

        try:
            # Download with progress reporting
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = min(100, (downloaded * 100) // total_size)
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"\r📊 Progress: {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end='', flush=True)

            urllib.request.urlretrieve(data_url, ccf_path, reporthook=download_progress)
            print(f"\n✅ Download complete: {ccf_path}")

        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to download CCF data: {e}")
        except Exception as e:
            raise RuntimeError(f"Error downloading file: {e}")

    else:
        print(f"✅ Found cached CCF data: {ccf_path}")

    # Verify file exists and get size
    if not os.path.exists(ccf_path):
        raise FileNotFoundError(f"CCF data file not found: {ccf_path}")

    file_size_gb = os.path.getsize(ccf_path) / (1024*1024*1024)
    print(f"📁 File size: {file_size_gb:.2f} GB")

    print(f"🔄 Loading CCF dataset into memory (this may take a moment)...")

    # Load with low_memory=False to handle mixed types
    try:
        df = pd.read_csv(ccf_path, low_memory=False)
        print(f"✅ Loaded {len(df):,} cells with {len(df.columns)} columns")
        return df

    except Exception as e:
        raise RuntimeError(f"Error loading CCF data: {e}")


def generate_cell_count_report(df, output_dir):
    """Generate cell count report for each taxonomy node."""

    print("\n=== GENERATING CELL COUNT REPORT ===")

    # Define taxonomy levels
    taxonomy_levels = ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster']

    all_counts = []

    for tax_level in taxonomy_levels:
        if tax_level not in df.columns:
            print(f"⚠️ Taxonomy column '{tax_level}' not found")
            continue

        print(f"  📊 Counting cells for {tax_level} level...")

        # Count cells for each taxonomy node, excluding null values
        df_clean = df.dropna(subset=[tax_level])
        counts = df_clean[tax_level].value_counts().sort_values(ascending=False)

        # Add to master list
        for cell_set, count in counts.items():
            all_counts.append({
                'taxonomy_level': tax_level,
                'cell_set': cell_set,
                'cell_count': int(count)
            })

        print(f"    ✅ Found {len(counts)} {tax_level} nodes with total {counts.sum():,} cells")

    # Create DataFrame and save
    counts_df = pd.DataFrame(all_counts)

    # Add percentage of total cells
    total_cells = len(df)
    counts_df['percentage_of_total'] = (counts_df['cell_count'] / total_cells * 100).round(3)

    # Save main report
    counts_file = os.path.join(output_dir, 'cell_counts_by_taxonomy.csv')
    counts_df.to_csv(counts_file, index=False)

    # Save summary by taxonomy level
    summary_df = counts_df.groupby('taxonomy_level').agg({
        'cell_set': 'count',
        'cell_count': ['sum', 'mean', 'median', 'std']
    }).round(2)
    summary_df.columns = ['num_nodes', 'total_cells', 'mean_cells_per_node', 'median_cells_per_node', 'std_cells_per_node']
    summary_file = os.path.join(output_dir, 'cell_counts_summary_by_level.csv')
    summary_df.to_csv(summary_file)

    print(f"✅ Cell count report saved: {counts_file}")
    print(f"✅ Summary by level saved: {summary_file}")

    return counts_df


def generate_proportion_reports(df, output_dir):
    """Generate proportion reports showing structure distribution for each cell set."""

    print("\n=== GENERATING PROPORTION REPORTS ===")

    # Define taxonomy and region levels
    taxonomy_levels = ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster']
    region_levels = ['parcellation_division', 'parcellation_structure', 'parcellation_substructure']

    # Create subdirectory for proportion reports
    prop_dir = os.path.join(output_dir, 'proportion_reports')
    if not os.path.exists(prop_dir):
        os.makedirs(prop_dir)
        print(f"✅ Created proportion reports directory: {prop_dir}")

    all_metadata = []

    for tax_level in taxonomy_levels:
        if tax_level not in df.columns:
            print(f"⚠️ Taxonomy column '{tax_level}' not found")
            continue

        for reg_level in region_levels:
            if reg_level not in df.columns:
                print(f"⚠️ Region column '{reg_level}' not found")
                continue

            print(f"  📊 Generating proportions: {tax_level} × {reg_level}...")

            # Filter out null values
            df_clean = df.dropna(subset=[tax_level, reg_level])

            if len(df_clean) == 0:
                print(f"    ⚠️ No valid data for {tax_level} × {reg_level}")
                continue

            # Create cross-tabulation (raw counts)
            crosstab = pd.crosstab(df_clean[tax_level], df_clean[reg_level])

            # Convert to proportions (each row sums to 1.0) and round to 2 decimal places
            proportions = crosstab.div(crosstab.sum(axis=1), axis=0).fillna(0).round(2)

            # Create output filename
            tax_short = tax_level.replace('parcellation_', '')
            reg_short = reg_level.replace('parcellation_', '')
            filename = f"{tax_short}_proportions_by_{reg_short}.csv"
            filepath = os.path.join(prop_dir, filename)

            # Save proportion matrix
            proportions.to_csv(filepath)

            # Calculate metadata
            file_size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
            matrix_shape = proportions.shape
            total_cell_sets = matrix_shape[0]
            total_regions = matrix_shape[1]

            # Find cell sets with highest regional concentration
            max_proportions = proportions.max(axis=1).sort_values(ascending=False)
            most_concentrated = max_proportions.head(5)

            metadata = {
                'filename': filename,
                'taxonomy_level': tax_short,
                'region_level': reg_short,
                'num_cell_sets': total_cell_sets,
                'num_regions': total_regions,
                'matrix_shape': list(matrix_shape),
                'file_size_mb': file_size_mb,
                'most_concentrated_cell_sets': {
                    cell_set: round(prop, 2) for cell_set, prop in most_concentrated.items()
                }
            }

            all_metadata.append(metadata)

            print(f"    ✅ {filename} - {total_cell_sets} cell sets × {total_regions} regions")

    # Save metadata
    metadata_file = os.path.join(prop_dir, 'proportion_reports_metadata.json')
    with open(metadata_file, 'w') as f:
        json.dump(all_metadata, f, indent=2)

    print(f"✅ Proportion reports saved to: {prop_dir}/")
    print(f"✅ Metadata saved: {metadata_file}")

    return all_metadata


def create_summary_report(counts_df, proportion_metadata, output_dir):
    """Create comprehensive summary report."""

    print("\n=== GENERATING SUMMARY REPORT ===")

    # Summary statistics
    total_cell_sets = len(counts_df)
    total_cells = counts_df['cell_count'].sum()

    # Top 10 largest cell sets
    top_10 = counts_df.nlargest(10, 'cell_count')

    # Cell sets by taxonomy level
    by_level = counts_df.groupby('taxonomy_level').agg({
        'cell_set': 'count',
        'cell_count': ['sum', 'mean'],
        'percentage_of_total': 'sum'
    }).round(3)

    summary_content = f"""# Cell Count and Proportion Analysis Report

## Overview

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Cell Sets**: {total_cell_sets:,}
**Total Cells Analyzed**: {total_cells:,}
**Data Source**: Allen Brain Cell Atlas MERFISH-C57BL6J-638850-CCF

## Cell Count Summary

### By Taxonomy Level

| Level | Cell Sets | Total Cells | Mean Cells/Set | % of Total |
|-------|-----------|-------------|----------------|------------|
"""

    for level, row in by_level.iterrows():
        summary_content += f"| {level} | {int(row[('cell_set', 'count')]):,} | {int(row[('cell_count', 'sum')]):,} | {row[('cell_count', 'mean')]:,.0f} | {row[('percentage_of_total', 'sum')]:.1f}% |\n"

    summary_content += f"""

### Top 10 Largest Cell Sets

| Rank | Cell Set | Taxonomy Level | Cell Count | % of Total |
|------|----------|----------------|------------|------------|
"""

    for i, (_, row) in enumerate(top_10.iterrows(), 1):
        summary_content += f"| {i} | {row['cell_set']} | {row['taxonomy_level']} | {row['cell_count']:,} | {row['percentage_of_total']:.3f}% |\n"

    summary_content += f"""

## Proportion Reports Generated

{len(proportion_metadata)} proportion matrices created showing regional distribution for each cell set:

| Taxonomy Level | Region Level | Cell Sets | Regions | File Size |
|----------------|--------------|-----------|---------|-----------|
"""

    for meta in proportion_metadata:
        summary_content += f"| {meta['taxonomy_level']} | {meta['region_level']} | {meta['num_cell_sets']} | {meta['num_regions']} | {meta['file_size_mb']} MB |\n"

    summary_content += f"""

## Files Generated

### Cell Count Reports
- `cell_counts_by_taxonomy.csv` - Complete cell count data for all taxonomy nodes
- `cell_counts_summary_by_level.csv` - Summary statistics by taxonomy level

### Proportion Reports (in proportion_reports/ subdirectory)
- `{len(proportion_metadata)}` CSV files showing proportion of cells in each region for each cell set
- `proportion_reports_metadata.json` - Detailed metadata for all proportion reports

## Usage Examples

### Python
```python
import pandas as pd

# Load cell counts
counts = pd.read_csv('cell_counts_by_taxonomy.csv')

# Find largest cell sets
largest = counts.nlargest(10, 'cell_count')

# Load proportion data for class level
class_props = pd.read_csv('proportion_reports/class_proportions_by_structure.csv', index_col=0)

# Find which structure has highest proportion for a specific cell set
cell_set = "Glutamatergic"
top_regions = class_props.loc[cell_set].sort_values(ascending=False).head(5)
```

### R
```r
# Load cell counts
counts <- read.csv('cell_counts_by_taxonomy.csv')

# Load proportion data
class_props <- read.csv('proportion_reports/class_proportions_by_structure.csv', row.names=1)

# Find top regions for a cell set
cell_set_props <- class_props["Glutamatergic", ]
top_regions <- sort(cell_set_props, decreasing=TRUE)[1:5]
```

## Notes

- Proportions are calculated as row percentages (each cell set sums to 1.0 across all regions)
- Null values in taxonomy or region annotations are excluded from analysis
- Regional proportions help identify anatomical specificity of cell types
- Data represents single-cell spatial transcriptomics from whole mouse brain
"""

    # Save summary
    summary_file = os.path.join(output_dir, 'ANALYSIS_SUMMARY.md')
    with open(summary_file, 'w') as f:
        f.write(summary_content)

    print(f"✅ Summary report saved: {summary_file}")


def main():
    """Main execution function."""

    print("🧠 CELL COUNT AND PROPORTION ANALYSIS")
    print("="*50)
    print("Generating cell counts and regional proportions for all taxonomy nodes")
    print("="*50)

    # Create output directory
    output_dir = create_output_directory()

    # Load data
    df = load_full_ccf_data()

    # Generate cell count report
    counts_df = generate_cell_count_report(df, output_dir)

    # Generate proportion reports
    proportion_metadata = generate_proportion_reports(df, output_dir)

    # Create summary report
    create_summary_report(counts_df, proportion_metadata, output_dir)

    # Final summary
    total_files = 2 + len(proportion_metadata) + 2  # counts + proportions + metadata + summary
    total_cell_sets = len(counts_df)

    print(f"\n🎉 ANALYSIS COMPLETE!")
    print(f"✅ Generated {total_files} report files")
    print(f"✅ Analyzed {total_cell_sets:,} cell sets")
    print(f"✅ Output directory: {output_dir}/")

    print(f"\n📊 Key Reports:")
    print(f"  • cell_counts_by_taxonomy.csv - Cell counts for all taxonomy nodes")
    print(f"  • proportion_reports/ - Regional distribution for each cell set")
    print(f"  • ANALYSIS_SUMMARY.md - Comprehensive overview and usage examples")


if __name__ == "__main__":
    main()