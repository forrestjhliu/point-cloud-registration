"""Audit small author-provided metadata; never downloads point clouds or weights.

Run with an existing Python environment containing NumPy and requests.
Input pickle deserialization is restricted to the NumPy array/scalar types used
by these metadata files. Outputs use exclusive creation to protect existing work.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pickle
import re

import numpy as np
import requests


ROOT = Path(__file__).resolve().parent
META = ROOT / "registration_metadata"
GEO_COMMIT = "e7a135af4c318ff3b8d7f6c963df094d7e4ea540"
PREDATOR_COMMIT = "8c78f125fc58d62ad7d149adf1fed43ed54937e4"
GEO_BASE = f"https://raw.githubusercontent.com/qinzheng93/GeoTransformer/{GEO_COMMIT}/data/3DMatch/metadata/"
PREDATOR_BASE = f"https://raw.githubusercontent.com/prs-eth/OverlapPredator/{PREDATOR_COMMIT}/configs/indoor/"


class RestrictedUnpickler(pickle.Unpickler):
    ALLOWED = {
        ("numpy.core.multiarray", "_reconstruct"),
        ("numpy.core.multiarray", "scalar"),
        ("numpy", "ndarray"),
        ("numpy", "dtype"),
    }

    def find_class(self, module, name):
        if (module, name) not in self.ALLOWED:
            raise pickle.UnpicklingError(f"Forbidden global: {module}.{name}")
        return super().find_class(module, name)


def load(name):
    with (META / name).open("rb") as stream:
        return RestrictedUnpickler(stream).load()


def as_rows(predator):
    return [
        {
            "pcd0": ref,
            "pcd1": src,
            "scene_name": Path(src).parts[-2],
            "rotation": predator["rot"][index],
            "translation": np.asarray(predator["trans"][index]).reshape(3),
            "overlap": predator["overlap"][index],
        }
        for index, (ref, src) in enumerate(zip(predator["tgt"], predator["src"]))
    ]


def describe(rows, originals):
    overlaps = np.array([row["overlap"] for row in rows], dtype=float)
    scene_counts = Counter(row["scene_name"] for row in rows)
    mapping = {}
    for sequence in sorted(scene_counts):
        candidates = [s for s in originals if sequence == s or sequence.startswith(s + "_")]
        mapping[sequence] = max(candidates, key=len) if candidates else None
    histogram, edges = np.histogram(overlaps, bins=[0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.000001])
    unique_fragments = {name for row in rows for name in (row["pcd0"], row["pcd1"])}
    return {
        "pairs": len(rows),
        "metadata_sequence_names": len(scene_counts),
        "original_scene_archives_matched_by_name_prefix": len(set(mapping.values())),
        "mapping_method": "Exact original archive name, otherwise longest original archive prefix plus underscore. This is a name-based mapping, not a point-cloud identity test.",
        "unmapped_sequences": [key for key, val in mapping.items() if val is None],
        "pairs_by_sequence": dict(sorted(scene_counts.items())),
        "sequence_to_original_scene": mapping,
        "unique_fragment_paths": len(unique_fragments),
        "overlap_column": {
            "min_q25_median_q75_max": np.quantile(overlaps, [0, .25, .5, .75, 1]).tolist(),
            "mean": float(overlaps.mean()),
            "bins_left_inclusive_right_exclusive_except_last": edges.tolist(),
            "bin_counts": histogram.tolist(),
            "below_0_1": int(np.sum(overlaps < .1)),
            "below_0_3": int(np.sum(overlaps < .3)),
            "above_0_3": int(np.sum(overlaps > .3)),
            "interpretation": "Values of this particular metadata field; do not equate to physical occlusion fraction or independently measured geometric overlap.",
        },
    }


def intersections(first, second):
    first_map = {(r["pcd0"], r["pcd1"]): r for r in first}
    second_map = {(r["pcd0"], r["pcd1"]): r for r in second}
    common = first_map.keys() & second_map.keys()
    first_frag = {p for r in first for p in (r["pcd0"], r["pcd1"])}
    second_frag = {p for r in second for p in (r["pcd0"], r["pcd1"])}
    return {
        "shared_sequence_names": sorted({r["scene_name"] for r in first} & {r["scene_name"] for r in second}),
        "shared_directed_pair_paths": len(common),
        "shared_fragment_paths": len(first_frag & second_frag),
        "shared_pair_ground_truth_identical": all(
            np.array_equal(first_map[k]["rotation"], second_map[k]["rotation"])
            and np.array_equal(first_map[k]["translation"], second_map[k]["translation"])
            for k in common
        ) if common else None,
        "shared_pairs": [list(pair) for pair in sorted(common)],
    }


def main():
    outputs = [ROOT / "registration_audit.json", ROOT / "registration_audit.txt"]
    if any(path.exists() for path in outputs):
        raise FileExistsError("Refusing to overwrite an existing audit output.")
    response = requests.get("https://3dmatch.cs.princeton.edu/", timeout=20)
    response.raise_for_status()
    originals = sorted(set(re.findall(r'/rgbd-datasets/([^/"\s]+)\.zip', response.text)))
    assert len(originals) == 62, "Official scene list changed; inspect before interpreting counts."
    datasets = {name: load(name + ".pkl") for name in ("train", "val", "3DMatch", "3DLoMatch")}
    predator = {name: as_rows(load("predator_" + name + ".pkl")) for name in ("val_info", "3DMatch", "3DLoMatch")}
    downloads = []
    for path in sorted(META.iterdir()):
        if path.name.startswith("predator_"):
            url = PREDATOR_BASE + path.name[len("predator_"):]
        elif path.suffix == ".txt":
            url = GEO_BASE + "split/" + path.name
        else:
            url = GEO_BASE + path.name
        downloads.append({"file": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pinned_source": url})
    comparisons = {}
    for name, pred_name in (("val", "val_info"), ("3DMatch", "3DMatch"), ("3DLoMatch", "3DLoMatch")):
        first, second = datasets[name], predator[pred_name]
        comparisons[name] = {
            "same_ordered_pairs": len(first) == len(second) and all((a["pcd0"], a["pcd1"]) == (b["pcd0"], b["pcd1"]) for a, b in zip(first, second)),
            "identical_rotation_translation": len(first) == len(second) and all(np.array_equal(a["rotation"], b["rotation"]) and np.array_equal(a["translation"], b["translation"]) for a, b in zip(first, second)),
            "overlap_columns_identical": all(a["overlap"] == b["overlap"] for a, b in zip(first, second)),
        }
    audit = {
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Small metadata only. No point clouds, RGB-D frames, weights, or large dataset archives were downloaded; no registration model was run.",
        "metadata_total_bytes": sum(item["bytes"] for item in downloads),
        "downloads": downloads,
        "official_protocol": {
            "3dmatch_original": "62 real indoor RGB-D scenes; original paper splits 54 training / 8 testing. Each benchmark fragment fuses 50 depth frames using TSDF.",
            "geotransformer_paper": "Paper section 4.1 states 46 training / 8 validation / 8 testing scenes. This is a literature statement, not what the downloaded current metadata count shows.",
            "nominal_overlap": "3DMatch >30%; 3DLoMatch 10-30%. Benchmark membership is fixed by author-provided pair lists. Actual overlap columns differ between implementations and do not always obey the nominal intervals.",
            "original_3dmatch_paper": "https://arxiv.org/pdf/1603.08182",
            "geotransformer_paper_url": "https://openaccess.thecvf.com/content/CVPR2022/papers/Qin_Geometric_Transformer_for_Fast_and_Robust_Point_Cloud_Registration_CVPR_2022_paper.pdf",
            "predator_paper_url": "https://openaccess.thecvf.com/content/CVPR2021/papers/Huang_Predator_Registration_of_3D_Point_Clouds_With_Low_Overlap_CVPR_2021_paper.pdf",
        },
        "geotransformer_metadata_measured": {name: describe(rows, originals) for name, rows in datasets.items()},
        "predator_metadata_measured": {name: describe(rows, originals) for name, rows in predator.items()},
        "cross_implementation_comparison": comparisons,
        "split_checks": {
            "train_vs_val": intersections(datasets["train"], datasets["val"]),
            "train_vs_test": intersections(datasets["train"], datasets["3DMatch"]),
            "val_vs_test": intersections(datasets["val"], datasets["3DMatch"]),
            "match_vs_lomatch": intersections(datasets["3DMatch"], datasets["3DLoMatch"]),
            "interpretation": "Current GeoTransformer metadata share 75 train/val pair paths in analysis-by-synthesis-apt2-kitchen, with identical R/t. This is an artifact audit, not evidence about the authors' historical training run. Its example loader applies no overlap filter by default. Before training, use a documented scene-disjoint validation split; removing this sequence from train would remove 75 rows.",
            "predator_train_not_downloaded": "HEAD size 4,522,214 bytes; not downloaded to respect the 10 MB total metadata cap. PREDATOR validation/test pair paths and R/t match GeoTransformer exactly.",
        },
        "ground_truth": {
            "transform_convention": "Source cloud pcd1 to reference cloud pcd0: x_ref = R x_src + t, units meters.",
            "construction": "Original benchmark reads fragment camera-to-world transforms and forms inverse(T_world_from_ref) @ T_world_from_src. These originate in registered RGB-D reconstructions. Ground-truth correspondences and the gt.info matrix are then derived from aligned overlapping surfaces.",
            "source": "https://github.com/andyzeng/3dmatch-toolbox/blob/master/evaluation/geometric-registration/getGtInfoLog.m",
            "limits": "Reconstruction-derived reference poses are not exact external metrology. Sensor noise, imperfect reconstruction, fusion and sampling remain. This audit cannot measure the error of GT or physical occlusion ratios without the scans and independent references.",
        },
        "evaluation": {
            "main": "Use the existing 3DMatch/3DLoMatch benchmark evaluator for registration recall (RR), with its gt.log/gt.info transform error and RMSE threshold 0.2 m. Average per scene as the reference script does.",
            "supporting": "RRE and RTE; correspondence IR with 0.1 m distance threshold; FMR with 5% inlier threshold. Explicitly state whether RRE/RTE summarize all pairs or only accepted pairs; GeoTransformer eval.py reports them only for accepted registrations.",
            "source": f"https://github.com/qinzheng93/GeoTransformer/blob/{GEO_COMMIT}/experiments/geotransformer.3dmatch.stage4.gse.k3.max.oacl.stage2.sinkhorn/eval.py",
            "warning": "Do not substitute nearest-neighbor Chamfer distance or custom RRE/RTE thresholds while calling the result official RR.",
        },
        "storage_checked_without_download": {
            "predator_preprocessed_data_zip_bytes_head": 936097584,
            "predator_preprocessed_url": "https://share.phys.ethz.ch/~gseg/Predator/data.zip",
            "predator_dense_3dmatch_zip_bytes_head": 5172589610,
            "predator_dense_url": "https://share.phys.ethz.ch/~gsg/pairwise_reg/3dmatch.zip",
            "official_test_archives_website_advertised_MB": {"redkitchen": 40, "home_at": 44, "home_md": 36, "hotel_uc": 55, "hotel_umd_1": 51, "hotel_umd_3": 33, "studyroom": 82, "lab": 42},
            "official_test_archives_advertised_total_MB": 383,
            "official_evaluation_archives_advertised_MB_each": 1,
            "size_limit": "Archive byte counts are HTTP Content-Length, while website MB sizes are advertised rounded values. Extracted size not measured.",
            "small_demo_head_bytes": {"data/demo/src.npy": 383000, "data/demo/ref.npy": 455576, "data/demo/gt.npy": 256},
            "demo_url": f"https://github.com/qinzheng93/GeoTransformer/tree/{GEO_COMMIT}/data/demo",
        },
        "unknowns": ["Actual per-fragment point count distribution (point clouds not downloaded)", "Physical occlusion ratio and sensor noise distributions", "Historical paper train/validation split beyond its written protocol", "Precise cause of overlap-field differences between implementations", "Model accuracy, runtime, and GPU memory on this environment (not run)", "Compatibility of old CUDA/PyTorch implementations with H100 cluster (not tested)"],
    }
    assert audit["metadata_total_bytes"] < 10_000_000
    with outputs[0].open("x", encoding="utf-8") as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2)
    summary = """3DMatch-3DLoMatch metadata audit

