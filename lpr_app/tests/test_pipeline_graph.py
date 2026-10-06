"""Tests for the stage graph: construction validation, ordering, and execution."""

from __future__ import annotations

from unittest import TestCase

from lpr_app.pipeline.graph import (
    SKIP_CONDITION,
    SKIP_MISSING_INPUT,
    SKIP_UPSTREAM_FAILED,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_SKIPPED,
    GraphError,
    Node,
    PipelineGraph,
    build_graph,
    confidence_at_least,
    detections_present,
)
from lpr_app.pipeline.stages.base import Stage


class FakeStage(Stage):
    """A stage that returns canned data, optionally failing or sleeping."""

    def __init__(self, name, inputs, outputs, *, payload=None, exc=None, sleep=0.0):
        self.name = name
        self.inputs = tuple(inputs)
        self.outputs = tuple(outputs)
        self.model_path = None
        self._payload = payload or {}
        self._exc = exc
        self._sleep = sleep
        self.calls = 0
        super().__init__()

    def run(self, data):
        self.calls += 1
        if self._sleep:
            import time

            time.sleep(self._sleep)
        if self._exc is not None:
            raise self._exc
        # Return only the fields the stage declares, so graph routing is
        # exercised rather than masked by extra keys.
        payload = {field: self._payload.get(field) for field in self.outputs}
        return payload


def source(name="source", outputs=("image",), payload=None, **kw):
    """A source stage with no inputs. Produces a non-null value per output field
    unless the caller overrides it, so downstream stages are not skipped."""
    if payload is None:
        payload = {field: f"VALUE-{field}" for field in outputs}
    return FakeStage(name, (), outputs, payload=payload, **kw)


class GraphConstructionTest(TestCase):
    """Validation happens at construction, before any stage loads or executes."""

    def test_graph_assembles_from_declarations_without_code_changes(self):
        a = source()
        b = FakeStage("b", ("image",), ("text",), payload={"text": "ABC"})
        graph = build_graph([(a, {}), (b, {"image": "image"})])
        self.assertEqual(graph.order, ["source", "b"])

    def test_unsatisfied_binding_is_rejected_at_construction(self):
        a = source()
        b = FakeStage("b", ("image",), ("text",))
        with self.assertRaises(GraphError) as ctx:
            build_graph([(a, {}), (b, {"image": "nonexistent_field"})])
        self.assertIn("nonexistent_field", str(ctx.exception))
        self.assertEqual(a.calls, 0, "no stage may execute when construction fails")

    def test_binding_to_undeclared_input_is_rejected(self):
        a = source()
        b = FakeStage("b", ("image",), ("text",))
        with self.assertRaises(GraphError) as ctx:
            build_graph([(a, {}), (b, {"not_an_input": "image"})])
        self.assertIn("not_an_input", str(ctx.exception))

    def test_missing_required_binding_is_rejected(self):
        a = source()
        b = FakeStage("b", ("image",), ("text",))
        with self.assertRaises(GraphError) as ctx:
            build_graph([(a, {}), (b, {})])
        self.assertIn("image", str(ctx.exception))

    def test_cycle_is_rejected_and_names_the_cycle(self):
        a = FakeStage("a", ("text",), ("image",))
        b = FakeStage("b", ("image",), ("text",))
        with self.assertRaises(GraphError) as ctx:
            build_graph([(a, {"text": "text"}), (b, {"image": "image"})])
        self.assertIn("cycle", str(ctx.exception).lower())

    def test_duplicate_stage_name_is_rejected(self):
        with self.assertRaises(GraphError):
            build_graph([(source("dup"), {}), (source("dup"), {})])

    def test_empty_graph_is_rejected(self):
        with self.assertRaises(GraphError):
            build_graph([])

    def test_two_stages_cannot_produce_the_same_field(self):
        a = source("a")
        b = source("b")
        with self.assertRaises(GraphError) as ctx:
            build_graph([(a, {}), (b, {})])
        self.assertIn("image", str(ctx.exception))


