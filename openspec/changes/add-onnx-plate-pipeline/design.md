## Context

The current backend in `lpr_app/services/image_processing_service.py` is a fixed three-phase procedure driven by a Qwen3-VL model served over llama.cpp (`qwen_client.py`):

1. Downscale the image, ask the LLM to detect plates, parse the JSON bounding boxes, scale coordinates back to the original resolution, then filter via `DetectionValidator`.
2. Crop each detected plate with fixed-pixel padding from `OCR_CROP_PADDING_PX`, batch the crops, and ask the LLM to read each one.
3. Merge results, validate OCR text, and visualize bounding boxes.

Two properties of this shape drive everything below.

**It is slow because it is generative.** Each detection is one multimodal generation and each plate is another. A 3s+ floor for a single image is the expected cost of that design, not a tuning problem. Phase 2's cost scales linearly with plate count.

**It is a hardcoded sequence, not a pipeline.** Phases are inline procedural code with data threaded through local variables. Inserting a stage means editing the method; running two stages over the same crop means restructuring control flow.

Constraints that shape the solution:

- The available corpus (an annotated image dataset with a single `plate` class and no transcription labels) supports training a detector. It does not support training a recognizer, so the OCR model is adopted from an existing pretrained project rather than trained here.
- Contributors will not all have ROCm. The maintainer's workstation has AMD GPUs, but the supported inference target is CPU-only, so the latency budget must be met without a GPU.
- `.gitignore` already excludes `model/`, `models/*`, and `filestorage/*`; model artifacts follow that convention.
- The repo has an OpenSpec workflow, a ruff lint/format gate, and a coverage ratchet, so new code is expected to arrive with tests.

## Goals / Non-Goals

**Goals:**

- Detect plates and read their text in well under 500ms per image on CPU, versus 3s+ today.
- Make each stage independently swappable through configuration, so a new model or a new stage is a config change plus a new class, not a refactor.
- Allow stages that consume the same input to run concurrently, so added analysis does not multiply end-to-end latency.
- Support CPU, CUDA, and ROCm from a single model artifact, with per-stage placement.
- Produce output in the existing `detections` array shape so the API and SPA are unaffected.
- Keep the LLM backend selectable so accuracy can be compared before committing to a switch.

**Non-Goals:**

- Plate-type and issuing-region classification. Deferred; the graph must admit it later, but no implementation now.
- Retraining or fine-tuning an OCR model. An existing pretrained recognizer is adopted as-is.
- Replacing the LLM path outright, or removing it.
- Real-time video or multi-frame tracking. Single still images only.
- Improving the underlying detector's accuracy beyond the supplied corpus.
- GPU-accelerated production deployment.

## Decisions

### ONNX Runtime as the single inference runtime

**Choice.** All stages are ONNX graphs executed by `onnxruntime`, wrapped in one session wrapper.

**Why.** One runtime serves CPU, CUDA, and ROCm from the same artifact — the target is selected by passing an execution provider at session construction, not by changing model or code. That is exactly the portability the project needs, and it means CPU deployment needs no GPU-specific build.

**Alternatives.**
- *PyTorch at inference.* Heavier, slower on CPU, and couples the web process to a training framework. Rejected: the web process should not import torch at all.
- *Triton.* Operational overhead out of proportion to serving two models. Rejected.
- *A native C++ extension.* Fastest, but reintroduces a per-platform build for every host and defeats model swappability. Rejected; revisit only if the latency budget is missed.

### A stage graph, not a phase pipeline

**Choice.** The pipeline is a configuration-declared DAG. Each node names a stage class and its model path; edges declare data dependencies. Execution is dependency-ordered, with independent nodes run concurrently.

**Why.** It makes the "insert a stage" requirement structural rather than a code edit, and it expresses fan-out as the default case. A later plate-type classifier becomes one node consuming the rectified plate, automatically concurrent with OCR, with no change to either.

**Alternatives.**
- *Linear list of stages.* Cannot express fan-out, so the concurrency requirement would still need special-casing.
- *A plugin/entry-point registry.* More indirection than the problem warrants; stages are few and known. Revisit if third-party stages become a goal.

### Uniform stage contract

**Choice.** Every stage subclasses one base and declares its name, input fields, output fields, and model path. The graph runner introspects declared fields to route data, so adding a stage requires no changes to the runner.

**Why.** Keeps the runner generic and makes the data contract between stages explicit and checkable rather than implicit in local variable names.

### Explicit model placement per stage

**Choice.** Configuration specifies a device per stage (`cpu`, `cuda`, `rocm`), defaulting to CPU. The wrapper requests that provider and falls back to CPU when unavailable, logging the substitution.

