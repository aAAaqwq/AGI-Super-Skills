//! Main simulation loop for the backtesting engine.
//!
//! Processes all symbols bar-by-bar in chronological order, orchestrating the
//! full trading lifecycle: indicator warmup → exit checks → gate evaluation →
//! signal generation → engine-level transforms → entry execution → PnL.

use crate::accounting;
use crate::candle::{CandleData, FundingRateData, OhlcvBar};
use crate::config::{Confidence, Signal, StrategyConfig};
use crate::decision_kernel;
use crate::exits::ExitResult;
use crate::indicators::{IndicatorBank, IndicatorSnapshot};
use crate::kernel_exits::{self, ExitParams, KernelExitResult};
use crate::position::{ExitContext, Position, PositionType, SignalRecord, TradeRecord};
use crate::signals::{entry, gates};
use risk_core::{
    compute_entry_sizing, compute_pyramid_sizing, evaluate_exposure_guard, ConfidenceTier,
    EntrySizingInput, ExposureBlockReason, ExposureGuardInput, PyramidSizingInput,
};
use rustc_hash::FxHashMap;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Public result types
// ---------------------------------------------------------------------------

/// Aggregate statistics about gate-level blocking.
#[derive(Debug, Clone, Default)]
pub struct GateStats {
    pub total_checks: u64,
    pub neutral_count: u64,
    pub buy_count: u64,
    pub sell_count: u64,
    pub blocked_by_ranging: u64,
    pub blocked_by_anomaly: u64,
    pub blocked_by_extension: u64,
    pub blocked_by_adx_low: u64,
    pub blocked_by_adx_not_rising: u64,
    pub blocked_by_volume: u64,
    pub blocked_by_btc: u64,
    pub blocked_by_confidence: u64,
    pub blocked_by_max_positions: u64,
    pub blocked_by_pesc: u64,
    pub blocked_by_ssf: u64,
    pub blocked_by_reef: u64,
    pub blocked_by_margin: u64,
}

/// Complete output of a simulation run.
pub struct SimResult {
    pub trades: Vec<TradeRecord>,
    pub signals: Vec<SignalRecord>,
    pub decision_diagnostics: Vec<DecisionKernelTrace>,
    pub final_balance: f64,
    pub equity_curve: Vec<(i64, f64)>,
    pub gate_stats: GateStats,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DecisionKernelIntentSummary {
    kind: String,
    side: String,
    symbol: String,
    quantity: f64,
    price: f64,
    notional_usd: f64,
    fee_rate: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DecisionKernelFillSummary {
    side: String,
    symbol: String,
    quantity: f64,
    price: f64,
    notional_usd: f64,
    fee_usd: f64,
    pnl_usd: f64,
}

/// Detail of a single gate evaluation during entry signal processing.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GateCheck {
    pub gate_name: String,
    pub passed: bool,
    pub actual_value: f64,
    pub threshold_value: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

/// Per-signal gate evaluation chain — captures which gates were checked,
/// what values were compared, and which gate (if any) blocked the signal.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GateEvaluation {
    pub passed: bool,
    pub checked_gates: Vec<GateCheck>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DecisionKernelTrace {
    event_id: u64,
    source: String,
    timestamp_ms: i64,
    symbol: String,
    signal: String,
    requested_notional_usd: f64,
    requested_price: f64,
    schema_version: u32,
    step: u64,
    state_step: u64,
    state_cash_usd: f64,
    state_positions: usize,
    intent_count: usize,
    fill_count: usize,
    warnings: Vec<String>,
    errors: Vec<String>,
    intents: Vec<DecisionKernelIntentSummary>,
    fills: Vec<DecisionKernelFillSummary>,
    applied_to_kernel_state: bool,
    #[serde(default)]
    active_params: HashMap<String, f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    gate_result: Option<GateEvaluation>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    indicator_snapshot: Option<IndicatorSnapshot>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    config_fingerprint: Option<String>,
}

impl DecisionKernelTrace {
    pub fn set_config_fingerprint(&mut self, config_fingerprint: String) {
        self.config_fingerprint = Some(config_fingerprint);
    }
}

// ---------------------------------------------------------------------------
// Entry candidate for signal ranking
// ---------------------------------------------------------------------------

struct EntryCandidate {
    symbol: String,
    signal: Signal,
    confidence: Confidence,
    adx: f64,
    atr: f64,
    entry_adx_threshold: f64,
    snap: IndicatorSnapshot,
    ts: i64,
    gate_eval: GateEvaluation,
}

// ---------------------------------------------------------------------------
// Internal simulation state
// ---------------------------------------------------------------------------

struct SimState {
    balance: f64,
    positions: FxHashMap<String, Position>,
    /// Per-symbol successful entry/add timestamps (ms) for entry cooldown.
    last_entry_attempt_ms: FxHashMap<String, i64>,
    /// Per-symbol successful exit timestamps (ms) for exit cooldown.
    last_exit_attempt_ms: FxHashMap<String, i64>,
    indicators: FxHashMap<String, IndicatorBank>,
    /// EMA slow history per symbol (for slow-drift slope computation).
    ema_slow_history: FxHashMap<String, Vec<f64>>,
    /// Per-symbol bar counter (tracks warmup independently from IndicatorBank).
    bar_counts: FxHashMap<String, usize>,
    /// PESC: last close (timestamp_ms, position_type, exit_reason) per symbol.
    last_close: FxHashMap<String, (i64, PositionType, String)>,
    trades: Vec<TradeRecord>,
    signals: Vec<SignalRecord>,
    decision_diagnostics: Vec<DecisionKernelTrace>,
    kernel_state: decision_kernel::StrategyState,
    kernel_params: decision_kernel::KernelParams,
    next_kernel_event_id: u64,
    equity_curve: Vec<(i64, f64)>,
    gate_stats: GateStats,
}

/// Build kernel ExitParams from StrategyConfig trade fields.
fn build_exit_params(cfg: &StrategyConfig) -> ExitParams {
    let t = &cfg.trade;
    ExitParams {
        sl_atr_mult: t.sl_atr_mult,
        tp_atr_mult: t.tp_atr_mult,
        trailing_start_atr: t.trailing_start_atr,
        trailing_distance_atr: t.trailing_distance_atr,
        enable_partial_tp: t.enable_partial_tp,
        tp_partial_pct: t.tp_partial_pct,
        tp_partial_atr_mult: t.tp_partial_atr_mult,
        tp_partial_min_notional_usd: t.tp_partial_min_notional_usd,
        enable_breakeven_stop: t.enable_breakeven_stop,
        breakeven_start_atr: t.breakeven_start_atr,
        breakeven_buffer_atr: t.breakeven_buffer_atr,
        enable_vol_buffered_trailing: t.enable_vol_buffered_trailing,
        block_exits_on_extreme_dev: t.block_exits_on_extreme_dev,
        glitch_price_dev_pct: t.glitch_price_dev_pct,
        glitch_atr_mult: t.glitch_atr_mult,
        smart_exit_adx_exhaustion_lt: t.smart_exit_adx_exhaustion_lt,
        tsme_min_profit_atr: t.tsme_min_profit_atr,
        tsme_require_adx_slope_negative: t.tsme_require_adx_slope_negative,
        enable_rsi_overextension_exit: t.enable_rsi_overextension_exit,
        rsi_exit_profit_atr_switch: t.rsi_exit_profit_atr_switch,
        rsi_exit_ub_lo_profit: t.rsi_exit_ub_lo_profit,
        rsi_exit_ub_hi_profit: t.rsi_exit_ub_hi_profit,
        rsi_exit_lb_lo_profit: t.rsi_exit_lb_lo_profit,
        rsi_exit_lb_hi_profit: t.rsi_exit_lb_hi_profit,
        rsi_exit_ub_lo_profit_low_conf: t.rsi_exit_ub_lo_profit_low_conf,
        rsi_exit_lb_lo_profit_low_conf: t.rsi_exit_lb_lo_profit_low_conf,
        rsi_exit_ub_hi_profit_low_conf: t.rsi_exit_ub_hi_profit_low_conf,
        rsi_exit_lb_hi_profit_low_conf: t.rsi_exit_lb_hi_profit_low_conf,
        smart_exit_adx_exhaustion_lt_low_conf: t.smart_exit_adx_exhaustion_lt_low_conf,
        require_macro_alignment: cfg.filters.require_macro_alignment,
        trailing_start_atr_low_conf: t.trailing_start_atr_low_conf,
        trailing_distance_atr_low_conf: t.trailing_distance_atr_low_conf,
    }
}

fn make_kernel_params(cfg: &StrategyConfig) -> decision_kernel::KernelParams {
    let mut kernel_params = decision_kernel::KernelParams::default();
    kernel_params.allow_pyramid = cfg.trade.enable_pyramiding;
    // Engine entry processing closes the existing position first when a reverse
    // signal arrives; keep this behaviour by disabling canonical reverses.
    kernel_params.allow_reverse = false;
    // Kernel cash-check leverage uses cfg.trade.leverage (the base/fallback
    // leverage), NOT the per-confidence-tier value.  This matches the GPU
    // sweep kernel which computes kernel_margin_req = notional / cfg.leverage.
    kernel_params.leverage = cfg.trade.leverage.max(1.0);
    kernel_params.exit_params = Some(build_exit_params(cfg));
    kernel_params
}

fn maker_taker_fee_rate(params: &decision_kernel::KernelParams, role: accounting::FeeRole) -> f64 {
    accounting::FeeModel {
        maker_fee_bps: params.maker_fee_bps,
        taker_fee_bps: params.taker_fee_bps,
    }
    .role_rate(role)
}

fn make_kernel_state(
    init_balance: f64,
    timestamp_ms: i64,
    positions: &FxHashMap<String, Position>,
) -> decision_kernel::StrategyState {
    let mut kernel_state = decision_kernel::StrategyState::new(init_balance, timestamp_ms);
    for sym in sorted_position_symbols(positions) {
        let Some(pos) = positions.get(sym) else {
            continue;
        };
        let side = match pos.pos_type {
            PositionType::Long => decision_kernel::PositionSide::Long,
            PositionType::Short => decision_kernel::PositionSide::Short,
        };
        let quantity = accounting::quantize(pos.size);
        if quantity <= 0.0 {
            continue;
        }
        let notional_usd = accounting::quantize(pos.size * pos.entry_price);
        kernel_state.positions.insert(
            pos.symbol.clone(),
            decision_kernel::Position {
                symbol: pos.symbol.clone(),
                side,
                quantity,
                avg_entry_price: accounting::quantize(pos.entry_price),
                opened_at_ms: pos.open_time_ms,
                updated_at_ms: pos.open_time_ms,
                notional_usd,
                margin_usd: accounting::quantize(pos.margin_used),
                confidence: None,
                entry_atr: None,
                entry_adx_threshold: None,
                adds_count: 0,
                tp1_taken: false,
                trailing_sl: None,
                mae_usd: 0.0,
                mfe_usd: 0.0,
                last_funding_ms: None,
            },
        );
    }
    kernel_state
}

fn kernel_signal(signal: Signal) -> decision_kernel::MarketSignal {
    match signal {
        Signal::Buy => decision_kernel::MarketSignal::Buy,
        Signal::Sell => decision_kernel::MarketSignal::Sell,
        Signal::Neutral => decision_kernel::MarketSignal::Neutral,
    }
}

fn signal_name(signal: Signal) -> &'static str {
    match signal {
        Signal::Buy => "BUY",
        Signal::Sell => "SELL",
        Signal::Neutral => "NEUTRAL",
    }
}

/// Sync the authoritative engine position into the corresponding kernel position.
///
/// The engine is execution SSOT for realised fills (entry/add prices, size, margin).
/// Exit evaluation reads from kernel positions, so we must mirror all state that
/// affects exit thresholds and triggers before calling `kernel_exits::evaluate_exits`.
fn sync_engine_to_kernel_pos(engine_pos: &Position, kernel_pos: &mut decision_kernel::Position) {
    kernel_pos.side = match engine_pos.pos_type {
        PositionType::Long => decision_kernel::PositionSide::Long,
        PositionType::Short => decision_kernel::PositionSide::Short,
    };
    kernel_pos.quantity = accounting::quantize(engine_pos.size);
    kernel_pos.avg_entry_price = accounting::quantize(engine_pos.entry_price);
    kernel_pos.opened_at_ms = engine_pos.open_time_ms;
    kernel_pos.updated_at_ms = engine_pos.last_add_time_ms.max(engine_pos.open_time_ms);
    kernel_pos.notional_usd = accounting::quantize(engine_pos.entry_price * engine_pos.size);
    kernel_pos.margin_usd = accounting::quantize(engine_pos.margin_used);
    kernel_pos.adds_count = engine_pos.adds_count;
    kernel_pos.mae_usd = engine_pos.mae_usd;
    kernel_pos.mfe_usd = engine_pos.mfe_usd;

    kernel_pos.entry_atr = Some(engine_pos.entry_atr);
    kernel_pos.confidence = Some(engine_pos.confidence.rank());
    kernel_pos.entry_adx_threshold = if engine_pos.entry_adx_threshold > 0.0 {
        Some(engine_pos.entry_adx_threshold)
    } else {
        None
    };
    kernel_pos.trailing_sl = engine_pos.trailing_sl;
    kernel_pos.tp1_taken = engine_pos.tp1_taken;
}

/// Sync kernel position exit state (trailing_sl, tp1_taken) back to the engine
/// position after kernel exit evaluation has updated them.
fn sync_kernel_to_engine_pos(kernel_pos: &decision_kernel::Position, engine_pos: &mut Position) {
    engine_pos.trailing_sl = kernel_pos.trailing_sl;
    engine_pos.tp1_taken = kernel_pos.tp1_taken;
}

/// Convert a `KernelExitResult` to the engine's `ExitResult` type.
fn kernel_exit_to_engine(result: &KernelExitResult) -> Option<ExitResult> {
    match result {
        KernelExitResult::Hold => None,
        KernelExitResult::FullClose { reason, exit_price } => {
            Some(ExitResult::exit(reason, *exit_price))
        }
        KernelExitResult::PartialClose {
            reason,
            exit_price,
            fraction,
        } => Some(ExitResult::partial_exit(reason, *exit_price, *fraction)),
    }
}

/// Evaluate exit conditions via the kernel's exit logic for a given symbol.
///
/// 1. Syncs engine → kernel position metadata.
/// 2. Calls `kernel_exits::evaluate_exits()` on the kernel position.
/// 3. Syncs updated trailing_sl / tp1_taken back to the engine position.
/// 4. Returns an `ExitResult` if an exit was triggered, or `None` to hold.
fn evaluate_kernel_exit(
    state: &mut SimState,
    symbol: &str,
    snap: &IndicatorSnapshot,
    ts: i64,
) -> Option<ExitResult> {
    let exit_params = match state.kernel_params.exit_params {
        Some(ref ep) => ep.clone(),
        None => return None,
    };

    // Phase 1: sync engine → kernel position
    if let Some(epos) = state.positions.get(symbol) {
        if let Some(kpos) = state.kernel_state.positions.get_mut(symbol) {
            sync_engine_to_kernel_pos(epos, kpos);
        }
    }

    // Phase 2: evaluate exits on kernel position (mutates trailing_sl in-place)
    let kernel_result = {
        if let Some(kpos) = state.kernel_state.positions.get_mut(symbol) {
            kernel_exits::evaluate_exits(kpos, snap, &exit_params, ts)
        } else {
            return None;
        }
    };

    // Phase 3: sync kernel → engine position (trailing_sl, tp1_taken)
    if let Some(kpos) = state.kernel_state.positions.get(symbol) {
        if let Some(epos) = state.positions.get_mut(symbol) {
            sync_kernel_to_engine_pos(kpos, epos);
        }
    }

    // Phase 4: convert to engine ExitResult
    kernel_exit_to_engine(&kernel_result)
}

fn build_active_params(
    source: &str,
    cfg: &StrategyConfig,
    kernel_params: &decision_kernel::KernelParams,
) -> HashMap<String, f64> {
    let is_entry = source.contains("open") || source.contains("pyramid");
    let mut params = HashMap::new();
    if is_entry {
        params.insert("min_adx".into(), cfg.thresholds.entry.min_adx);
        params.insert("reef_adx_threshold".into(), cfg.trade.reef_adx_threshold);
        params.insert(
            "reef_long_rsi_block_gt".into(),
            cfg.trade.reef_long_rsi_block_gt,
        );
        params.insert(
            "pullback_rsi_long_min".into(),
            cfg.thresholds.entry.pullback_rsi_long_min,
        );
        params.insert(
            "pullback_rsi_short_max".into(),
            cfg.thresholds.entry.pullback_rsi_short_max,
        );
        params.insert("leverage".into(), kernel_params.leverage);
        params.insert("taker_fee_bps".into(), kernel_params.taker_fee_bps);
        params.insert("maker_fee_bps".into(), kernel_params.maker_fee_bps);
    } else {
        params.insert("sl_atr_mult".into(), cfg.trade.sl_atr_mult);
        params.insert("tp_atr_mult".into(), cfg.trade.tp_atr_mult);
        params.insert("trailing_start_atr".into(), cfg.trade.trailing_start_atr);
        params.insert("tsme_min_profit_atr".into(), cfg.trade.tsme_min_profit_atr);
        params.insert(
            "smart_exit_adx_exhaustion_lt".into(),
            cfg.trade.smart_exit_adx_exhaustion_lt,
        );
    }
    params
}

/// Build a per-signal gate evaluation chain from the primary `GateResult`
/// and engine-level post-signal checks.
fn build_gate_evaluation(
    gr: &gates::GateResult,
    snap: &IndicatorSnapshot,
    signal: Signal,
    confidence: Confidence,
    cfg: &StrategyConfig,
) -> GateEvaluation {
    let mut checks = Vec::with_capacity(10);

    // Gate 1: ADX minimum threshold
    checks.push(GateCheck {
        gate_name: "adx_min".into(),
        passed: gr.adx_above_min,
        actual_value: snap.adx,
        threshold_value: gr.effective_min_adx,
        reason: if !gr.adx_above_min {
            Some(format!(
                "ADX {:.2} below effective min {:.2}",
                snap.adx, gr.effective_min_adx
            ))
        } else {
            None
        },
    });

    // Gate 2: Ranging filter (vote system; bb_width_ratio is the most visible metric)
    checks.push(GateCheck {
        gate_name: "ranging".into(),
        passed: !gr.is_ranging,
        actual_value: gr.bb_width_ratio,
        threshold_value: 0.0,
        reason: if gr.is_ranging {
            Some("Market in ranging regime (vote system)".into())
        } else {
            None
        },
    });

    // Gate 3: Anomaly filter
    let price_change_pct = if snap.prev_close > 0.0 {
        (snap.close - snap.prev_close).abs() / snap.prev_close
    } else {
        0.0
    };
    checks.push(GateCheck {
        gate_name: "anomaly".into(),
        passed: !gr.is_anomaly,
        actual_value: price_change_pct,
        threshold_value: 0.0,
        reason: if gr.is_anomaly {
            Some("Anomalous price move or EMA deviation".into())
        } else {
            None
        },
    });

    // Gate 4: Extension filter (distance from EMA_fast)
    let ext_dist = if snap.ema_fast > 0.0 {
        (snap.close - snap.ema_fast).abs() / snap.ema_fast
    } else {
        0.0
    };
    checks.push(GateCheck {
        gate_name: "extension".into(),
        passed: !gr.is_extended,
        actual_value: ext_dist,
        threshold_value: cfg.thresholds.entry.max_dist_ema_fast,
        reason: if gr.is_extended {
            Some(format!(
                "Price dist {:.4} from EMA_fast exceeds {:.4}",
                ext_dist, cfg.thresholds.entry.max_dist_ema_fast
            ))
        } else {
            None
        },
    });

    // Gate 5: Volume confirmation
    checks.push(GateCheck {
        gate_name: "volume".into(),
        passed: gr.vol_confirm,
        actual_value: snap.volume,
        threshold_value: snap.vol_sma,
        reason: if !gr.vol_confirm {
            Some("Volume below SMA or vol_trend false".into())
        } else {
            None
        },
    });

    // Gate 6: ADX rising
    checks.push(GateCheck {
        gate_name: "adx_rising".into(),
        passed: gr.is_trending_up,
        actual_value: snap.adx_slope,
        threshold_value: 0.0,
        reason: if !gr.is_trending_up {
            Some(format!(
                "ADX slope {:.4} not rising and ADX below saturation",
                snap.adx_slope
            ))
        } else {
            None
        },
    });

    // Gate 7: BTC alignment (directional)
    let btc_passed = match signal {
        Signal::Buy => gr.btc_ok_long,
        Signal::Sell => gr.btc_ok_short,
        Signal::Neutral => true,
    };
    checks.push(GateCheck {
        gate_name: "btc_alignment".into(),
        passed: btc_passed,
        actual_value: if btc_passed { 1.0 } else { 0.0 },
        threshold_value: 1.0,
        reason: if !btc_passed {
            Some(format!(
                "BTC alignment blocked {} signal",
                match signal {
                    Signal::Buy => "long",
                    Signal::Sell => "short",
                    Signal::Neutral => "neutral",
                }
            ))
        } else {
            None
        },
    });

    // Post-signal gate: Confidence
    let conf_meets = confidence.meets_min(cfg.trade.entry_min_confidence);
    checks.push(GateCheck {
        gate_name: "confidence".into(),
        passed: conf_meets,
        actual_value: confidence.rank() as f64,
        threshold_value: cfg.trade.entry_min_confidence.rank() as f64,
        reason: if !conf_meets {
            Some(format!(
                "Confidence {:?} below min {:?}",
                confidence, cfg.trade.entry_min_confidence
            ))
        } else {
            None
        },
    });

    // Post-signal gate: SSF filter (MACD histogram)
    if cfg.trade.enable_ssf_filter {
        let ssf_ok = match signal {
            Signal::Buy => snap.macd_hist > 0.0,
            Signal::Sell => snap.macd_hist < 0.0,
            Signal::Neutral => true,
        };
        checks.push(GateCheck {
            gate_name: "ssf".into(),
            passed: ssf_ok,
            actual_value: snap.macd_hist,
            threshold_value: 0.0,
            reason: if !ssf_ok {
                Some(format!(
                    "MACD histogram {:.4} wrong side for {:?}",
                    snap.macd_hist, signal
                ))
            } else {
                None
            },
        });
    }

    // Post-signal gate: REEF filter (RSI with ADX-adaptive threshold)
    if cfg.trade.enable_reef_filter {
        let (reef_blocked, rsi_threshold) = match signal {
            Signal::Buy => {
                let thresh = if snap.adx < cfg.trade.reef_adx_threshold {
                    cfg.trade.reef_long_rsi_block_gt
                } else {
                    cfg.trade.reef_long_rsi_extreme_gt
                };
                (snap.rsi > thresh, thresh)
            }
            Signal::Sell => {
                let thresh = if snap.adx < cfg.trade.reef_adx_threshold {
                    cfg.trade.reef_short_rsi_block_lt
                } else {
                    cfg.trade.reef_short_rsi_extreme_lt
                };
                (snap.rsi < thresh, thresh)
            }
            Signal::Neutral => (false, 0.0),
        };
        checks.push(GateCheck {
            gate_name: "reef".into(),
            passed: !reef_blocked,
            actual_value: snap.rsi,
            threshold_value: rsi_threshold,
            reason: if reef_blocked {
                Some(format!(
                    "RSI {:.2} blocked by reef threshold {:.2}",
                    snap.rsi, rsi_threshold
                ))
            } else {
                None
            },
        });
    }

    let passed = checks.iter().all(|c| c.passed);
    GateEvaluation {
        passed,
        checked_gates: checks,
    }
}

struct StepDecisionInput<'a> {
    ts: i64,
    symbol: &'a str,
    signal: Signal,
    price: f64,
    requested_notional_usd: Option<f64>,
    source: &'a str,
    cfg: &'a StrategyConfig,
}

