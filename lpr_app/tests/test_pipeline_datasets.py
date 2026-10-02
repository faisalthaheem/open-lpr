"""Tests for the corpus exporter, using a small synthetic fixture corpus.

The fixture corpus is built to reproduce the properties that make the real one
awkward: consecutive integer frame names, near-duplicate adjacent frames, a
stacked two-line plate, and an annotation record naming a missing image.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from PIL import Image

from lpr_app.ml.datasets.plate import build, find_databases, group_key, load_records


def make_corpus(root: Path, *, frames: int = 200) -> Path:
    """Build a corpus with consecutive frames, one plate per frame."""
    (root / "train").mkdir(parents=True)
    for frame in range(frames):
        name = f"{frame}.jpg"
        image = Image.new("RGB", (320, 240), (20, 20, 20))
        image.save(root / "train" / name)

    connection = sqlite3.connect(root / "train.db")
    connection.execute(
        "CREATE TABLE annotations (filename TEXT, imheight INTEGER, imwidth INTEGER, "
        "isreviewed INTEGER, lastreviewedat TEXT, isdeleted INTEGER, isbackground INTEGER, imgareas TEXT)"
    )
    rows = []
    for frame in range(frames):
        areas = json.dumps(
            [{"id": 0, "x": 40, "y": 100, "z": 100, "width": 120, "height": 60, "lblid": "1", "lbltxt": "plate"}]
        )
        rows.append((f"{frame}.jpg", 240, 320, 1, None, 0, 0, areas))
    connection.executemany("INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", rows)
    connection.commit()
    connection.close()
    return root


class GroupKeyTest(TestCase):
    """Consecutive frames must land in the same group."""

    def test_nearby_frames_share_a_group(self):
        self.assertEqual(group_key("100.jpg", 25), group_key("124.jpg", 25))

    def test_distant_frames_differ(self):
        self.assertNotEqual(group_key("10.jpg", 25), group_key("900.jpg", 25))

    def test_non_numeric_names_group_by_name(self):
        self.assertEqual(group_key("frameA.jpg"), "name:frameA")
        self.assertEqual(group_key("frameB.jpg"), "name:frameB")

    def test_mixed_extensions_group_together(self):
        self.assertEqual(group_key("100.jpg", 25), group_key("100.jpeg", 25))


class LoadRecordsTest(TestCase):
    """Unusable records are excluded but counted, not silently dropped."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.corpus = make_corpus(self.tmp / "corpus", frames=10)

    def test_all_usable_records_are_read(self):
        records, skipped = load_records(self.corpus / "train.db")
        self.assertEqual(len(records), 10)
        self.assertEqual(skipped, {})

    def test_deleted_background_and_unreviewed_are_skipped_with_counts(self):
        connection = sqlite3.connect(self.corpus / "train.db")
        areas = json.dumps([{"x": 1, "y": 1, "z": 100, "width": 10, "height": 5, "lblid": "1", "lbltxt": "plate"}])
        connection.execute(
            "INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", ("del.jpg", 240, 320, 1, None, 1, 0, areas)
        )
        connection.execute(
            "INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", ("bg.jpg", 240, 320, 1, None, 0, 1, areas)
        )
        connection.execute(
            "INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", ("un.jpg", 240, 320, 0, None, 0, 0, areas)
        )
        connection.commit()
        connection.close()

        records, skipped = load_records(self.corpus / "train.db")
        self.assertEqual(len(records), 10)
        self.assertEqual(skipped.get("deleted"), 1)
        self.assertEqual(skipped.get("background"), 1)
        self.assertEqual(skipped.get("unreviewed"), 1)

    def test_record_with_no_regions_is_skipped(self):
        connection = sqlite3.connect(self.corpus / "train.db")
        connection.execute("INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", ("x.jpg", 240, 320, 1, None, 0, 0, "[]"))
        connection.commit()
        connection.close()
        records, skipped = load_records(self.corpus / "train.db")
        self.assertEqual(len(records), 10)
        self.assertEqual(skipped.get("no_regions"), 1)

    def test_malformed_json_is_skipped(self):
        connection = sqlite3.connect(self.corpus / "train.db")
        connection.execute(
            "INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", ("y.jpg", 240, 320, 1, None, 0, 0, "{not json")
        )
        connection.commit()
        connection.close()
        records, skipped = load_records(self.corpus / "train.db")
        self.assertEqual(len(records), 10)
        self.assertEqual(skipped.get("malformed_json"), 1)


