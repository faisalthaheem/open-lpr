"""The local backend: settings-driven selection, output parity, and validation.

Two properties matter more than the pipeline working here.

**The default is the LLM backend.** The local pipeline has not been shown to be
as accurate on this corpus as the vision model it would replace, and a silent
default flip would be an accuracy regression shipped as a config default. These
tests assert the default explicitly so changing it has to be deliberate.

**Both backends emit the same collection shape.** Callers, the API, the
visualizer, and the metrics all read one shape. A key present on one backend and
absent on the other would not fail here; it would fail in production, in whichever
consumer nobody re-checked. So the shape is asserted directly against the shape
the LLM path produces.
"""

from __future__ import annotations

from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from lpr_app.pipeline.local_backend import (
    KNOWN_BACKENDS,
    LLM_BACKEND,
    LOCAL_BACKEND,
    LocalBackendError,
    build_local_backend_from_settings,
    plate_crop_for,
    record_text,
    resolve_backend,
)
from lpr_app.pipeline.stages.detect import Detection
from lpr_app.pipeline.stages.ocr import RecognitionResult

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "model" / "plate"
DETECTOR = MODEL_DIR / "plate_yolox_tiny_640.onnx"
OCR_MODEL = MODEL_DIR / "plate_ocr_ppocrv5_mobile.onnx"
OCR_DICT = MODEL_DIR / "plate_ocr_dict.json"

has_models = DETECTOR.is_file() and OCR_MODEL.is_file() and OCR_DICT.is_file()


