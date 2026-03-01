"""Config hashing utilities for immutable config IDs.

`config_id` is a SHA-256 hash of a normalised, fully materialised YAML config.

Normalisation rules (v1):
- Load YAML into Python primitives (dict/list/str/int/float/bool/None).
- Canonicalise to JSON with stable key ordering.
- Hash the UTF-8 bytes of that canonical JSON.

This intentionally ignores YAML comments/whitespace and is order-independent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def _normalise_obj(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        # YAML keys are expected to be strings, but coerce defensively.
        return {str(k): _normalise_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalise_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return [_normalise_obj(v) for v in obj]
    return str(obj)


def config_id_from_obj(obj: Any) -> str:
    """Compute a config_id from a loaded YAML object."""
    payload = _normalise_obj(obj)
    b = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def config_id_from_yaml_text(text: str) -> str:
    """Compute a config_id from YAML text."""
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("Expected a mapping at root of YAML")
    return config_id_from_obj(data)


def config_id_from_yaml_file(path: Path) -> str:
    """Compute a config_id from a YAML file path."""
    return config_id_from_yaml_text(path.read_text(encoding="utf-8"))