**Why.** The dominant deployment target is CPU-only, so the default must be the thing that works everywhere. Explicit per-stage placement matters for the maintainer's GPU workstation, where a fan-out pair genuinely can run in parallel. Silent fallback rather than hard failure keeps a misconfigured stage from taking down image processing.

### Rectification as a non-model stage

**Choice.** A classical perspective transform maps the detected plate region to a layout-appropriate aspect ratio before recognition.

**Why.** It decouples the hardest OCR accuracy problem — skewed, non-rectangular input — from the recognizer, which then only ever sees clean plates. Being classical, it adds microseconds and needs no model or training. The transform accepts explicit corner geometry when a detector supplies it, and derives corners from the axis-aligned bounding region when it does not, because the corpus supports only box regression (see the corpus-geometry decision below).

### Adopt an existing OCR model rather than train one

**Choice.** Adopt **PP-OCRv6_small** recognition, exported to ONNX, executed through ONNX Runtime. Published CPU figures for the small tier on an Intel Xeon are 0.61s per full document end-to-end (detection plus recognition across all text lines), which leaves ample headroom for the handful of single-plate crops this pipeline handles. Reported recognition accuracy is 81.3% weighted average, and its 50-language Latin coverage is irrelevant to cost here since decoding is restricted anyway.

**Why.** The corpus has no transcription labels, so training a recognizer is not possible from available data. PP-OCRv6_small is Apache-2.0, ships first-class ONNX exports, and is supported by RapidOCR and other ONNX-only loaders, so no PaddlePaddle dependency is needed. The small tier rather than medium is chosen deliberately: on published CPU benchmarks the *small* tier also beats the *medium* tier on detection H-mean (84.1 vs 86.2 for medium is close, but medium recognition is 40ms vs 7ms for small), and the plate task is far easier than general document OCR. Tiny is rejected — its recognition accuracy (73.5%) drops below even v5_mobile.

**Alternatives.**
- *PP-OCRv6_medium.* More accurate in general (83.2%) but 5× the recognition latency and, per the RapidOCR benchmark discussion, not reliably better than small even on general text. Revisit only if plate-specific accuracy proves insufficient.
- *PARSeq.* Strong on ambiguous and dirty text and an appealing teacher for distillation, but an order of magnitude larger and slower, which is the wrong trade against a 500ms budget. Noted as follow-on work if a distillation round is ever justified.
- *A cloud OCR API.* Violates the latency budget and the self-hosting posture. Rejected.
- *Tesseract.* Materially slower on small, blurred, embossed crops and weaker on stylized plate glyphs. Rejected.
- *Hand-training a CRNN on gathered transcription data.* Best long-term accuracy and control, but blocked on data acquisition; noted as follow-on work.

### No per-image fallback to the LLM
**Choice.** When the local pipeline is uncertain about an image, the result is reported as-is. The image is not re-processed by the LLM. The backend remains switchable for the whole pipeline, but there is no per-image or per-plate escalation.

**Why.** Escalation makes the worst case the LLM's worst case, which defeats the sub-500ms budget whenever it triggers, and it makes cost per request unbounded in a way that is hard to forecast. It also hides accuracy problems: the metrics would show healthy results while a large fraction of images were quietly paying LLM latency, so a regression would surface as an unexplained bill rather than as a detectable accuracy drop. A confidence threshold that silently triggers escalation is not observably different from a bug.

Reported-low-confidence results are the honest signal. If accuracy turns out insufficient, the correct response is to improve the model or gather transcription labels, not to add a slow path behind a threshold. This decision is revisited only if a recorded comparison shows the local backend's accuracy gap is small and localized enough that a targeted fix is unavailable.

### Detector choice is constrained by the project's Apache-2.0 license

**Choice.** Do not adopt Ultralytics YOLO26 or YOLO11 for the detector, despite their speed advantage. Select a permissive detector after a licensing and accuracy check.

**Why.** This is a hard constraint discovered during the open-question review, and it invalidates the detector named earlier in this project. Ultralytics weights and code are **AGPL-3.0**, which is incompatible with distributing this Apache-2.0 application under AGPL terms. AGPL's network-use clause reaches users interacting with the application over a network, which a self-hosted web app plainly triggers. YOLO26 is additionally ~31% faster on CPU ONNX than YOLO11n and NMS-free, which makes it the model that would otherwise have been chosen — the license makes it unusable without converting the project's license.

Permissive alternatives exist and are the ones to evaluate: RF-DETR (Apache-2.0), which additionally benchmarked best on small and occluded license plates, and MMDetection's RTMDet family (Apache-2.0). A purpose-built plate detector or a self-trained model on this corpus is also viable and would avoid third-party weights entirely.

