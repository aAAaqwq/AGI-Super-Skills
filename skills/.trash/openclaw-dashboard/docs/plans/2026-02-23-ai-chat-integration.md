# AI Chat Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
>
> **Status (2026-02-23):** Implemented in dashboard `v2026.2.23` / server `v2.4.0`.
> This document is retained as a historical implementation plan; current behavior is authoritative in `server.py`, `index.html`, and tests.
> Historical note: earlier plan text mentions `x-openclaw-agent-id`; current implementation uses bearer auth only.

**Goal:** Embed an AI assistant panel in the OpenClaw Dashboard that answers natural-language questions about live metrics and configuration using the running OpenClaw gateway as its LLM backend.

**Architecture:** A floating `💬` button in the dashboard opens a chat panel. The frontend sends POST requests to a new `/api/chat` endpoint in `server.py`, which reads `data.json` to build a system prompt, then calls the OpenClaw gateway's OpenAI-compatible completions API at `localhost:18789`. Authentication uses the token from `~/.openclaw/.env`. All code uses Python stdlib only — no new dependencies.

**Tech Stack:** Python 3.6+ stdlib (`urllib.request`, `json`, `http.server`), vanilla JS (no framework), OpenClaw gateway OpenAI-compatible API (`POST /v1/chat/completions`), Bearer token auth.

---

## Deep Analysis: Why This Architecture

### Why not call the LLM directly?

The OpenClaw gateway at `localhost:18789` already has:
- Your model routing config (primary → fallbacks)
- API keys for all providers (kimi, deepseek, anthropic, minimax)
- Cost tracking that shows up in the dashboard's own metrics
- The `x-openclaw-agent-id` header routes through your `main` agent's config

Calling the gateway means the chat cost appears in the dashboard's cost tracking automatically.

### Why the gateway's OpenAI endpoint is currently returning 405

In `src/openclaw/src/gateway/server-runtime-config.ts:75-78`:
```typescript
const openAiChatCompletionsEnabled =
    params.openAiChatCompletionsEnabled ??
    params.cfg.gateway?.http?.endpoints?.chatCompletions?.enabled ??
    false;  // ← defaults to false
```
The endpoint exists but is **disabled by default**. Task 1 enables it.

### Why read ~/.openclaw/.env instead of an env var?

The gateway token is stored as `OPENCLAW_GATEWAY_TOKEN=<value>` in `~/.openclaw/.env`. This file is already sourced by OpenClaw at startup. The dashboard server reads it at startup using a tiny stdlib dotenv reader (15 lines) — no package needed.

### Data flow after change

```
User types question in chat panel
    ↓  POST /api/chat  {"question":"...", "history":[...]}
server.py handle_chat()
    ├─ loads data.json → build_dashboard_prompt(data) → 300-char context
    ├─ calls call_gateway(system, history, question, port=18789, token, model, agent_id)
    │   └─ urllib.request.urlopen(POST localhost:18789/v1/chat/completions)
    │       headers: Authorization: Bearer <token>, x-openclaw-agent-id: main
    └─ returns {"answer": "..."}
        ↓
JS appendMessage("assistant", answer)
```

### Why context must be compressed

`data.json` is large (35+ keys, arrays of sessions/crons/runs). The system prompt passes only the **key metrics** the AI needs:
- Gateway: status, uptime, memory
- Costs: today, all-time, projected, model breakdown
- Sessions: count + top 3 (model, type, context%)
- Crons: count + any failed jobs
- Alerts: verbatim from data.json
- Config: primary model, fallbacks, active channels

This keeps the system prompt under 800 tokens and the LLM focused.

### test_server.py pattern (important — follow this)

Existing server tests spin up a **real subprocess** of `server.py` on a random port using `ServerTestBase`. They use `http.client` to make real HTTP requests. All new chat endpoint tests must follow this exact pattern.

The `_post()` helper doesn't exist yet in `ServerTestBase` — you'll add it.

### index.html pattern (important — follow this)

- All user-visible strings go through `esc()` before being placed in `innerHTML`
- CSS custom properties are used for all colors (e.g. `var(--accent)`)
- New global JS variables are declared alongside existing ones in the `let D={},prevD=null,...` line
- New HTML elements are added before `</body>`
- New CSS is added inside the existing `<style>` block before `</style>`

---

## Files Modified

| File | Change |
|------|--------|
| `~/.openclaw/openclaw.json` | Add `gateway.http.endpoints.chatCompletions.enabled: true` |
| `config.json` | Add `"ai"` section |
| `server.py` | Add `read_dotenv()`, `build_dashboard_prompt()`, `call_gateway()`, `do_POST()`, `handle_chat()` |
| `index.html` | Add chat panel CSS, HTML markup, JavaScript |
| `tests/test_chat.py` | New test file — 8 acceptance tests for `/api/chat` |
| `tests/test_frontend.py` | Append 3 new tests for chat panel HTML/JS |

---

## Task 1: Enable Gateway OpenAI HTTP Endpoint

**Files:**
- Modify: `~/.openclaw/openclaw.json`

**Context:** The OpenClaw gateway's OpenAI-compatible API is disabled by default. This task enables it by adding a config key. This is a **prerequisite** — nothing else works without it.

