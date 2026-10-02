"""Configuration-declared directed graph of pipeline stages.

The graph is a set of nodes, each naming a stage class and its model artifact,
plus edges that bind a node's input fields to output fields produced by
upstream nodes. Execution is dependency-ordered; independent nodes may run
concurrently.

Data routing is driven entirely by the stage declarations, so a new stage is a
config entry plus a class, not a change to this module.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .stages.base import CPU_PROVIDER, Stage, StageContext

logger = logging.getLogger(__name__)

# Why a stage did not run. Kept distinct from failures so a downstream skip
# caused by an upstream failure stays attributable to the originating stage.
SKIP_MISSING_INPUT = "missing-input"
SKIP_CONDITION = "condition-not-met"
SKIP_UPSTREAM_FAILED = "upstream-failed"

STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"


class GraphError(Exception):
    """The graph declaration is invalid."""


def _has_content(value: Any) -> bool:
    """Whether an upstream field carries something a stage can consume.

    ``0`` and ``False`` are content; ``None`` and empty containers are not. A
    zero-valued confidence is a real reading, while an empty detections list
    means the detector found nothing.
    """
    if value is None:
        return False
    if isinstance(value, bool | int | float):
        return True
    if isinstance(value, str | bytes | list | tuple | set | dict):
        return len(value) > 0
    return True


@dataclass
class Node:
    """One stage instance within the graph."""

    stage: Stage
    #: Maps an input field name to the output field name it is bound to.
    bindings: dict[str, str] = field(default_factory=dict)
    #: Optional predicate over this node's bound inputs; false skips the node.
    condition: Callable[[dict[str, Any]], bool] | None = None
    #: Description of what ``condition`` enforces, recorded on a skip.
    condition_description: str = ""

    @property
    def name(self) -> str:
        return self.stage.name

    @property
    def bound_fields(self) -> set[str]:
        """Output field names this node binds."""
        return set(self.bindings.values())


@dataclass
class StageOutcome:
    """Result of running one node, including when and why it did not run."""

    name: str
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    reason: str = ""
    provider: str = CPU_PROVIDER

    @property
    def succeeded(self) -> bool:
        return self.status == STATUS_OK


@dataclass
class GraphResult:
    """Aggregate outcome of one pipeline run.

    ``data`` holds every output field produced during the run, so callers read
    results by field name rather than by position in the graph.
    """

    data: dict[str, Any] = field(default_factory=dict)
    outcomes: dict[str, StageOutcome] = field(default_factory=dict)
    duration: float = 0.0

    @property
    def ok(self) -> bool:
        """True when no stage failed. A skip is not a failure."""
        return all(o.status != STATUS_FAILED for o in self.outcomes.values())

    def failures(self) -> dict[str, StageOutcome]:
        return {n: o for n, o in self.outcomes.items() if o.status == STATUS_FAILED}

    def skipped(self) -> dict[str, StageOutcome]:
        return {n: o for n, o in self.outcomes.items() if o.status == STATUS_SKIPPED}

    def stage_duration(self, name: str) -> float:
        outcome = self.outcomes.get(name)
        return outcome.duration if outcome else 0.0

    def total_stage_duration(self) -> float:
        return sum(o.duration for o in self.outcomes.values() if o.status == STATUS_OK)


class PipelineGraph:
    """A validated DAG of stages, executed in dependency order."""

    def __init__(
        self,
        nodes: Iterable[Node],
        *,
        concurrent: bool = True,
        max_workers: int = 4,
        entry_fields: Iterable[str] = (),
    ) -> None:
        self.nodes: dict[str, Node] = {}
        for node in nodes:
            if node.name in self.nodes:
                raise GraphError(f"duplicate stage name in graph: {node.name!r}")
            self.nodes[node.name] = node

        if not self.nodes:
            raise GraphError("graph declares no stages")

        self.concurrent = concurrent
        self.max_workers = max_workers
        self.entry_fields = set(entry_fields)
        self._producer = self._map_producers()
        self._sources = self._map_sources(self.entry_fields)
        self._order = self._topological_order()
        self._downstream = self._map_downstream()
        self._data: dict[str, Any] = {}
        self._lock = threading.Lock()

    # -- construction and validation --------------------------------------

    def _map_producers(self) -> dict[str, str]:
        """Map every declared output field to the stage that produces it.

        A field may be declared by at most one stage; two stages producing the
        same field would make bindings ambiguous.
        """
        producers: dict[str, str] = {}
        for name, node in self.nodes.items():
            for output_field in node.stage.outputs:
                if output_field in producers:
                    raise GraphError(
                        f"output field {output_field!r} is declared by both "
                        f"{producers[output_field]!r} and {name!r}; a field must have one producer"
                    )
                producers[output_field] = name
        return producers

    def _map_sources(self, entry_fields: Iterable[str] = ()) -> dict[str, dict[str, str | None]]:
        """For each node, map each bound input field to its producing stage.

        A field listed in ``entry_fields`` is supplied by the caller's initial
        data rather than by a stage, and maps to ``None``. Everything else must
        have a producer, which is what makes an unsatisfied binding a
        construction error rather than a runtime surprise.
        """
        entry = set(entry_fields)
        sources: dict[str, dict[str, str | None]] = {}
        for name, node in self.nodes.items():
            resolved: dict[str, str | None] = {}
            for input_field, bound_field in node.bindings.items():
                if input_field not in node.stage.inputs:
                    raise GraphError(
                        f"stage {name!r} binds {input_field!r}, which it does not declare as an input. "
                        f"Declared inputs: {list(node.stage.inputs)}"
                    )
                if bound_field in entry:
                    resolved[input_field] = None
                elif bound_field in self._producer:
                    resolved[input_field] = self._producer[bound_field]
                else:
                    raise GraphError(
                        f"stage {name!r} binds input {input_field!r} to field {bound_field!r}, "
                        f"which no stage in the graph produces and which is not declared as an "
                        f"entry field. Entry fields: {sorted(entry)}"
                    )
            for required in node.stage.inputs:
                if required not in resolved:
                    raise GraphError(
                        f"stage {name!r} requires input {required!r} but no binding provides it. "
                        f"Bindings present: {sorted(node.bindings)}"
                    )
            sources[name] = resolved
        return sources

    def _topological_order(self) -> list[str]:
        """Return a deterministic dependency-respecting order, rejecting cycles."""
        # Entry fields have no producing stage, so they contribute no edge.
        pending = {
            name: {producer for producer in self._sources[name].values() if producer is not None} for name in self.nodes
        }
        ready = sorted(name for name, deps in pending.items() if not deps)
        order: list[str] = []

        while ready:
            current = ready.pop(0)
            order.append(current)
            newly_ready = []
            for name, deps in pending.items():
                if name in order or name in ready or current not in deps:
                    continue
                deps.discard(current)
                if not deps:
                    newly_ready.append(name)
            ready.extend(newly_ready)
            ready.sort()

        if len(order) != len(self.nodes):
            unresolved = sorted(set(self.nodes) - set(order))
            raise GraphError(f"graph contains a cycle among stages: {unresolved}")

        return order

    def _map_downstream(self) -> dict[str, set[str]]:
        downstream: dict[str, set[str]] = {name: set() for name in self.nodes}
        for stage_name, sources in self._sources.items():
            for producer in sources.values():
                if producer is not None:
                    downstream[producer].add(stage_name)
        return downstream

    # -- introspection -----------------------------------------------------

    @property
    def order(self) -> list[str]:
        return list(self._order)

    def __contains__(self, name: object) -> bool:
        return name in self.nodes

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PipelineGraph stages={list(self._order)} concurrent={self.concurrent}>"

    # -- execution ---------------------------------------------------------

    def run(self, initial: dict[str, Any] | None = None) -> GraphResult:
        """Execute the graph, returning outputs keyed by field name.

        Nodes are executed in dependency order. When concurrency is enabled,
        nodes in the same dependency level -- which cannot depend on one
        another, so they are by construction independent -- run together. That
        is what lets OCR and a later classification stage share a plate crop
        without either waiting on the other's execution.
        """
        started = time.perf_counter()
        self._data = dict(initial or {})
        result = GraphResult()
        failed: set[str] = set()

        for level in self._levels():
            # A node is blocked when any stage producing a field it binds has
            # failed. Producer names come from _sources; entry fields there map
            # to None and can never block.
            blocked = {
                name: sorted(failed & {s for s in self._sources[name].values() if s is not None}) for name in level
            }
            ready = [name for name in level if not blocked[name]]
            for name in level:
                if blocked[name]:
                    result.outcomes[name] = self._skip(
                        self.nodes[name],
                        SKIP_UPSTREAM_FAILED,
                        f"upstream stage(s) failed: {blocked[name]}",
                    )

            if self.concurrent and len(ready) > 1:
                outcomes = self._run_level_concurrently(ready, failed)
            else:
                outcomes = {name: self._run_node(self.nodes[name], failed) for name in ready}

            for name, outcome in outcomes.items():
                result.outcomes[name] = outcome
                if outcome.status == STATUS_FAILED:
                    failed.add(name)

        result.data = dict(self._data)
        result.duration = time.perf_counter() - started
        return result

    def _levels(self) -> list[list[str]]:
        """Group nodes into dependency levels, preserving order within a level.

        Nodes in one level cannot depend on each other, which is what makes them
        safe to run together.
        """
        depth: dict[str, int] = {}
        for name in self._order:
            sources = [s for s in self._sources[name].values() if s is not None]
            depth[name] = 1 + max((depth[s] for s in sources), default=-1)

        levels: list[list[str]] = []
        for name in self._order:
            d = depth[name]
            while len(levels) <= d:
                levels.append([])
            levels[d].append(name)
        return levels

    def _run_level_concurrently(self, names: list[str], failed: set[str]) -> dict[str, StageOutcome]:
        outcomes: dict[str, StageOutcome] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(names))) as pool:
            futures = {name: pool.submit(self._run_node, self.nodes[name], failed) for name in names}
            for name, future in futures.items():
                try:
                    outcomes[name] = future.result()
                except Exception as exc:  # noqa: BLE001 - never lose a stage's outcome
                    outcomes[name] = StageOutcome(
                        name=name,
                        status=STATUS_FAILED,
                        reason=str(exc),
                        provider=self.nodes[name].stage.context.provider,
                    )
        return outcomes

    def _skip(self, node: Node, reason_code: str, detail: str) -> StageOutcome:
        message = f"{reason_code}: {detail}"
        logger.info("Skipping stage %s (%s)", node.name, message)
        return StageOutcome(
            name=node.name,
            status=STATUS_SKIPPED,
            reason=message,
            provider=node.stage.context.provider,
        )

    def _run_node(self, node: Node, failed: set[str]) -> StageOutcome:
        bound = {input_field: self._data.get(bound_field) for input_field, bound_field in node.bindings.items()}

        # A stage is skipped when a required input is absent, null, or empty.
        # Testing falsiness rather than `is None` matters: a detector that finds
        # no plates yields an empty detections list, and downstream recognition
        # must be skipped rather than invoked on nothing.
        missing = [name for name in node.stage.inputs if not _has_content(bound.get(name))]
        if missing:
            return self._skip(node, SKIP_MISSING_INPUT, f"absent, null, or empty field(s) {missing}")

        if node.condition is not None and not node.condition(bound):
            return self._skip(node, SKIP_CONDITION, node.condition_description or "condition not met")

        try:
            outputs, duration = node.stage.execute_timed(bound)
        except Exception as exc:  # noqa: BLE001 - contained so siblings still complete
            logger.warning("Stage %s failed: %s", node.name, exc)
            return StageOutcome(
                name=node.name,
                status=STATUS_FAILED,
                reason=str(exc),
                provider=node.stage.context.provider,
            )

        with self._lock:
            self._data.update(outputs)
        return StageOutcome(
            name=node.name,
            status=STATUS_OK,
            outputs=outputs,
            duration=duration,
            provider=node.stage.context.provider,
        )


# -- condition helpers -------------------------------------------------------


def _describe(predicate: Callable[[dict[str, Any]], bool], fallback: str) -> Callable[[dict[str, Any]], bool]:
    predicate.description = fallback  # type: ignore[attr-defined]
    return predicate


def confidence_at_least(threshold: float, description: str = "") -> Callable[[dict[str, Any]], bool]:
    """Condition requiring the bound ``confidence`` field to reach a threshold."""

    def predicate(data: dict[str, Any]) -> bool:
        confidence = data.get("confidence")
        return confidence is not None and float(confidence) >= threshold

    return _describe(predicate, description or f"confidence >= {threshold}")


def detections_present(description: str = "") -> Callable[[dict[str, Any]], bool]:
    """Condition requiring a non-empty ``detections`` field."""

    def predicate(data: dict[str, Any]) -> bool:
        return bool(data.get("detections"))

    return _describe(predicate, description or "detections is non-empty")


def build_graph(
    stages: Iterable[tuple[Stage, dict[str, str]]],
    *,
    context_for: Callable[[Stage], StageContext] | None = None,
    concurrent: bool = True,
    max_workers: int = 4,
    entry_fields: Iterable[str] = (),
) -> PipelineGraph:
    """Constructor used by configuration loading and by tests."""
    nodes = []
    for stage, bindings in stages:
        if context_for is not None:
            stage.context = context_for(stage)
        nodes.append(Node(stage=stage, bindings=bindings))
    return PipelineGraph(
        nodes,
        concurrent=concurrent,
        max_workers=max_workers,
        entry_fields=entry_fields,
    )
