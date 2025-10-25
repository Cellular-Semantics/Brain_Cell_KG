# Cell Count and Proportion Analysis Report

## Overview

**Generated**: 2025-10-20 20:29:34
**Total Cell Sets**: 6,856
**Total Cells Analyzed**: 17,093,040
**Data Source**: Allen Brain Cell Atlas MERFISH-C57BL6J-638850-CCF

## Cell Count Summary

### By Taxonomy Level

| Level | Cell Sets | Total Cells | Mean Cells/Set | % of Total |
|-------|-----------|-------------|----------------|------------|
| class | 34 | 3,739,961 | 109,999 | 100.0% |
| cluster | 5,274 | 3,739,961 | 709 | 100.0% |
| neurotransmitter | 9 | 2,133,196 | 237,022 | 57.0% |
| subclass | 338 | 3,739,961 | 11,065 | 100.0% |
| supertype | 1,201 | 3,739,961 | 3,114 | 100.0% |


### Top 10 Largest Cell Sets

| Rank | Cell Set | Taxonomy Level | Cell Count | % of Total |
|------|----------|----------------|------------|------------|
| 1 | Glut | neurotransmitter | 1,323,818 | 35.397% |
| 2 | GABA | neurotransmitter | 745,023 | 19.921% |
| 3 | 01 IT-ET Glut | class | 657,365 | 17.577% |
| 4 | 30 Astro-Epen | class | 588,691 | 15.741% |
| 5 | 31 OPC-Oligo | class | 538,887 | 14.409% |
| 6 | 327 Oligo NN | subclass | 476,819 | 12.749% |
| 7 | 1184 MOL NN_4 | supertype | 450,146 | 12.036% |
| 8 | 33 Vascular | class | 425,630 | 11.381% |
| 9 | 319 Astro-TE NN | subclass | 294,884 | 7.885% |
| 10 | 333 Endo NN | subclass | 263,210 | 7.038% |


## Proportion Reports Generated

15 proportion matrices created showing regional distribution for each cell set:

| Taxonomy Level | Region Level | Cell Sets | Regions | File Size |
|----------------|--------------|-----------|---------|-----------|
| neurotransmitter | division | 9 | 25 | 0.0 MB |
| neurotransmitter | structure | 9 | 354 | 0.01 MB |
| neurotransmitter | substructure | 9 | 669 | 0.03 MB |
| class | division | 34 | 25 | 0.0 MB |
| class | structure | 34 | 354 | 0.05 MB |
| class | substructure | 34 | 670 | 0.09 MB |
| subclass | division | 338 | 25 | 0.04 MB |
| subclass | structure | 338 | 354 | 0.47 MB |
| subclass | substructure | 338 | 670 | 0.88 MB |
| supertype | division | 1201 | 25 | 0.15 MB |
| supertype | structure | 1201 | 354 | 1.67 MB |
| supertype | substructure | 1201 | 670 | 3.12 MB |
| cluster | division | 5274 | 25 | 0.65 MB |
| cluster | structure | 5274 | 354 | 7.3 MB |
| cluster | substructure | 5274 | 670 | 13.67 MB |


## Files Generated

### Cell Count Reports
- `cell_counts_by_taxonomy.csv` - Complete cell count data for all taxonomy nodes
- `cell_counts_summary_by_level.csv` - Summary statistics by taxonomy level

### Proportion Reports (in proportion_reports/ subdirectory)
- `15` CSV files showing proportion of cells in each region for each cell set
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
