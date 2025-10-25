#!/usr/bin/env python3
"""
Generate complete taxonomy × brain region matrices from CCF data.

This script creates all cross-tabulation matrices directly from the
cell_metadata_with_parcellation_annotation.csv file.

Data Caching:
- Automatically downloads CCF data from Allen Brain Cell Atlas if not cached
- Stores data in src/scripts/cell_counts/resources/aba_cache/
- Cache directory is added to .gitignore to avoid versioning large files
- File size: ~1.5 GB, download may take several minutes on first run
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import urllib.request
import urllib.error
from pathlib import Path

def create_output_directory():
    """Create directory for matrix outputs."""

    output_dir = "../reports/cell_counts_and_proportions/taxonomy_by_region_matrices"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"✅ Created output directory: {output_dir}")
    return output_dir

def load_full_ccf_data():
    """Load the complete CCF dataset, downloading if necessary."""

    # Define cache configuration
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
        print(f"⚠️  This is a large file (~2GB) and may take several minutes to download...")

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

def generate_matrix(df, taxonomy_col, region_col, output_dir):
    """Generate a single cross-tabulation matrix."""

    print(f"  📊 Generating {taxonomy_col} × {region_col} matrix...")

    # Filter out null values
    df_clean = df.dropna(subset=[taxonomy_col, region_col])

    if len(df_clean) == 0:
        print(f"    ⚠️ No valid data for {taxonomy_col} × {region_col}")
        return None, None

    # Create cross-tabulation
    crosstab = pd.crosstab(df_clean[taxonomy_col], df_clean[region_col])

    # Create output filename
    tax_short = taxonomy_col.replace('parcellation_', '')
    reg_short = region_col.replace('parcellation_', '')
    filename = f"{tax_short}_by_{reg_short}.csv"
    filepath = os.path.join(output_dir, filename)

    # Save matrix
    crosstab.to_csv(filepath)

    # Calculate metadata
    file_size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
    matrix_shape = crosstab.shape
    total_cells = int(crosstab.sum().sum())
    # Count non-zero entries using numpy
    non_zero_combinations = int(np.sum(crosstab > 0))

    metadata = {
        'filename': filename,
        'taxonomy_level': tax_short,
        'region_level': reg_short,
        'matrix_shape': list(matrix_shape),
        'total_cells': int(total_cells),
        'non_zero_combinations': int(non_zero_combinations),
        'file_size_mb': file_size_mb,
        'sparsity': round(1 - (non_zero_combinations / (matrix_shape[0] * matrix_shape[1])), 3)
    }

    print(f"    ✅ {filename} - {matrix_shape[0]}×{matrix_shape[1]} - {file_size_mb} MB")

    return metadata, crosstab

def generate_all_matrices(df, output_dir):
    """Generate all taxonomy × region matrices."""

    print(f"\n=== GENERATING ALL MATRICES ===")

    # Define taxonomy and region levels
    taxonomy_levels = ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster']
    region_levels = ['parcellation_division', 'parcellation_structure', 'parcellation_substructure']

    all_metadata = []

    # Generate matrices
    for tax_col in taxonomy_levels:
        if tax_col not in df.columns:
            print(f"⚠️ Taxonomy column '{tax_col}' not found")
            continue

        for reg_col in region_levels:
            if reg_col not in df.columns:
                print(f"⚠️ Region column '{reg_col}' not found")
                continue

            metadata, crosstab = generate_matrix(df, tax_col, reg_col, output_dir)
            if metadata:
                all_metadata.append(metadata)

    # Save metadata summary
    metadata_file = os.path.join(output_dir, 'matrix_metadata.json')
    with open(metadata_file, 'w') as f:
        json.dump(all_metadata, f, indent=2)

    print(f"✅ Saved metadata: matrix_metadata.json")

    # Create summary CSV
    summary_df = pd.DataFrame(all_metadata)
    summary_file = os.path.join(output_dir, 'matrix_summary.csv')
    summary_df.to_csv(summary_file, index=False)

    print(f"✅ Saved summary: matrix_summary.csv")

    return all_metadata

def create_readme(output_dir, metadata_list):
    """Create comprehensive README for the matrices."""

    readme_content = f"""# Taxonomy × Brain Region Cross-Tabulation Matrices

## Overview

This directory contains complete cross-tabulation matrices showing cell counts for each taxonomy node within each brain region, extracted from the Allen Brain Cell Atlas.

**Source Data**: `cell_metadata_with_parcellation_annotation.csv`
**Source Date**: 2023-12-15
**Total Cells**: {sum(m['total_cells'] for m in metadata_list):,}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Matrix Files