Downloaded metadata only: 9,878,860 bytes (under 10 MB). No point clouds or models.

Stable proposal facts:
- Real indoor partial surface fragments, each fused from 50 RGB-D depth frames.
- Task: given two unaligned metric point clouds, estimate source-to-reference R,t.
- Eight held-out test scenes; 3DMatch 1,623 pairs; 3DLoMatch 1,781 pairs.
- The two test benchmarks use the same eight scenes and different pair lists;
  these current pair lists share 100 exact directed pairs and are not disjoint.
- GT comes from reconstruction-derived fragment poses, not exact external metrology.
- Use official RR (0.2 m benchmark transform-error threshold); report per-scene means.

Actual GeoTransformer metadata audit:
- train: 20,642 pairs / 75 sequence names / 48 original scene archive names.
- val: 1,331 pairs / 8 sequence names / 6 original scene archive names.
- train/val share 75 exact directed pair paths and 19 fragment paths in
  analysis-by-synthesis-apt2-kitchen; corresponding R,t values are identical.
- train/test and val/test have no shared scene names or fragment paths.
- The paper's 46/8/8 description must not be presented as these artifact counts.
- Before any training, document a scene-disjoint validation split. Removing the
  shared sequence from training gives 20,567 training pairs / 74 sequence names.
  This is a proposed cleanup, not a claim that it reproduces the paper's split.