**Step 1: Back up openclaw.json**

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak
```

**Step 2: Check current gateway config section**

```bash
python3 -c "
import json
with open('/Users/mudrii/.openclaw/openclaw.json') as f:
    d = json.load(f)
print(json.dumps(d.get('gateway', {}), indent=2))
"
```

Expected output: shows gateway object with `port`, `mode`, `bind`, `auth` keys but **no** `http` key.

**Step 3: Add the http.endpoints.chatCompletions block**

Use Python to do a safe, non-destructive JSON update (preserves all existing keys):

```python
import json

path = '/Users/mudrii/.openclaw/openclaw.json'
with open(path) as f:
    cfg = json.load(f)

gw = cfg.setdefault('gateway', {})
gw.setdefault('http', {}).setdefault('endpoints', {})['chatCompletions'] = {'enabled': True}

with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')

print("Done. gateway.http.endpoints.chatCompletions.enabled =",
      cfg['gateway']['http']['endpoints']['chatCompletions']['enabled'])
```

Run:
```bash
python3 -c "
import json
path = '/Users/mudrii/.openclaw/openclaw.json'
with open(path) as f:
    cfg = json.load(f)
gw = cfg.setdefault('gateway', {})
gw.setdefault('http', {}).setdefault('endpoints', {})['chatCompletions'] = {'enabled': True}
with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')
print('Enabled:', cfg['gateway']['http']['endpoints']['chatCompletions']['enabled'])
"
```

Expected: `Enabled: True`

**Step 4: Restart the OpenClaw gateway**

Restart via the OpenClaw Mac menubar app (click the app icon → Restart Gateway), or:

```bash
# Kill and relaunch (macOS menubar app approach)
pkill -f "openclaw-gateway" 2>/dev/null; sleep 2
# Then reopen the OpenClaw Mac app to start the gateway
open -a OpenClaw
sleep 3
```

**Step 5: Verify the endpoint is now enabled**

```bash
TOKEN=$(grep OPENCLAW_GATEWAY_TOKEN ~/.openclaw/.env | cut -d= -f2)
curl -s -X POST http://localhost:18789/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-openclaw-agent-id: main" \
  -d '{"model":"kimi-coding/k2p5","messages":[{"role":"user","content":"Reply with the single word OK"}],"max_tokens":5}' \
  | python3 -m json.tool
```

Expected: JSON response with `choices[0].message.content` containing "OK". If you get `{"error":"..."}` check the gateway logs.

**Step 6: Commit**

```bash
# Note: openclaw.json is NOT in the dashboard repo — no commit needed here.
# This is a config change to ~/.openclaw/openclaw.json (the live config).
echo "Gateway endpoint enabled. No dashboard repo commit needed for this step."
```

---

## Task 2: Add `"ai"` Section to config.json

**Files:**
- Modify: `config.json` in the dashboard repo root

**Context:** The dashboard server reads `config.json` at startup. Adding an `"ai"` section here lets the user configure the gateway port, model, agent, and dotenv path without touching Python code.

**Step 1: Read current config.json**

```bash
cat /Users/mudrii/src/openclaw-dashboard/config.json
```

**Step 2: Write the failing test**

Add to `tests/test_chat.py` (create the file):

```python
"""AI chat endpoint tests — AC-CHAT-1 through AC-CHAT-8."""

import json
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(REPO, "config.json")


class TestAiConfig(unittest.TestCase):
    """AC-CHAT-1: config.json has ai section with required keys."""

    def test_ac_chat_1_ai_config_has_required_keys(self):
        """AC-CHAT-1: config.json must have ai section with expected keys."""
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        ai = cfg.get("ai", {})
        self.assertIsInstance(ai, dict, "ai section must be a dict")
        self.assertIn("gatewayPort", ai, "ai.gatewayPort required")
        self.assertIn("model", ai, "ai.model required")
        self.assertIn("agentId", ai, "ai.agentId required")
        self.assertIn("maxHistory", ai, "ai.maxHistory required")
        self.assertIsInstance(ai["gatewayPort"], int)
        self.assertIsInstance(ai["maxHistory"], int)
        self.assertGreater(ai["maxHistory"], 0)
```

**Step 3: Run test to verify it fails**

```bash
cd /Users/mudrii/src/openclaw-dashboard
python3 -m pytest tests/test_chat.py::TestAiConfig -v
```

Expected: FAIL — `ai section must be a dict` or `ai.gatewayPort required`

**Step 4: Add ai section to config.json**

Edit `config.json` to add after the existing `"openclawPath"` line:

```json
"ai": {
    "enabled": true,
    "gatewayPort": 18789,
    "model": "kimi-coding/k2p5",
    "agentId": "main",
    "maxHistory": 6,
    "dotenvPath": "~/.openclaw/.env"
}
```

The full updated `config.json` (keeping all existing keys):
```json
{
  "bot": {
    "name": "My Bot",
    "emoji": "🤖"
  },
  "theme": {
    "preset": "dark"
  },
  "panels": {
    "sessions": true,
    "crons": true,
    "skills": true,
    "tokenUsage": true,
    "subagentUsage": true,
    "models": true
  },
  "refresh": {
    "intervalSeconds": 30,
    "autoRefresh": true
  },
  "server": {
    "port": 8080,
    "host": "127.0.0.1"
  },
  "openclawPath": "~/.openclaw",
  "ai": {
    "enabled": true,
    "gatewayPort": 18789,
    "model": "kimi-coding/k2p5",
    "agentId": "main",
    "maxHistory": 6,
    "dotenvPath": "~/.openclaw/.env"
  }
}
```

**Step 5: Run test to verify it passes**

```bash
python3 -m pytest tests/test_chat.py::TestAiConfig -v
```

Expected: PASS

**Step 6: Commit**

```bash
cd /Users/mudrii/src/openclaw-dashboard
git add config.json tests/test_chat.py
git commit -m "feat: add ai config section and initial test skeleton"
```

---

## Task 3: Add `read_dotenv()` to server.py

**Files:**
- Modify: `server.py` (add function after the `load_config()` function at line ~28)
- Test: `tests/test_chat.py` (add TestReadDotenv class)

**Context:** The gateway token lives in `~/.openclaw/.env` as `OPENCLAW_GATEWAY_TOKEN=<value>`. This function reads a `.env` style file (KEY=value lines, ignoring comments and blanks) and returns a dict. Pure stdlib — no `python-dotenv` package.

**Step 1: Write the failing test**

Add `TestReadDotenv` class to `tests/test_chat.py`:

```python
import tempfile