fn step_decision(
    state: &mut SimState,
    input: StepDecisionInput<'_>,
) -> decision_kernel::DecisionResult {
    let StepDecisionInput {
        ts,
        symbol,
        signal,
        price,
        requested_notional_usd,
        source,
        cfg,
    } = input;
    let event = decision_kernel::MarketEvent {
        schema_version: 1,
        event_id: state.next_kernel_event_id,
        timestamp_ms: ts,
        symbol: symbol.to_string(),
        signal: kernel_signal(signal),
        price: accounting::quantize(price),
        notional_hint_usd: requested_notional_usd,
        close_fraction: None,
        fee_role: None,
        funding_rate: None,
        indicators: None,
        gate_result: None,
        ema_slow_slope_pct: None,
    };
    state.next_kernel_event_id = state.next_kernel_event_id.saturating_add(1);

    let decision = decision_kernel::step(&state.kernel_state, &event, &state.kernel_params);
    state.kernel_state = decision.state.clone();

    let trace = DecisionKernelTrace {
        event_id: event.event_id,
        source: source.to_string(),
        timestamp_ms: ts,
        symbol: symbol.to_string(),
        signal: signal_name(signal).to_string(),
        requested_notional_usd: requested_notional_usd.unwrap_or(0.0),
        requested_price: price,
        schema_version: decision.diagnostics.schema_version,
        step: decision.state.step,
        state_step: decision.state.step,
        state_cash_usd: decision.state.cash_usd,
        state_positions: decision.state.positions.len(),
        intent_count: decision.intents.len(),
        fill_count: decision.fills.len(),
        warnings: decision.diagnostics.warnings.clone(),
        errors: decision.diagnostics.errors.clone(),
        intents: decision
            .intents
            .iter()
            .map(|intent| DecisionKernelIntentSummary {
                kind: format!("{:?}", intent.kind).to_lowercase(),
                side: format!("{:?}", intent.side).to_lowercase(),
                symbol: intent.symbol.clone(),
                quantity: intent.quantity,
                price: intent.price,
                notional_usd: intent.notional_usd,
                fee_rate: intent.fee_rate,
            })
            .collect(),
        fills: decision
            .fills
            .iter()
            .map(|fill| DecisionKernelFillSummary {
                side: format!("{:?}", fill.side).to_lowercase(),
                symbol: fill.symbol.clone(),
                quantity: fill.quantity,
                price: fill.price,
                notional_usd: fill.notional_usd,
                fee_usd: fill.fee_usd,
                pnl_usd: fill.pnl_usd,
            })
            .collect(),
        applied_to_kernel_state: !decision.diagnostics.has_errors(),
        active_params: build_active_params(source, cfg, &state.kernel_params),
        gate_result: None,
        indicator_snapshot: None,
        config_fingerprint: None,
    };
    state.decision_diagnostics.push(trace);
    decision
}

fn make_indicator_bank(cfg: &StrategyConfig, use_stoch_rsi: bool) -> IndicatorBank {
    IndicatorBank::new_with_ave_window(
        &cfg.indicators,
        use_stoch_rsi,
        cfg.effective_ave_avg_atr_window(),
    )
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

/// Run a full backtest simulation.
///
/// # Arguments
/// * `candles`         - Bar data keyed by symbol (indicator-resolution, e.g. 1h).
/// * `cfg`             - Strategy configuration.
/// * `initial_balance` - Starting equity in USD.
/// * `lookback`        - Number of warmup bars before trading begins.
/// * `exit_candles`    - Optional higher-resolution bar data for exit checks (e.g. 1m).
///                       When provided, exit conditions are evaluated on sub-bars within
///                       each indicator bar, aligning backtest exits with live behavior.
/// * `entry_candles`   - Optional higher-resolution bar data for entry checks (e.g. 15m).
///                       When provided, entry signals are evaluated at sub-bar resolution
///                       (indicator-bar indicators + sub-bar price) instead of indicator bars.
///                       This matches live engine behavior where signals are checked every ~60s.
/// * `funding_rates`   - Optional per-symbol funding rate data. When provided, funding
///                       payments are applied at hourly boundaries for open positions.
/// * `from_ts`         - Optional start timestamp (ms, inclusive). Bars before this
///                       still update indicators (warmup) but no trading occurs.
/// * `to_ts`           - Optional end timestamp (ms, inclusive). Bars after this are
///                       skipped for trading.
pub struct RunSimulationInput<'a> {
    pub candles: &'a CandleData,
    pub cfg: &'a StrategyConfig,
    pub initial_balance: f64,
    pub lookback: usize,
    pub exit_candles: Option<&'a CandleData>,
    pub entry_candles: Option<&'a CandleData>,
    pub funding_rates: Option<&'a FundingRateData>,
    pub init_state: Option<crate::init_state::SimInitState>,
    pub from_ts: Option<i64>,
    pub to_ts: Option<i64>,
}

