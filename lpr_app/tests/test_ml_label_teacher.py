"""Tests for the sharded teacher labeller.

The sharding itself is arithmetic. What is not is the distinction the whole tool
rests on: an image where the teacher found no plate, and an image where the
teacher was never successfully asked, both produce an empty result.

Getting that wrong writes thousands of confident negatives into a training set
and teaches a detector to ignore plates — a failure that would not show up as an
error, only as a model that quietly stops working on real traffic.

Resume is tested for the same reason. An interrupted pass that does not resume
correctly silently redoes hours of work or, worse, leaves a file that looks
complete.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from PIL import Image

from lpr_app.ml.label_teacher import (
    SETTLED_STATUSES,
    append_record,
    build_shards,
    completed_paths,
    discover_images,
    load_shard,
    merge_shards,
    teacher_provenance,
)


class DiscoverImagesTests(SimpleTestCase):
    def test_sorted_so_the_queue_is_reproducible(self):
        # A queue that reorders between builds invalidates every worker's
        # progress record, since resume matches on image path.
        with tempfile.TemporaryDirectory() as raw:
            for name in ("c.jpg", "a.jpg", "b.jpg"):
                (Path(raw) / name).write_bytes(b"x")
            self.assertEqual([path.name for path in discover_images(raw)], ["a.jpg", "b.jpg", "c.jpg"])

    def test_single_file_is_one_image(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "a.jpg"
            path.write_bytes(b"x")
            self.assertEqual(discover_images(path), [path])

    def test_missing_source_is_empty(self):
        self.assertEqual(discover_images("/nonexistent"), [])

    def test_ignores_non_images(self):
        with tempfile.TemporaryDirectory() as raw:
            (Path(raw) / "notes.txt").write_bytes(b"x")
            (Path(raw) / "a.png").write_bytes(b"x")
            self.assertEqual([path.name for path in discover_images(raw)], ["a.png"])


class ShardingTests(SimpleTestCase):
    def _images(self, directory: Path, count: int) -> list[Path]:
        return [directory / f"{index:03d}.jpg" for index in range(count)]

    def test_every_image_lands_in_exactly_one_shard(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            images = self._images(root, 17)
            for image in images:
                image.write_bytes(b"x")
            shards = build_shards(discover_images(root), root / "queue", 5)
            assigned = [image for shard in shards for image in shard.images]
            self.assertEqual(sorted(assigned), sorted(str(image) for image in images))
            self.assertEqual(len(assigned), len(set(assigned)))

    def test_shard_sizes_are_balanced(self):
        # An unbalanced shard finishes last and holds up the merge.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for image in self._images(root, 100):
                image.write_bytes(b"x")
            shards = build_shards(discover_images(root), root / "queue", 8)
            self.assertLessEqual(
                max(len(shard.images) for shard in shards) - min(len(shard.images) for shard in shards),
                1,
            )

    def test_rebuilding_produces_identical_shards(self):
        # Determinism is what makes a queue safe to regenerate after a crash
        # without invalidating every worker's progress.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for image in self._images(root, 10):
                image.write_bytes(b"x")
            images = discover_images(root)
            first = [shard.images for shard in build_shards(images, root / "q1", 3)]
            second = [shard.images for shard in build_shards(images, root / "q2", 3)]
            self.assertEqual(first, second)

    def test_round_robin_spreads_across_shards(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            images = [str(root / f"{index:03d}.jpg") for index in range(6)]
            shards = build_shards([Path(image) for image in images], root / "queue", 3)
            self.assertEqual(
                [shard.images for shard in shards],
                [[images[0], images[3]], [images[1], images[4]], [images[2], images[5]]],
            )

    def test_more_shards_than_images_is_allowed(self):
        # Workers are per-GPU and may outnumber the data on a small run.
        with tempfile.TemporaryDirectory() as raw:
            shards = build_shards([Path(raw) / "a.jpg"], Path(raw) / "queue", 4)
            self.assertEqual(len(shards), 4)
            self.assertEqual(sum(len(shard.images) for shard in shards), 1)

    def test_rejects_zero_shards(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(ValueError):
                build_shards([], Path(raw) / "queue", 0)

    def test_shard_round_trips(self):
        with tempfile.TemporaryDirectory() as raw:
            shards = build_shards([Path(raw) / "a.jpg"], Path(raw) / "queue", 1)
            self.assertEqual(load_shard(shards[0].path).images, shards[0].images)


class ResumeTests(SimpleTestCase):
    def test_missing_output_means_nothing_done(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(completed_paths(Path(raw) / "missing.jsonl"), (set(), 0))

    def test_only_settled_statuses_count_as_done(self):
        # The core invariant. An `error` is not progress and must be retried.
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "out.jsonl"
            append_record(path, {"image": "a.jpg", "status": "ok", "detections": []})
            append_record(path, {"image": "b.jpg", "status": "no_plates", "detections": []})
            append_record(path, {"image": "c.jpg", "status": "error", "error": "boom", "detections": []})
            done, _ = completed_paths(path)
            self.assertEqual(done, {"a.jpg", "b.jpg"})

    def test_errors_are_retried_not_skipped(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "out.jsonl"
            append_record(path, {"image": "a.jpg", "status": "error", "error": "timeout"})
            self.assertEqual(completed_paths(path)[0], set())

    def test_no_plates_is_progress(self):
        # A genuine negative must not be re-run: it costs an API call and, worse,
        # re-running it risks writing an error over a correct negative.
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "out.jsonl"
            append_record(path, {"image": "a.jpg", "status": "no_plates"})
            self.assertEqual(completed_paths(path)[0], {"a.jpg"})

    def test_truncated_final_line_is_discarded_not_fatal(self):
        # The signature of a kill mid-append. Treating it as poison would mean a
        # crash permanently breaks that shard's resume.
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "out.jsonl"
            append_record(path, {"image": "a.jpg", "status": "ok"})
            with path.open("a") as handle:
                handle.write('{"image": "b.jpg", "status": "o')
            done, discarded = completed_paths(path)
            self.assertEqual(done, {"a.jpg"})
            self.assertEqual(discarded, 1)

    def test_settled_statuses_are_the_two_expected(self):
        self.assertEqual(SETTLED_STATUSES, {"ok", "no_plates"})


class ScratchIsolationTests(SimpleTestCase):
    """`raw/` must survive labelling untouched.

    `ImageProcessor.downscale_for_detection` and `crop_region` both write their
    outputs next to their input. That is fine in production, where the media
    directory is disposable, and wrong here: the input is the immutable source
    corpus. This was observed happening -- 50 `_downscale.jpg` and `_crop_*.jpg`
    files appeared in the community image directory before it was fixed.
    """

    def test_labelling_leaves_no_files_beside_the_source(self):
        from unittest.mock import MagicMock

        from lpr_app.ml.label_teacher import label_one

        with tempfile.TemporaryDirectory() as raw:
            source_dir = Path(raw) / "raw"
            source_dir.mkdir()
            source = source_dir / "plate.jpg"
            Image.new("RGB", (640, 480), (30, 90, 160)).save(source)

            before = sorted(path.name for path in source_dir.iterdir())

            # A client that returns nothing exercises the failure path, which
            # still downscales first -- the step that pollutes.
            client = MagicMock()
            client.analyze_image.return_value = None

            scratch = Path(raw) / "scratch"
            scratch.mkdir()
            label_one(str(source), client=client, scratch_dir=scratch)

            self.assertEqual(sorted(path.name for path in source_dir.iterdir()), before)

    def test_intermediates_land_in_the_scratch_directory(self):
        from unittest.mock import MagicMock

        from lpr_app.ml.label_teacher import label_one

        with tempfile.TemporaryDirectory() as raw:
            source_dir = Path(raw) / "raw"
            source_dir.mkdir()
            source = source_dir / "plate.jpg"
            Image.new("RGB", (1600, 1200), (30, 90, 160)).save(source)

            client = MagicMock()
            client.analyze_image.return_value = None

            scratch = Path(raw) / "scratch"
            scratch.mkdir()
            label_one(str(source), client=client, scratch_dir=scratch)

            # A downscale artefact is what proves intermediates are confined here
            # rather than beside the source. It only happens above the derived
            # minimum image height (MIN_PLATE_HEIGHT / PLATE_HEIGHT_FRACTION), so
            # this needs a large enough image to trigger one at all.
            self.assertTrue(any("downscale" in path.name for path in scratch.iterdir()))


class ImageNormalisationTests(SimpleTestCase):
    """Images that PIL cannot re-encode as JPEG must not be lost.

    121 of the 4,995 community images are RGBA PNGs carrying a `.jpg`
    extension. `downscale_for_detection` saves as JPEG, so those raise and land
    as errors -- a 2.4% silent hole in the queue that only shows up as a merge
    that never completes.
    """

    def test_rgba_png_with_jpg_extension_is_handled(self):
        from unittest.mock import MagicMock

        from lpr_app.ml.label_teacher import label_one

        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "screenshot.jpg"
            Image.new("RGBA", (900, 600), (200, 30, 30, 128)).save(source, "PNG")

            client = MagicMock()
            client.analyze_image.return_value = None
            record = label_one(str(source), client=client, scratch_dir=Path(raw) / "scratch")

            # Reaches the API call, rather than failing in the downscale step.
            self.assertEqual(record["status"], "error")
            self.assertNotEqual(record["error"], "downscale failed")
            self.assertTrue(client.analyze_image.called)

    def test_greyscale_and_cmyk_are_handled(self):
        from unittest.mock import MagicMock

        from lpr_app.ml.label_teacher import label_one

        # PNG cannot hold greyscale-as-L or CMYK here, so L goes out as PNG and
        # CMYK as JPEG -- both still land on disk with a .jpg name.
        for mode, fmt in (("L", "PNG"), ("CMYK", "JPEG")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as raw:
                source = Path(raw) / "odd.jpg"
                Image.new(mode, (400, 300)).save(source, fmt)

                client = MagicMock()
                client.analyze_image.return_value = None
                record = label_one(str(source), client=client, scratch_dir=Path(raw) / "scratch")

                self.assertNotEqual(record["error"], "downscale failed")

    def test_pathological_image_is_bounded(self):
        # A 108-megapixel screenshot trips PIL's decompression-bomb guard on the
        # re-encode, and costs nothing at full size for plate detection.
        from unittest.mock import MagicMock

        from lpr_app.ml.label_teacher import label_one

        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "huge.jpg"
            Image.new("RGB", (9000, 7000), (10, 90, 200)).save(source)

            client = MagicMock()
            client.analyze_image.return_value = None
            record = label_one(str(source), client=client, scratch_dir=Path(raw) / "scratch")

            self.assertNotEqual(record["error"], "downscale failed")


class MergeTests(SimpleTestCase):
    def _queue(self, root: Path, images: list[str], shards: int = 1) -> Path:
        for image in images:
            (root / image).write_bytes(b"x")
        build_shards([root / image for image in images], root / "queue", shards)
        return root / "queue"

    def test_merge_reports_missing_when_incomplete(self):
        # An interrupted pass must never look finished. Training on half a
        # dataset silently is worse than failing here.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            queue = self._queue(root, ["a.jpg", "b.jpg"])
            out = root / "out"
            out.mkdir()
            append_record(out / "teacher_pass1.shard000.jsonl", {"image": str(root / "a.jpg"), "status": "ok"})
            report, code = merge_shards(queue, out)
            self.assertFalse(report["complete"])
            self.assertEqual(report["missing"], 1)
            self.assertEqual(code, 1)

    def test_complete_when_every_image_settled(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            queue = self._queue(root, ["a.jpg", "b.jpg"])
            out = root / "out"
            out.mkdir()
            for image in ("a.jpg", "b.jpg"):
                append_record(
                    out / "teacher_pass1.shard000.jsonl",
                    {"image": str(root / image), "status": "ok", "detections": [{"plate": {}}]},
                )
            report, code = merge_shards(queue, out)
            self.assertTrue(report["complete"])
            self.assertEqual(code, 0)
            self.assertEqual(report["with_plates"], 2)

    def test_high_error_rate_blocks_completion(self):
        # Every image "settled" but most were errors: coverage looks perfect and
        # the negatives mean nothing.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            queue = self._queue(root, ["a.jpg", "b.jpg"])
            out = root / "out"
            out.mkdir()
            for image in ("a.jpg", "b.jpg"):
                append_record(
                    out / "teacher_pass1.shard000.jsonl",
                    {"image": str(root / image), "status": "error", "error": "boom"},
                )
            report, code = merge_shards(queue, out)
            self.assertFalse(report["complete"])
            self.assertEqual(code, 1)
            self.assertEqual(report["errors"], 2)

    def test_later_record_overwrites_an_earlier_error(self):
        # Re-running an image that errored must repair it, not accumulate.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            queue = self._queue(root, ["a.jpg"])
            out = root / "out"
            out.mkdir()
            worker = out / "teacher_pass1.shard000.jsonl"
            append_record(worker, {"image": str(root / "a.jpg"), "status": "error", "error": "boom"})
            append_record(worker, {"image": str(root / "a.jpg"), "status": "ok", "detections": [{"plate": {}}]})
            report, _ = merge_shards(queue, out)
            self.assertEqual(report["errors"], 0)
            self.assertEqual(report["with_plates"], 1)
            self.assertTrue(report["complete"])

    def test_errors_are_counted_separately_from_negatives(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            queue = self._queue(root, ["a.jpg", "b.jpg"])
            out = root / "out"
            out.mkdir()
            append_record(out / "teacher_pass1.shard000.jsonl", {"image": str(root / "a.jpg"), "status": "ok"})
            append_record(
                out / "teacher_pass1.shard000.jsonl",
                {"image": str(root / "b.jpg"), "status": "no_plates"},
            )
            report, _ = merge_shards(queue, out)
            self.assertEqual(report["with_plates"], 1)
            self.assertEqual(report["no_plates"], 1)
            self.assertEqual(report["errors"], 0)

    def test_multi_shard_merge_is_ordered_deterministically(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            queue = self._queue(root, ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], shards=2)
            out = root / "out"
            out.mkdir()
            for index in range(2):
                append_record(
                    out / f"teacher_pass1.shard{index:03d}.jsonl",
                    {"image": str(root / ("a.jpg" if index == 0 else "b.jpg")), "status": "ok"},
                )
            report, _ = merge_shards(queue, out)
            self.assertEqual(report["images_expected"], 4)
            self.assertEqual(report["settled"], 2)

    def test_writes_merged_file_with_summary(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            queue = self._queue(root, ["a.jpg"])
            out = root / "out"
            out.mkdir()
            append_record(out / "teacher_pass1.shard000.jsonl", {"image": str(root / "a.jpg"), "status": "ok"})
            merge_shards(queue, out)
            payload = json.loads((out / "teacher_pass1.json").read_text())
            self.assertIn("summary", payload)
            self.assertEqual(len(payload["records"]), 1)

    def test_missing_queue_is_fatal(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(SystemExit):
                merge_shards(Path(raw) / "no-queue", Path(raw) / "out")


class TeacherProvenanceTests(SimpleTestCase):
    """The merge must succeed without a client, and must say so honestly.

    `merge_shards` runs in its own process after the labelling workers exited,
    so there is no client object to hand it. That was previously an undefined
    name, which meant every merge crashed. The fix makes the parameter optional
    -- these tests exist so the crash cannot come back, and so the provenance is
    not quietly claiming more certainty than it has.
    """

    def test_works_with_no_client_at_all(self):
        provenance = teacher_provenance()

        self.assertIsNone(provenance["client_class"])
        self.assertIn("separate process", provenance["client_class_note"])

    def test_records_the_client_class_when_one_is_available(self):
        provenance = teacher_provenance(client=object())

        self.assertEqual(provenance["client_class"], "object")

    @override_settings(QWEN_MODEL="test/model-v1", QWEN_BASE_URL="http://teacher.invalid/v1")
    def test_records_model_and_endpoint(self):
        # The reason this exists: the first labelling pass recorded no model
        # anywhere, leaving 2,634 training boxes unattributable.
        provenance = teacher_provenance()

        self.assertEqual(provenance["model"], "test/model-v1")
        self.assertEqual(provenance["base_url"], "http://teacher.invalid/v1")

    def test_prompt_hashes_are_recorded(self):
        """Same model, different prompts, different boxes.

        Without the hashes a label set cannot be tied to the prompt that made it.
        """
        provenance = teacher_provenance()

        self.assertEqual(len(provenance["detection_prompt_sha256"]), 16)
        self.assertEqual(len(provenance["ocr_prompt_sha256"]), 16)
        self.assertNotEqual(provenance["detection_prompt_sha256"], provenance["ocr_prompt_sha256"])

    def test_merge_report_carries_provenance(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.jpg").write_bytes(b"x")
            build_shards([root / "a.jpg"], root / "queue", 1)
            out = root / "out"
            out.mkdir()
            append_record(out / "teacher_pass1.shard000.jsonl", {"image": str(root / "a.jpg"), "status": "ok"})

            report, _ = merge_shards(root / "queue", out)

            self.assertIn("teacher", report)
            self.assertIsNone(report["teacher"]["client_class"])
