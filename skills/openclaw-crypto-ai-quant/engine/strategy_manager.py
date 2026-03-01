from __future__ import annotations

import copy
import logging
import os
import stat
import threading
from dataclasses import dataclass
from typing import Any, Callable

import yaml

from .utils import deep_merge, file_mtime, sha1_json

logger = logging.getLogger(__name__)


def _env_str(name: str, default: str = "") -> str:
    val = os.getenv(name)
    return default if val is None else str(val)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _norm_mode_key(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return ""
    # Allow a few friendly aliases.
    if s in {"mode1", "m1"}:
        return "primary"
    if s in {"mode2", "m2"}:
        return "fallback"
    if s in {"mode3", "m3", "safety", "safe"}:
        return "conservative"
    if s in {"halt", "pause", "paused"}:
        return "flat"
    return s


def _parse_symbol_list(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in str(raw or "").replace("\n", ",").split(","):
        sym = part.strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


@dataclass(frozen=True)
class StrategySnapshot:
    """A consistent view of strategy settings at a point in time."""

    yaml_path: str
    yaml_mtime: float | None
    overrides_sha1: str
    version: str | None


class StrategyManager:
    """Singleton-style strategy configuration loader.

    Key behaviors:
    - Deep-merge defaults ← global ← symbols.<SYMBOL>.
    - Optional live overrides when AI_QUANT_MODE in {live,dry_live}.
    - Hot-reload the YAML when file mtime changes, without reloading Python modules.
    - Thread-safe and fails-open: if YAML is broken, keep the last known-good config.

    This is designed to replace module reload loops used only to pick up YAML edits.
    """

    _instance: "StrategyManager | None" = None
    _instance_lock = threading.Lock()

    @classmethod
    def bootstrap(
        cls,
        *,
        defaults: dict[str, Any],
        yaml_path: str,
        changelog_path: str | None = None,
        watchlist_refresh_s: float = 60.0,
    ) -> "StrategyManager":
        """Create or replace the process-wide singleton using explicit defaults."""

        def defaults_provider() -> dict[str, Any]:
            return copy.deepcopy(defaults)

        with cls._instance_lock:
            cls._instance = cls(
                yaml_path=str(yaml_path),
                defaults_provider=defaults_provider,
                changelog_path=str(changelog_path) if changelog_path else None,
                watchlist_refresh_s=float(watchlist_refresh_s),
            )
            return cls._instance

    def __init__(
        self,
        *,
        yaml_path: str,
        defaults_provider: Callable[[], dict[str, Any]],
        changelog_path: str | None = None,
        watchlist_refresh_s: float = 60.0,
    ):
        self._yaml_path = str(yaml_path)
        self._defaults_provider = defaults_provider
        self._changelog_path = changelog_path
        self._watchlist_refresh_s = float(watchlist_refresh_s)

        self._lock = threading.RLock()
        self._yaml_mtime: float | None = None
        self._changelog_mtime: float | None = file_mtime(self._changelog_path) if self._changelog_path else None
        self._overrides: dict[str, Any] = {}
        self._overrides_sha1: str = ""
        self._version: str | None = None
        self._snapshot: StrategySnapshot | None = None

        self._watchlist: list[str] = []
        self._watchlist_updated_at: float = 0.0

        self._load_if_needed(force=True)

    @classmethod
    def get(cls) -> "StrategyManager":
        """Return the process-wide StrategyManager.

        Env vars:
        - AI_QUANT_STRATEGY_YAML. defaults to ./config/strategy_overrides.yaml
        - AI_QUANT_STRATEGY_CHANGELOG. optional path to strategy_changelog.json

        Defaults are pulled from mei_alpha_v1._DEFAULT_STRATEGY_CONFIG when available.
        """
        with cls._instance_lock:
            if cls._instance is not None:
                return cls._instance

            here = os.path.dirname(os.path.abspath(__file__))
            yaml_path = os.getenv(
                "AI_QUANT_STRATEGY_YAML",
                os.path.join(here, "..", "config", "strategy_overrides.yaml"),
            )
            changelog = os.getenv(
                "AI_QUANT_STRATEGY_CHANGELOG",
                os.path.join(here, "..", "strategy_changelog.json"),
            )

            def defaults_provider() -> dict[str, Any]:
                try:
                    import strategy.mei_alpha_v1 as mei_alpha_v1

                    return copy.deepcopy(getattr(mei_alpha_v1, "_DEFAULT_STRATEGY_CONFIG"))
                except (ImportError, AttributeError, TypeError):
                    return {"trade": {}, "indicators": {}, "filters": {}, "thresholds": {}}

            cls._instance = cls(
                yaml_path=str(yaml_path),
                defaults_provider=defaults_provider,
                changelog_path=str(changelog) if changelog and os.path.exists(changelog) else None,
                watchlist_refresh_s=float(os.getenv("AI_QUANT_WATCHLIST_REFRESH_S", "60")),
            )
            return cls._instance

    @property
    def snapshot(self) -> StrategySnapshot:
        self._load_if_needed(force=False)
        with self._lock:
            if self._snapshot is None:
                self._snapshot = StrategySnapshot(
                    yaml_path=self._yaml_path,
                    yaml_mtime=self._yaml_mtime,
                    overrides_sha1=self._overrides_sha1,
                    version=self._read_version_no_lock(),
                )
            return self._snapshot

    def _read_version_no_lock(self) -> str | None:
        path = self._changelog_path
        if not path or not os.path.exists(path):
            return self._version
        try:
            import json

            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            v = obj.get("current_version")
            if v:
                self._version = str(v)
            return self._version
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return self._version

    @staticmethod
    def _check_yaml_path(yaml_path: str) -> bool:
        """Best-effort safety checks on the YAML config path.

        Returns ``True`` if the file looks safe to load, ``False`` if it
        should be skipped (caller keeps the last known-good config).
        """
        try:
            if os.path.islink(yaml_path):
                logger.warning(
                    "Strategy YAML %s is a symlink — skipping reload for safety",
                    yaml_path,
                )
                return False
            mode = os.stat(yaml_path).st_mode
            if mode & stat.S_IWOTH:
                logger.warning(
                    "Strategy YAML %s is world-writable (mode %s) — skipping reload for safety",
                    yaml_path,
                    oct(mode),
                )
                return False
        except OSError:
            pass  # best-effort; don't block on stat failures
        return True

    def _load_yaml(self) -> dict[str, Any] | None:
        if not os.path.exists(self._yaml_path):
            return {}
        if not self._check_yaml_path(self._yaml_path):
            return None
        with open(self._yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}

    def _load_if_needed(self, *, force: bool = False) -> None:
        yaml_mtime = file_mtime(self._yaml_path)
        changelog_mtime = file_mtime(self._changelog_path) if self._changelog_path else None
        with self._lock:
            yaml_needs_reload = bool(force)
            if not yaml_needs_reload:
                if yaml_mtime is None:
                    yaml_needs_reload = self._yaml_mtime is not None
                elif self._yaml_mtime is None:
                    yaml_needs_reload = True
                else:
                    yaml_needs_reload = yaml_mtime > self._yaml_mtime

            changelog_needs_reload = bool(force)
            if not changelog_needs_reload and self._changelog_path:
                if changelog_mtime is None:
                    changelog_needs_reload = self._changelog_mtime is not None
                elif self._changelog_mtime is None:
                    changelog_needs_reload = True
                else:
                    changelog_needs_reload = changelog_mtime > self._changelog_mtime

            if not yaml_needs_reload and not changelog_needs_reload:
                return

            if yaml_needs_reload:
                try:
                    overrides = self._load_yaml()
                    overrides_sha1 = sha1_json(overrides) if overrides is not None else None
                except (OSError, ValueError):
                    return

                if overrides is not None:
                    self._yaml_mtime = yaml_mtime
                    self._overrides = overrides
                    self._overrides_sha1 = str(overrides_sha1)
                elif not changelog_needs_reload:
                    return

            if changelog_needs_reload:
                self._changelog_mtime = changelog_mtime

            self._snapshot = StrategySnapshot(
                yaml_path=self._yaml_path,
                yaml_mtime=self._yaml_mtime,
                overrides_sha1=self._overrides_sha1,
                version=self._read_version_no_lock(),
            )

    def maybe_reload(self) -> None:
        self._load_if_needed(force=False)

    def get_config(self, symbol: str) -> dict[str, Any]:
        """Returns merged config for symbol."""
        self._load_if_needed(force=False)
        sym = (symbol or "").upper()

        with self._lock:
            cfg = self._defaults_provider() or {}
            overrides = self._overrides or {}

        deep_merge(cfg, overrides.get("global") or {})
        deep_merge(cfg, (overrides.get("symbols") or {}).get(sym) or {})

        mode = str(os.getenv("AI_QUANT_MODE", "paper") or "paper").strip().lower()
        if mode in {"live", "dry_live"}:
            live_over = overrides.get("live") or {}
            if isinstance(live_over, dict):
                if "global" in live_over or "symbols" in live_over:
                    deep_merge(cfg, live_over.get("global") or {})
                    deep_merge(cfg, (live_over.get("symbols") or {}).get(sym) or {})
                else:
                    deep_merge(cfg, live_over)

        # Optional strategy-mode overlays (e.g., Primary/Fallback/Conservative/Flat).
        # The mode is selected via env var so operators can switch quickly without editing YAML.
        # YAML structure:
        #   modes:
        #     primary:
        #       global: {...}
        #       symbols: { BTC: {...}, ... }
        mode_key = _norm_mode_key(_env_str("AI_QUANT_STRATEGY_MODE", ""))
        if mode_key:
            modes = overrides.get("modes") or {}
            if isinstance(modes, dict):
                mode_over = modes.get(mode_key)
                if mode_over is None:
                    mode_over = modes.get(str(mode_key).upper())
                if mode_over is None:
                    mode_over = modes.get(str(mode_key).lower())
                if isinstance(mode_over, dict):
                    if "global" in mode_over or "symbols" in mode_over:
                        deep_merge(cfg, mode_over.get("global") or {})
                        deep_merge(cfg, (mode_over.get("symbols") or {}).get(sym) or {})
                    else:
                        # Shorthand: modes.<mode>: {trade: {...}, filters: {...}, ...}
                        deep_merge(cfg, mode_over)

        for key in ("trade", "indicators", "filters", "thresholds"):
            if not isinstance(cfg.get(key), dict):
                cfg[key] = {}
        return cfg

    def get_watchlist(self) -> list[str]:
        """Return the active watchlist.

        Priority:
        1) AI_QUANT_SYMBOLS explicit list
        2) top-N by 24h notional volume via hyperliquid_meta.top_symbols_by_day_notional_volume
        3) fallback list from mei_alpha_v1._FALLBACK_SYMBOLS

        The list is cached for watchlist_refresh_s seconds.
        """
        import time

        raw = _env_str("AI_QUANT_SYMBOLS", "").strip()
        if raw:
            return _parse_symbol_list(raw)

        with self._lock:
            if self._watchlist and (time.time() - self._watchlist_updated_at) < self._watchlist_refresh_s:
                return list(self._watchlist)

        try:
            top_n = int(os.getenv("AI_QUANT_TOP_N", "50"))
        except Exception:
            top_n = 50
        top_n = max(1, min(200, top_n))

        watchlist: list[str] = []
        rest_enabled = _env_bool("AI_QUANT_REST_ENABLE", True)
        if rest_enabled:
            try:
                import exchange.meta as hyperliquid_meta

                watchlist = hyperliquid_meta.top_symbols_by_day_notional_volume(top_n) or []
            except Exception:
                watchlist = []

        if not watchlist:
            try:
                import strategy.mei_alpha_v1 as mei_alpha_v1

                watchlist = list(getattr(mei_alpha_v1, "_FALLBACK_SYMBOLS", []))
            except Exception:
                watchlist = []

        out: list[str] = []
        seen: set[str] = set()
        for s in watchlist:
            su = str(s).upper()
            if not su or su in seen:
                continue
            seen.add(su)
            out.append(su)

        with self._lock:
            self._watchlist = out
            self._watchlist_updated_at = time.time()

        return list(out)
