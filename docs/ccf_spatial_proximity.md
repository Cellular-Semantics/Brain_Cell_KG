# Grounding cell-type-to-region matches in measured spatial proximity

*A CCF-based extension to the Brain Cell Knowledge Graph*

**David Osumi-Sutherland** and **Claude-Code**

---

## 1. Motivation

### The matching problem

The Brain Cell Knowledge Graph (Brain_Cell_KG) catalogues *transcriptomic*
cell types — discrete classes defined by single-cell gene expression
patterns from whole-brain MERFISH and 10x datasets. Most cell-type
descriptions in the published neuroscience literature are not phrased that
way: they refer to *anatomically* defined types — "the calbindin-positive
interneurons of CA1 stratum oriens", "GABAergic neurons of the
periaqueductal grey", "layer 5 extratelencephalic neurons of motor cortex".
Linking the two — *which transcriptomic types correspond to which
literature-described types?* — is a core task for an agentic workflow
that wants to build from prior knowledge rather than rediscover it.

Anatomical descriptions in the literature are typically location-defined,
so the match has to be grounded in *where each transcriptomic type sits in
the brain*. The Brain Cell KG already records this at the *discrete-
assignment* level: each MERFISH cell carries a `parcellation_index` from
the painted Allen CCF, and aggregated per cell type this becomes a count of
cells in each named region (the existing
[`PCL:0010063` location edge](src/scripts/cell_counts/generate_hierarchical_location_templates.py)
with `cell_count` and `cell_ratio` axiom annotations). That answers *"how
many cells of type X were observed inside region A?"*.

### Why the discrete count is not enough: misregistration is inevitable

Registering a particular animal's MERFISH sections into the Allen CCF
template means non-linearly warping the imaged anatomy onto an idealised
average brain. The warp is never perfect: published MERFISH-to-CCF
registration error is on the order of tens of micrometres per cell. So a
cell type that anatomically sits along the border between two regions will,
by registration noise alone, have many of its cells assigned to whichever
side of the boundary the warp happened to put them on. From the
discrete-count view the type can look *distributed across* a set of
substructures when it is really *concentrated at the boundary between
them* — and a literature search for "type X of region A" misses it
because most cells are recorded in the neighbouring B or C.

### The clearest evidence of misregistration is in the data itself

In the pooled Yao + Zhuang MERFISH datasets we use (9.14 M cells), about
**164 700 cells (~1.8 %) have valid `x_ccf / y_ccf / z_ccf` coordinates but
`parcellation_index = 0`** — they sit *inside* the CCF coordinate frame
yet *outside* any parcellated region. These are not unregistered cells;
they have real CCF positions. They are cells whose registered position
landed just outside the painted brain.

How far outside? On the Yao subset (68 586 such cells), the distribution of
distance from each unassigned cell to the nearest parcellated voxel is:

| percentile | distance to nearest parcellated voxel |
|---|---|
| 25 % | 24 µm |
| 50 % | 50 µm |
| 75 % | 130 µm |
| 90 % | 289 µm |
| 95 % | 429 µm |

| cumulative ≤ | fraction of unassigned cells |
|---|---|
| 50 µm | 50.1 % |
| 100 µm | **69.1 %** |
| 200 µm | 83.7 % |
| 500 µm | 96.5 % |

Half of these "outside-the-parcellation" cells sit within one MERFISH
registration-error standard (50 µm) of a parcellated voxel; over two
thirds within 100 µm. They cluster spatially at section peripheries — on
the worst-affected Yao section the unassigned cells sit on average **55 %
further from the section centroid** than the assigned ones — and they
concentrate on anterior and olfactory-bulb sections (sections 5 – 19 of
brain `638850` carry 4 – 6 % unassigned vs the 1.8 % global mean), which
is exactly where inter-animal anatomical variation is hardest for the
CCF to absorb.

Figure 1 shows the pattern on section `C57BL6J-638850.05` (5.6 %
unassigned). Cells outside any painted region appear both **(a)** in a
peripheral ring outside the brain — registered positions that fell off the
edge of the parcellated volume — and **(b)** in interior unpainted wedges
*between* named regions, e.g. the gap between CB (cerebellum) and MY
(medulla). The interior-gap cells are particularly informative because they
cannot be explained by a missing tissue scan: they are real, fully
transcriptomically-typed cells whose registered position landed in
unparcellated space inside the brain, at a CB/MY boundary that the CCF
template does not paint cleanly.

![Misregistration on section C57BL6J-638850.05](figures/fig1.png)

