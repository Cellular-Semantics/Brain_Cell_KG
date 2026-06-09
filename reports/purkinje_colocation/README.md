# Anchor-based spatial co-location scoring: Purkinje as a proof of concept

## 1. Goal

Score cell types for spatial co-location with one or more "anchor" types,
as evidence for shared cellular identity or shared anatomical niche. The
hypothesis is that cell types whose cells consistently sit in
characteristic positions relative to known anchors share location-
determined biology (e.g. occupy the same layer, integrate into the same
circuit), and that the strength and pattern of this co-location is
quantitative evidence about cell-type identity.

The cerebellar Purkinje cell layer (PCL) is the proof-of-concept system.
Two anchors are used:

- **Purkinje cells** (`313 CBX Purkinje Gaba`, 18 030 cells in Yao
  MERFISH). Transcriptomically unambiguous; form a thin monolayer
  (the PCL) running through every cerebellar folium; the PCL separates
  molecular layer (pial side) from granular layer (white-matter side).
- **Vascular leptomeningeal cells** (`330 VLMC NN`, 70 506 cells).
  Pia residents — provide an independent anatomical reference for "the
  surface of the brain".

The candidate cell types tested here are the cerebellar GABAergic and
glutamatergic populations expected to fall in or adjacent to the PCL:

| Subclass / supertype | Expected layer |
|---|---|
| `309 CB PLI Gly-Gaba` (subclass + 4 supertypes 1144–1147) | Purkinje layer interneurons — in the PCL |
| `311 CBX MLI Megf11 Gaba` | Molecular layer (inner) |
| `312 CBX MLI Cdh22 Gaba` | Molecular layer (outer) |
| `310 CBX Golgi Gly-Gaba` | Granular layer (just below PCL) |
| `314 CB Granule Glut` | Granular layer (filling) |
| `315 DCO UBC Glut` | Granular layer (unipolar brush cells) |

## 2. Data

Single source: Yao MERFISH single-brain dataset
(`MERFISH-C57BL6J-638850-CCF`, ~3.74 M cells, CCFv3-registered, single
donor). Used because cell coordinates and the full taxonomy (subclass,
supertype, cluster) are in one CSV with no cross-brain registration
issues.

Per-cell columns used:
- 3D position `(x_ccf, y_ccf, z_ccf)` in CCFv3 mm
- `subclass`, `supertype`, `cluster` (auto-detected per cell-type label)
- `parcellation_substructure` (sanity-check only, not used in scoring)

## 3. Two analytical methods

Two methods were developed in this POC and are kept as parallel views.
**Read §4 (naive distance method) as the primary approach** — it is
simpler, more robust, and the recommended starting point. §5 (sheet-frame
decomposition) is a refinement for questions that require a within-PCL
geometric frame.

A direct comparison is in §6.

## 4. Naive two-anchor distance method (primary)

### 4.1 The measurement

For each non-anchor cell `M`, compute two scalar distances:

```
    d_PC(M)   = 3D distance from M to its nearest Purkinje cell    (mm)
    d_VLMC(M) = 3D distance from M to its nearest VLMC cell        (mm)
```

That is the entire per-cell computation. Two `cKDTree.query(..., k=1)`
calls. No PCA, no sheet normal, no polarity orientation.

### 4.2 What (d_PC, d_VLMC) means geometrically

In a perpendicular section of mouse cerebellar cortex (~350 µm thick),
position in this plane reads as anatomical depth:

| Position in (d_VLMC, d_PC) | Layer |
|---|---|
| `d_VLMC ≈ 0`, `d_PC ≈ 175` | pial surface |
| `d_VLMC ≈ 100`, `d_PC ≈ 75` | outer molecular layer |
| `d_VLMC ≈ 175`, `d_PC ≈ 0` | PCL |
| `d_VLMC ≈ 250`, `d_PC ≈ 75` | granular layer (mid) |
| `d_VLMC ≈ 325`, `d_PC ≈ 150` | white matter boundary |

A perpendicular slice traces out a V-shape in the (d_VLMC, d_PC) plane,
with the apex at the PCL. Different cell types occupy different
positions along this V; identity-consistent types cluster in the same
region of the plane.