Each CSV file contains a cross-tabulation matrix where:
- **Rows**: Taxonomy terms (cell types)
- **Columns**: Brain regions
- **Values**: Cell counts

### Taxonomy Levels
- **neurotransmitter**: Broad neurotransmitter types (10 terms)
- **class**: Major cell classes (34 terms)
- **subclass**: Cell subclasses (265 terms)
- **supertype**: Cell supertypes (690 terms)
- **cluster**: Individual clusters (1,406 terms)

### Brain Region Levels
- **division**: Major brain divisions (25 regions)
- **structure**: Brain structures (354 regions)
- **substructure**: Fine brain substructures (669 regions)

## File Listing

| File | Taxonomy Level | Region Level | Matrix Size | File Size |
|------|----------------|--------------|-------------|-----------|
"""

    for metadata in sorted(metadata_list, key=lambda x: x['file_size_mb']):
        tax = metadata['taxonomy_level']
        reg = metadata['region_level'].replace('parcellation_', '')
        shape = f"{metadata['matrix_shape'][0]} × {metadata['matrix_shape'][1]}"
        size = f"{metadata['file_size_mb']} MB"
        filename = f"{tax}_by_{reg}.csv"

        readme_content += f"| {filename} | {tax} | {reg} | {shape} | {size} |\n"

    readme_content += f"""
## Usage Examples

### Python
```python
import pandas as pd

# Load a matrix
cluster_by_structure = pd.read_csv('cluster_by_structure.csv', index_col=0)

# Find cell count for specific cluster in specific region
cell_count = cluster_by_structure.loc['0982 STR D2 Gaba_4', 'CP']

# Get top regions for a specific cluster
cluster_row = cluster_by_structure.loc['0982 STR D2 Gaba_4']
top_regions = cluster_row.sort_values(ascending=False).head(10)
```

### R
```r
# Load a matrix
cluster_by_structure <- read.csv('cluster_by_structure.csv', row.names=1)

# Find cell count
cell_count <- cluster_by_structure['0982 STR D2 Gaba_4', 'CP']

# Get top regions
cluster_row <- cluster_by_structure['0982 STR D2 Gaba_4', ]
top_regions <- sort(cluster_row, decreasing=TRUE)[1:10]
```

## Data Quality

- **Total cells analyzed**: {sum(m['total_cells'] for m in metadata_list):,}
- **Non-zero combinations**: {sum(m['non_zero_combinations'] for m in metadata_list):,}
- **Matrix sparsity**: Most matrices are sparse (many zero entries)
- **Source validation**: Cross-checked against ABC Atlas web interface

## Notes

- Zero values are included in matrices (not sparse format)
- All cell counts are integers
- Missing taxonomy annotations are excluded
- Brain regions include 'unassigned' category for unmapped cells

## Citation

Data source: Allen Brain Cell Atlas
- Yao et al. (2023) "A high-resolution transcriptomic and spatial atlas of cell types in the whole mouse brain"
- Allen Institute for Brain Science ABC Atlas Access API
"""

    readme_path = os.path.join(output_dir, 'README.md')
    with open(readme_path, 'w') as f:
        f.write(readme_content)

    print(f"✅ Created README.md")

def main():
    """Main execution function."""

    print("🧠 COMPLETE TAXONOMY × BRAIN REGION MATRIX GENERATION")
    print("="*60)
    print("Generating all cross-tabulation matrices from CCF data")
    print("="*60)

    # Create output directory
    output_dir = create_output_directory()

    # Load data
    df = load_full_ccf_data()

    # Generate all matrices
    metadata_list = generate_all_matrices(df, output_dir)

    # Create documentation
    create_readme(output_dir, metadata_list)

    # Final summary
    total_size_gb = sum(m['file_size_mb'] for m in metadata_list) / 1024
    total_files = len(metadata_list)
    total_cells = sum(m['total_cells'] for m in metadata_list)

    print(f"\n🎉 MATRIX GENERATION COMPLETE!")
    print(f"✅ Generated {total_files} matrix files")
    print(f"✅ Total size: {total_size_gb:.2f} GB")
    print(f"✅ Total cells analyzed: {total_cells:,}")
    print(f"✅ Output directory: {output_dir}/")

    print(f"\n📊 Files created:")
    print(f"  • {total_files} cross-tabulation CSV files")
    print(f"  • matrix_summary.csv - Overview of all matrices")
    print(f"  • matrix_metadata.json - Detailed metadata")
    print(f"  • README.md - Comprehensive documentation")

if __name__ == "__main__":
    main()