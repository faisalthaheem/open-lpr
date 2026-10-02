"""Tests for the stage contract: declaration, lazy loading, and artifact errors."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

import numpy as np

from lpr_app.pipeline.stages.base import CPU_PROVIDER, Stage, StageContext, StageError
from lpr_app.tests.fixtures.onnx_builders import save_identity, save_renamed, zeros


class RecordingStage(Stage):
    """Minimal concrete stage used to test the base class contract."""

    inputs = ("source",)
    outputs = ("result",)

    def __init__(self, context=None, *, name="recording", model_path=None, payload=None):
        self.name = name
        self.model_path = model_path
        self._payload = payload if payload is not None else {"result": "done"}
        super().__init__(context)

    def run(self, data):
        return dict(self._payload)


class UnnamedStage(Stage):
    """A stage that never declares a name, so the contract check must reject it."""

    inputs = ("source",)
    outputs = ("result",)

    def run(self, data):
        return {"result": "done"}


class NoOutputStage(Stage):
    """A stage that declares no output fields, so routing would be undefined."""

    inputs = ("source",)

    def run(self, data):
        return {}


class StageDeclarationTest(TestCase):
    """A stage declares its contract without being executed."""

    def test_declaration_is_available_without_execution(self):
        stage = RecordingStage()
        self.assertEqual(stage.name, "recording")
        self.assertEqual(stage.inputs, ("source",))
        self.assertEqual(stage.outputs, ("result",))
        self.assertFalse(stage.loaded)

    def test_stage_must_declare_a_name(self):
        with self.assertRaises(StageError):
            UnnamedStage()

    def test_stage_must_declare_an_output(self):
        with self.assertRaises(StageError):
            NoOutputStage()

    def test_non_model_stage_declares_no_artifact(self):
        self.assertFalse(RecordingStage().has_model)

    def test_context_defaults_to_cpu(self):
        self.assertEqual(RecordingStage().context.provider, CPU_PROVIDER)

    def test_context_carries_provider_config_and_budgets(self):
        context = StageContext(provider="rocm", config={"k": 1}, budgets={"pipeline": 0.5})
        stage = RecordingStage(context)
        self.assertEqual(stage.context.provider, "rocm")
        self.assertEqual(stage.context.config, {"k": 1})
        self.assertEqual(stage.context.budgets["pipeline"], 0.5)


class LazyLoadingTest(TestCase):
    """Loading is lazy, happens once, and never happens for a skipped stage."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.model = save_identity(Path(self.tmp.name) / "id.onnx")

    def test_model_loads_on_first_execution_only(self):
        stage = RecordingStage(model_path=self.model)
        self.assertFalse(stage.loaded)
        stage.execute({"source": 1})
        self.assertTrue(stage.loaded)
        session = stage._session
        stage.execute({"source": 1})
        self.assertIs(stage._session, session, "session must be reused, not rebuilt")

    def test_explicit_load_is_idempotent(self):
        stage = RecordingStage(model_path=self.model)
        stage.load()
        first = stage._session
        stage.load()
        self.assertIs(stage._session, first)

    def test_never_executed_stage_does_not_load(self):
        stage = RecordingStage(model_path=self.model)
        self.assertFalse(stage.loaded)
        self.assertIsNone(stage._session)

    def test_reset_drops_the_session(self):
        stage = RecordingStage(model_path=self.model)
        stage.execute({"source": 1})
        stage.reset()
        self.assertFalse(stage.loaded)

    def test_each_stage_has_its_own_session(self):
        a = RecordingStage(name="a", model_path=self.model)
        b = RecordingStage(name="b", model_path=self.model)
        a.execute({"source": 1})
        b.execute({"source": 1})
        self.assertIsNot(a._session, b._session)

    def test_non_model_stage_load_is_a_no_op(self):
        stage = RecordingStage()
        stage.load()
        self.assertFalse(stage.loaded)


class ArtifactErrorTest(TestCase):
    """A missing or mismatched artifact is an error, never a silent substitution."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_missing_artifact_names_stage_and_path(self):
        missing = Path(self.tmp.name) / "absent.onnx"
        stage = RecordingStage(name="missing_stage", model_path=str(missing))
        with self.assertRaises(StageError) as ctx:
            stage.load()
        message = str(ctx.exception)
        self.assertIn("missing_stage", message)
        self.assertIn(str(missing), message)

    def test_no_model_path_declares_no_artifact_and_loads_nothing(self):
        # A non-model stage legitimately has no path, so load() is a no-op
        # rather than an error; the error path applies only when a stage claims
        # a model it cannot use.
        stage = RecordingStage(name="no_path", model_path=None)
        self.assertFalse(stage.has_model)
        stage.load()
        self.assertFalse(stage.loaded)

    def test_unloadable_artifact_raises_rather_than_substituting(self):
        junk = Path(self.tmp.name) / "junk.onnx"
        junk.write_text("this is not an onnx model")
        stage = RecordingStage(name="junk_stage", model_path=str(junk))
        with self.assertRaises(StageError) as ctx:
            stage.load()
        self.assertIn("junk_stage", str(ctx.exception))


class SignatureValidationTest(TestCase):
    """Shape and output-name checks happen against the real loaded artifact."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.model = save_identity(Path(self.tmp.name) / "id.onnx")
        self.renamed = save_renamed(Path(self.tmp.name) / "renamed.onnx")

    def test_matching_signature_succeeds(self):
        stage = RecordingStage(model_path=self.model)
        outputs = stage.execute({"source": 1})
        self.assertEqual(outputs, {"result": "done"})

    def test_unexpected_output_name_is_rejected(self):
        from lpr_app.pipeline.runtime.onnx import run_session, validate_output_names

        stage = RecordingStage(name="outname", model_path=self.renamed)
        stage.load()
        with self.assertRaises(StageError) as ctx:
            validate_output_names(stage._session, ("y",), stage_name="outname")
        self.assertIn("y", str(ctx.exception))
        self.assertIsNotNone(run_session)

    def test_input_rank_mismatch_is_rejected(self):
        from lpr_app.pipeline.runtime.onnx import validate_input_shape

        stage = RecordingStage(name="shape", model_path=self.model)
        stage.load()
        with self.assertRaises(StageError) as ctx:
            validate_input_shape(stage._session, {"x": zeros((1, 3, 4))}, stage_name="shape")
        self.assertIn("rank", str(ctx.exception))

    def test_missing_declared_input_is_rejected(self):
        from lpr_app.pipeline.runtime.onnx import validate_input_shape

        stage = RecordingStage(name="feed", model_path=self.model)
        stage.load()
        with self.assertRaises(StageError) as ctx:
            validate_input_shape(stage._session, {}, stage_name="feed")
        self.assertIn("x", str(ctx.exception))

    def test_correct_feed_passes_validation(self):
        from lpr_app.pipeline.runtime.onnx import run_session

        stage = RecordingStage(model_path=self.model)
        stage.load()
        out = run_session(stage._session, {"x": zeros((1, 3, 4, 4))}, ("y",), stage_name="identity")
        self.assertEqual(out["y"].shape, (1, 3, 4, 4))
        self.assertIsInstance(out["y"], np.ndarray)