**Consequence for the detection input resolution.** Because the detector choice is open, the input resolution cannot be frozen yet. Resolution trades recall on small plates against CPU cost, and the corpus makes this concrete: median plate height is only 61px, with a 10th percentile of 36px, so a resolution too low to resolve a 36px plate destroys recall outright. Resolution and thresholds are to be settled by the benchmark tooling (task 11.7) rather than assumed.

### The corpus is multi-country and contains two-line plates, so layout handling must be explicit

**Choice.** Treat the charset as a **configurable profile with an alphanumeric-only default**, and make rectification support both single-line and stacked two-line layouts rather than assuming one.

**Why.** Inspecting the corpus contradicts the EU-centric assumption this project started from. Of 2363 usable regions, the observed plates are overwhelmingly **US state plates** (Delaware, Minnesota, Illinois, Michigan, Kansas, Ohio, Arizona, New Jersey) and **Indian plates** (ICT Islamabad, Punjab, Kashmir, Himachal Pradesh, Haryana, Uttarakhand), with a minority of EU plates (Belgium, Germany, Turkey). Sample plates seen include `937087` (Delaware), `MN 5730`, `IDH-4497` (Islamabad), `O136AB` (Kashmir), `LUE-416` (Michigan), `EBS ER9H` (EU-format with blue band).

This has three concrete consequences:

1. **No single canonical aspect ratio is correct.** Plate width-to-height ratios in the corpus are bimodal: 44.7% below 2.0 (stacked two-line plates such as `RIW/6522`, `LRL/8005`, `X4G/LKK`) and 22.1% in the 2.6–3.4 band (single-line US and EU plates), median 2.12, with a 90th percentile of 3.59. Forcing one ratio either squeezes two-line plates or wastes resolution on wide ones. The canonical ratio must therefore be **configurable per layout**, with the layout either declared in configuration or detected from the detected geometry.
2. **Two-line plates must be readable.** A single-line recognizer pass over a stacked plate misreads the rows as one string. The recognition stage must support splitting a tall crop into two rows, or a layout-aware input, and must be tested against stacked plates specifically.
3. **Charset must not be a single global set.** US plates omit `I` and `O` in many states; Indian and EU plates use different characters and separators; the corpus also shows non-Latin text on some Indian plates. A single hardcoded `0-9A-Z` is wrong as a global truth. The default profile restricts to alphanumerics and treats separators as a per-profile concern, with regional profiles selectable at runtime.

### Corpus annotations are axis-aligned boxes, which constrains the detector's output geometry

**Choice.** Design the detection stage to accept an axis-aligned box as its minimum viable output, with the quadrilateral an optional refinement rather than a hard requirement.

**Why.** Every one of the 2363 annotations in the corpus is an axis-aligned `{x, y, width, height}` box with a single label `plate`. There are **no corner or polygon annotations**, and the `z` field is a constant 100 for 2314 of 2363 regions and 0 for the rest — it is not per-region geometry. Two consequences: a detector can be trained directly on this corpus only for box regression, not for corner regression; and any quadrilateral refinement must come from a model trained on different data, or from a classical corner estimate.

The design therefore treats rectification as best-effort: given a box, estimate corners (classically, or from a pose-style head trained on separate data), then rectify. The `plate-rectification` requirement is deliberately written to accept a bounding region when corner estimation is unavailable, and the bypass path already specifies exactly that. This is why that bypass is not merely a convenience.

### Ground-truth database does not match the corpus directory

**Choice.** Resolve annotation file names against the image directory, verify resolution, and report unresolved entries rather than failing hard.

**Why.** `train.db` records 2339 annotation records and `val.db` a further 260, and every region checked resolves to an existing file — but the corpus also contains an older `train_and_val.db` and a `README.md`, so the intended split is not obvious from the directory alone. `train_and_val.db` should be inspected before assuming `train`/`val` is authoritative, and the tooling must report any filename it cannot resolve instead of silently dropping it, so a split mistake cannot quietly shrink the training set.

### Training lives in `lpr_app/ml/` and is not importable by the web app

**Choice.** Training, export, and benchmark scripts live under `lpr_app/ml/` and are not imported by the Django process. They locate the corpus via a configurable path.

**Why.** Keeps the web runtime's dependency set free of torch and avoids a torchvision/OpenCV version conflict with the host packages. A subpackage, rather than top-level `scripts/`, because these are part of the model lifecycle rather than deployment tooling.

### Switch is configuration-gated with the LLM as default

**Choice.** A setting selects the backend; `llm` remains the default until a recorded accuracy comparison justifies otherwise.

**Why.** The new pipeline may well be worse than an LLM on unusual plates. Making the switch explicit and reversible means an accuracy regression is a config change, not an incident. This is the main risk control in the whole design.

### Corpus stays out of the repository

