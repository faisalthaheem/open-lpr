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

## Training configuration

- Input 640x640, not the checkpoint's default 416. A 36px plate letterboxed
  from 480x640 into 416 is ~23px tall; at 640 it is ~45px against a stride-8
  head. This is the single most important setting for small-object recall.
- Multi-scale training enabled (YOLOX `--multiscale_upsizing`). Highest-value
  knob for the small-plate case.
- COCO-pretrained backbone, lower backbone learning rate than the head.
- Mosaic and colour augmentation; the corpus is frame-derived with adjacent-frame
  redundancy.
- Early stopping on validation. Held-out negative/background images retained to
  measure false-positive rate, which is the dominant failure mode on live video.
- Single GPU. At 2351 images the run is minutes; DDP over 2 GPUs adds friction
  for no benefit.

## Unverified

- **No candidate publishes CPU ONNX latency.** The 20-50ms figure for
  YOLOX-Tiny is an estimate. Task 11.7 measures it.
- ROCm training is expected to be straightforward (plain PyTorch, no custom
  CUDA ops) but is **unverified** for this checkpoint on this hardware.
- YOLOX is largely dormant upstream (last README update 2023). It works; we
  would own its maintenance.
- YOLOX ONNX input is raw 0-255 letterboxed, **not** normalised to 0-1, and
  output needs grid/stride decoding. Port from the official
  `demo/ONNXRuntime` rather than reimplementing.

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