### 4.3 Per-type summary statistic

For each candidate type `c` in the universe (cells within
`R = 1.0 mm` of a Purkinje), report median `d_PC` and median `d_VLMC`.
Median (not mean) because both distance distributions are skewed; the
median is the conventional robust summary.

### 4.4 Score and significance

The same one-sided permutation test from §5.4 applies to either distance,
or to a chosen combination (e.g. `d_PC` alone). It is currently computed
only on `d_PC` (the original sheet-frame implementation), so the
significance test in §5 carries over to the naive method's `d_PC`
column without modification.

### 4.5 Naive-method results

Restricting to cells within 1.0 mm of a Purkinje (universe = 285 054
cells), per-type medians:

| Type | n | median d_PC (µm) | median d_VLMC (µm) | Layer call |
|---|---|---|---|---|
| 1144 CB PLI Gly-Gaba_1 | 3376 | **28** | **162** | PCL (canonical) |
| 309 CB PLI Gly-Gaba (sub) | 4229 | 34 | 161 | PCL |
| 1145 CB PLI Gly-Gaba_2 | 207 | 48 | 186 | PCL, slight WM bias |
| 310 CBX Golgi Gly-Gaba | 1487 | 77 | **183** | granular (WM side of PCL) |
| 1147 CB PLI Gly-Gaba_4 | 324 | 79 | **137** | molecular (pial side) |
| 311 CBX MLI Megf11 Gaba | 76 167 | 98 | 109 | inner molecular |
| 314 CB Granule Glut | 183 974 | 115 | **183** | granular |
| 312 CBX MLI Cdh22 Gaba | 17 455 | 129 | **99** | outer molecular |
| **1146 CB PLI Gly-Gaba_3** | 322 | **158** | **156** | PCL-depth, Purkinje-distant |
| **315 DCO UBC Glut** | 1742 | **328** | 129 | not cerebellar cortex |

Headline findings:

- **MLI inner/outer distinction reads directly off `d_VLMC`.** MLI Megf11
  (d_VLMC = 109) is more PCL-proximal than MLI Cdh22 (d_VLMC = 99,
  closer to pia). This matches the molecular-layer outer/inner
  organisation described in the literature.
- **Granule cells and Golgi correctly placed on the WM side**
  (`d_VLMC` 183 µm — deeper than PCL reference 161 µm). MLI types
  correctly on the pial side (`d_VLMC` ≪ 161 µm).
- **`315 DCO UBC Glut` is flagged as not-cerebellar-cortex** (`d_PC`
  = 328 µm — far from any Purkinje). The "DCO" prefix is correct: this
  subclass is anchored in dorsal cochlear nucleus, not cerebellum
  proper. The naive method surfaces this without any prior anatomical
  knowledge.
- **`1146 CB PLI Gly-Gaba_3` is geometrically anomalous in a new way.**
  Its median d_VLMC = 156 µm is essentially identical to the canonical
  PCL d_VLMC (161 µm — i.e. at PCL pia-depth), but its median d_PC =
  158 µm — far from the nearest Purkinje. So the cells sit at the same
  depth as the PCL but are not Purkinje-adjacent. Possible
  interpretation: PLI_3 cells reside at PCL-equivalent depth in regions
  with sparse local Purkinje density, or in a sub-region of cerebellum
  (e.g. lobule boundary) where they are spatially decoupled from the
  canonical PCL.

Files (all paths relative to repo root):
- `reports/purkinje_colocation/purkinje_naive_distances.tsv` — per-type summary
- `reports/purkinje_colocation/purkinje_naive_distances_cells.csv` — per-cell (xyz + d_PC + d_VLMC + taxonomy); large (~32 MB), `.gitignore`d, regenerated by the compute script
- `reports/purkinje_colocation/figures/purkinje_naive_distances.png` — facet plot + overlay

### 4.6 Why this is the primary method

- **Robustness.** Per-cell measurement is two scalar distances. There
  is no sign, no PCA, no normal flipping, no polarity reference — so
  none of those steps can fail. The wrong-side cells that plagued the
  sheet-frame method (§5.6, §6) do not exist here by construction.
