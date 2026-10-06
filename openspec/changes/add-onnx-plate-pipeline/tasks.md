## 1. Package scaffolding and dependency split

- [x] 1.1 Create `lpr_app/pipeline/` with `__init__.py`, `stages/__init__.py`, and `runtime/__init__.py`.
- [x] 1.2 Create `lpr_app/ml/` with `__init__.py`, `datasets/`, and `requirements-train.txt` holding the training-only dependencies (torch, torchvision, OCR data pipeline) so the runtime requirements never need them.
- [x] 1.3 Add `onnxruntime` at a pinned exact version to the runtime requirements.
- [x] 1.4 Document the ROCm and CUDA install variants of `onnxruntime` as alternatives in `AGENTS.md`, noting they are install-time choices and no code branches on the provider.
- [x] 1.5 Verify the web application starts and image processing runs with no training dependency installed, confirming the dependency split holds.

## 2. Stage contract

- [x] 2.1 Implement the stage base class declaring name, required input fields, output fields, and optional model path.
- [x] 2.2 Implement lazy model loading: load on first execution, cache the session, never load when the stage is skipped.
- [x] 2.3 Implement shape and output-name validation against the loaded artifact's declared signature, failing with a message naming expected versus actual.
- [x] 2.4 Implement the missing-artifact error path that names the stage and resolved path, with no silent substitution of another model.
- [x] 2.5 Write unit tests for contract declaration, lazy load-once, skip-does-not-load, missing artifact, and input shape mismatch.
- [x] 2.6 Confirm the tests fail before the implementation exists and pass after.

## 3. ONNX runtime wrapper

- [x] 3.1 Implement a session wrapper that constructs an inference session for a requested provider from `cpu`, `cuda`, or `rocm`.
- [x] 3.2 Default to the CPU provider when no provider is requested.
- [x] 3.3 Detect provider unavailability, fall back to CPU, and log the substitution without failing the pipeline.
- [x] 3.4 Expose per-execution timing so call sites can record stage duration.
- [x] 3.5 Write tests covering CPU default, explicit provider selection, and the fallback-with-log path, using a trivially small model artifact.

## 4. Graph runtime

- [x] 4.1 Implement graph construction from configuration: nodes declaring stage class and model path, edges declaring input bindings by field name.
- [x] 4.2 Validate bindings at construction, raising an error naming the node and the unsatisfied input field before any stage loads.
- [x] 4.3 Detect cycles at construction and raise an error identifying the participating nodes.
- [x] 4.4 Implement dependency-ordered execution over the validated graph.
- [x] 4.5 Skip a stage whose required input field is absent or null, recording the skip reason rather than raising.
- [x] 4.6 Implement conditional execution on upstream output, including confidence thresholds, recording the skip reason when unmet.
- [x] 4.7 Contain stage failures: record the failing stage name and reason, preserve outputs of stages that succeeded, and skip only the stages that depend on the failed output.
- [x] 4.8 Implement concurrent execution of independent stages, guarded so each stage uses its own session instance.
- [x] 4.9 Add a setting to disable concurrency and execute independent stages sequentially in a deterministic order.
- [x] 4.10 Write tests for topological order, unsatisfied binding, cycle rejection, skip on absent input, conditional skip, failure containment, dependent-skip cascade, and concurrent-versus-sequential equivalence of results.

## 5. Plate rectification stage

- [x] 5.1 Implement a non-model stage that maps a detected plate region to a configured aspect ratio via perspective transform at a configured output width and height.
- [x] 5.2 Make the canonical aspect ratio configurable per layout rather than a single global constant.
- [x] 5.3 Support rectification from an axis-aligned bounding region alone, deriving corners when explicit corner geometry is absent.
- [x] 5.4 Use explicit corner geometry for rectification when the detection supplies it, in preference to the bounding region's corners.
- [x] 5.5 Confirm the stage declares no model artifact and loads no session.
- [x] 5.6 Reject self-intersecting corner geometry, reporting rectification as failed.
- [x] 5.7 Reject regions below the configured minimum area, reporting rectification as failed.
- [x] 5.8 Make failed rectification yield no recognition input, causing the recognition stage to skip for that detection with no recognized text recorded.
- [x] 5.9 Add the bypass configuration path deriving the crop from the detection's bounding region with no transform.
- [x] 5.10 Write tests for skew correction, per-layout aspect ratio enforcement, exact output dimensions, box-only input, explicit-corner preference, each degenerate case, and the bypass path.

## 6. Local detection stage

