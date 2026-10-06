#!/usr/bin/env python3
"""Standalone evaluator: run candidate models against images and compare them.

The question this answers is "is this checkpoint better than the one we ship?",
which `benchmark.py` answers in aggregate over a labelled split and
`compare_backends.py` answers across backends. Neither is any use when the
question is about a handful of specific images -- a validation set of twenty, a
plate someone reported, the corner cases that only show up when you look.

**This lives in `lpr_app/ml/` rather than the training root.** It is code, not
state: it is versioned, reviewable, and reuses `LocalPlateBackend` and
`BoundingBoxVisualizer` directly. The training root holds the artifacts this
reads. Streamlit is an optional extra in `requirements-eval.txt`, kept out of
both `requirements.txt` (which must never pull torch) and
`requirements-train.txt` (which does not need a UI).

Everything above `main()` is importable without Streamlit installed, so the
model-discovery and evaluation logic is unit-testable in CI. Streamlit is
imported inside `main()` for that reason -- see the import at the bottom.

**It reads ONNX artifacts, not `.pth` checkpoints.** ONNX Runtime cannot load a
PyTorch checkpoint, and silently offering a model that cannot run would be worse
than saying so: `discover_models` reports checkpoints as needing an export rather
than listing them alongside runnable ones.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Manifest fields worth surfacing in the UI. Everything else in a manifest is
# provenance for a human reading the JSON, not something to render in a table.
MANIFEST_DISPLAY_FIELDS = (
    "trained_on",
    "upstream",
    "license",
    "exported_with",
    "input_size",
    "checkpoint_sha256",
    "sha256",
)


@dataclass
class ModelCandidate:
    """One artifact under evaluation.

    `runnable` distinguishes an ONNX graph from a PyTorch checkpoint. Both are
    discovered, because a run directory holds both and the distinction is the
    first thing anyone looking at that directory needs explained to them.
    """

    path: Path
    kind: str  # "onnx" | "checkpoint"
    promoted: bool
    manifest: dict = field(default_factory=dict)

    @property
    def runnable(self) -> bool:
        return self.kind == "onnx" and self.path.is_file()

    @property
    def label(self) -> str:
        # Promoted first, then by path depth, so the model we actually ship is
        # the default selection rather than whichever one sorted first.
        return f"{'★ ' if self.promoted else ''}{self.path.name}"

    @property
    def detail(self) -> str:
        if not self.runnable:
            return "PyTorch checkpoint - export to ONNX before evaluating"
        provenance = self.manifest.get("trained_on")
        return f"{self.path.parent.name} | {provenance}" if provenance else str(self.path.parent)

    @property
    def group(self) -> str:
        return "Promoted" if self.promoted else "Candidates"


def load_manifest(model_path: Path) -> dict:
    """Read a sibling `.manifest.json` if one exists.

    Best-effort: a manifest is provenance, not a requirement for running a
    model. A missing or malformed one returns empty rather than raising, so an
    exported-but-not-yet-documented artifact is still evaluable.
    """
    manifest_path = model_path.with_suffix(model_path.suffix + ".manifest.json")
    if not manifest_path.is_file():
        alternate = model_path.with_suffix(".manifest.json")
        if alternate.is_file():
            manifest_path = alternate
        else:
            return {}

    try:
        data = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

    # Accept both the flat schema and the repo's filename-keyed variant.
    if isinstance(data, dict):
        if model_path.name in data and isinstance(data[model_path.name], dict):
            return data[model_path.name]
        if all(isinstance(value, dict) for value in data.values()) and data:
            return data
    return data if isinstance(data, dict) else {}


def discover_models(training_root: str | Path) -> list[ModelCandidate]:
    """Find every artifact under a training root.

    Promoted models come from `models/`; candidates from each run's `exported/`
    directory. Checkpoints are discovered too, and reported as not runnable,
    so that the runs directory is fully accounted for in the UI instead of
    appearing to contain fewer models than it does.
    """
    root = Path(training_root)
    if not root.is_dir():
        return []

    found: list[ModelCandidate] = []

    promoted_dir = root / "models"
    for path in sorted(promoted_dir.rglob("*.onnx")) if promoted_dir.is_dir() else []:
        found.append(ModelCandidate(path, "onnx", promoted=True, manifest=load_manifest(path)))

    for path in sorted((root / "runs").rglob("*.pth")) if (root / "runs").is_dir() else []:
        found.append(ModelCandidate(path, "checkpoint", promoted=False))
    for path in sorted((root / "runs").rglob("*.onnx")) if (root / "runs").is_dir() else []:
        found.append(ModelCandidate(path, "onnx", promoted=False, manifest=load_manifest(path)))

    # Promoted first, then alphabetically within each tier, so the shipped model
    # is the default and two runs of the same name do not swap places.
    return sorted(found, key=lambda candidate: (not candidate.promoted, str(candidate.path)))


def build_backend(
    detector_model: str | Path,
    ocr_model: str | Path | None = None,
    ocr_dict: str | Path | None = None,
    provider: str = "cpu",
    detector_conf_threshold: float = 0.3,
):
    """Construct a backend pointed at a specific artifact.

    Built directly rather than through `build_local_backend_from_settings`,
    because settings resolve `PIPELINE_MODEL_DIR` and this tool's whole purpose
    is to run a model that is *not* the configured default. Mutating settings to
    evaluate one model would leak into anything else running in the process --
    which in a Streamlit session means the next upload.
    """
    from django.conf import settings

    from lpr_app.pipeline.local_backend import LocalPlateBackend
    from lpr_app.services.detection_validator import DetectionValidator

    def resolve(candidate, fallback_setting):
        if candidate:
            return str(candidate)
        return os.path.join(settings.PIPELINE_MODEL_DIR, fallback_setting)

    return LocalPlateBackend(
        detector_model=str(detector_model),
        detector_input_size=tuple(settings.PIPELINE_DETECTOR_INPUT_SIZE),
        detector_conf_threshold=detector_conf_threshold,
        detector_nms_iou=settings.PIPELINE_DETECTOR_NMS_IOU,
        layout_threshold=settings.PIPELINE_LAYOUT_THRESHOLD,
        ocr_model=resolve(ocr_model, settings.PIPELINE_OCR_MODEL),
        ocr_dict=resolve(ocr_dict, settings.PIPELINE_OCR_DICT),
        ocr_batch_size=settings.PIPELINE_OCR_BATCH_SIZE,
        ocr_charset_profile=settings.PIPELINE_OCR_CHARSET_PROFILE,
        ocr_split_stacked=settings.PIPELINE_OCR_SPLIT_STACKED,
        rectify_enabled=settings.PIPELINE_RECTIFY_ENABLED,
        provider=provider,
        crop_padding_px=settings.OCR_CROP_PADDING_PX,
        validator=DetectionValidator(
            min_confidence=settings.DETECTION_MIN_CONFIDENCE,
            min_box_area_fraction=settings.DETECTION_MIN_BOX_AREA_FRACTION,
            max_box_area_fraction=settings.DETECTION_MAX_BOX_AREA_FRACTION,
            min_plate_aspect=settings.DETECTION_MIN_PLATE_ASPECT,
            max_plate_aspect=settings.DETECTION_MAX_PLATE_ASPECT,
        ),
    )


def evaluate_image(backend, image_path: str | Path) -> dict:
    """Run one image through a backend and return renderable results plus timing.

    Returns the same `{"detections": [...]}` shape both production backends emit,
    so `BoundingBoxVisualizer` consumes it unchanged and nothing here needs to
    know which backend produced it.
    """
    from PIL import Image

    path = Path(image_path)
    with Image.open(path) as opened:
        image = opened.convert("RGB")

    started = time.perf_counter()
    result = backend.run(image)
    elapsed_ms = (time.perf_counter() - started) * 1000

    return {
        "image": path.name,
        "path": str(path),
        "detections": result.detections,
        "latency_ms": round(elapsed_ms, 1),
        "plates": len(result.detections),
        "reads": sum(1 for detection in result.detections if detection.get("ocr")),
    }


def render(image_path: str | Path, lpr_data: dict):
    """Draw detections and reads onto the image, returning a PIL image."""
    from lpr_app.services.bbox_visualizer import BoundingBoxVisualizer

    visualizer = BoundingBoxVisualizer(str(image_path))
    visualizer.visualize_lpr_results(lpr_data)
    return visualizer.image


def summarise(results: list[dict]) -> dict:
    """Aggregate per-image results into the numbers a comparison needs.

    Reads-as-written is reported next to exact agreement between models, because
    a model can score well on one by declining to read. Detection count and mean
    latency complete it.
    """
    if not results:
        return {"images": 0, "plates": 0, "reads": 0, "mean_latency_ms": None, "reads_per_plate": None}

    plates = sum(result["plates"] for result in results)
    reads = sum(result["reads"] for result in results)
    return {
        "images": len(results),
        "plates": plates,
        "reads": reads,
        "mean_latency_ms": round(statistics.fmean(result["latency_ms"] for result in results), 1),
        "reads_per_plate": round(reads / plates, 4) if plates else None,
    }


def compare_reads(per_model: dict[str, list[dict]]) -> dict[str, dict]:
    """Report, per image, what each model read.

    This is the comparison the tool exists for. Two models agreeing on 19 of 20
    plates is a different finding from one of them reading 20 plates confidently
    and wrongly, and aggregate plate counts cannot distinguish those.
    """
    by_image: dict[str, dict[str, list[str]]] = {}
    for model_name, results in per_model.items():
        for result in results:
            key = Path(result["path"]).name
            entry = by_image.setdefault(key, {})
            entry[model_name] = [
                detection["ocr"][0]["text"] if detection.get("ocr") else "" for detection in result["detections"]
            ]

    return {
        image: {
            "reads": reads,
            "agreement": len({tuple(values) for values in reads.values()}) == 1,
        }
        for image, reads in sorted(by_image.items())
    }


def collect_images(source: str | Path, limit: int = 50) -> list[Path]:
    """List images from a file or a directory.

    Directory walks are sorted and capped so a multi-thousand-image training
    directory does not stall the UI trying to render all of it.
    """
    path = Path(source)
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []

    found = [
        candidate
        for candidate in sorted(path.rglob("*"))
        if candidate.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    ]
    return found[:limit]


def main(argv=None) -> int:  # pragma: no cover - UI entry point
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description="Evaluate candidate plate models against images.")
    parser.add_argument("--training-root", required=True, help="plate-training/ directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument(
        "--images",
        default=None,
        help="image file or directory; ignored when running the UI, which selects interactively",
    )
    args = parser.parse_args(argv)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lpr_project.settings")
    import django

    django.setup()

    root = Path(args.training_root)
    candidates = discover_models(root)
    runnable = [candidate for candidate in candidates if candidate.runnable]

    # Headless mode, so the tool is useful in a script and testable without a
    # browser: evaluate every runnable model against the images and print a table.
    if args.images:
        images = collect_images(args.images)
        if not runnable or not images:
            print(
                json.dumps(
                    {
                        "error": "no runnable models or no images",
                        "models_found": len(candidates),
                        "runnable": len(runnable),
                        "images": len(images),
                        "hint": "export a checkpoint to ONNX first: python -m lpr_app.ml.export_onnx ...",
                    },
                    indent=2,
                )
            )
            return 2 if not runnable else 1

        report: dict[str, list[dict]] = {}
        for candidate in runnable:
            backend = build_backend(candidate.path)
            backend.warm_up()
            report[candidate.label] = [evaluate_image(backend, image) for image in images]

        print(
            json.dumps(
                {
                    "summaries": {name: summarise(results) for name, results in report.items()},
                    "per_image": compare_reads(report),
                },
                indent=2,
            )
        )
        return 0

    _serve_ui(root, candidates, runnable, args.host, args.port)
    return 0


def _serve_ui(root, candidates, runnable, host, port) -> None:  # pragma: no cover - UI
    """Launch the Streamlit UI.

    Streamlit is imported here rather than at module scope so the discovery and
    evaluation functions above stay importable in CI, where Streamlit is not
    installed and the production dependency set does not include it.
    """
    import tempfile

    import streamlit as st

    st.set_page_config(page_title="Plate model evaluator", layout="wide")
    st.title("Plate model evaluator")

    if not candidates:
        st.error(f"No models found under `{root}`. Expected `models/` or `runs/*/exported/`.")
        st.stop()
    if not runnable:
        st.warning(
            "Found no runnable ONNX artifacts. PyTorch checkpoints must be exported first: "
            "`python -m lpr_app.ml.export_onnx --exp-file <exp.py> --ckpt <ckpt.pth> --out <run>/exported/`"
        )
        st.stop()

    by_label = {candidate.label: candidate for candidate in runnable}
    labels = list(by_label)

    sidebar = st.sidebar
    sidebar.header("Models")
    chosen = sidebar.multiselect("Compare", labels, default=labels[:1])
    provider = sidebar.selectbox("Provider", ["cpu", "cuda", "rocm"], index=0)
    threshold = sidebar.slider("Detection confidence", 0.05, 0.95, 0.3, 0.05)

    with st.expander("Provenance", expanded=False):
        for label in chosen:
            manifest = by_label[label].manifest
            if not manifest:
                st.write(f"**{label}** — no manifest recorded.")
                continue
            st.write(f"**{label}** — {by_label[label].detail}")
            st.json(
                {field_name: manifest[field_name] for field_name in MANIFEST_DISPLAY_FIELDS if field_name in manifest}
            )

    uploaded = st.file_uploader("Images", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
    directory = st.text_input("Or a directory", value="")

    paths: list[Path] = []
    for handle in uploaded or []:
        target = Path(tempfile.gettempdir()) / handle.name
        target.write_bytes(handle.read())
        paths.append(target)
    if directory and not paths:
        paths = collect_images(directory, limit=20)

    if not chosen or not paths:
        st.caption("Choose at least one model and supply images.")
        st.stop()

    if st.button("Run", type="primary"):
        rows: dict[str, list[dict]] = {}
        progress = st.progress(0.0)
        # Build each backend once and reuse it across images. Constructing a
        # backend loads an ONNX session, so per-image construction would reload
        # the weights for every file and make the timing comparison meaningless.
        with st.spinner("Loading models…"):
            backends = {
                label: build_backend(
                    by_label[label].path,
                    provider=provider,
                    detector_conf_threshold=threshold,
                )
                for label in chosen
            }
        for backend in backends.values():
            backend.warm_up()

        total = len(chosen) * len(paths)
        done = 0
        for label in chosen:
            rows[label] = []
            for path in paths:
                rows[label].append(evaluate_image(backends[label], path))
                done += 1
                progress.progress(done / total)
        st.session_state["results"] = rows

    results = st.session_state.get("results")
    if not results:
        st.stop()

    st.subheader("Summary")
    st.dataframe(
        [{"model": name, **summarise(rows)} for name, rows in results.items()],
        use_container_width=True,
    )

    st.subheader("Per image")
    for image, entry in compare_reads(results).items():
        marker = "agreement" if entry["agreement"] else "**differs**"
        with st.expander(f"{image} — {marker}"):
            for name, reads in entry["reads"].items():
                st.write(f"**{name}**: {', '.join(reads) if any(reads) else '(no text)'}")
            for name, rows in results.items():
                for row in rows:
                    if Path(row["path"]).name == image and row["detections"]:
                        st.image(render(row["path"], row), caption=f"{name} — {row['latency_ms']}ms")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
