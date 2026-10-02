"""ONNX Runtime session construction and invocation.

One runtime serves CPU, CUDA, and ROCm from the same artifact: the target is
chosen by passing an execution provider at session construction, never by
changing the model or branching in code. A requested provider that this
onnxruntime build does not ship is reported and replaced with the CPU provider
rather than raising, so a misconfigured stage cannot take down image
processing.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import onnxruntime as ort

from ..stages.base import CPU_PROVIDER, StageError

logger = logging.getLogger(__name__)

# Maps our provider names onto onnxruntime's provider class names.
_PROVIDER_CLASSES = {
    CPU_PROVIDER: "CPUExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "rocm": "ROCMExecutionProvider",
}


@dataclass
class LoadedSession:
    """An inference session plus the signature checks made against it."""

    session: ort.InferenceSession
    provider: str
    requested_provider: str
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]
    input_shapes: tuple[tuple[str, tuple[int | str | None, ...]], ...]


def resolve_provider(requested: str | None) -> tuple[str, str | None]:
    """Return ``(provider, provider_class)`` for a requested provider name.

    Falls back to the CPU provider when the requested one is unavailable,
    logging the substitution. An unrecognised name is treated the same way so
    that a typo degrades to working behaviour rather than an outage.
    """
    available = ort.get_available_providers()
    requested = (requested or CPU_PROVIDER).strip().lower()

    provider_class = _PROVIDER_CLASSES.get(requested)
    if provider_class is None:
        logger.warning(
            "Unknown execution provider %r; falling back to %s. Known providers: %s",
            requested,
            CPU_PROVIDER,
            sorted(_PROVIDER_CLASSES),
        )
        return CPU_PROVIDER, _PROVIDER_CLASSES[CPU_PROVIDER]

    if provider_class in available:
        return requested, provider_class

    logger.warning(
        "Execution provider %r is not available in this onnxruntime build (available: %s); " "falling back to %s.",
        requested,
        available,
        CPU_PROVIDER,
    )
    return CPU_PROVIDER, _PROVIDER_CLASSES[CPU_PROVIDER]


def load_session(model_path: str | None, provider: str = CPU_PROVIDER, *, stage_name: str = "") -> LoadedSession:
    """Load an ONNX artifact, or raise ``StageError`` naming the path.

    A missing or unloadable artifact is always an error. Nothing is substituted
    silently: a stage without a usable model is a configuration error, not
    something to paper over with a different artifact.
    """
    label = f"stage {stage_name!r}" if stage_name else "stage"
    if not model_path:
        raise StageError(f"{label} has no model path configured")

    if not os.path.isfile(model_path):
        raise StageError(f"{label} model artifact not found at resolved path: {model_path}")

    resolved, provider_class = resolve_provider(provider)

    options = ort.SessionOptions()
    # Keep per-execution timings out of the default log level; the pipeline
    # records its own durations through the metrics surface.
    options.log_severity_level = 3

    try:
        session = ort.InferenceSession(
            model_path,
            sess_options=options,
            providers=[provider_class],
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a stage error
        raise StageError(f"{label} failed to load model artifact {model_path}: {exc}") from exc

    actual_providers = session.get_providers()
    if provider_class not in actual_providers and CPU_PROVIDER not in actual_providers:
        raise StageError(f"{label} loaded {model_path} but no usable execution provider is active")

    inputs = session.get_inputs()
    outputs = session.get_outputs()

    return LoadedSession(
        session=session,
        provider=resolved,
        requested_provider=provider,
        input_names=tuple(i.name for i in inputs),
        output_names=tuple(o.name for o in outputs),
        input_shapes=tuple((i.name, tuple(i.shape)) for i in inputs),
    )


def validate_input_shape(loaded: LoadedSession, feed: dict[str, np.ndarray], *, stage_name: str = "") -> None:
    """Check a feed dict against the artifact's declared input signature.

    Rank and, where the artifact pins it, channel count are checked because a
    mismatch there produces a confusing downstream failure rather than a clear
    one at the point of the mistake.
    """
    label = f"stage {stage_name!r}" if stage_name else "stage"

    for name, expected in loaded.input_shapes:
        if name not in feed:
            raise StageError(f"{label} expects input {name!r} but it was not supplied")

        actual_rank = feed[name].ndim
        expected_rank = len(expected)
        if expected_rank and actual_rank != expected_rank:
            raise StageError(
                f"{label} input {name!r} expected rank {expected_rank} but got rank {actual_rank} "
                f"(shape {tuple(feed[name].shape)}); declared shape {expected}"
            )

        for axis, (want, got) in enumerate(zip(expected, feed[name].shape, strict=False)):
            if isinstance(want, int) and want > 0 and want != got:
                raise StageError(
                    f"{label} input {name!r} expected shape {expected} but got {tuple(feed[name].shape)} "
                    f"(axis {axis} expected {want}, got {got})"
                )


def validate_output_names(loaded: LoadedSession, expected: tuple[str, ...], *, stage_name: str = "") -> None:
    """Check that the artifact produces the output names the stage reads.

    Reading a tensor of unintended meaning because a name changed is silent
    corruption, so a mismatch is an error rather than a warning.
    """
    label = f"stage {stage_name!r}" if stage_name else "stage"
    missing = [name for name in expected if name not in loaded.output_names]
    if missing:
        raise StageError(
            f"{label} expects output(s) {missing} but the artifact only produces " f"{list(loaded.output_names)}"
        )


def run_session(
    loaded: LoadedSession,
    feed: dict[str, np.ndarray],
    output_names: tuple[str, ...],
    *,
    stage_name: str = "",
) -> dict[str, Any]:
    """Validate a feed against the signature and run one inference."""
    validate_input_shape(loaded, feed, stage_name=stage_name)
    validate_output_names(loaded, output_names, stage_name=stage_name)
    try:
        results = loaded.session.run(list(output_names), feed)
    except Exception as exc:  # noqa: BLE001 - surfaced as a stage error
        raise StageError(f"stage {stage_name!r} inference failed: {exc}") from exc
    return dict(zip(output_names, results, strict=True))