class GraphExecutionTest(TestCase):
    """Data routing, ordering, and conditions during execution."""

    def test_declared_output_fields_reach_downstream_stages(self):
        a = source()
        b = FakeStage("b", ("image",), ("text",), payload={"text": "ABC"})
        c = FakeStage("c", ("text",), ("final",))
        result = build_graph([(a, {}), (b, {"image": "image"}), (c, {"text": "text"})]).run()
        self.assertTrue(result.ok)
        self.assertEqual(result.data["text"], "ABC")
        self.assertIn("final", result.data)

    def test_no_detections_upstream_skips_dependent_stages(self):
        a = source(outputs=("detections",), payload={"detections": []})
        b = FakeStage("b", ("detections",), ("text",))
        result = build_graph([(a, {}), (b, {"detections": "detections"})]).run()
        self.assertTrue(result.ok, "a skip is not a failure")
        self.assertEqual(result.outcomes["b"].status, STATUS_SKIPPED)
        self.assertIn(SKIP_MISSING_INPUT, result.outcomes["b"].reason)
        self.assertEqual(b.calls, 0, "a skipped stage must not execute")

    def test_condition_on_confidence_threshold_skips_below(self):
        a = source(outputs=("confidence",), payload={"confidence": 0.2})
        b = FakeStage("b", ("confidence",), ("text",))
        graph = build_graph([(a, {}), (b, {"confidence": "confidence"})])
        graph.nodes["b"].condition = confidence_at_least(0.5)
        graph.nodes["b"].condition_description = "confidence >= 0.5"
        result = graph.run()
        self.assertEqual(result.outcomes["b"].status, STATUS_SKIPPED)
        self.assertIn(SKIP_CONDITION, result.outcomes["b"].reason)

    def test_condition_passes_above_threshold(self):
        a = source(outputs=("confidence",), payload={"confidence": 0.9})
        b = FakeStage("b", ("confidence",), ("text",), payload={"text": "OK"})
        graph = build_graph([(a, {}), (b, {"confidence": "confidence"})])
        graph.nodes["b"].condition = confidence_at_least(0.5)
        result = graph.run()
        self.assertEqual(result.outcomes["b"].status, STATUS_OK)
        self.assertEqual(result.data["text"], "OK")

    def test_detections_present_condition(self):
        predicate = detections_present()
        self.assertFalse(predicate({"detections": []}))
        self.assertTrue(predicate({"detections": [1]}))

    def test_initial_data_seeds_fields_no_stage_produces(self):
        # A stage may bind an input to a field that comes from the caller's
        # initial data rather than from an upstream stage. That is how a loaded
        # image enters the graph.
        reader = FakeStage("reader", (), ("text",), payload={"text": "READ"})
        consumer = FakeStage("consumer", ("image",), ("ocr_text",), payload={"ocr_text": "SEEN"})
        graph = PipelineGraph(
            [
                Node(stage=reader, bindings={}),
                Node(stage=consumer, bindings={"image": "image"}),
            ],
            entry_fields={"image"},
        )
        result = graph.run({"image": "PRESET"})
        self.assertEqual(result.outcomes["consumer"].status, STATUS_OK)
        self.assertEqual(result.data["ocr_text"], "SEEN")
        self.assertEqual(result.data["image"], "PRESET", "initial data must survive the run")


class FailureContainmentTest(TestCase):
    """A failing stage is contained and does not abort unrelated stages."""

    def test_failure_does_not_prevent_other_stages_completing(self):
        good = source("good", outputs=("image",))
        bad = FakeStage("bad", (), ("boom",), exc=RuntimeError("stage exploded"))
        result = build_graph([(good, {}), (bad, {})]).run()
        self.assertFalse(result.ok)
        self.assertEqual(result.outcomes["good"].status, STATUS_OK)
        self.assertEqual(result.outcomes["bad"].status, STATUS_FAILED)
        self.assertIn("stage exploded", result.outcomes["bad"].reason)
        self.assertIn("image", result.data, "successful outputs must be preserved")

    def test_failure_names_the_failing_stage(self):
        bad = FakeStage("bad", (), ("boom",), exc=ValueError("nope"))
        result = build_graph([(bad, {})]).run()
        self.assertIn("bad", result.failures())
        self.assertIn("nope", result.outcomes["bad"].reason)

    def test_dependent_stages_skip_and_attribute_the_cause(self):
        good = source("good", outputs=("image",))
        bad = FakeStage("bad", ("image",), ("mid",), exc=RuntimeError("upstream broke"))
        after = FakeStage("after", ("mid",), ("text",))
        graph = build_graph([(good, {}), (bad, {"image": "image"}), (after, {"mid": "mid"})])
        result = graph.run()
        self.assertEqual(result.outcomes["after"].status, STATUS_SKIPPED)
        reason = result.outcomes["after"].reason
        self.assertIn(SKIP_UPSTREAM_FAILED, reason)
        self.assertIn("bad", reason, "the skip must name the originating stage")
        self.assertNotIn(SKIP_UPSTREAM_FAILED, result.outcomes["bad"].reason)

    def test_downstream_skip_is_distinct_from_its_own_failure(self):
        good = source("good", outputs=("image",))
        bad = FakeStage("bad", ("image",), ("mid",), exc=RuntimeError("x"))
        after = FakeStage("after", ("mid",), ("text",))
        graph = build_graph([(good, {}), (bad, {"image": "image"}), (after, {"mid": "mid"})])
        result = graph.run()
        self.assertEqual(result.outcomes["bad"].status, STATUS_FAILED)
        self.assertEqual(result.outcomes["after"].status, STATUS_SKIPPED)


