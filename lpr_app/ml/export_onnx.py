#!/usr/bin/env python3
"""Export a trained checkpoint to ONNX for ONNX Runtime CPU inference.

YOLOX's own demo exports are the reference for the decode path, but they target
their bundled demo script. This exports the same graph and records provenance
alongside it, so a deployed artifact can be traced to the checkpoint and corpus
it came from.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model(exp_file: str, ckpt: str, device: str = "cuda"):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "YOLOX"))
    exp_module = __import__(Path(exp_file).stem, fromlist=["Exp"])
    exp = exp_module.Exp()

    import torch

    ckpt_path = Path(ckpt)
    device = "cuda" if (device == "cuda" and torch.cuda.is_available()) else "cpu"
    ckpt_data = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model = exp.get_model()
    model.load_state_dict(ckpt_data["model"])
    model.eval()
    if device == "cuda":
        model.cuda()
    return exp, model, device


def export(exp, model, device: str, out_path: Path, *, opset: int = 11, simplify: bool = False) -> Path:
    import torch

    height, width = exp.test_size
    dummy = torch.zeros(1, 3, height, width, device=device)
    dynamic = {"images": {0: "batch", 2: "height", 3: "width"}}
    out_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy,
        str(out_path),
        opset_version=opset,
        input_names=["images"],
        output_names=["output"],
        dynamic_axes=dynamic,
        do_constant_folding=True,
    )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exp", required=True)
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--opset", type=int, default=11)
    parser.add_argument("--simplify", action="store_true")
    parser.add_argument(
        "--manifest",
        default=None,
        help="manifest json to update; defaults to <out>.manifest.json",
    )
    args = parser.parse_args()

    exp, model, device = load_model(args.exp, args.ckpt, args.device)
    out_path = Path(args.out)
    export(exp, model, device, out_path, opset=args.opset, simplify=args.simplify)

    manifest_path = Path(args.manifest) if args.manifest else out_path.with_suffix(".manifest.json")
    entry = {
        "artifact": out_path.name,
        "sha256": sha256(out_path),
        "bytes": out_path.stat().st_size,
        "checkpoint": str(Path(args.ckpt).name),
        "checkpoint_sha256": sha256(Path(args.ckpt)),
        "experiment": Path(args.exp).name,
        "input_size": list(exp.test_size),
        "num_classes": exp.num_classes,
        "class_names": exp.class_names,
        # YOLOX is Apache-2.0 for both code and its same-repository release
        # weights. Recorded because the license must be auditable, not assumed:
        # Ultralytics YOLO weights are AGPL-3.0 and are excluded from this
        # project for that reason. See DETECTOR.md.
        "upstream": "YOLOX (Megvii-BaseDetection/YOLOX)",
        "license": "Apache-2.0",
        "weights_license_basis": "repository LICENSE; weights are release assets of the same repository",
        "pretrained_from": "COCO (yolox_tiny.pth)",
        "trained_on": "open-lpr annotated plate corpus, frame-grouped split with gap",
        "exported_with": f"torch {__import__('torch').__version__}",
    }

    existing = {}
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text())
    existing[out_path.name] = entry
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(existing, indent=2, sort_keys=True))

    print(json.dumps(entry, indent=2))
    print(f"\nmanifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    raise SystemExit(main())
