## Why

Plate detection and OCR currently run through a Qwen3-VL multimodal LLM served by llama.cpp, which takes 3s or more per image because every detection and every plate crop is a generative inference call. A purpose-trained pipeline of small convolutional/recurrent networks runs the same work in well under 500ms, and — more importantly — makes each stage swappable, so future stages such as plate-type and issuing-region classification can be inserted without reworking the pipeline's structure.

## What Changes

- Add a local inference pipeline that performs plate detection and OCR with ONNX Runtime instead of the LLM, with the LLM retained as a selectable fallback backend.
- Model the pipeline as a directed graph of independently swappable stages rather than a fixed three-phase procedure, so stages can be added, removed, or reordered by configuration.
- Support fan-out within the graph: stages that consume the same plate crop (OCR and plate classification) execute concurrently rather than sequentially.
- Support per-stage execution-provider selection so a stage can run on CPU, CUDA, or ROCm, chosen by configuration, with CPU inference as the supported deployment target.
- Add a classical perspective-rectification stage between detection and OCR so the OCR model only ever sees a deskewed plate.
- Support plate layouts that are not uniform: the annotated corpus is mixed US, Indian, and EU plates where 45% are stacked two-line plates, so rectification aspect ratios and recognition must handle both stacked and single-line layouts, and the character set must be a selectable profile rather than one global set.
- Add offline training, ONNX export, and latency benchmark tooling for the detection model, sourced from an out-of-tree annotated image corpus, restricted to model weights under a permissive license compatible with this project's Apache-2.0 license.
- Gate the whole path behind a setting so the existing LLM path remains the default until accuracy is validated against it.

No breaking changes: the pipeline's output continues to populate the same `detections` array shape consumed by the API and UI, and the LLM backend remains selectable.

## Capabilities

### New Capabilities
- `stage-graph-runtime`: Composition and execution of a directed graph of swappable inference stages, including conditional execution, fan-out concurrency, and per-stage execution-provider placement.
- `onnx-stage-contract`: The uniform interface every pipeline stage implements — declared inputs, outputs, schema, model loading, and provider binding — so that swapping a stage implementation or model file requires no change to the graph or its callers.
- `local-plate-detection`: Plate detection from a local ONNX model, replacing LLM detection as a selectable backend, including coordinate scaling from the detection input resolution to the original image.
- `local-plate-ocr`: Text recognition on rectified plate crops from a local ONNX recognizer, including layout-aware handling of stacked two-line plates, charset-profile-restricted decoding, and per-plate confidence reporting.
- `plate-rectification`: Classical perspective correction that maps a detected plate region to a layout-appropriate deskewed aspect ratio before OCR, degrading gracefully when corner geometry is unavailable.
- `pipeline-latency-budget`: A measurable, enforced per-stage and end-to-end latency budget, reported through the existing metrics surface so regressions are observable in production.
- `model-training-tooling`: Offline dataset loading, training, ONNX export, and benchmarking scripts for the pipeline's detector, including locating the out-of-tree annotated corpus and recording each model artifact's provenance and license.

### Modified Capabilities
- `ocr-crop-padding`: The existing crop padding requirement governs LLM-phase crops keyed to `OCR_CROP_PADDING_PX`. Rectified plates are now the OCR input, so the requirement must state that rectification supersedes fixed-pixel padding when the rectification stage is enabled, while padding still applies to the fallback path.

## Impact

- **New code**: `lpr_app/pipeline/` (graph runtime, stage base class, ONNX runtime wrapper, stage implementations) and `lpr_app/ml/` (offline training, export, and benchmark tooling). Neither is imported by the web process except `lpr_app/pipeline/`.
- **Modified code**: `lpr_app/services/image_processing_service.py` gains a backend switch between the existing phased LLM flow and the graph runtime; `lpr_project/settings.py` gains pipeline and backend settings; `.env.example` and `AGENTS.md` document them.
- **New dependencies**: `onnxruntime` (and `onnxruntime-gpu`/`onnxruntime-rocm` as install variants, not runtime imports), plus training-only `torch` and `torchvision`. Training dependencies must not be required by the web runtime.
- **Licensing constraint**: detector weights must be under a license compatible with this project's Apache-2.0 license. AGPL-3.0 weights, including the Ultralytics YOLO families, are excluded.
- **Models**: new ONNX artifacts under the already-gitignored `model/` path. Training data lives outside the repository and is located by a configurable path.
- **Runtime**: CPU-only inference is the supported deployment path, so no production host change is required to run the new backend. Training is GPU-executed and runs in a container with the appropriate device passthrough, so ROCm is not a host prerequisite for contributors.
- **Operational risk**: the new backend may be less accurate than the LLM on unusual plates. The LLM default is retained until a recorded accuracy comparison justifies the switch.