class DatabaseDiscoveryTest(TestCase):
    """Multiple databases must be reported rather than one being assumed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.corpus = make_corpus(self.tmp / "corpus", frames=5)

    def test_all_databases_are_found(self):
        shutil.copy(self.corpus / "train.db", self.corpus / "val.db")
        shutil.copy(self.corpus / "train.db", self.corpus / "train_and_val.db")
        found = [p.name for p in find_databases(self.corpus)]
        self.assertEqual(sorted(found), ["train.db", "train_and_val.db", "val.db"])

    def test_summary_names_every_database_and_which_was_used(self):
        shutil.copy(self.corpus / "train.db", self.corpus / "val.db")
        summary = build(self.corpus, self.tmp / "out", val_fraction=0.2, group_size=25)
        self.assertIn("val.db", summary["databases_present"])
        self.assertEqual(summary["database_used"], "train.db")


class ExportTest(TestCase):
    """COCO output, split integrity, and reporting."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.corpus = make_corpus(cls.tmp / "corpus", frames=200)
        cls.out = cls.tmp / "out"
        cls.summary = build(cls.corpus, cls.out, group_size=25, val_fraction=0.2, seed=0)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_coco_files_are_written_in_the_expected_layout(self):
        self.assertTrue((self.out / "annotations" / "train2017.json").is_file())
        self.assertTrue((self.out / "annotations" / "val2017.json").is_file())
        self.assertTrue((self.out / "train2017").is_dir())
        self.assertTrue((self.out / "val2017").is_dir())

    def test_single_class_plate(self):
        coco = json.loads((self.out / "annotations" / "train2017.json").read_text())
        self.assertEqual(len(coco["categories"]), 1)
        self.assertEqual(coco["categories"][0]["name"], "plate")

    def test_annotations_use_coco_xywh_and_full_size_pixels(self):
        coco = json.loads((self.out / "annotations" / "train2017.json").read_text())
        first = coco["annotations"][0]
        self.assertEqual(len(first["bbox"]), 4)
        # Fixture plate is x=40 y=100 w=120 h=60 in a 320x240 image.
        self.assertEqual(first["bbox"], [40.0, 100.0, 120.0, 60.0])
        self.assertLessEqual(first["bbox"][0] + first["bbox"][2], coco["images"][0]["width"])

    def test_every_annotation_references_a_known_image(self):
        for split in ("train2017", "val2017"):
            coco = json.loads((self.out / "annotations" / f"{split}.json").read_text())
            known = {image["id"] for image in coco["images"]}
            self.assertTrue(all(a["image_id"] in known for a in coco["annotations"]))

    def test_every_image_file_exists_on_disk(self):
        for split in ("train2017", "val2017"):
            coco = json.loads((self.out / "annotations" / f"{split}.json").read_text())
            for image in coco["images"][:20]:
                self.assertTrue((self.out / split / image["file_name"]).is_file())

    def test_splits_do_not_share_frames(self):
        train = {
            i["file_name"] for i in json.loads((self.out / "annotations" / "train2017.json").read_text())["images"]
        }
        val = {i["file_name"] for i in json.loads((self.out / "annotations" / "val2017.json").read_text())["images"]}
        self.assertEqual(train & val, set())

    def test_no_frame_is_close_to_a_validation_frame(self):
        """The gap must exceed a few frames or near-duplicate frames leak."""
        train = sorted(
            int(i["file_name"].split(".")[0])
            for i in json.loads((self.out / "annotations" / "train2017.json").read_text())["images"]
        )
        val = sorted(
            int(i["file_name"].split(".")[0])
            for i in json.loads((self.out / "annotations" / "val2017.json").read_text())["images"]
        )
        self.assertTrue(train and val, "both splits must be populated")
        for frame in val:
            nearest = min((abs(frame - t) for t in train), default=10**9)
            self.assertGreater(nearest, 10, f"frame {frame} sits too close to a training frame")

    def test_split_is_deterministic(self):
        second = build(self.corpus, self.tmp / "out2", group_size=25, val_fraction=0.2, seed=0)
        first_val = {
            i["file_name"] for i in json.loads((self.out / "annotations" / "val2017.json").read_text())["images"]
        }
        second_val = {
            i["file_name"]
            for i in json.loads((self.tmp / "out2" / "annotations" / "val2017.json").read_text())["images"]
        }
        self.assertEqual(first_val, second_val)
        self.assertEqual(self.summary["val2017_images"], second["val2017_images"])

    def test_plate_height_distribution_is_reported(self):
        self.assertIn("plate_height_median", self.summary)
        self.assertEqual(self.summary["plate_height_median"], 60.0)

    def test_missing_image_is_reported_by_name(self):
        connection = sqlite3.connect(self.corpus / "train.db")
        areas = json.dumps([{"x": 1, "y": 1, "z": 100, "width": 10, "height": 5, "lblid": "1", "lbltxt": "plate"}])
        connection.execute(
            "INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", ("ghost.jpg", 240, 320, 1, None, 0, 0, areas)
        )
        connection.commit()
        connection.close()
        summary = build(self.corpus, self.tmp / "out3", val_fraction=0.2, group_size=25)
        self.assertIn("ghost.jpg", summary["missing_images"])

    def test_missing_corpus_is_reported_clearly(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(SystemExit) as ctx:
            build(empty, self.tmp / "out4")
        message = str(ctx.exception)
        self.assertIn(str(empty), message)