class ConcurrencyTest(TestCase):
    """Independent stages run concurrently, and the result is unchanged."""

    def _fanout_graph(self, **kw):
        """Detect feeds two independent siblings that both read the same crop.

        Both siblings sleep the same amount, so overlapping them is observable
        as elapsed time well below their sum.
        """
        detect = FakeStage("detect", (), ("rectified",), payload={"rectified": "PLATE"})
        ocr = FakeStage("ocr", ("rectified",), ("ocr_text",), payload={"ocr_text": "ABC"}, sleep=0.05)
        classify = FakeStage(
            "classify", ("rectified",), ("plate_type",), payload={"plate_type": "commercial"}, sleep=0.05
        )
        return build_graph(
            [(detect, {}), (ocr, {"rectified": "rectified"}), (classify, {"rectified": "rectified"})], **kw
        )

    def test_sibling_stages_share_one_upstream_output(self):
        result = self._fanout_graph().run()
        self.assertTrue(result.ok)
        self.assertEqual(result.data["ocr_text"], "ABC")
        self.assertEqual(result.data["plate_type"], "commercial")

    def test_concurrent_and_sequential_produce_the_same_result(self):
        concurrent = self._fanout_graph(concurrent=True).run()
        sequential = self._fanout_graph(concurrent=False).run()
        for key in ("ocr_text", "plate_type", "rectified"):
            self.assertEqual(concurrent.data[key], sequential.data[key])
        self.assertEqual(set(concurrent.outcomes), set(sequential.outcomes))

    def test_concurrent_execution_overlaps_independent_stages(self):
        import time

        graph = self._fanout_graph(concurrent=True)
        started = time.perf_counter()
        graph.run()
        concurrent_elapsed = time.perf_counter() - started

        graph_seq = self._fanout_graph(concurrent=False)
        started = time.perf_counter()
        graph_seq.run()
        sequential_elapsed = time.perf_counter() - started

        # Two independent 50ms stages: overlapping is substantially faster than
        # additive. Loose bound keeps this robust on a loaded machine.
        self.assertLess(concurrent_elapsed, sequential_elapsed * 0.75)

    def test_sequential_execution_is_deterministic(self):
        graph = self._fanout_graph(concurrent=False)
        declared_order = graph.order
        result = graph.run()
        # Outcomes are recorded in execution order, which in sequential mode is
        # the declared dependency order.
        self.assertEqual(declared_order, list(result.outcomes))

    def test_declared_order_respects_dependencies(self):
        graph = self._fanout_graph(concurrent=False)
        order = graph.order
        self.assertLess(order.index("detect"), order.index("ocr"))
        self.assertLess(order.index("detect"), order.index("classify"))

    def test_each_stage_uses_its_own_session_under_concurrency(self):
        import tempfile
        from pathlib import Path

        from lpr_app.tests.fixtures.onnx_builders import save_identity

        with tempfile.TemporaryDirectory() as tmp:
            model = save_identity(Path(tmp) / "id.onnx")

            class CountingStage(Stage):
                def __init__(self, name, out):
                    self.name = name
                    self.inputs = ("x",)
                    self.outputs = (out,)
                    self.model_path = model
                    super().__init__()

                def run(self, data):
                    # Touch the session so loading is exercised concurrently.
                    self._session.session.get_inputs()
                    return {self.outputs[0]: self.name}

            stages = [CountingStage("s1", "y1"), CountingStage("s2", "y2")]
            detect = FakeStage("detect", (), ("x",), payload={"x": "SEED"})
            # Both siblings bind the same upstream field, so they are independent.
            graph = PipelineGraph(
                [
                    Node(stage=detect, bindings={}),
                    Node(stage=stages[0], bindings={"x": "x"}),
                    Node(stage=stages[1], bindings={"x": "x"}),
                ],
                concurrent=True,
            )
            result = graph.run()
            self.assertTrue(result.ok, result.failures())
            self.assertIsNot(stages[0]._session, stages[1]._session)


class GraphResultTest(TestCase):
    """Result accessors behave as the runner's callers expect."""

    def test_duration_is_recorded_per_stage_and_end_to_end(self):
        a = source()
        b = FakeStage("b", ("image",), ("text",), payload={"text": "x"})
        result = build_graph([(a, {}), (b, {"image": "image"})]).run()
        self.assertGreater(result.duration, 0.0)
        self.assertGreaterEqual(result.stage_duration("b"), 0.0)
        self.assertEqual(result.stage_duration("nonexistent"), 0.0)
        self.assertGreater(result.total_stage_duration(), 0.0)

    def test_thread_safety_of_data_update_under_concurrency(self):
        # Many independent writers; every output must land exactly once with no
        # lost update or interleaved corruption.
        stages = []
        pairs = []
        for i in range(8):
            stages.append((source(f"s{i}", outputs=(f"f{i}",), payload={f"f{i}": i}), {}))
        previous = None
        for i in range(8):
            if previous is not None:
                pairs.append((previous, f"f{i - 1}"))
            previous = None
        # Simple independent leaf stages all reading the first output.
        first = source("first", outputs=("shared",), payload={"shared": "S"})
        leaves = [
            (FakeStage(f"leaf{i}", ("shared",), (f"out{i}",), payload={f"out{i}": i}), {"shared": "shared"})
            for i in range(8)
        ]
        graph = build_graph([(first, {}), *leaves], concurrent=True)
        result = graph.run()
        self.assertTrue(result.ok, result.failures())
        for i in range(8):
            self.assertEqual(result.data[f"out{i}"], i)