- **Layer assignment without sheet assumptions.** The method makes no
  assumption that the PCL is locally flat or that it has a well-defined
  normal. Cells in heavily folded regions, at folium tips, and away
  from the PCL all get clean numbers.
- **Flagging non-cerebellar types** (UBC, brainstem-leaking subclasses)
  falls out for free — large `d_PC` means "not near any Purkinje".
- **Interpretable to non-specialists.** "This cell is 70 µm from a
  Purkinje and 220 µm from the pia" is plain-language.

## 5. Sheet-frame decomposition method (refinement)

### 5.1 What it gives that the naive method does not

The naive method cannot distinguish "tangentially next to a Purkinje
within the sheet" from "perpendicularly above a Purkinje outside the
sheet". Both look like the same small `d_PC`. The sheet-frame method
decomposes each cell's displacement to its nearest Purkinje into:

- `tangent` (in-plane lateral distance, always ≥ 0)
- `normal` (perpendicular to local PCL plane; unsigned magnitude, or
  signed if a polarity reference is supplied)

This is useful when the question is specifically whether a cell sits
*within* the PCL plane or *above/below* it — e.g. PLI vs slightly-pial
small interneurons.

### 5.2 Universe definition (shared with §4)

For radius `R`, the universe is the set of all non-anchor cells in the
dataset whose 3D nearest-neighbour distance to any anchor (Purkinje)
cell is ≤ `R`. We use `R ∈ {0.1, 0.3, 1.0}` mm.

We deliberately avoid CCF parcellation labels for the universe because
registration imperfection at thin layers (PCL ~50 µm) makes
parcellation substructure unreliable. The anchor-conditioned universe
includes or excludes purely by measured 3D proximity to Purkinje.

### 5.3 The score statistic

For each candidate type `c` at radius `R`, let `d_i` be the NN distance
(mm) from each cell `i` of type `c` (in the universe) to its closest
Purkinje. The score is

```
    score_c(R) = exp( mean_log_NN_universe(R) − mean_log_NN_c(R) )
```

where the means are over the natural log of `d_i` (floored at 1 µm to
avoid `log(0)` from registration ties).

Interpretation:
- `score > 1` ⇒ type `c` sits closer to anchor than the universe-average
  cell.
- `score = 1` ⇒ same as universe.
- `score < 1` ⇒ farther than universe.

Log domain is used because the NN distance distribution is heavy-tailed
— a handful of cells with `d > 0.5 mm` would dominate a linear mean.

### 5.4 Permutation p-value

Null hypothesis: cells of type `c` in the universe are a random draw
with respect to their NN-to-Purkinje distance.

Procedure per candidate:
1. Let `N_c` = number of `c` cells in the universe.
2. Repeat `n_perm = 1000` times: draw `N_c` indices uniformly without
   replacement from the universe, compute the mean log NN of that
   random sample.
3. `p = (#shuffles ≤ observed + 1) / (n_perm + 1)`.

With 1000 permutations the smallest reportable `p` is `1/1001 ≈ 0.001`.

### 5.5 Local PCL sheet frame: normal and tangent

For each Purkinje cell `P`, fit a local plane to its 20 nearest Purkinje
neighbours by 3D PCA. The eigenvector of the local 3×3 covariance with
the smallest eigenvalue is the unit normal `n_P` to the PCL at `P`.

For each non-anchor cell `M` with nearest Purkinje `P*`:
- displacement `Δ = M − P*`
- `signed_normal = Δ · n_{P*}`
- `tangent = sqrt(|Δ|² − signed_normal²)` (always ≥ 0)
- `normal = |signed_normal|` (unsigned, used in the score TSV)

To convert unsigned normal into *signed* normal, use VLMC as a polarity
reference. For each Purkinje cell `P`:

1. Find P's 5 nearest VLMC cells.
2. Compute mean of those positions, subtract `P` → vector toward local
   pia.
3. If `n_P · (that direction) < 0`, flip `n_P`.

After this every `n_P` points toward pia; positive signed normal = pial
side, negative = WM side.

### 5.6 Sheet-frame results (1000 permutations, R = 1.0 mm)

Sorted by score descending:

