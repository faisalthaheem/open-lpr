"""Tests for the OCR stage: preprocessing, CTC decode, charset, and row splitting."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase

import numpy as np
from PIL import Image

from lpr_app.pipeline.stages.base import StageError
from lpr_app.pipeline.stages.ocr import (
    DEFAULT_CHARSET,
    CharsetProfile,
    PlateOCRStage,
    _as_probabilities,
    ctc_greedy_decode,
    load_charset,
    preprocess_crop,
    split_two_rows,
)


def plate_image(width=208, height=109, text_rows=1):
    """A light plate with dark bars standing in for glyphs."""
    array = np.full((height, width, 3), 230, dtype=np.uint8)
    if text_rows == 1:
        top, bottom = height // 3, 2 * height // 3
    else:
        top, bottom = height // 6, height // 2 - 4
    array[top:bottom, width // 10 : width - width // 10] = 30
    if text_rows == 2:
        array[height // 2 + 4 : height - height // 6, width // 10 : width - width // 10] = 30
    return Image.fromarray(array)


class PreprocessTest(TestCase):
    """Input is 48px tall with width bucketed to a multiple of 8."""

    def test_height_is_48_and_rank_is_nchw(self):
        tensor = preprocess_crop(plate_image(208, 109))
        self.assertEqual(tensor.shape[0], 1)
        self.assertEqual(tensor.shape[1], 3)
        self.assertEqual(tensor.shape[2], 48)

    def test_width_is_a_multiple_of_eight(self):
        for width in (100, 137, 208, 333):
            tensor = preprocess_crop(plate_image(width, 60))
            self.assertEqual(tensor.shape[3] % 8, 0, f"width {width} produced a non-bucketed shape")

    def test_width_is_bounded(self):
        tensor = preprocess_crop(plate_image(2000, 100), max_width=320)
        self.assertLessEqual(tensor.shape[3], 320)

    def test_aspect_ratio_is_preserved(self):
        tensor = preprocess_crop(plate_image(200, 100))
        self.assertAlmostEqual(tensor.shape[3] / 48, 200 / 100, delta=0.3)

    def test_normalisation_range(self):
        tensor = preprocess_crop(plate_image(208, 109))
        self.assertGreaterEqual(float(tensor.min()), -1.0)
        self.assertLessEqual(float(tensor.max()), 1.0)

    def test_degenerate_crop_is_rejected(self):
        with self.assertRaises(StageError):
            preprocess_crop(Image.new("RGB", (0, 10)))


class CTCDecodeTest(TestCase):
    """Greedy CTC decode collapses repeats and drops blanks."""

    def test_collapses_repeated_indices(self):
        # Two timesteps emitting the same class is one character.
        charset = ["", "A", "B"]
        # One-hot rows: index 0 is blank, others name the emitted class.
        probabilities = np.array(
            [
                [0.0, 1.0, 0.0],  # A
                [0.0, 1.0, 0.0],  # A again: a repeat, not a new character
                [0.0, 0.0, 1.0],  # B
                [1.0, 0.0, 0.0],  # blank
            ],
            dtype=np.float32,
        )
        text, confidences = ctc_greedy_decode(probabilities, charset)
        self.assertEqual(text, "AB")
        self.assertEqual(len(confidences), 2)

    def test_blank_between_same_char_keeps_both(self):
        # A blank separating identical characters is what yields "AA".
        charset = ["", "A"]
        probabilities = np.array(
            [
                [0.0, 1.0],  # A
                [1.0, 0.0],  # blank separating the two identical characters
                [0.0, 1.0],  # A
            ],
            dtype=np.float32,
        )
        text, _ = ctc_greedy_decode(probabilities, charset)
        self.assertEqual(text, "AA")

    def test_all_blank_yields_empty_text(self):
        charset = ["", "A"]
        probabilities = np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (5, 1))
        text, confidences = ctc_greedy_decode(probabilities, charset)
        self.assertEqual(text, "")
        self.assertEqual(confidences, [])

    def test_confidence_is_mean_of_emitted_steps(self):
        charset = ["", "A"]
        probabilities = np.array([[0.2, 0.8], [1.0, 0.0]], dtype=np.float32)
        text, confidences = ctc_greedy_decode(probabilities, charset)
        self.assertEqual(text, "A")
        self.assertAlmostEqual(confidences[0], 0.8, places=5)

    def test_wrong_rank_is_rejected(self):
        with self.assertRaises(StageError):
            ctc_greedy_decode(np.zeros((2, 2, 2)), ["", "A"])


class ProbabilityHandlingTest(TestCase):
    """Already-normalised output must not be softmaxed again."""

    def test_normalised_input_is_passed_through(self):
        raw = np.array([[0.7, 0.3, 0.0, 0.0], [0.0, 0.0, 0.7, 0.3]], dtype=np.float32)
        result = _as_probabilities(raw)
        np.testing.assert_allclose(result, raw)

    def test_logits_are_softmaxed(self):
        raw = np.array([[2.0, 1.0, 0.0]], dtype=np.float32)
        result = _as_probabilities(raw)
        np.testing.assert_allclose(result.sum(axis=-1), np.ones(1), rtol=1e-5)
        self.assertGreater(result[0, 0], result[0, 2])

    def test_confidence_survives_the_round_trip(self):
        """Guards the bug where a second softmax flattened confidence to zero."""
        raw = np.array(
            [
                [0.0, 1.0, 0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )
        text, confidences = ctc_greedy_decode(_as_probabilities(raw), ["", "A", "B"])
        self.assertEqual(text, "A")
        self.assertGreater(confidences[0], 0.85, "confidence must reflect the real peak, not be squashed")

    def test_rank_three_is_reduced(self):
        raw = np.array([[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]], dtype=np.float32)
        self.assertEqual(_as_probabilities(raw).shape, (2, 4))


class CharsetTest(TestCase):
    """Decoding is restricted to a selectable profile."""

    def test_default_is_alphanumeric(self):
        self.assertEqual(DEFAULT_CHARSET, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_default_profile_strips_non_alphanumerics(self):
        profile = CharsetProfile("default", DEFAULT_CHARSET)
        self.assertEqual(profile.sanitise("AB-12 CD"), "AB12CD")

    def test_profile_excludes_configured_characters(self):
        profile = CharsetProfile("no_io", "".join(c for c in DEFAULT_CHARSET if c not in "IO"))
        self.assertNotIn("I", profile.sanitise("IABC"))
        self.assertNotIn("O", profile.sanitise("OABC"))
        self.assertEqual(profile.sanitise("IABC"), "ABC")

    def test_lowercase_is_excluded_by_default(self):
        profile = CharsetProfile("upper", DEFAULT_CHARSET)
        # Lowercase is not in the default profile, so 'a' and 'c' are dropped and
        # only the uppercase letter and the digit survive.
        self.assertEqual(profile.sanitise("aBc1"), "B1")
        self.assertTrue(set(profile.sanitise("aBc1")).isdisjoint("abc"))

    def test_empty_result_when_nothing_permitted(self):
        profile = CharsetProfile("empty", "")
        self.assertEqual(profile.sanitise("ABC123"), "")

    def test_profiles_are_selectable_at_runtime(self):
        stage = PlateOCRStage()
        self.assertEqual(stage.use_profile("alphanumeric").name, "alphanumeric")
        self.assertEqual(stage.use_profile("no_io").name, "no_io")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(StageError) as ctx:
            PlateOCRStage().use_profile("martian")
        self.assertIn("martian", str(ctx.exception))


class CharsetFileTest(TestCase):
    """The dictionary is loaded and labelled correctly."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "dict.json"
        self.path.write_text(json.dumps(["A", "B", "C"], ensure_ascii=False), encoding="utf-8")

    def test_blank_is_index_zero(self):
        charset = load_charset(self.path)
        self.assertEqual(charset[0], "", "index 0 must be the CTC blank")

    def test_dictionary_follows_blank(self):
        charset = load_charset(self.path)
        self.assertEqual(charset[1:4], ["A", "B", "C"])

    def test_trailing_space_class_is_present(self):
        """The CTC head emits len(dict)+2 columns: blank, dictionary, space."""
        charset = load_charset(self.path)
        self.assertEqual(charset[-1], " ")
        self.assertEqual(len(charset), 5)

    def test_missing_file_is_reported(self):
        with self.assertRaises(StageError) as ctx:
            load_charset(Path(self.tmp.name) / "absent.json")
        self.assertIn("absent.json", str(ctx.exception))

    def test_non_list_is_rejected(self):
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text('{"a": 1}', encoding="utf-8")
        with self.assertRaises(StageError):
            load_charset(bad)


