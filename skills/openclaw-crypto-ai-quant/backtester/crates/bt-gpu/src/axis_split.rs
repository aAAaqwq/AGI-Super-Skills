//! Classify sweep axes into indicator-affecting vs trade-only.
//!
//! Indicator axes change EMA/ADX/BB/ATR/RSI window parameters, requiring
//! a full indicator recomputation. Trade axes only affect sizing, SL/TP,
//! trailing, etc. and can be swept on GPU without recomputing indicators.

use std::collections::{HashMap, HashSet};

use bt_core::sweep::SweepAxis;

/// Indicator config paths that require indicator recomputation.
pub const INDICATOR_PATHS: &[&str] = &[
    "indicators.ema_slow_window",
    "indicators.ema_fast_window",
    "indicators.ema_macro_window",
    "indicators.adx_window",
    "indicators.bb_window",
    "indicators.bb_width_avg_window",
    "indicators.atr_window",
    "indicators.rsi_window",
    "indicators.vol_sma_window",
    "indicators.vol_trend_window",
    "indicators.stoch_rsi_window",
    "indicators.stoch_rsi_smooth1",
    "indicators.stoch_rsi_smooth2",
    // Keep Stoch-RSI gate family in one split so gate pruning is correct on GPU:
    // parent toggle + threshold children + indicator windows must move together.
    "filters.use_stoch_rsi_filter",
    "thresholds.stoch_rsi.block_long_if_k_gt",
    "thresholds.stoch_rsi.block_short_if_k_lt",
    "indicators.ave_avg_atr_window",
    // Threshold paths that affect indicator-derived values computed at gate time
    "thresholds.entry.ave_avg_atr_window",
    "thresholds.entry.slow_drift_slope_window",
];

/// Split sweep axes into (indicator_axes, trade_axes).
pub fn split_axes(axes: &[SweepAxis]) -> (Vec<SweepAxis>, Vec<SweepAxis>) {
    // Start from explicit indicator seeds.
    let mut indicator_paths: HashSet<&str> = axes
        .iter()
        .filter(|a| is_indicator_axis(&a.path))
        .map(|a| a.path.as_str())
        .collect();

    // Build undirected gate graph path <-> gate_parent for closure expansion.
    let axis_present: HashSet<&str> = axes.iter().map(|a| a.path.as_str()).collect();
    let mut graph: HashMap<&str, Vec<&str>> = HashMap::new();
    for axis in axes {
        if let Some(g) = &axis.gate {
            if axis_present.contains(g.path.as_str()) {
                graph
                    .entry(axis.path.as_str())
                    .or_default()
                    .push(g.path.as_str());
                graph
                    .entry(g.path.as_str())
                    .or_default()
                    .push(axis.path.as_str());
            }
        }
    }

    // Expand to full connected components so gate families stay in one split.
    // This prevents cross-split parent/child gates from leaking no-op axes.
    let mut stack: Vec<&str> = indicator_paths.iter().copied().collect();
    while let Some(node) = stack.pop() {
        if let Some(neighbours) = graph.get(node) {
            for &next in neighbours {
                if indicator_paths.insert(next) {
                    stack.push(next);
                }
            }
        }
    }

    let mut indicator = Vec::new();
    let mut trade = Vec::new();

    for axis in axes {
        if indicator_paths.contains(axis.path.as_str()) {
            indicator.push(axis.clone());
        } else {
            trade.push(axis.clone());
        }
    }

    (indicator, trade)
}

fn is_indicator_axis(path: &str) -> bool {
    INDICATOR_PATHS.contains(&path)
}