pub fn run_simulation(input: RunSimulationInput<'_>) -> SimResult {
    let RunSimulationInput {
        candles,
        cfg,
        initial_balance,
        lookback,
        exit_candles,
        entry_candles,
        funding_rates,
        init_state,
        from_ts,
        to_ts,
    } = input;
    let use_stoch_rsi = cfg.filters.use_stoch_rsi_filter;

    // -- Build sorted timeline of unique timestamps --
    let timestamps = build_timeline(candles);
    if timestamps.is_empty() {
        return SimResult {
            trades: vec![],
            signals: vec![],
            decision_diagnostics: vec![],
            final_balance: initial_balance,
            equity_curve: vec![],
            gate_stats: GateStats::default(),
        };
    }

    // -- Build per-symbol bar index for O(1) lookup --
    let bar_index = build_bar_index(candles);

    // -- Initialize state (optionally from exported live/paper snapshot) --
    let (init_balance, init_positions, init_last_entry_attempt_ms, init_last_exit_attempt_ms) =
        match init_state {
            Some((b, p, entry_attempts, exit_attempts)) => (b, p, entry_attempts, exit_attempts),
            None => (
                initial_balance,
                FxHashMap::default(),
                FxHashMap::default(),
                FxHashMap::default(),
            ),
        };
    let mut state = SimState {
        balance: init_balance,
        positions: init_positions.clone(),
        last_entry_attempt_ms: init_last_entry_attempt_ms,
        last_exit_attempt_ms: init_last_exit_attempt_ms,
        indicators: FxHashMap::default(),
        ema_slow_history: FxHashMap::default(),
        bar_counts: FxHashMap::default(),
        last_close: FxHashMap::default(),
        trades: Vec::with_capacity(4096),
        signals: Vec::with_capacity(8192),
        decision_diagnostics: Vec::new(),
        kernel_state: make_kernel_state(init_balance, timestamps[0], &init_positions),
        kernel_params: make_kernel_params(cfg),
        next_kernel_event_id: 1,
        equity_curve: Vec::with_capacity(timestamps.len()),
        gate_stats: GateStats::default(),
    };

    // Pre-create indicator banks for every symbol
    for sym in candles.keys() {
        state
            .indicators
            .insert(sym.clone(), make_indicator_bank(cfg, use_stoch_rsi));
    }

    // Build exit candle index: symbol → sorted Vec<(timestamp_ms, index)>
    // Used for binary-search lookups when doing sub-bar exit checks.
    let exit_bar_index: Option<FxHashMap<String, Vec<(i64, usize)>>> = exit_candles.map(|ec| {
        let mut idx: FxHashMap<String, Vec<(i64, usize)>> = FxHashMap::default();
        for (sym, bars) in ec {
            let entries: Vec<(i64, usize)> =
                bars.iter().enumerate().map(|(i, b)| (b.t, i)).collect();
            idx.insert(sym.clone(), entries);
        }
        idx
    });

    // Build entry candle index (same structure as exit, but for entry sub-bars).
    let entry_bar_index: Option<FxHashMap<String, Vec<(i64, usize)>>> = entry_candles.map(|ec| {
        let mut idx: FxHashMap<String, Vec<(i64, usize)>> = FxHashMap::default();
        for (sym, bars) in ec {
            let entries: Vec<(i64, usize)> =
                bars.iter().enumerate().map(|(i, b)| (b.t, i)).collect();
            idx.insert(sym.clone(), entries);
        }
        idx
    });

    // Collect symbol names for ordered iteration (deterministic)
    let mut symbols: Vec<&String> = candles.keys().collect();
    symbols.sort();

    // -- Main loop: iterate every timestamp --
    for &ts in &timestamps {
        // Hard stop at the upper replay bound so that hourly funding settlement
        // and equity sampling cannot leak beyond the requested time window.
        if let Some(tt) = to_ts {
            if ts > tt {
                break;
            }
        }

        // 1. BTC context: determine if BTC is bullish
        let btc_bullish = compute_btc_bullish(&state, ts, &bar_index, candles);

        // 2. Compute market breadth (percentage of symbols where EMA_fast > EMA_slow)
        let breadth_pct = compute_market_breadth(&state);

        // Per-symbol EMA-slow slope cache for sub-bar entry evaluation
        let mut sub_bar_slopes: FxHashMap<String, f64> = FxHashMap::default();
        // Last fully-closed indicator snapshot per symbol.
        // Sub-bar entry evaluation must use this previous snapshot to avoid
        // peeking at the current indicator bar before it has closed.
        let mut prev_indicator_snaps: FxHashMap<String, IndicatorSnapshot> = FxHashMap::default();
        // Current indicator snapshot per symbol after processing this indicator bar.
        // Used for signal-on-candle-close entry evaluation at the bar boundary.
        let mut current_indicator_snaps: FxHashMap<String, IndicatorSnapshot> = FxHashMap::default();

        // Per-bar entry counter (limits entries to max_entry_orders_per_loop)
        let mut entries_this_bar: usize = 0;

        // Indicator-bar entry candidates (collected in phase 1, ranked in phase 2)
        let mut indicator_bar_candidates: Vec<EntryCandidate> = Vec::new();

        // When an explicit finer exit interval is configured, exit checks must
        // run on the exit sub-bar stream only. Running base-interval exits
        // first can close positions too early versus live.
        let use_exit_sub_bar = exit_candles.is_some()
            && exit_bar_index.is_some()
            && cfg.engine.exit_interval != cfg.engine.interval;

        // 3. Process each symbol at this timestamp
        for sym in &symbols {
            let sym_str: &str = sym.as_str();

            // Check if this symbol has a bar at this timestamp
            let bar = match lookup_bar(&bar_index, sym_str, ts, candles) {
                Some(b) => b,
                None => continue,
            };

            // Feed bar to indicator bank
            // H9: replace .unwrap() with defensive continue (key is guaranteed
            // by pre-creation loop above, but avoid panic on impossible state).
            let bank = match state.indicators.get_mut(sym_str) {
                Some(b) => b,
                None => {
                    eprintln!("[bt-core] BUG: indicator bank missing for {sym_str}, skipping bar");
                    continue;
                }
            };
            let prev_snap = bank.latest_snap();
            prev_indicator_snaps.insert(sym.to_string(), prev_snap);
            let snap = bank.update(bar);
            current_indicator_snaps.insert(sym.to_string(), snap.clone());

            // Store EMA slow for slope computation (borrow ends immediately)
            state
                .ema_slow_history
                .entry(sym.to_string())
                .or_insert_with(Vec::new)
                .push(snap.ema_slow);

            // Increment bar count (copy value so mutable borrow ends)
            let bar_count = {
                let bc = state.bar_counts.entry(sym.to_string()).or_insert(0);
                *bc += 1;
                *bc
            };

            // ── Trade scope guard ─────────────────────────────────────
            // Skip exits and entries for bars outside [from_ts, to_ts].
            // Indicators are already updated above (needed for warmup).
            if let Some(ft) = from_ts {
                if ts < ft {
                    continue;
                }
            }
            if let Some(tt) = to_ts {
                if ts > tt {
                    continue;
                }
            }

            // ── Exit check for existing position (kernel-delegated) ──────
            // Runs BEFORE warmup guard so that init-state positions are
            // monitored from the very first bar (without init-state,
            // positions are empty during warmup so this is a no-op).
            // Exit evaluation is delegated to kernel_exits::evaluate_exits()
            // which handles SL, trailing, TP, glitch guard, and smart exits.
            // The kernel updates trailing_sl/tp1_taken in-place; we sync them
            // back to the engine position after each evaluation.
            if state.positions.contains_key(sym_str) && !use_exit_sub_bar {
                if !is_exit_cooldown_active(&state, sym_str, ts, cfg) {
                    if let Some(exit_result) = evaluate_kernel_exit(&mut state, sym_str, &snap, ts)
                    {
                        apply_exit(&mut state, sym_str, &exit_result, &snap, ts, cfg);
                    }
                }
            }

            // Skip warmup period (entries only — exits above always run)
            if bar_count < lookback {
                continue;
            }

            // Compute EMA slow slope (re-borrow immutably after exit check)
            let slope_window = cfg.thresholds.entry.slow_drift_slope_window;
            let ema_slow_slope_pct = {
                // H9: replace .unwrap() with defensive continue (history is
                // populated a few lines above on this same iteration, but
                // avoid panic on impossible state).
                let hist = match state.ema_slow_history.get(sym_str) {
                    Some(h) => h,
                    None => {
                        eprintln!(
                            "[bt-core] BUG: ema_slow_history missing for {sym_str}, skipping"
                        );
                        continue;
                    }
                };
                compute_ema_slow_slope(hist, slope_window, snap.close)
            };
            sub_bar_slopes.insert(sym.to_string(), ema_slow_slope_pct);

            // ── Entry evaluation (collect candidates) ─────────────────
            let btc_bull_opt = btc_bullish;
            let gate_result =
                gates::check_gates(&snap, cfg, sym_str, btc_bull_opt, ema_slow_slope_pct);
            let (mut signal, confidence, entry_adx_threshold) =
                entry::generate_signal(&snap, &gate_result, cfg, ema_slow_slope_pct);

            // Track gate statistics
            state.gate_stats.total_checks += 1;
            match signal {
                Signal::Neutral => state.gate_stats.neutral_count += 1,
                Signal::Buy => state.gate_stats.buy_count += 1,
                Signal::Sell => state.gate_stats.sell_count += 1,
            }

            // Track gate-level blocks
            if gate_result.is_ranging {
                state.gate_stats.blocked_by_ranging += 1;
            }
            if gate_result.is_anomaly {
                state.gate_stats.blocked_by_anomaly += 1;
            }
            if gate_result.is_extended {
                state.gate_stats.blocked_by_extension += 1;
            }
            if !gate_result.adx_above_min {
                state.gate_stats.blocked_by_adx_low += 1;
            }
            if !gate_result.is_trending_up {
                state.gate_stats.blocked_by_adx_not_rising += 1;
            }
            if !gate_result.vol_confirm {
                state.gate_stats.blocked_by_volume += 1;
            }
            if !gate_result.btc_ok_long || !gate_result.btc_ok_short {
                state.gate_stats.blocked_by_btc += 1;
            }

            // Record raw signal
            if signal != Signal::Neutral {
                state.signals.push(SignalRecord {
                    timestamp_ms: ts,
                    symbol: sym.to_string(),
                    signal,
                    confidence,
                    price: snap.close,
                    adx: snap.adx,
                    rsi: snap.rsi,
                    atr: snap.atr,
                });
            }

            // ── Collect entry candidates (only on indicator bars when no entry_candles) ──
            // When entry_candles is provided, entry signals are deferred to the
            // entry sub-bar block below for higher-resolution timing.
            if entry_candles.is_none() {
                let debug_target = match (
                    std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
                    std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
                ) {
                    (Ok(sym_filter), Ok(ts_filter_raw)) => {
                        sym_str == sym_filter && ts == ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN)
                    }
                    _ => false,
                };
                // Engine-level transforms
                let atr = apply_atr_floor(snap.atr, snap.close, cfg.trade.min_atr_pct);

                if signal != Signal::Neutral {
                    signal = apply_reverse(signal, cfg, breadth_pct);
                }
                if signal != Signal::Neutral {
                    signal = apply_regime_filter(signal, cfg, breadth_pct);
                }

                if signal == Signal::Neutral {
                    if debug_target {
                        eprintln!(
                            "[cpu-cand-debug] sym={} ts_ms={} rejected=neutral_after_reverse_regime breadth={:.6} adx={:.6} adx_slope={:.6} macd={:.8} rsi={:.6}",
                            sym_str, ts, breadth_pct, snap.adx, snap.adx_slope, snap.macd_hist, snap.rsi
                        );
                    }
                    continue;
                }

                let desired_type = match signal {
                    Signal::Buy => PositionType::Long,
                    Signal::Sell => PositionType::Short,
                    Signal::Neutral => unreachable!(),
                };

                // Handle signal-directed close for opposite positions via canonical kernel step.
                if let Some(pos) = state.positions.get(sym_str) {
                    if pos.pos_type != desired_type {
                        let decision = step_decision(
                            &mut state,
                            StepDecisionInput {
                                ts,
                                symbol: sym_str,
                                signal,
                                price: snap.close,
                                requested_notional_usd: None,
                                source: "indicator-bar-close",
                                cfg,
                            },
                        );
                        if let Some(last) = state.decision_diagnostics.last_mut() {
                            last.indicator_snapshot = Some(snap.clone());
                        }
                        if decision.intents.iter().any(|intent| {
                            matches!(
                                intent.kind,
                                decision_kernel::OrderIntentKind::Close
                                    | decision_kernel::OrderIntentKind::Reverse
                            )
                        }) {
                            let exit = ExitResult::exit("Signal Flip", snap.close);
                            apply_exit(&mut state, sym_str, &exit, &snap, ts, cfg);
                        }
                    }
                }

                // Handle same-direction pyramiding (immediate, not ranked)
                if let Some(pos) = state.positions.get(sym_str) {
                    let pos_type = pos.pos_type;
                    if pos_type == desired_type && cfg.trade.enable_pyramiding {
                        try_pyramid(&mut state, sym_str, &snap, cfg, confidence, atr, ts);
                        if debug_target {
                            eprintln!(
                                "[cpu-cand-debug] sym={} ts_ms={} rejected=already_open_pyramid pos_type={:?} desired={:?}",
                                sym_str, ts, pos_type, desired_type
                            );
                        }
                    } else if debug_target {
                        eprintln!(
                            "[cpu-cand-debug] sym={} ts_ms={} rejected=already_open_no_pyramid pos_type={:?} desired={:?}",
                            sym_str, ts, pos_type, desired_type
                        );
                    }
                    continue;
                }

                // Pre-filter gates that don't depend on cross-symbol state
                if !confidence.meets_min(cfg.trade.entry_min_confidence) {
                    state.gate_stats.blocked_by_confidence += 1;
                    if debug_target {
                        eprintln!(
                            "[cpu-cand-debug] sym={} ts_ms={} rejected=min_conf confidence={:?} min={:?}",
                            sym_str, ts, confidence, cfg.trade.entry_min_confidence
                        );
                    }
                    continue;
                }
                if is_pesc_blocked(&state, sym_str, desired_type, ts, snap.adx, cfg) {
                    state.gate_stats.blocked_by_pesc += 1;
                    if debug_target {
                        eprintln!(
                            "[cpu-cand-debug] sym={} ts_ms={} rejected=pesc desired={:?} adx={:.6}",
                            sym_str, ts, desired_type, snap.adx
                        );
                    }
                    continue;
                }
                if cfg.trade.enable_ssf_filter {
                    let ssf_ok = match signal {
                        Signal::Buy => snap.macd_hist > 0.0,
                        Signal::Sell => snap.macd_hist < 0.0,
                        Signal::Neutral => true,
                    };
                    if !ssf_ok {
                        state.gate_stats.blocked_by_ssf += 1;
                        if debug_target {
                            eprintln!(
                                "[cpu-cand-debug] sym={} ts_ms={} rejected=ssf signal={:?} macd={:.10}",
                                sym_str, ts, signal, snap.macd_hist
                            );
                        }
                        continue;
                    }
                }
                if cfg.trade.enable_reef_filter {
                    let reef_blocked = match signal {
                        Signal::Buy => {
                            if snap.adx < cfg.trade.reef_adx_threshold {
                                snap.rsi > cfg.trade.reef_long_rsi_block_gt
                            } else {
                                snap.rsi > cfg.trade.reef_long_rsi_extreme_gt
                            }
                        }
                        Signal::Sell => {
                            if snap.adx < cfg.trade.reef_adx_threshold {
                                snap.rsi < cfg.trade.reef_short_rsi_block_lt
                            } else {
                                snap.rsi < cfg.trade.reef_short_rsi_extreme_lt
                            }
                        }
                        Signal::Neutral => false,
                    };
                    if reef_blocked {
                        state.gate_stats.blocked_by_reef += 1;
                        if debug_target {
                            eprintln!(
                                "[cpu-cand-debug] sym={} ts_ms={} rejected=reef signal={:?} adx={:.6} rsi={:.6}",
                                sym_str, ts, signal, snap.adx, snap.rsi
                            );
                        }
                        continue;
                    }
                }

                // Build per-signal gate evaluation chain
                let gate_eval = build_gate_evaluation(&gate_result, &snap, signal, confidence, cfg);

                // Collect as candidate for ranking
                indicator_bar_candidates.push(EntryCandidate {
                    symbol: sym.to_string(),
                    signal,
                    confidence,
                    adx: snap.adx,
                    atr,
                    entry_adx_threshold,
                    snap: snap.clone(),
                    ts,
                    gate_eval,
                });
                if debug_target {
                    eprintln!(
                        "[cpu-cand-debug] sym={} ts_ms={} accepted signal={:?} confidence={:?} adx={:.6} atr={:.10} entry_adx_thresh={:.6} breadth={:.6} btc_bull={:?}",
                        sym_str,
                        ts,
                        signal,
                        confidence,
                        snap.adx,
                        atr,
                        entry_adx_threshold,
                        breadth_pct,
                        btc_bullish
                    );
                }
            }
        }

        // ── Phase 2: Rank indicator-bar entry candidates by score ────
        // Score = confidence_rank * 100 + ADX (descending), tiebreak by symbol (ascending).
        if !indicator_bar_candidates.is_empty() {
            indicator_bar_candidates.sort_by(|a, b| {
                let score_a = (a.confidence as i32) * 100 + a.adx as i32;
                let score_b = (b.confidence as i32) * 100 + b.adx as i32;
                score_b.cmp(&score_a).then_with(|| a.symbol.cmp(&b.symbol))
            });

            if let (Ok(sym_filter), Ok(ts_filter_raw)) = (
                std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
                std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
            ) {
                let ts_filter = ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN);
                let mut printed_header = false;
                for (idx, cand) in indicator_bar_candidates.iter().enumerate() {
                    if cand.ts == ts_filter {
                        if !printed_header {
                            eprintln!(
                                "[cpu-rank-debug] ts_ms={} entries_this_bar_start={} max_entries={} candidates_at_ts:",
                                ts_filter,
                                entries_this_bar,
                                cfg.trade.max_entry_orders_per_loop
                            );
                            printed_header = true;
                        }
                        let score = (cand.confidence as i32) * 100 + cand.adx as i32;
                        eprintln!(
                            "[cpu-rank-debug] idx={} symbol={} score={} conf={:?} adx={:.6} signal={:?}",
                            idx, cand.symbol, score, cand.confidence, cand.adx, cand.signal
                        );
                    }
                }
                if !printed_header {
                    let _ = sym_filter;
                }
            }

            let equity = state.balance
                + unrealized_pnl(&state.positions, &state.indicators, ts, candles, &bar_index);

            for cand in &indicator_bar_candidates {
                if entries_this_bar >= cfg.trade.max_entry_orders_per_loop {
                    if let (Ok(sym_filter), Ok(ts_filter_raw)) = (
                        std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
                        std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
                    ) {
                        let ts_filter = ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN);
                        if cand.ts == ts_filter || cand.symbol == sym_filter {
                            eprintln!(
                                "[cpu-rank-debug] break_on_entry_limit at symbol={} ts_ms={} entries_this_bar={} max_entries={}",
                                cand.symbol,
                                cand.ts,
                                entries_this_bar,
                                cfg.trade.max_entry_orders_per_loop
                            );
                        }
                    }
                    break;
                }
                let total_margin = total_margin_used(&state.positions);
                let exposure = evaluate_exposure_guard(ExposureGuardInput {
                    open_positions: state.positions.len(),
                    max_open_positions: Some(cfg.trade.max_open_positions),
                    total_margin_used: total_margin,
                    equity,
                    max_total_margin_pct: cfg.trade.max_total_margin_pct,
                    allow_zero_margin_headroom: false,
                });
                if let (Ok(sym_filter), Ok(ts_filter_raw)) = (
                    std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
                    std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
                ) {
                    let ts_filter = ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN);
                    if cand.symbol == sym_filter && cand.ts == ts_filter {
                        eprintln!(
                            "[cpu-rank-debug] sym={} ts_ms={} exposure_allowed={} blocked_reason={:?} equity={:.12} total_margin={:.12} headroom={:.12} max_total_margin_pct={:.12}",
                            cand.symbol,
                            cand.ts,
                            exposure.allowed,
                            exposure.blocked_reason,
                            equity,
                            total_margin,
                            exposure.margin_headroom,
                            cfg.trade.max_total_margin_pct
                        );
                    }
                }
                if matches!(
                    exposure.blocked_reason,
                    Some(ExposureBlockReason::MaxOpenPositions)
                ) {
                    state.gate_stats.blocked_by_max_positions += 1;
                    break;
                }

                // Skip if a position was opened for this symbol (e.g. via signal flip above)
                if state.positions.contains_key(&cand.symbol) {
                    continue;
                }
                if is_entry_cooldown_active(&state, &cand.symbol, cand.ts, cfg) {
                    continue;
                }
                let margin_check = evaluate_exposure_guard(ExposureGuardInput {
                    open_positions: state.positions.len(),
                    max_open_positions: None,
                    total_margin_used: total_margin,
                    equity,
                    max_total_margin_pct: cfg.trade.max_total_margin_pct,
                    allow_zero_margin_headroom: false,
                });
                if !margin_check.allowed {
                    state.gate_stats.blocked_by_margin += 1;
                    continue;
                }
                let margin_headroom = margin_check.margin_headroom;

                let (size, margin_used, leverage) = compute_entry_size(
                    &cand.symbol,
                    equity,
                    cand.snap.close,
                    cand.confidence,
                    cand.atr,
                    &cand.snap,
                    cfg,
                );
                if let (Ok(sym_filter), Ok(ts_filter_raw)) = (
                    std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
                    std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
                ) {
                    if cand.symbol == sym_filter
                        && cand.ts == ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN)
                    {
                        eprintln!(
                            "[cpu-entry-debug] sym={} ts_ms={} equity={:.12} total_margin={:.12} headroom={:.12} price={:.12} atr={:.12} adx={:.12} conf={:?} size_pre={:.12} margin_pre={:.12} lev={:.12}",
                            cand.symbol,
                            cand.ts,
                            equity,
                            total_margin,
                            margin_headroom,
                            cand.snap.close,
                            cand.atr,
                            cand.snap.adx,
                            cand.confidence,
                            size,
                            margin_used,
                            leverage
                        );
                    }
                }
                let (mut size, mut margin_used) = if margin_used > margin_headroom {
                    // M13: zero-guard on margin_used division
                    let ratio = if margin_used > 1e-12 {
                        margin_headroom / margin_used
                    } else {
                        0.0
                    };
                    (size * ratio, margin_headroom)
                } else {
                    (size, margin_used)
                };

                let mut notional = size * cand.snap.close;
                if notional < cfg.trade.min_notional_usd {
                    if cfg.trade.bump_to_min_notional && cand.snap.close > 0.0 {
                        size = cfg.trade.min_notional_usd / cand.snap.close;
                        margin_used = size * cand.snap.close / leverage;
                        notional = size * cand.snap.close;
                        if margin_used > margin_headroom {
                            continue;
                        }
                    } else {
                        continue;
                    }
                }
                let kernel_notional = notional;
                let decision = step_decision(
                    &mut state,
                    StepDecisionInput {
                        ts: cand.ts,
                        symbol: &cand.symbol,
                        signal: cand.signal,
                        price: cand.snap.close,
                        requested_notional_usd: Some(kernel_notional),
                        source: "indicator-bar-open",
                        cfg,
                    },
                );
                // Attach per-signal gate evaluation and indicator snapshot to the trace entry
                if let Some(last) = state.decision_diagnostics.last_mut() {
                    last.gate_result = Some(cand.gate_eval.clone());
                    last.indicator_snapshot = Some(cand.snap.clone());
                }
                let intent_open = decision.intents.iter().any(|intent| {
                    matches!(
                        intent.kind,
                        decision_kernel::OrderIntentKind::Open
                            | decision_kernel::OrderIntentKind::Add
                    )
                });
                if intent_open
                    && apply_indicator_open_from_kernel(
                        &mut state,
                        &cand,
                        size,
                        margin_used,
                        leverage,
                        kernel_notional,
                        cfg,
                        &format!("{:?} entry", cand.confidence),
                    )
                {
                    entries_this_bar += 1;
                }
            }
        }

        // Pre-compute next indicator-bar timestamp (shared by exit + entry sub-bar blocks)
        let ts_i = timestamps.binary_search(&ts).unwrap_or(0);
        let next_ts = if ts_i + 1 < timestamps.len() {
            timestamps[ts_i + 1]
        } else {
            i64::MAX
        };
        if let Some(ft) = from_ts {
            if ts < ft {
                continue;
            }
        }
        if let Some(tt) = to_ts {
            if ts > tt {
                continue;
            }
        }

        // ── Exit sub-bar block (kernel-delegated) ──────────────────────
        // Scan exit candles (e.g. 1m) within this indicator bar's time range
        // for SL/TP exit precision, matching live behavior.
        // Uses kernel exit evaluation instead of direct exits::check_all_exits.
        if use_exit_sub_bar {
            if let (Some(ec), Some(ref ec_idx)) = (exit_candles, &exit_bar_index) {
                if !state.positions.is_empty() {
                    let mut exit_syms: Vec<String> = state.positions.keys().cloned().collect();
                    exit_syms.sort();

                    for sym in &exit_syms {
                        if let Some(sym_exit_idx) = ec_idx.get(sym.as_str()) {
                            let start = match sym_exit_idx.binary_search_by_key(&(ts + 1), |(t, _)| *t)
                            {
                                Ok(i) => i,
                                Err(i) => i,
                            };

                            if let Some(exit_bars) = ec.get(sym.as_str()) {
                                // Use the last fully-closed indicator-bar snapshot for
                                // sub-bar exits to avoid peeking at the current indicator
                                // bar before it closes (same anti-lookahead rule as
                                // sub-bar entry evaluation).
                                let base_snap = prev_indicator_snaps
                                    .get(sym.as_str())
                                    .cloned()
                                    .or_else(|| {
                                        state
                                            .indicators
                                            .get(sym.as_str())
                                            .map(|bank| bank.latest_snap())
                                    })
                                    .unwrap_or_else(|| make_minimal_snap(0.0, ts));

                                for &(sub_ts, bar_i) in &sym_exit_idx[start..] {
                                    if sub_ts > next_ts {
                                        break;
                                    }
                                    if !state.positions.contains_key(sym.as_str()) {
                                        break; // Already exited
                                    }
                                    if let Some(sub_bar) = exit_bars.get(bar_i) {
                                        if is_exit_cooldown_active(&state, sym.as_str(), sub_ts, cfg) {
                                            continue;
                                        }
                                        let sub_snap = make_exit_snap(&base_snap, sub_bar);
                                        if let Some(exit_result) = evaluate_kernel_exit(
                                            &mut state,
                                            sym.as_str(),
                                            &sub_snap,
                                            sub_ts,
                                        ) {
                                            apply_exit(
                                                &mut state,
                                                sym.as_str(),
                                                &exit_result,
                                                &sub_snap,
                                                sub_ts,
                                                cfg,
                                            );
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Entry sub-bar block (with signal ranking) ─────────────────
        // When entry_candles is provided, evaluate entry signals at sub-bar
        // resolution (indicator-bar indicators + sub-bar price).
        // Signals at each sub-bar tick are collected across all symbols,
        // ranked by score, then executed — matching the indicator-bar ranking.
        if let (Some(enc), Some(ref enc_idx)) = (entry_candles, &entry_bar_index) {
            let sub_equity = state.balance
                + unrealized_pnl(&state.positions, &state.indicators, ts, candles, &bar_index);
            let entry_bar_ms = if cfg.engine.signal_on_candle_close {
                interval_to_ms(&cfg.engine.entry_interval)
            } else {
                0
            };

            // Build a merged timeline of unique sub-bar timestamps across all symbols.
            // Default range is (ts+1 .. next_ts], but when signal-on-candle-close
            // is enabled we evaluate the sub-bar whose close aligns to next_ts.
            let sub_tick_from = if cfg.engine.signal_on_candle_close && entry_bar_ms > 0 {
                next_ts.saturating_sub(entry_bar_ms)
            } else if cfg.engine.signal_on_candle_close {
                next_ts
            } else {
                ts + 1
            };
            let sub_tick_to = next_ts;
            let mut sub_bar_ticks: Vec<i64> = Vec::new();
            for sym in &symbols {
                if let Some(sym_entry_idx) = enc_idx.get(sym.as_str()) {
                    let start = match sym_entry_idx.binary_search_by_key(&sub_tick_from, |(t, _)| *t) {
                        Ok(i) => i,
                        Err(i) => i,
                    };
                    for &(sub_ts, _) in &sym_entry_idx[start..] {
                        if sub_ts > sub_tick_to {
                            break;
                        }
                        if cfg.engine.signal_on_candle_close && entry_bar_ms > 0 {
                            let sub_close_ts = sub_ts.saturating_add(entry_bar_ms);
                            if sub_close_ts < next_ts {
                                continue;
                            }
                            if sub_close_ts > next_ts {
                                break;
                            }
                        }
                        sub_bar_ticks.push(sub_ts);
                    }
                }
            }
            sub_bar_ticks.sort_unstable();
            sub_bar_ticks.dedup();

            // Process each sub-bar tick: collect candidates across symbols, rank, execute.
            for sub_ts in &sub_bar_ticks {
                if entries_this_bar >= cfg.trade.max_entry_orders_per_loop {
                    break;
                }

                let mut sub_candidates: Vec<EntryCandidate> = Vec::new();

                for sym in &symbols {
                    // Skip warmup
                    let bc = state.bar_counts.get(sym.as_str()).copied().unwrap_or(0);
                    if bc < lookback {
                        continue;
                    }

                    // Look up this symbol's bar at this sub-bar tick
                    if let Some(sym_entry_idx) = enc_idx.get(sym.as_str()) {
                        // Binary search for exact timestamp match
                        if let Ok(idx) = sym_entry_idx.binary_search_by_key(sub_ts, |(t, _)| *t) {
                            let (_, bar_i) = sym_entry_idx[idx];
                            if let Some(entry_bars) = enc.get(sym.as_str()) {
                                if let Some(sub_bar) = entry_bars.get(bar_i) {
                                    let eval_ts = if cfg.engine.signal_on_candle_close {
                                        next_ts
                                    } else {
                                        *sub_ts
                                    };
                                    let base_snap = if cfg.engine.signal_on_candle_close {
                                        current_indicator_snaps
                                            .get(sym.as_str())
                                            .cloned()
                                            .unwrap_or_else(|| make_minimal_snap(0.0, eval_ts))
                                    } else {
                                        prev_indicator_snaps
                                            .get(sym.as_str())
                                            .cloned()
                                            .unwrap_or_else(|| make_minimal_snap(0.0, eval_ts))
                                    };
                                    let sub_snap = make_exit_snap(&base_snap, sub_bar);
                                    let slope =
                                        sub_bar_slopes.get(sym.as_str()).copied().unwrap_or(0.0);

                                    // Evaluate signal (same logic as try_sub_bar_entry but collect instead)
                                    if let Some(cand) = evaluate_sub_bar_candidate(
                                        &state,
                                        sym.as_str(),
                                        &sub_snap,
                                        cfg,
                                        btc_bullish,
                                        breadth_pct,
                                        slope,
                                        eval_ts,
                                    ) {
                                        // Sub-bar path parity with indicator-bar path:
                                        // if the symbol already has a same-direction position,
                                        // route accepted signal into pyramiding checks instead
                                        // of ranking as a fresh OPEN candidate.
                                        let existing_pos_type =
                                            state.positions.get(sym.as_str()).map(|pos| pos.pos_type);
                                        if let Some(pos_type) = existing_pos_type {
                                            let desired_type = match cand.signal {
                                                Signal::Buy => PositionType::Long,
                                                Signal::Sell => PositionType::Short,
                                                Signal::Neutral => continue,
                                            };
                                            if pos_type == desired_type && cfg.trade.enable_pyramiding {
                                                try_pyramid(
                                                    &mut state,
                                                    sym.as_str(),
                                                    &cand.snap,
                                                    cfg,
                                                    cand.confidence,
                                                    cand.atr,
                                                    cand.ts,
                                                );
                                            }
                                            continue;
                                        }
                                        sub_candidates.push(cand);
                                    }
                                }
                            }
                        }
                    }
                }

                // Rank sub-bar candidates by score (same formula as indicator-bar)
                if !sub_candidates.is_empty() {
                    sub_candidates.sort_by(|a, b| {
                        let score_a = (a.confidence as i32) * 100 + a.adx as i32;
                        let score_b = (b.confidence as i32) * 100 + b.adx as i32;
                        score_b.cmp(&score_a).then_with(|| a.symbol.cmp(&b.symbol))
                    });

                    let debug_filter = match (
                        std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
                        std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
                    ) {
                        (Ok(sym_filter), Ok(ts_filter_raw)) => {
                            Some((sym_filter, ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN)))
                        }
                        _ => None,
                    };
                    if let Some((ref sym_filter, ts_filter)) = debug_filter {
                        if *sub_ts == ts_filter {
                            eprintln!(
                                "[cpu-sub-rank-debug] ts_ms={} entries_this_bar_start={} max_entries={} candidates_at_ts:",
                                ts_filter,
                                entries_this_bar,
                                cfg.trade.max_entry_orders_per_loop
                            );
                            for (idx, cand) in sub_candidates.iter().enumerate() {
                                let score = (cand.confidence as i32) * 100 + cand.adx as i32;
                                eprintln!(
                                    "[cpu-sub-rank-debug] idx={} symbol={} score={} conf={:?} adx={:.6} signal={:?}",
                                    idx, cand.symbol, score, cand.confidence, cand.adx, cand.signal
                                );
                            }
                            let _ = sym_filter;
                        }
                    }

                    for cand in &sub_candidates {
                        if entries_this_bar >= cfg.trade.max_entry_orders_per_loop {
                            if let Some((ref sym_filter, ts_filter)) = debug_filter {
                                if cand.ts == ts_filter || cand.symbol == *sym_filter {
                                    eprintln!(
                                        "[cpu-sub-rank-debug] break_on_entry_limit symbol={} ts_ms={} entries_this_bar={} max_entries={}",
                                        cand.symbol,
                                        cand.ts,
                                        entries_this_bar,
                                        cfg.trade.max_entry_orders_per_loop
                                    );
                                }
                            }
                            break;
                        }
                        // Re-check: position may have been opened for this symbol by a higher-ranked candidate
                        if state.positions.contains_key(&cand.symbol) {
                            if let Some((ref sym_filter, ts_filter)) = debug_filter {
                                if cand.symbol == *sym_filter && cand.ts == ts_filter {
                                    eprintln!(
                                        "[cpu-sub-rank-debug] sym={} ts_ms={} rejected=already_open",
                                        cand.symbol, cand.ts
                                    );
                                }
                            }
                            continue;
                        }
                        let total_margin = total_margin_used(&state.positions);
                        let exposure = evaluate_exposure_guard(ExposureGuardInput {
                            open_positions: state.positions.len(),
                            max_open_positions: Some(cfg.trade.max_open_positions),
                            total_margin_used: total_margin,
                            equity: sub_equity,
                            max_total_margin_pct: cfg.trade.max_total_margin_pct,
                            allow_zero_margin_headroom: false,
                        });
                        if let Some((ref sym_filter, ts_filter)) = debug_filter {
                            if cand.symbol == *sym_filter && cand.ts == ts_filter {
                                eprintln!(
                                    "[cpu-sub-rank-debug] sym={} ts_ms={} exposure_allowed={} blocked_reason={:?} equity={:.12} total_margin={:.12} headroom={:.12} max_total_margin_pct={:.12}",
                                    cand.symbol,
                                    cand.ts,
                                    exposure.allowed,
                                    exposure.blocked_reason,
                                    sub_equity,
                                    total_margin,
                                    exposure.margin_headroom,
                                    cfg.trade.max_total_margin_pct
                                );
                            }
                        }
                        if !exposure.allowed {
                            if matches!(
                                exposure.blocked_reason,
                                Some(ExposureBlockReason::MaxOpenPositions)
                            ) {
                                break;
                            }
                            continue;
                        }

                        let opened = execute_sub_bar_entry(
                            &mut state,
                            ExecuteSubBarEntryInput {
                                sym: &cand.symbol,
                                snap: &cand.snap,
                                cfg,
                                confidence: cand.confidence,
                                atr: cand.atr,
                                entry_adx_threshold: cand.entry_adx_threshold,
                                signal: cand.signal,
                                ts: cand.ts,
                                equity: sub_equity,
                                gate_eval: &cand.gate_eval,
                            },
                        );
                        if let Some((ref sym_filter, ts_filter)) = debug_filter {
                            if cand.symbol == *sym_filter && cand.ts == ts_filter {
                                eprintln!(
                                    "[cpu-sub-rank-debug] sym={} ts_ms={} opened={} entries_this_bar_before_inc={}",
                                    cand.symbol, cand.ts, opened, entries_this_bar
                                );
                            }
                        }
                        if opened {
                            entries_this_bar += 1;
                        }
                    }
                }
            }
        }

        // ── Funding rate payments at hourly boundaries ───────────────────
        // Funding is settled every hour at the :00 boundary on Hyperliquid.
        // Check if this bar crosses an hourly boundary and apply funding to open positions.
        if let Some(fr) = funding_rates {
            if !state.positions.is_empty() {
                let ts_i = timestamps.binary_search(&ts).unwrap_or(0);
                let prev_ts = if ts_i > 0 { timestamps[ts_i - 1] } else { ts };

                // Find hourly boundaries crossed between prev_ts (exclusive) and ts (inclusive).
                // Hourly boundary = timestamp divisible by 3_600_000 ms.
                let hour_ms: i64 = 3_600_000;
                let first_boundary = ((prev_ts / hour_ms) + 1) * hour_ms;

                let mut boundary = first_boundary;
                while boundary <= ts {
                    let mut open_syms: Vec<String> = state.positions.keys().cloned().collect();
                    open_syms.sort();
                    for sym in open_syms {
                        if let Some(pos) = state.positions.get(&sym) {
                            if let Some(rates) = fr.get(&sym) {
                                // Find the funding rate at this boundary
                                if let Some(rate) = lookup_funding_rate(rates, boundary) {
                                    let price = state
                                        .indicators
                                        .get(&sym)
                                        .map(|b| b.prev_close)
                                        .unwrap_or(pos.entry_price);
                                    let delta_usd = accounting::funding_delta(
                                        matches!(pos.pos_type, PositionType::Long),
                                        pos.size,
                                        price,
                                        rate,
                                    );
                                    state.balance += delta_usd;

                                    state.trades.push(TradeRecord {
                                        timestamp_ms: boundary,
                                        symbol: sym.to_string(),
                                        action: "FUNDING".to_string(),
                                        price,
                                        size: pos.size,
                                        notional: pos.size * price,
                                        reason: format!("Funding rate={:.6}", rate),
                                        confidence: pos.confidence,
                                        pnl: delta_usd,
                                        fee_usd: 0.0,
                                        balance: state.balance,
                                        entry_atr: pos.entry_atr,
                                        leverage: pos.leverage,
                                        margin_used: pos.margin_used,
                                        ..Default::default()
                                    });
                                }
                            }
                        }
                    }
                    boundary += hour_ms;
                }
            }
        }

        // Record equity curve point
        let unrealized =
            unrealized_pnl_simple(&state.positions, &timestamps, ts, candles, &bar_index);
        state.equity_curve.push((ts, state.balance + unrealized));
    }

    // -- Force-close remaining positions at scoped terminal bar --
    // Use the last timeline timestamp within `to_ts` when scope is set.
    // This avoids leaking future prices outside the requested replay window.
    let terminal_ts = if let Some(to) = to_ts {
        match timestamps.binary_search(&to) {
            Ok(i) => timestamps[i],
            Err(0) => to,
            Err(i) => timestamps[i - 1],
        }
    } else {
        *timestamps.last().unwrap_or(&0)
    };

    let mut remaining: Vec<String> = state.positions.keys().cloned().collect();
    remaining.sort();
    for sym in remaining {
        if state.positions.contains_key(&sym) {
            let terminal_price = lookup_bar(&bar_index, &sym, terminal_ts, candles)
                .map(|bar| bar.c)
                .or_else(|| last_price_at_or_before(candles, &sym, terminal_ts));
            let Some(terminal_price) = terminal_price else {
                continue;
            };
            if terminal_price <= 0.0 {
                continue;
            }
            let exit = ExitResult::exit("End of Backtest", terminal_price);
            let snap = make_minimal_snap(terminal_price, terminal_ts);
            apply_exit(
                &mut state,
                &sym,
                &exit,
                &snap,
                terminal_ts,
                cfg,
            );
        }
    }

    SimResult {
        trades: state.trades,
        signals: state.signals,
        decision_diagnostics: state.decision_diagnostics,
        final_balance: state.balance,
        equity_curve: state.equity_curve,
        gate_stats: state.gate_stats,
    }
}

// ---------------------------------------------------------------------------
// Timeline construction
// ---------------------------------------------------------------------------

fn build_timeline(candles: &CandleData) -> Vec<i64> {
    let mut set: Vec<i64> = candles
        .values()
        .flat_map(|bars| bars.iter().map(|b| b.t))
        .collect();
    set.sort_unstable();
    set.dedup();
    set
}

/// Build a per-symbol HashMap<timestamp -> index> for O(1) bar lookup.
fn build_bar_index(candles: &CandleData) -> FxHashMap<String, FxHashMap<i64, usize>> {
    let mut idx: FxHashMap<String, FxHashMap<i64, usize>> = FxHashMap::default();
    for (sym, bars) in candles {
        let mut sym_idx = FxHashMap::default();
        for (i, bar) in bars.iter().enumerate() {
            sym_idx.insert(bar.t, i);
        }
        idx.insert(sym.clone(), sym_idx);
    }
    idx
}

fn lookup_bar<'a>(
    index: &FxHashMap<String, FxHashMap<i64, usize>>,
    symbol: &str,
    ts: i64,
    candles: &'a CandleData,
) -> Option<&'a OhlcvBar> {
    let sym_idx = index.get(symbol)?;
    let &i = sym_idx.get(&ts)?;
    candles.get(symbol).and_then(|bars| bars.get(i))
}

// ---------------------------------------------------------------------------
// BTC context
// ---------------------------------------------------------------------------

fn compute_btc_bullish(
    state: &SimState,
    _ts: i64,
    _bar_index: &FxHashMap<String, FxHashMap<i64, usize>>,
    _candles: &CandleData,
) -> Option<bool> {
    // Check if we have BTC indicators
    if let Some(bank) = state.indicators.get("BTC") {
        if bank.bar_count > 0 {
            // BTC is bullish when price > EMA_slow
            return Some(bank.prev_close > bank.prev_ema_slow);
        }
    }
    // Also check BTCUSDT variant
    if let Some(bank) = state.indicators.get("BTCUSDT") {
        if bank.bar_count > 0 {
            return Some(bank.prev_close > bank.prev_ema_slow);
        }
    }
    None // No BTC data available
}

// ---------------------------------------------------------------------------
// Market breadth
// ---------------------------------------------------------------------------

fn compute_market_breadth(state: &SimState) -> f64 {
    let mut bullish = 0u32;
    let mut total = 0u32;
    for bank in state.indicators.values() {
        if bank.bar_count < 2 {
            continue;
        }
        total += 1;
        // EMA_fast > EMA_slow means bullish
        if bank.prev_ema_fast > bank.prev_ema_slow {
            bullish += 1;
        }
    }
    if total == 0 {
        return 50.0;
    }
    (bullish as f64 / total as f64) * 100.0
}

// ---------------------------------------------------------------------------
// EMA slow slope
// ---------------------------------------------------------------------------

fn compute_ema_slow_slope(history: &[f64], window: usize, current_close: f64) -> f64 {
    if history.len() < window || current_close <= 0.0 {
        return 0.0;
    }
    let current = history[history.len() - 1];
    let past = history[history.len() - window];
    (current - past) / current_close
}

// ---------------------------------------------------------------------------
// Engine-level transforms
// ---------------------------------------------------------------------------

fn apply_atr_floor(atr: f64, price: f64, min_atr_pct: f64) -> f64 {
    if min_atr_pct > 0.0 {
        let floor = price * min_atr_pct;
        if atr < floor {
            return floor;
        }
    }
    atr
}

fn apply_reverse(signal: Signal, cfg: &StrategyConfig, breadth_pct: f64) -> Signal {
    let mut should_reverse = cfg.trade.reverse_entry_signal;

    // Auto-reverse based on market breadth
    if cfg.market_regime.enable_auto_reverse {
        let low = cfg.market_regime.auto_reverse_breadth_low;
        let high = cfg.market_regime.auto_reverse_breadth_high;
        if breadth_pct >= low && breadth_pct <= high {
            should_reverse = true; // Choppy market → fade
        } else {
            should_reverse = false; // Trending → follow
        }
    }

    if should_reverse {
        match signal {
            Signal::Buy => Signal::Sell,
            Signal::Sell => Signal::Buy,
            Signal::Neutral => Signal::Neutral,
        }
    } else {
        signal
    }
}

fn apply_regime_filter(signal: Signal, cfg: &StrategyConfig, breadth_pct: f64) -> Signal {
    if !cfg.market_regime.enable_regime_filter {
        return signal;
    }
    match signal {
        Signal::Sell if breadth_pct > cfg.market_regime.breadth_block_short_above => {
            Signal::Neutral // Block SHORT in strong bull market
        }
        Signal::Buy if breadth_pct < cfg.market_regime.breadth_block_long_below => {
            Signal::Neutral // Block LONG in strong bear market
        }
        _ => signal,
    }
}

// ---------------------------------------------------------------------------
// PESC (Post-Exit Same-Direction Cooldown)
// ---------------------------------------------------------------------------

fn is_pesc_blocked(
    state: &SimState,
    symbol: &str,
    desired_type: PositionType,
    current_ts: i64,
    adx: f64,
    cfg: &StrategyConfig,
) -> bool {
    // Gate: reentry_cooldown_minutes == 0 disables PESC entirely (matches Python engine)
    if cfg.trade.reentry_cooldown_minutes == 0 {
        return false;
    }

    let (close_ts, close_type, ref close_reason) = match state.last_close.get(symbol) {
        Some(v) => v.clone(),
        None => return false,
    };

    // No cooldown after signal flips
    if close_reason == "Signal Flip" {
        return false;
    }

    // Only applies to same direction
    if close_type != desired_type {
        return false;
    }

    // ADX-adaptive cooldown interpolation
    let min_cd = cfg.trade.reentry_cooldown_min_mins as f64;
    let max_cd = cfg.trade.reentry_cooldown_max_mins as f64;

    let cooldown_mins = if adx >= 40.0 {
        min_cd
    } else if adx <= 25.0 {
        max_cd
    } else {
        // Linear interpolation: ADX 25→40 maps to max_cd→min_cd
        let t = (adx - 25.0) / 15.0;
        max_cd + t * (min_cd - max_cd)
    };

    let cooldown_ms = (cooldown_mins * 60_000.0) as i64;
    let elapsed = current_ts - close_ts;

    elapsed < cooldown_ms
}

// ---------------------------------------------------------------------------
// Entry/Exit cooldowns
// ---------------------------------------------------------------------------

fn is_entry_cooldown_active(state: &SimState, symbol: &str, ts: i64, cfg: &StrategyConfig) -> bool {
    is_symbol_cooldown_active(
        &state.last_entry_attempt_ms,
        symbol,
        ts,
        cfg.trade.entry_cooldown_s as i64,
    )
}

fn is_exit_cooldown_active(state: &SimState, symbol: &str, ts: i64, cfg: &StrategyConfig) -> bool {
    is_symbol_cooldown_active(
        &state.last_exit_attempt_ms,
        symbol,
        ts,
        cfg.trade.exit_cooldown_s as i64,
    )
}

fn note_entry_attempt(state: &mut SimState, symbol: &str, ts: i64) {
    state.last_entry_attempt_ms.insert(symbol.to_string(), ts);
}

fn note_exit_attempt(state: &mut SimState, symbol: &str, ts: i64) {
    state.last_exit_attempt_ms.insert(symbol.to_string(), ts);
}

fn is_symbol_cooldown_active(
    last_attempts_ms: &FxHashMap<String, i64>,
    symbol: &str,
    ts: i64,
    cooldown_s: i64,
) -> bool {
    if cooldown_s <= 0 {
        return false;
    }
    let last_ts = match last_attempts_ms.get(symbol) {
        Some(v) => *v,
        None => return false,
    };
    let cooldown_ms = cooldown_s.saturating_mul(1000);
    ts.saturating_sub(last_ts) < cooldown_ms
}

fn to_confidence_tier(confidence: Confidence) -> ConfidenceTier {
    match confidence {
        Confidence::Low => ConfidenceTier::Low,
        Confidence::Medium => ConfidenceTier::Medium,
        Confidence::High => ConfidenceTier::High,
    }
}

// ---------------------------------------------------------------------------
// Entry sizing
// ---------------------------------------------------------------------------

fn compute_entry_size(
    _symbol: &str,
    equity: f64,
    price: f64,
    confidence: Confidence,
    atr: f64,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
) -> (f64, f64, f64) {
    let tc = &cfg.trade;
    let sizing = compute_entry_sizing(EntrySizingInput {
        equity,
        price,
        atr,
        adx: snap.adx,
        confidence: to_confidence_tier(confidence),
        allocation_pct: tc.allocation_pct,
        enable_dynamic_sizing: tc.enable_dynamic_sizing,
        confidence_mult_high: tc.confidence_mult_high,
        confidence_mult_medium: tc.confidence_mult_medium,
        confidence_mult_low: tc.confidence_mult_low,
        adx_sizing_min_mult: tc.adx_sizing_min_mult,
        adx_sizing_full_adx: tc.adx_sizing_full_adx,
        vol_baseline_pct: tc.vol_baseline_pct,
        vol_scalar_min: tc.vol_scalar_min,
        vol_scalar_max: tc.vol_scalar_max,
        leverage_low: tc.leverage_low,
        leverage_medium: tc.leverage_medium,
        leverage_high: tc.leverage_high,
    });

    (sizing.size, sizing.margin_used, sizing.leverage)
}

// ---------------------------------------------------------------------------
// Exit application
// ---------------------------------------------------------------------------

/// Convert an interval string (e.g. "15m", "1h", "4h", "1d") to milliseconds.
fn interval_to_ms(interval: &str) -> i64 {
    let s = interval.trim();
    if s.is_empty() {
        return 0;
    }
    let (num_part, unit) = s.split_at(s.len() - 1);
    let n: i64 = num_part.parse().unwrap_or(1);
    match unit {
        "m" => n * 60_000,
        "h" => n * 3_600_000,
        "d" => n * 86_400_000,
        _ => 0,
    }
}

fn apply_exit(
    state: &mut SimState,
    symbol: &str,
    exit: &ExitResult,
    snap: &IndicatorSnapshot,
    ts: i64,
    cfg: &StrategyConfig,
) {
    let pos = match state.positions.get(symbol) {
        Some(p) => p.clone(),
        None => return,
    };

    // Build exit context snapshot
    let bar_ms = interval_to_ms(&cfg.engine.interval);
    let bars_held = if bar_ms > 0 {
        ((ts - pos.open_time_ms).max(0) / bar_ms) as u32
    } else {
        0
    };
    let exit_ctx = ExitContext {
        trailing_active: pos.trailing_sl.is_some(),
        trailing_high_water_mark: pos.trailing_sl.unwrap_or(0.0),
        sl_atr_mult_applied: cfg.trade.sl_atr_mult,
        tp_atr_mult_applied: cfg.trade.tp_atr_mult,
        smart_exit_threshold: if cfg.trade.smart_exit_adx_exhaustion_lt > 0.0 {
            Some(cfg.trade.smart_exit_adx_exhaustion_lt)
        } else {
            None
        },
        indicator_at_exit: Some(snap.clone()),
        bars_held,
        max_unrealized_pnl: pos.mfe_usd,
        min_unrealized_pnl: pos.mae_usd,
    };

    let exit_price = if exit.exit_price > 0.0 {
        exit.exit_price
    } else {
        snap.close
    };

    // Apply slippage to exit
    let fill_price = accounting::quantize(match pos.pos_type {
        PositionType::Long => exit_price * (1.0 - 0.5 / 10_000.0), // Conservative: half a bps
        PositionType::Short => exit_price * (1.0 + 0.5 / 10_000.0),
    });

    if let Some(partial_pct) = exit.partial_pct {
        // Partial exit
        let partial_fill =
            accounting::build_partial_close_plan(pos.size, pos.margin_used, partial_pct);
        let exit_size = partial_fill.closed_size;
        let close = accounting::apply_close_fill(
            matches!(pos.pos_type, PositionType::Long),
            pos.entry_price,
            fill_price,
            exit_size,
            maker_taker_fee_rate(&state.kernel_params, accounting::FeeRole::Taker),
        );
        // Margin-based: balance += pnl - fee (margin tracked per-position, not in balance).
        state.balance += close.pnl - close.fee_usd;

        // Record PESC info (partial exits also count)
        state
            .last_close
            .insert(symbol.to_string(), (ts, pos.pos_type, exit.reason.clone()));
        note_exit_attempt(state, symbol, ts);

        let action = match pos.pos_type {
            PositionType::Long => "REDUCE_LONG",
            PositionType::Short => "REDUCE_SHORT",
        };
        let closed_margin = pos.margin_used
            * if pos.size > 0.0 {
                partial_fill.closed_size / pos.size
            } else {
                0.0
            };
        state.trades.push(TradeRecord {
            timestamp_ms: ts,
            symbol: symbol.to_string(),
            action: action.to_string(),
            price: fill_price,
            size: exit_size,
            notional: close.notional,
            reason: exit.reason.clone(),
            confidence: pos.confidence,
            pnl: close.pnl,
            fee_usd: close.fee_usd,
            balance: state.balance,
            entry_atr: pos.entry_atr,
            leverage: pos.leverage,
            margin_used: closed_margin,
            exit_context: Some(exit_ctx.clone()),
            ..Default::default()
        });

        // Reduce position in place
        if let Some(p) = state.positions.get_mut(symbol) {
            let reduce_fraction = if pos.size > 0.0 {
                partial_fill.closed_size / pos.size
            } else {
                0.0
            };
            p.reduce_by_fraction(reduce_fraction);
            // Partial exits represent TP1 in the current engine contract.
            // Do not couple this state transition to human-readable reason text.
            p.tp1_taken = true;
        }

        // Sync kernel state: reduce kernel position + return margin proportionally.
        if let Some(kpos) = state.kernel_state.positions.get_mut(symbol) {
            let close_frac = if pos.size > 0.0 {
                exit_size / pos.size
            } else {
                0.0
            };
            let returned_margin = accounting::quantize(kpos.margin_usd * close_frac);
            kpos.margin_usd = accounting::quantize(kpos.margin_usd - returned_margin);
            kpos.quantity = accounting::quantize(kpos.quantity - exit_size);
            kpos.notional_usd =
                accounting::quantize(kpos.notional_usd - (exit_size * pos.entry_price));
            state.kernel_state.cash_usd = accounting::quantize(
                state.kernel_state.cash_usd + returned_margin + close.pnl - close.fee_usd,
            );
        }
    } else {
        // Full exit
        let close = accounting::apply_close_fill(
            matches!(pos.pos_type, PositionType::Long),
            pos.entry_price,
            fill_price,
            pos.size,
            maker_taker_fee_rate(&state.kernel_params, accounting::FeeRole::Taker),
        );
        // Margin-based: balance += pnl - fee.
        state.balance += close.pnl - close.fee_usd;

        // Record PESC info
        state
            .last_close
            .insert(symbol.to_string(), (ts, pos.pos_type, exit.reason.clone()));
        note_exit_attempt(state, symbol, ts);

        let action = match pos.pos_type {
            PositionType::Long => "CLOSE_LONG",
            PositionType::Short => "CLOSE_SHORT",
        };
        state.trades.push(TradeRecord {
            timestamp_ms: ts,
            symbol: symbol.to_string(),
            action: action.to_string(),
            price: fill_price,
            size: pos.size,
            notional: close.notional,
            reason: exit.reason.clone(),
            confidence: pos.confidence,
            pnl: close.pnl,
            fee_usd: close.fee_usd,
            balance: state.balance,
            entry_atr: pos.entry_atr,
            leverage: pos.leverage,
            margin_used: pos.margin_used,
            exit_context: Some(exit_ctx),
            ..Default::default()
        });

        // Sync kernel state: remove position + return margin to cash.
        if let Some(kpos) = state.kernel_state.positions.remove(symbol) {
            state.kernel_state.cash_usd = accounting::quantize(
                state.kernel_state.cash_usd + kpos.margin_usd + close.pnl - close.fee_usd,
            );
        }

        state.positions.remove(symbol);
    }
}

// ---------------------------------------------------------------------------
// Pyramiding
// ---------------------------------------------------------------------------

fn try_pyramid(
    state: &mut SimState,
    symbol: &str,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    confidence: Confidence,
    atr: f64,
    ts: i64,
) {
    let tc = &cfg.trade;
    let debug_target = match (
        std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
        std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
    ) {
        (Ok(sym_filter), Ok(ts_filter_raw)) => {
            symbol == sym_filter && ts == ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN)
        }
        _ => false,
    };
    let pos = match state.positions.get(symbol) {
        Some(p) => p,
        None => return,
    };

    // Check add limits
    if pos.adds_count >= tc.max_adds_per_symbol as u32 {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=max_adds adds={} max={}",
                symbol, ts, pos.adds_count, tc.max_adds_per_symbol
            );
        }
        return;
    }

    // Confidence gate for adds
    if !confidence.meets_min(tc.add_min_confidence) {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=min_conf conf={:?} min={:?}",
                symbol, ts, confidence, tc.add_min_confidence
            );
        }
        return;
    }

    // Cooldown since last add
    let elapsed_mins = (ts - pos.last_add_time_ms) as f64 / 60_000.0;
    if elapsed_mins < tc.add_cooldown_minutes as f64 {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=cooldown elapsed_mins={:.6} min={}",
                symbol, ts, elapsed_mins, tc.add_cooldown_minutes
            );
        }
        return;
    }

    // Must be in profit by min ATR (with DPS parity to Python live path).
    let mut min_profit_atr = tc.add_min_profit_atr;
    if snap.adx_slope > 0.75 && snap.atr_slope <= 0.0 {
        let is_rsi_extreme = match pos.pos_type {
            PositionType::Long => snap.rsi > 65.0,
            PositionType::Short => snap.rsi < 35.0,
        };
        if !is_rsi_extreme {
            min_profit_atr *= 0.5;
        }
    }

    let current_atr = if atr > 0.0 {
        atr
    } else if pos.entry_atr > 0.0 {
        pos.entry_atr
    } else if pos.entry_price > 0.0 {
        pos.entry_price * 0.005
    } else {
        0.0
    };
    if current_atr <= 0.0 {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=invalid_atr atr={:.12} entry_atr={:.12} entry_price={:.12}",
                symbol, ts, atr, pos.entry_atr, pos.entry_price
            );
        }
        return;
    }

    let profit_atr = match pos.pos_type {
        PositionType::Long => (snap.close - pos.entry_price) / current_atr,
        PositionType::Short => (pos.entry_price - snap.close) / current_atr,
    };
    if profit_atr < min_profit_atr {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=min_profit_atr profit_atr={:.12} min={:.12} atr={:.12} adx_slope={:.12} atr_slope={:.12} rsi={:.12}",
                symbol, ts, profit_atr, min_profit_atr, current_atr, snap.adx_slope, snap.atr_slope, snap.rsi
            );
        }
        return;
    }
    if is_entry_cooldown_active(state, symbol, ts, cfg) {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=entry_cooldown",
                symbol, ts
            );
        }
        return;
    }

    // Compute add size
    let equity = state.balance + unrealized_pnl_for_positions(&state.positions, snap.close);
    let leverage = pos.leverage;
    let add_sizing = match compute_pyramid_sizing(PyramidSizingInput {
        equity,
        price: snap.close,
        leverage,
        allocation_pct: tc.allocation_pct,
        add_fraction_of_base_margin: tc.add_fraction_of_base_margin,
        min_notional_usd: tc.min_notional_usd,
        bump_to_min_notional: tc.bump_to_min_notional,
    }) {
        Some(v) => v,
        None => {
            if debug_target {
                eprintln!(
                    "[cpu-pyr-debug] sym={} ts_ms={} rejected=sizing_none equity={:.12} price={:.12} lev={:.12}",
                    symbol, ts, equity, snap.close, leverage
                );
            }
            return;
        }
    };
    let add_margin = add_sizing.add_margin;
    let add_notional = add_sizing.add_notional;
    let add_size = add_sizing.add_size;

    // Margin cap check
    let total_margin = total_margin_used(&state.positions);
    let exposure = evaluate_exposure_guard(ExposureGuardInput {
        open_positions: state.positions.len(),
        max_open_positions: None,
        total_margin_used: total_margin + add_margin,
        equity,
        max_total_margin_pct: tc.max_total_margin_pct,
        allow_zero_margin_headroom: true,
    });
    if !exposure.allowed {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=exposure block={:?} total_margin={:.12} add_margin={:.12} equity={:.12} max_margin_pct={:.12} headroom={:.12}",
                symbol,
                ts,
                exposure.blocked_reason,
                total_margin,
                add_margin,
                equity,
                tc.max_total_margin_pct,
                exposure.margin_headroom
            );
        }
        return;
    }

    let add_signal = match pos.pos_type {
        PositionType::Long => Signal::Buy,
        PositionType::Short => Signal::Sell,
    };
    let decision = step_decision(
        state,
        StepDecisionInput {
            ts,
            symbol,
            signal: add_signal,
            price: snap.close,
            requested_notional_usd: Some(add_notional),
            source: "pyramid",
            cfg,
        },
    );
    if let Some(last) = state.decision_diagnostics.last_mut() {
        last.indicator_snapshot = Some(snap.clone());
    }
    let has_add = decision
        .intents
        .iter()
        .any(|intent| matches!(intent.kind, decision_kernel::OrderIntentKind::Add));
    if !has_add {
        if debug_target {
            eprintln!(
                "[cpu-pyr-debug] sym={} ts_ms={} rejected=no_add_intent add_notional={:.12} add_size={:.12} add_margin={:.12}",
                symbol, ts, add_notional, add_size, add_margin
            );
        }
        return;
    }
    if debug_target {
        eprintln!(
            "[cpu-pyr-debug] sym={} ts_ms={} accepted add_notional={:.12} add_size={:.12} add_margin={:.12} equity={:.12}",
            symbol, ts, add_notional, add_size, add_margin, equity
        );
    }
    let _ = apply_kernel_add_from_plan(
        state,
        symbol,
        cfg,
        snap,
        confidence,
        atr,
        add_size,
        add_notional,
        add_margin,
        ts,
    );
}

