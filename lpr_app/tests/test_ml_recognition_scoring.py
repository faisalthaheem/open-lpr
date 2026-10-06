"""Tests for recognition scoring, and for a comparison report that has labels.

The scoring itself is pure, so it is testable without the corpus — which is the
point of splitting it out. The integration here covers the part that cannot be
tested synthetically: that a labels file actually reaches the report, and that
an unlabelled corpus still reports honestly rather than quietly reporting zero
accuracy.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from lpr_app.ml.recognition_scoring import (
    RecognitionScore,
    label_template,
    levenshtein,
    load_labels,
    normalise,
    plate_key,
    score_read,
)

# Keys in the fixture below are `<image path>#<plate index>`, which is the same
# format `compare_backends.py` uses, so a labels file authored against these
# fixtures loads unchanged against a real corpus.


class NormalisationTests(SimpleTestCase):
    def test_strips_separators_and_case(self):
        self.assertEqual(normalise("idh-4497"), "IDH4497")
        self.assertEqual(normalise("QG.260"), "QG260")

    def test_drops_characters_outside_alphanumerics(self):
        # The alphanumeric profile never emits these, so charging for them
        # would penalise the backend for the charset it is configured with.
        self.assertEqual(normalise("AB 12 إ"), "AB12")

    def test_none_and_empty_are_empty(self):
        self.assertEqual(normalise(None), "")
        self.assertEqual(normalise(""), "")


class LevenshteinTests(SimpleTestCase):
    def test_identical_is_zero(self):
        self.assertEqual(levenshtein("ABC", "ABC"), 0)

    def test_substitution_insertion_deletion(self):
        self.assertEqual(levenshtein("ABC", "ABX"), 1)
        self.assertEqual(levenshtein("ABC", "ABCD"), 1)
        self.assertEqual(levenshtein("ABC", "AC"), 1)

    def test_empty_operands(self):
        self.assertEqual(levenshtein("", "ABC"), 3)
        self.assertEqual(levenshtein("ABC", ""), 3)
        self.assertEqual(levenshtein("", ""), 0)

    def test_cited_misread_costs_one_character(self):
        # The QG.260 -> 0G260 case from COMPARISON.md. Whole plate is not
        # wrong, which is exactly what the edit distance is for.
        self.assertEqual(levenshtein("QG260", "0G260"), 1)


class ScoreReadTests(SimpleTestCase):
    def test_exact_match(self):
        scored = score_read("QG260", "qg-260")
        self.assertTrue(scored["exact"])
        self.assertEqual(scored["cer"], 0.0)

    def test_substitution_is_a_fraction_of_the_plate(self):
        scored = score_read("QG260", "0G260")
        self.assertAlmostEqual(scored["cer"], 0.2)

    def test_unread_is_a_full_deletion_not_an_exclusion(self):
        scored = score_read("QG260", None)
        self.assertTrue(scored["unread"])
        self.assertEqual(scored["distance"], 5)
        self.assertEqual(scored["cer"], 1.0)
        self.assertFalse(scored["exact"])

    def test_blank_truth_is_not_scored_as_accuracy(self):
        # Otherwise a corpus of blanks reports CER 0.0 and reads as perfect.
        self.assertTrue(score_read("", None)["blank_truth"])
        self.assertIsNone(score_read("", "AB12")["cer"])
        self.assertFalse(score_read("", "AB12")["exact"])


class RecognitionScoreTests(SimpleTestCase):
    def test_empty_corpus_reports_none_not_zero(self):
        # The difference between "no labels yet" and "perfect accuracy" is the
        # whole reason this gap matters. None must not collapse to 0.0.
        report = RecognitionScore().report()
        self.assertIsNone(report["cer"])
        self.assertIsNone(report["exact_match"])
        self.assertEqual(report["labelled_plates"], 0)

    def test_unread_counts_against_the_denominator(self):
        score = RecognitionScore()
        score.observe("QG260", "QG260", 0.9, "single_line", "a#0")
        score.observe("IDH4497", None, 0.0, "single_line", "a#1")
        report = score.report()
        self.assertEqual(report["labelled_plates"], 2)
        self.assertEqual(report["unread"], 1)
        self.assertAlmostEqual(report["cer"], round(7 / 12, 4))
        self.assertAlmostEqual(report["exact_match"], 0.5)

    def test_layouts_are_scored_separately(self):
        score = RecognitionScore()
        score.observe("QG260", "QG260", 0.9, "single_line", "a#0")
        score.observe("IDH4497", "XXX0000", 0.9, "stacked", "b#0")
        report = score.report()
        self.assertEqual(report["by_layout"]["single_line"]["exact_match"], 1.0)
        self.assertGreater(report["by_layout"]["stacked"]["cer"], 0.0)

    def test_confidence_bands_separate_correctness_from_confidence(self):
        # The open question is whether confidence is informative. Low-band
        # reads being wrong and high-band reads being right is the evidence
        # that makes a threshold a real lever rather than a coin flip.
        score = RecognitionScore()
        score.observe("QG260", "0G260", 0.4, "single_line", "a#0")
        score.observe("IDH4497", "IDH4497", 0.95, "single_line", "a#1")
        bands = score.report()["by_confidence"]
        self.assertAlmostEqual(bands["0.0-0.5"]["exact_match"], 0.0)
        self.assertAlmostEqual(bands["0.8-1.0"]["exact_match"], 1.0)

    def test_mismatches_are_capped_but_present(self):
        score = RecognitionScore()
        for index in range(60):
            score.observe("QG260", "XXXXXX", 0.9, "single_line", f"k{index}#0")
        report = score.report()
        self.assertEqual(report["labelled_plates"], 60)
        self.assertEqual(len(report["mismatches"]), 50)

    def test_blank_truth_is_excluded(self):
        score = RecognitionScore()
        score.observe("", None, 0.0, "single_line", "a#0")
        self.assertEqual(score.report()["labelled_plates"], 0)


class UnknownLayoutTests(SimpleTestCase):
    def test_unknown_layout_is_its_own_bucket(self):
        # Per-layout accuracy is only meaningful if the layout is right, and
        # aspect ratio cannot be relied on to say it. A plate the guess cannot
        # classify is recorded as unknown rather than folded into a bucket it may
        # not belong to.
        score = RecognitionScore()
        score.observe("QG260", "0G260", 0.6, "unknown", "a#0")
        score.observe("SE428", "SE428", 0.9, "single_line", "b#0")
        report = score.report()
        self.assertIn("unknown", report["by_layout"])
        self.assertLess(report["by_layout"]["unknown"]["exact_match"], 1.0)


class LabelFileTests(SimpleTestCase):
    def test_loads_flat_object(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps({"a.jpg#0": "QG260"}))
            self.assertEqual(load_labels(path), {"a.jpg#0": "QG260"})

    def test_loads_list_form_for_spreadsheet_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps([{"key": "a.jpg#0", "text": "QG260"}]))
            self.assertEqual(load_labels(path), {"a.jpg#0": "QG260"})

    def test_loads_wrapped_form(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps({"labels": {"a.jpg#0": "QG260"}}))
            self.assertEqual(load_labels(path), {"a.jpg#0": "QG260"})

    def test_template_carries_model_reads_for_annotation(self):
        # The transcriber overwrites these. Shipping the model's own read in
        # the file is a convenience, and a hazard if mistaken for truth -- which
        # is why the key identifies the plate and the value is what gets
        # replaced.
        self.assertEqual(label_template([(plate_key("a.jpg", 0), "0G260")]), {"a.jpg#0": "0G260"})

    def test_blank_labels_are_dropped(self):
        # A blank means "unreadable to the transcriber", i.e. no label. Keeping
        # it would score as a full-length deletion against the backend for a
        # plate no one managed to read.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps({"a.jpg#0": "QG260", "a.jpg#1": "", "a.jpg#2": "   "}))
            self.assertEqual(load_labels(path), {"a.jpg#0": "QG260"})


class LayoutGuessTests(SimpleTestCase):
    """`layout_of` declining is the point; these pin the boundary it draws."""

    def _ratio(self, ratio: float) -> str | None:
        from lpr_app.ml.compare_backends import layout_of

        return layout_of((0, 0, 100, 100 / ratio))

    def test_extreme_ratios_are_classified(self):
        self.assertEqual(self._ratio(1.3), "stacked")
        self.assertEqual(self._ratio(4.0), "single_line")

    def test_captured_plate_declines_rather_than_guessing(self):
        # EG·209 with an ICT-ISLAMABAD caption measures 1.91 and is one line.
        # L802 WGK measures 1.9 and is genuinely two rows. Any single threshold
        # here gets one of them wrong, so both are reported unknown.
        self.assertIsNone(self._ratio(1.91))
        self.assertIsNone(self._ratio(1.9))

    def test_degenerate_box_declines(self):
        from lpr_app.ml.compare_backends import layout_of

        self.assertIsNone(layout_of((0, 0, 100, 0)))

    def test_template_carries_model_reads_for_annotation(self):
        # The transcriber overwrites these. Shipping the model's own read in
        # the file is a convenience, and a hazard if mistaken for truth — which
        # is why the key is what identifies the plate and the value is what
        # gets replaced.
        template = label_template([(plate_key("a.jpg", 0), "0G260")])
        self.assertEqual(template, {"a.jpg#0": "0G260"})
