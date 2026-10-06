"""Build small ONNX artifacts used by the pipeline tests.

Kept in one place so tests exercise real onnxruntime session construction and
signature validation rather than a mock, which is what these requirements are
actually about.
"""

from __future__ import annotations

import numpy as np
import onnx
from onnx import TensorProto, helper

# Bumped when the opset used by the fixtures changes, so onnxruntime does not
# reject a saved model as too old for the installed runtime.
_OPSET = 13
_IR_VERSION = 9


def save_identity(path, *, in_shape=(1, 3, 4, 4), in_name="x", out_name="y"):
    """Save a single-node identity model with pinned input and output shapes."""
    x = helper.make_tensor_value_info(in_name, TensorProto.FLOAT, list(in_shape))
    y = helper.make_tensor_value_info(out_name, TensorProto.FLOAT, list(in_shape))
    graph = helper.make_graph([helper.make_node("Identity", [in_name], [out_name])], "identity", [x], [y])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", _OPSET)])
    model.ir_version = _IR_VERSION
    onnx.save(model, str(path))
    return str(path)


def save_renamed(path, *, in_shape=(1, 3, 4, 4)):
    """Save an identity model whose output is named differently from the input.

    Used to test that a stage reading an unexpected output name is an error
    rather than a silent read of unintended meaning.
    """
    return save_identity(path, in_shape=in_shape, in_name="input", out_name="renamed_output")


def save_double_input(path):
    """Save a model taking two inputs and emitting their sum.

    Used to test that a feed missing a declared input is rejected, and to give a
    stage more than one input in graph tests.
    """
    a = helper.make_tensor_value_info("a", TensorProto.FLOAT, [1, 4])
    b = helper.make_tensor_value_info("b", TensorProto.FLOAT, [1, 4])
    out = helper.make_tensor_value_info("sum", TensorProto.FLOAT, [1, 4])
    graph = helper.make_graph([helper.make_node("Add", ["a", "b"], ["sum"])], "add", [a, b], [out])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", _OPSET)])
    model.ir_version = _IR_VERSION
    onnx.save(model, str(path))
    return str(path)


def zeros(shape, dtype=np.float32):
    return np.zeros(shape, dtype=dtype)