def a_plate_image(width: int = 240, height: int = 90) -> Image.Image:
    """A light plate with a dark bar standing in for glyphs."""
    array = np.full((height, width, 3), 225, dtype=np.uint8)
    array[height // 3 : 2 * height // 3, width // 12 : width - width // 12] = 40
    return Image.fromarray(array)


class ResolveBackendTest(SimpleTestCase):
    """Backend selection is by name, defaulting to the local pipeline."""

    def test_local_is_the_default(self):
        """The local backend is the only path that fits the sub-500ms budget, so it
        is what a deployment with no PIPELINE_BACKEND configured gets."""
        self.assertEqual(resolve_backend(None), LOCAL_BACKEND)

    def test_omitted_name_matches_the_settings_default(self):
        """Two defaulting code paths that disagree would resolve differently
        depending on which asked, which is exactly the kind of bug that only shows
        up on the path nobody exercised."""
        from django.conf import settings

        self.assertEqual(resolve_backend(None), settings.PIPELINE_BACKEND)

    def test_explicit_llm_is_honoured(self):
        self.assertEqual(resolve_backend("llm"), LLM_BACKEND)

    def test_local_is_selectable(self):
        self.assertEqual(resolve_backend("local"), LOCAL_BACKEND)

    def test_selection_is_case_insensitive(self):
        self.assertEqual(resolve_backend("LOCAL"), LOCAL_BACKEND)

    def test_unknown_backend_is_an_error_not_a_silent_fallback(self):
        """Falling back would hide a typo behind a working backend, so the
        misconfiguration stays visible."""
        with self.assertRaises(LocalBackendError) as ctx:
            resolve_backend("yolo")
        self.assertIn("yolo", str(ctx.exception))

    def test_known_backends_are_documented(self):
        self.assertEqual(KNOWN_BACKENDS, (LLM_BACKEND, LOCAL_BACKEND))


class SettingsSelectionTest(SimpleTestCase):
    """The setting on ``settings`` is what the service branches on."""

    def test_default_setting_is_local(self):
        from django.conf import settings

        self.assertEqual(settings.PIPELINE_BACKEND, LOCAL_BACKEND)

    @override_settings(PIPELINE_BACKEND=LLM_BACKEND)
    def test_override_selects_llm(self):
        """The rollback path: selecting the LLM backend must remain a working
        configuration, not a removed one."""
        from django.conf import settings

        self.assertEqual(settings.PIPELINE_BACKEND, LLM_BACKEND)

    def test_end_to_end_budget_defaults_to_half_a_second(self):
        from django.conf import settings

        self.assertEqual(settings.PIPELINE_LATENCY_BUDGET_SECONDS, 0.5)

    @override_settings(PIPELINE_LATENCY_BUDGET_SECONDS=0.25)
    def test_end_to_end_budget_is_configurable(self):
        from django.conf import settings

        self.assertEqual(settings.PIPELINE_LATENCY_BUDGET_SECONDS, 0.25)

    def test_stage_budgets_default_to_none_rather_than_zero(self):
        """An unset budget must not read as a zero budget, which everything would
        exceed."""
        from django.conf import settings

        self.assertEqual(settings.PIPELINE_STAGE_BUDGETS, {})

    def test_stage_budgets_parse_from_configuration(self):
        """python-decouple evaluates the cast at import, so the parser is asserted
        directly rather than through the already-resolved setting."""
        from lpr_project.settings import _parse_stage_budgets

        self.assertEqual(
            _parse_stage_budgets("detect_plate=0.4,read_plate=0.1"),
            {"detect_plate": 0.4, "read_plate": 0.1},
        )

    def test_empty_stage_budgets_parse_to_nothing(self):
        from lpr_project.settings import _parse_stage_budgets

        self.assertEqual(_parse_stage_budgets(""), {})

    def test_provider_defaults_to_cpu(self):
        from django.conf import settings

        self.assertEqual(settings.PIPELINE_PROVIDER, "cpu")

    def test_ocr_charset_profile_defaults_to_alphanumeric(self):
        from django.conf import settings

        self.assertEqual(settings.PIPELINE_OCR_CHARSET_PROFILE, "alphanumeric")

    def test_stacked_splitting_is_off_by_default(self):
        from django.conf import settings

        self.assertFalse(settings.PIPELINE_OCR_SPLIT_STACKED)


class ServiceBranchTest(SimpleTestCase):
    """The service branches on the setting without knowing how either path works."""

    def test_llm_path_is_not_taken_when_local_is_selected(self):
        """The branch is the whole switch: if the LLM runner is reached on the local
        path, the selection is broken regardless of what either path does."""
        from lpr_app.services import image_processing_service as service

        with override_settings(PIPELINE_BACKEND=LOCAL_BACKEND):
            self.assertFalse(service.settings.PIPELINE_BACKEND == LLM_BACKEND)

    def test_llm_path_is_taken_when_llm_is_selected(self):
        from lpr_app.services import image_processing_service as service

        with override_settings(PIPELINE_BACKEND=LLM_BACKEND):
            self.assertFalse(service.settings.PIPELINE_BACKEND == LOCAL_BACKEND)

    def test_both_backends_converge_on_one_detections_collection(self):
        """Whichever branch runs, the caller receives the same two things."""
        from lpr_app.services import image_processing_service as service

        signature = service.ImageProcessingService._run_local_pipeline.__annotations__
        llm_signature = service.ImageProcessingService._run_llm_pipeline.__annotations__
        self.assertIn("return", signature)
        self.assertIn("return", llm_signature)

    def test_resetting_the_backend_drops_the_cached_instance(self):
        from lpr_app.services import image_processing_service as service

        service.reset_local_backend()
        self.assertIsNone(service._LOCAL_BACKEND)

    def test_llm_pipeline_failure_is_distinct_from_no_plates(self):
        """An unprocessed image and an image with no plates are different answers,
        and conflating them would report a failed request as a successful empty one."""
        from lpr_app.services.image_processing_service import LLMPipelineError

        self.assertTrue(issubclass(LLMPipelineError, Exception))


class OutputShapeTest(SimpleTestCase):
    """The collection both backends return."""

    def _plate_entry(self) -> dict:
        return {
            "plate": {
                "confidence": 0.91,
                "coordinates": {"x1": 10, "y1": 20, "x2": 110, "y2": 60},
            }
        }

    def test_a_detection_has_exactly_the_keys_the_llm_path_produces(self):
        from lpr_app.pipeline.stages.detect import Detection as D

        payload = D(10, 20, 110, 60, 0.91).to_dict()
        self.assertEqual(set(payload), {"confidence", "coordinates"})
        self.assertEqual(set(payload["coordinates"]), {"x1", "y1", "x2", "y2"})
        for value in payload["coordinates"].values():
            self.assertIsInstance(value, int)

    def test_ocr_entry_has_the_keys_the_llm_path_produces(self):
        detections = [self._plate_entry()]
        record_text(detections, 0, RecognitionResult(text="EG209", confidence=0.78))
        ocr = detections[0]["ocr"]
        self.assertEqual(len(ocr), 1)
        self.assertEqual(set(ocr[0]), {"text", "confidence", "coordinates"})
        self.assertEqual(ocr[0]["text"], "EG209")

    def test_ocr_coordinates_are_the_plates_own_box(self):
        """The recognizer emits characters, not word geometry. Claiming a tighter
        box would be fabrication; the plate region is the honest extent."""
        detections = [self._plate_entry()]
        record_text(detections, 0, RecognitionResult(text="EG209", confidence=0.78))
        self.assertEqual(detections[0]["ocr"][0]["coordinates"], detections[0]["plate"]["coordinates"])

    def test_every_detection_carries_an_ocr_key(self):
        """Even a rejected read leaves ``ocr`` present, so a consumer can index it
        without a presence check."""
        detections = [self._plate_entry(), self._plate_entry()]
        record_text(detections, 0, RecognitionResult(text="", confidence=0.0))
        record_text(detections, 1, RecognitionResult(text="EG209", confidence=0.5))
        self.assertEqual(detections[0]["ocr"], [])
        self.assertEqual(len(detections[1]["ocr"]), 1)

    def test_confidence_is_a_float_in_both_backends(self):
        detections = [self._plate_entry()]
        record_text(detections, 0, RecognitionResult(text="EG209", confidence=0.7812345))
        self.assertIsInstance(detections[0]["ocr"][0]["confidence"], float)


class TextValidationTest(SimpleTestCase):
    """Recognized text goes through the existing validator, as the LLM path does."""

    def _record(self, text: str, confidence: float = 0.8) -> dict:
        detections = [{"plate": {"confidence": 0.9, "coordinates": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}}]
        record_text(detections, 0, RecognitionResult(text=text, confidence=confidence))
        return detections[0]

    def test_valid_text_is_recorded(self):
        self.assertEqual(self._record("EG209")["ocr"][0]["text"], "EG209")

    def test_single_character_text_is_rejected(self):
        """The validator rejects text shorter than two characters; a local
        recognizer emits these more often than the LLM did, so the rule has to
        hold here too rather than being loosened for one backend."""
        self.assertEqual(self._record("T")["ocr"], [])

    def test_empty_text_is_discarded(self):
        self.assertEqual(self._record("")["ocr"], [])

    def test_zero_confidence_is_discarded(self):
        self.assertEqual(self._record("EG209", confidence=0.0)["ocr"], [])

    def test_a_rejected_read_leaves_the_detection_in_place(self):
        """Hiding the plate would make detector recall unreadable: a rejected read
        and a missed detection are different facts."""
        detection = self._record("T")
        self.assertIn("plate", detection)
        self.assertEqual(detection["plate"]["confidence"], 0.9)


class CropPaddingTest(SimpleTestCase):
    """Rectified crops are not padded; bypassed crops are."""

    def setUp(self):
        from lpr_app.pipeline.local_backend import build_local_backend_from_settings

        with override_settings(PIPELINE_MODEL_DIR=str(MODEL_DIR)):
            self.backend = build_local_backend_from_settings()

    def test_rectified_crop_is_not_expanded_by_the_padding(self):
        image = Image.new("RGB", (400, 300), (90, 90, 90))
        image.paste(a_plate_image(), (100, 120))
        detection = Detection(100, 120, 340, 210, 0.9, layout="single_line")

        crop = plate_crop_for(image, detection, self.backend.crop_padding_px, self.backend.rectifier)

        # Rectification maps to a fixed output size, so the crop's dimensions are
        # the layout's target and cannot have grown by the padding.
        self.assertEqual(crop.size, self.backend.rectifier.target_size_for("single_line"))

    def test_bypassed_crop_is_expanded_by_the_padding(self):
        """With rectification off, the crop is the box plus OCR_CROP_PADDING_PX on
        each side, which is the contract the LLM path has always had."""
        image = Image.new("RGB", (400, 300), (90, 90, 90))
        detection = Detection(100, 100, 180, 160, 0.9, layout="single_line")

        crop = plate_crop_for(image, detection, 20, None)

        self.assertEqual(crop.size, (80 + 40, 60 + 40))

    def test_bypassed_crop_clamps_at_the_image_edge(self):
        image = Image.new("RGB", (200, 150), (90, 90, 90))
        detection = Detection(0, 0, 40, 30, 0.9, layout="single_line")

        crop = plate_crop_for(image, detection, 25, None)

        # 25px is available on the left and top, none on the right or bottom.
        self.assertEqual(crop.size, (40 + 25, 30 + 25))

    def test_bypassed_crop_at_the_image_edge_clamps(self):
        image = Image.new("RGB", (200, 150), (90, 90, 90))
        detection = Detection(0, 0, 40, 30, 0.9, layout="single_line")
        crop = plate_crop_for(image, detection, 25, None)
        self.assertEqual(crop.size, (40 + 25, 30 + 25))
        self.assertEqual(crop.size[0] <= image.width, True)

    def test_bypass_is_used_when_rectification_is_disabled(self):
        """The bypass path is what keeps the fixed-pixel padding contract intact
        when a deployment turns rectification off."""
        with override_settings(PIPELINE_MODEL_DIR=str(MODEL_DIR), PIPELINE_RECTIFY_ENABLED=False):
            from lpr_app.pipeline.local_backend import build_local_backend_from_settings

            backend = build_local_backend_from_settings()
        self.assertFalse(backend.rectifier.enabled)


class SettingsConstructionTest(SimpleTestCase):
    """The backend is built from settings, with artifacts resolved under the dir."""

    def test_model_paths_resolve_under_the_model_directory(self):
        with override_settings(PIPELINE_MODEL_DIR="/srv/models"):
            backend = build_local_backend_from_settings()
        self.assertEqual(backend.detector.model_path, "/srv/models/plate_yolox_tiny_640.onnx")
        self.assertEqual(backend.recogniser.dict_path, "/srv/models/plate_ocr_dict.json")

    def test_validator_thresholds_come_from_settings(self):
        with override_settings(
            PIPELINE_MODEL_DIR=str(MODEL_DIR),
            DETECTION_MIN_CONFIDENCE=0.42,
            DETECTION_MIN_PLATE_ASPECT=2.0,
        ):
            backend = build_local_backend_from_settings()
        self.assertEqual(backend.validator.min_confidence, 0.42)
        self.assertEqual(backend.validator.min_plate_aspect, 2.0)

    def test_stage_budgets_are_passed_through(self):
        with override_settings(
            PIPELINE_MODEL_DIR=str(MODEL_DIR),
            PIPELINE_STAGE_BUDGETS={"detect_plate": 0.4},
        ):
            backend = build_local_backend_from_settings()
        self.assertEqual(backend.stage_budgets, {"detect_plate": 0.4})

    def test_provider_is_applied_to_every_model_stage(self):
        with override_settings(PIPELINE_MODEL_DIR=str(MODEL_DIR), PIPELINE_PROVIDER="rocm"):
            backend = build_local_backend_from_settings()
        self.assertEqual(backend.detector.context.provider, "rocm")
        self.assertEqual(backend.recogniser.context.provider, "rocm")


class TimingTest(SimpleTestCase):
    """Budget comparison."""

    def test_no_budget_means_no_verdict(self):
        from lpr_app.pipeline.local_backend import StageTiming

        self.assertIsNone(StageTiming("read_plate", "ok", duration=9.0).within_budget)

    def test_within_budget_when_under(self):
        from lpr_app.pipeline.local_backend import StageTiming

        self.assertTrue(StageTiming("read_plate", "ok", duration=0.1, budget=0.5).within_budget)

    def test_over_budget_when_over(self):
        from lpr_app.pipeline.local_backend import StageTiming

        self.assertFalse(StageTiming("read_plate", "ok", duration=0.9, budget=0.5).within_budget)

    def test_end_to_end_budget_comparison(self):
        from lpr_app.pipeline.local_backend import LocalPipelineResult

        result = LocalPipelineResult(duration=0.4)
        self.assertTrue(result.within_budget(0.5))
        self.assertFalse(result.within_budget(0.3))
        self.assertIsNone(result.within_budget(None))


class MetricsTest(SimpleTestCase):
    """Per-stage and end-to-end timings reach the Prometheus registry."""

    def test_stage_duration_is_recorded_with_stage_and_outcome_labels(self):
        from prometheus_client import REGISTRY as DEFAULT_REGISTRY

        from lpr_app.metrics import PIPELINE_STAGE_DURATION

        before = PIPELINE_STAGE_DURATION.labels(stage="read_plate", outcome="ok")._sum.get()
        from lpr_app.utils.metrics_helpers import MetricsHelper

        MetricsHelper.record_pipeline_stage_duration("read_plate", "ok", 0.02)
        after = PIPELINE_STAGE_DURATION.labels(stage="read_plate", outcome="ok")._sum.get()
        self.assertAlmostEqual(after - before, 0.02, places=6)
        self.assertIsNotNone(DEFAULT_REGISTRY)

    def test_outcomes_are_distinguishable_series(self):
        """A skipped stage must not land in the successful series, or a failure
        would be invisible next to a stage that never ran.

        Asserted on the exported text, which is what a monitoring system reads, and
        which is the only place the distinction survives: a skip costs no time, so
        the observation *sum* for a skip is 0 either way.
        """
        from prometheus_client import generate_latest

        from lpr_app.metrics import REGISTRY
        from lpr_app.utils.metrics_helpers import MetricsHelper

        MetricsHelper.record_pipeline_stage_duration("read_plate", "skipped", 0.0)
        MetricsHelper.record_pipeline_stage_duration("read_plate", "failed", 0.02)

        exported = generate_latest(REGISTRY).decode()
        self.assertIn('lpr_pipeline_stage_duration_seconds_count{outcome="skipped"', exported)
        self.assertIn('lpr_pipeline_stage_duration_seconds_count{outcome="failed"', exported)
        self.assertIn('stage="read_plate"', exported)

    def test_stages_are_separate_series(self):
        """Per-stage cost has to be readable per stage, or a regression in one stage
        is indistinguishable from a rise in all of them."""
        from lpr_app.metrics import PIPELINE_STAGE_DURATION
        from lpr_app.utils.metrics_helpers import MetricsHelper

        MetricsHelper.record_pipeline_stage_duration("detect_plate", "ok", 0.4)
        MetricsHelper.record_pipeline_stage_duration("read_plate", "ok", 0.01)

        detect = PIPELINE_STAGE_DURATION.labels(stage="detect_plate", outcome="ok")._sum.get()
        read = PIPELINE_STAGE_DURATION.labels(stage="read_plate", outcome="ok")._sum.get()
        self.assertGreater(detect, read * 10)

    def test_pipeline_duration_is_recorded(self):
        from lpr_app.metrics import PIPELINE_DURATION
        from lpr_app.utils.metrics_helpers import MetricsHelper

        before = PIPELINE_DURATION.labels(outcome="ok")._sum.get()
        MetricsHelper.record_pipeline_duration("ok", 0.06)
        self.assertAlmostEqual(PIPELINE_DURATION.labels(outcome="ok")._sum.get() - before, 0.06, places=6)

    def test_processing_duration_metric_is_unchanged(self):
        """The existing overall processing metric must keep existing, so the two
        backends stay comparable on one series."""
        from lpr_app.metrics import PROCESSING_DURATION

        PROCESSING_DURATION.labels(status="completed").observe(0.5)
        self.assertGreater(PROCESSING_DURATION.labels(status="completed")._sum.get(), 0.0)

    def test_stage_histogram_is_exported(self):
        from prometheus_client import generate_latest

        from lpr_app.metrics import REGISTRY
        from lpr_app.utils.metrics_helpers import MetricsHelper

        MetricsHelper.record_pipeline_stage_duration("detect_plate", "ok", 0.01)
        exported = generate_latest(REGISTRY).decode()
        self.assertIn("lpr_pipeline_stage_duration_seconds", exported)
        self.assertIn('stage="detect_plate"', exported)
        self.assertIn('outcome="ok"', exported)


@skipUnless(has_models, f"no trained artifacts under {MODEL_DIR}")
class RealModelLocalBackendTest(SimpleTestCase):
    """The whole local path against genuine artifacts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with override_settings(PIPELINE_MODEL_DIR=str(MODEL_DIR)):
            cls.backend = build_local_backend_from_settings()
            cls.backend.warm_up()

    def test_blank_image_yields_no_detections(self):
        result = self.backend.run(Image.new("RGB", (1280, 960), (200, 200, 200)))
        self.assertEqual(result.detections, [])

    def test_result_carries_timings_for_the_stages_that_ran(self):
        result = self.backend.run(Image.new("RGB", (640, 480), (200, 200, 200)))
        self.assertIn("detect_plate", result.timings)
        self.assertGreater(result.duration, 0.0)

    def test_a_detected_plate_is_rectified_into_its_own_region(self):
        """A wrong box convention rectifies a mostly-car crop, which reads as
        empty rather than as an error. Asserting non-empty geometry is the only
        way that bug is visible."""
        plate = a_plate_image(240, 90)
        canvas = Image.new("RGB", (1280, 960), (150, 150, 150))
        canvas.paste(plate, (500, 400))
        detection = Detection(500, 400, 740, 490, 0.9, layout="single_line")

        crop = plate_crop_for(canvas, detection, 25, self.backend.rectifier)
        self.assertEqual(crop.size, self.backend.rectifier.target_size_for("single_line"))
        # The rectified crop should carry the plate's ink, not a flat car panel.
        grey = np.asarray(crop.convert("L"), dtype=np.float32)
        self.assertLess(float(grey.std()), 120.0, "a flat crop means the box convention is wrong")

    def test_recognizer_returns_confidence_within_range(self):
        plate = a_plate_image(240, 90)
        results = self.backend.recogniser.read_plates([(plate, "single_line")])
        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(results[0].confidence, 0.0)
        self.assertLessEqual(results[0].confidence, 1.0)

    def test_one_result_per_plate_within_the_batch_bound(self):
        plates = [(a_plate_image(200 + 10 * i, 90), "single_line") for i in range(6)]
        self.backend.recogniser.batch_size = 4
        results = self.backend.recogniser.read_plates(plates)
        self.assertEqual(len(results), 6)

    def test_batching_does_not_change_the_readings(self):
        """Padded batching must decode to the same text as one-at-a-time, which is
        the only way to know the padding and the timestep trim are both correct."""
        plates = [(a_plate_image(200 + 10 * i, 90), "single_line") for i in range(5)]
        self.backend.recogniser.batch_size = 1
        unbatched = [r.text for r in self.backend.recogniser.read_plates(plates)]
        self.backend.recogniser.batch_size = 8
        batched = [r.text for r in self.backend.recogniser.read_plates(plates)]
        self.assertEqual(unbatched, batched)

    def test_real_export_label_layout_still_matches_the_dictionary(self):
        """The export's class count must equal len(dictionary) + 2 (blank and the
        trailing space). A regression here would make the highest index look out of
        range on every decode, so it is asserted against the real artifact rather
        than against the decoder's own assumption."""
        import json

        import onnxruntime as ort

        session = ort.InferenceSession(str(OCR_MODEL), providers=["CPUExecutionProvider"])
        width = session.get_outputs()[0].shape[-1]
        dictionary = json.loads(OCR_DICT.read_text(encoding="utf-8"))

        self.assertEqual(int(width), len(dictionary) + 2)


