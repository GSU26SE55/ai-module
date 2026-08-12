"""Verify immutable production model artifacts before deserializing them."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from src.core.runtime import PROJECT_ROOT, env_bool

DEFAULT_MANIFEST = PROJECT_ROOT / "models" / "model-manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_manifest(path: str | Path | None = None) -> dict:
    """Fail closed when a required model artifact is missing or modified.

    Verification may only be disabled explicitly for isolated developer tooling.
    The production Compose file always enables it.
    """

    if not env_bool("AI_VERIFY_MODEL_MANIFEST", default=True):
        return {"verified": False, "reason": "disabled"}

    manifest_path = Path(path or os.getenv("AI_MODEL_MANIFEST", DEFAULT_MANIFEST))
    if not manifest_path.is_file():
        raise RuntimeError(f"Model manifest not found: {manifest_path}")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid model manifest: {manifest_path}") from exc

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("Model manifest must contain a non-empty artifacts list")

    seen: set[str] = set()
    for artifact in artifacts:
        relative = artifact.get("path")
        expected = artifact.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise RuntimeError("Every model artifact needs path and sha256 strings")
        if relative in seen:
            raise RuntimeError(f"Duplicate model artifact in manifest: {relative}")
        seen.add(relative)

        candidate = (PROJECT_ROOT / relative).resolve()
        try:
            candidate.relative_to(PROJECT_ROOT)
        except ValueError as exc:
            raise RuntimeError(f"Artifact escapes project root: {relative}") from exc
        if not candidate.is_file():
            raise RuntimeError(f"Model artifact not found: {relative}")

        actual = _sha256(candidate)
        if actual != expected.lower():
            raise RuntimeError(
                f"Model artifact checksum mismatch for {relative}: "
                f"expected {expected.lower()}, got {actual}"
            )

    complete_directories = payload.get("complete_directories", [])
    if not isinstance(complete_directories, list):
        raise RuntimeError("complete_directories must be a list")
    for relative_directory in complete_directories:
        if not isinstance(relative_directory, str):
            raise RuntimeError("Every complete_directories entry must be a string")
        directory = (PROJECT_ROOT / relative_directory).resolve()
        try:
            directory.relative_to(PROJECT_ROOT)
        except ValueError as exc:
            raise RuntimeError(
                f"Complete directory escapes project root: {relative_directory}"
            ) from exc
        if not directory.is_dir():
            raise RuntimeError(f"Complete artifact directory not found: {relative_directory}")
        untracked = sorted(
            str(candidate.relative_to(PROJECT_ROOT))
            for candidate in directory.rglob("*")
            if candidate.is_file()
            and str(candidate.relative_to(PROJECT_ROOT)) not in seen
        )
        if untracked:
            raise RuntimeError(
                "Untracked files found in complete artifact directory "
                f"{relative_directory}: {', '.join(untracked)}"
            )

    return {
        "verified": True,
        "manifest_version": payload.get("manifest_version", 1),
        "release": payload.get("release", "unknown"),
        "artifacts": len(artifacts),
    }