- [x] 6.1 Select a detector whose license is compatible with this project's Apache-2.0 license, explicitly excluding AGPL-3.0 weights including the Ultralytics YOLO families. Evaluate RF-DETR and RTMDet, and weigh self-training on the corpus as a way to avoid third-party weights entirely. Record the decision and the license identifier.
- [x] 6.2 Implement a detection stage running the selected ONNX detector, producing a plate region plus confidence per detection.
- [x] 6.3 Treat a stacked two-line plate as one detection covering both rows rather than one per row, and verify this on corpus examples.
- [x] 6.4 Implement aspect-ratio-preserving resize of the detection input.
- [x] 6.5 Scale returned coordinates back to the original image coordinate space.
- [x] 6.6 Clamp scaled coordinates to the original image bounds.
- [x] 6.7 Apply the configured confidence threshold, discarding lower-confidence detections.
- [x] 6.8 Implement duplicate suppression to collapse substantially overlapping detections, keeping the higher-confidence detection.
- [x] 6.9 Record the detector's upstream identity and license in the model manifest.
- [x] 6.10 Write tests for single and multiple detections, a stacked two-line plate counted as one detection, the empty result, coordinate round-tripping through a resize, clamping, thresholding, and duplicate suppression.

## 7. Local OCR stage

- [x] 7.1 Implement a recognition stage running the PP-OCRv6_small ONNX recognizer on a rectified crop, returning text plus confidence.
- [x] 7.2 Return an empty text result rather than fabricating characters for an illegible crop.
- [x] 7.3 Implement stacked two-line handling: identify a stacked plate, split the crop into its two rows before recognition, and combine the rows with order preserved.
- [x] 7.4 Ensure a single-row crop is not split and that attempted row splitting does not introduce spurious characters into a one-row result.
- [x] 7.5 Implement a charset profile restricting emitted tokens to its members, applied at decode time, selectable at runtime without code changes.
- [x] 7.6 Default the charset profile to alphanumerics, and make region-specific profiles configurable.
- [x] 7.7 Route recognized text through the existing `DetectionValidator` text validation and discard implausible results.
- [x] 7.8 Record validated text and confidence against the corresponding entry in the detections collection.
- [x] 7.9 Ensure exactly one recognizer invocation per detected plate, treating the two rows of a stacked plate as one plate, batching across multiple invocations when the plate count exceeds the configured batch size.
- [x] 7.10 Write tests for clean-crop recognition, confidence reporting, illegible crop, two-line row splitting, single-row non-splitting, split-without-spurious-characters, out-of-charset suppression, profile selection and default, validation rejection, and the once-per-plate plus batch-bound behavior.

## 8. Backend switch

- [x] 8.1 Add settings selecting the detection and OCR backend, defaulting to the existing LLM backend.
- [x] 8.2 Add the local pipeline execution path to `image_processing_service.py`, selected by the setting, leaving the LLM flow intact.
- [x] 8.3 Populate the identical detections collection shape from both backends so no caller or API branch depends on which ran.
- [x] 8.4 Confirm the LLM backend path is byte-for-byte unchanged in behavior, including the existing fixed-pixel crop padding.
- [x] 8.5 Write tests asserting the default selects the LLM backend and that the override selects the local pipeline.
- [x] 8.6 Document the new settings in `.env.example` and `AGENTS.md`, including that switching back is a configuration-only rollback.

## 9. Latency instrumentation

- [x] 9.1 Record a duration for every executed stage, distinguishing success, skip, and failure.
- [x] 9.2 Record end-to-end pipeline duration per image.
- [x] 9.3 Compare each measurement against a configurable budget, defaulting the end-to-end budget to 0.5 seconds.
- [x] 9.4 Export per-stage durations as a histogram on the existing Prometheus registry with a stage label and an outcome label.
- [x] 9.5 Confirm the existing overall processing duration metric is still recorded when the local backend runs, keeping backends comparable on one metric.
- [x] 9.6 Write tests for budget comparison, the 0.5s default, per-stage and outcome labelling, and continued recording of the existing metric.

## 10. Dataset tooling

- [x] 10.1 Inspect all annotation databases in the corpus, including `train_and_val.db` alongside `train.db` and `val.db`, and report which exist and which the tooling uses, so the authoritative split is not assumed.
- [x] 10.2 Implement annotation loading, parsing file name, image dimensions, and the per-image region list into samples pairing an image with its plate region and label.
- [x] 10.3 Resolve each annotation's file name to an image under the corpus image directory.
- [x] 10.4 Emit region boxes in full-size image pixel coordinates.
- [x] 10.5 Support axis-aligned box regions as the corpus geometry, and do not require corner or polygon annotations that the corpus does not contain.
- [x] 10.6 Exclude records with no region or marked deleted, background, or unreviewed, counting them as skipped.
- [x] 10.7 Report missing image files by name and count rather than discarding silently.
- [x] 10.8 Implement a seeded, configurable train/validation split, asserting the partitions do not intersect.
- [x] 10.9 Resolve the corpus path from an environment variable with a documented default, printing the resolved path.
- [x] 10.10 Exit with a clear error naming the resolved path and expectations when the corpus is missing.
- [x] 10.11 Write tests for annotation parsing, coordinate space, axis-aligned region handling, skip categories, missing-image reporting, multi-database reporting, and split determinism and disjointness, using a small fixture corpus.

