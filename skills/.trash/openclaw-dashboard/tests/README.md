# OpenClaw Dashboard — ATDD Test Suite

## Quick Start

```bash
cd /path/to/openclaw-dashboard

# Run all static tests (no server needed)
python3 -m pytest tests/test_frontend.py tests/test_data_schema.py -v

# Run all tests including server integration (starts its own server)
python3 -m pytest tests/ -v

# Or use the runner script
bash tests/run_tests.sh
```

## Test Files

| File | Type | Server needed? | ACs covered |
|------|------|----------------|-------------|
| `test_chat.py` | Unit + Integration | Partial (unit tests no server; endpoint tests start server) | AC-CHAT-1..AC-CHAT-8 |
| `test_critical.py` | Static + Integration smoke | Partial (mixed static/runtime checks) | TC1-TC20 |
| `test_server.py` | Integration | No (self-contained — starts own server) | AC1-AC8 |
| `test_data_schema.py` | Static | No (reads data.json) | AC9-AC14 |
| `test_frontend.py` | Static analysis | No (reads source files) | AC15-AC24 |

## Acceptance Criteria

### Server Tests (test_server.py)
- **AC1:** GET / returns 200 and HTML content
- **AC2:** GET /api/refresh returns JSON with required top-level keys
- **AC3:** CORS header restricted to localhost origins (not wildcard *)
- **AC4:** GET /themes.json returns valid JSON
- **AC5:** Concurrent requests (5 threads) don't corrupt data.json
- **AC6:** Unknown routes return 404
- **AC7:** Refresh debouncing — rapid requests don't re-trigger refresh.sh
- **AC8:** data.json served correctly from pre-existing file

### Schema Tests (test_data_schema.py)
- **AC9:** All required top-level keys present in data.json
- **AC10:** `crons` list items have name, schedule, status, lastRun, nextRun
- **AC11:** `sessions` list items have key, model, type
- **AC12:** `totalCostToday` is a non-negative float
- **AC13:** `dailyChart` entries have date and totalCost keys
- **AC14:** `gateway` status is one of: online, offline, unknown

### Frontend Static Analysis (test_frontend.py)
- **AC15:** `esc()` XSS sanitizer defined and used on innerHTML positions
- **AC16:** `safeColor()` defined with hex regex validation
- **AC17:** `sectionChanged()` defined and uses `prevD`
- **AC18:** All 3 prev-tab variables exist (prevUTab, prevSrTab, prevStTab)
- **AC19:** `requestAnimationFrame` used in loadData()
- **AC20:** `prevD` deep-clone snapshot at end of render()
- **AC21:** No `shell=True` in embedded Python in refresh.sh
- **AC22:** `set -euo pipefail` in refresh.sh
- **AC23:** No CORS wildcard `*` in server.py
- **AC24:** json.load uses context managers (no bare `open()`)

### AI Chat Tests (test_chat.py)
- **AC-CHAT-1:** `config.json` contains required `ai` keys
- **AC-CHAT-2:** `read_dotenv()` parses dotenv safely
- **AC-CHAT-3:** `build_dashboard_prompt()` includes required context sections
- **AC-CHAT-4:** `call_gateway()` gracefully handles unreachable gateway
- **AC-CHAT-5:** POST `/api/chat` returns 200 with `answer` or `error`
- **AC-CHAT-6:** Empty question returns 400
- **AC-CHAT-7:** Missing question key returns 400
- **AC-CHAT-8:** Invalid JSON body returns 400

## Adding New Tests

1. Pick the appropriate file based on what you're testing
2. Add a new test method with a docstring starting with the AC number
3. Follow the naming convention: `test_acNN_description`
4. Static tests go in `test_frontend.py`; runtime tests in `test_server.py`

## Dependencies

- Python 3.8+ (stdlib only — `unittest`, `json`, `re`, `http.client`, `threading`)
- pytest (optional, for nicer output — tests work with `python3 -m unittest` too)
