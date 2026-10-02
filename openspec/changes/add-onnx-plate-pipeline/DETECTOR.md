# Detector selection: YOLOX, fine-tuned from COCO-pretrained weights

Task 6.1 of `add-onnx-plate-pipeline`. Records the decision, its licensing
basis, and what remains unverified.

## Decision

**YOLOX-Tiny, fine-tuned from the COCO-pretrained `yolox_tiny.pth` checkpoint,
trained at 640x640 with multi-scale augmentation.**

Chosen over RF-DETR-Nano and D-FINE, both of which are also license-safe. The
tie-breaker was CPU latency margin against a 500ms budget combined with
integration cost, not raw accuracy.

## Why not YOLO26 / YOLO11

They are the fastest and most accurate option on paper, and they are excluded.
Ultralytics states that "All Ultralytics YOLO trained models fall under the
AGPL-3.0 License by default... The AGPL-3.0 License covers the training code
and the models produced by that training code", and that this holds even when
training from scratch and regardless of ONNX export.

- Source: https://www.ultralytics.com/license
- Maintainer confirmation on the derivative-work question:
  https://github.com/ultralytics/ultralytics/issues/22458

This project is Apache-2.0. AGPL's network-use clause reaches users
interacting with the application over a network, which a self-hosted web app
plainly triggers. Using these weights would require relicensing the project or
purchasing an Ultralytics Enterprise license.

## Candidates evaluated

| Model | Code license | Weights license | Params | CPU ONNX | Verdict |
|---|---|---|---|---|---|
| **YOLOX-Tiny** | Apache-2.0 | Apache-2.0 (inferred, see caveats) | 5.06M | ~20-50ms expected, unverified | **Selected** |
| YOLOX-S | Apache-2.0 | same | 9.0M | higher | Escalation path if Tiny under-recalls |
| D-FINE-N/S | Apache-2.0 | Apache-2.0 COCO ckpts only | 3.8M / 10.2M | unpublished | Accuracy challenger |
| RF-DETR-Nano | Apache-2.0 | Apache-2.0 (explicit) | 30.5M | ~58-70ms measured | Runner-up |
| RT-DETRv2-R18 | Apache-2.0 | inferred | 20M | unpublished | Superseded by D-FINE |
| RTMDet / MMDetection | Apache-2.0 | inferred | ~4M | unpublished | Rejected: MMCV license exceptions, ROCm friction |
| Purpose-built ALPR checkpoints | mixed | mixed | — | — | Rejected: provenance risk |

## Licensing basis for the selection

**YOLOX code:** Apache-2.0, `LICENSE` at
https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE

**YOLOX weights:** published as GitHub Release assets in the same repository
under that same license, e.g.
https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.pth

**Caveat, stated honestly:** YOLOX makes no explicit sentence licensing the
`.pth` files separately. The conclusion rests on inference from repository-wide
Apache-2.0 licensing rather than a direct upstream grant of the weights. Keep
the citation trail in NOTICE. Prefer the official GitHub Release URLs; the
ModelScope copies are re-hosted by Alibaba under a separate license, and the
"legacy" OneDrive links in the README are of unclear provenance.

**D-FINE boundary, if used as challenger:** upstream states that checkpoints
trained on Objects365 (`*_obj365`, `*_obj2coco`) "may be subject to the
Objects365 dataset terms and should not be assumed to be commercially cleared".
Only the pure-COCO checkpoints may be used.

**RF-DETR boundary, if used:** Nano/Small/Medium are Apache-2.0; **XL and 2XL
are PML 1.0**. Pin the variant in code and assert it.

**MMDetection boundary, if ever used:** MMCV is Apache-2.0 *with exceptions*;
its `LICENSES.md` must be read before commercial use.

## Why training from scratch is not viable

At 2363 regions, training from scratch will not reach acceptable recall. A
two-stage detector (Faster R-CNN, RetinaNet) depends on region-proposal
supervision to bootstrap box regression, and cannot learn a reliable regressor
from 2.3k boxes. Pretraining on COCO supplies exactly what this corpus cannot:
background diversity, negative examples, and box-regression priors. Every
option considered is therefore a pretrained-backbone fine-tune.

## Corpus findings that affect training

These were measured on the annotated corpus and change how the split must be
built:

- **The corpus is frame-extracted video.** All 2351 train images are named by
  consecutive integers; 100% of them sit within 3 of their numeric neighbour.