## 11. Training, export, and benchmark

- [x] 11.1 Implement detector training against the loaded corpus, in the training-only subpackage, runnable without Django settings.
- [x] 11.2 Export the trained or adopted detector to ONNX and record a manifest entry with filename, checksum, upstream identity, and license.
- [x] 11.3 Adopt the PP-OCRv6_small recognizer, export it to ONNX, and record its manifest entry with the upstream checkpoint identity and license.
- [x] 11.4 Confirm model artifacts land under the already-ignored model path while the manifest stays reviewable.
- [x] 11.5 Implement the benchmark, excluding first-run model loading from per-stage figures, reporting per-stage and end-to-end durations and the image count.
- [x] 11.6 Make the benchmark exit non-zero when measured end-to-end latency exceeds the budget.
- [x] 11.7 Sweep detection input resolution, confidence threshold, and duplicate-suppression settings against the corpus, recording recall and latency, and freeze the chosen values into configuration. Pay particular attention to small plates: the corpus median plate height is 61px with a 36px 10th percentile, so a resolution that loses those destroys recall.
- [x] 11.8 Measure the local pipeline against the corpus on CPU, reporting recognition accuracy separately for single-row and stacked two-line plates.
- [x] 11.9 Run a side-by-side accuracy and latency comparison of local versus LLM backend over the corpus and record the numbers.
- [x] 11.10 Keep the default backend as the LLM until the comparison justifies a switch, and open a follow-up change proposing the flip with the measured numbers attached.

## 12. Verification

- [x] 12.1 Run `ruff check` and `ruff format`, fixing all violations in the new code.
- [x] 12.2 Confirm `ruff format` reports no changes on a second run.
- [x] 12.3 Run the full test suite and confirm coverage over `lpr_app` does not regress below the established ratchet.
- [x] 12.4 Confirm the application starts and processes an image correctly with the default LLM backend.
- [x] 12.5 Confirm the application starts and processes an image correctly with the local backend selected.
- [x] 12.6 Confirm the detections output shape is identical across backends.
- [x] 12.7 Update `AGENTS.md` with the pipeline architecture, stage contract, configuration keys, and the training workflow.
- [x] 12.8 Update the changelog.

## 13. Release documentation sweep

Documentation was updated as each piece landed, which leaves it describing
several states of the project at once. This section is the single pass that
reconciles the docs against the change as shipped. It runs last, after the
trained model is promoted, because the numbers it has to record are the
measured ones and not the pilot's.

Deliberately last, and deliberately a checklist rather than work done
alongside: every item below is a place where a reader would otherwise find a
claim that was true when written and is not true now.

The training imagery is deliberately **not** published. The ~5,000
community-contributed images are photographs taken by users of a live
deployment: they contain real plates, and as whole scenes rather than crops,
very likely faces and vehicles. Filenames preserve upload-time device and
timestamp strings. Nobody consented, and a transcription beside an image is a
searchable index of real registration numbers. The reusable contribution is the
tooling in `lpr_app/ml/`, which is already public and needs none of that data
to be useful.

### Accuracy numbers

- [ ] 13.1 Replace the 20-plate pilot figures (CER 0.367, exact-match 0.35) in `AGENTS.md` and `CHANGELOG.md` with the measured figures from the trained-model evaluation, and record the sample size the new numbers rest on. A number without its sample size is not evidence.
- [ ] 13.2 Update `docs/RELEASE_NOTES_*` or add a release note for the flip, stating what a deployment must do to obtain `model/plate/` and what happens if it does not. This is the one breaking operational change in this work: a deployment that upgrades without the artifacts cannot process images.
- [ ] 13.3 State the rollback path (`PIPELINE_BACKEND=llm`) in the release note, since it is configuration-only and a reader deciding whether to upgrade needs it before upgrading.
- [ ] 13.4 Correct any claim that coverage equals accuracy. The local backend reads more plates than the LLM backend and gets fewer of them right; several current sentences put those two facts next to each other in a way that reads as the first implying the second.

### Docs and layout