**Figure 1.** Misregistration on section `C57BL6J-638850.05` of the ABC
atlas Yao WMB MERFISH dataset (imputed genes / reconstructed coordinates
view). Coloured dots are individual cells, coloured by transcriptomic
identity. **Left panel — painted parcellation:** yellow = CB (cerebellum);
pink = MY (medulla). Substantial numbers of cells sit *outside* both
fills — both in the peripheral ring at the section boundary and in the
unpainted wedge between the two regions. **Right panel — region outlines
only, same section:** the cells in the gap between the CB outline (yellow)
and the MY outline (pink) are real, transcriptomically-typed neurons
whose registered CCF position fell in unpainted space at the CB / MY
boundary. They cannot be explained as missing tissue scans — they are
fully imaged cells whose CCF assignment is `parcellation_index = 0`. On
this section ≈ 5.6 % of cells fall in that category, against the 1.8 %
whole-brain mean.

If 1.8 % of cells are *frankly* outside the parcellation, many more are
*subtly* misassigned — in the wrong substructure but a few voxels from the
right one. A discrete count cannot reveal this; an agent reasoning from it
cannot account for it.

### The fix this work implements

We use the registered coordinates *directly* — they have been flowing
through the cell-count pipeline but, until now, had been aggregated into
discrete counts and discarded. For each cell type and each named region X,
the new layer measures:

- `countInRegion` — cells of the type whose `parcellation_index` puts them
  inside X (the existing signal), and
- `countInOrNear100um` — `countInRegion` **plus** cells of the type whose
  CCF coordinates fall within 100 µm of X's painted surface from the
  outside (the new signal).

The 100 µm band sits comfortably above MERFISH registration error and
approximates one cortical layer / a few cell-spacings — biologically a
"this type is at this region's boundary" scale. A cell that the
parcellation assigned to neighbour Y but whose CCF position is within
100 µm of X's surface still counts toward X's proximity signal. Border-
living cell types are no longer hidden behind the noise floor of
registration.

Alongside this, we emit a region-to-region adjacency layer from the
painted volume itself, so the graph carries explicit *measured* "next-to"
relations between named regions rather than relying on latent anatomy
knowledge.

The remainder of this paper describes both products, the schema we chose,
the filtering decisions (with their explicit trade-offs), and the
validation patterns.

## 2. Data sources

Everything reuses data that the existing pipeline already caches:

| dataset | what we use |
|---|---|
| Allen CCF 2020 annotation volume | the *painted* parcellation at 25 µm voxel resolution: every voxel labelled with a `parcellation_index` |
| `parcellation_to_parcellation_term_membership_acronym.csv` | maps `parcellation_index` → division / structure / substructure acronym |
| `reports/mba_symbol_map.csv` | acronym → [`MBA:` CURIE](http://purl.brain-bican.org/ontology/mbao/) |
| Yao WMB MERFISH (~3.7 M cells, single brain) | per-cell `x_ccf / y_ccf / z_ccf` + cluster-level taxonomy assignment |
| Zhuang ABCA MERFISH (4 brains, ~5.3 M cells) | same per-cell coordinates + taxonomy |
| `reports/cell_set_map.csv` | taxonomy label → cell-type CURIE |

Pooled: **9.14 M cells in CCF mm space**. The shared bridge that turns a
`parcellation_index` into a knowledge-graph CURIE at any of the three
hierarchical region levels lives in
[`src/utils/ccf_parcellation.py`](src/utils/ccf_parcellation.py); the
existing cell-count matrix script
[`generate_zhuang_matrices.py`](src/scripts/cell_counts/scripts/generate_zhuang_matrices.py)
was refactored to share it.

## 3. Two products

### 3.1 Region adjacency

The painted volume defines which regions abut which. For every pair of
regions whose painted territories share at least one voxel face we emit a
**`RO:0002220` "adjacent to"** edge, with axiom annotations capturing:

- `n2o:contactArea` (µm² — the shared boundary surface)
- `n2o:minDistance` (always one voxel = 25 µm for face-touching pairs)
- `n2o:centroidDistance` (µm)

Computed once per region level (division → structure → substructure) by
[`compute_region_adjacency.py`](src/scripts/ccf_spatial/scripts/compute_region_adjacency.py).
The implementation walks the volume along each of three axes in one
vectorised pass: 25 regions, 339 structures, 574 substructures, ~2 seconds.
Outputs land in [`templates/region_adjacency_{level}.tsv`](templates/) →
[`owl/region_adjacency_{level}.owl`](owl/).

### 3.2 Per-type "located in or near" proximity

For every (cell type, region X) pair we emit an
**`n2o:locatedInOrNear`** edge carrying three integer counts:

| axiom annotation | meaning |
|---|---|
| `n2o:typeCellTotal` | total cells of this type observed (whole brain) |
| `n2o:countInRegion` | cells whose painted resident region is X |
| `n2o:countInOrNear100um` | `countInRegion` **plus** cells observed within 100 µm of X's painted surface but residing outside X |

Computed by
[`compute_cell_proximity.py`](src/scripts/ccf_spatial/scripts/compute_cell_proximity.py).
The distance from each cell to a region's surface is measured against a KD-tree
built from the region's *painted boundary voxels* — robust to MERFISH section
spacing (sections are ~100–200 µm apart in z, but the surface is dense).

A literature-match agent can read two questions directly off these counts:

- *"Is this type really there?"* → `countInOrNear100um` above its noise floor.
- *"Is most of this type there?"* → `countInOrNear100um / typeCellTotal` close to 1.

The fractions are derivable, so the OWL carries only the integers.

### Why 100 µm?

It sits comfortably above MERFISH per-cell registration error (tens of
micrometres) and approximates one cortical layer or a few cell-spacings —
biologically a sensible "abutting" scale.

## 4. Schema

### Each region in exactly one place

A region acronym's *native level* in the CCF hierarchy is the first column in
the membership table where it appears without a `-unassigned` suffix. `MB` is
a division, `ZI` a structure, `DG-mo` a substructure. We restrict each
region-level's proximity table to regions canonical at that level, so:

- the **division** table contains only divisions (`HY`, `MB`, `Isocortex`, …);
- the **structure** table contains only structures (`ZI`, `SNr`, `MOs`, …);
- the **substructure** table contains only substructures (`MOs6a`, `CA1so`, …).

No region is duplicated across levels; an agent that resolves a literature
term to a CURIE pulls the edges at that CURIE's native level directly. The
canonical-level helper lives in
[`load_canonical_levels()`](src/utils/ccf_parcellation.py).

### Boundary cells (`parcellation_index = 0`)

About **1.8 %** of cells with valid CCF coordinates sit *outside* any
parcellated region (boundary slivers, CSF). The script keeps them: their
`region_<level>` is `NaN` so they never increment `countInRegion`, but they
do contribute to `typeCellTotal` (the denominator the agent uses) and to
`countInOrNear100um` when they fall within 100 µm of a region surface. The
alternative (drop them up-front) silently undercounts every type and
slightly inflates every fraction.

### `<X>-unassigned` cells

About **10 %** of cells at substructure granularity sit in regions like
`HY-unassigned` (hypothalamus without further annotation). These are
correctly captured *without* needing CURIEs for `-unassigned` placeholders:
the shared bridge folds them to the parent acronym, the cells appear in the
global cells KD-tree, and when queried against a canonical substructure B
nearby they classify as "near B but not in B" — contributing to `n_100`. They
also appear at the parent's canonical level (e.g. as residents of `HY` at
the division-level table), where they belong.

## 5. Filtering choices — the deliberate minimalism

Three filters survive in production. Everything else is left to the agent.

### 5.1 What we filter

| filter | rule | what it removes |
|---|---|---|
| **Noise floor** | `countInOrNear100um ≥ 3` | rows where fewer than 3 cells of the type are in or within 100 µm of the region — anecdotal at MERFISH registration noise |
| **Canonical level** | each region acronym in exactly one region-level table | duplication and the cross-level fold-through described above |
| **Empty rows** | implicit: rows with `countInOrNear100um = 0` are not emitted | uninformative (the rows would just say "this type has zero cells near this region", which is essentially every type × every distant region) |

### 5.2 What we deliberately do not filter

We considered, and dropped, two further filters that were attractive on size
but punitive on signal.

**A minimum-denominator floor on cells in the neighbourhood.** The earliest
version computed a "local concentration" fraction with a denominator of
*cells of the type that live in regions adjacent to B*. Filtering rows where
that denominator was below 50 would have cut the cluster table from 153 k
edges to about 31 k. But it would also have silently dropped every small
focal cluster — clusters with 5 cells, all of which sit at one region. Those
are *the strongest possible match signal* for a literature description, not
the weakest. We replaced the local denominator with the global
`typeCellTotal` and dropped the floor.