| Type | level | n in universe | median NN (µm) | score | p |
|---|---|---|---|---|---|
| 1144 CB PLI Gly-Gaba_1 | supertype | 3376 | 28.3 | **6.03** | <0.001 |
| 309 CB PLI Gly-Gaba | subclass | 4229 | 33.7 | **5.04** | <0.001 |
| 1145 CB PLI Gly-Gaba_2 | supertype | 207 | 48.2 | 4.12 | <0.001 |
| 310 CBX Golgi Gly-Gaba | subclass | 1487 | 76.9 | 3.46 | <0.001 |
| 311 CBX MLI Megf11 Gaba | subclass | 76 167 | 97.7 | 2.72 | <0.001 |
| 1147 CB PLI Gly-Gaba_4 | supertype | 324 | 79.0 | 2.47 | <0.001 |
| 312 CBX MLI Cdh22 Gaba | subclass | 17 455 | 128.7 | 1.97 | <0.001 |
| **1146 CB PLI Gly-Gaba_3** | supertype | 322 | **157.9** | **1.79** | <0.001 |

All types are significantly closer to Purkinje than a random
cerebellar-vicinity cell (every `p < 0.001`). Score gradient matches
the expected anatomical proximity: PLI > Golgi > MLI > anomalous PLI_3.

Mean signed normal per type, from the polarity-oriented sheet frame
(positive = pial side, negative = WM side):

| Type | mean signed normal (µm) | % cells pial side |
|---|---|---|
| 312 CBX MLI Cdh22 Gaba | **+47** | 74% |
| 311 CBX MLI Megf11 Gaba | **+37** | 71% |
| 1147 CB PLI Gly-Gaba_4 | +6 | 60% |
| 1144 CB PLI Gly-Gaba_1 | +3 | 54% |
| 309 CB PLI Gly-Gaba (sub) | +1 | 51% |
| 1145 CB PLI Gly-Gaba_2 | −12 | 40% |
| 310 CBX Golgi Gly-Gaba | −19 | 40% |
| 1146 CB PLI Gly-Gaba_3 | −20 | 39% |
| 314 CB Granule Glut | −26 | 36% |
| 315 DCO UBC Glut | −36 | 29% |

Files (all paths relative to repo root):
- `reports/purkinje_colocation/colocation_purkinje_anchor.tsv` — score + permutation table
- `reports/purkinje_colocation/figures/purkinje_colocation_signed.png` — sheet-frame facet plot (current; uses VLMC polarity orientation, signed normal)
- `reports/purkinje_colocation/figures/purkinje_colocation_sheet_frame.png` — early variant of the same figure with *unsigned* normal (no VLMC polarity step). Kept as a historical reference for how the analysis evolved; superseded by the signed version above for actual interpretation.

### 5.7 Why mean signed normal, not median

When normals have noise, cells genuinely close to the PCL have signed
normals scattered around zero. The *median* of such a distribution
collapses to ≈0 even when the underlying population is asymmetric.
The *mean* exposes the asymmetry. For reporting layer side from the
sheet-frame method, we use the mean.

## 6. Method comparison

The two methods agree on the broad layer assignments but diverge in
important details, and each surfaces information the other misses.

| Question | Naive (§4) | Sheet-frame (§5) |
|---|---|---|
| Inner vs outer molecular (Megf11 vs Cdh22) | Yes — direct from d_VLMC | Yes — direct from signed normal |
| Pial vs WM side (MLI vs Golgi) | Yes — d_VLMC | Yes — sign of normal |
| PLI cells are *in* the sheet | Inferred from low d_PC + PCL-equivalent d_VLMC | Direct: small unsigned normal |
| Tangent vs normal distance to nearest Purkinje | Not separated (only |Δ|) | Separated |
| Flag non-cerebellar types (e.g. UBC) | Direct (high d_PC) | Cannot — projects every cell onto the sheet |
| Effect of folding | Mild (just affects distance, not category) | Severe (can sign-flip per-cell normal) |

**Where the methods disagree on PLI_3 (1146):**

- **Sheet-frame** says PLI_3 is "on the granular-layer side of the PCL"
  (mean signed normal = −20 µm, 39% pial fraction).
