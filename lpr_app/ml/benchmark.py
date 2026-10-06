#!/usr/bin/env python3
"""Measure CPU latency and recall of the local pipeline.

Two things this measures that a single mAP figure hides.

**Latency per stage and end to end, on CPU.** The deployment target is CPU-only,
and no detector publishes CPU ONNX numbers, so the estimate in DETECTOR.md has to
be replaced by a measurement. One-time model loading is excluded, since it does
not recur per request.

**Recall bucketed by plate height.** A flat mAP hides the case that actually
limits this project: plate height has a 10th percentile of 36px, and a detector
that scores well overall can still miss most of the smallest plates. Recall is
reported per height bucket so that failure is visible.

Exits non-zero when the end-to-end budget is exceeded, so a regression fails the
check rather than being discovered in production.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image  # noqa: E402

from lpr_app.pipeline.stages.detect import (  # noqa: E402
    Detection,
    PlateDetectionStage,
    box_iou,
)


def load_split(data_dir: Path, split: str):
    coco = json.loads((data_dir / "annotations" / f"{split}.json").read_text())
    images = {image["id"]: image for image in coco["images"]}
    by_image: dict[int, list[dict]] = {}
    for annotation in coco["annotations"]:
        by_image.setdefault(annotation["image_id"], []).append(annotation)
    return images, by_image


def match(predictions: list[Detection], truths: list[dict], iou_threshold: float = 0.3):
    """Greedy IoU matching; returns per-truth hit flags and precision."""
    used = set()
    hits = []
    for truth in truths:
        x, y, w, h = truth["bbox"]
        target = Detection(x, y, x + w, y + h, 1.0)
        best_iou, best_index = 0.0, None
        for index, prediction in enumerate(predictions):
            if index in used:
                continue
            overlap = box_iou(prediction, target)
            if overlap > best_iou:
                best_iou, best_index = overlap, index
        if best_index is not None and best_iou >= iou_threshold:
            used.add(best_index)
            hits.append(True)
        else:
            hits.append(False)
    return hits, len(used)


def benchmark(args) -> int:
    data_dir = Path(args.data)
    images, by_image = load_split(data_dir, args.split)
    image_dir = data_dir / args.split

    stage = PlateDetectionStage(
        model_path=args.model,
        input_size=tuple(args.input_size),
        conf_threshold=args.conf,
        nms_iou=args.nms,
    )

    sample = sorted(images.values(), key=lambda i: i["id"])[: args.limit]

    # Warm up so one-time session creation and lazy init are excluded. They do not
    # recur per request, so including them would misreport steady-state cost.
    if sample:
        warm = Image.open(image_dir / sample[0]["file_name"]).convert("RGB")
        stage.run({"image": warm})

    per_image: list[float] = []
    buckets: dict[str, list[int]] = {}
    true_positives = 0
    false_positives = 0
    total_truths = 0

    for image_info in sample:
        path = image_dir / image_info["file_name"]
        if not path.is_file():
            continue
        image = Image.open(path).convert("RGB")

        started = time.perf_counter()
        outputs = stage.run({"image": image})
        per_image.append(time.perf_counter() - started)

        predictions = outputs["detections"]
        truths = by_image.get(image_info["id"], [])
        hits, matched = match(predictions, truths, iou_threshold=args.match_iou)

        true_positives += sum(hits)
        false_positives += max(0, len(predictions) - matched)
        total_truths += len(truths)

        for truth, hit in zip(truths, hits, strict=True):
            height = truth["bbox"][3]
            bucket = "<40px" if height < 40 else "40-60px" if height < 60 else "60-100px" if height < 100 else ">=100px"
            buckets.setdefault(bucket, []).append(int(hit))

    if not per_image:
        print("no images measured", file=sys.stderr)
        return 2

    ordered = sorted(per_image)
    recall = true_positives / total_truths if total_truths else 0.0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0.0

    report = {
        "model": str(args.model),
        "split": args.split,
        "images": len(per_image),
        "input_size": list(args.input_size),
        "conf_threshold": args.conf,
        "latency_seconds": {
            "mean": statistics.fmean(per_image),
            "median": statistics.median(per_image),
            "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
            "max": ordered[-1],
            "min": ordered[0],
        },
        "budget_seconds": args.budget,
        "within_budget": statistics.fmean(per_image) <= args.budget,
        "recall_at_iou": {"iou": args.match_iou, "overall": recall},
        "precision": precision,
        "false_positives_per_image": false_positives / len(per_image),
        "recall_by_plate_height": {
            bucket: {"recall": sum(hits) / len(hits), "count": len(hits)} for bucket, hits in sorted(buckets.items())
        },
    }

    print(json.dumps(report, indent=2))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2))

    if not report["within_budget"]:
        print(
            f"\nFAIL: mean latency {report['latency_seconds']['mean'] * 1000:.1f}ms exceeds "
            f"budget {args.budget * 1000:.1f}ms",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="dataset root with annotations/ and <split>/")
    parser.add_argument("--model", required=True, help="ONNX artifact to measure")
    parser.add_argument("--split", default="val2017")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--input-size", type=int, nargs=2, default=(640, 640))
    parser.add_argument("--conf", type=float, default=0.3)
    parser.add_argument("--nms", type=float, default=0.45)
    parser.add_argument("--match-iou", type=float, default=0.3)
    parser.add_argument("--budget", type=float, default=0.5)
    parser.add_argument("--json-out", default=None)
    return benchmark(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
