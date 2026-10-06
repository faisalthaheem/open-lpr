"""Runtime artifact integrity, for the health path.

Download-time verification in `fetch_artifacts` proves the bytes arrived intact
at that moment. It says nothing about what happens afterwards: a volume that is
truncated by an unclean shutdown, a tampered mount, or a recycled volume can all
leave an artifact that is present and wrong.

That matters more than it sounds. The recogniser and its dictionary are a set --
decoding assumes `len(dict) + 2` output classes -- so pairing the wrong two
yields plausible-looking text rather than an error. A silent OCR failure is the
one failure mode an operator is least likely to notice.

Hashing ~37MB on every health request would be worse than the problem, so the
result is cached for a short interval: the fast path is a presence check, and
full verification runs only on a cache miss.
"""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

CACHE_KEY = "pipeline:artifact_integrity"

# Short enough that a corruption is noticed within a couple of minutes of
# health polls, long enough that a burst of health requests does not re-hash.
DEFAULT_TTL_SECONDS = 60


def configured_artifacts() -> list[str]:
    """Artifact filenames the running deployment is configured to load."""
    return [
        getattr(settings, "PIPELINE_DETECTOR_MODEL", "plate_yolox_tiny_640.onnx"),
        getattr(settings, "PIPELINE_OCR_MODEL", "plate_ocr_ppocrv5_mobile.onnx"),
        getattr(settings, "PIPELINE_OCR_DICT", "plate_ocr_dict.json"),
    ]


def model_dir() -> Path:
    return Path(getattr(settings, "PIPELINE_MODEL_DIR", "model/plate"))


def check_integrity(ttl: int | None = None, use_cache: bool = True) -> dict:
    """Report whether the deployed artifacts are present and correct.

    Returns a dict with ``ok``, and on failure ``missing`` and ``corrupt`` lists.
    When the manifest cannot be fetched, ``ok`` is True and ``unverified`` is
    set: integrity is then unknown, not known-bad, and reporting it as
    corruption would turn a DNS failure into a page.

    `use_cache` exists for tests and for the rare case where an operator has
    just replaced artifacts and wants an immediate answer.
    """
    if use_cache:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    # Imported here rather than at module scope: fetch_artifacts pulls in urllib
    # and is a container-bootstrap concern, not a web-request one.
    from .fetch_artifacts import _base_url, verify_artifacts

    base = _base_url(
        getattr(settings, "PIPELINE_MODEL_REPO", "faisalthaheem/open-lpr-models"),
        getattr(settings, "PIPELINE_MODEL_REVISION", "detector-2026.10.1"),
    )

    result = verify_artifacts(model_dir(), base, configured_artifacts())
    if not result["ok"]:
        log.error(
            "Artifact integrity check failed: missing=%s corrupt=%s",
            result.get("missing"),
            result.get("corrupt"),
        )

    cache.set(CACHE_KEY, result, timeout=ttl or DEFAULT_TTL_SECONDS)
    return result


def invalidate() -> None:
    """Drop the cached verdict so the next call re-verifies."""
    cache.delete(CACHE_KEY)
