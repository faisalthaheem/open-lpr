"""
Tests for the shared Qwen3-VL client and its response parsing helpers.
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from lpr_app.services.qwen_client import (
    QwenVLClient,
    _extract_json_text,
    get_qwen_client,
    parse_detection_response,
    parse_ocr_response,
    reset_qwen_client,
)


class QwenClientCachingTest(SimpleTestCase):
    """The client owns an httpx connection pool and must be reused, not rebuilt."""

    def setUp(self):
        reset_qwen_client()
        self.addCleanup(reset_qwen_client)

    @override_settings(QWEN_API_KEY="test-key", QWEN_BASE_URL="http://example.invalid/v1", QWEN_MODEL="m")
    def test_repeated_calls_return_same_instance(self):
        with patch("lpr_app.services.qwen_client.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            first = get_qwen_client()
            second = get_qwen_client()

        self.assertIs(first, second)

    @override_settings(QWEN_API_KEY="test-key", QWEN_BASE_URL="http://example.invalid/v1", QWEN_MODEL="m")
    def test_connection_pool_is_constructed_once(self):
        with patch("lpr_app.services.qwen_client.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            get_qwen_client()
            get_qwen_client()
            get_qwen_client()

        self.assertEqual(mock_openai.call_count, 1)

    @override_settings(QWEN_API_KEY="", QWEN_BASE_URL="http://example.invalid/v1", QWEN_MODEL="m")
    def test_missing_api_key_raises(self):
        with self.assertRaises(ValueError):
            get_qwen_client()

    @override_settings(QWEN_API_KEY="", QWEN_BASE_URL="http://example.invalid/v1", QWEN_MODEL="m")
    def test_failed_construction_is_not_cached(self):
        """lru_cache must not memoize a failure, or a fixed config stays broken."""
        with self.assertRaises(ValueError):
            get_qwen_client()

        with override_settings(QWEN_API_KEY="recovered-key", QWEN_MODEL="m"):
            with patch("lpr_app.services.qwen_client.OpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()
                client = get_qwen_client()

        self.assertEqual(client.api_key, "recovered-key")

    @override_settings(QWEN_API_KEY="test-key", QWEN_BASE_URL="http://example.invalid/v1", QWEN_MODEL="m")
    def test_reset_discards_cached_client(self):
        with patch("lpr_app.services.qwen_client.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            first = get_qwen_client()
            reset_qwen_client()
            second = get_qwen_client()

        self.assertIsNot(first, second)


@override_settings(QWEN_API_KEY="test-key", QWEN_BASE_URL="http://example.invalid/v1", QWEN_MODEL="m")
class QwenBatchInferenceTest(SimpleTestCase):
    """One bad plate crop must not discard results for the other crops."""

    # Setting QWEN_API_KEY matters: QwenVLClient refuses to construct without one,
    # so without this the class only passes where a developer's local .env happens
    # to supply a placeholder key.

    def _client(self, side_effect):
        with patch("lpr_app.services.qwen_client.OpenAI") as mock_openai:
            completions = MagicMock()
            completions.chat.completions.create.side_effect = side_effect
            mock_openai.return_value = completions
            return QwenVLClient()

    def _response(self, text):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = text
        return resp

    def test_one_failure_preserves_other_results(self):
        client = self._client([self._response("first"), Exception("boom"), self._response("third")])

        results = client.analyze_images_batch(["a", "b", "c"], "prompt")

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], "first")
        self.assertIsNone(results[1])
        self.assertEqual(results[2], "third")

    def test_all_failures_return_full_length_list_of_empties(self):
        client = self._client([Exception("a"), Exception("b")])

        results = client.analyze_images_batch(["x", "y"], "prompt")

        self.assertEqual(results, [None, None])

    def test_empty_batch_returns_empty_list(self):
        client = self._client([])

        self.assertEqual(client.analyze_images_batch([], "prompt"), [])

    def test_failure_does_not_abort_remaining_requests(self):
        """The client must keep calling after a failure, not re-raise."""
        client = self._client([Exception("a"), self._response("ok")])

        results = client.analyze_images_batch(["x", "y"], "prompt")

        self.assertEqual(results[1], "ok")


class ExtractJsonTextTest(TestCase):
    def test_json_tagged_fence(self):
        self.assertEqual(_extract_json_text('```json\n{"a": 1}\n```'), '{"a": 1}')

    def test_bare_fence(self):
        self.assertEqual(_extract_json_text('```\n{"a": 1}\n```'), '{"a": 1}')

    def test_no_fence(self):
        self.assertEqual(_extract_json_text('  {"a": 1}  '), '{"a": 1}')

    def test_unterminated_fence_takes_content_to_end(self):
        # A naive find() returns -1 here and would silently drop the last character.
        self.assertEqual(_extract_json_text('```json\n{"a": 1}'), '{"a": 1}')

    def test_unterminated_bare_fence_takes_content_to_end(self):
        self.assertEqual(_extract_json_text('```\n{"a": 1}'), '{"a": 1}')


class ParserEntryPointTest(TestCase):
    """Public parsers keep their signatures and return shapes."""

    def test_detection_response_with_unterminated_fence_parses(self):
        payload = (
            '{"detections": [{"plate": {"confidence": 0.9, "coordinates": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}}]}'
        )
        result = parse_detection_response("```json\n" + payload)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["detections"]), 1)

    def test_detection_response_returns_none_on_invalid_json(self):
        self.assertIsNone(parse_detection_response("not json at all"))

    def test_ocr_response_scales_and_offsets_coordinates(self):
        payload = '{"text": "ABC123", "confidence": 0.9, "coordinates": {"x1": 0, "y1": 0, "x2": 1000, "y2": 500}}'
        result = parse_ocr_response(
            "```json\n" + payload + "\n```", crop_h=50, crop_w=100, crop_offset_x=10, crop_offset_y=20
        )
        self.assertEqual(result["text"], "ABC123")
        coords = result["coordinates"]
        self.assertEqual((coords["x1"], coords["y1"]), (10, 20))
        self.assertEqual((coords["x2"], coords["y2"]), (110, 45))
