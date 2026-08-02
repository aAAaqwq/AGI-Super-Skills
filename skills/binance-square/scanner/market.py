"""Public, read-only Binance market evidence for the v4 scanner.

The module deliberately keeps contract discovery on USDⓈ-M Futures.  Spot may
only proxy price and closed OHLC after a Futures catalog has verified the exact
contract at the decision point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
import socket
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scanner.contracts import ContractViolation, parse_utc


FUTURES_ORIGIN = "https://fapi.binance.com"
SPOT_ORIGIN = "https://api.binance.com"
INTERVALS = ("15m", "1h", "4h", "1d")
UNKNOWN = "UNKNOWN"


class MarketSource(str, Enum):
    FUTURES = "FUTURES"
    SPOT_PROXY = "SPOT_PROXY"


class FailureKind(str, Enum):
    RATE_LIMITED = "RATE_LIMITED"
    REGION_RESTRICTED = "REGION_RESTRICTED"
    TIMEOUT = "TIMEOUT"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    HTTP_ERROR = "HTTP_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class MarketApiError(RuntimeError):
    """A bounded failure that never embeds an upstream body or raw exception."""

    def __init__(
        self,
        kind: FailureKind,
        *,
        status: int | None = None,
        retry_after: str | None = None,
    ) -> None:
        self.kind = kind
        self.status = status
        self.retry_after = retry_after
        super().__init__(kind.value)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes | str
    headers: Mapping[str, str]


class Transport(Protocol):
    def __call__(self, url: str, timeout: float) -> HttpResponse: ...


def _urllib_transport(url: str, timeout: float) -> HttpResponse:
    request = Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "binance-square-scanner-v4"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(
                status=response.status,
                body=response.read(),
                headers=dict(response.headers.items()),
            )
    except HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            body=b"",
            headers=dict(exc.headers.items()) if exc.headers else {},
        )
    except (TimeoutError, socket.timeout) as exc:
        raise TimeoutError from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise TimeoutError from exc
        raise OSError("public market transport unavailable") from exc


def _decimal(value: Any, field_name: str) -> Decimal:
    if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
        raise ContractViolation(f"{field_name} must be a decimal string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ContractViolation(f"invalid {field_name}") from exc
    if not parsed.is_finite():
        raise ContractViolation(f"{field_name} must be finite")
    return parsed


def _decision_time_ms(value: int | None, *, maximum_ms: int) -> int:
    """Validate an explicit point-in-time cutoff against observed server time."""

    if not isinstance(maximum_ms, int) or isinstance(maximum_ms, bool):
        raise ContractViolation("maximum decision time must be integer milliseconds")
    if value is None:
        return maximum_ms
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ContractViolation("decision_time_ms must be positive integer milliseconds")
    if value > maximum_ms:
        raise ContractViolation("decision_time_ms cannot exceed observed server time")
    return value


@dataclass(frozen=True, slots=True)
class Candle:
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | str
    close_time: int
    quote_volume: Decimal | str
    number_of_trades: int
    source: MarketSource
    volume_unit: str


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    symbol: str
    contract: ContractRecord
    source: MarketSource
    decision_time_ms: int
    captured_at: datetime
    last_price: Decimal
    mark_price: Decimal | str
    index_price: Decimal | str
    funding_rate: Decimal | str
    open_interest: Decimal | str
    base_volume_24h: Decimal | str
    quote_volume_24h: Decimal | str
    candles: Mapping[str, tuple[Candle, ...]]
    missing_fields: tuple[str, ...]
    failures: tuple[FailureKind, ...]

    @property
    def expected_dataset_count(self) -> int:
        return 11

    @property
    def complete_dataset_count(self) -> int:
        scalar_values = (
            self.last_price,
            self.mark_price,
            self.index_price,
            self.funding_rate,
            self.open_interest,
            self.base_volume_24h,
            self.quote_volume_24h,
        )
        return sum(value != UNKNOWN for value in scalar_values) + sum(
            bool(self.candles.get(interval)) for interval in INTERVALS
        )

    @property
    def completeness_ratio(self) -> Decimal:
        return Decimal(self.complete_dataset_count) / Decimal(self.expected_dataset_count)


def closed_klines(
    rows: Any,
    *,
    decision_at_ms: int,
    source: MarketSource,
    keep_last: int | None = None,
) -> tuple[Candle, ...]:
    """Validate Binance tuples, filter by close time, then take the tail."""

    if not isinstance(rows, list):
        raise ContractViolation("klines response must be a list")
    if not isinstance(decision_at_ms, int) or isinstance(decision_at_ms, bool):
        raise ContractViolation("decision time must be integer milliseconds")
    if keep_last is not None and (not isinstance(keep_last, int) or keep_last < 1):
        raise ContractViolation("keep_last must be a positive integer")

    parsed: list[Candle] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 12:
            raise ContractViolation("kline tuple must contain at least 12 fields")
        if (
            not isinstance(row[0], int)
            or isinstance(row[0], bool)
            or not isinstance(row[6], int)
            or isinstance(row[6], bool)
            or not isinstance(row[8], int)
            or isinstance(row[8], bool)
        ):
            raise ContractViolation("kline times and trade count must be integers")
        if row[6] >= decision_at_ms:
            continue
        spot_proxy = source is MarketSource.SPOT_PROXY
        parsed.append(
            Candle(
                open_time=row[0],
                open=_decimal(row[1], "open"),
                high=_decimal(row[2], "high"),
                low=_decimal(row[3], "low"),
                close=_decimal(row[4], "close"),
                volume=UNKNOWN if spot_proxy else _decimal(row[5], "base volume"),
                close_time=row[6],
                quote_volume=(
                    UNKNOWN if spot_proxy else _decimal(row[7], "quote volume")
                ),
                number_of_trades=row[8],
                source=source,
                volume_unit=UNKNOWN if spot_proxy else "BASE_ASSET",
            )
        )
    parsed.sort(key=lambda candle: candle.open_time)
    if len({candle.open_time for candle in parsed}) != len(parsed):
        raise ContractViolation("duplicate kline open_time")
    if keep_last is not None:
        parsed = parsed[-keep_last:]
    return tuple(parsed)


@dataclass(frozen=True, slots=True)
class ContractRecord:
    symbol: str
    status: str
    contract_type: str
    base_asset: str
    quote_asset: str
    margin_asset: str


@dataclass(frozen=True, slots=True)
class ContractCatalog:
    """An immutable exact-symbol view of one Futures exchangeInfo response."""

    server_time_ms: int
    captured_at: datetime
    contracts: Mapping[str, ContractRecord]

    @classmethod
    def from_exchange_info(
        cls,
        payload: Mapping[str, Any],
        *,
        server_time_ms: int,
        captured_at: datetime | str,
    ) -> "ContractCatalog":
        rows = payload.get("symbols")
        if not isinstance(rows, list):
            raise ContractViolation("Futures exchangeInfo must contain a symbols list")
        if not isinstance(server_time_ms, int) or isinstance(server_time_ms, bool):
            raise ContractViolation("Futures server time must be integer milliseconds")

        contracts: dict[str, ContractRecord] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise ContractViolation("Futures symbol record must be an object")
            required = (
                "symbol",
                "status",
                "contractType",
                "baseAsset",
                "quoteAsset",
                "marginAsset",
            )
            if any(not isinstance(row.get(key), str) or not row[key] for key in required):
                raise ContractViolation("Futures symbol record is missing identity fields")
            symbol = row["symbol"]
            if symbol in contracts:
                raise ContractViolation(f"duplicate Futures symbol: {symbol}")
            contracts[symbol] = ContractRecord(
                symbol=symbol,
                status=row["status"],
                contract_type=row["contractType"],
                base_asset=row["baseAsset"],
                quote_asset=row["quoteAsset"],
                margin_asset=row["marginAsset"],
            )
        return cls(
            server_time_ms=server_time_ms,
            captured_at=parse_utc(captured_at),
            contracts=MappingProxyType(contracts),
        )

    def require_trading(self, symbol: str) -> ContractRecord:
        record = self.contracts.get(symbol)
        if record is None or record.status != "TRADING":
            raise ContractViolation(f"active Futures contract not found: {symbol}")
        return record


class BinanceMarketClient:
    """Injectable client for the allowlisted Binance public GET market chain."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout: float = 10.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._transport = transport or _urllib_transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout = timeout

    def _captured_at(self) -> datetime:
        return parse_utc(self._clock())

    @staticmethod
    def _classify(response: HttpResponse) -> None:
        headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
        if response.status in (418, 429):
            raise MarketApiError(
                FailureKind.RATE_LIMITED,
                status=response.status,
                retry_after=headers.get("retry-after"),
            )
        if response.status == 451:
            raise MarketApiError(FailureKind.REGION_RESTRICTED, status=451)
        if 500 <= response.status <= 599:
            raise MarketApiError(
                FailureKind.UPSTREAM_UNAVAILABLE, status=response.status
            )
        if not 200 <= response.status <= 299:
            raise MarketApiError(FailureKind.HTTP_ERROR, status=response.status)

    def _get_json(
        self, origin: str, path: str, params: Mapping[str, str | int] | None = None
    ) -> Any:
        if origin not in (FUTURES_ORIGIN, SPOT_ORIGIN):
            raise ValueError("origin is not allowlisted")
        query = f"?{urlencode(params)}" if params else ""
        try:
            response = self._transport(f"{origin}{path}{query}", self._timeout)
        except TimeoutError as exc:
            raise MarketApiError(FailureKind.TIMEOUT) from exc
        except OSError as exc:
            raise MarketApiError(FailureKind.UPSTREAM_UNAVAILABLE) from exc
        if not isinstance(response, HttpResponse):
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        self._classify(response)
        try:
            body = response.body.decode("utf-8") if isinstance(response.body, bytes) else response.body
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise MarketApiError(FailureKind.INVALID_RESPONSE) from exc

    def fetch_futures_catalog(self) -> ContractCatalog:
        time_payload = self._get_json(FUTURES_ORIGIN, "/fapi/v1/time")
        if not isinstance(time_payload, Mapping):
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        server_time_ms = time_payload.get("serverTime")
        if not isinstance(server_time_ms, int) or isinstance(server_time_ms, bool):
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        exchange_info = self._get_json(FUTURES_ORIGIN, "/fapi/v1/exchangeInfo")
        if not isinstance(exchange_info, Mapping):
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        return ContractCatalog.from_exchange_info(
            exchange_info,
            server_time_ms=server_time_ms,
            captured_at=self._captured_at(),
        )

    def _fetch_candles(
        self,
        *,
        origin: str,
        path: str,
        symbol: str,
        decision_time_ms: int,
        source: MarketSource,
    ) -> Mapping[str, tuple[Candle, ...]]:
        candles: dict[str, tuple[Candle, ...]] = {}
        for interval in INTERVALS:
            payload = self._get_json(
                origin,
                path,
                {
                    "symbol": symbol,
                    "interval": interval,
                    "limit": 22,
                    "endTime": decision_time_ms - 1,
                },
            )
            candles[interval] = closed_klines(
                payload,
                decision_at_ms=decision_time_ms,
                source=source,
            )
        return MappingProxyType(candles)

    def _optional_json(
        self,
        path: str,
        params: Mapping[str, str | int],
        failures: list[FailureKind],
    ) -> Any | None:
        try:
            return self._get_json(FUTURES_ORIGIN, path, params)
        except MarketApiError as exc:
            if exc.kind in {
                FailureKind.RATE_LIMITED,
                FailureKind.REGION_RESTRICTED,
            }:
                raise
            failures.append(exc.kind)
            return None

    def fetch_futures_snapshot(
        self,
        symbol: str,
        *,
        catalog: ContractCatalog | None = None,
        decision_time_ms: int | None = None,
    ) -> MarketSnapshot:
        catalog = catalog or self.fetch_futures_catalog()
        contract = catalog.require_trading(symbol)
        cutoff_ms = _decision_time_ms(
            decision_time_ms,
            maximum_ms=catalog.server_time_ms,
        )
        price_payload = self._get_json(
            FUTURES_ORIGIN, "/fapi/v2/ticker/price", {"symbol": symbol}
        )
        if not isinstance(price_payload, Mapping) or price_payload.get("symbol") != symbol:
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        last_price = _decimal(price_payload.get("price"), "last price")
        candles = self._fetch_candles(
            origin=FUTURES_ORIGIN,
            path="/fapi/v1/klines",
            symbol=symbol,
            decision_time_ms=cutoff_ms,
            source=MarketSource.FUTURES,
        )

        failures: list[FailureKind] = []
        missing: list[str] = []
        premium = self._optional_json(
            "/fapi/v1/premiumIndex", {"symbol": symbol}, failures
        )
        if isinstance(premium, Mapping) and premium.get("symbol") == symbol:
            mark_price: Decimal | str = _decimal(premium.get("markPrice"), "mark price")
            index_price: Decimal | str = _decimal(premium.get("indexPrice"), "index price")
            funding_rate: Decimal | str = _decimal(
                premium.get("lastFundingRate"), "funding rate"
            )
        else:
            mark_price = index_price = funding_rate = UNKNOWN
            missing.extend(("mark_price", "index_price", "funding_rate"))

        ticker = self._optional_json(
            "/fapi/v1/ticker/24hr", {"symbol": symbol}, failures
        )
        if isinstance(ticker, Mapping) and ticker.get("symbol") == symbol:
            base_volume: Decimal | str = _decimal(ticker.get("volume"), "base volume")
            quote_volume: Decimal | str = _decimal(
                ticker.get("quoteVolume"), "quote volume"
            )
        else:
            base_volume = quote_volume = UNKNOWN
            missing.extend(("base_volume_24h", "quote_volume_24h"))

        interest = self._optional_json(
            "/fapi/v1/openInterest", {"symbol": symbol}, failures
        )
        if isinstance(interest, Mapping) and interest.get("symbol") == symbol:
            open_interest: Decimal | str = _decimal(
                interest.get("openInterest"), "open interest"
            )
        else:
            open_interest = UNKNOWN
            missing.append("open_interest")

        return MarketSnapshot(
            symbol=symbol,
            contract=contract,
            source=MarketSource.FUTURES,
            decision_time_ms=cutoff_ms,
            captured_at=self._captured_at(),
            last_price=last_price,
            mark_price=mark_price,
            index_price=index_price,
            funding_rate=funding_rate,
            open_interest=open_interest,
            base_volume_24h=base_volume,
            quote_volume_24h=quote_volume,
            candles=candles,
            missing_fields=tuple(missing),
            failures=tuple(failures),
        )

    def fetch_spot_proxy_snapshot(
        self,
        symbol: str,
        *,
        catalog: ContractCatalog,
        decision_time_ms: int | None = None,
    ) -> MarketSnapshot:
        """Proxy only price/OHLC after the Futures catalog verified the symbol."""

        contract = catalog.require_trading(symbol)
        time_payload = self._get_json(SPOT_ORIGIN, "/api/v3/time")
        if not isinstance(time_payload, Mapping):
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        spot_time = time_payload.get("serverTime")
        if not isinstance(spot_time, int) or isinstance(spot_time, bool):
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        cutoff_ms = _decision_time_ms(
            decision_time_ms,
            maximum_ms=min(catalog.server_time_ms, spot_time),
        )
        price_payload = self._get_json(
            SPOT_ORIGIN, "/api/v3/ticker/price", {"symbol": symbol}
        )
        if not isinstance(price_payload, Mapping) or price_payload.get("symbol") != symbol:
            raise MarketApiError(FailureKind.INVALID_RESPONSE)
        candles = self._fetch_candles(
            origin=SPOT_ORIGIN,
            path="/api/v3/klines",
            symbol=symbol,
            decision_time_ms=cutoff_ms,
            source=MarketSource.SPOT_PROXY,
        )
        missing = (
            "mark_price",
            "index_price",
            "funding_rate",
            "open_interest",
            "base_volume_24h",
            "quote_volume_24h",
        )
        return MarketSnapshot(
            symbol=symbol,
            contract=contract,
            source=MarketSource.SPOT_PROXY,
            decision_time_ms=cutoff_ms,
            captured_at=self._captured_at(),
            last_price=_decimal(price_payload.get("price"), "Spot proxy price"),
            mark_price=UNKNOWN,
            index_price=UNKNOWN,
            funding_rate=UNKNOWN,
            open_interest=UNKNOWN,
            base_volume_24h=UNKNOWN,
            quote_volume_24h=UNKNOWN,
            candles=candles,
            missing_fields=missing,
            failures=(),
        )

    def fetch_snapshot(
        self,
        symbol: str,
        *,
        catalog: ContractCatalog | None = None,
        allow_spot_proxy: bool = True,
        decision_time_ms: int | None = None,
    ) -> MarketSnapshot:
        catalog = catalog or self.fetch_futures_catalog()
        catalog.require_trading(symbol)
        try:
            return self.fetch_futures_snapshot(
                symbol,
                catalog=catalog,
                decision_time_ms=decision_time_ms,
            )
        except MarketApiError as exc:
            can_proxy = exc.kind in {
                FailureKind.TIMEOUT,
                FailureKind.UPSTREAM_UNAVAILABLE,
            }
            if not allow_spot_proxy or not can_proxy:
                raise
            snapshot = self.fetch_spot_proxy_snapshot(
                symbol,
                catalog=catalog,
                decision_time_ms=decision_time_ms,
            )
            return MarketSnapshot(
                symbol=snapshot.symbol,
                contract=snapshot.contract,
                source=snapshot.source,
                decision_time_ms=snapshot.decision_time_ms,
                captured_at=snapshot.captured_at,
                last_price=snapshot.last_price,
                mark_price=snapshot.mark_price,
                index_price=snapshot.index_price,
                funding_rate=snapshot.funding_rate,
                open_interest=snapshot.open_interest,
                base_volume_24h=snapshot.base_volume_24h,
                quote_volume_24h=snapshot.quote_volume_24h,
                candles=snapshot.candles,
                missing_fields=snapshot.missing_fields,
                failures=(exc.kind,),
            )
