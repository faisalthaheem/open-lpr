#!/usr/bin/env python3
"""Side-by-side comparison of the local pipeline against the LLM backend.

Task 11.9 asks for the numbers that decide whether the default backend should
flip, and task 11.10 asks that the flip not happen until they justify it.

**What cannot be measured here, and why it matters.** Text accuracy cannot be
scored against ground truth: the corpus annotates plate *boxes* and carries no
transcription labels, so there is no correct answer to compare a read against.
Any character error rate reported from this corpus would be measured against
labels that do not exist. What is measurable instead:

- **Detection recall and precision at IoU 0.3**, which is a real, label-backed
  comparison and the axis on which the two backends differ most.
- **Read coverage**: the fraction of detected plates that produced text at all,
  and the confidence distribution of those reads. This is not accuracy, and is
  reported as such. A high coverage with low confidence is a different failure
  from a low coverage, and the distinction matters when reading the numbers.
- **Latency**, because the case for the local backend is that it fits in-process
  against a 500ms budget while an API round trip does not.

Recognition accuracy therefore needs transcription labels, which is the gap the
follow-up change has to close before a flip is justified rather than merely
plausible.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image  # noqa: E402


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def layout_of(bbox) -> str:
    _x, _y, w, h = bbox
    return "stacked" if h > 0 and w / h < 2.0 else "single_line"


def box_iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    intersection_w = min(ax2, bx2) - max(ax1, bx1)
    intersection_h = min(ay2, by2) - max(ay1, by1)
    if intersection_w <= 0 or intersection_h <= 0:
        return 0.0
    intersection = intersection_w * intersection_h
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    return intersection / union if union > 0 else 0.0


class Tally:
    """Accumulates the axes both backends are measured on."""

    def __init__(self) -> None:
        self.latencies: list[float] = []
        self.hits = 0
        self.misses = 0
        self.false_positives = 0
        self.reads = 0
        self.confidences: list[float] = []
        self.plates_by_layout: dict[str, dict[str, int]] = {}

    def observe_image(self, seconds: float) -> None:
        self.latencies.append(seconds)

    def observe_detection(self, matched: int, predicted: int, truth_count: int) -> None:
        self.hits += matched
        self.false_positives += max(0, predicted - matched)
        self.misses += max(0, truth_count - matched)

    def observe_text(self, text: str | None, confidence: float, layout: str) -> None:
        bucket = self.plates_by_layout.setdefault(layout, {"plates": 0, "read": 0})
        bucket["plates"] += 1
        if text:
            bucket["read"] += 1
            self.reads += 1
            self.confidences.append(confidence)

    def report(self) -> dict:
        total = self.hits + self.misses
        predicted = self.hits + self.false_positives
        return {
            "latency": {
                "images": len(self.latencies),
                "mean_ms": round(statistics.fmean(self.latencies) * 1000, 1) if self.latencies else None,
                "median_ms": round(statistics.median(self.latencies) * 1000, 1) if self.latencies else None,
                "p95_ms": round(percentile(self.latencies, 0.95) * 1000, 1),
                "max_ms": round(max(self.latencies) * 1000, 1) if self.latencies else None,
            },
            "detection": {
                "plates_in_corpus": total,
                "recall": round(self.hits / total, 4) if total else None,
                "precision": round(self.hits / predicted, 4) if predicted else None,
                "false_positives": self.false_positives,
            },
            "text": {
                "note": "coverage and confidence only; no transcription labels in the corpus",
                "plates_read": self.reads,
                "read_coverage": round(self.reads / total, 4) if total else None,
                "median_confidence": round(statistics.median(self.confidences), 3) if self.confidences else None,
                "by_layout": {
                    layout: {
                        **counts,
                        "coverage": round(counts["read"] / counts["plates"], 4) if counts["plates"] else None,
                    }
                    for layout, counts in sorted(self.plates_by_layout.items())
                },
            },
        }


def load_split(data_dir: Path, split: str):
    coco = json.loads((data_dir / "annotations" / f"{split}.json").read_text())
    images = {image["id"]: image for image in coco["images"]}
    by_image: dict[int, list[dict]] = {}
    for annotation in coco["annotations"]:
        by_image.setdefault(annotation["image_id"], []).append(annotation)
    return images, by_image


def match(predictions: list[tuple], truths: list[dict], iou_threshold: float) -> list[tuple[int | None, dict]]:
    used: set[int] = set()
    pairs = []
    for truth in truths:
        x, y, w, h = truth["bbox"]
        target = (x, y, x + w, y + h)
        best_iou, best_index = 0.0, None
        for index, prediction in enumerate(predictions):
            if index in used:
                continue
            overlap = box_iou(prediction, target)
            if overlap > best_iou:
                best_iou, best_index = overlap, index
        if best_index is not None and best_iou >= iou_threshold:
            used.add(best_index)
            pairs.append((best_index, truth))
        else:
            pairs.append((None, truth))
    return pairs


def measure_local(data_dir: Path, split: str, image_ids, files, by_image, iou_threshold: float) -> Tally:
    from lpr_app.pipeline.local_backend import build_local_backend_from_settings

    backend = build_local_backend_from_settings()
    backend.warm_up()
    tally = Tally()

    for image_id in image_ids:
        path = data_dir / split / files[image_id]
        if not path.is_file():
            continue
        image = Image.open(path).convert("RGB")

        started = time.perf_counter()
        result = backend.run(image)
        tally.observe_image(time.perf_counter() - started)

        boxes: list[tuple] = []
        texts: list[tuple[str | None, float]] = []
        for detection in result.detections:
            coords = detection["plate"]["coordinates"]
            boxes.append((coords["x1"], coords["y1"], coords["x2"], coords["y2"]))
            ocr = detection["ocr"]
            texts.append((ocr[0]["text"], ocr[0]["confidence"]) if ocr else (None, 0.0))

        truths = by_image.get(image_id, [])
        pairs = match(boxes, truths, iou_threshold)
        tally.observe_detection(sum(1 for index, _ in pairs if index is not None), len(boxes), len(truths))

        for index, truth in pairs:
            layout = layout_of(truth["bbox"])
            if index is None:
                tally.observe_text(None, 0.0, layout)
            else:
                text, confidence = texts[index]
                tally.observe_text(text, confidence, layout)

    return tally


def measure_llm(data_dir: Path, split: str, image_ids, files, by_image, iou_threshold: float) -> Tally:
    """Drive the real LLM backend through the service's own extracted method."""
    from django.test import override_settings

    from lpr_app.models import ProcessingLog, UploadedImage
    from lpr_app.services import image_processing_service as service

    tally = Tally()

    for image_id in image_ids:
        path = data_dir / split / files[image_id]
        if not path.is_file():
            continue

        started = time.perf_counter()
        with override_settings(MEDIA_ROOT=str(path.parent)):
            # The log row needs a saved parent, since _run_llm_pipeline records a
            # duration on it in a finally block; an unsaved one raises rather than
            # silently skipping the metric write.
            image = UploadedImage.objects.create(filename=path.name, original_image=path.name)
            try:
                log = ProcessingLog.objects.create(uploaded_image=image, status="api_call", message="comparison")
                with Image.open(path) as opened:
                    width, height = opened.size
                detections, _summary = service.ImageProcessingService._run_llm_pipeline(
                    image, str(path), height, width, 0.0, log
                )
            finally:
                image.delete()
        tally.observe_image(time.perf_counter() - started)

        boxes = []
        texts = []
        for detection in detections:
            coords = detection["plate"]["coordinates"]
            boxes.append((coords["x1"], coords["y1"], coords["x2"], coords["y2"]))
            ocr = detection.get("ocr") or []
            texts.append((ocr[0]["text"], ocr[0]["confidence"]) if ocr else (None, 0.0))

        truths = by_image.get(image_id, [])
        pairs = match(boxes, truths, iou_threshold)
        tally.observe_detection(sum(1 for index, _ in pairs if index is not None), len(boxes), len(truths))

        for index, truth in pairs:
            layout = layout_of(truth["bbox"])
            if index is None:
                tally.observe_text(None, 0.0, layout)
            else:
                text, confidence = texts[index]
                tally.observe_text(text, confidence, layout)

    return tally


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="dataset root")
    parser.add_argument("--split", default="val2017")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--match-iou", type=float, default=0.3)
    parser.add_argument("--backends", default="local,llm")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lpr_project.settings")
    import django

    django.setup()

    data_dir = Path(args.data)
    images, by_image = load_split(data_dir, args.split)
    files = {image["id"]: image["file_name"] for image in images.values()}
    sample = sorted(i for i in images if by_image.get(i))[: args.limit]

    report = {
        "split": args.split,
        "images": len(sample),
        "match_iou": args.match_iou,
        "budget_seconds": 0.5,
    }

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    if "local" in backends:
        report["local"] = measure_local(data_dir, args.split, sample, files, by_image, args.match_iou).report()
    if "llm" in backends:
        report["llm"] = measure_llm(data_dir, args.split, sample, files, by_image, args.match_iou).report()

    if "local" in report:
        mean = report["local"]["latency"]["mean_ms"]
        report["local"]["within_budget"] = bool(mean is not None and mean / 1000 <= args_budget())

    print(json.dumps(report, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2))
    return 0


def args_budget() -> float:
    from django.conf import settings

    return settings.PIPELINE_LATENCY_BUDGET_SECONDS


if __name__ == "__main__":
    raise SystemExit(main())