Overlap fields (not physical occlusion percentages):
- GeoTransformer 3DMatch: median 47.50%, mean 49.95%; 103 pairs <30%.
- GeoTransformer 3DLoMatch: median 18.43%, mean 18.91%; 4 pairs <10%, 5 >30%.
- PREDATOR 3DLoMatch: median 18.48%, range 10.01%-29.97%.
- PREDATOR 3DMatch overlap field uses different values (median 29.64%).
- All test pair identities and GT R,t are identical across these two repositories.
  Therefore retain official pair membership; do not silently re-filter by an
  implementation-specific overlap column. Causes of numerical differences remain
  unverified without preprocessing provenance / point cloud recomputation.

Storage preflight (HEAD only): preprocessed archive 936,097,584 bytes;
dense archive 5,172,589,610 bytes. Official website lists test-scene archives as
33-82 MB each, 383 MB summed (rounded advertised sizes). GeoTransformer demo
src/ref/GT files total 838,832 bytes; not downloaded in this audit.

Full scene counts, binned overlap distribution, pinned sources, checksums,
GT/evaluation details, and explicit unknowns are in registration_audit.json.
"""
    with outputs[1].open("x", encoding="utf-8") as stream:
        stream.write(summary)
    print(json.dumps({"outputs": [str(path) for path in outputs], "metadata_bytes": audit["metadata_total_bytes"]}))


if __name__ == "__main__":
    main()