// ---------------------------------------------------------------------------
// Unrealized PnL helpers
// ---------------------------------------------------------------------------

fn sorted_position_symbols(positions: &FxHashMap<String, Position>) -> Vec<&str> {
    let mut syms: Vec<&str> = positions.keys().map(|s| s.as_str()).collect();
    syms.sort_unstable();
    syms
}

fn total_margin_used(positions: &FxHashMap<String, Position>) -> f64 {
    sorted_position_symbols(positions)
        .into_iter()
        .filter_map(|sym| positions.get(sym))
        .map(|p| p.margin_used)
        .sum()
}

/// Compute total unrealized PnL using last known price from indicator banks.
fn unrealized_pnl(
    positions: &FxHashMap<String, Position>,
    indicators: &FxHashMap<String, IndicatorBank>,
    _ts: i64,
    _candles: &CandleData,
    _bar_index: &FxHashMap<String, FxHashMap<i64, usize>>,
) -> f64 {
    sorted_position_symbols(positions)
        .into_iter()
        .filter_map(|sym| positions.get(sym))
        .map(|pos| {
            let price = indicators
                .get(&pos.symbol)
                .map(|b| b.prev_close)
                .unwrap_or(pos.entry_price);
            pos.profit_usd(price)
        })
        .sum()
}

