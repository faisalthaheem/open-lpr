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
    DEFAULT_PROFILES,
    CharsetProfile,
    PlateOCRStage,
    _as_probabilities,
    ctc_greedy_decode,
    load_charset,
    preprocess_batch,
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


class PreprocessBatchTest(TestCase):
    """A batch shares one width, padded to its widest member."""

    def test_batch_is_nchw_with_one_row_per_image(self):
        tensor, widths = preprocess_batch([plate_image(208, 109), plate_image(104, 109)])
        self.assertEqual(tensor.shape[0], 2)
        self.assertEqual(tensor.shape[1], 3)
        self.assertEqual(tensor.shape[2], 48)
        self.assertEqual(len(widths), 2)

    def test_padded_to_the_widest_member(self):
        tensor, widths = preprocess_batch([plate_image(208, 109), plate_image(104, 109)])
        self.assertEqual(tensor.shape[3], max(widths))

    def test_per_row_widths_are_reported_unpadded(self):
        _, widths = preprocess_batch([plate_image(208, 109), plate_image(104, 109)])
        self.assertLess(widths[1], widths[0])

    def test_padding_is_normalised_black_not_mid_grey(self):
        """Zero-filling would paint the pad mid-grey, where plate ink sits."""
        tensor, widths = preprocess_batch([plate_image(208, 109), plate_image(104, 109)])
        pad = tensor[1, :, :, widths[1] :]
        self.assertGreater(pad.size, 0, "this batch should contain padding to inspect")
        self.assertAlmostEqual(float(pad.max()), -1.0, places=5)

    def test_real_content_is_preserved_at_its_own_offset(self):
        tensor, widths = preprocess_batch([plate_image(208, 109), plate_image(104, 109)])
        narrow = preprocess_crop(plate_image(104, 109))
        self.assertTrue(np.allclose(tensor[1, :, :, : widths[1]], narrow[0]))

    def test_empty_batch_is_rejected(self):
        with self.assertRaises(StageError):
            preprocess_batch([])


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

    def test_script_profiles_keep_their_own_script(self):
        """Every shipped script profile must keep its own glyphs, Latin, and digits.

        Under "alphanumeric" any non-Latin glyph the multilingual recogniser
        decodes is stripped before the response is built; a deployment serving a
        non-Latin region must select that region's profile.
        """
        samples = {
            "thai": "ตก 8534",
            "arabic": "ص ب 9 1 2 3",
            "cyrillic": "А123ВС",
            "chinese": "苏A88888",
            "korean": "부산1234",
            "latin_extended": "ĞİŞğ01",
        }
        for name, sample in samples.items():
            profile = DEFAULT_PROFILES[name]
            kept = profile.sanitise(sample)
            self.assertTrue(
                any(c.isalpha() and c not in DEFAULT_CHARSET for c in kept),
                f"{name} stripped its own script: {sample!r} -> {kept!r}",
            )
            digits = [c for c in sample if c.isdigit()]
            for digit in digits:
                self.assertIn(digit, kept)

    def test_all_profile_keeps_everything_and_strips_separators(self):
        profile = DEFAULT_PROFILES["all"]
        self.assertEqual(profile.sanitise("ตก 8534"), "ตก8534")
        self.assertEqual(profile.sanitise("AB-12 CD"), "AB-12CD")

    def test_stage_built_with_a_profile_uses_it_by_default(self):
        """A profile passed at construction must survive to read time.

        It used to be accepted by the backend and dropped, so every deployment
        ran "alphanumeric" regardless of what it configured.
        """
        stage = PlateOCRStage(charset_profile="thai")
        self.assertEqual(stage.charset_profile, "thai")
        self.assertEqual(stage._profile_for({}).name, "thai")
        self.assertEqual(stage.use_profile(stage.charset_profile).sanitise("ตก 8534"), "ตก8534")

    def test_stage_defaults_to_alphanumeric(self):
        self.assertEqual(PlateOCRStage()._profile_for({}).name, "alphanumeric")


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

    def test_splitting_is_on_by_default(self):
        """Documented decision (2026-11 prod replay): the split completes every
        genuinely stacked read it touches, and read_plates' arbitration reverts
        any split that cuts real text or reads worse than the whole crop."""
        self.assertTrue(PlateOCRStage().split_stacked)

    def test_missing_crop_is_rejected(self):
        with self.assertRaises(StageError):
            PlateOCRStage().run({})

    def test_no_dictionary_is_an_error_not_a_silent_empty_result(self):
        """Reading text without a dictionary would silently return nothing."""
        with self.assertRaises(StageError):
            PlateOCRStage(dict_path=None)._ensure_charset()


