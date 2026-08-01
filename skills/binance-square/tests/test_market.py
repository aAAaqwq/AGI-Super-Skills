from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

from scanner.contracts import ContractViolation
from scanner.market import (
    BinanceMarketClient,
    ContractCatalog,
    FailureKind,
    HttpResponse,
    MarketApiError,
    MarketSource,
    UNKNOWN,
    closed_klines,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "m4"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def fixture_catalog() -> ContractCatalog:
    fixture = load_fixture("futures_api_snapshot.json")
    return ContractCatalog.from_exchange_info(
        {"symbols": fixture["catalog"]["selected_records"]},
        server_time_ms=fixture["authoritative_server_time_ms"],
        captured_at="2026-08-01T07:03:53.228Z",
    )


def json_response(payload: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status, json.dumps(payload).encode(), {})


class PointInTimeContractCatalogTests(unittest.TestCase):
    def test_fixture_catalog_proves_exact_active_btc_and_sol_contracts(self) -> None:
        fixture = load_fixture("futures_api_snapshot.json")
        catalog = ContractCatalog.from_exchange_info(
            {"symbols": fixture["catalog"]["selected_records"]},
            server_time_ms=fixture["authoritative_server_time_ms"],
            captured_at=datetime(2026, 8, 1, 7, 3, 53, 228000, tzinfo=timezone.utc),
        )

        btc = catalog.require_trading("BTCUSDT")
        sol = catalog.require_trading("SOLUSDT")

        self.assertEqual("PERPETUAL", btc.contract_type)
        self.assertEqual("USDT", btc.quote_asset)
        self.assertEqual("USDT", sol.margin_asset)
        self.assertEqual(1785567833227, catalog.server_time_ms)
        with self.assertRaises(ContractViolation):
            catalog.require_trading("BTC")


class ClosedKlineTests(unittest.TestCase):
    def test_all_four_fixture_intervals_exclude_the_open_candle(self) -> None:
        fixture = load_fixture("futures_api_snapshot.json")
        decision_at_ms = fixture["authoritative_server_time_ms"]

        for symbol in ("BTCUSDT", "SOLUSDT"):
            for interval in ("15m", "1h", "4h", "1d"):
                with self.subTest(symbol=symbol, interval=interval):
                    raw = fixture["klines"][symbol][interval]["raw_body"]
                    candles = closed_klines(
                        raw,
                        decision_at_ms=decision_at_ms,
                        source=MarketSource.FUTURES,
                    )

                    self.assertEqual(2, len(candles))
                    self.assertTrue(all(c.close_time < decision_at_ms for c in candles))
                    self.assertEqual(raw[-2][0], candles[-1].open_time)
                    self.assertEqual("BASE_ASSET", candles[-1].volume_unit)


class PublicClientFailureTests(unittest.TestCase):
    def test_http_and_timeout_failures_have_stable_safe_classifications(self) -> None:
        cases = (
            (HttpResponse(418, b"{}", {}), FailureKind.RATE_LIMITED),
            (HttpResponse(429, b"{}", {"Retry-After": "7"}), FailureKind.RATE_LIMITED),
            (HttpResponse(451, b"{}", {}), FailureKind.REGION_RESTRICTED),
            (TimeoutError(), FailureKind.TIMEOUT),
        )
        for outcome, expected in cases:
            with self.subTest(expected=expected):
                def transport(url: str, timeout: float, value=outcome) -> HttpResponse:
                    if isinstance(value, BaseException):
                        raise value
                    return value

                client = BinanceMarketClient(
                    transport=transport,
                    clock=lambda: datetime(2026, 8, 1, tzinfo=timezone.utc),
                )
                with self.assertRaises(MarketApiError) as caught:
                    client.fetch_futures_catalog()

                self.assertEqual(expected, caught.exception.kind)


class MarketSnapshotFixtureTests(unittest.TestCase):
    def test_btc_snapshot_is_futures_sourced_and_complete(self) -> None:
        fixture = load_fixture("futures_api_snapshot.json")
        market = fixture["current_market"]["BTCUSDT"]
        requested_urls: list[str] = []

        def transport(url: str, timeout: float) -> HttpResponse:
            requested_urls.append(url)
            parsed = urlsplit(url)
            query = parse_qs(parsed.query)
            if parsed.path == "/fapi/v2/ticker/price":
                return json_response(market["last_price_v2"])
            if parsed.path == "/fapi/v1/klines":
                return json_response(
                    fixture["klines"]["BTCUSDT"][query["interval"][0]]["raw_body"]
                )
            if parsed.path == "/fapi/v1/premiumIndex":
                return json_response(market["mark_price"])
            if parsed.path == "/fapi/v1/ticker/24hr":
                return json_response(market["ticker_24h"])
            if parsed.path == "/fapi/v1/openInterest":
                return json_response(market["open_interest"])
            raise AssertionError(f"unexpected URL {url}")

        explicit_cutoff_ms = 1785567600000
        snapshot = BinanceMarketClient(
            transport=transport,
            clock=lambda: datetime(2026, 8, 1, 7, 5, tzinfo=timezone.utc),
        ).fetch_futures_snapshot(
            "BTCUSDT",
            catalog=fixture_catalog(),
            decision_time_ms=explicit_cutoff_ms,
        )

        self.assertEqual(MarketSource.FUTURES, snapshot.source)
        self.assertEqual("63057.20", str(snapshot.last_price))
        self.assertEqual("139503.896", str(snapshot.base_volume_24h))
        self.assertEqual("8811171973.50", str(snapshot.quote_volume_24h))
        self.assertEqual(Decimal("1"), snapshot.completeness_ratio)
        self.assertEqual(explicit_cutoff_ms, snapshot.decision_time_ms)
        self.assertTrue(all(len(snapshot.candles[interval]) == 2 for interval in snapshot.candles))
        self.assertTrue(all(
            candle.close_time < explicit_cutoff_ms
            for values in snapshot.candles.values()
            for candle in values
        ))
        self.assertTrue(all("limit=22" in url for url in requested_urls if "klines" in url))
        expected_end = str(explicit_cutoff_ms - 1)
        self.assertTrue(
            all(
                parse_qs(urlsplit(url).query).get("endTime") == [expected_end]
                for url in requested_urls
                if "klines" in url
            )
        )
        self.assertFalse(any("api.binance.com/api" in url for url in requested_urls))

    def test_spot_proxy_preserves_only_price_and_closed_ohlc(self) -> None:
        fixture = load_fixture("spot_proxy_snapshot.json")

        def transport(url: str, timeout: float) -> HttpResponse:
            parsed = urlsplit(url)
            query = parse_qs(parsed.query)
            if parsed.path == "/api/v3/time":
                return json_response({"serverTime": fixture["authoritative_server_time_ms"]})
            if parsed.path == "/api/v3/ticker/price":
                return json_response(fixture["price"]["body"])
            if parsed.path == "/api/v3/klines":
                return json_response(fixture["klines"][query["interval"][0]]["raw_body"])
            raise AssertionError(f"unexpected URL {url}")

        snapshot = BinanceMarketClient(
            transport=transport,
            clock=lambda: datetime(2026, 8, 1, 7, 6, tzinfo=timezone.utc),
        ).fetch_spot_proxy_snapshot("SOLUSDT", catalog=fixture_catalog())

        self.assertEqual(MarketSource.SPOT_PROXY, snapshot.source)
        self.assertEqual(Decimal("73.00000000"), snapshot.last_price)
        self.assertEqual(UNKNOWN, snapshot.mark_price)
        self.assertEqual(UNKNOWN, snapshot.index_price)
        self.assertEqual(UNKNOWN, snapshot.funding_rate)
        self.assertEqual(UNKNOWN, snapshot.open_interest)
        self.assertEqual(UNKNOWN, snapshot.base_volume_24h)
        self.assertEqual(UNKNOWN, snapshot.quote_volume_24h)
        self.assertTrue(
            all(
                candle.volume == UNKNOWN and candle.quote_volume == UNKNOWN
                for candles in snapshot.candles.values()
                for candle in candles
            )
        )


if __name__ == "__main__":
    unittest.main()
