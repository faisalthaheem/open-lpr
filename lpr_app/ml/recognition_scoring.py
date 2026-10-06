#!/usr/bin/env python3
"""Character error rate and exact-match scoring for plate reads.

`compare_backends.py` can report whether a plate was *read*, but not whether it
was read *correctly*, because the corpus carries no transcription labels. This
module is the scoring half of closing that gap, and it is deliberately usable
without the labels: every function here is pure and takes its inputs as
arguments, so the scoring can be developed and tested against synthetic cases
before a single string is transcribed.

Two decisions worth stating, because they change the numbers:

- **Only alphanumerics are compared.** The default charset profile
  (`alphanumeric`) emits only alphanumerics, so comparing raw strings would
  charge the local backend for every separator it is configured not to emit.
  A ground truth of `AB-12 CD` normalises to `AB12CD`. Characters outside
  `[A-Z0-9]` are stripped from *both* sides before scoring, which means this
  measures registration content and not separator convention.
- **Levenshtein distance over the normalised strings.** Not normalised by
  plate length into a ratio at the call site, so that a zero-length ground
  truth stays meaningful instead of dividing by zero.

The remaining case — a plate detected but read as nothing — is scored as a
full deletion. That is deliberate and it is the strictest choice available: an
empty read has an edit distance equal to the length of the truth, so it can
never look better than a partial read. Reporting it as a separate bucket as
well (`unread`) keeps it visible, because a corpus where every plate is
silently deleted and one where every plate is confidently misread call for
opposite fixes.

**Labels are transcribed by a human and are not in the repository.** The corpus
carries plate boxes only — verified at the source, where each `imgareas` entry
has an `lbltxt` field whose only value across the whole corpus is the class name
`plate`. `compare_backends.py --dump-label-template` produces a file to
transcribe, pre-filled with each backend's own read; those values are an aid to
transcription and must be overwritten rather than confirmed, since confirming
them would turn the resulting CER into a measurement of how well the model
agrees with itself.
"""

from __future__ import annotations

import json
from pathlib import Path

NORMALISED_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def normalise(text: str | None) -> str:
    """Strip to uppercase alphanumerics, dropping separators and whitespace.

    Both the ground truth and the prediction go through this, so a model that
    emits `0G260` for `QG260` scores one substitution rather than being
    penalised for the punctuation it never emits.
    """
    if not text:
        return ""
    return "".join(character for character in text.upper() if character in NORMALISED_CHARS)


def levenshtein(reference: str, hypothesis: str) -> int:
    """Edit distance between two normalised strings.

    Standard two-row dynamic programme. `previous` is the row for the prefix
    of `reference` already consumed; the full matrix is avoided because plates
    are short but the corpus is large and this runs per plate per backend.
    """
    if reference == hypothesis:
        return 0
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)

    previous = list(range(len(hypothesis) + 1))
    for row, reference_char in enumerate(reference, start=1):
        current = [row]
        for column, hypothesis_char in enumerate(hypothesis, start=1):
            current.append(
                min(
                    previous[column] + 1,  # deletion
                    current[column - 1] + 1,  # insertion
                    previous[column - 1] + (reference_char != hypothesis_char),  # substitution
                )
            )
        previous = current
    return previous[-1]


def score_read(reference: str | None, hypothesis: str | None) -> dict:
    """Score one read against its ground truth.

    Returns the raw distance alongside the CER contribution so a caller can
    aggregate either way. `unread` distinguishes "the backend found nothing"
    from "the backend read the wrong thing", which are different failures even
    though both contribute a large distance.
    """
    truth = normalise(reference)
    read = normalise(hypothesis)

    if not truth:
        # A blank ground truth would make CER undefined. Treat an empty truth
        # as a perfect match only for an empty read, so a spurious read on an
        # unlabelled plate still shows up as a false positive.
        return {
            "distance": 0 if not read else len(read),
            "cer": 0.0 if not read else None,
            "exact": not read,
            "unread": False,
            "blank_truth": True,
        }

    distance = levenshtein(truth, read)
    return {
        "distance": distance,
        "cer": distance / len(truth),
        "exact": distance == 0,
        "unread": not read,
        "blank_truth": False,
    }