/// Generate all combinations (cartesian product) from axes.
pub fn generate_combinations(axes: &[SweepAxis]) -> Vec<Vec<(String, f64)>> {
    if axes.is_empty() {
        return vec![Vec::new()];
    }

    // Mirror bt-core gate semantics:
    // - ungated axes first
    // - gated axis expands only when gate parent equals `eq`
    // - otherwise freeze to first value (no-op branch pruning)
    let mut sorted: Vec<&SweepAxis> = axes.iter().collect();
    sorted.sort_by_key(|a| u8::from(a.gate.is_some()));

    let mut combos: Vec<Vec<(String, f64)>> = vec![Vec::new()];
    for axis in &sorted {
        let mut next = Vec::with_capacity(combos.len().saturating_mul(axis.values.len().max(1)));
        for combo in &combos {
            let expand = if let Some(gate) = &axis.gate {
                combo
                    .iter()
                    .find(|(p, _)| *p == gate.path)
                    .map_or(true, |(_, v)| (*v - gate.eq).abs() < 1e-9)
            } else {
                true
            };

            let vals = if expand {
                &axis.values[..]
            } else {
                &axis.values[..1]
            };

            for value in vals {
                let mut expanded = combo.clone();
                expanded.push((axis.path.clone(), *value));
                next.push(expanded);
            }
        }
        combos = next;
    }
    combos
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_split_axes() {
        let axes = vec![
            SweepAxis {
                path: "trade.sl_atr_mult".to_string(),
                values: vec![1.5, 2.0],
                gate: None,
            },
            SweepAxis {
                path: "indicators.ema_slow_window".to_string(),
                values: vec![30.0, 50.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.tp_atr_mult".to_string(),
                values: vec![3.0, 5.0],
                gate: None,
            },
        ];
        let (ind, trade) = split_axes(&axes);
        assert_eq!(ind.len(), 1);
        assert_eq!(ind[0].path, "indicators.ema_slow_window");
        assert_eq!(trade.len(), 2);
    }

    #[test]
    fn test_generate_combinations() {
        let axes = vec![
            SweepAxis {
                path: "a".to_string(),
                values: vec![1.0, 2.0],
                gate: None,
            },
            SweepAxis {
                path: "b".to_string(),
                values: vec![10.0, 20.0],
                gate: None,
            },
        ];
        let combos = generate_combinations(&axes);
        assert_eq!(combos.len(), 4);
    }

    #[test]
    fn test_empty_axes() {
        let combos = generate_combinations(&[]);
        assert_eq!(combos.len(), 1);
        assert_eq!(combos[0].len(), 0);
    }

    #[test]
    fn test_generate_combinations_with_gate_freeze() {
        let axes = vec![
            SweepAxis {
                path: "trade.enable_x".to_string(),
                values: vec![0.0, 1.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.x_param".to_string(),
                values: vec![10.0, 20.0, 30.0],
                gate: Some(bt_core::sweep::AxisGate {
                    path: "trade.enable_x".to_string(),
                    eq: 1.0,
                }),
            },
        ];

        let combos = generate_combinations(&axes);
        // enable_x=0 -> frozen x_param=10 (1 combo)
        // enable_x=1 -> x_param expands to 3 values (3 combos)
        assert_eq!(combos.len(), 4);

        let mut seen = Vec::new();
        for combo in combos {
            let en = combo
                .iter()
                .find(|(k, _)| k == "trade.enable_x")
                .map(|(_, v)| *v)
                .unwrap_or(-1.0);
            let x = combo
                .iter()
                .find(|(k, _)| k == "trade.x_param")
                .map(|(_, v)| *v)
                .unwrap_or(-1.0);
            seen.push((en, x));
        }
        seen.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        assert_eq!(seen, vec![(0.0, 10.0), (1.0, 10.0), (1.0, 20.0), (1.0, 30.0)]);
    }

    #[test]
    fn test_split_axes_stoch_gate_family_in_indicator_bucket() {
        let axes = vec![
            SweepAxis {
                path: "filters.use_stoch_rsi_filter".to_string(),
                values: vec![0.0, 1.0],
                gate: None,
            },
            SweepAxis {
                path: "indicators.stoch_rsi_window".to_string(),
                values: vec![10.0, 14.0],
                gate: Some(bt_core::sweep::AxisGate {
                    path: "filters.use_stoch_rsi_filter".to_string(),
                    eq: 1.0,
                }),
            },
            SweepAxis {
                path: "thresholds.stoch_rsi.block_long_if_k_gt".to_string(),
                values: vec![0.6, 0.75],
                gate: Some(bt_core::sweep::AxisGate {
                    path: "filters.use_stoch_rsi_filter".to_string(),
                    eq: 1.0,
                }),
            },
        ];

        let (ind, trade) = split_axes(&axes);
        assert_eq!(trade.len(), 0);
        assert_eq!(ind.len(), 3);
    }

    #[test]
    fn test_generate_combinations_many_axes_no_recursion() {
        let axes: Vec<SweepAxis> = (0..256)
            .map(|i| SweepAxis {
                path: format!("axis{i}"),
                values: vec![i as f64],
                gate: None,
            })
            .collect();
        let combos = generate_combinations(&axes);
        assert_eq!(combos.len(), 1);
        assert_eq!(combos[0].len(), 256);
        assert_eq!(combos[0][0], ("axis0".to_string(), 0.0));
        assert_eq!(combos[0][255], ("axis255".to_string(), 255.0));
    }
}
