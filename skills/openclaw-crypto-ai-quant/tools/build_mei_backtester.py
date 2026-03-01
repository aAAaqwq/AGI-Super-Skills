#!/usr/bin/env python3
"""Build stamped mei-backtester binaries (CPU and optional GPU) (AQC-1103).

This is a small automation wrapper around cargo build that:
- builds a release binary without GPU features (CPU build)
- optionally builds a GPU-featured release binary
- copies the resulting artefacts into backtester/dist/
- writes a build_info.json summary for traceability
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AIQ_ROOT = Path(__file__).resolve().parents[1]
BT_ROOT = (AIQ_ROOT / "backtester").resolve()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, check=False)


def _git_head() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(AIQ_ROOT)).decode("utf-8").strip()
        return out
    except Exception:
        return ""


def _target_bin_path() -> Path:
    exe = "mei-backtester.exe" if os.name == "nt" else "mei-backtester"
    return (BT_ROOT / "target" / "release" / exe).resolve()


@dataclass(frozen=True)
class BuiltArtefact:
    kind: str  # cpu | gpu
    path: str
    sha256: str
    version: str


def _read_version(path: Path) -> str:
    proc = _run([str(path), "--version"], cwd=BT_ROOT)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"--version failed (exit={proc.returncode}): {stderr}")
    return (proc.stdout or "").strip()


def _build_one(*, kind: str, features: list[str]) -> BuiltArtefact:
    argv = ["cargo", "build", "--release", "-p", "bt-cli", "--bin", "mei-backtester"]
    if features:
        argv += ["--features", ",".join(features)]

    proc = _run(argv, cwd=BT_ROOT)
    if proc.returncode != 0:
        raise SystemExit(
            "cargo build failed:\n"
            + (proc.stdout or "")
            + "\n"
            + (proc.stderr or "")
        )

    bin_path = _target_bin_path()
    if not bin_path.exists():
        raise SystemExit(f"Expected binary not found after build: {bin_path}")

    version = _read_version(bin_path)
    return BuiltArtefact(kind=str(kind), path=str(bin_path), sha256=_sha256(bin_path), version=version)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build mei-backtester CPU/GPU binaries and stamp build metadata.")
    ap.add_argument("--out-dir", default=str(BT_ROOT / "dist"), help="Output directory (default: backtester/dist).")
    ap.add_argument("--gpu", action="store_true", help="Also build the GPU-featured binary.")
    args = ap.parse_args(argv)

    out_dir = Path(str(args.out_dir)).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    started = int(time.time() * 1000)
    artefacts: list[BuiltArtefact] = []

    # CPU build first, copy out before the GPU build overwrites the target binary.
    cpu = _build_one(kind="cpu", features=[])
    cpu_dst = (out_dir / ("mei-backtester-cpu.exe" if os.name == "nt" else "mei-backtester-cpu")).resolve()
    shutil.copy2(Path(cpu.path), cpu_dst)
    artefacts.append(BuiltArtefact(kind="cpu", path=str(cpu_dst), sha256=_sha256(cpu_dst), version=cpu.version))

    if bool(args.gpu):
        gpu = _build_one(kind="gpu", features=["gpu"])
        gpu_dst = (out_dir / ("mei-backtester-gpu.exe" if os.name == "nt" else "mei-backtester-gpu")).resolve()
        shutil.copy2(Path(gpu.path), gpu_dst)
        artefacts.append(BuiltArtefact(kind="gpu", path=str(gpu_dst), sha256=_sha256(gpu_dst), version=gpu.version))

    meta: dict[str, Any] = {
        "version": "mei_backtester_build_v1",
        "generated_at_ms": started,
        "git_head": _git_head(),
        "artefacts": [a.__dict__ for a in artefacts],
    }
    (out_dir / "build_info.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