- **The published split leaks.** Comparing downscaled perceptual hashes, 10
  train images match an image in `val`. A random split will leak far more than
  this, because adjacent frames are near-identical.
- **Splitting must group by frame adjacency**, not by image. See task 10.8.
- **Duplicate images exist within train:** 35 exact-duplicate groups covering
  72 files.
- **Plate size is small:** median plate height 61px, 10th percentile 36px.
  Resolution and recall must therefore be reported bucketed by plate height,
  since a single mAP figure hides the case being optimised.

## Measured results

Trained to completion (100 epochs, ~37 min on one RX 7900 XTX under ROCm) and
evaluated by `lpr_app/ml/benchmark.py` on the full 480-image validation split,
CPU only, ONNX Runtime. Reproduce with:

```
python -m lpr_app.ml.benchmark --data <dataset> \
    --model model/plate/plate_yolox_tiny_640.onnx --split val2017
```

| Metric | Value |
|---|---|
| COCO AP / AR (best) | 83.02 / 85.81 |
| Latency mean | **21.7 ms** (median 20.8, p95 29.7, max 49.2) |
| Budget | 500 ms — **23x headroom** |
| Recall @ IoU 0.3 | **0.998** |
| Precision | 0.970 |
| False positives per image | 0.031 |
| Model size | 20.2 MB |

Recall by plate height, the case that limits this project:

| Plate height | Recall | Count |
|---|---|---|
| < 40 px | **1.000** | 57 |
| 40-60 px | 0.988 | 86 |
| 60-100 px | 1.000 | 255 |
| >= 100 px | 1.000 | 89 |

Confidence threshold sweep at 640px:

| Threshold | Recall | Precision | FP/image | Mean latency |
|---|---|---|---|---|
| 0.3 | 0.9979 | 0.9701 | 0.031 | 22.2 ms |
| **0.5** | **0.9979** | **0.9759** | **0.025** | 22.8 ms |
| 0.7 | 0.9918 | 0.9817 | 0.019 | 23.0 ms |

**0.5 is frozen into configuration**: it holds recall identical to 0.3 while
cutting false positives by a fifth. 0.7 buys little extra precision and starts
costing recall.

These figures supersede the estimates above, which were stated as unverified.
The original expectation was 20-50 ms and adequate small-object recall; both
held, and the 640px input choice is what makes the under-40px bucket work. A
416px input would put those plates at ~23px against a stride-8 head.

### Split integrity

The reported numbers come from the frame-grouped split with a deliberate gap, not
the corpus's published split:

- Zero perceptual-hash overlap between train and validation.
- Minimum frame distance of 51 between any training and validation frame.
- 1789 train / 480 validation images, 1806 / 487 plate annotations.

The published split leaks 10 images directly, and a random split leaks far more
through adjacent near-identical frames, so metrics computed on it would be
inflated.

## OCR: PP-OCRv5 mobile, adopted not trained

The corpus carries **no transcription labels**, so a recogniser cannot be trained
here. PP-OCRv5_mobile_rec is adopted and converted to ONNX with `paddle2onnx`;
it is Apache-2.0 and ships a 18383-entry character dictionary.

The design originally named PP-OCRv6_small. v6 was unavailable from this network
(Hugging Face returned 401 for the RapidAI and PaddlePaddle repos), so v5 mobile
was used instead. v6 is expected to be somewhat more accurate; the stage is
artifact-agnostic, so swapping it in is a configuration change.

Measured on 120 validation plates read as single lines: **median confidence
0.80, 1% empty results**, with reads such as `EG209`, `QG260`, `SE428`, `ADT140`.
Separators are stripped by the charset profile.

### What measuring OCR revealed, and the design change it forced

Row splitting for stacked plates was specified in this change and is implemented,
but it is **off by default**, because measuring it showed the premise was wrong.

Inspection of the corpus found three distinct plate shapes, not two:

- genuinely stacked two-line, e.g. `VA9/2229`, `L802 WGK`, `MN f1 / 5730`
- single-line US/EU, e.g. `SV07UVG`, `KRR 2583`
- **single-line with a caption** underneath, e.g. `QG.260` with `ISLAMABAD`
  beneath it, at aspect ratio 1.88

The captioned plates overlap the stacked ones on every geometric signal
available: aspect ratio (both span 1.4-2.4), presence of an ink gap (both have
one), and row-height balance (both split unevenly). A splitter therefore reads
the caption as a second line, and observed results like `QG260ISLAMABAD` and
`ICTSE428` rather than `QG260` and `SE428`.

