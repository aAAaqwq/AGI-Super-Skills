use serde::Deserialize;
use std::fmt;

pub mod confidence;
pub mod entry;
pub mod gates;
mod views;

pub use views::{
    AnomalyThresholdsView, EntryThresholdsView, FiltersView, IndicatorSnapshotLike,
    RangingThresholdsView, SignalConfigLike, SignalConfigView, SnapshotView,
    StochRsiThresholdsView, ThresholdsView, TpAndMomentumThresholdsView, TradeView,
};

/// Signal direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Signal {
    Buy,
    Sell,
    Neutral,
}

/// Confidence tier for entry and add filters.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Default)]
pub enum Confidence {
    #[default]
    Low = 0,
    Medium = 1,
    High = 2,
}

impl Confidence {
    pub fn from_str(s: &str) -> Result<Self, String> {
        match s.trim().to_ascii_lowercase().as_str() {
            "low" => Ok(Confidence::Low),
            "medium" => Ok(Confidence::Medium),
            "high" => Ok(Confidence::High),
            _ => Err(format!(
                "invalid confidence {s:?}; expected low|medium|high"
            )),
        }
    }
}

impl fmt::Display for Confidence {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Confidence::Low => write!(f, "low"),
            Confidence::Medium => write!(f, "medium"),
            Confidence::High => write!(f, "high"),
        }
    }
}

impl<'de> Deserialize<'de> for Confidence {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        Confidence::from_str(&s).map_err(serde::de::Error::custom)
    }
}

/// MACD histogram gating mode for trend entries.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MacdMode {
    /// Require MACD_hist > prev_MACD_hist (acceleration).
    Accel,
    /// Require MACD_hist > 0 for BUY, < 0 for SELL.
    Sign,
    /// Ignore MACD_hist gate.
    None,
}

impl MacdMode {
    pub fn from_str(s: &str) -> Result<Self, String> {
        match s.trim().to_ascii_lowercase().as_str() {
            "accel" => Ok(MacdMode::Accel),
            "sign" => Ok(MacdMode::Sign),
            "none" => Ok(MacdMode::None),
            _ => Err(format!("invalid macd mode {s:?}; expected accel|sign|none")),
        }
    }
}

impl fmt::Display for MacdMode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            MacdMode::Accel => write!(f, "accel"),
            MacdMode::Sign => write!(f, "sign"),
            MacdMode::None => write!(f, "none"),
        }
    }
}

impl<'de> Deserialize<'de> for MacdMode {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        MacdMode::from_str(&s).map_err(serde::de::Error::custom)
    }
}

#[cfg(test)]
mod tests {
    use super::{Confidence, MacdMode};

    #[test]
    fn confidence_from_str_rejects_unknown_values() {
        assert_eq!(Confidence::from_str("low").unwrap(), Confidence::Low);
        assert_eq!(Confidence::from_str("medium").unwrap(), Confidence::Medium);
        assert_eq!(Confidence::from_str("high").unwrap(), Confidence::High);
        assert!(Confidence::from_str("typo").is_err());
    }

    #[test]
    fn macd_mode_from_str_rejects_unknown_values() {
        assert_eq!(MacdMode::from_str("accel").unwrap(), MacdMode::Accel);
        assert_eq!(MacdMode::from_str("sign").unwrap(), MacdMode::Sign);
        assert_eq!(MacdMode::from_str("none").unwrap(), MacdMode::None);
        assert!(MacdMode::from_str("typo").is_err());
    }

    #[test]
    fn confidence_deserialize_fails_on_unknown_value() {
        let parsed: Result<Confidence, _> = serde_yaml::from_str("typo");
        assert!(parsed.is_err());
    }

    #[test]
    fn macd_mode_deserialize_fails_on_unknown_value() {
        let parsed: Result<MacdMode, _> = serde_yaml::from_str("typo");
        assert!(parsed.is_err());
    }
}
