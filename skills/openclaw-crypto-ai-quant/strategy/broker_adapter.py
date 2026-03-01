"""AQC-815: Broker adapter translating kernel OrderIntent to Hyperliquid orders.

Provides a ``BrokerAdapter`` class that:

1. Takes kernel ``OrderIntent`` dicts (from ``DecisionResult.intents``) and routes
   them to the appropriate Hyperliquid exchange operation (market_open, market_close).
2. Returns ``FillEvent`` dicts matching the kernel schema so fills can be fed back
   to the kernel's state.
3. Handles szDecimals rounding, slippage application, rate limiting, and exchange
   error handling.

The adapter is exchange-client agnostic: it calls methods on a duck-typed
``exchange_client`` (see ``HyperliquidLiveExecutor`` for the production impl).
"""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Kernel schema version — must match ``KERNEL_SCHEMA_VERSION`` in Rust.
KERNEL_SCHEMA_VERSION = 1

#: Default slippage percentage applied to limit prices.
DEFAULT_SLIPPAGE_PCT = 0.001  # 0.1%

#: Default minimum delay between consecutive exchange submissions (seconds).
DEFAULT_RATE_LIMIT_DELAY_S = 0.25

#: Default number of retry attempts for transient exchange errors.
DEFAULT_MAX_RETRIES = 2

#: Default retry backoff base (seconds); actual delay = base * 2^attempt.
DEFAULT_RETRY_BACKOFF_S = 0.5

#: Default hard cap for notional per open/add/reverse intent (USD).
DEFAULT_MAX_NOTIONAL_USD = 1_000_000.0

#: Default hard cap for quantity per open/add/reverse intent (base units).
DEFAULT_MAX_QUANTITY = 1_000_000.0


# ---------------------------------------------------------------------------
# Exchange client protocol (duck-typing contract)
# ---------------------------------------------------------------------------


@runtime_checkable
class ExchangeClient(Protocol):
    """Minimal interface expected from the exchange client.

    The production implementation is ``HyperliquidLiveExecutor`` from
    ``exchange.executor``.  For testing, any object satisfying this protocol
    (or a ``MagicMock`` with appropriate return values) suffices.
    """

    def market_open(
        self,
        symbol: str,
        *,
        is_buy: bool,
        sz: float,
        px: float | None = None,
        slippage_pct: float,
        cloid: str | None = None,
    ) -> dict | None: ...

    def market_close(
        self,
        symbol: str,
        *,
        is_buy: bool,
        sz: float,
        px: float | None = None,
        slippage_pct: float,
        cloid: str | None = None,
    ) -> dict | None: ...


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def intent_to_hl_side(side_str: str) -> bool:
    """Map kernel PositionSide string to Hyperliquid ``is_buy`` flag.

    Kernel uses serde ``rename_all = "snake_case"`` so values are lowercase.

    Opening a Long  -> buy  (is_buy=True)
    Opening a Short -> sell (is_buy=False)

    For *close* intents the direction is reversed by the caller.
    """
    normalised = str(side_str or "").strip().lower()
    if normalised in ("long",):
        return True
    if normalised in ("short",):
        return False
    raise ValueError(f"Unknown PositionSide: {side_str!r}")


def intent_type(intent: dict[str, Any]) -> str:
    """Classify an ``OrderIntent`` dict into an action type.

    Returns one of: ``"open"``, ``"add"``, ``"close"``, ``"partial_close"``,
    ``"hold"``, ``"reverse"``.

    Partial close is inferred from kind == ``"close"`` with a
    ``close_fraction`` field present and < 1.0.
    """
    kind = str(intent.get("kind", "")).strip().lower()
    if kind == "open":
        return "open"
    if kind == "add":
        return "add"
    if kind == "close":
        frac = intent.get("close_fraction")
        if frac is not None:
            try:
                frac_f = float(frac)
            except (TypeError, ValueError):
                frac_f = 1.0
            if 0.0 < frac_f < 1.0 - 1e-15:
                return "partial_close"
        return "close"
    if kind == "hold":
        return "hold"
    if kind == "reverse":
        return "reverse"
    raise ValueError(f"Unknown OrderIntentKind: {intent.get('kind')!r}")


# ---------------------------------------------------------------------------
# BrokerAdapter
# ---------------------------------------------------------------------------


