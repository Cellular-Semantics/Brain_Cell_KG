# Curvilinear coordinate flatmaps — future work

Status: **parked / aspirational**. Document captures what was learnt during
the 2026-06 exploration of Bhandiwad et al.'s hippocampal flatmap
infrastructure so we can pick it up later without re-deriving.

## 1. Why this matters

Our current spatial cell-type-identity evidence framework
([Purkinje co-location POC](../../reports/purkinje_colocation/README.md))
uses **anchor-based distances**: for each candidate cell, the distance
to a chosen anatomical anchor (Purkinje cells, VLMC) is the geometric
primitive. This is robust and simple. Its limit is that it gives a
*local* answer — relative to the anchor — and doesn't provide a *global,
continuous depth coordinate* through a layered region.

A proper depth coordinate would let us:

- Place every cell on a unified `(depth, surface_x, surface_y)` axis
  per region, comparable across donors, brains, and species.
- Compare topographic gradients across folia / lobules / subfields.
- Reuse the coordinate as input to other analyses (gene-expression
  gradients, connectomics) without recomputing.
- Detect cells that don't fit any layer at all (e.g. our PLI_3 anomaly
  would have an unambiguous depth or no defined depth).

Bhandiwad et al. (2026, biorxiv preprint at
[docs/2026.01.29.702633v2.full.pdf](../2026.01.29.702633v2.full.pdf))
provide exactly this for hippocampus. This document records what
they've done, what it would take to do the same for cerebellum, and
quick wins available without doing the full build.

## 2. The Bhandiwad method in one paragraph

Mark CCFv3 voxels on the meningeal (pia) and ventricular surfaces of
the hippocampal formation. Set Dirichlet boundary conditions
(`u = 0` on pia, `u = 1` on ventricle) and solve **Laplace's equation**
`∇²u = 0` over the HPF volume. The resulting scalar field `u` is
smooth and monotonic from one surface to the other. Integrate
**streamlines** along the gradient `∇u` — these are non-intersecting
paths from each pial voxel to a corresponding ventricular voxel.
Each voxel in the volume is assigned to the nearest streamline, and
its position along that streamline is its **radial depth**. Use
**Isomap** to project the pial surface to a 2D slab, giving a
`(radial_depth, slab_x, slab_y)` curvilinear coordinate triple per
voxel. The output is a per-voxel lookup table from CCF
`(x, y, z)` to flatmap coordinates that handles curvature properly.

Validation in the paper: layer-specific entorhinal projections
(ENTl → outer DG stratum moleculare, ENTm → inner; CA1 stratum
lacunosum-moleculare) land in the expected layers in flatmap space.

## 3. HPF data inventory (from streaming structure probe)

The Allen-hosted file is `P56_HPF.hdf5` at
`https://ansrs-neuroglancer-poc.s3.us-west-2.amazonaws.com/HPF+flatmap/P56_HPF.hdf5`.

Probed structure (cost: 4.1 KB of HTTP via `src/utils/probe_hdf5_url.py`,
no full download):

| Dataset | Shape | dtype | Size | What it almost certainly is |
|---|---|---|---|---|
| `closest_streamline` | (41,284,830, 5) | float64 | ~1.65 GB | Per-voxel lookup: 41 M voxels × 5 fields (likely streamline_id, radial_depth, slab_x, slab_y, residual or weight) |
| `neighbor_map` | (45,834,086, 2, 3) | int64 | ~2.20 GB | Voxel-pair adjacency for streamline / topology rendering — 45 M edges of `(xyz, xyz)` |
| `slab_mask` | (2401, 712, 2) | float32 | ~14 MB | **The 2D flatmap image itself** — 2401 × 712 pixels, 2 channels (probably HPF + DG masks) |
| `slab_space` | (34,609,200, 3) | int32 | ~415 MB | The (x, y, z) coordinates of the 34.6 M voxels making up the slab |

Notable: no compression, no chunking — file would be ~600 MB with
modest gzip+chunks. The whole file is 4 GB but the analysis-essential
parts (`slab_mask` + `closest_streamline`) total ~1.7 GB.

## 4. Allen Institute repositories

| Repo | Purpose | Status |
|---|---|---|
| `AllenInstitute/flatmap` | The Bhandiwad et al. HPF pipeline itself. CLI tools + reference data download script. | Released "AS IS, no support". HPF-only. Depends on a forked `ccf_streamlines`. |
| `AllenInstitute/ccf_streamlines` | Generic streamlines library, originally for isocortex. The base that Bhandiwad et al. forked and adapted for HPF. | Actively maintained. Cortex-focused; arbitrary region support requires fork + custom boundary masks. |
| `AllenInstitute/lamination_station` | Different problem: Bayesian/Pyro model that *discovers* discrete laminae from spatial cell-type points (no boundary annotation needed). | Early development (1 star, no release, no licence). |
| `AllenInstitute/cortical_coordinates` | Isocortex flatmap reference data and scripts. | Active. |

## 5. Effort estimate: cerebellum equivalent

Building a cerebellum flatmap by analogy to Bhandiwad et al.'s HPF
pipeline means forking `ccf_streamlines` and adapting the boundary
masks + solver for cerebellar geometry. Phase-by-phase:

| Phase | Effort | Risk | Notes |
|---|---|---|---|
| 1. Fork `ccf_streamlines`; read Bhandiwad's HPF adaptations | 2-3 days | low | Familiarisation; understand which pieces are HPF-specific vs generic. |
| 2. Define cerebellar pia + WM (arbor vitae) boundary masks from CCFv3 annotations | 3-5 days | **medium** | Arbor vitae is a *branched tree*, not a single connected surface like the hippocampal ventricle. Defining the inner boundary mask is the hardest novel step. |
| 3. Run Laplace solver + streamline integration on cerebellum volume | 1-2 days | low | Standard numerics. Need enough memory for the volume + solver state. |
| 4. Debug fold-tip and folium-junction streamline pathologies | 3-7 days | **high** | Cerebellum is far more folded than HPF; streamlines pinch at deep fold tips. Likely need boundary smoothing or local mesh refinement. |
| 5. 2D Isomap embedding (optional flatmap) | 1-2 days | **high** | Cerebellar pia has ~10× the surface area of its convex hull. Area distortion in 2D may be unusable. The 1D radial coordinate (`depth_along_streamline`) is more likely to be useful than a 2D flatmap. |
| 6. Validation against PCL position, MLI/Golgi layer biology | 2-3 days | low | Check that PCL voxels cluster at `u ≈ 0.5`; MLI voxels at `u < 0.5`; Golgi/Granule at `u > 0.5`. We have the cell positions for this already. |

**Realistic total: 2-3 weeks of focused work.** Best case ~1 week if
the HPF fork turns out to be cleanly generic (unlikely — it depended
on HPF-specific assumptions like a single ventricular surface).

Risk-adjusted recommendation: **the 1D radial coordinate is the part
worth investing in. The 2D flatmap is a stretch goal** and may not
yield a useful representation for cerebellum at all.

## 6. Lamination Station as an alternative

`AllenInstitute/lamination_station` is unrelated to the flatmap
pipeline but addresses a *different* parked question of ours: can we
discover laminae *from cell-type point data* without prior knowledge
of boundary surfaces? (This is what our parked `compute_laminar_eigenmap.py`
DG/CA1 work was trying to do via Laplacian eigenmaps.)

Lamination Station uses a Bayesian/Pyro model to fit discrete laminae
to labelled spatial points. Cleaner stats than our eigenmap approach.

Potential application to cerebellum: feed it the PLI / MLI / Golgi /
Granule cell point data and see whether it independently rediscovers
the PCL / molecular / granular structure. Would be a third
methodological view alongside our anchor-based POC and the (hypothetical)
flatmap approach.

Caveats:
- Repo is in early development (1 star, no releases, no licence
  visible).
- Pyro adds a moderately heavy dependency (probabilistic programming
  language).
- "Bayesian detection of lamination" wording suggests it's looking for
  discrete cluster-like laminae, not continuous coordinates.

## 7. Recommendations

**Now (no action needed).** The anchor-based POC produces interpretable
results for cerebellum and a clean methodological story. The
flatmap detour is not justified by current questions.

**When to revisit:**

- **Hippocampus comes back on the agenda.** Then download
  `P56_HPF.hdf5`'s analysis-essential subsets (`slab_mask` ~14 MB +
  `closest_streamline` ~1.65 GB; skip `neighbor_map` ~2.2 GB which is
  just topology for rendering), and use the existing pipeline directly.
  No new development needed.

- **Multi-region brain-wide analysis** becomes the goal — e.g. comparing
  topographic gradients across cortex, HPF, cerebellum, thalamus in
  unified `(depth, surface_x, surface_y)` coordinates. Then the
  cerebellum flatmap build is worth the 2-3 weeks.

- **An alternative lamina-discovery method is wanted** to compare
  against the anchor-based POC. Then try `lamination_station` on
  cerebellum cells (modest effort: install Pyro, follow the example
  notebook).

## 8. Quick wins available right now

- **Download just the analysis-essential HPF data** (`slab_mask` +
  `closest_streamline`) using HTTP Range reads. Total ~1.7 GB. Could
  be cached at `src/scripts/cell_counts/resources/hpf_flatmap/` or
  similar. Done once, usable indefinitely.

- **Run `src/utils/probe_hdf5_url.py`** against any other ABC Atlas
  HDF5 to map out its structure before deciding whether to download.
  Useful sanity check for any future external data source.

## 9. References

- Bhandiwad et al. 2026, *A curvilinear coordinate flatmap for
  visualizing hippocampal structure and development.* Preprint PDF:
  [docs/2026.01.29.702633v2.full.pdf](../2026.01.29.702633v2.full.pdf)
- `AllenInstitute/flatmap` — https://github.com/AllenInstitute/flatmap
- `AllenInstitute/ccf_streamlines` — https://github.com/AllenInstitute/ccf_streamlines
- `AllenInstitute/lamination_station` — https://github.com/AllenInstitute/lamination_station
- HPF flatmap HDF5 — `https://ansrs-neuroglancer-poc.s3.us-west-2.amazonaws.com/HPF+flatmap/P56_HPF.hdf5`
- Probe script — [src/utils/probe_hdf5_url.py](../../src/utils/probe_hdf5_url.py)
- Current spatial POC — [reports/purkinje_colocation/README.md](../../reports/purkinje_colocation/README.md)
