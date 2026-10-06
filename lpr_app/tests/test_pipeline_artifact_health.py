"""Artifact integrity as a runtime health signal.

Download-time verification only proves the bytes arrived intact at that moment.
This covers the case where they stop being intact: a truncated volume write, a
tampered or recycled mount. The recogniser paired with a mismatched dictionary
reads as plausible text rather than erroring, so a silent OCR failure is exactly
the kind an operator is least likely to notice.

The caching behaviour is tested as carefully as the verdict itself -- an
unbounded re-hash on every health request would replace an invisible failure
with a visible latency problem.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from lpr_app.pipeline import fetch_artifacts
from lpr_app.pipeline.artifact_health import check_integrity, invalidate

DETECTOR = "plate_yolox_tiny_640.onnx"
RECOGNISER = "plate_ocr_ppocrv5_mobile.onnx"
DICTIONARY = "plate_ocr_dict.json"


class IntegrityCheckTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.model_dir = Path(self.tmp.name) / "plate"
        self.model_dir.mkdir(parents=True)
        for name in (DETECTOR, RECOGNISER, DICTIONARY):
            (self.model_dir / name).write_bytes(b"x")

    def _mock_verify(self, result):
        """Patch verify_artifacts for the whole test, not one call.

        Several tests call check_integrity twice -- once to prime the cache and
        once to read it. A patch scoped to the first call would let the second
        reach the real function and hit the filesystem.
        """
        patcher = patch.object(fetch_artifacts, "verify_artifacts", return_value=result)
        self.addCleanup(patcher.stop)
        return patcher.start()

    @override_settings(PIPELINE_MODEL_DIR="/nonexistent")
    def test_missing_artifacts_are_unhealthy(self):
        verify = self._mock_verify({"ok": False, "missing": [DETECTOR], "corrupt": []})
        self.assertIsNotNone(verify)
        result = check_integrity(use_cache=False)

        self.assertFalse(result["ok"])
        self.assertIn(DETECTOR, result["missing"])

    @override_settings(PIPELINE_MODEL_DIR="/nonexistent")
    def test_corrupt_artifact_is_unhealthy(self):
        self._mock_verify({"ok": False, "missing": [], "corrupt": [RECOGNISER]})
        result = check_integrity(use_cache=False)

        self.assertFalse(result["ok"])
        self.assertIn(RECOGNISER, result["corrupt"])

    def test_all_correct_is_healthy(self):
        self._mock_verify({"ok": True, "missing": [], "corrupt": []})
        self.assertTrue(check_integrity(use_cache=False)["ok"])

    @override_settings(PIPELINE_MODEL_DIR="/nonexistent")
    def test_unreachable_manifest_is_unknown_not_corrupt(self):
        """Integrity unknown must not be reported as corrupt.

        Otherwise a transient DNS failure pages someone about a bad artifact
        that is in fact perfectly fine.
        """
        self._mock_verify({"ok": True, "unverified": True, "missing": [], "corrupt": []})
        result = check_integrity(use_cache=False)

        self.assertTrue(result["ok"])
        self.assertTrue(result.get("unverified"))
        self.assertEqual(result["corrupt"], [])

    def test_result_is_cached(self):
        verify = self._mock_verify({"ok": True, "missing": [], "corrupt": []})

        check_integrity()
        check_integrity()
        check_integrity()

        # One call did the work; the rest read the cache.
        self.assertEqual(verify.call_count, 1)

    def test_invalidate_forces_reverification(self):
        verify = self._mock_verify({"ok": True, "missing": [], "corrupt": []})

        check_integrity()
        invalidate()
        check_integrity()

        self.assertEqual(verify.call_count, 2)

    def test_use_cache_false_bypasses_the_cache(self):
        verify = self._mock_verify({"ok": True, "missing": [], "corrupt": []})

        check_integrity()
        check_integrity(use_cache=False)

        self.assertEqual(verify.call_count, 2)

    @override_settings(
        PIPELINE_DETECTOR_MODEL=DETECTOR,
        PIPELINE_OCR_MODEL=RECOGNISER,
        PIPELINE_OCR_DICT=DICTIONARY,
    )
    def test_checks_exactly_the_configured_artifacts(self):
        """Verification must follow configuration, not a hardcoded list.

        An operator pointing at a differently-named detector would otherwise get
        a clean health check that never looked at the file being loaded.
        """
        from unittest.mock import MagicMock

        verify = MagicMock(return_value={"ok": True, "missing": [], "corrupt": []})
        with patch.object(fetch_artifacts, "verify_artifacts", verify):
            with override_settings(PIPELINE_MODEL_DIR=str(self.model_dir)):
                check_integrity(use_cache=False)

        checked = verify.call_args.args[2]
        self.assertEqual(checked, [DETECTOR, RECOGNISER, DICTIONARY])


class RealArtifactTests(SimpleTestCase):
    """Against artifacts actually on disk, when they exist.

    Skipped rather than mocked when the model directory is absent, which is the
    normal case in CI until task 6 lands.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _artifacts_present(self) -> bool:
        from lpr_app.pipeline.artifact_health import configured_artifacts, model_dir

        return all((model_dir() / name).is_file() for name in configured_artifacts())

    def test_real_artifacts_verify(self):
        if not self._artifacts_present():
            self.skipTest("model artifacts not present")

        result = check_integrity(use_cache=False)

        self.assertTrue(result["ok"], f"artifacts failed verification: {result}")