class TestReadDotenv(unittest.TestCase):
    """AC-CHAT-2: read_dotenv() parses KEY=VALUE files correctly."""

    def _run(self, content):
        """Write content to a temp file and call read_dotenv."""
        import sys
        sys.path.insert(0, REPO)
        from server import read_dotenv
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(content)
            f.flush()
            return read_dotenv(f.name)

    def test_ac_chat_2a_parses_key_value(self):
        """AC-CHAT-2a: Basic KEY=VALUE parsing."""
        result = self._run("FOO=bar\nBAZ=qux\n")
        self.assertEqual(result.get("FOO"), "bar")
        self.assertEqual(result.get("BAZ"), "qux")

    def test_ac_chat_2b_ignores_comments_and_blanks(self):
        """AC-CHAT-2b: Lines starting with # and blank lines are ignored."""
        result = self._run("# comment\n\nKEY=value\n")
        self.assertNotIn("# comment", result)
        self.assertIn("KEY", result)

    def test_ac_chat_2c_missing_file_returns_empty(self):
        """AC-CHAT-2c: Non-existent file returns empty dict (no exception)."""
        import sys
        sys.path.insert(0, REPO)
        from server import read_dotenv
        result = read_dotenv("/nonexistent/path/.env")
        self.assertEqual(result, {})

    def test_ac_chat_2d_values_with_equals_sign(self):
        """AC-CHAT-2d: Values containing = are preserved after first split."""
        result = self._run("TOKEN=abc=def=ghi\n")
        self.assertEqual(result.get("TOKEN"), "abc=def=ghi")
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_chat.py::TestReadDotenv -v
```

Expected: FAIL — `ImportError: cannot import name 'read_dotenv' from 'server'`

**Step 3: Add `read_dotenv()` to server.py**

Add after `load_config()` function (after line 34), before `run_refresh()`:

```python
def read_dotenv(path):
    """Read a KEY=VALUE .env file, return dict. Ignores comments and blanks."""
    result = {}
    try:
        expanded = os.path.expanduser(path)
        with open(expanded, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip()
    except (FileNotFoundError, PermissionError):
        pass
    return result
```

**Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_chat.py::TestReadDotenv -v
```

Expected: 4 PASS

**Step 5: Commit**

```bash
git add server.py tests/test_chat.py
git commit -m "feat: add read_dotenv() utility to server.py"
```

---

## Task 4: Add `build_dashboard_prompt()` to server.py

**Files:**
- Modify: `server.py` (add after `read_dotenv()`)
- Test: `tests/test_chat.py` (add TestBuildPrompt class)

**Context:** Converts `data.json` into a compressed text system prompt for the LLM. Must be self-contained (no missing key should crash it — use `.get()` everywhere). The prompt should give the AI everything it needs to answer questions about costs, sessions, crons, alerts, and configuration.

**Step 1: Write the failing test**

Add `TestBuildPrompt` class to `tests/test_chat.py`:

```python
class TestBuildPrompt(unittest.TestCase):
    """AC-CHAT-3: build_dashboard_prompt() produces structured context."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, REPO)
        from server import build_dashboard_prompt
        cls.build = build_dashboard_prompt

    def _minimal_data(self, **overrides):
        base = {
            "gateway": {"status": "online", "uptime": "2h", "memory": "120 MB", "pid": 1234},
            "totalCostToday": 0.42,
            "totalCostAllTime": 18.5,
            "projectedMonthly": 12.0,
            "subagentCostToday": 0.05,
            "sessionCount": 3,
            "sessions": [{"name": "test", "model": "kimi", "type": "dm", "contextPct": 40}],
            "crons": [{"name": "daily", "lastStatus": "ok", "schedule": "0 9 * * *"}],
            "alerts": [],
            "costBreakdown": [{"model": "kimi", "cost": 0.42}],
            "agentConfig": {"primaryModel": "kimi/k2p5", "fallbacks": []},
            "lastRefresh": "14:32:00",
        }
        base.update(overrides)
        return base

    def test_ac_chat_3a_contains_gateway_status(self):
        """AC-CHAT-3a: Prompt contains gateway status."""
        prompt = self.build(self._minimal_data())
        self.assertIn("online", prompt.lower())

    def test_ac_chat_3b_contains_cost_today(self):
        """AC-CHAT-3b: Prompt contains today's cost."""
        prompt = self.build(self._minimal_data())
        self.assertIn("0.42", prompt)

    def test_ac_chat_3c_contains_alerts_section(self):
        """AC-CHAT-3c: Prompt has alerts section even when empty."""
        prompt = self.build(self._minimal_data(alerts=[]))
        self.assertIn("ALERTS", prompt.upper())

    def test_ac_chat_3d_handles_missing_keys_gracefully(self):
        """AC-CHAT-3d: Empty dict does not raise."""
        try:
            prompt = self.build({})
            self.assertIsInstance(prompt, str)
        except KeyError as e:
            self.fail(f"build_dashboard_prompt crashed on empty data: {e}")

    def test_ac_chat_3e_contains_failed_cron(self):
        """AC-CHAT-3e: Failed cron jobs are highlighted in prompt."""
        data = self._minimal_data(crons=[
            {"name": "backup", "lastStatus": "error", "schedule": "0 1 * * *", "lastError": "timeout"}
        ])
        prompt = self.build(data)
        self.assertIn("error", prompt.lower())
        self.assertIn("backup", prompt)
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_chat.py::TestBuildPrompt -v
```

Expected: FAIL — `ImportError: cannot import name 'build_dashboard_prompt'`

**Step 3: Add `build_dashboard_prompt()` to server.py**

Add after `read_dotenv()`:

```python
def build_dashboard_prompt(data):
    """Build a compressed system prompt from data.json for the AI assistant."""
    gw = data.get("gateway") or {}
    ac = data.get("agentConfig") or {}

    lines = [
        "You are an AI assistant embedded in the OpenClaw Dashboard.",
        "Answer questions concisely. Use plain text, no markdown.",
        f"Data as of: {data.get('lastRefresh', 'unknown')}",
        "",
        "=== GATEWAY ===",
        f"Status: {gw.get('status', '?')} | PID: {gw.get('pid', '?')} | "
        f"Uptime: {gw.get('uptime', '?')} | Memory: {gw.get('memory', '?')}",
        "",
        "=== COSTS ===",
        f"Today: ${data.get('totalCostToday', 0):.4f} "
        f"(sub-agents: ${data.get('subagentCostToday', 0):.4f})",
        f"All-time: ${data.get('totalCostAllTime', 0):.2f} | "
        f"Projected monthly: ${data.get('projectedMonthly', 0):.0f}",
    ]

    breakdown = data.get("costBreakdown") or []
    if breakdown:
        lines.append("By model (all-time): " + ", ".join(
            f"{d.get('model','?')} ${d.get('cost', 0):.2f}"
            for d in breakdown[:5]
        ))

    sess = data.get("sessions") or []
    lines += [
        "",
        f"=== SESSIONS ({data.get('sessionCount', len(sess))} total, showing top 3) ===",
    ]
    for s in sess[:3]:
        lines.append(
            f"  {s.get('name','?')} | {s.get('model','?')} | "
            f"{s.get('type','?')} | context: {s.get('contextPct', 0)}%"
        )

    crons = data.get("crons") or []
    failed = [c for c in crons if c.get("lastStatus") == "error"]
    lines += [
        "",
        f"=== CRON JOBS ({len(crons)} total, {len(failed)} failed) ===",
    ]
    for c in crons[:5]:
        status = c.get("lastStatus", "?")
        err = f" ERROR: {c.get('lastError','')}" if status == "error" else ""
        lines.append(f"  {c.get('name','?')} | {c.get('schedule','?')} | {status}{err}")

    alerts = data.get("alerts") or []
    lines += ["", "=== ALERTS ==="]
    if alerts:
        for a in alerts:
            lines.append(f"  [{a.get('severity','?').upper()}] {a.get('message','?')}")
    else:
        lines.append("  None")

    lines += [
        "",
        "=== CONFIGURATION ===",
        f"Primary model: {ac.get('primaryModel', '?')}",
        f"Fallbacks: {', '.join(ac.get('fallbacks', [])) or 'none'}",
    ]

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_chat.py::TestBuildPrompt -v
```

Expected: 5 PASS

**Step 5: Commit**

```bash
git add server.py tests/test_chat.py
git commit -m "feat: add build_dashboard_prompt() for AI context compression"
```

---

## Task 5: Add `call_gateway()` to server.py

**Files:**
- Modify: `server.py` (add after `build_dashboard_prompt()`)
- Test: `tests/test_chat.py` (add TestCallGateway class)

**Context:** Uses `urllib.request` (stdlib) to POST to `localhost:<port>/v1/chat/completions`. Returns `{"answer": "..."}` on success or `{"error": "..."}` on failure. Timeout is 30 seconds. History is a list of `{"role": "user"|"assistant", "content": "..."}` dicts — prepend system as the first message.

**Step 1: Write the failing test**

Add `TestCallGateway` to `tests/test_chat.py`:

```python
class TestCallGateway(unittest.TestCase):
    """AC-CHAT-4: call_gateway() handles success and failure cases."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, REPO)
        from server import call_gateway
        cls.call = call_gateway

    def test_ac_chat_4a_unreachable_port_returns_error(self):
        """AC-CHAT-4a: Unreachable gateway returns error dict, not exception."""
        result = self.call(
            system="You are a helper.",
            history=[],
            question="hi",
            port=19999,  # nothing running here
            token="fake",
            model="test-model",
            agent_id="main",
        )
        self.assertIn("error", result)
        self.assertIsInstance(result["error"], str)

    def test_ac_chat_4b_returns_dict_with_answer_or_error(self):
        """AC-CHAT-4b: Return value is always a dict with 'answer' or 'error'."""
        result = self.call(
            system="You are a helper.",
            history=[],
            question="hi",
            port=19999,
            token="fake",
            model="test-model",
            agent_id="main",
        )
        self.assertIsInstance(result, dict)
        has_answer = "answer" in result
        has_error = "error" in result
        self.assertTrue(has_answer or has_error, "Must have answer or error key")
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_chat.py::TestCallGateway -v
```

Expected: FAIL — `ImportError: cannot import name 'call_gateway'`

**Step 3: Add `call_gateway()` to server.py**

Add after `build_dashboard_prompt()`, before the `DashboardHandler` class:

```python
def call_gateway(system, history, question, port, token, model, agent_id):
    """Call the OpenClaw gateway's OpenAI-compatible chat completions endpoint.

    Returns {"answer": "..."} on success, {"error": "..."} on failure.
    history is a list of {"role": ..., "content": ...} dicts (last maxHistory items).
    """
    import urllib.request
    import urllib.error

    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 512,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"http://localhost:{port}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "x-openclaw-agent-id": agent_id,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            content = (
                body.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
            )
            return {"answer": content or "(empty response)"}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": f"Gateway HTTP {e.code}: {body[:200]}"}
    except urllib.error.URLError as e:
        return {"error": f"Gateway unreachable: {e.reason}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}
```

**Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_chat.py::TestCallGateway -v
```

Expected: 2 PASS

**Step 5: Commit**

```bash
git add server.py tests/test_chat.py
git commit -m "feat: add call_gateway() with urllib stdlib, error handling"
```

---

## Task 6: Add `/api/chat` POST Endpoint to server.py

**Files:**
- Modify: `server.py` (modify `DashboardHandler`, add globals, update `main()`)
- Test: `tests/test_chat.py` (add TestChatEndpoint class — integration tests)

**Context:** This is the main wiring task. `DashboardHandler` needs `do_POST()` and `handle_chat()`. Module-level globals `_ai_cfg` and `_gateway_token` are set once by `main()`. The endpoint: reads body, validates question, loads `data.json`, builds prompt, calls gateway, returns JSON.

**Step 1: Write the failing integration test**

Add `TestChatEndpoint` to `tests/test_chat.py`. Note: this extends `ServerTestBase` from `test_server.py` pattern but defined here inline:

```python
import http.client
import subprocess
import sys
import threading
import time


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


SERVER_PY = os.path.join(REPO, "server.py")
DATA_FILE = os.path.join(REPO, "data.json")


class ChatServerBase(unittest.TestCase):
    """Start server.py on a random port. Shared by all chat endpoint tests."""

    port = None
    proc = None

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump({
                    "gateway": {"status": "online", "uptime": "1h", "memory": "100 MB", "pid": 1},
                    "totalCostToday": 0.50, "totalCostAllTime": 10.0, "projectedMonthly": 15.0,
                    "subagentCostToday": 0.0, "sessionCount": 1,
                    "sessions": [], "crons": [], "alerts": [],
                    "costBreakdown": [], "agentConfig": {},
                    "lastRefresh": "now",
                }, f)
        cls.proc = subprocess.Popen(
            [sys.executable, SERVER_PY, "-p", str(cls.port)],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for _ in range(30):
            try:
                conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("Server didn't start in time")

    @classmethod
    def tearDownClass(cls):
        if cls.proc:
            cls.proc.terminate()
            cls.proc.wait(timeout=5)

    def _post(self, path, body, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        encoded = json.dumps(body).encode() if isinstance(body, dict) else body
        h = {"Content-Type": "application/json", "Content-Length": str(len(encoded))}
        if headers:
            h.update(headers)
        conn.request("POST", path, body=encoded, headers=h)
        resp = conn.getresponse()
        raw = resp.read().decode()
        conn.close()
        return resp, raw


class TestChatEndpoint(ChatServerBase):
    """AC-CHAT-5 through AC-CHAT-8: /api/chat HTTP endpoint tests."""

    def test_ac_chat_5_post_returns_json_with_answer_or_error(self):
        """AC-CHAT-5: POST /api/chat returns 200 with answer or error key."""
        resp, body = self._post("/api/chat", {"question": "What is today's cost?"})
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertTrue("answer" in data or "error" in data,
                        f"Missing answer/error key: {data}")

    def test_ac_chat_6_empty_question_returns_400(self):
        """AC-CHAT-6: Empty question returns 400."""
        resp, body = self._post("/api/chat", {"question": ""})
        self.assertEqual(resp.status, 400)

    def test_ac_chat_7_missing_question_key_returns_400(self):
        """AC-CHAT-7: Missing question key returns 400."""
        resp, body = self._post("/api/chat", {"msg": "hi"})
        self.assertEqual(resp.status, 400)

    def test_ac_chat_8_bad_json_returns_400(self):
        """AC-CHAT-8: Non-JSON body returns 400."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/chat", body=b"not json",
                     headers={"Content-Type": "application/json", "Content-Length": "8"})
        resp = conn.getresponse()
        conn.close()
        self.assertEqual(resp.status, 400)
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_chat.py::TestChatEndpoint -v
```

Expected: FAIL — server returns 405 (no POST handler yet)

**Step 3: Add globals + `do_POST` + `handle_chat()` to server.py**

**3a** — Add globals after the existing globals (around line 26):

```python
_ai_cfg = {}          # Set by main()
_gateway_token = ""   # Set by main() from dotenv
```

**3b** — Add `do_POST` and `handle_chat` to `DashboardHandler` class (after `handle_refresh`, before `log_message`):

```python
def do_POST(self):
    if self.path == "/api/chat":
        self.handle_chat()
    else:
        self.send_response(404)
        self.end_headers()

def handle_chat(self):
    if not _ai_cfg.get("enabled", True):
        self._send_json(503, {"error": "AI chat is disabled in config.json"})
        return

    length = int(self.headers.get("Content-Length", 0))
    try:
        body = json.loads(self.rfile.read(length))
    except (json.JSONDecodeError, ValueError):
        self._send_json(400, {"error": "Invalid JSON body"})
        return

    question = body.get("question", "").strip()
    if not question:
        self._send_json(400, {"error": "question is required and must be non-empty"})
        return

    history = body.get("history", [])
    if not isinstance(history, list):
        history = []
    max_hist = int(_ai_cfg.get("maxHistory", 6))
    history = history[-max_hist:]

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    system_prompt = build_dashboard_prompt(data)
    result = call_gateway(
        system=system_prompt,
        history=history,
        question=question,
        port=int(_ai_cfg.get("gatewayPort", 18789)),
        token=_gateway_token,
        model=_ai_cfg.get("model", "kimi-coding/k2p5"),
        agent_id=_ai_cfg.get("agentId", "main"),
    )
    self._send_json(200, result)

def _send_json(self, status, data):
    """Helper: send a JSON response with CORS headers."""
    body = json.dumps(data).encode()
    self.send_response(status)
    self.send_header("Content-Type", "application/json")
    self.send_header("Cache-Control", "no-cache")
    origin = self.headers.get("Origin", "")
    if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
        self.send_header("Access-Control-Allow-Origin", origin)
    else:
        self.send_header("Access-Control-Allow-Origin", "http://localhost:8080")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)
```

**3c** — Update `main()` to load AI config and gateway token into globals (add after `_debounce_sec` is set, around line 140):

```python
global _ai_cfg, _gateway_token
_ai_cfg = cfg.get("ai", {})
dotenv_path = _ai_cfg.get("dotenvPath", "~/.openclaw/.env")
env_vars = read_dotenv(dotenv_path)
_gateway_token = env_vars.get("OPENCLAW_GATEWAY_TOKEN", "")
if _ai_cfg.get("enabled", True) and not _gateway_token:
    print("[dashboard] WARNING: ai.enabled=true but OPENCLAW_GATEWAY_TOKEN not found in dotenv")
```

**Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_chat.py::TestChatEndpoint -v
```

Expected: 4 PASS (AC-CHAT-5 may show `error` key if gateway is not reachable — that's correct behavior)

**Step 5: Run full test suite — must still pass**

```bash
python3 -m pytest tests/ -v
```

Expected: All existing 44 tests pass + 4 new chat endpoint tests pass. Zero failures.

**Step 6: Commit**

```bash
git add server.py tests/test_chat.py
git commit -m "feat: add /api/chat POST endpoint with gateway integration"
```

---

## Task 7: Add Chat Panel CSS + HTML to index.html

**Files:**
- Modify: `index.html` (CSS inside `<style>`, HTML before `</body>`)
- Test: `tests/test_frontend.py` (add 3 new static analysis tests)

**Context:** The chat panel is a fixed-position overlay that slides up from the bottom-right. It uses existing CSS custom properties (`var(--bg)`, `var(--border)`, `var(--accent)`, etc.) and the `.glass` pattern. The `💬` FAB button sits in the bottom-right corner.

**Step 1: Write the failing test**

Add to `tests/test_frontend.py` (at the end, new class):

```python
class TestChatPanelHTML(unittest.TestCase):
    """AC-CHAT-9 through AC-CHAT-11: Chat panel HTML/CSS presence."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "index.html")) as f:
            cls.html = f.read()

    def test_ac_chat_9_chat_button_exists(self):
        """AC-CHAT-9: Chat FAB button with id=chatBtn exists."""
        self.assertIn('id="chatBtn"', self.html)

    def test_ac_chat_10_chat_panel_exists(self):
        """AC-CHAT-10: Chat panel with id=chatPanel exists."""
        self.assertIn('id="chatPanel"', self.html)

    def test_ac_chat_11_chat_input_exists(self):
        """AC-CHAT-11: Chat input with id=chatInput exists."""
        self.assertIn('id="chatInput"', self.html)
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_frontend.py::TestChatPanelHTML -v
```

Expected: 3 FAIL — elements don't exist yet

**Step 3: Add CSS to index.html**

Insert before the closing `</style>` tag (around line 190):

```css
/* AI Chat Panel */
.chat-fab{position:fixed;bottom:24px;right:24px;width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 4px 20px rgba(99,102,241,.4);z-index:1000;transition:transform .2s}
.chat-fab:hover{transform:scale(1.1)}
.chat-panel{position:fixed;bottom:84px;right:24px;width:360px;max-height:520px;display:none;flex-direction:column;border-radius:16px;border:1px solid var(--border);background:var(--bg);box-shadow:0 8px 40px rgba(0,0,0,.5);z-index:999;overflow:hidden}
.chat-panel.open{display:flex}
.chat-header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border);background:var(--surface)}
.chat-header-title{font-size:13px;font-weight:700;color:var(--textStrong)}
.chat-close{background:none;border:none;color:var(--muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:4px}
.chat-close:hover{color:var(--textStrong);background:var(--surfaceHover)}
.chat-messages{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;min-height:200px;max-height:340px}
.chat-bubble{padding:8px 12px;border-radius:10px;font-size:12px;line-height:1.5;max-width:90%;word-wrap:break-word;white-space:pre-wrap}
.chat-bubble.user{background:rgba(99,102,241,.15);color:var(--text);border:1px solid rgba(99,102,241,.2);align-self:flex-end;border-radius:10px 10px 2px 10px}
.chat-bubble.assistant{background:var(--surface);color:var(--text);border:1px solid var(--border);align-self:flex-start;border-radius:10px 10px 10px 2px}
.chat-bubble.error{background:rgba(248,113,113,.08);color:var(--red);border:1px solid rgba(248,113,113,.2)}
.chat-bubble.thinking{color:var(--dim);font-style:italic}
.chat-quick{display:flex;flex-wrap:wrap;gap:4px;padding:8px 12px;border-top:1px solid var(--border)}
.chat-chip{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:4px 10px;font-size:10px;color:var(--muted);cursor:pointer;transition:all .15s;white-space:nowrap}
.chat-chip:hover{background:var(--surfaceHover);color:var(--textStrong);border-color:var(--accent)}
.chat-input-row{display:flex;gap:6px;padding:10px 12px;border-top:1px solid var(--border);background:var(--surface)}
.chat-input{flex:1;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:7px 10px;font-size:12px;color:var(--text);font-family:inherit;resize:none;outline:none;transition:border-color .15s}
.chat-input:focus{border-color:var(--accent)}
.chat-send{background:var(--accent);border:none;border-radius:8px;padding:7px 12px;color:#fff;font-size:13px;cursor:pointer;transition:background .15s;flex-shrink:0}
.chat-send:hover{background:var(--accent2)}
.chat-send:disabled{opacity:.5;cursor:not-allowed}
```

**Step 4: Add HTML to index.html**

Insert before the closing `</body>` tag (after line 1159, before `</body>`):

```html
<!-- AI Chat Panel -->
<button class="chat-fab" id="chatBtn" onclick="toggleChat()" title="Ask AI about your dashboard">💬</button>
<div class="chat-panel" id="chatPanel">
  <div class="chat-header">
    <span class="chat-header-title">🤖 Dashboard AI</span>
    <button class="chat-close" onclick="toggleChat()">✕</button>
  </div>
  <div class="chat-messages" id="chatMessages">
    <div class="chat-bubble assistant">Hi! Ask me anything about your dashboard metrics, costs, or configuration.</div>
  </div>
  <div class="chat-quick" id="chatQuick">
    <button class="chat-chip" onclick="sendChat('Summarize today\'s costs')">Today's costs</button>
    <button class="chat-chip" onclick="sendChat('Are there any alerts or issues?')">Alerts</button>
    <button class="chat-chip" onclick="sendChat('Which model is costing the most?')">Top model</button>
    <button class="chat-chip" onclick="sendChat('What is the gateway status and uptime?')">Gateway</button>
  </div>
  <div class="chat-input-row">
    <textarea class="chat-input" id="chatInput" rows="1" placeholder="Ask about metrics, costs, crons..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat()}"></textarea>
    <button class="chat-send" id="chatSend" onclick="sendChat()">↑</button>
  </div>
</div>
```

**Step 5: Run test to verify it passes**

```bash
python3 -m pytest tests/test_frontend.py::TestChatPanelHTML -v
```

Expected: 3 PASS

**Step 6: Commit**

```bash
git add index.html tests/test_frontend.py
git commit -m "feat: add AI chat panel CSS and HTML markup"
```

---

## Task 8: Add Chat JavaScript to index.html

**Files:**
- Modify: `index.html` (add JS before `</script>`)
- Test: `tests/test_frontend.py` (add TestChatPanelJS class)

**Context:** JavaScript manages chat state and calls `/api/chat`. Key design decisions: `chatHistory` is capped at `maxHistory` items; the user message is appended immediately (optimistic UI) while the API call is in flight; send button is disabled during request; `esc()` is called on all message content before `innerHTML`.

**Step 1: Write the failing test**

Add to `tests/test_frontend.py`:

```python
class TestChatPanelJS(unittest.TestCase):
    """AC-CHAT-12 through AC-CHAT-14: Chat JavaScript patterns."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "index.html")) as f:
            cls.html = f.read()

    def test_ac_chat_12_send_chat_function_defined(self):
        """AC-CHAT-12: sendChat() function is defined."""
        self.assertIn("function sendChat", self.html)

    def test_ac_chat_13_chat_history_variable(self):
        """AC-CHAT-13: chatHistory variable is declared."""
        self.assertIn("chatHistory", self.html)

    def test_ac_chat_14_toggle_chat_defined(self):
        """AC-CHAT-14: toggleChat() function is defined."""
        self.assertIn("function toggleChat", self.html)
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_frontend.py::TestChatPanelJS -v
```

Expected: 3 FAIL

**Step 3: Add JavaScript to index.html**

Insert before the closing `</script>` tag (before line 1158 `setInterval(...)`):

```javascript
// ── AI Chat ──
let chatHistory = [];
const CHAT_MAX_HISTORY = 6;

function toggleChat() {
  const panel = $('chatPanel');
  panel.classList.toggle('open');
  if (panel.classList.contains('open')) {
    $('chatInput').focus();
  }
}

function appendMessage(role, text) {
  const msgs = $('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-bubble ' + role;
  div.textContent = text;  // textContent is XSS-safe — no esc() needed
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

async function sendChat(prefill) {
  const input = $('chatInput');
  const question = (prefill !== undefined ? prefill : input.value).trim();
  if (!question) return;

  input.value = '';
  $('chatSend').disabled = true;

  appendMessage('user', question);
  const thinking = appendMessage('thinking', '…');

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        question,
        history: chatHistory.slice(-CHAT_MAX_HISTORY),
      }),
    });
    const data = await res.json();

    thinking.remove();

    if (data.answer) {
      appendMessage('assistant', data.answer);
      chatHistory.push({role: 'user', content: question});
      chatHistory.push({role: 'assistant', content: data.answer});
      if (chatHistory.length > CHAT_MAX_HISTORY * 2) {
        chatHistory = chatHistory.slice(-CHAT_MAX_HISTORY * 2);
      }
    } else {
      appendMessage('error', 'Error: ' + (data.error || 'Unknown error'));
    }
  } catch (e) {
    thinking.remove();
    appendMessage('error', 'Network error: ' + e.message);
  } finally {
    $('chatSend').disabled = false;
    input.focus();
  }
}
```

**Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_frontend.py::TestChatPanelJS -v
```

Expected: 3 PASS

**Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: All 44 original tests + 10 new tests (test_chat.py) + 6 new frontend tests = **60 total PASS, 0 FAIL**

**Step 6: Manual smoke test**

```bash
cd /Users/mudrii/src/openclaw-dashboard
python3 server.py &
sleep 1
# Test the endpoint directly
curl -s -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the gateway status?","history":[]}' | python3 -m json.tool
# Open browser
open http://localhost:8080
```

Expected: `{"answer": "The gateway is online..."}` from the curl, and the `💬` button visible in bottom-right of the browser.

**Step 7: Commit**

```bash
git add index.html tests/test_frontend.py
git commit -m "feat: add AI chat JavaScript with history management"
```

---

## Final Checklist

- [ ] Task 1: Gateway OpenAI endpoint enabled in `~/.openclaw/openclaw.json`
- [ ] Task 2: `config.json` has `"ai"` section, `TestAiConfig` passes
- [ ] Task 3: `read_dotenv()` in `server.py`, 4 tests pass
- [ ] Task 4: `build_dashboard_prompt()` in `server.py`, 5 tests pass
- [ ] Task 5: `call_gateway()` in `server.py`, 2 tests pass
- [ ] Task 6: `do_POST` + `handle_chat()` + globals in `server.py`, 4 integration tests pass
- [ ] Task 7: Chat panel CSS + HTML in `index.html`, 3 tests pass
- [ ] Task 8: Chat JavaScript in `index.html`, 3 tests pass
- [ ] Full suite: `python3 -m pytest tests/ -v` — all tests pass
- [ ] Manual smoke: `💬` button opens panel, question gets AI answer

## File Summary: What Changed and Where

### `server.py` (after all tasks)

```
line ~28  read_dotenv(path)                    ← new
line ~45  build_dashboard_prompt(data)          ← new
line ~90  call_gateway(system, history, ...)   ← new
line ~115 _ai_cfg = {}                          ← new global
line ~116 _gateway_token = ""                  ← new global
line ~140 DashboardHandler.do_POST()           ← new
line ~145 DashboardHandler.handle_chat()       ← new
line ~175 DashboardHandler._send_json()        ← new helper
line ~230 main() — loads _ai_cfg, _gateway_token ← modified
```

### `index.html` (after all tasks)

```
line ~187 AI Chat Panel CSS (20 rules)         ← new, inside <style>
line ~1160 chat FAB button #chatBtn            ← new, before </body>
line ~1162 chat panel #chatPanel               ← new
line ~1155 chatHistory, toggleChat(), ...      ← new JS, before </script>
```

### `tests/test_chat.py` (new file)

```
TestAiConfig          — AC-CHAT-1  (1 test)
TestReadDotenv        — AC-CHAT-2  (4 tests)
TestBuildPrompt       — AC-CHAT-3  (5 tests)
TestCallGateway       — AC-CHAT-4  (2 tests)
TestChatEndpoint      — AC-CHAT-5-8 (4 tests)
```

### `tests/test_frontend.py` (appended)

```
TestChatPanelHTML     — AC-CHAT-9-11  (3 tests)
TestChatPanelJS       — AC-CHAT-12-14 (3 tests)
```
