use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use tokio::sync::broadcast;

const CHANNEL_CAPACITY: usize = 64;

/// Central broadcast hub.  Each topic has a `broadcast::Sender`.
///
/// Topics are created lazily on first subscribe or publish.
/// Clone-able via internal Arc.
#[derive(Clone)]
pub struct BroadcastHub {
    channels: Arc<RwLock<HashMap<String, broadcast::Sender<String>>>>,
}

impl BroadcastHub {
    pub fn new() -> Self {
        Self {
            channels: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Subscribe to a topic.  Creates the channel if it doesn't exist.
    pub fn subscribe(&self, topic: &str) -> broadcast::Receiver<String> {
        {
            let channels = self.channels.read().unwrap();
            if let Some(tx) = channels.get(topic) {
                return tx.subscribe();
            }
        }

        let mut channels = self.channels.write().unwrap();
        let entry = channels
            .entry(topic.to_string())
            .or_insert_with(|| broadcast::channel(CHANNEL_CAPACITY).0);
        entry.subscribe()
    }

    /// Publish a message to a topic and return receiver count.
    /// Returns 0 when no client is subscribed to that topic.
    pub fn publish(&self, topic: &str, message: String) -> usize {
        let channels = self.channels.read().unwrap();
        if let Some(tx) = channels.get(topic) {
            tx.send(message).unwrap_or(0)
        } else {
            0
        }
    }
}

impl Default for BroadcastHub {
    fn default() -> Self {
        Self::new()
    }
}