/// Simple unrealized PnL for equity curve (uses last indicator close).
fn unrealized_pnl_simple(
    positions: &FxHashMap<String, Position>,
    _timestamps: &[i64],
    _ts: i64,
    _candles: &CandleData,
    _bar_index: &FxHashMap<String, FxHashMap<i64, usize>>,
) -> f64 {
    sorted_position_symbols(positions)
        .into_iter()
        .filter_map(|sym| positions.get(sym))
        .map(|pos| {
            // Use entry price as fallback (will be updated by indicator banks)
            pos.profit_usd(pos.entry_price) // This is 0 for just-opened positions
        })
        .sum()
}

/// Quick unrealized PnL using a single snapshot price (for pyramid sizing).
fn unrealized_pnl_for_positions(
    positions: &FxHashMap<String, Position>,
    _current_price: f64,
) -> f64 {
    // Approximate: each position at its entry (gives 0 unrealized)
    // In practice during pyramid check we just use balance as equity
    sorted_position_symbols(positions)
        .into_iter()
        .filter_map(|sym| positions.get(sym))
        .map(|pos| pos.profit_usd(pos.entry_price))
        .sum()
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn last_price_at_or_before(candles: &CandleData, symbol: &str, ts: i64) -> Option<f64> {
    let bars = candles.get(symbol)?;
    match bars.binary_search_by_key(&ts, |b| b.t) {
        Ok(i) => bars.get(i).map(|b| b.c),
        Err(0) => None,
        Err(i) => bars.get(i - 1).map(|b| b.c),
    }
}

/// Evaluate whether a sub-bar entry candidate should be collected for ranking.
/// Returns Some(EntryCandidate) if the signal passes gates, None otherwise.
fn evaluate_sub_bar_candidate(
    state: &SimState,
    sym: &str,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    btc_bullish: Option<bool>,
    breadth_pct: f64,
    ema_slow_slope_pct: f64,
    ts: i64,
) -> Option<EntryCandidate> {
    let gate_result = gates::check_gates(snap, cfg, sym, btc_bullish, ema_slow_slope_pct);
    let (mut signal, confidence, entry_adx_threshold) =
        entry::generate_signal(snap, &gate_result, cfg, ema_slow_slope_pct);
    let debug_target = match (
        std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
        std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
    ) {
        (Ok(sym_filter), Ok(ts_filter_raw)) => {
            sym == sym_filter && ts == ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN)
        }
        _ => false,
    };

    if debug_target {
        eprintln!(
            "[cpu-sub-cand-debug] sym={} ts_ms={} raw_signal={:?} conf={:?} breadth={:.6} btc_bull={:?} adx={:.6} adx_slope={:.6} macd={:.10} rsi={:.6}",
            sym,
            ts,
            signal,
            confidence,
            breadth_pct,
            btc_bullish,
            snap.adx,
            snap.adx_slope,
            snap.macd_hist,
            snap.rsi
        );
    }

    if signal == Signal::Neutral {
        if debug_target {
            eprintln!(
                "[cpu-sub-cand-debug] sym={} ts_ms={} rejected=neutral_raw breadth={:.6}",
                sym, ts, breadth_pct
            );
        }
        return None;
    }

    let atr = apply_atr_floor(snap.atr, snap.close, cfg.trade.min_atr_pct);
    signal = apply_reverse(signal, cfg, breadth_pct);
    if debug_target {
        eprintln!(
            "[cpu-sub-cand-debug] sym={} ts_ms={} after_reverse={:?} breadth={:.6}",
            sym, ts, signal, breadth_pct
        );
    }
    if signal == Signal::Neutral {
        if debug_target {
            eprintln!(
                "[cpu-sub-cand-debug] sym={} ts_ms={} rejected=neutral_after_reverse breadth={:.6}",
                sym, ts, breadth_pct
            );
        }
        return None;
    }
    signal = apply_regime_filter(signal, cfg, breadth_pct);
    if debug_target {
        eprintln!(
            "[cpu-sub-cand-debug] sym={} ts_ms={} after_regime={:?} breadth={:.6}",
            sym, ts, signal, breadth_pct
        );
    }
    if signal == Signal::Neutral {
        if debug_target {
            eprintln!(
                "[cpu-sub-cand-debug] sym={} ts_ms={} rejected=neutral_after_regime breadth={:.6}",
                sym, ts, breadth_pct
            );
        }
        return None;
    }

    let desired_type = match signal {
        Signal::Buy => PositionType::Long,
        Signal::Sell => PositionType::Short,
        Signal::Neutral => return None,
    };

    if !confidence.meets_min(cfg.trade.entry_min_confidence) {
        if debug_target {
            eprintln!(
                "[cpu-sub-cand-debug] sym={} ts_ms={} rejected=min_conf conf={:?} min={:?}",
                sym, ts, confidence, cfg.trade.entry_min_confidence
            );
        }
        return None;
    }
    if is_pesc_blocked(state, sym, desired_type, ts, snap.adx, cfg) {
        if debug_target {
            eprintln!(
                "[cpu-sub-cand-debug] sym={} ts_ms={} rejected=pesc desired={:?} adx={:.6}",
                sym, ts, desired_type, snap.adx
            );
        }
        return None;
    }
    if cfg.trade.enable_ssf_filter {
        let ssf_ok = match signal {
            Signal::Buy => snap.macd_hist > 0.0,
            Signal::Sell => snap.macd_hist < 0.0,
            Signal::Neutral => true,
        };
        if !ssf_ok {
            if debug_target {
                eprintln!(
                    "[cpu-sub-cand-debug] sym={} ts_ms={} rejected=ssf signal={:?} macd={:.10}",
                    sym, ts, signal, snap.macd_hist
                );
            }
            return None;
        }
    }
    if cfg.trade.enable_reef_filter {
        let reef_blocked = match signal {
            Signal::Buy => {
                if snap.adx < cfg.trade.reef_adx_threshold {
                    snap.rsi > cfg.trade.reef_long_rsi_block_gt
                } else {
                    snap.rsi > cfg.trade.reef_long_rsi_extreme_gt
                }
            }
            Signal::Sell => {
                if snap.adx < cfg.trade.reef_adx_threshold {
                    snap.rsi < cfg.trade.reef_short_rsi_block_lt
                } else {
                    snap.rsi < cfg.trade.reef_short_rsi_extreme_lt
                }
            }
            Signal::Neutral => false,
        };
        if reef_blocked {
            if debug_target {
                eprintln!(
                    "[cpu-sub-cand-debug] sym={} ts_ms={} rejected=reef signal={:?} adx={:.6} rsi={:.6}",
                    sym, ts, signal, snap.adx, snap.rsi
                );
            }
            return None;
        }
    }

    if debug_target {
        eprintln!(
            "[cpu-sub-cand-debug] sym={} ts_ms={} accepted signal={:?} conf={:?} adx={:.6} atr={:.10} entry_adx_thresh={:.6} breadth={:.6} btc_bull={:?}",
            sym, ts, signal, confidence, snap.adx, atr, entry_adx_threshold, breadth_pct, btc_bullish
        );
    }

    let gate_eval = build_gate_evaluation(&gate_result, snap, signal, confidence, cfg);

    Some(EntryCandidate {
        symbol: sym.to_string(),
        signal,
        confidence,
        adx: snap.adx,
        atr,
        entry_adx_threshold,
        snap: snap.clone(),
        ts,
        gate_eval,
    })
}