class RowSplittingTest(TestCase):
    """Row splitting must not fire on a single-row crop."""

    def test_single_row_plate_is_not_split(self):
        self.assertIsNone(split_two_rows(plate_image(208, 109, text_rows=1)))

    def test_single_row_with_caption_is_not_split(self):
        """A small caption under a large registration must not be read as a row.

        This is the case that made splitting net-negative on the corpus: a
        single-line plate carrying a state name was read as two lines and the
        caption was appended to the registration.
        """
        array = np.full((109, 208, 3), 230, dtype=np.uint8)
        array[30:70, 20:188] = 30  # large registration
        array[80:92, 20:188] = 60  # small caption
        self.assertIsNone(split_two_rows(Image.fromarray(array)))

    def test_balanced_two_row_plate_is_split(self):
        array = np.full((120, 160, 3), 230, dtype=np.uint8)
        array[15:45, 15:145] = 30
        array[75:105, 15:145] = 30
        rows = split_two_rows(Image.fromarray(array))
        self.assertIsNotNone(rows)
        self.assertEqual(len(rows), 2)
        # The cut lands in the blank band between the two glyph blocks, so the
        # rows are near-equal but not necessarily exactly half.
        self.assertLess(abs(rows[0].height - rows[1].height), rows[0].height)

    def test_blank_image_is_not_split(self):
        self.assertIsNone(split_two_rows(Image.new("RGB", (200, 100), (255, 255, 255))))

    def test_tiny_crop_is_not_split(self):
        self.assertIsNone(split_two_rows(Image.new("RGB", (40, 6), (230, 230, 230))))


class StageContractTest(TestCase):
    """The stage satisfies the graph's routing contract."""

    def test_declares_inputs_and_outputs(self):
        stage = PlateOCRStage()
        self.assertEqual(stage.inputs, ("plate_crop",))
        self.assertEqual(stage.outputs, ("ocr",))

    def test_splitting_is_off_by_default(self):
        """Documented decision: splitting appends captions more often than it
        rescues stacked plates on this corpus."""
        self.assertFalse(PlateOCRStage().split_stacked)

    def test_missing_crop_is_rejected(self):
        with self.assertRaises(StageError):
            PlateOCRStage().run({})

    def test_no_dictionary_is_an_error_not_a_silent_empty_result(self):
        """Reading text without a dictionary would silently return nothing."""
        with self.assertRaises(StageError):
            PlateOCRStage(dict_path=None)._ensure_charset()
