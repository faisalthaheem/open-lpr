#!/usr/bin/env python3
"""Sharded teacher labelling: run the LLM backend over a directory of images.

Produces pseudo-labels for detector training by driving the *real* LLM code path
— `QwenVLClient`, `DETECTION_PROMPT`, `OCR_PROMPT`, `parse_detection_response`,
`DetectionValidator` — rather than a reimplementation. That matters: pseudo-labels
that came from a subtly different prompt would teach the student to imitate a
pipeline that does not exist.

**The central hazard is conflating "the teacher found no plate" with "the teacher
was not asked."** Both produce an empty result, and an interrupted or failed pass
that wrote empty results would silently poison a training set with thousands of
correct-looking negative examples — teaching a detector to ignore plates. Every
record therefore carries an explicit `status`:

- `ok` — teacher ran, found plates
- `no_plates` — teacher ran, found none. A real, valid negative.
- `error` — teacher failed or the response was unparseable. **Not a negative.**

`error` records are counted and reported separately, and a merge whose error rate
exceeds `--max-error-rate` refuses to promote itself to "complete". This is the
single property that makes the output safe to train on.

## Sharding and resume

Work is split into deterministic shards (`shard-000.json`…), one worker per GPU.
Each worker appends JSONL to its own file and, on restart, reads that file first
and skips images already present. Resuming is therefore free and safe.

Only `ok` and `no_plates` count as processed. An `error` is retried on the next
run, so a transient API failure does not permanently cost an image.

Crash safety comes from appending one line and flushing per record. A kill
mid-write loses at most the final line, and a truncated final line is detected
and discarded on resume rather than parsed as JSON.

## Usage

```bash
# 1. build the queue (deterministic, safe to re-run)
python -m lpr_app.ml.label_teacher build-queue \\
    --images raw/community/images --queue staged/queue --shards 8

# 2. run workers, one per GPU (24GB each fits several)
for i in 0 1 2 3; do
  HIP_VISIBLE_DEVICES=$((i % 2)) python -m lpr_app.ml.label_teacher run \\
      --shard $i --queue staged/queue --out staged/annotations &
done
wait

# 3. merge shards into one labelled set
python -m lpr_app.ml.label_teacher merge \\
    --queue staged/queue --out staged/annotations/teacher_pass1.json
```
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SHARD_FILENAME = "shard-{index:03d}.json"

# Statuses that mean "the teacher was asked and answered".
SETTLED_STATUSES = {"ok", "no_plates"}


@dataclass
class Shard:
    index: int
    path: Path
    images: list[str]


def discover_images(source: str | Path) -> list[Path]:
    """Every image under `source`, sorted.

    Sorted so the queue is a pure function of the input directory: rebuilding it
    yields identical shards, which is what lets a worker resume against a queue
    another process generated.
    """
    path = Path(source)
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return [candidate for candidate in sorted(path.rglob("*")) if candidate.suffix.lower() in IMAGE_SUFFIXES]


def build_shards(images: list[Path], queue_dir: Path, shards: int) -> list[Shard]:
    """Split images across `shards` files, round-robin.

    Round-robin rather than contiguous blocks so each shard gets a mix of
    filenames and, more importantly, each shard takes roughly the same number of
    images from any prefix of the sorted list — which matters because concurrent
    workers pull from a shared API endpoint and a lopsided shard finishes last.
    """
    if shards < 1:
        raise ValueError("shards must be at least 1")

    queue_dir.mkdir(parents=True, exist_ok=True)
    built: list[Shard] = []

    for index in range(shards):
        path = queue_dir / SHARD_FILENAME.format(index=index)
        assigned = [str(image) for position, image in enumerate(images) if position % shards == index]
        path.write_text(json.dumps({"index": index, "images": assigned}, indent=2))
        built.append(Shard(index=index, path=path, images=assigned))

    return built


def load_shard(path: Path) -> Shard:
    payload = json.loads(Path(path).read_text())
    return Shard(index=int(payload["index"]), path=Path(path), images=list(payload["images"]))


def completed_paths(shard_file: Path) -> tuple[set[str], int]:
    """Read a worker's output, returning settled image paths and discarded lines.

    A line that is not valid JSON is dropped rather than fatal. The only way to
    produce one is a kill mid-append, so treating it as poison would mean a
    crash permanently breaks that shard's resume.
    """
    if not shard_file.exists():
        return set(), 0

    settled: set[str] = set()
    discarded = 0
    with shard_file.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                discarded += 1
                continue
            if record.get("status") in SETTLED_STATUSES:
                settled.add(record["image"])
    return settled, discarded


def append_record(shard_file: Path, record: dict) -> None:
    """Append one JSONL record and flush.

    Flushed per record so an interrupted run loses at most the record in flight,
    which resume then redoes. Buffering would silently drop the tail of a killed
    run while leaving the file looking complete.
    """
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    with shard_file.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def label_one(image_path: str, client=None, scratch_dir: Path | None = None) -> dict:
    """Run one image through the teacher's detection and OCR phases.

    Mirrors `ImageProcessingService._run_llm_pipeline` — same downscale, same
    prompts, same coordinate scaling, same validator — and returns a record for
    the pseudo-label set.

    The image is copied into a scratch directory first, because
    `ImageProcessor.downscale_for_detection` and `crop_region` both write their
    outputs *next to their input*. That is correct in production, where the media
    working directory is disposable, but here the input lives in `raw/`, which is
    immutable. Labelling in place scatters `_downscale.jpg` and `_crop_N_M.jpg`
    files through the source corpus.

    Never raises for an image-level failure. Every outcome is a record, because a
    raising worker would abandon the rest of its shard and the queue would stall
    behind it.
    """
    from django.conf import settings

    from lpr_app.services.detection_validator import DetectionValidator
    from lpr_app.services.image_processor import ImageProcessor
    from lpr_app.services.qwen_client import (
        DETECTION_PROMPT,
        OCR_PROMPT,
        get_qwen_client,
        parse_detection_response,
        parse_ocr_response,
    )

    path = Path(image_path)
    record = {"image": str(path), "status": "error", "detections": [], "error": None}

    scratch = Path(scratch_dir) if scratch_dir else Path(tempfile.mkdtemp(prefix="teacher-"))
    owns_scratch = scratch_dir is None
    try:
        from PIL import Image

        with Image.open(path) as opened:
            original_w, original_h = opened.size

        # Every intermediate stays inside scratch; the source is only read.
        staged = scratch / path.name
        shutil.copy2(path, staged)

        downscaled_path = ImageProcessor.downscale_for_detection(
            str(staged),
            min_plate_height=settings.MIN_PLATE_HEIGHT,
            plate_height_fraction=settings.PLATE_HEIGHT_FRACTION,
        )
        if not downscaled_path:
            record["error"] = "downscale failed"
            return record

        downscaled_info = ImageProcessor.get_image_info(downscaled_path)
        if not downscaled_info:
            record["error"] = "downscaled image unreadable"
            return record

        client = client or get_qwen_client()

        encoded = ImageProcessor.encode_image_to_base64(downscaled_path)
        if not encoded:
            record["error"] = "encode failed"
            return record

        prompt = DETECTION_PROMPT.replace("[actual filename of the image]", path.name)
        response = client.analyze_image(encoded, prompt)
        if not response:
            record["error"] = "detection phase returned nothing"
            return record

        detection_data = parse_detection_response(
            response, original_h, original_w, downscaled_info["height"], downscaled_info["width"]
        )
        if not detection_data:
            record["error"] = "unparseable detection response"
            return record

        detections = detection_data.get("detections", [])
        if detections:
            validator = DetectionValidator(
                min_confidence=settings.DETECTION_MIN_CONFIDENCE,
                min_box_area_fraction=settings.DETECTION_MIN_BOX_AREA_FRACTION,
                max_box_area_fraction=settings.DETECTION_MAX_BOX_AREA_FRACTION,
                min_plate_aspect=settings.DETECTION_MIN_PLATE_ASPECT,
                max_plate_aspect=settings.DETECTION_MAX_PLATE_ASPECT,
            )
            detections = validator.filter_detections(detections, original_h, original_w)

        if not detections:
            # A genuine negative, and a valuable one: the teacher saw the image
            # and there was nothing there. Distinct from every failure above.
            record["status"] = "no_plates"
            return record

        # OCR each detected plate, mirroring the LLM path's fixed-pixel padding.
        ocr_padding_px = settings.OCR_CROP_PADDING_PX
        for detection in detections:
            coords = detection["plate"]["coordinates"]
            crop_result = ImageProcessor.crop_region(
                str(staged),
                int(coords["x1"]),
                int(coords["y1"]),
                int(coords["x2"]),
                int(coords["y2"]),
                padding_px=ocr_padding_px,
            )
            if not crop_result:
                continue
            crop_path, offset_x, offset_y = crop_result
            encoded_crop = ImageProcessor.encode_image_to_base64(crop_path)
            if not encoded_crop:
                continue

            crop_info = ImageProcessor.get_image_info(crop_path)
            if not crop_info:
                continue

            ocr_response = client.analyze_image(encoded_crop, OCR_PROMPT)
            parsed = (
                parse_ocr_response(ocr_response, crop_info["height"], crop_info["width"], offset_x, offset_y)
                if ocr_response
                else {}
            ) or {}
            detection["ocr"] = [
                {
                    "text": (parsed.get("text") or ""),
                    "confidence": float(parsed.get("confidence") or 0.0),
                }
            ]

        record["status"] = "ok"
        record["detections"] = detections
        return record

    except Exception as exc:  # noqa: BLE001 - one bad image must not kill a shard
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record

    finally:
        if owns_scratch:
            shutil.rmtree(scratch, ignore_errors=True)


def run_shard(
    shard_path: Path,
    out_dir: Path,
    limit: int | None = None,
    delay: float = 0.0,
    args_verbose: bool = False,
) -> dict:
    """Process one shard, skipping images an earlier run already settled.

    Resumable by construction: the output file is the progress record.
    """
    shard = load_shard(shard_path)
    shard_file = out_dir / f"teacher_pass1.shard{shard.index:03d}.jsonl"
    done, discarded = completed_paths(shard_file)

    pending = [image for image in shard.images if image not in done]
    if limit is not None:
        pending = pending[:limit]

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lpr_project.settings")
    import django

    django.setup()
    from lpr_app.services.qwen_client import get_qwen_client

    client = get_qwen_client()
    stats = {"shard": shard.index, "processed": 0, "errors": 0, "skipped": len(done), "discarded": discarded}

    for position, image in enumerate(pending, start=1):
        record = label_one(image, client=client)
        append_record(shard_file, record)
        stats["processed"] += 1
        stats["errors"] += int(record["status"] == "error")
        if args_verbose:
            # A pass over 5,000 images takes hours. Silence for that long is
            # indistinguishable from a hang, and with several workers running
            # concurrently there is no other way to see which shard is behind.
            print(
                f"[shard {shard.index}] {position}/{len(pending)} {record['status']} {Path(image).name}",
                flush=True,
            )
        if delay:
            time.sleep(delay)

    return stats


def merge_shards(queue_dir: Path, out_dir: Path, max_error_rate: float = 0.05) -> tuple[dict, int]:
    """Combine shard outputs into one annotated file and report coverage.

    Exits non-zero when the merge is not trustworthy — either images are missing
    because the pass was interrupted, or the error rate is too high for the
    negatives to mean anything. A merge that "succeeds" on half the queue would
    produce a training set that looks finished and is not.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lpr_project.settings")
    import django

    django.setup()

    shards = sorted(queue_dir.glob(SHARD_FILENAME.format(index=0).replace("000", "*")))
    if not shards:
        raise SystemExit(f"no shards found in {queue_dir}")

    expected = 0
    records: dict[str, dict] = {}

    for shard_path in shards:
        shard = load_shard(shard_path)
        expected += len(shard.images)
        worker_file = out_dir / f"teacher_pass1.shard{shard.index:03d}.jsonl"
        if not worker_file.exists():
            continue
        with worker_file.open() as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Last write wins, so re-processing an image that previously
                # errored overwrites the error with its settled result.
                records[record["image"]] = record

    ok = sum(1 for record in records.values() if record["status"] == "ok")
    negatives = sum(1 for record in records.values() if record["status"] == "no_plates")
    errors = sum(1 for record in records.values() if record["status"] == "error")
    settled = ok + negatives
    error_rate = errors / len(records) if records else 1.0

    report = {
        "shards": len(shards),
        "images_expected": expected,
        "images_seen": len(records),
        "with_plates": ok,
        "no_plates": negatives,
        "errors": errors,
        "settled": settled,
        "missing": max(0, expected - settled),
        "error_rate": round(error_rate, 4),
        "complete": settled == expected and error_rate <= max_error_rate,
        "note": (
            "complete requires every image settled AND the error rate within tolerance. "
            "'errors' records are NOT negatives: the teacher never answered for them."
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "teacher_pass1.json"
    out_path.write_text(
        json.dumps(
            {
                "summary": report,
                "records": [records[key] for key in sorted(records)],
            },
            indent=2,
            sort_keys=True,
        )
    )
    report["output"] = str(out_path)
    return report, 0 if report["complete"] else 1


def command_build_queue(args) -> int:
    images = discover_images(args.images)
    if not images:
        print(json.dumps({"error": "no images found", "path": str(args.images)}, indent=2))
        return 2

    shards = build_shards(images, Path(args.queue), args.shards)
    print(
        json.dumps(
            {
                "images": len(images),
                "shards": len(shards),
                "queue": str(Path(args.queue).resolve()),
                "sizes": [len(shard.images) for shard in shards],
            },
            indent=2,
        )
    )
    return 0


def command_run(args) -> int:
    stats = run_shard(
        Path(args.shard),
        Path(args.out),
        limit=args.limit,
        delay=args.delay,
        args_verbose=not args.quiet,
    )
    print(json.dumps(stats, indent=2))
    return 0


def command_merge(args) -> int:
    report, code = merge_shards(Path(args.queue), Path(args.out), max_error_rate=args.max_error_rate)
    report.pop("output", None)
    print(json.dumps(report, indent=2))
    return code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-queue", help="split images into deterministic shards")
    build.add_argument("--images", required=True, help="image file or directory")
    build.add_argument("--queue", required=True, help="queue output directory")
    build.add_argument("--shards", type=int, default=8)
    build.set_defaults(handler=command_build_queue)

    run = subparsers.add_parser("run", help="process one shard (resumable)")
    run.add_argument("--shard", required=True, help="shard file, e.g. staged/queue/shard-000.json")
    run.add_argument("--out", required=True, help="annotation output directory")
    run.add_argument("--limit", type=int, default=None, help="stop after N new images (for a smoke test)")
    run.add_argument("--delay", type=float, default=0.0, help="seconds to sleep between images")
    run.add_argument("--quiet", action="store_true", help="suppress per-image progress")
    run.set_defaults(handler=command_run)

    merge = subparsers.add_parser("merge", help="combine shards and verify completeness")
    merge.add_argument("--queue", required=True)
    merge.add_argument("--out", required=True)
    merge.add_argument(
        "--max-error-rate",
        type=float,
        default=0.05,
        help="refuse to report complete above this fraction of failed images",
    )
    merge.set_defaults(handler=command_merge)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
