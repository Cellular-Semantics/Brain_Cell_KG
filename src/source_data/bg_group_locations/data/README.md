# Source data: HMBA BG consensus annotation

`HMBA_BG_consensus_annotation.csv` is a verbatim copy of

    hmba_basal_ganglia_ontology/src/dendrograms/28082024/HMBA_BG_consensus_annotation.csv

vendored at upstream commit `af48d5b4ea17b63296c5e008b6f29c91ceb5e5c4` (2025-10-01).

## Why it is vendored

Only one column is used here: **`spatial_regional_proportions`**, keyed by
`accession_group`. It holds the per-Group spatial breakdown as
`ACRONYM:fraction` pairs, e.g.

    STR:0.3, SN:0.1, STH:0.1, Adj:0.4

The named anatomical regions (`STR`, `GPe`, `GPi`, `SN`, `STH`) survive into
`bgo-full.owl` as `CLM:0010001` assignments and are read from there, so this
repo does **not** re-derive the acronym -> DHBA mapping.

What does *not* survive is the **`Adj`** ("adjacent") fraction. Upstream
`src/scripts/template_generation_tools.py` maps `adj`/`na` to `root`, which is
absent from the DHBA symbol map, so the fraction is silently dropped:

```python
if region_label.lower() in ["na", "adj"]:
    region_label = 'root'  # handle NA as brain
```

That is the only reason this file is here: it is the sole available source for
the `Adj` fraction, which the generator emits as `n2o:adjacentCellRatio`.

## What `Adj` means

Tissue *adjacent to* the dissected nucleus -- cells captured by the dissection
that are not localised to a named basal ganglia structure. It is explicitly
**not** a claim that the cells are in the basal ganglia, and for the 12 Groups
whose named regions are substantia nigra (`DHBA:12251`) or subthalamic nucleus
(`DHBA:10466`) it cannot be: neither region has a path to `DHBA:10332`
("basal nuclei (basal ganglia)") in the DHBA hierarchy. It is therefore
recorded as a plain data annotation on the cell set, never as a soma location.

## Known imprecision

Upstream proportions are rounded to one decimal place. 46 of 61 Groups sum to
1.0; the other 15 sum to 0.9. So `1 - sum(named)` is **not** a safe proxy for
`Adj` -- the generator reads `Adj` directly from this file rather than
computing a residual, and the 0.1 slack on those 15 Groups is left unassigned.

## Refreshing

Re-copy from upstream and re-run `make bg-location-templates`. The generator
cross-checks every named ratio in this file against `bgo-full.owl` and fails
the build if the two sources have drifted apart.
