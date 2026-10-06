"""Local ONNX plate text recognition.

Reads a rectified plate crop and returns the registration text with a confidence.

Two corpus properties shape this stage.

**Plates are not one shape, but geometry cannot tell the cases apart.** The
annotated corpus is bimodal: roughly 45% are stacked two-line (ratio well under
2.0) and a large minority are single-line US and EU plates between 2.6 and 3.4.
A stacked plate must not be recognised in one pass, or the rows concatenate into
an unreadable string.

That much is true, and `split_two_rows` implements it. But inspection of the
corpus shows the stacked case cannot be *identified* reliably here: genuinely
stacked plates such as `VA9/2229` and `L802 WGK` overlap in aspect ratio with
single-line plates carrying a caption, such as `QG.260` with `ISLAMABAD`
beneath it at ratio 1.88. Aspect ratio, ink-gap presence, and row-height balance
all fail to separate them. Splitting is therefore **off by default**, because
enabling it appends captions to results more often than it rescues stacked
plates. `split_stacked=True` enables it for regions where plates are known to be
uniformly stacked.

**The character set is not one set.** A single hardcoded alphabet is wrong as a
global truth: many US states omit I and O, and regions differ in which
characters and separators appear. Decoding is therefore restricted by a
selectable charset profile rather than trusting the model to avoid characters
the region never uses. The default profile is alphanumerics.

Recognition is deliberately *not* read from non-registration text. Plates in this
corpus carry a state name, district, slogan, or registration sticker, and
reading those is a separate detection problem inside the crop.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..runtime.onnx import run_session
from .base import Stage, StageError

logger = logging.getLogger(__name__)

# PP-OCR recognisers consume 48px-tall crops, width bucketed to a multiple of 8.
DEFAULT_INPUT_HEIGHT = 48
DEFAULT_INPUT_WIDTH_BUCKET = 8
DEFAULT_MAX_INPUT_WIDTH = 320

# Crops per inference. One plate is one crop unless it is stacked and splitting
# is enabled, so this bounds invocations per image rather than plates per image.
DEFAULT_OCR_BATCH_SIZE = 8

# Digits and Latin letters: the default profile, for a region whose plates are
# alphanumeric. Region-specific profiles narrow or widen this.
DEFAULT_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Characters commonly mistaken for one another on plates. A profile may exclude
# them, but that is a per-region decision, not a global truth, so the default
# profile keeps them all.
CONFUSABLE_CHARS = "O0IQB8S5Z2"

STACKED_LAYOUT = "stacked"
SINGLE_LINE_LAYOUT = "single_line"


@dataclass
class CharsetProfile:
    """The characters a region actually uses on its plates.

    ``name`` is for configuration and metrics. ``characters`` is the permitted
    set. ``strip_separators`` controls whether spacing and punctuation found in
    the raw decode is removed, which is usually desirable since plates use
    separators inconsistently.
    """

    name: str
    characters: str = DEFAULT_CHARSET
    strip_separators: bool = True

    def allowed(self) -> set[str]:
        return set(self.characters)

    def sanitise(self, text: str) -> str:
        """Drop anything outside the profile and, by default, separators."""
        allowed = self.allowed()
        kept = [c for c in text if c in allowed]
        if not self.strip_separators:
            kept = [c for c in text if c in allowed or not c.isspace()]
        return "".join(kept)


DEFAULT_PROFILES = {
    "alphanumeric": CharsetProfile("alphanumeric", DEFAULT_CHARSET),
    # A profile for regions whose plates never use I or O, as many US states do.
    "no_io": CharsetProfile("no_io", "".join(c for c in DEFAULT_CHARSET if c not in "IO"), strip_separators=True),
}


@dataclass
class RecognitionResult:
    """Recognised text for one plate."""

    text: str
    confidence: float
    raw_text: str = ""
    rows: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "confidence": round(float(self.confidence), 4)}


def load_charset(dict_path: str | Path | None) -> list[str]:
    """Load the recogniser's character dictionary.

    PaddleOCR-style CTC recognisers emit log-softmax over the dictionary plus a
    blank index, so the full label list is ``[""] + dictionary``.
    """
    if not dict_path:
        return []
    path = Path(dict_path)
    if not path.is_file():
        raise StageError(f"character dictionary not found at {path}")
    characters = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(characters, list):
        raise StageError(f"character dictionary at {path} is not a list")

    # Label layout is ["blank"] + dictionary + ["space"], where the trailing
    # space class lets CTC emit a gap. Verified against the model's output
    # width, which is exactly len(dictionary) + 2. Omitting it makes the highest
    # index look out of range on every decode.
    return [""] + list(characters) + [" "]


def preprocess_crop(
    image: Image.Image,
    *,
    input_height: int = DEFAULT_INPUT_HEIGHT,
    bucket: int = DEFAULT_INPUT_WIDTH_BUCKET,
    max_width: int = DEFAULT_MAX_INPUT_WIDTH,
) -> np.ndarray:
    """Resize a crop to the recogniser's input: height 48, width a multiple of 8.

    Aspect ratio is preserved, since stretching distorts glyph proportions and
    costs accuracy.
    """
    width, height = image.size
    if width <= 0 or height <= 0:
        raise StageError(f"cannot preprocess a {width}x{height} crop")

    scaled_width = int(round(width * input_height / height))
    scaled_width = max(bucket, (scaled_width // bucket) * bucket)
    scaled_width = min(scaled_width, max_width)

    resized = image.resize((scaled_width, input_height), Image.BILINEAR)
    array = np.asarray(resized, dtype=np.float32).transpose(2, 0, 1)[np.newaxis, ...]
    # The recogniser was trained on inputs normalised with this mean and scale.
    array = array / 255.0
    array = (array - 0.5) / 0.5
    return np.ascontiguousarray(array)


def preprocess_batch(
    images: list[Image.Image],
    *,
    input_height: int = DEFAULT_INPUT_HEIGHT,
    bucket: int = DEFAULT_INPUT_WIDTH_BUCKET,
    max_width: int = DEFAULT_MAX_INPUT_WIDTH,
) -> tuple[np.ndarray, list[int]]:
    """Preprocess several crops into one padded NCHW batch.

    Width is a dynamic axis in the recogniser's signature, but every row in a
    single inference must share one width. Rows are therefore padded to the
    widest member of the batch, so a batch costs the width of its widest crop
    rather than the sum of its crops.

    Two details keep the padding from corrupting the decode:

    - The pad value is the *normalised* value of a black pixel, not zero. The
      normalisation maps black to -1.0 and mid-grey to 0.0, so zero-filling would
      paint the padded region mid-grey, which is where plate ink sits.
    - The per-row widths are returned alongside the tensor so the caller can trim
      the timesteps belonging to padding. PP-OCR emits one timestep per 8px of
      input width, so the valid timestep count is the row's own width over the
      bucket. Without trimming, padding is decoded as extra characters.
    """
    if not images:
        raise StageError("cannot preprocess an empty batch")

    tensors = [
        preprocess_crop(image, input_height=input_height, bucket=bucket, max_width=max_width) for image in images
    ]
    widths = [tensor.shape[3] for tensor in tensors]
    width = max(widths)

    # preprocess_crop normalises with (x/255 - 0.5)/0.5, so black is exactly -1.
    black = -1.0
    # preprocess_crop returns a single-row NCHW tensor, so drop its batch axis and
    # rebuild it with the padded width.
    padded = np.full((len(tensors), *tensors[0].shape[1:3], width), black, dtype=np.float32)
    for index, tensor in enumerate(tensors):
        padded[index, :, :, : tensor.shape[3]] = tensor
    return np.ascontiguousarray(padded), widths


def _as_probabilities(raw: np.ndarray) -> np.ndarray:
    """Return a 2D probability array, applying softmax only if needed.

    A recogniser export may emit either logits or already-normalised
    probabilities. Softmaxing probabilities again is not harmless: it pushes
    every value toward uniform and silently destroys the confidence signal. So
    the normalised case is detected and left alone.
    """
    if raw.ndim == 3:
        raw = raw[0]
    if raw.ndim != 2:
        raise StageError(f"expected a 2D output, got shape {raw.shape}")

    total = raw.sum(axis=-1, keepdims=True)
    looks_normalised = np.all(raw >= -1e-5) and np.all(raw <= 1.0 + 1e-5) and np.allclose(total, 1.0, atol=1e-3)
    if looks_normalised:
        return raw

    shifted = raw - raw.max(axis=-1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / exponentials.sum(axis=-1, keepdims=True)


def ctc_greedy_decode(probabilities: np.ndarray, charset: list[str]) -> tuple[str, list[float]]:
    """Greedy CTC decode.

    Returns the text plus the per-character confidence, taken as the mean
    probability over the timesteps that emitted a character. A blank between two
    identical adjacent characters is what separates them, so runs of the same
    index collapse to one emission.
    """
    if probabilities.ndim != 2:
        raise StageError(f"expected a 2D probability array, got shape {probabilities.shape}")

    indices = probabilities.argmax(axis=1)
    confidences = probabilities.max(axis=1)

    text: list[str] = []
    emitted_confidence: list[float] = []
    previous = -1
    for step, index in enumerate(indices):
        index = int(index)
        if index != previous and index != 0:
            if index < len(charset):
                text.append(charset[index])
                emitted_confidence.append(float(confidences[step]))
            else:
                # An index beyond the dictionary means model and dictionary
                # disagree, which must be visible rather than silently dropped.
                logger.warning(
                    "recogniser emitted index %d but the dictionary has %d entries",
                    index,
                    len(charset),
                )
        previous = index

    # Confidence is the mean over the steps that emitted a character; an all-blank
    # decode has no emitted steps and therefore no confidence.
    return "".join(text), emitted_confidence


def split_two_rows(
    image: Image.Image, *, min_gap: float = 0.45, max_imbalance: float = 0.55
) -> list[Image.Image] | None:
    """Split a crop horizontally on the weakest row of its ink profile.

    Returns None when no credible gap exists, so the caller recognises the crop as
    one line rather than inventing characters from arbitrary slices.

    **What this cannot do.** On this corpus it cannot reliably tell a genuinely
    stacked plate from a single-line plate carrying a caption. Inspected samples
    include ``VA9/2229`` and ``L802 WGK`` (truly stacked) alongside ``QG.260``
    with an ``ISLAMABAD`` caption beneath it (one line, ratio 1.88). The two
    cases overlap on every geometric signal available here:

    - plate aspect ratio -- stacked and captioned plates interleave from 1.4 to 2.4
    - presence of an ink gap -- both have one
    - row height ratio -- both produce an imbalanced split

    So splitting is opt-in via ``split_stacked`` and defaults off. Turning it on
    reads the caption as a second line and appends it to the result. Resolving
    this properly needs a layout classifier trained on captioned examples, which
    the corpus does not provide; see the open items in DETECTOR.md.
    """
    grey = np.asarray(image.convert("L"), dtype=np.float32)
    height = grey.shape[0]
    if height < 12:
        return None

    # Rows are dark and the background light, so ink is darkness relative to the
    # brightest pixel.
    ink = (grey.max() - grey).mean(axis=1)
    peak = float(ink.max())
    if peak <= 1e-6:
        return None
    ink = ink / peak

    # Search only the middle: a plate border or edge shadow would otherwise be
    # the strongest minimum in the profile.
    margin = max(2, height // 5)
    window = ink[margin : height - margin]
    if window.size < 6:
        return None

    cut = int(np.argmin(window)) + margin
    if ink[cut] > min_gap:
        return None

    top, bottom = cut, height - cut
    if top < 6 or bottom < 6:
        return None

    # A caption is small next to the registration; two registration rows are
    # closer in height. Rejecting the extreme imbalance avoids reading a caption.
    imbalance = abs(top - bottom) / max(top, bottom)
    if imbalance > max_imbalance:
        return None

    return [image.crop((0, 0, image.width, cut)), image.crop((0, cut, image.width, height))]


class PlateOCRStage(Stage):
    """Recognise plate text from a rectified crop."""

    name = "read_plate"
    inputs = ("plate_crop",)
    outputs = ("ocr",)

    ONNX_OUTPUTS = ("fetch_name_0",)

    def __init__(
        self,
        context=None,
        *,
        model_path: str | None = None,
        dict_path: str | None = None,
        input_height: int = DEFAULT_INPUT_HEIGHT,
        max_input_width: int = DEFAULT_MAX_INPUT_WIDTH,
        split_stacked: bool = False,
        stacked_threshold: float = 2.0,
        min_confidence: float = 0.0,
        batch_size: int = DEFAULT_OCR_BATCH_SIZE,
    ) -> None:
        super().__init__(context)
        self.model_path = model_path
        self.dict_path = dict_path
        self.input_height = input_height
        self.max_input_width = max_input_width
        self.split_stacked = split_stacked
        self.stacked_threshold = stacked_threshold
        self.min_confidence = float(min_confidence)
        # Crops per inference. Bounded because the recogniser's width is the
        # widest crop in the batch, so a batch of N plates costs the width of its
        # widest member rather than N inferences.
        self.batch_size = max(1, int(batch_size))
        self.charset: list[str] = []
        self.profiles = dict(DEFAULT_PROFILES)
        self._loaded_dict = False

    def use_profile(self, name: str) -> CharsetProfile:
        """Select the charset profile, which must exist in configuration."""
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise StageError(f"unknown charset profile {name!r}; configured: {sorted(self.profiles)}") from exc

    def run(self, data: dict[str, Any]) -> dict[str, Any]:
        """Read one crop. This is the graph-facing single-plate entry point."""
        crop = data.get("plate_crop")
        if crop is None:
            raise StageError("read_plate received no plate crop")

        profile = self._profile_for(data)
        layout = data.get("layout") or SINGLE_LINE_LAYOUT
        return {"ocr": self.read_plates([(crop, layout)], profile=profile)[0]}

    def read_plates(
        self,
        plates: list[tuple[Image.Image, str | None]],
        *,
        profile: CharsetProfile | None = None,
    ) -> list[RecognitionResult]:
        """Read a list of plates, one result per plate, in order.

        This is the entry point the service layer uses, because it is the only
        one that can honour the batch bound: cropping happens here so every row
        of every plate is known up front, and the rows are then packed into
        inferences of at most ``batch_size`` crops.

        Two properties the spec depends on and that are easy to lose:

        - **One recognition per plate.** Each plate appears in exactly one batch
          and contributes exactly one result, at its own index. The two rows of a
          stacked plate are two crops of that one plate, so they count once.
        - **Bounded invocations.** ``batch_size`` crops per inference, so an image
          with more plates than the bound produces several inferences, none
          oversized.

        Row order is preserved when combining a stacked plate's rows.
        """
        if not plates:
            return []

        chosen = profile or self.profiles["alphanumeric"]

        # Flatten plates into rows, remembering which plate each row belongs to.
        rows: list[Image.Image] = []
        owners: list[int] = []
        for index, (crop, layout) in enumerate(plates):
            for row in self._rows_for(crop, layout or SINGLE_LINE_LAYOUT):
                rows.append(row)
                owners.append(index)

        decoded: list[tuple[str, float]] = [("", 0.0)] * len(rows)
        for start in range(0, len(rows), self.batch_size):
            chunk = rows[start : start + self.batch_size]
            for offset, (text, confidence) in enumerate(self._decode_chunk(chunk)):
                decoded[start + offset] = (text, confidence)

        results: list[RecognitionResult] = []
        for index in range(len(plates)):
            texts: list[str] = []
            confidences: list[float] = []
            for row_index, owner in enumerate(owners):
                if owner != index:
                    continue
                text, confidence = decoded[row_index]
                texts.append(text)
                confidences.append(confidence)

            combined_raw = "".join(texts)
            cleaned = chosen.sanitise(combined_raw)
            confidence = float(np.mean(confidences)) if confidences else 0.0

            if cleaned and confidence < self.min_confidence:
                # Reported rather than dropped: the caller decides, and a
                # low-confidence read is still information.
                logger.info("recognition confidence %.2f below threshold %.2f", confidence, self.min_confidence)

            results.append(
                RecognitionResult(
                    text=cleaned,
                    confidence=confidence,
                    raw_text=combined_raw,
                    rows=texts,
                )
            )
        return results

    def _profile_for(self, data: dict[str, Any]) -> CharsetProfile:
        profile_name = data.get("charset_profile") or self.context.config.get("charset_profile")
        return self.use_profile(profile_name) if profile_name else self.profiles["alphanumeric"]

    def _rows_for(self, crop: Image.Image, layout: str) -> list[Image.Image]:
        """One crop, or two when the plate is stacked."""
        if layout == STACKED_LAYOUT and self.split_stacked:
            rows = split_two_rows(crop)
            if rows is not None:
                return rows
            # Fall through: a stacked plate whose rows do not separate is still
            # recognised as one line rather than producing nothing.
            logger.info("stacked plate did not separate into two rows; recognising as one line")
        return [crop]

    def _decode_chunk(self, chunk: list[Image.Image]) -> list[tuple[str, float]]:
        """Run one inference over up to ``batch_size`` crops."""
        if not self.charset:
            self._ensure_charset()
        if self._session is None:
            self.load()

        tensor, widths = preprocess_batch(chunk, input_height=self.input_height, max_width=self.max_input_width)
        feed = {self._session.input_names[0]: tensor}
        outputs = run_session(self._session, feed, self.ONNX_OUTPUTS, stage_name=self.name)
        raw = np.asarray(next(iter(outputs.values())))
        if raw.ndim == 2:
            raw = raw[np.newaxis, ...]

        results: list[tuple[str, float]] = []
        for row_index, width in enumerate(widths):
            if row_index >= raw.shape[0]:
                break
            probabilities = raw[row_index]
            # Trim the timesteps that belong to padding. PP-OCR emits one
            # timestep per 8px of input width, so a row's own width determines
            # how much of the shared output width is real.
            valid_steps = max(1, width // DEFAULT_INPUT_WIDTH_BUCKET)
            probabilities = probabilities[:valid_steps]

            # The CTC head already emits normalised probabilities, which the ONNX
            # graph contains as Softmax. Softmaxing again squashes every value
            # toward uniform and drives confidence to zero, so detect the
            # normalised case instead of assuming logits.
            text, per_char = ctc_greedy_decode(_as_probabilities(probabilities), self.charset)
            results.append((text, float(np.mean(per_char)) if per_char else 0.0))
        return results

    def _ensure_charset(self) -> None:
        if self._loaded_dict:
            return
        self.charset = load_charset(self.dict_path)
        self._loaded_dict = True
        if not self.charset:
            raise StageError("no character dictionary configured; recognised text would be meaningless")
