from __future__ import annotations

import hashlib
import json
import logging

from engine.utils import deep_merge, file_mtime, sha1_json, sha256_json


def test_file_mtime_none_returns_none() -> None:
    assert file_mtime(None) is None


def test_deep_merge_warns_and_ignores_non_dict_override(caplog) -> None:
    base = {"trade": {"leverage": 3}}

    with caplog.at_level(logging.WARNING):
        out = deep_merge(base, "not-a-dict")

    assert out is base
    assert base == {"trade": {"leverage": 3}}
    assert any("deep_merge override ignored" in rec.message for rec in caplog.records)


def test_deep_merge_with_none_override_keeps_base_without_warning(caplog) -> None:
    base = {"filters": {"enable_market_breadth_filter": True}}

    with caplog.at_level(logging.WARNING):
        out = deep_merge(base, None)

    assert out is base
    assert base == {"filters": {"enable_market_breadth_filter": True}}
    assert not caplog.records


def test_sha1_json_returns_sha256_digest_for_json_payload() -> None:
    payload = {"b": 2, "a": [1, "x"]}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    expected = hashlib.sha256(encoded).hexdigest()

    assert sha1_json(payload) == expected
    assert sha256_json(payload) == expected
    assert len(sha1_json(payload)) == 64


def test_sha1_json_uses_repr_fallback_with_sha256() -> None:
    class _OnlyRepr:
        def __repr__(self) -> str:
            return "only-repr"

    expected = hashlib.sha256(b"only-repr").hexdigest()
    assert sha1_json(_OnlyRepr()) == expected