class FakeRecogniser:
    """Stands in for a loaded session, recording the batch size of each call.

    The stage's batching contract is about how many crops reach the model per
    invocation and how many invocations happen. A fake that returns plausible CTC
    output and counts its calls tests that contract directly; a real model cannot
    report how many times it was called.

    It also stands in for ``LoadedSession``, so the runtime's own signature
    validation runs against it rather than being bypassed.
    """

    def __init__(self, labels_per_step: int = 4):
        self.calls: list[int] = []
        self.labels_per_step = labels_per_step
        self.input_names = ("x",)
        # Rank 4 NCHW with dynamic batch and width, as the real export declares.
        self.input_shapes = (("x", ("N", 3, 48, "W")),)
        self.output_names = PlateOCRStage.ONNX_OUTPUTS
        # The runtime reaches the ORT session through this attribute.
        self.session = self

    def run(self, output_names, feed):
        batch = int(feed["x"].shape[0])
        self.calls.append(batch)
        # One timestep per 8px of the shared width, as PP-OCR emits.
        steps = int(feed["x"].shape[3]) // 8
        # Label 1 is the first real character; index 0 is the CTC blank.
        raw = np.zeros((batch, steps, self.labels_per_step), dtype=np.float32)
        raw[:, 0, 1] = 1.0
        return [raw]


def stage_with_fake_session(**kwargs):
    stage = PlateOCRStage(**kwargs)
    stage.charset = ["", "A", "B", "C"]
    stage._loaded_dict = True
    stage._session = FakeRecogniser()
    return stage


class BatchBoundTest(TestCase):
    """One recognition per plate, and batched invocations within the bound."""

    def _plates(self, count):
        return [(plate_image(200, 100), "single_line") for _ in range(count)]

    def test_three_plates_produce_three_results(self):
        stage = stage_with_fake_session(batch_size=8)
        results = stage.read_plates(self._plates(3))
        self.assertEqual(len(results), 3)

    def test_results_are_in_plate_order(self):
        """Each result must line up with the plate it came from, not with the
        order the batch happened to pack them in."""
        stage = stage_with_fake_session(batch_size=2)
        plates = [
            (plate_image(200, 100), "single_line"),
            (plate_image(80, 100), "single_line"),
            (plate_image(280, 100), "single_line"),
        ]
        results = stage.read_plates(plates)
        self.assertEqual([r.text for r in results], ["A"] * 3)

    def test_no_plate_is_recognised_twice(self):
        """Every crop in the batch must come from a distinct plate, so the sum of
        the batch sizes equals the plate count."""
        stage = stage_with_fake_session(batch_size=8)
        stage.read_plates(self._plates(3))
        self.assertEqual(sum(stage._session.calls), 3)

    def test_batch_size_bounds_a_single_invocation(self):
        stage = stage_with_fake_session(batch_size=2)
        stage.read_plates(self._plates(5))
        self.assertTrue(all(size <= 2 for size in stage._session.calls), stage._session.calls)

    def test_more_plates_than_the_bound_span_several_invocations(self):
        stage = stage_with_fake_session(batch_size=2)
        stage.read_plates(self._plates(5))
        self.assertEqual(len(stage._session.calls), 3)

    def test_fewer_plates_than_the_bound_use_one_invocation(self):
        stage = stage_with_fake_session(batch_size=8)
        stage.read_plates(self._plates(3))
        self.assertEqual(len(stage._session.calls), 1)

    def test_a_stacked_plate_counts_once_not_twice(self):
        """Two rows of one plate are two crops of one plate, so a plate count of
        one must not produce two recogniser results."""
        stage = stage_with_fake_session(split_stacked=True, batch_size=8)
        # A balanced two-row crop so split_two_rows finds a gap.
        results = stage.read_plates([(plate_image(200, 100, text_rows=2), "stacked")])
        self.assertEqual(len(results), 1)
        # Rows are combined with order preserved, so "AA" rather than one "A".
        self.assertEqual(results[0].rows, ["A", "A"])
        self.assertEqual(results[0].text, "AA")

    def test_empty_input_produces_no_results_and_no_invocation(self):
        stage = stage_with_fake_session()
        self.assertEqual(stage.read_plates([]), [])
        self.assertEqual(stage._session.calls, [])

    def test_batch_size_is_at_least_one(self):
        self.assertEqual(PlateOCRStage(batch_size=0).batch_size, 1)


