"""Extract auditable trade parameters from authoritative Square posts.

The module deliberately does not derive missing prices or place trades.  It
normalizes author-supplied parameters into Decimal-based candidates that the
scoring layer can validate against a point-in-time market snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .authors import AuthorProfile
from .contracts import ContractViolation
from .square import PostDetail, StructuredPost


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class ParameterSource(str, Enum):
    AUTHOR = "AUTHOR"
    SYSTEM_REDERIVED = "SYSTEM_REDERIVED"


class ParameterEvidenceSource(str, Enum):
    STRUCTURED_POST = "STRUCTURED_POST"
    LEGACY_EXPLICIT_INPUT = "LEGACY_EXPLICIT_INPUT"


@dataclass(frozen=True, slots=True)
class SignalCandidate:
    signal_id: str
    signal_family_id: str
    post_id: str
    post_url: str
    author_id: str | None
    symbol: str
    direction: Direction
    entry_low: Decimal | None
    entry_high: Decimal | None
    entry_price: Decimal | None
    stop_loss: Decimal | None
    tp1: Decimal | None
    tp2: Decimal | None
    published_at: str
    invalidation: str | None
    rationale: str | None
    parameter_source: ParameterSource
    parameter_evidence_source: ParameterEvidenceSource
    source_class: str
    holding_period_hours: int = 72


@dataclass(frozen=True, slots=True)
class RiskReward:
    risk: Decimal
    tp1_rr: Decimal
    main_target: Decimal
    main_target_rr: Decimal


@dataclass(frozen=True, slots=True)
class ConsensusObservation:
    """One point-in-time input to the independent-author consensus index.

    ``author_id`` must be the stable Square identity, not a display name.  A
    missing identity is retained as an input fact but is never allowed to add
    consensus.  ``content_hash`` is supplied by the versioned post layer so
    copied/reposted content can be clustered without inspecting mutable text.
    """

    signal_id: str
    symbol: str
    direction: Direction
    author_id: str | None
    content_hash: str


@dataclass(frozen=True, slots=True)
class ConsensusCluster:
    content_hash: str
    author_ids: tuple[str, ...]
    signal_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConsensusIndex:
    """Immutable symbol/direction index of content-hash clusters."""

    clusters: Mapping[tuple[str, Direction], tuple[ConsensusCluster, ...]]

    def other_author_ids(
        self,
        *,
        symbol: str,
        direction: Direction,
        author_id: str | None,
        content_hash: str | None = None,
    ) -> tuple[str, ...]:
        """Return independent stable authors, excluding self and copied text.

        Each content-hash cluster can contribute at most one author and each
        author can contribute at most once.  When the candidate content hash is
        known, its whole cluster is excluded: another account copying the
        candidate is not independent confirmation.
        """

        excluded_author = author_id.strip() if isinstance(author_id, str) else None
        if not excluded_author or excluded_author.upper() == "LIVE":
            return ()
        excluded_hash = content_hash.strip() if isinstance(content_hash, str) else None
        chosen: set[str] = set()
        for cluster in self.clusters.get((symbol.upper(), direction), ()):
            if excluded_hash and cluster.content_hash == excluded_hash:
                continue
            if excluded_author and excluded_author in cluster.author_ids:
                continue
            alternatives = tuple(
                value for value in cluster.author_ids if value != excluded_author
            )
            if alternatives:
                chosen.add(alternatives[0])
        return tuple(sorted(chosen))

    def count_for(
        self,
        *,
        symbol: str,
        direction: Direction,
        author_id: str | None,
        content_hash: str | None = None,
    ) -> int:
        return len(
            self.other_author_ids(
                symbol=symbol,
                direction=direction,
                author_id=author_id,
                content_hash=content_hash,
            )
        )


def build_consensus_index(
    observations: Iterable[ConsensusObservation],
) -> ConsensusIndex:
    """Build a deterministic consensus index with no self/copy inflation."""

    grouped: dict[
        tuple[str, Direction], dict[str, dict[str, set[str]]]
    ] = {}
    for observation in observations:
        if not isinstance(observation, ConsensusObservation):
            raise ContractViolation("consensus inputs must be ConsensusObservation values")
        symbol = observation.symbol.strip().upper()
        content_hash = observation.content_hash.strip()
        signal_id = observation.signal_id.strip()
        if not symbol or not content_hash or not signal_id:
            raise ContractViolation(
                "consensus symbol, content hash, and signal ID must be non-empty"
            )
        if not isinstance(observation.direction, Direction):
            raise ContractViolation("consensus direction must be LONG or SHORT")
        key = (symbol, observation.direction)
        cluster = grouped.setdefault(key, {}).setdefault(
            content_hash, {"author_ids": set(), "signal_ids": set()}
        )
        cluster["signal_ids"].add(signal_id)
        author_id = (
            observation.author_id.strip()
            if isinstance(observation.author_id, str)
            else ""
        )
        if author_id and author_id.upper() != "LIVE":
            cluster["author_ids"].add(author_id)

    frozen: dict[tuple[str, Direction], tuple[ConsensusCluster, ...]] = {}
    for key, raw_clusters in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        frozen[key] = tuple(
            ConsensusCluster(
                content_hash=content_hash,
                author_ids=tuple(sorted(values["author_ids"])),
                signal_ids=tuple(sorted(values["signal_ids"])),
            )
            for content_hash, values in sorted(raw_clusters.items())
        )
    return ConsensusIndex(clusters=MappingProxyType(frozen))


_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_FIELD_END = r"(?=\s*(?:\n|$|[-–—~]))"


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value.replace(",", "").strip())
    except InvalidOperation as exc:
        raise ContractViolation(f"invalid signal price: {value!r}") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ContractViolation("signal prices must be finite and positive")
    return parsed


def _direction(text: str) -> Direction:
    matches = {
        Direction.LONG if token.casefold() == "long" else Direction.SHORT
        for token in re.findall(r"(?i)\b(long|short)\b", text)
    }
    if len(matches) != 1:
        raise ContractViolation("signal must contain exactly one unambiguous direction")
    return matches.pop()


def _symbol(text: str) -> str:
    direct = {
        match.group(1).upper()
        for match in re.finditer(
            r"(?i)(?<![A-Z0-9])\$?([A-Z0-9]{2,12})(?:/)?USDT\b", text
        )
    }
    if len(direct) == 1:
        return f"{direct.pop()}USDT"
    if len(direct) > 1:
        raise ContractViolation("signal must contain exactly one unambiguous USDT symbol")
    marked = set(re.findall(
        r"(?i)\b(?:long|short)\b(?:\s+(?:setup|signal|idea|on))?\s*[:\-]?\s*\$([A-Z][A-Z0-9]{1,11})\b",
        text,
    ))
    marked.update(re.findall(
        r"(?i)\$([A-Z][A-Z0-9]{1,11})\b.{0,40}?\b(?:long|short)\b",
        text,
    ))
    if len(marked) == 1:
        return f"{marked.pop().upper()}USDT"
    raise ContractViolation("signal must identify a USDT symbol")


def _field_price(text: str, names: str) -> Decimal | None:
    match = re.search(
        rf"(?im)^\s*(?:{names})\s*[:：]?\s*\$?({_NUMBER}){_FIELD_END}", text
    )
    return _decimal(match.group(1)) if match else None


def _entry(text: str) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    match = re.search(
        rf"(?im)^\s*(?:entry(?:\s+(?:zone|price|range))?|buy\s+zone|sell\s+zone)\s*[:：]?\s*"
        rf"\$?({_NUMBER})(?:\s*(?:-|–|—|~|to)\s*\$?({_NUMBER}))?{_FIELD_END}",
        text,
    )
    if not match:
        return None, None, None
    first = _decimal(match.group(1))
    second = _decimal(match.group(2)) if match.group(2) else first
    assert first is not None and second is not None
    low, high = sorted((first, second))
    return low, high, (low + high) / Decimal(2)


def _invalidation(text: str) -> str | None:
    match = re.search(
        r"(?im)^\s*(?:invalidation|invalid\s+if)\s*[:：]\s*(.+?)\s*$", text
    )
    return match.group(1).strip() if match else None


def _price_range(value: Any) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if value is None:
        return None, None, None
    numbers = re.findall(_NUMBER, str(value))
    if not numbers:
        return None, None, None
    first = _decimal(numbers[0])
    second = _decimal(numbers[1]) if len(numbers) > 1 else first
    assert first is not None and second is not None
    low, high = sorted((first, second))
    return low, high, (low + high) / Decimal(2)


def _legacy_values(value: Mapping[str, Any]) -> dict[str, Any]:
    raw_symbol = str(value.get("symbol") or "").strip().upper().replace("/", "")
    if not raw_symbol:
        raise ContractViolation("legacy signal must identify a symbol")
    symbol = raw_symbol if raw_symbol.endswith("USDT") else f"{raw_symbol}USDT"
    try:
        direction = Direction(str(value.get("direction") or "").strip().upper())
    except ValueError as exc:
        raise ContractViolation("legacy signal direction must be long or short") from exc
    entry_low, entry_high, entry_price = _price_range(value.get("entry"))
    stop_loss, _, _ = _price_range(value.get("sl") or value.get("stop_loss"))
    target_parts = re.split(
        r"\s*/\s*|\s*;\s*|,(?!\d{3}(?:\D|$))",
        str(value.get("tp") or ""),
    )
    targets: list[Decimal] = []
    for part in target_parts:
        low, high, _ = _price_range(part)
        if low is None or high is None:
            continue
        targets.append(low if direction is Direction.LONG else high)
    return {
        "symbol": symbol,
        "direction": direction,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "tp1": targets[0] if targets else None,
        "tp2": targets[1] if len(targets) > 1 else None,
        "invalidation": value.get("invalidation"),
    }


def _extract_from_text(text: str) -> dict[str, Any]:
    entry_low, entry_high, entry_price = _entry(text)
    return {
        "symbol": _symbol(text),
        "direction": _direction(text),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "entry_price": entry_price,
        "stop_loss": _field_price(text, r"sl\b|stop\s*loss|stop\b"),
        "tp1": _field_price(text, r"tp\s*[:：]|tp\s*1\b|target\s*1\b|take\s*profit\s*1\b"),
        "tp2": _field_price(text, r"tp\s*2\b|target\s*2\b|take\s*profit\s*2\b"),
        "invalidation": _invalidation(text),
    }


def extract_signal(
    post: StructuredPost | PostDetail,
    author: AuthorProfile | None,
    *,
    legacy_signal: Mapping[str, Any] | None = None,
) -> SignalCandidate:
    """Extract one signal without inferring missing author parameters.

    ``legacy_signal`` is accepted only as an explicit author-parameter record;
    its provenance remains visible and it never changes the author's tier.
    """

    if not isinstance(post, (StructuredPost, PostDetail)):
        raise ContractViolation("post must be a StructuredPost or PostDetail")
    if author is not None and isinstance(post, PostDetail) and author.author_id != post.author_id:
        raise ContractViolation("post and author stable IDs do not match")

    if legacy_signal is None:
        values = _extract_from_text(post.content)
        evidence_source = ParameterEvidenceSource.STRUCTURED_POST
        rationale = post.content.strip() or None
    else:
        values = _legacy_values(legacy_signal)
        evidence_source = ParameterEvidenceSource.LEGACY_EXPLICIT_INPUT
        raw_rationale = legacy_signal.get("reasoning")
        rationale = raw_rationale.strip() if isinstance(raw_rationale, str) else None

    symbol = values["symbol"]
    direction = values["direction"]
    signal_id = f"{post.post_id}:{symbol}:{direction.value}"
    return SignalCandidate(
        signal_id=signal_id,
        signal_family_id=signal_id,
        post_id=post.post_id,
        post_url=post.post_url,
        author_id=author.author_id if author is not None else getattr(post, "author_id", None),
        symbol=symbol,
        direction=direction,
        entry_low=values["entry_low"],
        entry_high=values["entry_high"],
        entry_price=values["entry_price"],
        stop_loss=values["stop_loss"],
        tp1=values["tp1"],
        tp2=values["tp2"],
        published_at=post.published_at,
        invalidation=values["invalidation"],
        rationale=rationale,
        parameter_source=ParameterSource.AUTHOR,
        parameter_evidence_source=evidence_source,
        source_class=getattr(post, "source_class", "SQUARE_UGC"),
    )


def calculate_risk_reward(candidate: SignalCandidate) -> RiskReward:
    """Calculate nominal R from the midpoint of the author's entry zone."""

    if candidate.entry_price is None or candidate.stop_loss is None or candidate.tp1 is None:
        raise ContractViolation("RR requires Entry, SL, and TP1")
    entry = candidate.entry_price
    stop = candidate.stop_loss
    tp1 = candidate.tp1
    main_target = candidate.tp2 if candidate.tp2 is not None else tp1
    if candidate.direction is Direction.LONG:
        if not stop < entry < tp1 or main_target < tp1:
            raise ContractViolation("long prices must satisfy SL < Entry < TP1 <= main target")
        risk = entry - stop
        tp1_reward = tp1 - entry
        main_reward = main_target - entry
    else:
        if not stop > entry > tp1 or main_target > tp1:
            raise ContractViolation("short prices must satisfy SL > Entry > TP1 >= main target")
        risk = stop - entry
        tp1_reward = entry - tp1
        main_reward = entry - main_target
    return RiskReward(
        risk=risk,
        tp1_rr=tp1_reward / risk,
        main_target=main_target,
        main_target_rr=main_reward / risk,
    )


__all__ = [
    "ConsensusCluster",
    "ConsensusIndex",
    "ConsensusObservation",
    "Direction",
    "ParameterEvidenceSource",
    "ParameterSource",
    "RiskReward",
    "SignalCandidate",
    "build_consensus_index",
    "calculate_risk_reward",
    "extract_signal",
]
