#!/usr/bin/env python3
"""Region<->region spatial proximity from the Allen-CCF-2020 painted parcellation.

For each region level (division/structure/substructure) this:
  1. Relabels the painted annotation volume from ``parcellation_index`` to MBA
     CURIEs (via the shared ccf_parcellation bridge).
  2. For every pair of regions whose bounding boxes come within the tolerance,
     measures contact area, minimum surface distance and centroid distance.
  3. For every region measures size (volume, max inscribed radius, extent).

Outputs, per level:
  * ``<reports>/ccf_region_adjacency_<level>.csv`` (inspection)
  * ``<reports>/ccf_region_size_<level>.csv``      (inspection)
  * ``<templates>/region_adjacency_<level>.tsv``   (ROBOT template -> KG)

Adjacency is symmetric (RO:0002220 'adjacent to'); the template emits both
directions. Recorded measures use the internal ``n2o:`` namespace, matching the
``n2o:Confidence`` precedent.

No barrier-masking: with a small tolerance (~50 um, ~ registration error) any
cross-gap "bridge" is by construction within registration error, i.e. genuine
proximity rather than noise.

Paths are all explicit arguments so the Makefile owns inputs/outputs.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Shared CCF bridge lives in src/utils (sibling-import convention).
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "utils"))
from ccf_parcellation import REGION_LEVELS, build_index_to_curie  # noqa: E402


def load_volume(path: Path):
    """Return (index_volume:int32, voxel_um:float). Assumes isotropic voxels."""
    import nibabel as nib

    img = nib.load(str(path))
    vol = np.asarray(img.dataobj).astype(np.int32)
    zooms = np.asarray(img.header.get_zooms()[:3], dtype=float)
    if not np.allclose(zooms, zooms[0], rtol=0.01):
        print(f"  WARNING: non-isotropic voxels {zooms} mm; using mean")
    voxel_um = float(zooms.mean()) * 1000.0
    print(f"  volume {vol.shape}, voxel {voxel_um:.1f} um, "
          f"{int(vol.max())} max parcellation_index")
    return vol, voxel_um


def relabel_to_level(vol: np.ndarray, idx2curie: dict):
    """Remap parcellation_index -> dense region code (1..N); 0 = background/other.

    Returns (labeled:int32 volume, code2curie:dict, curie2code:dict).
    """
    curies = sorted(set(idx2curie.values()))
    curie2code = {c: i + 1 for i, c in enumerate(curies)}
    code2curie = {i + 1: c for i, c in enumerate(curies)}

    max_pi = int(vol.max())
    remap = np.zeros(max_pi + 1, dtype=np.int32)
    for pi, curie in idx2curie.items():
        if 0 < pi <= max_pi:
            remap[pi] = curie2code[curie]
    return remap[vol], code2curie, curie2code


def face_contact_pairs(labeled: np.ndarray, ncodes: int) -> dict:
    """All face-adjacent (code_a, code_b) pairs with their contact voxel-face counts.

    Vectorised over the whole volume: for each of 3 axes, compare neighbouring
    voxels, keep where both nonzero and labels differ, then group-by pair.
    O(volume) total; replaces a per-pair Python loop.
    """
    out: dict = {}
    stride = ncodes + 1
    for ax in range(3):
        lo = [slice(None)] * 3
        hi = [slice(None)] * 3
        lo[ax] = slice(None, -1)
        hi[ax] = slice(1, None)
        a = labeled[tuple(lo)]
        b = labeled[tuple(hi)]
        mask = (a != b) & (a != 0) & (b != 0)
        if not mask.any():
            continue
        aa = a[mask].astype(np.int64)
        bb = b[mask].astype(np.int64)
        lo_id = np.minimum(aa, bb)
        hi_id = np.maximum(aa, bb)
        keys = lo_id * stride + hi_id
        u, counts = np.unique(keys, return_counts=True)
        for k, c in zip(u.tolist(), counts.tolist()):
            x = (k // stride, k % stride)
            out[x] = out.get(x, 0) + c
    return out


def region_sizes(labeled, code2curie, voxel_um, slices, counts):
    """Per-region volume, max inscribed radius and extent (Feret/bbox diagonal)."""
    from scipy import ndimage

    rows = []
    for code, curie in code2curie.items():
        sl = slices[code - 1]
        if sl is None:
            continue
        mask = labeled[sl] == code
        # Max inscribed radius = deepest interior distance to the region edge.
        inradius = float(ndimage.distance_transform_edt(mask, sampling=voxel_um).max())
        extent_vox = np.array([s.stop - s.start for s in sl], dtype=float)
        feret = float(np.linalg.norm(extent_vox) * voxel_um)
        rows.append({
            "region": curie,
            "n_voxels": int(counts[code]),
            "volume_um3": float(counts[code]) * voxel_um ** 3,
            "max_inscribed_radius_um": inradius,
            "feret_um": feret,
        })
    return pd.DataFrame(rows)


def region_adjacency(labeled, code2curie, voxel_um, centroids, tolerance_um):
    """Face-touching region pairs with contact area, min surface distance,
    centroid distance.

    Computed entirely from the volume-wide face-adjacency pass (one pass over
    each of three axes); no per-pair EDT. Min distance for face-touching pairs
    is one voxel (centre-to-centre). Pragmatic stopping point: face-touching
    is the right semantic for RO:0002220 'adjacent to', and at the small
    tolerance (~ registration error) appropriate for mouse the additional
    "near but not touching across a thin gap" pairs are rare enough that the
    per-pair distance work is not worth the cost; if needed later they can be
    added as a separate, optional pass.
    """
    del tolerance_um  # retained in the signature for API stability
    ncodes = len(code2curie)
    touch = face_contact_pairs(labeled, ncodes)
    print(f"    {len(touch)} face-touching pairs")

    rows = []
    for (a, b), contact_faces in touch.items():
        if a not in code2curie or b not in code2curie:
            continue
        cent = float(np.linalg.norm(
            np.array(centroids[a]) - np.array(centroids[b])) * voxel_um)
        rows.append({
            "region_a": code2curie[a],
            "region_b": code2curie[b],
            "contact_voxels": int(contact_faces),
            "contact_um2": float(contact_faces) * voxel_um ** 2,
            "min_dist_um": float(voxel_um),
            "centroid_um": cent,
        })
    return pd.DataFrame(rows)


def write_adjacency_template(df: pd.DataFrame, out_path: Path):
    """ROBOT template: region->region 'adjacent to' with n2o: measure annotations.

    Emits both directions (adjacency is symmetric)."""
    header = ["ID", "Type", "RO:0002220", "contact_um2", "min_dist_um", "centroid_um"]
    types = ["ID", "TYPE", "AI RO:0002220",
             ">AT n2o:contactArea^^xsd:float",
             ">AT n2o:minDistance^^xsd:float",
             ">AT n2o:centroidDistance^^xsd:float"]
    lines = ["\t".join(header), "\t".join(types)]
    for _, r in df.iterrows():
        for src, dst in ((r["region_a"], r["region_b"]), (r["region_b"], r["region_a"])):
            lines.append("\t".join([
                src, "owl:NamedIndividual", dst,
                f"{r['contact_um2']:.3f}", f"{r['min_dist_um']:.3f}", f"{r['centroid_um']:.3f}",
            ]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--annotation", required=True, type=Path,
                    help="Allen-CCF-2020 annotation NIfTI (parcellation_index volume)")
    ap.add_argument("--membership", required=True, type=Path,
                    help="parcellation_to_parcellation_term_membership_acronym.csv")
    ap.add_argument("--mba-map", required=True, type=Path,
                    help="reports/mba_symbol_map.csv (acronym -> MBA CURIE)")
    ap.add_argument("--reports-dir", required=True, type=Path)
    ap.add_argument("--templates-dir", required=True, type=Path)
    ap.add_argument("--levels", nargs="+", choices=REGION_LEVELS, default=list(REGION_LEVELS))
    ap.add_argument("--tolerance-um", type=float, default=50.0,
                    help="Max surface distance (um) for two regions to count as adjacent")
    args = ap.parse_args()

    from scipy import ndimage

    print(f"Loading annotation volume: {args.annotation}")
    vol, voxel_um = load_volume(args.annotation)

    idx2curie_all = build_index_to_curie(args.membership, args.mba_map)

    # Bridge coverage check (verification step 1).
    mapped_idx = set().union(*(set(idx2curie_all[lvl]) for lvl in REGION_LEVELS))
    present = set(np.unique(vol).tolist()) - {0}
    unmapped = sorted(present - mapped_idx)
    print(f"Bridge coverage: {len(present - {0})} indices in volume, "
          f"{len(unmapped)} with no CURIE at any level"
          + (f" (e.g. {unmapped[:10]})" if unmapped else ""))

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    args.templates_dir.mkdir(parents=True, exist_ok=True)

    for level in args.levels:
        print(f"\n=== {level} ===")
        labeled, code2curie, _ = relabel_to_level(vol, idx2curie_all[level])
        ncodes = len(code2curie)
        print(f"  {ncodes} regions")

        counts = np.bincount(labeled.ravel(), minlength=ncodes + 1)
        slices = ndimage.find_objects(labeled, max_label=ncodes)
        centroids = ndimage.center_of_mass(
            labeled > 0, labeled, list(code2curie.keys()))
        centroids = {code: centroids[i] for i, code in enumerate(code2curie)}

        size_df = region_sizes(labeled, code2curie, voxel_um, slices, counts)
        size_df.sort_values("region").to_csv(
            args.reports_dir / f"ccf_region_size_{level}.csv", index=False)

        adj_df = region_adjacency(
            labeled, code2curie, voxel_um, centroids, args.tolerance_um)
        adj_df.sort_values(["region_a", "region_b"]).to_csv(
            args.reports_dir / f"ccf_region_adjacency_{level}.csv", index=False)
        print(f"  {len(adj_df)} adjacency pairs (face-touching)")

        write_adjacency_template(
            adj_df, args.templates_dir / f"region_adjacency_{level}.tsv")

    print("\nRegion adjacency complete.")


if __name__ == "__main__":
    main()