/// Execute a ranked sub-bar entry candidate. Opens a new position.
/// Returns true if a new position was opened.
struct ExecuteSubBarEntryInput<'a> {
    sym: &'a str,
    snap: &'a IndicatorSnapshot,
    cfg: &'a StrategyConfig,
    confidence: Confidence,
    atr: f64,
    entry_adx_threshold: f64,
    signal: Signal,
    ts: i64,
    equity: f64,
    gate_eval: &'a GateEvaluation,
}

fn execute_sub_bar_entry(state: &mut SimState, input: ExecuteSubBarEntryInput<'_>) -> bool {
    let ExecuteSubBarEntryInput {
        sym,
        snap,
        cfg,
        confidence,
        atr,
        entry_adx_threshold,
        signal,
        ts,
        equity,
        gate_eval,
    } = input;
    if state.positions.contains_key(sym) {
        return false;
    }
    if is_entry_cooldown_active(state, sym, ts, cfg) {
        return false;
    }

    let desired_type = match signal {
        Signal::Buy => PositionType::Long,
        Signal::Sell => PositionType::Short,
        Signal::Neutral => return false,
    };

    // Margin cap check
    let total_margin = total_margin_used(&state.positions);
    let exposure = evaluate_exposure_guard(ExposureGuardInput {
        open_positions: state.positions.len(),
        max_open_positions: Some(cfg.trade.max_open_positions),
        total_margin_used: total_margin,
        equity,
        max_total_margin_pct: cfg.trade.max_total_margin_pct,
        allow_zero_margin_headroom: false,
    });
    if !exposure.allowed {
        return false;
    }
    let margin_headroom = exposure.margin_headroom;

    // Sizing
    let (size, margin_used, leverage) =
        compute_entry_size(sym, equity, snap.close, confidence, atr, snap, cfg);
    let (mut size, mut margin_used) = if margin_used > margin_headroom {
        // M13: zero-guard on margin_used division
        let ratio = if margin_used > 1e-12 {
            margin_headroom / margin_used
        } else {
            0.0
        };
        (size * ratio, margin_headroom)
    } else {
        (size, margin_used)
    };

    let mut notional = size * snap.close;
    if notional < cfg.trade.min_notional_usd {
        if cfg.trade.bump_to_min_notional && snap.close > 0.0 {
            size = cfg.trade.min_notional_usd / snap.close;
            margin_used = size * snap.close / leverage;
            notional = size * snap.close;
            if margin_used > margin_headroom {
                return false;
            }
        } else {
            return false;
        }
    }

    let decision = step_decision(
        state,
        StepDecisionInput {
            ts,
            symbol: sym,
            signal,
            price: snap.close,
            requested_notional_usd: Some(notional),
            source: "sub-bar-open",
            cfg,
        },
    );
    // Attach per-signal gate evaluation and indicator snapshot to the trace entry
    if let Some(last) = state.decision_diagnostics.last_mut() {
        last.gate_result = Some(gate_eval.clone());
        last.indicator_snapshot = Some(snap.clone());
    }
    let has_open = decision.intents.iter().any(|intent| {
        matches!(
            intent.kind,
            decision_kernel::OrderIntentKind::Open | decision_kernel::OrderIntentKind::Add,
        )
    });
    if !has_open {
        if let (Ok(sym_filter), Ok(ts_filter_raw)) = (
            std::env::var("AQC_DEBUG_ENTRY_SYMBOL"),
            std::env::var("AQC_DEBUG_ENTRY_TS_MS"),
        ) {
            let ts_filter = ts_filter_raw.parse::<i64>().unwrap_or(i64::MIN);
            if sym == sym_filter && ts == ts_filter {
                let intent_kinds: Vec<String> = decision
                    .intents
                    .iter()
                    .map(|intent| format!("{:?}", intent.kind))
                    .collect();
                let kernel_lev = state.kernel_params.leverage.max(1.0);
                let kernel_margin_req = if kernel_lev > 0.0 {
                    notional / kernel_lev
                } else {
                    0.0
                };
                eprintln!(
                    "[cpu-sub-open-debug] sym={} ts_ms={} rejected=no_open_intent intents={:?} gate_blocked={} gate_reasons={:?} cooldown_blocked={} pesc_blocked={} warnings={:?} notional={:.12} lev_used={:.12} margin_used={:.12} kernel_lev={:.12} kernel_margin_req={:.12} kernel_cash={:.12}",
                    sym,
                    ts,
                    intent_kinds,
                    decision.diagnostics.gate_blocked,
                    decision.diagnostics.gate_block_reasons,
                    decision.diagnostics.cooldown_blocked,
                    decision.diagnostics.pesc_blocked,
                    decision.diagnostics.warnings,
                    notional,
                    leverage,
                    margin_used,
                    kernel_lev,
                    kernel_margin_req,
                    state.kernel_state.cash_usd
                );
                for (ksym, kpos) in &state.kernel_state.positions {
                    eprintln!(
                        "[cpu-kcash-debug] sym={} side={:?} qty={:.12} avg_entry={:.12} notional={:.12} margin={:.12}",
                        ksym,
                        kpos.side,
                        kpos.quantity,
                        kpos.avg_entry_price,
                        kpos.notional_usd,
                        kpos.margin_usd
                    );
                }
            }
        }
        return false;
    }

    apply_kernel_open_from_plan(
        state,
        &EntryCandidate {
            symbol: sym.to_string(),
            signal,
            confidence,
            adx: snap.adx,
            atr,
            entry_adx_threshold,
            snap: snap.clone(),
            ts,
            gate_eval: gate_eval.clone(),
        },
        size,
        margin_used,
        leverage,
        notional,
        cfg,
        &format!("{:?} entry (sub-bar)", confidence),
    )
}

fn apply_kernel_open_from_plan(
    state: &mut SimState,
    cand: &EntryCandidate,
    size: f64,
    margin_used: f64,
    leverage: f64,
    requested_notional_usd: f64,
    cfg: &StrategyConfig,
    reason: &str,
) -> bool {
    if state.positions.contains_key(&cand.symbol) {
        return false;
    }

    let desired_type = match cand.signal {
        Signal::Buy => PositionType::Long,
        Signal::Sell => PositionType::Short,
        Signal::Neutral => return false,
    };

    if size <= 0.0 || margin_used <= 0.0 || leverage <= 0.0 {
        return false;
    }

    let fill_price = accounting::quantize(match desired_type {
        PositionType::Long => cand.snap.close * (1.0 + cfg.trade.slippage_bps / 10_000.0),
        PositionType::Short => cand.snap.close * (1.0 - cfg.trade.slippage_bps / 10_000.0),
    });

    // Margin-based accounting: only deduct fee from balance (matching main
    // backtester).  Margin is tracked per-position, not deducted from cash.
    let fee_rate = maker_taker_fee_rate(&state.kernel_params, accounting::FeeRole::Taker);
    let fee_usd = accounting::quantize(requested_notional_usd * fee_rate);
    state.balance -= fee_usd;

    let pos = Position {
        symbol: cand.symbol.to_string(),
        pos_type: desired_type,
        entry_price: fill_price,
        size,
        confidence: cand.confidence,
        entry_atr: cand.atr,
        entry_adx_threshold: cand.entry_adx_threshold,
        trailing_sl: None,
        leverage,
        margin_used,
        adds_count: 0,
        tp1_taken: false,
        open_time_ms: cand.ts,
        last_add_time_ms: cand.ts,
        mae_usd: 0.0,
        mfe_usd: 0.0,
    };
    state.positions.insert(cand.symbol.to_string(), pos);
    note_entry_attempt(state, &cand.symbol, cand.ts);

    let action = match desired_type {
        PositionType::Long => "OPEN_LONG",
        PositionType::Short => "OPEN_SHORT",
    };
    state.trades.push(TradeRecord {
        timestamp_ms: cand.ts,
        symbol: cand.symbol.to_string(),
        action: action.to_string(),
        price: fill_price,
        size,
        notional: requested_notional_usd,
        reason: reason.to_string(),
        confidence: cand.confidence,
        pnl: 0.0,
        fee_usd,
        balance: state.balance,
        entry_atr: cand.atr,
        leverage,
        margin_used,
        ..Default::default()
    });

    true
}

fn apply_indicator_open_from_kernel(
    state: &mut SimState,
    cand: &EntryCandidate,
    size: f64,
    margin_used: f64,
    leverage: f64,
    requested_notional_usd: f64,
    cfg: &StrategyConfig,
    reason: &str,
) -> bool {
    apply_kernel_open_from_plan(
        state,
        cand,
        size,
        margin_used,
        leverage,
        requested_notional_usd,
        cfg,
        reason,
    )
}