class RecognitionScore:
    """Aggregates per-read scores into the numbers a decision needs.

    Aggregates three ways on purpose:

    - overall CER, because it is the headline
    - per-layout CER, because stacked and single-row plates are different tasks
      and a change can improve one while degrading the other
    - per-confidence-band CER, because the open question is whether confidence
      is informative. If accuracy rises with confidence then a threshold is a
      real lever; if it does not, then confidence is not and thresholding would
      only be discarding reads at random.

    `unread` plates count toward the denominator as a full-length deletion, so
    this is CER over all labelled plates that were matched by a detection, not
    CER over plates that happened to produce text. Reported alongside
    `cer_read` — the same ratio restricted to plates that produced text — so
    that a backend cannot improve its CER by reading fewer plates.
    """

    def __init__(self, bands: tuple[tuple[float, float], ...] = ((0.0, 0.5), (0.5, 0.8), (0.8, 1.01))) -> None:
        self.bands = bands
        self._distance = 0
        self._characters = 0
        self._exact = 0
        self._total = 0
        self._unread = 0
        self._by_layout: dict[str, dict[str, float]] = {}
        self._by_band: dict[str, dict[str, float]] = {}
        self.mismatches: list[dict] = []

    def _bucket(self, store: dict[str, dict[str, float]], key: str) -> dict[str, float]:
        return store.setdefault(key, {"distance": 0.0, "characters": 0.0, "exact": 0.0, "total": 0.0, "unread": 0.0})

    def observe(self, reference: str | None, hypothesis: str | None, confidence: float, layout: str, key: str) -> dict:
        scored = score_read(reference, hypothesis)
        if scored["blank_truth"]:
            return scored

        self._total += 1
        self._distance += scored["distance"]
        self._characters += len(normalise(reference))
        self._exact += int(scored["exact"])
        self._unread += int(scored["unread"])

        for store, bucket_key in (
            (self._by_layout, layout),
            (self._by_band, self._band_for(confidence)),
        ):
            bucket = self._bucket(store, bucket_key)
            bucket["distance"] += scored["distance"]
            bucket["characters"] += len(normalise(reference))
            bucket["exact"] += int(scored["exact"])
            bucket["total"] += 1
            bucket["unread"] += int(scored["unread"])

        if not scored["exact"] and len(self.mismatches) < 50:
            # Capped: this is for reading, not for a full dump, and an unbounded
            # list would be a memory cost proportional to the corpus.
            self.mismatches.append(
                {
                    "key": key,
                    "truth": normalise(reference),
                    "read": normalise(hypothesis),
                    "confidence": round(confidence, 3),
                    "layout": layout,
                }
            )
        return scored

    def _band_for(self, confidence: float) -> str:
        for low, high in self.bands:
            if low <= confidence < high:
                return f"{low:.1f}-{min(high, 1.0):.1f}"
        return f"{self.bands[-1][0]:.1f}+"

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    def _summarise(self, bucket: dict[str, float]) -> dict:
        return {
            "plates": int(bucket["total"]),
            "cer": self._ratio(bucket["distance"], bucket["characters"]),
            "exact_match": self._ratio(bucket["exact"], bucket["total"]),
            "unread": int(bucket["unread"]),
        }

    @property
    def labelled(self) -> int:
        return int(self._total)

    def report(self) -> dict:
        return {
            "labelled_plates": self._total,
            "cer": self._ratio(self._distance, self._characters),
            "exact_match": self._ratio(self._exact, self._total),
            "unread": int(self._unread),
            "by_layout": {layout: self._summarise(bucket) for layout, bucket in sorted(self._by_layout.items())},
            "by_confidence": {
                band: self._summarise(bucket)
                for band, bucket in sorted(self._by_band.items(), key=lambda item: item[0])
            },
            "mismatches": self.mismatches,
        }


def load_labels(path: str | Path) -> dict[str, str]:
    """Load a transcription label file.

    Format is a flat JSON object of plate key to registration text, e.g.::

        {"val2017/000123.jpg#0": "QG260", "val2017/000123.jpg#1": "IDH4497"}

    The key is the image's path relative to the dataset root, a `#`, and the
    zero-based index of the plate within that image's annotation list — which is
    exactly how `compare_backends.py` indexes plates, so no separate mapping
    step is needed. A list of `{key, text}` objects is also accepted, since that
    is easier to produce from a spreadsheet export.

    Entries whose text is empty are dropped. A blank is how a transcriber marks
    "this plate is genuinely unreadable", and scoring it would either divide by
    zero or silently count as a full-length deletion attributed to the backend,
    when it is an admission that the label does not exist.
    """
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, dict) and "labels" in raw:
        raw = raw["labels"]

    if isinstance(raw, list):
        pairs = [(str(entry["key"]), entry.get("text", "")) for entry in raw]
    else:
        pairs = [(str(key), value) for key, value in raw.items()]

    return {key: str(text) for key, text in pairs if str(text).strip()}


def label_template(entries: list[tuple[str, str]]) -> dict[str, str]:
    """Build an empty label file for a set of `(key, expected_text)` pairs.

    `expected_text` is whatever the backend read, carried over purely to make
    annotation easy — the transcriber should overwrite it rather than confirm
    it, because the whole point is to establish what the truth *is* rather than
    what the model says. Keys where the model read nothing get an empty string,
    which is the case most worth transcribing carefully.
    """
    return {key: expected_text for key, expected_text in entries}


def plate_key(image_file: str, index: int) -> str:
    """Key format shared by `compare_backends.py` and `load_labels`."""
    return f"{image_file}#{index}"