- **Naive** says PLI_3 sits "at PCL pia-depth (d_VLMC = 156 µm,
  effectively the canonical PCL d_VLMC) but ~158 µm from its nearest
  Purkinje" — i.e. **at the PCL anatomically, but spatially decoupled
  from the Purkinje monolayer**.

These are not strictly contradictory but they tell very different
stories. The naive interpretation is more directly supported by the
data because no PCA or polarity step contributes noise. The
sheet-frame interpretation is partly a methodological artefact: when
PLI_3 cells happen to have a Purkinje as nearest neighbour but are 158
µm tangentially distant, the relative depth signal (signed normal) is
noisy and could read negative for non-anatomical reasons.

**Recommendation for downstream users:** trust the naive (d_PC, d_VLMC)
interpretation as the primary view, and use the sheet-frame as a
within-PCL refinement (e.g. to separate "in-sheet PLI" from "just-above
PCL early MLI" types).

## 7. Caveats and known noise sources

**Common to both methods:**

1. **CCF registration error.** Yao MERFISH registration to CCFv3 has
   spatial error of tens of microns. For thin layers (PCL ~50 µm), this
   alone can place a cell on the wrong side of its real layer
   regardless of the method.

2. **Transcriptomic edge cases.** The WMB taxonomy is not perfect.
   Cells whose transcriptomic profile sits between two subclasses can
   be assigned to either, and the spatial interpretation may differ.

3. **The PCL is not always one cell thick.** In some lobules Purkinje
   somata are slightly staggered, blurring the "sheet" assumption
   locally.

4. **Folding-induced "nearest" can cross a fold.** A cell in folium A's
   molecular layer may have its nearest Purkinje in folium B's PCL
   across a narrow fold. The naive method records this as a small d_PC
   (the distance is real and small) but the cell is not biologically
   "near A's PCL" — it just happens to be near B's PCL. This is
   noticeable only at deep folds and tends to affect a small fraction
   of cells.

**Sheet-frame-specific (§5):**

5. **PCA-of-neighbours fails at fold bases.** A Purkinje cell whose
   20 nearest Purkinje neighbours include cells from both leaflets of a
   fold gets a PCA normal that is neither leaflet's true sheet normal.
   Any candidate cell whose nearest-PC happens to be this confused PC
   gets a randomly-signed normal.

6. **Polarity ambiguity at fold bases.** The 5-NN VLMC averaging
   mitigates but doesn't eliminate the case where opposing pias
   contribute to the polarity direction.

7. **Sign ambiguity for cells in the PCL.** A PLI cell sitting in the
   sheet has very small `|Δ|`. The component along `n_P` is dominated
   by local jitter (PCL non-flatness, sub-cellular position,
   registration error). Sign of signed_normal is essentially a coin
   flip — canonical PLI types correctly read ~50/50 pial/WM. The mean
   signed normal stays near zero for these (correctly).

8. **Number of permutations bounds the minimum p.** At `n_perm=1000`,
   no p can be below `1/1001 ≈ 0.001`. All listed types reach this
   floor; to distinguish among the top PLI variants we would need
   `n_perm = 10⁴` or higher.

## 8. Reproducibility

### 8.1 Scripts

| Script | What it does |
|---|---|
| `src/scripts/cell_counts/purkinje_colocation/compute_purkinje_naive_distances.py` | Per-cell d_PC and d_VLMC; writes per-cell CSV and per-type summary TSV |
| `src/scripts/cell_counts/purkinje_colocation/plot_purkinje_naive_distances.py` | Facet figure for the (d_VLMC, d_PC) plane |
| `src/scripts/cell_counts/purkinje_colocation/compute_purkinje_colocation.py` | Sheet-frame score + permutation test |
| `src/scripts/cell_counts/purkinje_colocation/plot_purkinje_colocation.py` | Sheet-frame (tangent, signed normal) facet figure |

### 8.2 Naive method (primary)

```
python src/scripts/cell_counts/purkinje_colocation/compute_purkinje_naive_distances.py \
  --yao-csv src/scripts/cell_counts/resources/aba_cache/metadata/MERFISH-C57BL6J-638850-CCF/20231215/views/cell_metadata_with_parcellation_annotation.csv \
  --out-cells reports/purkinje_colocation/purkinje_naive_distances_cells.csv \
  --out-summary reports/purkinje_colocation/purkinje_naive_distances.tsv

python src/scripts/cell_counts/purkinje_colocation/plot_purkinje_naive_distances.py \
  --cells-csv reports/purkinje_colocation/purkinje_naive_distances_cells.csv \
  --output reports/purkinje_colocation/figures/purkinje_naive_distances.png
```

### 8.3 Sheet-frame method (refinement)

```
python src/scripts/cell_counts/purkinje_colocation/compute_purkinje_colocation.py \
  --yao-csv src/scripts/cell_counts/resources/aba_cache/metadata/MERFISH-C57BL6J-638850-CCF/20231215/views/cell_metadata_with_parcellation_annotation.csv \
  --n-permutations 1000 \
  --output reports/purkinje_colocation/colocation_purkinje_anchor.tsv

python src/scripts/cell_counts/purkinje_colocation/plot_purkinje_colocation.py \
  --yao-csv src/scripts/cell_counts/resources/aba_cache/metadata/MERFISH-C57BL6J-638850-CCF/20231215/views/cell_metadata_with_parcellation_annotation.csv \
  --output reports/purkinje_colocation/figures/purkinje_colocation_signed.png
```

### 8.4 Key parameters

| Parameter | Default | Where to change |
|---|---|---|
| `SHEET_K` (PC neighbours for PCA normal) | 20 | top of `compute_purkinje_colocation.py` |
| Polarity averaging k | 5 | `orient_normals_by_polarity(k=5)` |
| Universe radius (R) | 1.0 mm primary; also 0.1, 0.3 for score | `--universe-radius-mm`, `--radii-mm` |
| Permutations | 1000 | `--n-permutations` |
| Universe distance floor for log | 1 µm | `MIN_DISTANCE_MM` |

## 9. Next steps

- **Apply the naive method to PLI_3 spatially.** PLI_3 has the PCL-depth
  signature (`d_VLMC ≈ 161 µm`) but the high d_PC; mapping where
  exactly these cells sit in CCF coords might reveal a sub-region of
  cerebellum where they cluster, or a region outside cerebellum where
  they were transcriptomically mislabelled.
- **Add the permutation test on `d_VLMC`** in the naive script (currently
  only `d_PC` has a significance test, inherited from the sheet-frame
  pipeline).
- **Bump `n_perm` to 10⁴+** so top-scoring PLI variants can be ranked
  rather than all hitting the p-floor.
- **Test the folding-noise hypothesis empirically** for the sheet-frame
  method (per-MLI: distance to nearest PC and distance from that PC to
  nearest VLMC; wrong-side cells should cluster at large values of both
  if folding is the dominant noise source).
- **Add other sheet anchors** beyond Purkinje. Candidates: mitral cells
  (olfactory bulb), CA pyramidal cells, DG granule cells, TRN — applying
  the same dual-distance framework to other layered regions.
- **Extend to multi-anchor fingerprints.** Each cell could be tagged with
  distances to a panel of 5–10 brain-wide anchors. Each type's median
  vector across anchors becomes a low-dimensional fingerprint usable as
  evidence of identity that is independent of CCF parcellation entirely.

## 10. Method limitations summary

The naive (d_PC, d_VLMC) method ranks types by spatial proximity to
Purkinje cells and assigns them to layers via their distance to the
pia. It is robust because per-cell measurements are pure scalar
distances. Its main limitation is that it cannot separate "in-sheet" from
"slightly off-sheet" — both look like small d_PC.

The sheet-frame method adds an in-sheet/off-sheet decomposition by
fitting a local plane via PCA on Purkinje neighbours and signing the
normal via VLMC polarity. It is more informative for within-PCL
geometry questions but more vulnerable to fold artefacts and
sign-ambiguity near the sheet. Per-cell layer assignment is therefore
unreliable; population-level means are robust.

Both methods are most informative when used to rank many candidate
types or to identify type-level anomalies (such as PLI_3), and least
informative when used to make hard yes/no claims about an individual
cell.
