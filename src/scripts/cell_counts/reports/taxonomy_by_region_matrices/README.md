# Taxonomy × Brain Region Cross-Tabulation Matrices

## Overview

This directory contains complete cross-tabulation matrices showing cell counts for each taxonomy node within each brain region, extracted from the Allen Brain Cell Atlas.

**Source Data**: `cell_metadata_with_parcellation_annotation.csv`
**Source Date**: 2023-12-15
**Total Cells**: 51,279,120
**Generated**: 2025-10-16 18:07:18

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
| neurotransmitter_by_division.csv | neurotransmitter | division | 9 × 25 | 0.0 MB |
| neurotransmitter_by_structure.csv | neurotransmitter | structure | 9 × 354 | 0.0 MB |
| neurotransmitter_by_substructure.csv | neurotransmitter | substructure | 9 × 669 | 0.0 MB |
| class_by_division.csv | class | division | 34 × 25 | 0.0 MB |
| class_by_structure.csv | class | structure | 34 × 354 | 0.0 MB |
| subclass_by_division.csv | subclass | division | 338 × 25 | 0.0 MB |
| class_by_substructure.csv | class | substructure | 34 × 670 | 0.1 MB |
| supertype_by_division.csv | supertype | division | 1201 × 25 | 0.1 MB |
| subclass_by_structure.csv | subclass | structure | 338 × 354 | 0.2 MB |
| cluster_by_division.csv | cluster | division | 5274 × 25 | 0.4 MB |
| subclass_by_substructure.csv | subclass | substructure | 338 × 670 | 0.5 MB |
| supertype_by_structure.csv | supertype | structure | 1201 × 354 | 0.9 MB |
| supertype_by_substructure.csv | supertype | substructure | 1201 × 670 | 1.6 MB |
| cluster_by_structure.csv | cluster | structure | 5274 × 354 | 3.7 MB |
| cluster_by_substructure.csv | cluster | substructure | 5274 × 670 | 6.9 MB |

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

- **Total cells analyzed**: 51,279,120
- **Non-zero combinations**: 328,527
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