Confidence cannot arbitrate either: the split read scored *higher* confidence
(0.85 versus 0.79) while being wrong, because splitting a clean single line
gives the recogniser an easier input.

So the honest position is that this is not solvable by geometry on this corpus,
and `split_two_rows` defaults to off. `split_stacked=True` enables it for
regions whose plates are known to be uniformly stacked. Resolving it properly
needs a layout classifier trained on captioned examples, which the corpus does
not provide. This is recorded rather than papered over, because a test asserting
"stacked plates are recognised as two rows" would pass on synthetic fixtures
while doing nothing for the real ones.

### A bug measurement caught here too

The recogniser's CTC head emits **already-normalised probabilities** (the ONNX
graph contains the Softmax). Applying softmax again pushed every value toward
uniform and drove confidence to exactly 0.00 on every plate. `_as_probabilities`
now detects the normalised case and leaves it alone.

The same class of error as the detector's double `exp()`: an assumption taken
from framework semantics rather than from what the artifact actually emits.
Both were only caught by running the real model.

## Training configuration

As trained, in `training/exp_plate_tiny.py`:

- Input 640x640, not the checkpoint default of 416. Measured effect: the
  under-40px bucket reaches recall 1.000. At 416 those plates would be ~23px
  against a stride-8 head.
- Multi-scale training on (`multiscale_upsizing`), plus mixup and mosaic.
- COCO-pretrained backbone (yolox_tiny.pth), 100 epochs, batch 16, lr 0.01 with
  cosine decay, warmup 5 epochs, AdamW, weight decay 5e-4.
- fp32 rather than fp16: this ROCm build is unstable in long fp16 chains and a
  model this small gains nothing from it on a CPU deployment target.
- Single GPU. At this dataset size the run is ~37 minutes; DDP over 2 GPUs adds
  friction for no benefit.

The corpus contains no negative or background images (every record has a plate),
so false-positive rate is measured on plates plus whatever non-plate regions the
detector fires on: 0.031 per image at threshold 0.5. A held-out set of genuinely
negative frames would be worth adding, since false positives are the dominant
operational failure mode on live video and this corpus cannot measure it
properly.

## Unverified

- ROCm training is confirmed working: torch 2.5.1+rocm6.2 on an RX 7900 XTX
  (gfx1100) trains this checkpoint in ~37 minutes for 100 epochs. One caveat
  found in practice: YOLOX's own `setup.py` pins `onnx-simplifier==0.4.10`,
  whose `pinocchio` build fails to compile. Removing that requirement is
  sufficient for training; ONNX export needs only `torch` and `onnx`.
- YOLOX is largely dormant upstream (last README update 2023). It works; we
  would own its maintenance.
- Long chained fp16 matmuls on this ROCm build overflow to NaN. Training runs in
  fp32, which costs nothing meaningful for a model this small. Normalised fp16,
  bf16, and fp32 chains are all stable, so this is arithmetic overflow rather
  than a driver fault.

## A bug this measurement caught

The decoder originally exponentiated the regressed width and height. That is
correct for YOLOX's raw PyTorch output but wrong for the ONNX export, which
applies `exp()` inside the graph. Exponentiating twice inflated every box until
it clamped to the whole image:

```
predicted: 0, 0, 1280, 960   (the entire image)
truth:     516, 403, 208, 109
```

Synthetic test fixtures had been written to match the decoder rather than the
export, so they agreed with each other and passed. Only running the real
artifact exposed it. Worth recording because it is the failure mode unit tests
invite when the fixture is derived from the implementation instead of from the
thing being integrated.

## Sources

- YOLOX license: https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE
- YOLOX weights: https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.pth
- YOLOX custom-data training: https://github.com/Megvii-BaseDetection/YOLOX/blob/main/docs/train_custom_data.md
- YOLOX training image size: https://github.com/Megvii-BaseDetection/YOLOX/blob/main/docs/manipulate_training_image_size.md
- YOLOX model zoo: https://github.com/Megvii-BaseDetection/YOLOX/blob/main/docs/model_zoo.md
- YOLOX ONNXRuntime demo: https://github.com/Megvii-BaseDetection/YOLOX/tree/main/demo/ONNXRuntime
- Ultralytics license: https://www.ultralytics.com/license
- D-FINE license note: https://github.com/Peterande/D-FINE
- RF-DETR license: https://github.com/roboflow/rf-detr#license
- RF-DETR CPU ONNX measurements: https://github.com/imessam/RF-DETR-ONNX