#!/usr/bin/env python
# coding: utf-8

# # scFAIR_Sillet_WMB_2_KG: Jupyter Notebook Version
# 
# This notebook replicates the logic of `scFAIR_Sillet_WMB_2_KG.py` for interactive exploration and reporting. After each major code block, a concise report of the resulting data is shown. Only the final joined DataFrame is saved as a file.

# In[1]:


# Import Required Libraries
import pandas as pd
from pathlib import Path


# In[2]:


# Load and Preprocess Data
info_path = Path('info_celltype_complete.tsv')
matrix_path = Path('sm_cluster.mapping_table.tsv')

# Load info_cell_type_complete.tsv
df_info = pd.read_csv(info_path, sep='\t')
print('info_celltype_complete.tsv:')
print('Shape:', df_info.shape)
print('Columns:', df_info.columns.tolist())
display(df_info.head())

# Aggregate and prepend 'mm_'
df_info_agg = df_info[['cell_type', 'cellTypeId_', 'cellTypeName_']].groupby('cellTypeName_', as_index=False).agg({'cell_type': list})
df_info_agg['cellTypeName_'] = 'mm_' + df_info_agg['cellTypeName_'].astype(str)
print('Aggregated info_cell_type_complete.tsv:')
print('Shape:', df_info_agg.shape)
display(df_info_agg.head())

# Load mapping table
raw = pd.read_csv(matrix_path, sep='\t', header=None)
header = raw.iloc[0, 1:].tolist()
rows = raw.iloc[1:, 0].tolist()
matrix = raw.iloc[1:, 1:]
matrix.columns = header
matrix.index = rows
matrix = matrix.astype(float)

# Melt to long format
long_df = matrix.reset_index().melt(id_vars='index', var_name='c', value_name='score')
long_df = long_df.rename(columns={'index': 'r'})
long_df = long_df[long_df['score'] >= 0.1]
long_df['score'] = long_df['score'].round(2)
long_df = long_df.sort_values(by='score', ascending=False)
print('Processed mapping table (long format):')
print('Shape:', long_df.shape)
display(long_df.head())


# In[3]:


[x for x in list(df_info_agg['cellTypeName_']) if 'mm_' in x]


# In[4]:


[x for x in list(long_df['c']) if 'mm_' in x]


# In[5]:


# Inner join long_df and df_info on 'c'
joined_df = pd.merge(long_df, df_info_agg, left_on='c', right_on='cellTypeName_', how='inner')
print('Joined DataFrame:')
print('Shape:', joined_df.shape)
display(joined_df.head())

# Save the final joined DataFrame
joined_df.to_csv('sm_cluster.mappings_long_joined.tsv', sep='\t', index=False)
print('Final joined DataFrame saved to sm_cluster.mappings_long_joined.tsv')


# In[6]:


joined_df


# In[7]:


# Add cell_set_accession to joined_df using an inner join on r
human_clusters = pd.read_csv('human_clusters_with_top_mouse_pred_and_score.tsv', sep='\t', usecols=['human_cluster', 'cell_set_accession'])
joined_df_with_accession = pd.merge(joined_df, human_clusters, left_on='r', right_on='human_cluster', how='inner')
joined_df_with_accession = joined_df_with_accession.drop(columns=['human_cluster'])
display(joined_df_with_accession.head())


# In[8]:


# Rename columns and drop CellTypeName_ in joined_df_with_accession
joined_df_with_accession = joined_df_with_accession.rename(columns={
    'r': 'human_cluster',
    'c': 'mouse_CL_cell_set',
    'cell_type': 'Mouse_subclasses',
    'cell_set_accession': 'Human_cell_set_accession'
})
if 'cellTypeName_' in joined_df_with_accession.columns:
    joined_df_with_accession = joined_df_with_accession.drop(columns=['cellTypeName_'])
display(joined_df_with_accession.head())


# In[9]:


# Clean Mouse_subclasses: remove everything before ': ' in each list entry
if 'Mouse_subclasses' in joined_df_with_accession.columns:
    def clean_mouse_subclass(lst):
        cleaned= [x.split(': ', 1)[-1] if ': ' in x else x for x in lst]
        if len(cleaned) == 1:
            return(cleaned)[0]
        elif len(cleaned) == 0 or len(cleaned) > 1:
            return('')

    joined_df_with_accession['Mouse_subclasses'] = joined_df_with_accession['Mouse_subclasses'].apply(clean_mouse_subclass)
display(joined_df_with_accession.head())


# In[ ]:





# In[10]:


# Map Mouse_subclasses to mouse accession using cell_set_map.tsv
# Note: cell_set_map.tsv would normally be generated from Neo4j query: make reports
# For this notebook, we'll create a simplified mapping or skip this step if file doesn't exist
cell_set_map_path = Path('../../../../reports/cell_set_map.csv')

if cell_set_map_path.exists():
    cell_set_map = pd.read_csv(cell_set_map_path)

    # Filter for mouse subclass rows
    mouse_subclass_map = cell_set_map[(cell_set_map['dataset'] == 'Whole Mouse Brain Taxonomy') & (cell_set_map['labelset'] == 'subclass')].copy()

    # Remove leading numbers and space from label for matching
    import re
    def clean_label(label):
        return re.sub(r'^\d+ ', '', str(label))

    mouse_subclass_map['clean_label'] = mouse_subclass_map['label'].apply(clean_label)

    # Compute short_form from iri (text after last '/')
    def iri_to_short_form(iri):
        return str(iri).rsplit('/', 1)[-1] if pd.notnull(iri) else ''

    mouse_subclass_map['short_form'] = mouse_subclass_map['iri'].apply(iri_to_short_form)

    # Build mapping: cleaned label -> short_form
    label_to_accession = dict(zip(mouse_subclass_map['clean_label'], mouse_subclass_map['short_form']))

    # Map Mouse_subclasses to accession
    def map_mouse_accession(subclass):
        return label_to_accession.get(subclass, '')

    joined_df_with_accession['Mouse_accession'] = joined_df_with_accession['Mouse_subclasses'].apply(map_mouse_accession)
else:
    print("Warning: cell_set_map.csv not found. Run 'make reports' to generate it from Neo4j.")
    print("Setting Mouse_accession to empty for now.")
    joined_df_with_accession['Mouse_accession'] = ''

display(joined_df_with_accession.head())


# In[11]:


joined_df_with_accession.to_csv('./scFAIR_Siletti_AT_map.tsv', sep='\t', index=False)