**A graded fraction cutoff on `frac_in_or_near_100`.** The location-mapping
script applies graded cutoffs (0.5–2.5 %) keyed to taxonomy level. We chose
not to mirror that here because the proximity numbers serve two opposite
queries:

- For an *exact-match* query the agent wants edges where the fraction is
  high (e.g. ≥ 0.5).
- For a *broad-match* query the agent wants to see *every* region where the
  type has any presence — including 2–3 % edges that together establish a
  distributed pattern (e.g. an Lamp5 interneuron type across six cortical
  areas, none of them dominant).

A single fraction floor cannot simultaneously serve both queries; we keep
the absolute count floor (which is symmetric) and let the agent apply its
own threshold per query.

### 5.3 The honest counterpoint

The current cluster proximity table has 153 082 edges, of which:

- 31 % have `frac_in_or_near_100 < 1 %` — very weak fractional signal,
- 59 % have `frac_in_or_near_100 < 5 %`.

A defensible refinement would be to add an additional emit-time filter such
as `frac_in_or_near_100 ≥ 0.005` (drop the bottom 5 %, keep the rest). It
would shrink the table by ~30 % and lose only edges where one in every 200
cells of a type touches the region — arguably below the broad-match
threshold of interest. We have not made that change because:

1. The KG already loads cleanly (cluster OWL = 86 MB in OFN serialisation,
   well under platform limits).
2. The decision of *what fractional threshold counts* depends on context
   the agent has and the script does not.
3. Once trimmed at emit time, that information cannot be recovered without
   a re-run; whereas downstream filtering is a one-line query.

That said: if downstream KG queries turn out to be slowed by the long
low-fraction tail, dropping `frac_in_or_near_100 < 0.005` would be the
narrowest reasonable cut.

## 6. Examples

All examples below pool Yao + Zhuang (9.14 M cells) and read from
[`reports/cell_proximity_*.csv`](reports/) (the inspection CSV; the OWL
template carries the same numbers as axiom annotations).

### 6.1 Focal exact-match: large type, one home

**`037 DG Glut`** — the dentate-gyrus granule-cell glutamatergic subclass
(57 357 cells in Yao alone; 91 692 pooled).

| level | near | n_total | n_in_X | n_in_or_near_100 | frac_in_or_near_100 |
|---|---|---|---|---|---|
| division | `HPF` (hippocampal formation) | 91 692 | 90 373 | 91 290 | **0.996** |
| substructure | `DG-mo` (DG molecular layer) | 91 692 | 11 881 | 74 319 | **0.811** |

Lit search for "hippocampal granule cell" pulls the division edge: 99.6 % of
this subclass lives in HPF — strongest possible match. Search for "DG
molecular layer" pulls the substructure edge: 81 % of the subclass is *in or
within 100 µm of* DG-mo (most cells sit one layer deep in DG-sg, the granule
layer, which abuts DG-mo).

### 6.2 Focal small cluster — would be lost without the absolute-count approach

**`1728 ZI Pax6 Gaba_2`** — a 49-cell cluster name-tagged as a zona incerta
Pax6 GABAergic type.

| level | near | n_total | n_in_X | n_in_or_near_100 | frac_in_or_near_100 |
|---|---|---|---|---|---|
| division | `HY` (hypothalamus) | 49 | 48 | 49 | **1.000** |
| structure | `ZI` (zona incerta) | 49 | 44 | 49 | **1.000** |

Every single cell of this 49-cell cluster lives in or within 100 µm of ZI.
The earlier filter that demanded a 50-cell "neighbourhood denominator" would
have dropped this row entirely. Under the current schema it is the cleanest
possible match for a literature description of a ZI Pax6 type.

### 6.3 Broad distributed type — many partial matches

**`0364 L5 ET CTX Glut_2`** — a layer-5 extratelencephalic cortical
glutamatergic cluster (3 740 cells).

| level | near | n_in_X | n_in_or_near_100 | frac_in_or_near_100 |
|---|---|---|---|---|
| division | `Isocortex` | 3 739 | 3 740 | **1.000** |
| structure | `MOs` (secondary motor) | 1 070 | 1 351 | 0.361 |
| structure | `MOp` (primary motor) | 900 | 1 136 | 0.304 |
| structure | `SSp-ul` (somatosensory, upper limb) | 298 | 431 | 0.115 |
| structure | `SSp-ll` (somatosensory, lower limb) | 276 | 401 | 0.107 |
| substructure | `MOs6a` | 642 | 1 101 | 0.294 |
| substructure | `MOp6a` | 564 | 1 021 | 0.273 |
| substructure | `MOs5` | 428 | 874 | 0.234 |
| substructure | `MOp5` | 336 | 769 | 0.206 |

