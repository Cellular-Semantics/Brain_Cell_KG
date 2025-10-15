# WMB Token Mapping System

The directory `src/scripts/WMB_token_map` contains a comprehensive token mapping system for the WMB (Whole Mouse Brain) taxonomy. Tokens are elements extracted from the names of cell clusters in the WMB taxonomy stored in the knowledge graph.

## Data Source
```cypher
MATCH (cc:cell_Cluster:WMB) RETURN cc.label
```

## Token Grammar

WMB cell cluster labels follow this approximate grammar pattern:

### Example Labels
- `458 MPO-ADP Lhx8 Gaba_1`
- `319 SI-MA-ACB Ebf1 Bnc2 Gaba_1`
- `1146 CB PLI Gly-Gaba_3`

### Grammar Structure
Labels consist of sequential elements (0-many of each type):

1. **Number** (mandatory) - Cluster identifier at start
2. **Anatomical tokens** (st:anatomical) - Always capitalized brain regions
   - Multiple regions separated by '-' (e.g., `SI-MA-ACB`)
3. **Cell type tokens** (st:cell_type) - Cell type identifiers, space-separated
4. **Gene tokens** (st:gene) - Gene symbols, space separated, start with capital. May contain '-' so don't split on it.
5. **Neurotransmission tokens** (t:neurotransmission) - Neurotransmitter types
   - Can be compound (e.g., `Gly-Gaba`, `Dopa-Gaba`) - these are split into components
6. **Suffix** (optional) - `_{number}` variant identifier

**Note**: Grammar is a guide - ambiguities exist, especially between gene vs cell_type classification.

## Knowledge Graph Mapping

The system maps token primary identifiers to KG entities:

- **Genes**: `:Gene` node label
  - **Critical**: WMB uses `ENSEMBL:` (uppercase) while KG uses `ensembl:` (lowercase)
- **Anatomical**: `:MBA` node label (Mouse Brain Atlas), fallback to `:Class`
- **Cell types & Neurotransmission**: `:Cell` node label, fallback to `:Class`

## Implementation

### Key Components

1. **Token Parser** (`wmb_token_mapper.py`)
   - Parses 6,905 WMB cell clusters
   - Handles compound neurotransmission tokens (splits `Gly-Gaba` → `Gly` + `Gaba`)
   - Produces ~29,135 token mappings

2. **KG Matcher** (`kg_token_matcher.py`)
   - Maps tokens to KG entities using multiple strategies
   - Corrects CURIE case mismatches (`ENSEMBL:` → `ensembl:`)
   - Implements fallback searches (`:Gene`/`:MBA`/`:Cell` → `:Class`)
   - Uses short_form matching (`:` → `_` replacement)

3. **Report Generator** (`generate_wmb_token_reports.py`)
   - Creates comprehensive analysis reports
   - Generates consolidated Excel file for review
   - Produces problem token analysis

### Current Performance

**Overall Success Rate**: 98.4% (27,714/28,177 mappable tokens)

- **Anatomical**: 99.7% (12,152/12,183)
- **Gene**: 99.9% (7,670/7,676)
- **Cell type**: 94.9% (7,892/8,318)
- **Unknown tokens**: 22 remaining (mostly parsing ambiguities)

### Key Insights Learned

1. **CURIE Case Sensitivity**: Major issue resolved by normalizing `ENSEMBL:` → `ensembl:`
2. **Compound Neurotransmitters**: Required special parsing logic to split hyphenated combinations
3. **Fallback Strategies**: Essential for high match rates - specific labels → `:Class` → short_form
4. **Token Complexity**: Grammar covers ~95% of cases, remaining 5% require manual review

## Usage

```bash
# Generate complete mapping reports
make wmb-token-mapping

# Or run directly
cd src/scripts/WMB_token_map/scripts
../../../../.venv/bin/python generate.py
```

## Output Files

- `wmb_token_kg_mapping_complete.csv` - Main mapping results
- `wmb_token_mapping_complete.xlsx` - Consolidated Excel report
- `wmb_problem_tokens_report.csv` - Unresolved tokens for review
- Additional analysis reports for cluster composition and token usage

# Additional report generation

Using the KG, For each anatomical and gene mapping, what is the most general term in WMB with that 
mapping in each branch of the taxonomy?  
1. Generality can be partly determined by labelset, which we record using 
cypher :label for convenience.  General to specific (showing multiple labels) -  :WMB:class:Cell_cluster , :WMB:subclass:Cell_cluster ,
:WMB:supertype:Cell_cluster, :WMB:cluster:Cell_cluster
2. Individual branches can be navigated general to specific via (more_specific)-[:subcluster_of]->(more_general)

For each case of a most general term with mapping, report both cc and c from (cc:Cell_cluster)<-[:has_exemplar_data]-(c:Cell)

For neurotransmission - for each :class, :subclass or :supertype node, determine if all clusters under the node have 
that neurotransmission. This can be tested via (clus:cluster:WMB) clus.CCN20230722_nt_type_combo_label 
- split value on ':' to get each NT