fn apply_kernel_add_from_plan(
    state: &mut SimState,
    symbol: &str,
    cfg: &StrategyConfig,
    snap: &IndicatorSnapshot,
    confidence: Confidence,
    atr: f64,
    add_size: f64,
    add_notional: f64,
    add_margin: f64,
    ts: i64,
) -> bool {
    let add_signal = match state.positions.get(symbol).map(|pos| pos.pos_type) {
        Some(PositionType::Long) => Signal::Buy,
        Some(PositionType::Short) => Signal::Sell,
        None => return false,
    };

    if add_size <= 0.0 || add_margin <= 0.0 {
        return false;
    }

    // Margin-based accounting: only deduct fee from balance (matching main backtester).
    let add_fee_rate = maker_taker_fee_rate(&state.kernel_params, accounting::FeeRole::Taker);
    let add_fee_usd = accounting::quantize(add_notional * add_fee_rate);
    state.balance -= add_fee_usd;

    let fill_price = accounting::quantize(match add_signal {
        Signal::Buy => snap.close * (1.0 + cfg.trade.slippage_bps / 10_000.0),
        Signal::Sell => snap.close * (1.0 - cfg.trade.slippage_bps / 10_000.0),
        Signal::Neutral => return false,
    });

    if let Some(pos) = state.positions.get_mut(symbol) {
        pos.add_to_position(fill_price, add_size, add_margin, ts);

        let next_add = pos.adds_count;
        state.trades.push(TradeRecord {
            timestamp_ms: ts,
            symbol: symbol.to_string(),
            action: if pos.pos_type == PositionType::Long {
                "ADD_LONG".to_string()
            } else {
                "ADD_SHORT".to_string()
            },
            price: fill_price,
            size: add_size,
            notional: add_notional,
            reason: format!("Pyramid #{}", next_add),
            confidence,
            pnl: 0.0,
            fee_usd: add_fee_usd,
            balance: state.balance,
            entry_atr: atr,
            leverage: pos.leverage,
            margin_used: pos.margin_used,
            ..Default::default()
        });
    } else {
        return false;
    }

    note_entry_attempt(state, symbol, ts);
    true
}

/// Create a lightweight IndicatorSnapshot for sub-bar exit checks.
/// Copies all indicator values from the 1h snap, but overrides OHLC + time
/// with the sub-bar (e.g. 1m) values. This way exit conditions see the correct
/// price while indicator thresholds (ADX, RSI, etc.) stay at hourly resolution.
fn make_exit_snap(indicator_snap: &IndicatorSnapshot, exit_bar: &OhlcvBar) -> IndicatorSnapshot {
    let mut s = indicator_snap.clone();
    s.close = exit_bar.c;
    s.high = exit_bar.h;
    s.low = exit_bar.l;
    s.open = exit_bar.o;
    s.t = exit_bar.t;
    s
}

/// Binary-search for the funding rate at or just before `target_ts`.
fn lookup_funding_rate(rates: &[(i64, f64)], target_ts: i64) -> Option<f64> {
    match rates.binary_search_by_key(&target_ts, |(t, _)| *t) {
        Ok(i) => Some(rates[i].1),
        Err(i) => {
            // Use the rate from the most recent funding settlement before target_ts
            if i > 0 {
                Some(rates[i - 1].1)
            } else {
                None
            }
        }
    }
}

