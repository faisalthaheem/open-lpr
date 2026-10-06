"""Tests for the standalone model evaluator.

Everything tested here is the part that is importable without Streamlit: model
discovery, manifest reading, comparison and summarising. The UI itself is not
covered, which is why it is confined to `_serve_ui`.

The recurring theme is honesty about what is runnable and what is merely
present. A `.pth` checkpoint cannot be executed by ONNX Runtime, and the failure
mode that matters is offering it in a picker and then erroring when someone
selects it -- or, worse, appearing to succeed with the default model loaded
instead.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from lpr_app.ml.evaluate import (
    ModelCandidate,
    collect_images,
    compare_reads,
    discover_models,
    load_manifest,
    summarise,
)


class ManifestTests(SimpleTestCase):
    def _write(self, directory: Path, name: str, payload) -> None:
        (directory / name).write_text(json.dumps(payload) if not isinstance(payload, str) else payload)

    def test_missing_manifest_is_not_an_error(self):
        # Provenance is documentation, not a precondition for running a model.
        # An exported-but-undocumented artifact is still worth evaluating.
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(load_manifest(Path(raw) / "model.onnx"), {})

    def test_reads_flat_manifest(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "m.onnx").write_bytes(b"x")
            self._write(directory, "m.onnx.manifest.json", {"trained_on": "split v1", "license": "Apache-2.0"})
            self.assertEqual(load_manifest(directory / "m.onnx")["trained_on"], "split v1")

    def test_reads_alternate_suffix_manifest(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "m.onnx").write_bytes(b"x")
            self._write(directory, "m.manifest.json", {"trained_on": "split v1"})
            self.assertEqual(load_manifest(directory / "m.onnx")["trained_on"], "split v1")

    def test_reads_repo_style_filename_keyed_manifest(self):
        # The repo's model/plate/manifest.json keys by filename, so a promoted
        # artifact copied out of there must still resolve.
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "m.onnx").write_bytes(b"x")
            self._write(directory, "m.onnx.manifest.json", {"m.onnx": {"trained_on": "corpus v1"}})
            self.assertEqual(load_manifest(directory / "m.onnx")["trained_on"], "corpus v1")

    def test_malformed_manifest_degrades_quietly(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "m.onnx").write_bytes(b"x")
            self._write(directory, "m.onnx.manifest.json", "{not json")
            self.assertEqual(load_manifest(directory / "m.onnx"), {})


class DiscoveryTests(SimpleTestCase):
    def _tree(self, root: Path, relative: str, content: bytes = b"x") -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_missing_root_yields_nothing(self):
        self.assertEqual(discover_models("/nonexistent/training-root"), [])

    def test_empty_root_yields_nothing(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(discover_models(raw), [])

    def test_finds_promoted_and_candidate_models(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(root, "models/detector/promoted.onnx")
            self._tree(root, "runs/exp1_20261003/exported/candidate.onnx")
            found = discover_models(root)
            self.assertEqual(len(found), 2)
            self.assertEqual(sum(1 for candidate in found if candidate.promoted), 1)

    def test_promoted_models_sort_first(self):
        # The shipped model should be the default selection, not whichever
        # candidate happens to sort first alphabetically.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(root, "models/detector/zzz_promoted.onnx")
            self._tree(root, "runs/aaa/exported/aaa_candidate.onnx")
            found = discover_models(root)
            self.assertTrue(found[0].promoted)

    def test_checkpoints_are_discovered_but_not_runnable(self):
        # ONNX Runtime cannot load a PyTorch checkpoint. Listing it as runnable
        # would mean selecting it silently falls back to some other model.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(root, "runs/exp1/checkpoints/best_ckpt.pth")
            found = discover_models(root)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].kind, "checkpoint")
            self.assertFalse(found[0].runnable)
            self.assertIn("export", found[0].detail)

    def test_onnx_candidates_are_runnable(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(root, "runs/exp1/exported/c.onnx")
            self.assertTrue(discover_models(root)[0].runnable)

    def test_promoted_label_marks_the_shipped_model(self):
        candidate = ModelCandidate(Path("m.onnx"), "onnx", promoted=True)
        self.assertTrue(candidate.label.startswith("★"))

    def test_detail_surfaces_provenance_when_present(self):
        with tempfile.TemporaryDirectory() as raw:
            # A real file, because `runnable` requires the artifact to exist as
            # well as being an ONNX graph.
            path = Path(raw) / "m.onnx"
            path.write_bytes(b"x")
            candidate = ModelCandidate(path, "onnx", promoted=False, manifest={"trained_on": "split v1"})
            self.assertIn("split v1", candidate.detail)

    def test_detail_for_checkpoint_explains_itself(self):
        candidate = ModelCandidate(Path("m.pth"), "checkpoint", promoted=False)
        self.assertIn("export", candidate.detail)


class CompareReadsTests(SimpleTestCase):
    def _result(self, name: str, reads: list[str]) -> dict:
        return {
            "image": name,
            "path": f"/tmp/{name}",
            "latency_ms": 10.0,
            "plates": len(reads),
            "reads": sum(1 for read in reads if read),
            "detections": [{"ocr": ([{"text": read}] if read else [])} for read in reads],
        }

    def test_agreement_when_both_models_read_the_same(self):
        rows = {"a": [self._result("x.jpg", ["AB1"])], "b": [self._result("x.jpg", ["AB1"])]}
        self.assertTrue(compare_reads(rows)["x.jpg"]["agreement"])

    def test_disagreement_is_flagged(self):
        # This is the finding the tool exists to surface: one model reading
        # confidently and wrongly versus the other declining.
        rows = {"a": [self._result("x.jpg", ["AB1"])], "b": [self._result("x.jpg", ["ABZ"])]}
        self.assertFalse(compare_reads(rows)["x.jpg"]["agreement"])

    def test_one_model_reading_nothing_counts_as_disagreement(self):
        rows = {"a": [self._result("x.jpg", ["AB1"])], "b": [self._result("x.jpg", [""])]}
        entry = compare_reads(rows)["x.jpg"]
        self.assertFalse(entry["agreement"])
        self.assertEqual(entry["reads"]["b"], [""])

    def test_images_are_matched_by_basename(self):
        # Paths differ between a run directory and a staged directory but the
        # images are the same ones, so the basename is the join key.
        rows = {"a": [self._result("x.jpg", ["AB1"])], "b": [self._result("x.jpg", ["AB1"])]}
        self.assertEqual(list(compare_reads(rows)), ["x.jpg"])


class SummariseTests(SimpleTestCase):
    def _result(self, plates: int, reads: int, latency: float) -> dict:
        return {"plates": plates, "reads": reads, "latency_ms": latency}

    def test_empty_reports_none_rather_than_zero(self):
        # Zero plates across zero images would read as "found nothing" rather
        # than "measured nothing".
        summary = summarise([])
        self.assertEqual(summary["images"], 0)
        self.assertIsNone(summary["mean_latency_ms"])
        self.assertIsNone(summary["reads_per_plate"])

    def test_aggregates_plates_reads_and_latency(self):
        summary = summarise([self._result(2, 2, 10.0), self._result(1, 0, 20.0)])
        self.assertEqual(summary["images"], 2)
        self.assertEqual(summary["plates"], 3)
        self.assertEqual(summary["reads"], 2)
        self.assertEqual(summary["mean_latency_ms"], 15.0)

    def test_reads_per_plate_is_none_when_nothing_detected(self):
        self.assertIsNone(summarise([self._result(0, 0, 10.0)])["reads_per_plate"])

    def test_model_reading_nothing_is_visible_not_ignored(self):
        # A model that finds plates and reads none has a distinct failure mode
        # from one that finds no plates; reads_per_plate makes it visible.
        self.assertEqual(summarise([self._result(4, 0, 10.0)])["reads_per_plate"], 0.0)


class CollectImagesTests(SimpleTestCase):
    def test_single_file(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "a.jpg"
            path.write_bytes(b"x")
            self.assertEqual(collect_images(path), [path])

    def test_directory_walk_is_ordered_and_capped(self):
        # Ordered so a rerun evaluates the same images; capped so pointing at a
        # training directory does not stall the UI.
        with tempfile.TemporaryDirectory() as raw:
            for index in range(10):
                (Path(raw) / f"{index:02d}.jpg").write_bytes(b"x")
            found = collect_images(raw, limit=5)
            self.assertEqual(len(found), 5)
            self.assertEqual([path.name for path in found], [f"{i:02d}.jpg" for i in range(5)])

    def test_ignores_non_images(self):
        with tempfile.TemporaryDirectory() as raw:
            (Path(raw) / "notes.txt").write_bytes(b"x")
            (Path(raw) / "a.jpg").write_bytes(b"x")
            self.assertEqual([path.name for path in collect_images(raw)], ["a.jpg"])

    def test_missing_source_is_empty(self):
        self.assertEqual(collect_images("/nonexistent/path"), [])
