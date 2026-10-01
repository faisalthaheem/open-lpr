"""
Tests that media path partitioning uses an aware clock matching stored timestamps.
"""

import datetime as dt
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils.timezone import now as real_now

from lpr_app.models import upload_to_processed, upload_to_uploads


class MediaPathTimezoneTest(SimpleTestCase):
    @override_settings(TIME_ZONE="Pacific/Kiritimati")  # UTC+14
    def test_path_date_matches_upload_timestamp_date_in_utc(self):
        """A far-from-UTC server must not bucket media into a different day."""
        fixed = dt.datetime(2026, 3, 15, 23, 30, tzinfo=dt.timezone.utc)

        with patch("django.utils.timezone.now", return_value=fixed):
            path = upload_to_uploads(MagicMock(), "car.jpg")

        self.assertTrue(path.startswith("uploads/2026/03/15/"))
        self.assertTrue(path.endswith("car.jpg"))

    @override_settings(TIME_ZONE="Pacific/Midway")  # UTC-11
    def test_path_prefix_and_segment_structure_unchanged(self):
        fixed = dt.datetime(2026, 7, 4, 12, 0, tzinfo=dt.timezone.utc)

        with patch("django.utils.timezone.now", return_value=fixed):
            uploads = upload_to_uploads(MagicMock(), "car.jpg")
            processed = upload_to_processed(MagicMock(), "car.jpg")

        self.assertRegex(uploads, r"^uploads/\d{4}/\d{2}/\d{2}/[0-9a-f]{8}_car\.jpg$")
        self.assertRegex(processed, r"^processed/\d{4}/\d{2}/\d{2}/[0-9a-f]{8}_car\.jpg$")

    def test_month_and_day_are_zero_padded(self):
        fixed = dt.datetime(2026, 1, 5, 0, 0, tzinfo=dt.timezone.utc)

        with patch("django.utils.timezone.now", return_value=fixed):
            path = upload_to_uploads(MagicMock(), "car.jpg")

        self.assertTrue(path.startswith("uploads/2026/01/05/"))

    def test_path_uses_aware_clock(self):
        captured = []

        def _record():
            value = real_now()
            captured.append(value)
            return value

        with patch("django.utils.timezone.now", side_effect=_record):
            upload_to_uploads(MagicMock(), "car.jpg")

        self.assertEqual(len(captured), 1)
        self.assertIsNotNone(captured[0].tzinfo)
