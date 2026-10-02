"""Uniform interface implemented by every pipeline stage.

A stage declares the fields it consumes and the fields it produces. The graph
runner routes data between stages purely from those declarations, so adding a
stage or swapping its model artifact requires no change to the runner.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Execution providers a stage may be placed on. Kept as plain strings so a
# provider that this onnxruntime build does not ship is still expressible in
# configuration and falls back rather than failing to load.
CPU_PROVIDER = "cpu"
CUDA_PROVIDER = "cuda"
ROCM_PROVIDER = "rocm"

KNOWN_PROVIDERS = (CPU_PROVIDER, CUDA_PROVIDER, ROCM_PROVIDER)


class StageError(Exception):
    """A stage could not be constructed, loaded, or executed."""


@dataclass
class StageContext:
    """Everything a stage needs from the graph runner besides its inputs.

    ``provider`` is the execution provider this stage was assigned.
    ``config`` carries stage-specific settings from the pipeline config.
    ``budgets`` maps a stage or pipeline name to a latency budget in seconds,
    so stages can report against the same numbers the runner records.
    """

    provider: str = CPU_PROVIDER
    config: dict[str, Any] = field(default_factory=dict)
    budgets: dict[str, float] = field(default_factory=dict)


class Stage(ABC):
    """Base class for a pipeline stage.

    Subclasses declare ``name``, ``inputs``, and ``outputs``. ``model_path`` is
    optional: stages that perform no model inference (the rectification stage,
    for example) leave it unset and never load an artifact.
    """

    #: Stable identifier used in configuration, metrics, and error messages.
    name: str = ""

    #: Field names this stage reads from the bound input data.
    inputs: tuple[str, ...] = ()

    #: Field names this stage writes to the bound output data.
    outputs: tuple[str, ...] = ()

    #: Path to the ONNX artifact, or None for a stage with no model.
    model_path: str | None = None

    def __init__(self, context: StageContext | None = None) -> None:
        if not self.name:
            raise StageError(f"{type(self).__name__} must declare a non-empty name")
        if not self.outputs:
            raise StageError(f"stage {self.name!r} must declare at least one output field")
        self.context = context or StageContext()
        self._session = None

    # -- artifact lifecycle ------------------------------------------------

    @property
    def has_model(self) -> bool:
        """Whether this stage loads a model artifact."""
        return self.model_path is not None

    @property
    def loaded(self) -> bool:
        """Whether the model artifact is currently loaded."""
        return self._session is not None

    def load(self) -> None:
        """Load the model artifact if it is not already loaded.

        Loading is lazy and happens at most once per stage instance: a skipped
        stage must not load anything, and a stage executed repeatedly reuses the
        session it already built.
        """
        if not self.has_model:
            return
        if self._session is not None:
            return
        from ..runtime.onnx import load_session

        self._session = load_session(self.model_path, self.context.provider, stage_name=self.name)

    def reset(self) -> None:
        """Drop the loaded artifact. Used by tests to isolate sessions."""
        self._session = None

    # -- execution ---------------------------------------------------------

    @abstractmethod
    def run(self, data: dict[str, Any]) -> dict[str, Any]:
        """Execute the stage and return a mapping of declared output fields."""

    def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        """Load if needed, then run. Returns this stage's output fields only."""
        self.load()
        return self.run(data)

    # -- timing ------------------------------------------------------------

    def execute_timed(self, data: dict[str, Any]) -> tuple[dict[str, Any], float]:
        """Run the stage and return its outputs plus elapsed seconds."""
        started = time.perf_counter()
        outputs = self.execute(data)
        return outputs, time.perf_counter() - started

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        model = self.model_path or "no-model"
        return f"<{type(self).__name__} name={self.name!r} model={model} provider={self.context.provider}>"
