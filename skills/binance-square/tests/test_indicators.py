from decimal import Decimal
import unittest

from scanner.indicators import (
    average_true_range,
    bollinger_bands,
    calculate_indicators,
    volume_evidence,
)
from scanner.market import UNKNOWN, Candle, MarketSource


def candle(
    index: int,
    *,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: Decimal = Decimal("1"),
    source: MarketSource = MarketSource.FUTURES,
) -> Candle:
    return Candle(
        open_time=index * 60_000,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=volume,
        close_time=(index + 1) * 60_000 - 1,
        quote_volume=volume * close,
        number_of_trades=1,
        source=source,
        volume_unit="BASE_ASSET",
    )


class BollingerBandTests(unittest.TestCase):
    def test_bb20_population_golden_vector_includes_percent_b_and_bandwidth(self) -> None:
        closes = [Decimal(value) for value in range(1, 21)]

        result = bollinger_bands(closes)

        self.assertEqual(Decimal("10.5"), result.middle)
        self.assertEqual(
            Decimal("22.03256259467079588935418324"), result.upper
        )
        self.assertEqual(
            Decimal("-1.03256259467079588935418324"), result.lower
        )
        self.assertEqual(
            Decimal("0.9118772355239569960483636871"), result.percent_b
        )
        self.assertEqual(
            Decimal("2.196678589461103978924606331"), result.bandwidth
        )


class AverageTrueRangeTests(unittest.TestCase):
    def test_atr14_golden_vector_uses_a_previous_close(self) -> None:
        candles = [
            candle(0, high=Decimal("100"), low=Decimal("100"), close=Decimal("100"))
        ]
        candles.extend(
            candle(
                index,
                high=Decimal(100 + index),
                low=Decimal("100"),
                close=Decimal("100"),
            )
            for index in range(1, 15)
        )

        self.assertEqual(Decimal("7.5"), average_true_range(candles))


class VolumeEvidenceTests(unittest.TestCase):
    def test_futures_volume_ratio_compares_latest_base_volume_to_prior_20(self) -> None:
        candles = [
            candle(
                index,
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("31.5") if index == 20 else Decimal(index + 1),
            )
            for index in range(20)
        ]
        candles.append(
            candle(
                20,
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("30"),
            )
        )

        result = volume_evidence(candles)

        self.assertEqual(Decimal("30"), result.current)
        self.assertEqual(Decimal("10.5"), result.prior_average)
        self.assertEqual(Decimal("2.857142857142857142857142857"), result.ratio)
        self.assertEqual("BASE_ASSET", result.unit)

    def test_spot_proxy_volume_is_unknown_even_when_spot_api_has_numbers(self) -> None:
        candles = [
            candle(
                index,
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("999999"),
                source=MarketSource.SPOT_PROXY,
            )
            for index in range(21)
        ]

        result = volume_evidence(candles)

        self.assertEqual(UNKNOWN, result.current)
        self.assertEqual(UNKNOWN, result.prior_average)
        self.assertEqual(UNKNOWN, result.ratio)
        self.assertEqual(UNKNOWN, result.unit)


class IndicatorEvidenceTests(unittest.TestCase):
    def test_closed_futures_candles_produce_one_coherent_indicator_record(self) -> None:
        candles = [
            candle(
                index,
                high=Decimal(index + 2),
                low=Decimal(index),
                close=Decimal(index + 1),
                volume=Decimal("31.5") if index == 20 else Decimal(index + 1),
            )
            for index in range(21)
        ]

        result = calculate_indicators(candles)

        self.assertEqual(candles[-1].close_time, result.as_of_close_time)
        self.assertEqual(candles[-1].close, result.close)
        self.assertEqual(Decimal("2"), result.atr)
        self.assertEqual(Decimal("3.0"), result.volume.ratio)
        self.assertEqual(20, result.bollinger.period)


if __name__ == "__main__":
    unittest.main()