- [ ] 13.5 Verify every relative markdown link resolves, since the topic guides moved to `docs/` during this change and links were rewritten in bulk.
- [ ] 13.6 Confirm the `README.md` file-structure tree matches the actual root layout.
- [ ] 13.7 Confirm no document still describes the LLM backend as the default, or the local backend as opt-in.
- [ ] 13.8 Confirm `.env.example` and `.env.llamacpp.example` carry every pipeline key, with the same defaults as `AGENTS.md`. Three lists of the same keys drift unless they are compared deliberately.

### Tooling names

- [ ] 13.9 Confirm every reference to the renamed dataset exporter points at `lpr_app.ml.datasets.imanno_to_coco`, not the old module name.
- [ ] 13.10 Confirm no document describes the exporter as producing ONNX. It produces COCO JSON; the `.pth` and `.onnx` steps are separate and belong to the trainer and `export_onnx.py`.

### Artifact distribution

`PIPELINE_BACKEND` defaults to `local`, which requires model artifacts at
runtime that cannot be committed (`model/*` is gitignored). Without a
distribution mechanism a fresh deployment cannot start. Deferred until the
trained model is measured, so the decision reflects the final artifact's size
and the code that consumes it.

- [ ] 13.11 Publish **all three** artifacts -- detector, OCR recogniser, and OCR dictionary -- not the detector alone. `docker-entrypoint.sh` exits non-zero if any of the three is missing, so publishing one relocates the failure rather than removing it.
- [ ] 13.12 Publish **both** the exported ONNX and the training checkpoint (`best_ckpt.pth`). They serve different audiences and neither replaces the other: the ONNX is what the app loads with `onnxruntime` alone, the checkpoint is what lets someone continue the training instead of restarting from COCO. Publishing only the ONNX forfeits the only reusable artifact for anyone extending this.
- [ ] 13.13 Record for each artifact which one you trained and which you adopted upstream. Only the detector is trained here; the recogniser is pre-trained PP-OCR exported to ONNX. Without this the published checkpoint implies the whole pipeline is yours, which would misattribute PaddleOCR's work and misdescribe where to file a bug.
- [ ] 13.14 Write the model card at the repository root as `README.md` with YAML frontmatter (`license: apache-2.0`). HF renders only a root `README.md` as the card, and an undeclared licence shows no badge -- the first thing a reviewer looks for.
- [ ] 13.15 State in the card that loading the checkpoint requires torch and YOLOX but **not** ROCm; CPU torch reads a checkpoint fine and ROCm is only needed to train. Also note that a `.pth` is a pickle and executes constructors on load.
- [ ] 13.16 Record the measured accuracy and its sample size in the card. Not the 20-plate pilot: a reader deciding whether to trust the weights is entitled to the number the shipped model actually produced.
- [ ] 13.17 State that the training imagery is not published and why -- user-contributed photographs containing real plates, faces, and vehicles, with no consent obtained. Say what *is* published instead, so the absence reads as a decision rather than an oversight.

### Model repository layout

`onnx/` and `checkpoints/` are separated so a user who only wants to run
inference does not download training state, and a user fine-tuning is not left
to guess which ONNX file to load.

- [ ] 13.18 Use `README.md` (model card), `manifest.json`, `onnx/`, and `checkpoints/`.
- [ ] 13.19 Carry the existing `manifest.json` into the repository unchanged in structure. It already records `sha256`, `checkpoint_sha256`, `license`, `upstream`, `exported_with`, and `input_size`; it was written for this.
- [ ] 13.20 Pin by HF **commit SHA**, never by `main`. A `main` pointer moves on retrain, so a deployment would silently pull different weights than it was tested against. The SHA is content-addressed and is the one capability that makes the artifact reproducible.

### Consumption

- [ ] 13.21 Download with the standard library, not `huggingface_hub`. One HTTP GET with resume and retry does not justify a client library in the production image, and pinning a commit SHA is plain URL construction. Keep `huggingface_hub` in the training environment only, for publishing.
- [ ] 13.22 Verify every downloaded artifact against the `sha256` in `manifest.json` and fail startup on mismatch. Hosted files can be replaced; a plain fetch cannot tell.
- [ ] 13.23 Make the publish step reproducible: a script that uploads the files and regenerates `manifest.json` from the files actually uploaded, so checksums cannot drift from artifacts.
- [ ] 13.24 Keep the existing "artifacts missing, mount them or set `PIPELINE_BACKEND=llm`" failure as the offline path, and make the error say so.
- [ ] 13.25 Have CI verify the pinned model revision resolves, so a deleted or renamed repository fails the build rather than a deployment.

### Close out

- [ ] 13.26 Archive this change, and confirm the archived specs no longer contradict the shipped implementation.
- [ ] 13.27 Verify the change's own `tasks.md` has no unchecked box, so the archive does not claim completeness it does not have.