**Choice.** The annotated corpus is located by a configurable path with an environment variable and a sibling-directory default, and is never committed.

**Why.** It is third-party data in the hundreds of megabytes. Committing it would bloat every clone and fork the upstream project's history. The existing `.gitignore` already excludes model and storage paths, so the convention exists.

## Risks / Trade-offs

- **Detector licensing is a hard constraint, not a preference** → Ultralytics YOLO26/YOLO11 are AGPL-3.0 and are excluded. Evaluate permissive alternatives (RF-DETR, RTMDet) and record the license of the chosen weights in the model manifest. If none is adequate, self-train on the corpus.
- **No corner annotations in the corpus** → Rectification accepts a bounding region and treats corner estimation as best-effort; the bypass path is a first-class tested configuration, not a fallback. Do not promise quad-accurate rectification until a corner-annotated source is added.
- **Two-line plates will be misread if layout is ignored** → Recognition must support stacked layouts, and the charset/aspect profiles are configurable rather than global. Stacked plates are 44.7% of the corpus, so this is a majority case, not an edge case.
- **Plate median height is only 61px** → Detector resolution is a recall-critical parameter, not a free speed knob. If resolution must drop to meet the latency budget, the accuracy cost must be measured and reported rather than assumed.
- **No per-image fallback means low-confidence results are surfaced, not masked** → Exported per-stage metrics and confidence values make the accuracy gap visible rather than hidden behind silent escalation. This is deliberate: escalation would make worst-case latency and cost unbounded while concealing regressions.
- **Dependency footprint grows** (ONNX Runtime in the web image) → Pin exact versions; keep training dependencies in a separate requirement file so the web image never installs torch.
- **Latency budget missed on CPU** → The budget is enforced in tests and exported as a metric. Mitigation if it happens: quantize to int8, lower detection resolution (measuring recall cost), or reduce the recognizer to the tiny tier.
- **Model artifacts are not version-controlled** → Record filename, SHA, upstream checkpoint identity, and its license in a manifest committed alongside the pipeline config.
- **Fan-out concurrency on CPU yields little** → Stages run sequentially by default under a setting; concurrency is enabled explicitly.
- **Stage contract too loose** → Declare and validate input/output field names at graph construction, failing fast on an unsatisfied edge rather than at inference time.
- **Corpus assumptions may be wrong for future deployment regions** → Charset and aspect profiles are configuration, not code, so a new region is a config entry. Region-specific profiles need to be authored and validated against real plates from that region.
- **Orthogonal pre-existing spec breakage** → Eighteen existing specs fail validation due to a stray delta header from an earlier archive. Unrelated to this change; fix separately.

## Migration Plan

1. Land the graph runtime, stage base, ONNX wrapper, and rectification stage with no backend switch and no settings change. Dead code in production, fully unit-tested.
2. Select and verify the detector's license and accuracy; train on the corpus and add the detection stage. Default still `llm`.
3. Add the OCR stage using PP-OCRv6_small, plus charset and aspect profiles; verify stacked-plate handling explicitly.
4. Add the backend switch defaulting to `llm`, plus per-stage latency metrics. Deployment is a normal image build; CPU inference needs no host change.
5. Record a side-by-side accuracy and latency comparison on the corpus, including stacked-plate accuracy reported separately, then propose a separate change to flip the default once the numbers justify it.
6. Rollback is setting-only: revert to `llm` and redeploy. No schema change, no migration, no data rewrite, and no per-image escalation path to reason about.

## Open Questions

- **Which permissive detector, and at what settings?** The licensing constraint rules out the fastest option. Candidates are RF-DETR (Apache-2.0, best small/occluded plate performance in the one available benchmark) and RTMDet (Apache-2.0), plus self-training on the corpus. Resolution, confidence threshold, and duplicate-suppression settings are all downstream of this choice and are settled by a bake-off during implementation (tasks 6.1 and 11.7), not in advance — the corpus's 36px 10th-percentile plate height makes the resolution trade-off empirical. **Blocking the detection stage, not the proposal.**
- **Does PP-OCRv6_small reach acceptable plate accuracy, and how does it handle stacked plates?** The published figures are general-document OCR, not plates, and none are two-line-aware. Task 11.8 measures this against the LLM baseline, reporting single-row and stacked plates separately; a poor stacked-plate result would justify row-splitting refinements or, longer term, gathering transcription labels and training a dedicated recognizer.
- **Deployment regions and their charset/aspect profiles.** The corpus is US- and India-heavy; the actual deployment regions are unknown. Profiles must be authored per target region rather than inferred from the training corpus.
- **Does the OCR stage need to read non-registration text?** Many plates carry a state name, district, slogan, or registration sticker. Reading only the registration number is simpler and more accurate; reading all text is a separate detection problem inside the crop.