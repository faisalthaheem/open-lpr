"""Artifact fetching for deployments that start with an empty model directory.

The entrypoint downloads the ONNX artifacts on first boot so a fresh deployment
is functional without an operator running a download step first. These tests
cover that script directly rather than through the container, because the
properties that matter are all about failure handling: a download that appears
to succeed but leaves a truncated file is worse than one that visibly failed.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from lpr_app.pipeline import fetch_artifacts

DETECTOR = "plate_yolox_tiny_640.onnx"
RECOGNISER = "plate_ocr_ppocrv5_mobile.onnx"
DICTIONARY = "plate_ocr_dict.json"


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


class FakeFetcher:
    """Stands in for the network, serving bytes from a dict keyed by URL suffix."""

    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.requested: list[str] = []
        self.fail_on: set[str] = set()

    def __call__(self, url: str, dest: Path, timeout: float) -> None:
        """Mimics _download by writing to dest, not by returning a response.

        Patching _download wholesale means these tests exercise ensure_artifacts'
        own verify/rename/cleanup logic rather than reimplementing it.
        """
        self.requested.append(url)
        if any(token in url for token in self.fail_on):
            raise OSError("simulated network failure")
        for suffix, data in self.files.items():
            if url.endswith(suffix):
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                Path(dest).write_bytes(data)
                return
        raise AssertionError(f"unexpected URL requested: {url}")


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self, n: int) -> bytes:
        chunk, self._data = self._data[:n], self._data[n:]
        return chunk

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class ManifestTests(unittest.TestCase):
    def test_manifest_declares_no_checksum_is_an_error(self):
        """A manifest missing a checksum must not be read as 'anything goes'.

        Silently skipping verification would let a malformed manifest turn the
        checksum guarantee off without anyone noticing.
        """
        base = "https://example.test/resolve/rev"
        incomplete = json.dumps({"artifacts": {DETECTOR: {"sha256": "a" * 64}}})

        with patch.object(
            fetch_artifacts, "_download", lambda url, dest, t: Path(dest).write_bytes(incomplete.encode())
        ):
            with self.assertRaisesRegex(RuntimeError, "no sha256"):
                fetch_artifacts.fetch_manifest(base, 1.0)

    def test_url_is_pinned_to_the_requested_revision(self):
        self.assertIn("/resolve/detector-2026.10.1", fetch_artifacts._base_url("owner/repo", "detector-2026.10.1"))

    def test_default_revision_is_a_tag_not_a_branch(self):
        """A moving branch would silently change weights under a pinned deploy."""
        self.assertNotEqual(fetch_artifacts.DEFAULT_REVISION, "main")
        self.assertIn(".", fetch_artifacts.DEFAULT_REVISION)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.contents = {DETECTOR: b"detector-bytes", RECOGNISER: b"ocr-bytes", DICTIONARY: b"{}"}
        self.manifest = json.dumps(
            {"artifacts": {name: {"sha256": _digest(data)} for name, data in self.contents.items()}}
        ).encode()
        self.fetcher = FakeFetcher({**self.contents, "manifest.json": self.manifest})
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.model_dir = Path(self.tmp.name) / "plate"

    def _run(self, names=None, force=False):
        patcher = patch.object(fetch_artifacts, "_download", self.fetcher)
        with patcher:
            return fetch_artifacts.ensure_artifacts(
                self.model_dir,
                "https://example.test/resolve/rev",
                names or list(fetch_artifacts.ARTIFACTS),
                force=force,
            )

    def test_downloads_all_three_and_verifies(self):
        downloaded = self._run()

        self.assertEqual(downloaded, 3)
        for name, data in self.contents.items():
            self.assertEqual((self.model_dir / name).read_bytes(), data)

    def test_present_artifacts_are_not_re_fetched(self):
        self._run()
        self.fetcher.requested.clear()

        downloaded = self._run()

        self.assertEqual(downloaded, 0)
        self.assertEqual(self.fetcher.requested, [])

    def test_corrupt_existing_file_is_replaced(self):
        """A wrong-checksum file on disk is replaced, not trusted.

        This is the case where a persistent volume has been tampered with or
        corrupted by an interrupted earlier write.
        """
        self.model_dir.mkdir(parents=True, exist_ok=True)
        (self.model_dir / DETECTOR).write_bytes(b"truncated garbage")

        downloaded = self._run()

        # Three, not one: the other two were absent and had to be fetched too.
        # The point of the assertion is that the corrupt detector was replaced,
        # not preserved because a file happened to exist.
        self.assertEqual(downloaded, 3)
        self.assertEqual((self.model_dir / DETECTOR).read_bytes(), self.contents[DETECTOR])

    def test_mismatched_download_is_deleted(self):
        """A file that fails verification must not survive as if it were good.

        Leaving it in place means the next startup's existence check passes and
        inference fails later on a corrupt artifact.
        """
        corrupt = {**self.contents, DETECTOR: b"not what was published"}
        fetcher = FakeFetcher({**corrupt, "manifest.json": self.manifest})
        with patch.object(fetch_artifacts, "_download", fetcher):
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                fetch_artifacts.ensure_artifacts(
                    self.model_dir,
                    "https://example.test/resolve/rev",
                    [DETECTOR],
                )

        self.assertFalse((self.model_dir / DETECTOR).exists())

    def test_partial_download_leaves_no_named_artifact(self):
        """A stream interrupted mid-transfer must not produce a plausible file.

        The temp-and-rename in _download is what guarantees this; without it a
        killed container leaves a short .onnx that passes the existence check.
        """

        def _truncate(url, dest, timeout):
            """Write half the bytes, then die, as an interrupted transfer would."""
            suffix = next(s for s in {**self.contents, "manifest.json": self.manifest} if url.endswith(s))
            data = self.manifest if suffix == "manifest.json" else self.contents[suffix]
            Path(dest).write_bytes(data[:2])
            raise OSError("connection reset")

        with patch.object(fetch_artifacts, "_download", _truncate):
            with self.assertRaises(OSError):
                fetch_artifacts.ensure_artifacts(self.model_dir, "https://example.test/resolve/rev", [DETECTOR])

        self.assertFalse((self.model_dir / DETECTOR).exists())
        self.assertEqual(list(self.model_dir.glob("*.part")), [])

    def test_real_download_of_interrupted_response_cleans_up_temp_file(self):
        """Exercises the real temp-and-rename path, not a patched _download.

        The other interruption test replaces _download wholesale, so it never
        touches the temp-file handling that actually provides this guarantee.
        """
        target = self.model_dir / DETECTOR
        with patch.object(fetch_artifacts.urllib.request, "urlopen", side_effect=OSError("reset")):
            with self.assertRaises(OSError):
                fetch_artifacts._download("https://example.test/x", target, 1.0)

        self.assertFalse(target.exists())
        self.assertEqual(list(self.model_dir.iterdir()), [])

    def test_network_failure_propagates_rather_than_yielding_success(self):
        self.fetcher.fail_on = {DETECTOR}
        with self.assertRaises(OSError):
            self._run([DETECTOR])

    def test_directory_is_created_with_traversable_permissions(self):
        """The entrypoint drops privileges to django after fetching.

        Root-owned 0700 would make the artifacts unreadable at inference time,
        producing a permission error on a successful download.
        """
        self._run()

        self.assertTrue((self.model_dir.stat().st_mode & 0o755) == 0o755)


class CliTests(unittest.TestCase):
    def test_unknown_artifact_is_rejected(self):
        """An unrecognized filename has no known repository path.

        Refusing is right: guessing a path would produce a confusing 404 at
        deploy time rather than a clear error here.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                fetch_artifacts.main(["--model-dir", tmp, "--artifacts", "not_a_real_model.onnx"])

    def test_non_boolean_download_flag_is_read_as_false(self):
        self.assertFalse(fetch_artifacts._env_bool("X", False) is True)
        with patch.dict("os.environ", {"X": "maybe"}):
            self.assertFalse(fetch_artifacts._env_bool("X", True))
        with patch.dict("os.environ", {"X": "yes"}):
            self.assertTrue(fetch_artifacts._env_bool("X", False))
