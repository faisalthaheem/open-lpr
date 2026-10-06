"""Convert an iMAnno/Simanno-annotated plate corpus to COCO detection JSON.

**The source format is iMAnno (Simanno):** a SQLite database whose `annotations`
table holds one row per image, with an `imgareas` JSON column listing regions as
`{x, y, z, width, height, lblid, lbltxt}`. `lbltxt` is the *class* name and its
only value across the corpus is `plate` — there is no transcription field, which
is why text accuracy cannot be scored from this data.

**The target format is COCO detection JSON** (`annotations/{train,val}2017.json`
plus image split directories), which is what YOLOX's `COCODataset` reads.

**This script does not produce anything ONNX-related.** ONNX is a serialized
computation graph and consumes no dataset at all; a `.pth` checkpoint is
converted to one by `lpr_app/ml/export_onnx.py`, a separate step. The two are
easy to conflate because the artifacts sit close together, so: corpus → COCO
here, COCO → `.pth` by the YOLOX trainer, `.pth` → `.onnx` by export_onnx.

Two things this does that a naive export does not.

**Adjacency-aware grouping.** The corpus is frame-extracted video: every train
image is named by a consecutive integer and all 2351 sit within 3 of their
numeric neighbour. Adjacent frames are near-identical, so a random per-image
split leaks validation frames into training and the resulting metrics are
fiction. Measured directly, 10 train images already duplicate a val image under
the published split. Frames are therefore grouped into contiguous blocks and the
split is over groups.

**Reporting, not silent dropping.** Records that are unreviewed, background, or
deleted are excluded from training but counted, and annotation file names that
resolve to no image are reported by name. A split mistake must not quietly
shrink the training set.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

COCO_CATEGORIES = [{"id": 0, "name": "plate", "supercategory": "vehicle"}]

# Split names, in the COCO convention trainers expect (train2017/val2017).
SPLITS = (("train2017", False), ("val2017", True))


def group_key(filename: str, group_size: int = 25) -> str:
    """Map a frame filename to a contiguous frame block.

    Frames within one block are assumed to come from the same source sequence,
    so they are always split together. ``group_size`` trades leakage against
    validation-set size.
    """
    stem = Path(filename).stem
    try:
        number = int(stem)
    except ValueError:
        return f"name:{stem}"
    return f"block:{number // group_size}"


def load_records(db_path: Path) -> tuple[list[dict], dict]:
    """Read annotation records, skipping unusable ones with counts."""
    connection = sqlite3.connect(db_path)
    cursor = connection.execute(
        "SELECT filename, imheight, imwidth, isreviewed, isdeleted, isbackground, imgareas FROM annotations"
    )

    records: list[dict] = []
    skipped: dict[str, int] = defaultdict(int)

    for filename, height, width, reviewed, deleted, background, areas in cursor:
        if deleted:
            skipped["deleted"] += 1
            continue
        if background:
            skipped["background"] += 1
            continue
        if not reviewed:
            skipped["unreviewed"] += 1
            continue
        if not areas:
            skipped["no_regions"] += 1
            continue
        try:
            regions = json.loads(areas)
        except json.JSONDecodeError:
            skipped["malformed_json"] += 1
            continue
        if not regions:
            skipped["no_regions"] += 1
            continue

        records.append(
            {
                "filename": filename,
                "height": int(height),
                "width": int(width),
                "regions": regions,
            }
        )

    connection.close()
    return records, dict(skipped)


def find_databases(corpus: Path) -> list[Path]:
    """Report every annotation database present, rather than assuming one."""
    return sorted(corpus.glob("*.db"))


def build(
    corpus: Path,
    out_dir: Path,
    *,
    group_size: int = 25,
    val_fraction: float = 0.2,
    seed: int = 0,
) -> dict:
    image_dirs = [corpus / "train", corpus / "val"]
    available = {p.name: p for p in image_dirs if p.is_dir()}
    if not available:
        raise SystemExit(f"no image directory found under {corpus}; expected 'train' and/or 'val'")

    databases = find_databases(corpus)
    if not databases:
        raise SystemExit(f"no annotation database (*.db) found in {corpus}")

    primary = corpus / "train.db"
    if not primary.is_file():
        raise SystemExit(
            f"{primary} not found. Found databases: {[p.name for p in databases]}. "
            f"Re-run with an explicit --db once the authoritative split is chosen."
        )

    records, skipped = load_records(primary)

    # Resolve each record to an image file.
    resolved: list[dict] = []
    missing: list[str] = []
    for record in records:
        found = None
        for directory in available.values():
            candidate = directory / record["filename"]
            if candidate.is_file():
                found = candidate
                break
        if found is None:
            missing.append(record["filename"])
            continue
        record["path"] = found
        record["group"] = group_key(record["filename"], group_size=group_size)
        resolved.append(record)

    # Split at frame level with a deliberate gap. Because adjacent frames are
    # near-identical, validation takes one contiguous stretch of frame numbers
    # with a gap of frames on each side that goes to training. Working in frame
    # numbers rather than block indices matters: block boundaries are exactly
    # where frames touch, so a block-index gap of one still leaves adjacent
    # frames on opposite sides of the split.
    #
    # The sacrificed frames cost a little training and validation size and buy
    # trustworthy metrics. Without the gap every reported number is inflated by
    # near-duplicate frames.
    groups = {r["group"] for r in resolved}
    frames = sorted({int(Path(r["filename"]).stem) for r in resolved if Path(r["filename"]).stem.isdigit()})

    if frames:
        # A whole block is the atomic unit, so validation takes a whole run of
        # blocks. The frames immediately outside that run are dropped from
        # training to form the gap: block edges are where adjacent frames touch,
        # so a validation block and a training block side by side would be one
        # frame apart regardless of how many blocks separate them elsewhere.
        block_ids = sorted({int(Path(r["filename"]).stem) // group_size for r in resolved})
        target_blocks = max(1, int(round(len(block_ids) * val_fraction)))
        gap_blocks = 2

        centre = (block_ids[0] + block_ids[-1]) // 2
        run = min(target_blocks, max(1, len(block_ids) - 2 * gap_blocks))
        first = max(block_ids[0] + gap_blocks, min(centre - run // 2, block_ids[-1] - gap_blocks - run + 1))
        val_block_ids = set(range(first, first + run))

        val_groups = {r["group"] for r in resolved if int(Path(r["filename"]).stem) // group_size in val_block_ids}
        dropped = {
            r["group"]
            for r in resolved
            if int(Path(r["filename"]).stem) // group_size
            in set(range(first - gap_blocks, first)) | set(range(first + run, first + run + gap_blocks))
        }
        for record in resolved:
            if record["group"] in dropped:
                record["dropped_by_gap"] = True
    else:
        # No numeric frame names: fall back to whole-block assignment.
        indices = sorted(int(g.split(":")[1]) for g in groups)
        block = max(1, int(round(len(indices) * val_fraction)))
        start = max(1, (len(indices) - block) // 2)
        val_groups = {f"block:{i}" for i in indices[start : start + block]}
        dropped = set()

    out_dir.mkdir(parents=True, exist_ok=True)
    # COCODataset resolves both <data_dir>/<split>/<file_name> for images and
    # <data_dir>/annotations/<ann>.json, so annotations and images share one root.
    images_root = out_dir
    annotations_root = out_dir / "annotations"
    annotations_root.mkdir(parents=True, exist_ok=True)

    summary = {
        "corpus": str(corpus),
        "databases_present": [p.name for p in databases],
        "database_used": primary.name,
        "records_read": len(records),
        "records_skipped": skipped,
        "missing_images": missing,
        "groups": len(groups),
        "group_size": group_size,
        "val_groups": len(val_groups),
        "val_groups_after_seam_guard": len(val_groups),
    }

    for split, is_val in SPLITS:
        subset = [r for r in resolved if (r["group"] in val_groups) == is_val and not r.get("dropped_by_gap")]
        images: list[dict] = []
        annotations: list[dict] = []
        ann_id = 1

        for index, record in enumerate(sorted(subset, key=lambda r: r["filename"])):
            # Trainers resolve COCO file_name as <data_dir>/<name>/<file_name>,
            # with <name> the split directory. file_name is therefore bare.
            target_name = record["filename"]
            images.append(
                {
                    "id": index,
                    "file_name": target_name,
                    "width": record["width"],
                    "height": record["height"],
                }
            )
            for region in record["regions"]:
                x = float(region["x"])
                y = float(region["y"])
                w = float(region["width"])
                h = float(region["height"])
                annotations.append(
                    {
                        "id": ann_id,
                        "image_id": index,
                        "category_id": 0,
                        # COCO wants xywh; the corpus is already x/y/w/h.
                        "bbox": [x, y, w, h],
                        "area": w * h,
                        # A stacked two-line plate is one object: the whole plate
                        # is annotated as a single box.
                        "iscrowd": 0,
                    }
                )
                ann_id += 1

        coco = {
            "info": {"description": "open-lpr plate detection corpus"},
            "licenses": [],
            "images": images,
            "annotations": annotations,
            "categories": COCO_CATEGORIES,
        }
        (annotations_root / f"{split}.json").write_text(json.dumps(coco))

        split_dir = images_root / split
        split_dir.mkdir(parents=True, exist_ok=True)
        import shutil

        for record in sorted(subset, key=lambda r: r["filename"]):
            shutil.copy2(record["path"], split_dir / record["filename"])

        summary[f"{split}_images"] = len(images)
        summary[f"{split}_annotations"] = len(annotations)

    # Plate height distribution matters: recall must be judged on the smallest
    # plates, where a fixed input resolution loses them.
    heights = sorted(
        float(a["bbox"][3]) for r in resolved for a in [{"bbox": [0, 0, 0, reg["height"]]} for reg in r["regions"]]
    )
    if heights:
        summary["plate_height_p10"] = heights[len(heights) // 10]
        summary["plate_height_median"] = heights[len(heights) // 2]
        summary["plate_height_p90"] = heights[9 * len(heights) // 10]

    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True, help="corpus root containing train/ and *.db")
    parser.add_argument("--out", type=Path, required=True, help="output directory for COCO json and images")
    parser.add_argument(
        "--group-size", type=int, default=25, help="frames per group; a split boundary never falls inside one"
    )
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    summary = build(
        args.corpus,
        args.out,
        group_size=args.group_size,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2, default=str))
    if summary["missing_images"]:
        print(f"\nWARNING: {len(summary['missing_images'])} annotation(s) named no image file", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
