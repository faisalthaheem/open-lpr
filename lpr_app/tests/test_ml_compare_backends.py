"""Tests for the comparison tally's label wiring.

`compare_backends.py` drives real models and real endpoints, so most of it is not
unit-testable. What is testable is the part that has already gone wrong once:
whether a label reaches the report, and whether its absence is visible as absence
rather than as zero.

The distinction under test throughout is between "measured and wrong" and "not
measured". A corpus with no labels reporting CER 0.0 would be worse than useless —
it would look like a perfect result.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from lpr_app.ml.compare_backends import Tally, box_iou, match, percentile
from lpr_app.ml.recognition_scoring import RecognitionScore, load_labels


class TallyWithoutLabelsTests(SimpleTestCase):
    def test_no_labels_means_no_accuracy_key_at_all(self):
        report = Tally().report()
        # Absent rather than null: null cannot distinguish "unlabelled" from
        # "scored zero plates", and the note would have to be read to tell.
        self.assertNotIn("accuracy", report)
        self.assertIn("coverage and confidence only", report["text"]["note"])

    def test_empty_labels_file_behaves_as_unlabelled(self):
        self.assertNotIn("accuracy", Tally({}).report())

    def test_coverage_still_reported_without_labels(self):
        tally = Tally()
        # Coverage is reads over detected plates, so the detection tally has to
        # be primed first. measure_local/measure_llm always pair these.
        tally.observe_detection(matched=2, predicted=2, truth_count=2)
        tally.observe_text("QG260", 0.9, "single_line")
        tally.observe_text(None, 0.0, "single_line")
        report = tally.report()
        self.assertEqual(report["text"]["plates_read"], 1)
        self.assertEqual(report["text"]["read_coverage"], 0.5)


class TallyWithLabelsTests(SimpleTestCase):
    def test_labels_are_scored_into_accuracy(self):
        tally = Tally({"a.jpg#0": "QG260", "a.jpg#1": "SE428"})
        tally.observe_detection(matched=2, predicted=2, truth_count=2)
        tally.observe_text("0G260", 0.95, "single_line", "a.jpg#0")
        tally.observe_text("SE420", 0.6, "single_line", "a.jpg#1")
        accuracy = tally.report()["accuracy"]
        self.assertEqual(accuracy["labelled_plates"], 2)
        # One substitution in each of two five-character plates.
        self.assertAlmostEqual(accuracy["cer"], 2 / 10, places=4)
        self.assertEqual(accuracy["exact_match"], 0.0)

    def test_a_plate_missing_from_the_labels_is_skipped(self):
        # Not scored as an empty read. The plate was not transcribed, and
        # charging the backend for that would make partial annotation look like
        # a correctness failure.
        tally = Tally({"a.jpg#0": "QG260"})
        tally.observe_text("QG260", 0.9, "single_line", "a.jpg#0")
        tally.observe_text("WRONG", 0.9, "single_line", "a.jpg#1")
        accuracy = tally.report()["accuracy"]
        self.assertEqual(accuracy["labelled_plates"], 1)
        self.assertEqual(accuracy["exact_match"], 1.0)

    def test_unread_plate_with_a_label_counts_against_the_backend(self):
        # The counterpart to the case above: a label that does exist must be
        # scored even when the backend produced nothing.
        tally = Tally({"a.jpg#0": "QG260"})
        tally.observe_text(None, 0.0, "single_line", "a.jpg#0")
        accuracy = tally.report()["accuracy"]
        self.assertEqual(accuracy["labelled_plates"], 1)
        self.assertEqual(accuracy["unread"], 1)
        self.assertEqual(accuracy["cer"], 1.0)

    def test_note_reflects_that_accuracy_was_measured(self):
        tally = Tally({"a.jpg#0": "QG260"})
        tally.observe_text("QG260", 0.9, "single_line", "a.jpg#0")
        self.assertIn("accuracy against supplied labels", tally.report()["text"]["note"])

    def test_omitted_key_still_reports_coverage(self):
        # A caller that does not pass a key must not break tallying.
        tally = Tally({"a.jpg#0": "QG260"})
        tally.observe_text("QG260", 0.9, "single_line")
        self.assertEqual(tally.report()["text"]["plates_read"], 1)


class PlateKeyContractTests(SimpleTestCase):
    def test_labels_address_plates_by_image_and_index(self):
        # This is the contract between a hand-written labels file and the
        # scorer. `plate_key` and `load_labels` must agree on the format, or
        # every label silently misses and the run reports nothing scored.
        from lpr_app.ml.recognition_scoring import plate_key

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps({plate_key("val2017/000123.jpg", 1): "IDH4497"}))
            self.assertEqual(load_labels(path), {"val2017/000123.jpg#1": "IDH4497"})


class MatchingTests(SimpleTestCase):
    def test_identical_boxes_overlap_fully(self):
        self.assertAlmostEqual(box_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)

    def test_disjoint_boxes_do_not_overlap(self):
        self.assertEqual(box_iou((0, 0, 10, 10), (20, 20, 30, 30)), 0.0)

    def test_a_truth_box_with_no_prediction_pairs_with_none(self):
        pairs = match([], [{"bbox": [0, 0, 10, 10]}], 0.3)
        self.assertEqual(pairs[0][0], None)

    def test_a_prediction_below_threshold_is_not_matched(self):
        pairs = match([(0, 0, 10, 10)], [{"bbox": [100, 100, 10, 10]}], 0.3)
        self.assertEqual(pairs[0][0], None)

    def test_each_prediction_is_consumed_once(self):
        # Two truth boxes near one prediction: the second must not also claim it,
        # or one detection inflates recall across two plates.
        truths = [{"bbox": [0, 0, 10, 10]}, {"bbox": [1, 1, 10, 10]}]
        pairs = match([(0, 0, 10, 10)], truths, 0.3)
        self.assertEqual([index for index, _ in pairs], [0, None])

    def test_pairs_are_ordered_by_truth(self):
        # The scorer maps a pair index back to the plate's position in the
        # annotation list to build its label key, so ordering is load-bearing.
        truths = [{"bbox": [100, 100, 10, 10]}, {"bbox": [0, 0, 10, 10]}]
        pairs = match([(0, 0, 10, 10)], truths, 0.3)
        self.assertEqual([index for index, _ in pairs], [None, 0])


class PercentileTests(SimpleTestCase):
    def test_picks_the_expected_element(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.0), 1)
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.95), 5)

    def test_single_value(self):
        self.assertEqual(percentile([7], 0.5), 7)


class EmptyReportTests(SimpleTestCase):
    """A tally that observed nothing must not raise or fabricate numbers."""

    def test_unlabelled_empty_tally_reports_cleanly(self):
        report = Tally().report()
        self.assertEqual(report["latency"]["images"], 0)
        self.assertIsNone(report["detection"]["recall"])
        self.assertIsNone(report["text"]["read_coverage"])

    def test_labelled_empty_tally_reports_none_not_zero(self):
        report = Tally({"a.jpg#0": "QG260"}).report()
        self.assertIsNone(report["accuracy"]["cer"])
        self.assertIsNone(report["accuracy"]["exact_match"])


class ScoreCompositionTests(SimpleTestCase):
    def test_two_tallies_are_comparable(self):
        # Both backends are scored through the same Tally, which is what makes
        # their CER figures comparable at all.
        #
        # The setup mirrors the real trade: `llm` reads one plate perfectly and
        # returns nothing for the other; `local` reads both, one of them wrongly.
        # llm's CER is worse because an unread plate costs a full deletion. That
        # is the strict scoring choice doing its job -- a backend cannot look
        # accurate by declining to read.
        labels = {"a.jpg#0": "QG260", "a.jpg#1": "SE428"}
        local = Tally(labels)
        local.observe_detection(matched=2, predicted=2, truth_count=2)
        local.observe_text("0G260", 0.95, "single_line", "a.jpg#0")
        local.observe_text("SE428", 0.6, "single_line", "a.jpg#1")
        llm = Tally(labels)
        llm.observe_detection(matched=2, predicted=2, truth_count=2)
        llm.observe_text(None, 0.0, "single_line", "a.jpg#0")
        llm.observe_text("SE428", 0.98, "single_line", "a.jpg#1")

        local_accuracy = local.report()["accuracy"]
        llm_accuracy = llm.report()["accuracy"]
        # llm: one full deletion (5) over 10 characters. local: one substitution
        # (1) over 10.
        self.assertAlmostEqual(llm_accuracy["cer"], 0.5, places=4)
        self.assertAlmostEqual(local_accuracy["cer"], 0.1, places=4)
        # The asymmetry that matters: same exact-match rate, very different CER.
        # llm gets one plate exactly right and says nothing about the other,
        # which reads as the stronger result on exact-match alone.
        self.assertEqual(llm_accuracy["exact_match"], local_accuracy["exact_match"])
        self.assertEqual(llm_accuracy["unread"], 1)
        self.assertEqual(local_accuracy["unread"], 0)
        self.assertIsInstance(local.recognition, RecognitionScore)