class ScriptedRecogniser:
    """Fake recogniser returning a scripted (text, confidence) per row.

    Scripts are consumed in invocation order: the first inference call takes
    the first script, and so on. That matches how ``read_plates`` orders its
    calls -- plate rows batched first, then one standalone inference per
    split plate for the whole-crop arbitration read.
    """

    def __init__(self, scripts, labels=("", "A", "B", "C", "D")):
        self.scripts = list(scripts)
        self.labels = labels
        self.labels_per_step = len(labels)
        self.calls: list[int] = []
        self.input_names = ("x",)
        self.input_shapes = (("x", ("N", 3, 48, "W")),)
        self.output_names = PlateOCRStage.ONNX_OUTPUTS
        self.session = self

    def run(self, output_names, feed):
        tensor = feed["x"]
        batch = int(tensor.shape[0])
        self.calls.append(batch)
        script = self.scripts.pop(0)
        assert len(script) == batch, (script, batch)
        # One timestep per 8px of shared width, as PP-OCR emits.
        steps = int(tensor.shape[3]) // 8
        raw = np.zeros((batch, steps, self.labels_per_step), dtype=np.float32)
        for row, (text, probability) in enumerate(script):
            step = 0
            for char in text:
                if step >= steps:
                    break
                label = self.labels.index(char)
                spread = (1.0 - probability) / (self.labels_per_step - 1)
                raw[row, step, :] = spread
                raw[row, step, label] = probability
                # A blank timestep between characters, as greedy CTC expects.
                step += 2
            # Remaining steps stay all-zero: uniform, so argmax is the blank.
        return [raw]


class SplitArbitrationTest(TestCase):
    """A split is kept only when it beats a standalone whole-crop read."""

    def _stage(self, scripts, **kwargs):
        stage = PlateOCRStage(split_stacked=True, batch_size=8, **kwargs)
        stage.charset = ["", "A", "B", "C", "D"]
        stage._loaded_dict = True
        stage._session = ScriptedRecogniser(scripts, labels=stage.charset)
        return stage

    def _stacked(self, stage):
        return stage.read_plates([(plate_image(208, 109, text_rows=2), "stacked")])[0]

    def test_split_wins_when_rows_are_full_and_more_confident(self):
        stage = self._stage([[("A", 0.9), ("A", 0.9)], [("A", 0.7)]])
        result = self._stacked(stage)
        self.assertEqual(result.text, "AA")
        self.assertEqual(result.rows, ["A", "A"])

    def test_split_at_equal_confidence_keeps_the_split(self):
        stage = self._stage([[("A", 0.8), ("A", 0.8)], [("A", 0.8)]])
        self.assertEqual(self._stacked(stage).text, "AA")

    def test_split_with_an_empty_row_falls_back_to_the_whole_read(self):
        """An empty row means the split cut through text: the prod BME365 case,
        where a caption cut produced rows ['', 'YBME6'] and lost a 0.996 read."""
        stage = self._stage([[("", 0.0), ("A", 0.9)], [("B", 0.8)]])
        result = self._stacked(stage)
        self.assertEqual(result.text, "B")
        self.assertEqual(result.rows, ["B"])

    def test_split_below_whole_confidence_falls_back(self):
        stage = self._stage([[("A", 0.5), ("A", 0.5)], [("B", 0.6)]])
        result = self._stacked(stage)
        self.assertEqual(result.text, "B")

    def test_the_whole_read_is_its_own_single_crop_inference(self):
        """Batching the whole crop with its rows pads it to the rows' width,
        and the bidirectional head reads the padding back into the text."""
        stage = self._stage([[("A", 0.9), ("A", 0.9)], [("A", 0.7)]])
        self._stacked(stage)
        self.assertEqual(stage._session.calls, [2, 1])

    def test_a_single_line_plate_pays_no_extra_inference(self):
        stage = self._stage([[("A", 0.9)]])
        stage.read_plates([(plate_image(208, 109), "single_line")])
        self.assertEqual(stage._session.calls, [1])

    def test_a_stacked_crop_that_does_not_separate_pays_no_extra_inference(self):
        """split_two_rows returning None means one row, so no arbitration."""
        stage = self._stage([[("A", 0.9)]])
        # One text row is one ink band: no gap to split on.
        stage.read_plates([(plate_image(208, 109, text_rows=1), "stacked")])
        self.assertEqual(stage._session.calls, [1])