/// Create a minimal IndicatorSnapshot for force-close at end of backtest.
fn make_minimal_snap(price: f64, ts: i64) -> IndicatorSnapshot {
    IndicatorSnapshot {
        close: price,
        high: price,
        low: price,
        open: price,
        volume: 0.0,
        t: ts,
        ema_slow: price,
        ema_fast: price,
        ema_macro: price,
        adx: 0.0,
        adx_pos: 0.0,
        adx_neg: 0.0,
        adx_slope: 0.0,
        bb_upper: price,
        bb_lower: price,
        bb_width: 0.0,
        bb_width_avg: 0.0,
        bb_width_ratio: 1.0,
        atr: 0.0,
        atr_slope: 0.0,
        avg_atr: 0.0,
        rsi: 50.0,
        stoch_rsi_k: 0.5,
        stoch_rsi_d: 0.5,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 0.0,
        vol_trend: false,
        prev_close: price,
        prev_ema_fast: price,
        prev_ema_slow: price,
        bar_count: 0,
        funding_rate: 0.0,
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_atr_floor() {
        assert!((apply_atr_floor(0.5, 100.0, 0.01) - 1.0).abs() < 1e-9);
        assert!((apply_atr_floor(2.0, 100.0, 0.01) - 2.0).abs() < 1e-9);
        assert!((apply_atr_floor(0.5, 100.0, 0.0) - 0.5).abs() < 1e-9);
    }

    #[test]
    fn test_reverse_signal() {
        let mut cfg = StrategyConfig::default();
        cfg.trade.reverse_entry_signal = true;
        assert_eq!(apply_reverse(Signal::Buy, &cfg, 50.0), Signal::Sell);
        assert_eq!(apply_reverse(Signal::Sell, &cfg, 50.0), Signal::Buy);
        assert_eq!(apply_reverse(Signal::Neutral, &cfg, 50.0), Signal::Neutral);
    }

    #[test]
    fn test_regime_filter() {
        let mut cfg = StrategyConfig::default();
        cfg.market_regime.enable_regime_filter = true;
        cfg.market_regime.breadth_block_short_above = 80.0;
        cfg.market_regime.breadth_block_long_below = 20.0;
        assert_eq!(
            apply_regime_filter(Signal::Sell, &cfg, 85.0),
            Signal::Neutral
        );
        assert_eq!(
            apply_regime_filter(Signal::Buy, &cfg, 15.0),
            Signal::Neutral
        );
        assert_eq!(apply_regime_filter(Signal::Buy, &cfg, 50.0), Signal::Buy);
        assert_eq!(apply_regime_filter(Signal::Sell, &cfg, 50.0), Signal::Sell);
    }

    #[test]
    fn test_ema_slow_slope() {
        let history = vec![100.0, 101.0, 102.0, 103.0, 104.0];
        let slope = compute_ema_slow_slope(&history, 3, 104.0);
        // (104 - 102) / 104 ≈ 0.01923
        assert!((slope - 2.0 / 104.0).abs() < 1e-9);
    }

    #[test]
    fn test_ema_slow_slope_too_short() {
        let history = vec![100.0, 101.0];
        let slope = compute_ema_slow_slope(&history, 5, 101.0);
        assert!((slope - 0.0).abs() < 1e-9);
    }

    #[test]
    fn test_empty_candles() {
        let candles = FxHashMap::default();
        let cfg = StrategyConfig::default();
        let result = run_simulation(RunSimulationInput {
            candles: &candles,
            cfg: &cfg,
            initial_balance: 1000.0,
            lookback: 50,
            exit_candles: None,
            entry_candles: None,
            funding_rates: None,
            init_state: None,
            from_ts: None,
            to_ts: None,
        });
        assert_eq!(result.trades.len(), 0);
        assert!((result.final_balance - 1000.0).abs() < 1e-9);
    }

    #[test]
    fn test_indicator_bank_uses_threshold_ave_window() {
        let mut cfg = StrategyConfig::default();
        cfg.indicators.ave_avg_atr_window = 2;
        cfg.thresholds.entry.ave_avg_atr_window = 4;

        let mut bank = make_indicator_bank(&cfg, false);

        for i in 0..3 {
            bank.update(&OhlcvBar {
                t: i * 60_000,
                t_close: i * 60_000 + 59_999,
                o: 100.0 + i as f64,
                h: 101.0 + i as f64,
                l: 99.0 + i as f64,
                c: 100.5 + i as f64,
                v: 10_000.0,
                n: 100,
            });
        }
        assert!(!bank.avg_atr.full());

        bank.update(&OhlcvBar {
            t: 3 * 60_000,
            t_close: 3 * 60_000 + 59_999,
            o: 103.0,
            h: 104.0,
            l: 102.0,
            c: 103.5,
            v: 10_000.0,
            n: 100,
        });
        assert!(bank.avg_atr.full());
    }

    #[test]
    fn test_compute_entry_size_basic() {
        let cfg = StrategyConfig::default();
        let snap = make_minimal_snap(100.0, 0);
        let (size, margin, leverage) =
            compute_entry_size("ETH", 10000.0, 100.0, Confidence::High, 1.0, &snap, &cfg);
        // allocation_pct=0.03, dynamic sizing enabled, confidence_mult_high=1.0
        // adx=0 → adx_mult=min(0/40, 1.0).clamp(0.6, 1.0) = 0.6
        // vol_ratio = (1.0/100.0) / 0.01 = 1.0 → vol_scalar = 1.0
        // margin = 10000 * 0.03 * 1.0 * 0.6 * 1.0 = 180
        // leverage_high = 5.0
        // notional = 180 * 5 = 900
        // size = 900 / 100 = 9
        assert!(size > 0.0);
        assert!(margin > 0.0);
        assert!(leverage > 0.0);
    }

    #[test]
    fn test_market_breadth() {
        let state = SimState {
            balance: 1000.0,
            positions: FxHashMap::default(),
            last_entry_attempt_ms: FxHashMap::default(),
            last_exit_attempt_ms: FxHashMap::default(),
            indicators: FxHashMap::default(),
            ema_slow_history: FxHashMap::default(),
            bar_counts: FxHashMap::default(),
            last_close: FxHashMap::default(),
            trades: vec![],
            signals: vec![],
            decision_diagnostics: Vec::new(),
            kernel_state: make_kernel_state(1000.0, 0, &FxHashMap::default()),
            kernel_params: make_kernel_params(&StrategyConfig::default()),
            next_kernel_event_id: 1,
            equity_curve: vec![],
            gate_stats: GateStats::default(),
        };
        // No indicators → 50%
        assert!((compute_market_breadth(&state) - 50.0).abs() < 1e-9);
    }

    #[test]
    fn test_entry_cooldown_tracks_successful_entry_add_attempts() {
        let mut cfg = StrategyConfig::default();
        cfg.trade.entry_cooldown_s = 20;

        let mut state = SimState {
            balance: 1000.0,
            positions: FxHashMap::default(),
            last_entry_attempt_ms: FxHashMap::default(),
            last_exit_attempt_ms: FxHashMap::default(),
            indicators: FxHashMap::default(),
            ema_slow_history: FxHashMap::default(),
            bar_counts: FxHashMap::default(),
            last_close: FxHashMap::default(),
            trades: vec![],
            signals: vec![],
            decision_diagnostics: Vec::new(),
            kernel_state: make_kernel_state(1000.0, 0, &FxHashMap::default()),
            kernel_params: make_kernel_params(&StrategyConfig::default()),
            next_kernel_event_id: 1,
            equity_curve: vec![],
            gate_stats: GateStats::default(),
        };

        assert!(!is_entry_cooldown_active(&state, "ETH", 1_000, &cfg));
        note_entry_attempt(&mut state, "ETH", 1_000);
        assert!(is_entry_cooldown_active(&state, "ETH", 20_999, &cfg));
        assert!(!is_entry_cooldown_active(&state, "ETH", 21_000, &cfg));
    }

    #[test]
    fn test_exit_cooldown_tracks_successful_exit_attempts() {
        let mut cfg = StrategyConfig::default();
        cfg.trade.exit_cooldown_s = 15;

        let mut state = SimState {
            balance: 1000.0,
            positions: FxHashMap::default(),
            last_entry_attempt_ms: FxHashMap::default(),
            last_exit_attempt_ms: FxHashMap::default(),
            indicators: FxHashMap::default(),
            ema_slow_history: FxHashMap::default(),
            bar_counts: FxHashMap::default(),
            last_close: FxHashMap::default(),
            trades: vec![],
            signals: vec![],
            decision_diagnostics: Vec::new(),
            kernel_state: make_kernel_state(1000.0, 0, &FxHashMap::default()),
            kernel_params: make_kernel_params(&StrategyConfig::default()),
            next_kernel_event_id: 1,
            equity_curve: vec![],
            gate_stats: GateStats::default(),
        };

        assert!(!is_exit_cooldown_active(&state, "ETH", 5_000, &cfg));
        note_exit_attempt(&mut state, "ETH", 5_000);
        assert!(is_exit_cooldown_active(&state, "ETH", 19_999, &cfg));
        assert!(!is_exit_cooldown_active(&state, "ETH", 20_000, &cfg));
    }

    fn make_state_with_open_long(symbol: &str) -> SimState {
        let mut positions = FxHashMap::default();
        positions.insert(
            symbol.to_string(),
            Position {
                symbol: symbol.to_string(),
                pos_type: PositionType::Long,
                entry_price: 100.0,
                size: 1.0,
                confidence: Confidence::High,
                entry_atr: 1.0,
                entry_adx_threshold: 20.0,
                trailing_sl: None,
                leverage: 3.0,
                margin_used: 33.333_333,
                adds_count: 0,
                tp1_taken: false,
                open_time_ms: 0,
                last_add_time_ms: 0,
                mae_usd: 0.0,
                mfe_usd: 0.0,
            },
        );

        let kernel_state = make_kernel_state(1_000.0, 0, &positions);
        SimState {
            balance: 1_000.0,
            positions,
            indicators: FxHashMap::default(),
            ema_slow_history: FxHashMap::default(),
            bar_counts: FxHashMap::default(),
            last_close: FxHashMap::default(),
            trades: vec![],
            signals: vec![],
            decision_diagnostics: Vec::new(),
            kernel_state,
            kernel_params: make_kernel_params(&StrategyConfig::default()),
            next_kernel_event_id: 1,
            equity_curve: vec![],
            gate_stats: GateStats::default(),
            last_entry_attempt_ms: FxHashMap::default(),
            last_exit_attempt_ms: FxHashMap::default(),
        }
    }

    #[test]
    fn test_apply_exit_records_exit_cooldown_timestamp() {
        let mut state = make_state_with_open_long("ETH");
        let snap = make_minimal_snap(101.0, 10_000);
        let exit = ExitResult::exit("Take Profit", 101.0);
        let cfg = StrategyConfig::default();
        apply_exit(&mut state, "ETH", &exit, &snap, 10_000, &cfg);

        assert_eq!(state.last_exit_attempt_ms.get("ETH"), Some(&10_000));
        assert!(!state.positions.contains_key("ETH"));
    }

    #[test]
    fn test_apply_exit_partial_take_profit_marks_tp1_taken() {
        let symbol = "BTC";
        let mut state = make_state_with_open_long(symbol);
        let snap = make_minimal_snap(105.0, 1_700_000_000_000);
        let exit = ExitResult::partial_exit("Take Profit (Partial)", 105.0, 0.5);
        let cfg = StrategyConfig::default();

        apply_exit(&mut state, symbol, &exit, &snap, snap.t, &cfg);

        let pos = state
            .positions
            .get(symbol)
            .expect("position should remain after partial exit");
        assert!(pos.tp1_taken);
        assert!((pos.size - 0.5).abs() < 1e-12);
        assert_eq!(state.trades.len(), 1);
        assert_eq!(state.trades[0].action, "REDUCE_LONG");
    }

    #[test]
    fn test_apply_exit_partial_marks_tp1_taken_without_reason_match() {
        let symbol = "ETH";
        let mut state = make_state_with_open_long(symbol);
        let snap = make_minimal_snap(103.0, 1_700_000_000_001);
        let exit = ExitResult::partial_exit("Risk Trim", 103.0, 0.25);
        let cfg = StrategyConfig::default();

        apply_exit(&mut state, symbol, &exit, &snap, snap.t, &cfg);

        let pos = state
            .positions
            .get(symbol)
            .expect("position should remain after partial exit");
        assert!(pos.tp1_taken);
        assert!((pos.size - 0.75).abs() < 1e-12);
        assert_eq!(state.trades.len(), 1);
        assert_eq!(state.trades[0].action, "REDUCE_LONG");
    }

    #[test]
    fn test_apply_exit_pnl_matches_shared_accounting_close_formula() {
        let symbol = "ETH";
        let mut state = make_state_with_open_long(symbol);
        let close_price = 105.0;
        let snapped = make_minimal_snap(close_price, 1_700_000_000_002);
        let exit = ExitResult::exit("Take Profit", close_price);
        let fill_price = accounting::quantize(close_price * (1.0 - 0.5 / 10_000.0));
        let expected = accounting::apply_close_fill(
            true,
            100.0,
            fill_price,
            1.0,
            maker_taker_fee_rate(&state.kernel_params, accounting::FeeRole::Taker),
        );

        let cfg = StrategyConfig::default();
        apply_exit(&mut state, symbol, &exit, &snapped, snapped.t, &cfg);

        // Margin-based: balance changes by pnl - fee (not cash_delta which was notional-based).
        assert!((state.balance - (1_000.0 + expected.pnl - expected.fee_usd)).abs() < 1e-9);
        assert_eq!(state.trades.len(), 1);
        assert_eq!(state.trades[0].action, "CLOSE_LONG");
        assert!((state.trades[0].pnl - expected.pnl).abs() < 1e-9);
        assert!((state.trades[0].fee_usd - expected.fee_usd).abs() < 1e-9);
    }

    #[derive(Debug, serde::Deserialize)]
    struct KernelTraceFixture {
        final_cash: f64,
        traces: Vec<DecisionKernelTrace>,
    }

    #[test]
    fn test_kernel_entry_exit_sequence_matches_expected_fixture() {
        let fixture_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../testdata/kernel_path/entry_exit_kernel_path.json");
        let fixture_raw = std::fs::read_to_string(&fixture_path)
            .unwrap_or_else(|e| panic!("Failed to read fixture {:?}: {e}", fixture_path));
        let fixture: KernelTraceFixture = serde_json::from_str(&fixture_raw)
            .unwrap_or_else(|e| panic!("Invalid fixture JSON in {fixture_path:?}: {e}"));

        let mut state = SimState {
            balance: 10_000.0,
            positions: FxHashMap::default(),
            last_entry_attempt_ms: FxHashMap::default(),
            last_exit_attempt_ms: FxHashMap::default(),
            indicators: FxHashMap::default(),
            ema_slow_history: FxHashMap::default(),
            bar_counts: FxHashMap::default(),
            last_close: FxHashMap::default(),
            trades: vec![],
            signals: vec![],
            decision_diagnostics: Vec::new(),
            kernel_state: make_kernel_state(10_000.0, 0, &FxHashMap::default()),
            kernel_params: make_kernel_params(&StrategyConfig::default()),
            next_kernel_event_id: 1,
            equity_curve: vec![],
            gate_stats: GateStats::default(),
        };

        let cfg = StrategyConfig::default();
        let _ = step_decision(
            &mut state,
            StepDecisionInput {
                ts: 1_000,
                symbol: "BTC",
                signal: Signal::Buy,
                price: 100.0,
                requested_notional_usd: Some(1_000.0),
                source: "fixture-open",
                cfg: &cfg,
            },
        );
        let _ = step_decision(
            &mut state,
            StepDecisionInput {
                ts: 2_000,
                symbol: "BTC",
                signal: Signal::Sell,
                price: 110.0,
                requested_notional_usd: Some(1_000.0),
                source: "fixture-exit",
                cfg: &cfg,
            },
        );

        assert_eq!(state.decision_diagnostics, fixture.traces);
        assert!(
            (state.kernel_state.cash_usd - fixture.final_cash).abs() < 1e-12,
            "kernel final cash {} != fixture final cash {}",
            state.kernel_state.cash_usd,
            fixture.final_cash
        );
    }

    #[test]
    fn test_gate_evaluation_all_pass() {
        // Build a snapshot and config where all gates pass.
        let snap = IndicatorSnapshot {
            close: 100.0,
            high: 101.0,
            low: 99.0,
            open: 100.0,
            volume: 1000.0,
            t: 0,
            ema_slow: 98.0,
            ema_fast: 99.5,
            ema_macro: 95.0,
            adx: 30.0,
            adx_pos: 20.0,
            adx_neg: 10.0,
            adx_slope: 1.0,
            bb_upper: 102.0,
            bb_lower: 98.0,
            bb_width: 0.04,
            bb_width_avg: 0.03,
            bb_width_ratio: 1.33,
            atr: 1.5,
            atr_slope: 0.1,
            avg_atr: 1.4,
            rsi: 55.0,
            stoch_rsi_k: 0.5,
            stoch_rsi_d: 0.5,
            macd_hist: 0.5,
            prev_macd_hist: 0.3,
            prev2_macd_hist: 0.1,
            prev3_macd_hist: 0.0,
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 99.5,
            prev_ema_fast: 98.5,
            prev_ema_slow: 97.8,
            bar_count: 200,
            funding_rate: 0.0,
        };
        let cfg = StrategyConfig::default();
        let gr = gates::check_gates(&snap, &cfg, "ETH", Some(true), 0.001);
        assert!(gr.all_gates_pass, "precondition: all primary gates pass");

        let eval = build_gate_evaluation(&gr, &snap, Signal::Buy, Confidence::High, &cfg);

        assert!(eval.passed, "GateEvaluation should show passed");
        assert!(
            eval.checked_gates.iter().all(|c| c.passed),
            "Every individual gate check should be passed"
        );
        // Verify primary gates are present
        let names: Vec<&str> = eval
            .checked_gates
            .iter()
            .map(|c| c.gate_name.as_str())
            .collect();
        assert!(names.contains(&"adx_min"));
        assert!(names.contains(&"ranging"));
        assert!(names.contains(&"anomaly"));
        assert!(names.contains(&"extension"));
        assert!(names.contains(&"volume"));
        assert!(names.contains(&"adx_rising"));
        assert!(names.contains(&"btc_alignment"));
        assert!(names.contains(&"confidence"));
        // No reason strings when all pass
        assert!(
            eval.checked_gates.iter().all(|c| c.reason.is_none()),
            "No reason strings expected when all gates pass"
        );
    }

    #[test]
    fn test_gate_evaluation_blocked_by_adx() {
        let snap = IndicatorSnapshot {
            close: 100.0,
            high: 101.0,
            low: 99.0,
            open: 100.0,
            volume: 1000.0,
            t: 0,
            ema_slow: 98.0,
            ema_fast: 99.5,
            ema_macro: 95.0,
            adx: 15.0, // well below default min_adx (22.0)
            adx_pos: 10.0,
            adx_neg: 5.0,
            adx_slope: 1.0,
            bb_upper: 102.0,
            bb_lower: 98.0,
            bb_width: 0.04,
            bb_width_avg: 0.03,
            bb_width_ratio: 1.33,
            atr: 1.5,
            atr_slope: 0.1,
            avg_atr: 1.4,
            rsi: 55.0,
            stoch_rsi_k: 0.5,
            stoch_rsi_d: 0.5,
            macd_hist: 0.5,
            prev_macd_hist: 0.3,
            prev2_macd_hist: 0.1,
            prev3_macd_hist: 0.0,
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 99.5,
            prev_ema_fast: 98.5,
            prev_ema_slow: 97.8,
            bar_count: 200,
            funding_rate: 0.0,
        };
        let cfg = StrategyConfig::default();
        let gr = gates::check_gates(&snap, &cfg, "ETH", Some(true), 0.001);
        assert!(!gr.adx_above_min, "precondition: ADX below threshold");

        let eval = build_gate_evaluation(&gr, &snap, Signal::Buy, Confidence::High, &cfg);

        assert!(!eval.passed, "GateEvaluation should show NOT passed");
        let adx_check = eval
            .checked_gates
            .iter()
            .find(|c| c.gate_name == "adx_min")
            .expect("adx_min gate should be present");
        assert!(!adx_check.passed, "adx_min should be blocked");
        assert!(
            (adx_check.actual_value - 15.0).abs() < 1e-9,
            "actual should be snap.adx"
        );
        assert!(
            adx_check.threshold_value >= 22.0,
            "threshold should be effective_min_adx"
        );
        assert!(
            adx_check.reason.is_some(),
            "blocked gate should have reason"
        );
    }

    #[test]
    fn test_gate_evaluation_blocked_by_reef() {
        let snap = IndicatorSnapshot {
            close: 100.0,
            high: 101.0,
            low: 99.0,
            open: 100.0,
            volume: 1000.0,
            t: 0,
            ema_slow: 98.0,
            ema_fast: 99.5,
            ema_macro: 95.0,
            adx: 30.0,
            adx_pos: 20.0,
            adx_neg: 10.0,
            adx_slope: 1.0,
            bb_upper: 102.0,
            bb_lower: 98.0,
            bb_width: 0.04,
            bb_width_avg: 0.03,
            bb_width_ratio: 1.33,
            atr: 1.5,
            atr_slope: 0.1,
            avg_atr: 1.4,
            rsi: 75.0, // high RSI — will be blocked by reef for Buy signal
            stoch_rsi_k: 0.5,
            stoch_rsi_d: 0.5,
            macd_hist: 0.5,
            prev_macd_hist: 0.3,
            prev2_macd_hist: 0.1,
            prev3_macd_hist: 0.0,
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 99.5,
            prev_ema_fast: 98.5,
            prev_ema_slow: 97.8,
            bar_count: 200,
            funding_rate: 0.0,
        };
        let mut cfg = StrategyConfig::default();
        cfg.trade.enable_reef_filter = true;
        // Default reef_long_rsi_block_gt = 70.0 and adx(30) < reef_adx_threshold(45)
        // So RSI 75 > 70 → reef blocks long

        let gr = gates::check_gates(&snap, &cfg, "ETH", Some(true), 0.001);
        let eval = build_gate_evaluation(&gr, &snap, Signal::Buy, Confidence::High, &cfg);

        assert!(!eval.passed, "GateEvaluation should show NOT passed");
        let reef_check = eval
            .checked_gates
            .iter()
            .find(|c| c.gate_name == "reef")
            .expect("reef gate should be present");
        assert!(!reef_check.passed, "reef should be blocked");
        assert!(
            (reef_check.actual_value - 75.0).abs() < 1e-9,
            "actual should be snap.rsi"
        );
        assert!(
            (reef_check.threshold_value - 70.0).abs() < 1e-9,
            "threshold should be reef_long_rsi_block_gt"
        );
        assert!(
            reef_check.reason.is_some(),
            "blocked reef should have reason"
        );
    }

    #[test]
    fn test_gate_evaluation_serde_roundtrip() {
        let eval = GateEvaluation {
            passed: true,
            checked_gates: vec![
                GateCheck {
                    gate_name: "adx_min".into(),
                    passed: true,
                    actual_value: 30.0,
                    threshold_value: 22.0,
                    reason: None,
                },
                GateCheck {
                    gate_name: "ranging".into(),
                    passed: false,
                    actual_value: 0.7,
                    threshold_value: 0.0,
                    reason: Some("Market in ranging regime (vote system)".into()),
                },
            ],
        };
        let json = serde_json::to_string(&eval).unwrap();
        let deser: GateEvaluation = serde_json::from_str(&json).unwrap();
        assert_eq!(eval, deser);
    }

    #[test]
    fn test_indicator_snapshot_in_trace() {
        // Verify IndicatorSnapshot serializes/deserializes correctly in a trace context.
        let snap = make_minimal_snap(42000.0, 1_700_000_000_000);
        let json = serde_json::to_string(&snap).unwrap();
        let deser: IndicatorSnapshot = serde_json::from_str(&json).unwrap();
        assert_eq!(snap, deser, "IndicatorSnapshot serde roundtrip");

        // Verify indicator values match what we put in.
        assert!((deser.close - 42000.0).abs() < 1e-9);
        assert!((deser.adx - 0.0).abs() < 1e-9);
        assert!((deser.rsi - 50.0).abs() < 1e-9);
    }

    #[test]
    fn test_trace_with_indicator_snapshot() {
        // Build a trace via step_decision and then attach a snapshot,
        // verifying the snapshot values are preserved in the trace struct.
        let mut state = SimState {
            balance: 10_000.0,
            positions: FxHashMap::default(),
            last_entry_attempt_ms: FxHashMap::default(),
            last_exit_attempt_ms: FxHashMap::default(),
            indicators: FxHashMap::default(),
            ema_slow_history: FxHashMap::default(),
            bar_counts: FxHashMap::default(),
            last_close: FxHashMap::default(),
            trades: vec![],
            signals: vec![],
            decision_diagnostics: Vec::new(),
            kernel_state: make_kernel_state(10_000.0, 0, &FxHashMap::default()),
            kernel_params: make_kernel_params(&StrategyConfig::default()),
            next_kernel_event_id: 1,
            equity_curve: vec![],
            gate_stats: GateStats::default(),
        };
        let cfg = StrategyConfig::default();

        let _ = step_decision(
            &mut state,
            StepDecisionInput {
                ts: 1_000,
                symbol: "ETH",
                signal: Signal::Buy,
                price: 3500.0,
                requested_notional_usd: Some(500.0),
                source: "fixture-open",
                cfg: &cfg,
            },
        );

        // Simulate attaching an indicator snapshot (as the engine does after step_decision)
        let snap = IndicatorSnapshot {
            close: 3500.0,
            high: 3520.0,
            low: 3480.0,
            open: 3490.0,
            volume: 5000.0,
            t: 1_000,
            ema_slow: 3450.0,
            ema_fast: 3475.0,
            ema_macro: 3400.0,
            adx: 28.5,
            adx_pos: 22.0,
            adx_neg: 12.0,
            adx_slope: 0.8,
            bb_upper: 3550.0,
            bb_lower: 3430.0,
            bb_width: 0.034,
            bb_width_avg: 0.030,
            bb_width_ratio: 1.13,
            atr: 45.0,
            atr_slope: 2.0,
            avg_atr: 42.0,
            rsi: 58.0,
            stoch_rsi_k: 0.65,
            stoch_rsi_d: 0.60,
            macd_hist: 3.2,
            prev_macd_hist: 2.1,
            prev2_macd_hist: 1.0,
            prev3_macd_hist: 0.5,
            vol_sma: 4500.0,
            vol_trend: true,
            prev_close: 3490.0,
            prev_ema_fast: 3470.0,
            prev_ema_slow: 3445.0,
            bar_count: 150,
            funding_rate: 0.0001,
        };

        if let Some(last) = state.decision_diagnostics.last_mut() {
            last.indicator_snapshot = Some(snap.clone());
        }

        // Verify the trace has the snapshot with correct values
        let trace = state.decision_diagnostics.last().unwrap();
        assert!(trace.indicator_snapshot.is_some());
        let trace_snap = trace.indicator_snapshot.as_ref().unwrap();
        assert!((trace_snap.adx - 28.5).abs() < 1e-9, "ADX should match");
        assert!((trace_snap.rsi - 58.0).abs() < 1e-9, "RSI should match");
        assert!((trace_snap.atr - 45.0).abs() < 1e-9, "ATR should match");
        assert!(
            (trace_snap.close - 3500.0).abs() < 1e-9,
            "close should match"
        );
        assert!(
            (trace_snap.ema_slow - 3450.0).abs() < 1e-9,
            "EMA slow should match"
        );
        assert!(
            (trace_snap.ema_fast - 3475.0).abs() < 1e-9,
            "EMA fast should match"
        );
        assert!(
            (trace_snap.bb_width_ratio - 1.13).abs() < 1e-9,
            "BB width ratio should match"
        );

        // Verify full serde roundtrip of trace with snapshot
        let json = serde_json::to_string(trace).unwrap();
        let deser: DecisionKernelTrace = serde_json::from_str(&json).unwrap();
        assert_eq!(
            *trace, deser,
            "Trace with indicator_snapshot serde roundtrip"
        );
    }

    #[test]
    fn test_trace_without_snapshot_backward_compat() {
        // Verify that traces without indicator_snapshot deserialize correctly
        // (backward compatibility with old fixture format).
        let json = r#"{
            "event_id": 1,
            "source": "test",
            "timestamp_ms": 1000,
            "symbol": "BTC",
            "signal": "BUY",
            "requested_notional_usd": 100.0,
            "requested_price": 50000.0,
            "schema_version": 1,
            "step": 1,
            "state_step": 1,
            "state_cash_usd": 9900.0,
            "state_positions": 1,
            "intent_count": 0,
            "fill_count": 0,
            "warnings": [],
            "errors": [],
            "intents": [],
            "fills": [],
            "applied_to_kernel_state": true,
            "active_params": {}
        }"#;
        let trace: DecisionKernelTrace = serde_json::from_str(json).unwrap();
        assert!(
            trace.indicator_snapshot.is_none(),
            "Missing indicator_snapshot should default to None"
        );
        assert!(
            trace.gate_result.is_none(),
            "Missing gate_result should default to None"
        );
    }

    // -----------------------------------------------------------------------
    // AQC-710: ExitContext tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_exit_context_populated_on_full_close() {
        let symbol = "BTC";
        let mut state = make_state_with_open_long(symbol);
        // Give the position a trailing stop to verify it shows up in ExitContext
        state.positions.get_mut(symbol).unwrap().trailing_sl = Some(99.0);
        state.positions.get_mut(symbol).unwrap().mfe_usd = 5.0;
        state.positions.get_mut(symbol).unwrap().mae_usd = -2.0;
        let snap = make_minimal_snap(105.0, 1_700_000_000_000);
        let exit = ExitResult::exit("Take Profit", 105.0);
        let mut cfg = StrategyConfig::default();
        cfg.trade.sl_atr_mult = 1.5;
        cfg.trade.tp_atr_mult = 2.0;
        cfg.engine.interval = "15m".to_string();

        apply_exit(&mut state, symbol, &exit, &snap, snap.t, &cfg);

        assert_eq!(state.trades.len(), 1);
        let ctx = state.trades[0]
            .exit_context
            .as_ref()
            .expect("exit_context should be populated for close");
        assert!(ctx.trailing_active);
        assert!((ctx.trailing_high_water_mark - 99.0).abs() < 1e-9);
        assert!((ctx.sl_atr_mult_applied - 1.5).abs() < 1e-9);
        assert!((ctx.tp_atr_mult_applied - 2.0).abs() < 1e-9);
        assert!(ctx.indicator_at_exit.is_some());
        assert!((ctx.max_unrealized_pnl - 5.0).abs() < 1e-9);
        assert!((ctx.min_unrealized_pnl - (-2.0)).abs() < 1e-9);
        // Default config has smart_exit_adx_exhaustion_lt = 18.0
        assert_eq!(ctx.smart_exit_threshold, Some(18.0));
    }

    #[test]
    fn test_exit_context_with_smart_exit_threshold() {
        let symbol = "ETH";
        let mut state = make_state_with_open_long(symbol);
        let snap = make_minimal_snap(103.0, 1_700_000_000_000);
        let exit = ExitResult::exit("ADX Exhaustion", 103.0);
        let mut cfg = StrategyConfig::default();
        cfg.trade.smart_exit_adx_exhaustion_lt = 18.0;
        cfg.engine.interval = "1h".to_string();

        apply_exit(&mut state, symbol, &exit, &snap, snap.t, &cfg);

        let ctx = state.trades[0]
            .exit_context
            .as_ref()
            .expect("exit_context should be populated");
        assert_eq!(ctx.smart_exit_threshold, Some(18.0));
        assert!(!ctx.trailing_active);
        assert!((ctx.trailing_high_water_mark).abs() < 1e-9);
    }

    #[test]
    fn test_exit_context_bars_held_calculation() {
        let symbol = "BTC";
        let mut state = make_state_with_open_long(symbol);
        // Set position open_time to 10 bars ago (15m each = 9_000_000 ms)
        state.positions.get_mut(symbol).unwrap().open_time_ms = 1_700_000_000_000 - 9_000_000;
        let snap = make_minimal_snap(101.0, 1_700_000_000_000);
        let exit = ExitResult::exit("Stop Loss", 101.0);
        let mut cfg = StrategyConfig::default();
        cfg.engine.interval = "15m".to_string();

        apply_exit(&mut state, symbol, &exit, &snap, snap.t, &cfg);

        let ctx = state.trades[0]
            .exit_context
            .as_ref()
            .expect("exit_context should be populated");
        assert_eq!(ctx.bars_held, 10);
    }

    #[test]
    fn test_exit_context_serde_roundtrip() {
        use crate::position::ExitContext;
        let ctx = ExitContext {
            trailing_active: true,
            trailing_high_water_mark: 58_500.0,
            sl_atr_mult_applied: 1.5,
            tp_atr_mult_applied: 2.5,
            smart_exit_threshold: Some(18.0),
            indicator_at_exit: None,
            bars_held: 42,
            max_unrealized_pnl: 3_200.0,
            min_unrealized_pnl: -800.0,
        };
        let json = serde_json::to_string(&ctx).unwrap();
        let parsed: ExitContext = serde_json::from_str(&json).unwrap();
        assert_eq!(ctx, parsed);

        // Verify backward compat: missing optional fields deserialize to defaults
        let minimal = r#"{
            "trailing_active": false,
            "trailing_high_water_mark": 0.0,
            "sl_atr_mult_applied": 1.0,
            "tp_atr_mult_applied": 2.0,
            "bars_held": 5,
            "max_unrealized_pnl": 100.0,
            "min_unrealized_pnl": -50.0
        }"#;
        let parsed: ExitContext = serde_json::from_str(minimal).unwrap();
        assert!(parsed.smart_exit_threshold.is_none());
        assert!(parsed.indicator_at_exit.is_none());
    }
}
