"""Fetch the local pipeline's ONNX artifacts, verifying checksums.

Called from docker-entrypoint.sh so a fresh deployment becomes functional
without an operator first running a download step by hand. Uses only the
standard library: the runtime image is python:3.11-slim, which ships neither
curl nor wget, and adding one for ~37MB of downloads would grow the image for
every user to serve a path that runs once per deployment.

The artifacts are pinned to a tag in the weights repository rather than fetched
from a moving branch. A published deployment tag should resolve to the same
bytes on every redeploy, including ones months later; an unpinned `main` would
let a re-publish silently change what a pinned image version runs.

Checksums come from the manifest at the same pinned revision. Both are fetched
over HTTPS from the same tag, so verification establishes that the download
arrived intact and matches what that revision declares -- not that the
publisher was honest, which no checksum can establish.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("fetch_artifacts")

DEFAULT_REPO = "faisalthaheem/open-lpr-models"
DEFAULT_REVISION = "detector-2026.10.1"

# Artifact -> path within the weights repository, relative to its root.
ARTIFACTS = {
    "plate_yolox_tiny_640.onnx": "onnx/plate_yolox_tiny_640.onnx",
    "plate_ocr_ppocrv5_mobile.onnx": "onnx/plate_ocr_ppocrv5_mobile.onnx",
    "plate_ocr_dict.json": "onnx/plate_ocr_dict.json",
}

CHUNK = 1 << 16


def _base_url(repo: str, revision: str) -> str:
    return f"https://huggingface.co/{repo}/resolve/{revision}"


def _download(url: str, dest: Path, timeout: float) -> None:
    """Stream to a sibling temp file, then rename into place.

    The rename is what makes a partially-fetched artifact impossible to mistake
    for a complete one: a container killed mid-download leaves a .part file that
    no later run will treat as present, rather than a truncated .onnx that
    passes an existence check and fails at load time.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".part")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                while chunk := response.read(CHUNK):
                    handle.write(chunk)
        # mkstemp creates 0600. Artifacts are read-only data, and the entrypoint
        # may chown them to a different user than the one that fetched them, so
        # widen before publishing. Leaving 0600 here produced files that the
        # django user could read only by ownership accident.
        os.chmod(tmp, 0o644)
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_manifest(base: str, timeout: float) -> dict[str, str]:
    """Return {artifact: sha256} for the artifacts we know how to fetch."""
    raw = tempfile.NamedTemporaryFile(delete=False)
    raw.close()
    tmp = Path(raw.name)
    try:
        _download(f"{base}/manifest.json", tmp, timeout)
        manifest = json.loads(tmp.read_text(encoding="utf-8"))
    finally:
        tmp.unlink(missing_ok=True)

    published = manifest.get("artifacts", {})
    checksums = {}
    for name in ARTIFACTS:
        entry = published.get(name)
        if not entry or not entry.get("sha256"):
            raise RuntimeError(f"manifest at {base} declares no sha256 for {name}")
        checksums[name] = entry["sha256"]
    return checksums


def ensure_artifacts(
    model_dir: Path,
    base: str,
    names: list[str],
    timeout: float = 120.0,
    force: bool = False,
) -> int:
    """Ensure each artifact is present and matches its published checksum.

    Returns the number of artifacts downloaded. An artifact already present and
    correct is left alone, so a persistent volume pays this cost once rather
    than on every restart.
    """
    missing = [n for n in names if not (model_dir / n).is_file()]
    if not missing and not force:
        log.info("All artifacts present in %s", model_dir)
        return 0

    checksums = fetch_manifest(base, timeout)
    downloaded = 0

    for name in names:
        target = model_dir / name
        if target.is_file():
            actual = _sha256(target)
            if actual == checksums[name]:
                log.info("%s present and verified", name)
                continue
            log.warning("%s failed checksum verification, re-downloading", name)

        log.info("Downloading %s from %s", name, base)
        try:
            _download(f"{base}/{ARTIFACTS[name]}", target, timeout)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"failed to download {name}: HTTP {exc.code} from {base}/{ARTIFACTS[name]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"failed to download {name}: {exc.reason}") from exc

        actual = _sha256(target)
        if actual != checksums[name]:
            # Leave nothing that a later run could mistake for good.
            target.unlink(missing_ok=True)
            raise RuntimeError(
                f"{name} checksum mismatch: got {actual}, expected {checksums[name]}. "
                "The download was corrupted or the revision does not match its manifest."
            )

        log.info("%s downloaded and verified (%d bytes)", name, target.stat().st_size)
        downloaded += 1

    return downloaded


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default=os.environ.get("PIPELINE_MODEL_DIR", "/app/model/plate"))
    parser.add_argument("--repo", default=os.environ.get("PIPELINE_MODEL_REPO", DEFAULT_REPO))
    parser.add_argument("--revision", default=os.environ.get("PIPELINE_MODEL_REVISION", DEFAULT_REVISION))
    parser.add_argument("--artifacts", default=",".join(ARTIFACTS), help="comma-separated filenames")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s fetch_artifacts %(message)s")

    names = [n.strip() for n in args.artifacts.split(",") if n.strip()]
    unknown = [n for n in names if n not in ARTIFACTS]
    if unknown:
        parser.error(f"unknown artifacts, no known repository path: {unknown}")

    model_dir = Path(args.model_dir)
    try:
        model_dir.mkdir(parents=True, exist_ok=True)
        # The entrypoint runs as root and drops to the django user via gosu.
        # Without this the files are root-owned and unreadable afterwards.
        os.chmod(model_dir, 0o755)
        downloaded = ensure_artifacts(
            model_dir,
            _base_url(args.repo, args.revision),
            names,
            timeout=args.timeout,
            force=args.force,
        )
    except Exception as exc:
        log.error("Artifact fetch failed: %s", exc)
        return 1

    log.info("Artifacts ready in %s (%d downloaded)", model_dir, downloaded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