class BrokerAdapterError(Exception):
    """Raised when an exchange operation fails irrecoverably."""

    def __init__(self, message: str, *, intent: dict | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.intent = intent
        self.cause = cause


class BrokerAdapter:
    """Translates kernel OrderIntents to Hyperliquid exchange orders.

    Parameters
    ----------
    exchange_client
        An object implementing the ``ExchangeClient`` protocol (e.g.
        ``HyperliquidLiveExecutor``).
    config : dict, optional
        Configuration overrides::

            {
                "slippage_pct": 0.001,        # default slippage
                "rate_limit_delay_s": 0.25,   # min delay between orders
                "max_retries": 2,             # retries on transient error
                "retry_backoff_s": 0.5,       # base backoff (exponential)
                "abort_batch_on_error": True,  # stop batch on first failure
                "max_notional_usd": 1_000_000.0,  # hard risk cap per intent
                "max_quantity": 1_000_000.0,      # hard size cap per intent
            }
    """

    def __init__(self, exchange_client: Any, config: dict[str, Any] | None = None):
        self._client = exchange_client
        cfg = config or {}

        self._slippage_pct: float = float(cfg.get("slippage_pct", DEFAULT_SLIPPAGE_PCT))
        self._rate_limit_delay_s: float = float(cfg.get("rate_limit_delay_s", DEFAULT_RATE_LIMIT_DELAY_S))
        self._max_retries: int = int(cfg.get("max_retries", DEFAULT_MAX_RETRIES))
        self._retry_backoff_s: float = float(cfg.get("retry_backoff_s", DEFAULT_RETRY_BACKOFF_S))
        self._abort_batch_on_error: bool = bool(cfg.get("abort_batch_on_error", True))
        self._max_notional_usd: float = float(cfg.get("max_notional_usd", DEFAULT_MAX_NOTIONAL_USD))
        self._max_quantity: float = float(cfg.get("max_quantity", DEFAULT_MAX_QUANTITY))
        if self._max_notional_usd <= 0.0:
            self._max_notional_usd = float("inf")
        if self._max_quantity <= 0.0:
            self._max_quantity = float("inf")

        # Timestamp of last order submission (for rate limiting).
        self._last_submit_ts: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_intent(
        self,
        intent: dict[str, Any],
        symbol_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single OrderIntent and return a FillEvent dict.

        Parameters
        ----------
        intent
            Kernel ``OrderIntent`` dict (from ``DecisionResult.intents``).
        symbol_info
            Optional dict with ``sz_decimals`` (int) for size rounding.
            If not provided, the adapter uses ``intent["quantity"]`` as-is
            or falls back to a sensible default.

        Returns
        -------
        dict
            A ``FillEvent`` dict matching the kernel schema.

        Raises
        ------
        BrokerAdapterError
            If the exchange rejects the order after all retries.
        """
        it = intent_type(intent)
        if it == "hold":
            logger.debug("execute_intent: hold intent — no exchange action")
            return self._build_fill_event(intent, intent.get("price", 0.0), 0.0, fee_usd=0.0)

        handler = {
            "open": self._execute_open,
            "add": self._execute_add,
            "close": self._execute_close,
            "partial_close": self._execute_partial_close,
            "reverse": self._execute_open,  # Reverse opens use same flow as open
        }.get(it)

        if handler is None:
            raise BrokerAdapterError(f"No handler for intent type: {it}", intent=intent)

        return handler(intent, symbol_info)

    def execute_intents(
        self,
        intents: list[dict[str, Any]],
        symbol_info: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Batch-execute multiple intents from a single kernel step.

        Respects rate limiting between consecutive submissions.

        Parameters
        ----------
        intents
            List of ``OrderIntent`` dicts.
        symbol_info
            Optional symbol metadata for size rounding.

        Returns
        -------
        list[dict]
            List of ``FillEvent`` dicts (one per successfully executed intent).
            If ``abort_batch_on_error`` is ``True``, stops at the first failure
            and raises.  Otherwise, logs the error and continues.
        """
        if not intents:
            return []

        fills: list[dict[str, Any]] = []
        for i, intent in enumerate(intents):
            # Rate limit: wait between submissions.
            if i > 0:
                self._rate_limit_wait()

            try:
                fill = self.execute_intent(intent, symbol_info=symbol_info)
                fills.append(fill)
            except BrokerAdapterError:
                if self._abort_batch_on_error:
                    raise
                logger.exception(
                    "execute_intents: intent %d/%d failed (continuing)", i + 1, len(intents)
                )

        return fills

    @staticmethod
    def build_fill_event_json(fill_event: dict[str, Any]) -> str:
        """Serialize a FillEvent dict to a JSON string for feeding back to the kernel."""
        return json.dumps(fill_event, separators=(",", ":"), sort_keys=True)

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def _execute_open(
        self,
        intent: dict[str, Any],
        symbol_info: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Place a new position (or reverse) order on Hyperliquid."""
        symbol = str(intent.get("symbol", "")).strip().upper()
        side_str = str(intent.get("side", ""))
        is_buy = intent_to_hl_side(side_str)
        price = float(intent.get("price", 0.0))
        quantity = float(intent.get("quantity", 0.0))

        if quantity <= 0.0 and price > 0.0:
            notional = float(intent.get("notional_usd", 0.0))
            if notional > 0.0:
                quantity = notional / price

        sz_decimals = self._get_sz_decimals(symbol_info)
        quantity = self._round_size(quantity, sz_decimals)
        if quantity <= 0.0:
            raise BrokerAdapterError(
                f"Open: computed quantity is zero for {symbol}", intent=intent
            )
        self._validate_open_risk_limits(intent=intent, symbol=symbol, quantity=quantity, price=price)

        limit_price = self._apply_slippage(price, is_buy)

        logger.info(
            "broker_open: %s %s sz=%.8f px=%.2f slip_px=%.2f",
            "BUY" if is_buy else "SELL", symbol, quantity, price, limit_price,
        )

        res = self._submit_with_retry(
            lambda: self._client.market_open(
                symbol, is_buy=is_buy, sz=quantity, px=limit_price,
                slippage_pct=self._slippage_pct,
            ),
            op_name=f"market_open({symbol})",
            intent=intent,
        )

        fill_price = self._extract_fill_price(res, fallback=price)
        fill_qty = self._extract_fill_quantity(res, fallback=quantity)
        fee_usd = self._estimate_fee(fill_price, fill_qty, intent)

        return self._build_fill_event(intent, fill_price, fill_qty, fee_usd=fee_usd)

    def _validate_open_risk_limits(
        self,
        *,
        intent: dict[str, Any],
        symbol: str,
        quantity: float,
        price: float,
    ) -> None:
        if quantity > self._max_quantity:
            msg = (
                f"Open: quantity {quantity:.8f} exceeds max_quantity {self._max_quantity:.8f} "
                f"for {symbol}"
            )
            logger.error(msg)
            raise BrokerAdapterError(msg, intent=intent)

        intent_notional = 0.0
        try:
            parsed_notional = float(intent.get("notional_usd", 0.0))
            if parsed_notional > 0.0:
                intent_notional = parsed_notional
        except (TypeError, ValueError):
            intent_notional = 0.0

        if intent_notional <= 0.0 and price > 0.0:
            intent_notional = quantity * price

        if intent_notional > self._max_notional_usd:
            msg = (
                f"Open: notional {intent_notional:.2f} exceeds max_notional_usd "
                f"{self._max_notional_usd:.2f} for {symbol}"
            )
            logger.error(msg)
            raise BrokerAdapterError(msg, intent=intent)

    def _execute_add(
        self,
        intent: dict[str, Any],
        symbol_info: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Add to an existing position (pyramid)."""
        # Pyramid uses the same exchange operation as open.
        return self._execute_open(intent, symbol_info)

    def _execute_close(
        self,
        intent: dict[str, Any],
        symbol_info: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Close a full position on Hyperliquid."""
        symbol = str(intent.get("symbol", "")).strip().upper()
        side_str = str(intent.get("side", ""))

        # For closing: if we are Long, we sell (is_buy=False);
        #              if we are Short, we buy (is_buy=True).
        is_buy_position = intent_to_hl_side(side_str)
        is_buy_close = not is_buy_position

        price = float(intent.get("price", 0.0))
        quantity = float(intent.get("quantity", 0.0))

        sz_decimals = self._get_sz_decimals(symbol_info)
        quantity = self._round_size(quantity, sz_decimals)
        if quantity <= 0.0:
            raise BrokerAdapterError(
                f"Close: computed quantity is zero for {symbol}", intent=intent
            )

        limit_price = self._apply_slippage(price, is_buy_close)

        logger.info(
            "broker_close: %s %s sz=%.8f px=%.2f slip_px=%.2f",
            "BUY" if is_buy_close else "SELL", symbol, quantity, price, limit_price,
        )

        res = self._submit_with_retry(
            lambda: self._client.market_close(
                symbol, is_buy=is_buy_close, sz=quantity, px=limit_price,
                slippage_pct=self._slippage_pct,
            ),
            op_name=f"market_close({symbol})",
            intent=intent,
        )

        fill_price = self._extract_fill_price(res, fallback=price)
        fill_qty = self._extract_fill_quantity(res, fallback=quantity)
        fee_usd = self._estimate_fee(fill_price, fill_qty, intent)

        return self._build_fill_event(intent, fill_price, fill_qty, fee_usd=fee_usd)

    def _execute_partial_close(
        self,
        intent: dict[str, Any],
        symbol_info: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Partially close a position."""
        # Partial close is the same as close mechanically — the kernel already
        # computed the appropriate ``quantity`` based on ``close_fraction``.
        return self._execute_close(intent, symbol_info)

    # ------------------------------------------------------------------
    # Slippage & rounding
    # ------------------------------------------------------------------

    def _apply_slippage(self, price: float, is_buy: bool, slippage_pct: float | None = None) -> float:
        """Apply slippage to a limit price.

        For buys the price is *increased* (willing to pay more);
        for sells it is *decreased* (willing to receive less).
        """
        return apply_slippage(price, is_buy, slippage_pct or self._slippage_pct)

    @staticmethod
    def _round_size(quantity: float, sz_decimals: int) -> float:
        """Round (truncate) quantity to the allowed exchange precision."""
        return round_size(quantity, sz_decimals)

    @staticmethod
    def _get_sz_decimals(symbol_info: dict[str, Any] | None) -> int:
        """Extract szDecimals from symbol_info or return a safe default."""
        if symbol_info is None:
            return 4  # conservative default
        try:
            return int(symbol_info.get("sz_decimals", 4))
        except (TypeError, ValueError):
            return 4

    # ------------------------------------------------------------------
    # Fill extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_fill_price(response: dict | None, *, fallback: float) -> float:
        """Best-effort extraction of the fill price from an exchange response.

        The Hyperliquid SDK response shape is:
        ``{"status":"ok","response":{"data":{"statuses":[{"filled":{"totalSz":"...",
        "avgPx":"..."}}]}}}``
        """
        if not isinstance(response, dict):
            return fallback
        try:
            statuses = (
                response.get("response", {})
                .get("data", {})
                .get("statuses", [])
            )
            for st in statuses:
                if isinstance(st, dict) and "filled" in st:
                    avg_px = st["filled"].get("avgPx")
                    if avg_px is not None:
                        px = float(avg_px)
                        if px > 0.0:
                            return px
        except Exception:
            pass
        return fallback

    @staticmethod
    def _extract_fill_quantity(response: dict | None, *, fallback: float) -> float:
        """Best-effort extraction of the filled quantity from an exchange response."""
        if not isinstance(response, dict):
            return fallback
        try:
            statuses = (
                response.get("response", {})
                .get("data", {})
                .get("statuses", [])
            )
            for st in statuses:
                if isinstance(st, dict) and "filled" in st:
                    total_sz = st["filled"].get("totalSz")
                    if total_sz is not None:
                        sz = float(total_sz)
                        if sz > 0.0:
                            return sz
        except Exception:
            pass
        return fallback

    @staticmethod
    def _estimate_fee(fill_price: float, fill_quantity: float, intent: dict[str, Any]) -> float:
        """Estimate the fee in USD from the intent fee_rate and fill values."""
        fee_rate = float(intent.get("fee_rate", 0.0))
        notional = fill_price * fill_quantity
        return round(notional * fee_rate, 6)

    # ------------------------------------------------------------------
    # FillEvent construction
    # ------------------------------------------------------------------

    def _build_fill_event(
        self,
        intent: dict[str, Any],
        fill_price: float,
        fill_quantity: float,
        *,
        fee_usd: float = 0.0,
    ) -> dict[str, Any]:
        """Construct a ``FillEvent`` dict matching the kernel schema.

        Schema (from ``bt-core/decision_kernel.rs``)::

            FillEvent {
                schema_version: u32,
                intent_id: u64,
                symbol: String,
                side: PositionSide,
                quantity: f64,
                price: f64,
                notional_usd: f64,
                fee_usd: f64,
                pnl_usd: f64,
            }
        """
        return build_fill_event(
            intent=intent,
            fill_price=fill_price,
            fill_quantity=fill_quantity,
            fee_usd=fee_usd,
        )

    # ------------------------------------------------------------------
    # Retry / rate-limit
    # ------------------------------------------------------------------

    def _submit_with_retry(
        self,
        submit_fn,
        *,
        op_name: str,
        intent: dict[str, Any],
    ) -> dict:
        """Submit an exchange operation with retry on transient failures.

        Returns the raw exchange response dict on success.
        Raises ``BrokerAdapterError`` on exhausted retries.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 2):  # +2: first try + retries
            try:
                self._rate_limit_wait()
                res = submit_fn()
                if res is not None:
                    logger.debug("%s succeeded on attempt %d", op_name, attempt)
                    return res
                # None result means rejection — treat as non-retriable.
                raise BrokerAdapterError(
                    f"{op_name} rejected by exchange (returned None)",
                    intent=intent,
                )
            except BrokerAdapterError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt <= self._max_retries:
                    delay = self._retry_backoff_s * (2 ** (attempt - 1))
                    logger.warning(
                        "%s attempt %d failed (%s), retrying in %.2fs",
                        op_name, attempt, exc, delay,
                    )
                    time.sleep(delay)
                else:
                    break

        raise BrokerAdapterError(
            f"{op_name} failed after {self._max_retries + 1} attempts",
            intent=intent,
            cause=last_exc,
        )

    def _rate_limit_wait(self) -> None:
        """Enforce minimum delay between consecutive exchange submissions."""
        if self._rate_limit_delay_s <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_submit_ts
        if elapsed < self._rate_limit_delay_s:
            remaining = self._rate_limit_delay_s - elapsed
            time.sleep(remaining)
        self._last_submit_ts = time.monotonic()


# ---------------------------------------------------------------------------
# Module-level utility functions (also used in tests)
# ---------------------------------------------------------------------------


def apply_slippage(price: float, is_buy: bool, slippage_pct: float = DEFAULT_SLIPPAGE_PCT) -> float:
    """Apply slippage to a limit price.

    Buy  -> price * (1 + slippage_pct)
    Sell -> price * (1 - slippage_pct)
    """
    if slippage_pct < 0.0:
        slippage_pct = 0.0
    if is_buy:
        return price * (1.0 + slippage_pct)
    return price * (1.0 - slippage_pct)


def round_size(quantity: float, sz_decimals: int) -> float:
    """Round (truncate DOWN) quantity to *sz_decimals* decimal places.

    This matches the Hyperliquid convention: sizes must not exceed the
    allowed precision.
    """
    if quantity <= 0.0:
        return 0.0
    if sz_decimals < 0:
        sz_decimals = 0
    try:
        quantum = Decimal("1").scaleb(-int(sz_decimals))
        return float(Decimal(str(quantity)).quantize(quantum, rounding=ROUND_DOWN))
    except (InvalidOperation, ValueError, OverflowError):
        return 0.0


def build_fill_event(
    *,
    intent: dict[str, Any],
    fill_price: float,
    fill_quantity: float,
    fee_usd: float = 0.0,
    pnl_usd: float = 0.0,
) -> dict[str, Any]:
    """Construct a ``FillEvent`` dict matching the kernel Rust schema.

    Fields mirror ``FillEvent`` from ``bt-core/decision_kernel.rs``.
    """
    notional_usd = fill_price * fill_quantity
    return {
        "schema_version": int(intent.get("schema_version", KERNEL_SCHEMA_VERSION)),
        "intent_id": int(intent.get("intent_id", 0)),
        "symbol": str(intent.get("symbol", "")).upper(),
        "side": str(intent.get("side", "")).lower(),
        "quantity": float(fill_quantity),
        "price": float(fill_price),
        "notional_usd": round(float(notional_usd), 6),
        "fee_usd": round(float(fee_usd), 6),
        "pnl_usd": round(float(pnl_usd), 6),
    }