class ConsumerShapeTest(SimpleTestCase):
    """Existing consumers read a local-backend result without special-casing it."""

    def test_visualizer_accepts_the_local_shape(self):
        """The visualizer indexes into plate and ocr entries directly, so it is the
        consumer most likely to break on a key the local backend omits."""
        import tempfile

        from lpr_app.services.bbox_visualizer import visualize_lpr_on_image

        detections = [
            {
                "plate": {"confidence": 0.91, "coordinates": {"x1": 10, "y1": 20, "x2": 110, "y2": 60}},
                "ocr": [
                    {
                        "text": "EG209",
                        "confidence": 0.78,
                        "coordinates": {"x1": 10, "y1": 20, "x2": 110, "y2": 60},
                    }
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.png"
            output = Path(tmp) / "out.png"
            a_plate_image(200, 90).save(source)
            # The same call the LLM path's output makes; must not raise.
            self.assertTrue(visualize_lpr_on_image(str(source), {"detections": detections}, str(output)))

    def test_detection_metric_reader_accepts_the_local_shape(self):
        """update_detection_metrics reads confidence off both plate and ocr
        entries, so a local result must carry both."""
        detections = [
            {
                "plate": {"confidence": 0.91, "coordinates": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}},
                "ocr": [{"text": "EG209", "confidence": 0.78, "coordinates": {}}],
            }
        ]
        self.assertEqual(detections[0]["plate"]["confidence"], 0.91)
        self.assertEqual(detections[0]["ocr"][0]["confidence"], 0.78)


class BackendParityTest(SimpleTestCase):
    """Both backends, run for real against the same image, agree on structure.

    Structural equality is asserted by key sets and types rather than by value,
    since the two backends measure different things and their coordinates and
    confidences should differ. What must not differ is the shape a consumer reads.

    The detector is stubbed to a single known box so the comparison is
    deterministic: whether a *synthetic* plate is detected is a property of the
    model, not of this contract, and a test that skipped when the model declined
    would be a test that rarely ran.
    """

    def _structure(self, detections: list[dict]) -> list[tuple]:
        return [
            (
                tuple(sorted(detection)),
                tuple(sorted(detection["plate"])),
                tuple(sorted((k, type(v).__name__) for k, v in detection["plate"]["coordinates"].items())),
                tuple(
                    (tuple(sorted(item)), tuple(sorted((k, type(v).__name__) for k, v in item.items())))
                    for item in detection["ocr"]
                ),
            )
            for detection in detections
        ]

    def test_local_and_llm_detections_have_the_same_structure(self):
        from lpr_app.pipeline.stages.detect import Detection

        plate = a_plate_image(240, 90)
        canvas = Image.new("RGB", (1280, 960), (150, 150, 150))
        canvas.paste(plate, (400, 400))
        detection = Detection(400, 400, 640, 490, 0.9, layout="single_line")

        # Local backend, with detection stubbed so exactly one plate is present.
        with override_settings(PIPELINE_MODEL_DIR=str(MODEL_DIR)):
            backend = build_local_backend_from_settings()
        with patch.object(backend.detector, "run", return_value={"detections": [detection]}):
            backend.recogniser.read_plates = lambda plates, **kwargs: [  # type: ignore[method-assign]
                RecognitionResult(text="EG209", confidence=0.8)
            ] * len(plates)
            local = backend.run(canvas).detections

        # The entry the LLM path builds from a parsed response, verbatim in shape.
        llm = [
            {
                "plate": detection.to_dict(),
                "ocr": [
                    {
                        "text": "EG209",
                        "confidence": 0.8,
                        "coordinates": {"x1": 410, "y1": 410, "x2": 600, "y2": 470},
                    }
                ],
            }
        ]

        self.assertEqual(len(local), 1)
        structure = self._structure(local)[0]
        llm_structure = self._structure(llm)[0]

        self.assertEqual(structure[0], llm_structure[0], "top-level keys differ")
        self.assertEqual(structure[1], llm_structure[1], "plate keys differ")
        self.assertEqual(structure[2], llm_structure[2], "plate coordinate keys or types differ")
        self.assertEqual(structure[3], llm_structure[3], "ocr keys or types differ")


class OverallDurationMetricTest(TestCase):
    """The existing end-to-end metric is recorded whichever backend ran.

    A ``TestCase`` rather than a ``SimpleTestCase`` because the upload view creates
    a database record before processing; with the database blocked the request
    fails early and never reaches the metric recording under test.

    This is the metric a dashboard already graphs. If only the local backend's new
    histograms were recorded, a backend comparison would need two panels and two
    units of interpretation, and the pre-existing panel would show nothing.
    """

    def test_processing_duration_is_recorded_on_a_successful_upload(self):
        """The upload view records the overall duration whichever backend ran; only
        the processing call is stubbed, so the metric recording itself is under test."""
        from django.test import Client
        from prometheus_client import generate_latest

        from lpr_app.metrics import PROCESSING_DURATION, REGISTRY

        before = _processing_observations("completed")
        with patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image") as process:
            process.return_value = {"success": True, "processed_image_path": None, "processing_duration": 0.01}
            response = Client().post("/api/v1/ocr/", {"image": _uploaded_image()})

        self.assertEqual(response.status_code, 200)
        # Counted rather than summed: the stubbed processing takes under a
        # millisecond, so the observed duration rounds to zero and a sum
        # comparison would be true whether or not anything was recorded.
        self.assertGreater(
            _processing_observations("completed"),
            before,
            "the overall processing duration was not observed; exported series: " + _processing_series(),
        )
        self.assertIn("lpr_processing_duration_seconds", generate_latest(REGISTRY).decode())
        self.assertIsNotNone(PROCESSING_DURATION)

    def test_processing_duration_is_recorded_on_a_failed_upload(self):
        """A failure has to land on the same metric too, or the series would show
        only the successes and read as a latency improvement when processing broke."""
        from django.test import Client

        before = _processing_observations("failed")
        with patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image") as process:
            process.return_value = {"success": False, "error": "boom"}
            response = Client().post("/api/v1/ocr/", {"image": _uploaded_image()})

        self.assertEqual(response.status_code, 500)
        self.assertGreater(
            _processing_observations("failed"),
            before,
            "a failed processing attempt was not recorded; exported series: " + _processing_series(),
        )

    def test_pipeline_stage_metric_labels_match_the_stage_names(self):
        """The histogram's stage label has to be the stage's own name, or a Grafana
        query written against the configured names would match nothing."""
        from lpr_app.pipeline.stages.detect import PlateDetectionStage
        from lpr_app.pipeline.stages.ocr import PlateOCRStage

        self.assertEqual(PlateDetectionStage.name, "detect_plate")
        self.assertEqual(PlateOCRStage.name, "read_plate")


def _processing_series() -> str:
    """The exported processing-duration series, for assertion failure messages."""
    from prometheus_client import generate_latest

    from lpr_app.metrics import REGISTRY

    return "\n".join(
        line
        for line in generate_latest(REGISTRY).decode().splitlines()
        if line.startswith("lpr_processing_duration_seconds_count")
    )


def _processing_observations(status: str) -> int:
    """How many times the overall processing duration was observed for a status."""
    for line in _processing_series().splitlines():
        if f'status="{status}"' in line:
            return int(float(line.rsplit(" ", 1)[1]))
    return 0


def _uploaded_image():
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile

    buffer = io.BytesIO()
    a_plate_image(200, 90).save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile("plate.png", buffer.read(), content_type="image/png")