Reading these together (the broad-match pattern): every cell of this cluster
is cortical (division: Isocortex = 1.0), distributed across motor and
somatosensory areas (structure), specifically in deep cortical layers 5/6a
(substructure). No single edge is the "match" — the family of edges
describes the type. *Any fraction cutoff would either erase the broad
pattern (high cutoff) or admit far weaker types (low cutoff).*

### 6.4 Border-only — the case proximity exists to capture

**`3550 PAG-ND-PCG Onecut1 Gaba_3`** — an 11-cell cluster name-tagged to
PAG/ND/PCG.

| near | n_in_X | n_in_or_near_100 | frac_in_or_near_100 |
|---|---|---|---|
| `PCG` (pontine central grey) | 1 | 11 | **1.000** |
| `DTN` (dorsal tegmental nucleus) | 7 | 10 | 0.909 |
| `PAG` (periaqueductal grey) | 2 | 3 | 0.273 |

Only 1 of the 11 cells is *in* PCG. By cell counts alone this looks like a
DTN cluster. The proximity layer reveals that all 11 sit within 100 µm of
PCG's surface — the cluster lives at the PCG/DTN boundary. The taxonomy
name's mention of PCG turns out to be substantively correct, and only the
proximity edge surfaces it.

## 7. Validation

End-to-end checks against the pooled run:

- **Bridge coverage**: every non-zero `parcellation_index` in the volume
  resolves to an MBA CURIE.
- **Alignment self-check**: 88–90 % of 20 000 sampled cells land in their
  assigned region's voxels under the canonical relabel
  (cells in `-unassigned` substructure territories naturally fail this
  check, accounting for the gap).
- **Adjacency spot-checks**: HPF↔TH, HPF↔CTXsp, Isocortex↔OLF, CB↔MB all
  present with substantial contact areas.
- **DOI attribution**: 99.9 % of proximity edges cite both Yao and Zhuang
  DOIs; the handful of single-source edges sit in regions one dataset
  undersamples.
- **ROBOT compilation**: all 8 spatial templates compile end-to-end through
  the OFN-serialising pipeline; cluster OWL builds in ~13 s.

## 8. Implementation

| concern | code |
|---|---|
| volume → region CURIE bridge (shared) | [`src/utils/ccf_parcellation.py`](src/utils/ccf_parcellation.py) |
| region adjacency | [`src/scripts/ccf_spatial/scripts/compute_region_adjacency.py`](src/scripts/ccf_spatial/scripts/compute_region_adjacency.py) |
| per-cell proximity | [`src/scripts/ccf_spatial/scripts/compute_cell_proximity.py`](src/scripts/ccf_spatial/scripts/compute_cell_proximity.py) |
| build orchestration | new targets `ccf-region-adjacency`, `ccf-cell-proximity`, `ccf-spatial` in the [Makefile](Makefile) |
| KG configuration | new OWL URLs added to [`config/collectdata/vfb_fullontologies.txt`](config/collectdata/vfb_fullontologies.txt) |

OWL outputs are serialised in OWL Functional Syntax (OFN) with the `.owl`
extension; the OWL API auto-detects format from content. This keeps every
generated `.owl` under the 100 MB git per-file limit while remaining a
drop-in replacement at every downstream consumer.

## 9. Limitations and next steps

- **Distance bands**: only the 100 µm band is emitted. A future revision
  could add 50 µm and 200 µm as additional `n2o:countInOrNearXum`
  annotations on the same edge if downstream queries want finer or coarser
  thresholds. The pipeline already has the infrastructure to compute them.
- **Human atlas**: the Allen mouse CCF is the only painted volume in scope
  here. The Developing Human Brain Atlas (DHBA v2) under Allen's CCF-MAP
  framework will need a separate pass with its own hierarchy and an
  equivalent shared bridge.
- **Fraction floor**: as discussed in §5.3, an optional
  `frac_in_or_near_100 ≥ 0.005` filter would tighten the long low-fraction
  tail by ~30 % if downstream query performance demands it.
- **Region-region adjacency tolerance**: the current adjacency layer emits
  face-touching pairs only. A second pass could capture pairs separated by
  thin (≤ 50 µm) intervening territories (typically fibre tracts and CSF
  spaces), but in the mouse the resulting set is small.
