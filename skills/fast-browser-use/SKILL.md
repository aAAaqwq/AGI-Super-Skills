---
name: fast-browser-use
displayName: Fastest Browser Use
emoji: "⚡"
summary: Rust-powered browser automation that rips through DOMs 10x faster than Puppeteer.
aliases:
  - fbu
  - use fbu
homepage: https://github.com/rknoche6/fast-browser-use
primaryEnv: bash
os:
  - darwin
  - linux
requires:
  bins:
    - chrome
install:
  - kind: brew
    formula: rknoche6/tap/fast-browser-use
  - kind: cargo
    package: fast-browser-use
config:
  requiredEnv:
    - CHROME_PATH
  example: |
    # Standard headless setup
    export CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    export BROWSER_HEADLESS="true"
---

# Fastest Browser Use

A Rust-based browser automation engine that provides a lightweight binary driving Chrome directly via CDP. It is optimized for token-efficient DOM extraction, robust session management, and speed.

![Terminal Demo](https://placehold.co/800x400/1e1e1e/ffffff?text=Terminal+Demo+Coming+Soon)

## ⚠️ Important: Command Behavior

- **`navigate`** is a one-shot command — it opens the page, completes, then **immediately kills Chrome**. Do NOT use it if the user wants to see/interact with the browser.
- **`login`** keeps Chrome open and waits for user input (Enter) before saving session and closing. Use this when the user needs to interact manually.
- **`--headless false`** shows the Chrome window on the user's desktop (requires X11/Wayland display). Use this when the user wants to watch operations.
- **`--user-data-dir`** reuses an existing Chrome profile (login state, cookies, extensions). However, it may conflict if Chrome is already running with that profile. Prefer `--load-session` for saved sessions instead.

### 🔴 超时与自动关闭（必须遵守）

**所有 fbu 命令必须用 `timeout` 包裹**，防止 Chrome 进程残留：

```bash
# 标准用法：60秒超时，超时后先 SIGTERM，5秒后 SIGKILL
timeout --kill-after=5 60 fast-browser-use snapshot --url "https://example.com"

# 长任务（如 harvest）：120秒超时
timeout --kill-after=5 120 fast-browser-use harvest --url "https://example.com" --selector "a"
```

**超时后清理残留 Chrome 进程**（在 cron/自动化任务中建议加）：
```bash
# 命令结束后确保无残留
timeout --kill-after=5 60 fast-browser-use snapshot --url "..." || true
# 清理可能残留的 Chrome 进程（仅清理 fbu 启动的）
pkill -f "chrome.*--remote-debugging" 2>/dev/null || true
```

**推荐超时时间**：
- `snapshot`: 30-60s
- `navigate`: 30-60s
- `screenshot`: 30-60s
- `harvest`: 60-120s
- `login`: 300s（需要人工交互）
- Cloudflare 站点（`--headless false`）: 翻倍

### 🔐 Platform Authorization & Login Workflow

When you need to access a platform that requires the user's login (e.g. Polymarket, GitHub, Twitter), follow this complete workflow:

#### Session Persistence: `--user-data-dir` vs `--load-session`

- **`--load-session`** only restores cookies. Many modern platforms (OAuth, wallet-based, SPA) store auth state in localStorage/IndexedDB, so cookies alone are **insufficient**.
- **`--user-data-dir`** persists the **entire Chrome profile** (cookies + localStorage + IndexedDB + service workers). This is the **recommended approach** for most platforms.
- Use a **dedicated profile directory per platform** (e.g. `~/.openclaw/chrome-profiles/polymarket/`) to avoid lock conflicts with the user's running Chrome.

#### Complete Workflow

**Step 1: Create dedicated profile directory**
```bash
mkdir -p ~/.openclaw/chrome-profiles/<platform-name>
```

**Step 2: Open visible browser with `login` command**
```bash
export CHROME_PATH=/usr/bin/google-chrome  # adjust per system
fast-browser-use login \
  --url "https://platform.com" \
  --headless false \
  --user-data-dir ~/.openclaw/chrome-profiles/<platform-name> \
  --save-session ./<platform-name>-session.json
```
- `--headless false` so the user can see and interact with Chrome
- `--user-data-dir` for full state persistence
- `--save-session` as a backup (cookies-only fallback)
- The command will print "Press Enter after you have logged in..." and **wait**

**Step 3: Ask user to log in**
- Tell the user to log in manually in the Chrome window
- **Do NOT send Enter until the user explicitly confirms they have logged in**

**Step 4: User confirms → Save session**
- Once the user says they've logged in, send Enter (newline) to the process stdin
- fbu saves cookies to the session file and closes Chrome

**Step 5: Verify login state**
- Open a **new headless instance** with the same `--user-data-dir` and run `snapshot`:
```bash
fast-browser-use snapshot \
  --url "https://platform.com" \
  --user-data-dir ~/.openclaw/chrome-profiles/<platform-name>
```
- Check the DOM output for **logged-in indicators**: username, avatar, portfolio balance, dashboard content, account menu, etc.
- If you see "Login" / "Sign up" / "Register" buttons instead → login was NOT saved. Inform the user and re-run from Step 2.

**Step 6: Confirm to user**
- Report what you found (e.g. "✅ Verified: logged in, portfolio balance $6.02")
- The profile is now ready for future automated use

#### Subsequent Usage (After Login)
```bash
# All future commands for this platform just add --user-data-dir
fast-browser-use navigate \
  --url "https://platform.com/dashboard" \
  --user-data-dir ~/.openclaw/chrome-profiles/<platform-name>

fast-browser-use snapshot \
  --url "https://platform.com/portfolio" \
  --user-data-dir ~/.openclaw/chrome-profiles/<platform-name>
```

#### Session Expiry
- Before automated tasks, always **snapshot first and verify** the login is still valid
- If expired, re-run the login workflow from Step 2 (the profile dir already exists)

## 🧪 Recipes for Agents

### 1. Bypass "Bot Detection" via Human Emulation
Simulate mouse jitter and random delays to scrape protected sites.

```bash
fast-browser-use navigate --url "https://protected-site.com" \
  --human-emulation \
  --wait-for-selector "#content"
```

### 2. The "Deep Freeze" Snapshot
Capture the entire DOM state *and* computed styles for perfect reconstruction later.

```bash
fast-browser-use snapshot --include-styles --output state.json
```

### 3. Login & Cookie Heist
Log in manually once, then steal the session for headless automation.

**Step 1: Open non-headless for manual login**
```bash
fast-browser-use login --url "https://github.com/login" --save-session ./auth.json
```

**Step 2: Reuse session later**
```bash
fast-browser-use navigate --url "https://github.com/dashboard" --load-session ./auth.json
```

### 4. 🚜 Infinite Scroll Harvester
**Extract fresh data from infinite-scroll pages** — perfect for harvesting the latest posts, news, or social feeds.

```bash
# Harvest headlines from Hacker News (scrolls 3x, waits 800ms between)
fast-browser-use harvest \
  --url "https://news.ycombinator.com" \
  --selector ".titleline a" \
  --scrolls 3 \
  --delay 800 \
  --output headlines.json
```

**Real output** (59 unique items in ~6 seconds):
```json
[
  "Genode OS is a tool kit for building highly secure special-purpose OS",
  "Mobile carriers can get your GPS location",
  "Students using \"humanizer\" programs to beat accusations of cheating with AI",
  "Finland to end \"uncontrolled human experiment\" with ban on youth social media",
  ...
]
```

Works on any infinite scroll page: Reddit, Twitter, LinkedIn feeds, search results, etc.

### 5. 📸 Quick Screenshot
Capture any page as PNG:

```bash
fast-browser-use screenshot \
  --url "https://example.com" \
  --output page.png \
  --full-page  # Optional: capture entire scrollable page
```

### 6. 🗺️ Sitemap & Page Structure Analyzer
Discover how a site is organized by parsing sitemaps and analyzing page structure.

```bash
# Basic sitemap discovery (checks robots.txt + common sitemap URLs)
fast-browser-use sitemap --url "https://example.com"
```

```bash
# Full analysis with page structure (headings, nav, sections)
fast-browser-use sitemap \
  --url "https://example.com" \
  --analyze-structure \
  --max-pages 10 \
  --max-sitemaps 5 \
  --output site-structure.json
```

**Options:**
- `--analyze-structure`: Also extract page structure (headings, nav, sections, meta)
- `--max-pages N`: Limit structure analysis to N pages (default: 5)
- `--max-sitemaps N`: Limit sitemap parsing to N sitemaps (default: 10, useful for large sites)

**Example output:**
```json
{
  "base_url": "https://example.com",
  "robots_txt": "User-agent: *\nSitemap: https://example.com/sitemap.xml",
  "sitemaps": ["https://example.com/sitemap.xml"],
  "pages": [
    "https://example.com/about",
    "https://example.com/products",
    "https://example.com/contact"
  ],
  "page_structures": [
    {
      "url": "https://example.com",
      "title": "Example - Home",
      "headings": [
        {"level": 1, "text": "Welcome to Example"},
        {"level": 2, "text": "Our Services"}
      ],
      "nav_links": [
        {"text": "About", "href": "/about"},
        {"text": "Products", "href": "/products"}
      ],
      "sections": [
        {"tag": "main", "id": "content", "role": "main"},
        {"tag": "footer", "id": "footer", "role": null}
      ],
      "main_content": {"tag": "main", "id": "content", "word_count": 450},
      "meta": {
        "description": "Example company homepage",
        "canonical": "https://example.com/"
      }
    }
  ]
}
```

Use this to understand site architecture before scraping, map navigation flows, or audit SEO structure.

## ⚡ Performance Comparison

| Feature | Fast Browser Use (Rust) | Puppeteer (Node) | Selenium (Java) |
| :--- | :--- | :--- | :--- |
| **Startup Time** | **< 50ms** | ~800ms | ~2500ms |
| **Memory Footprint** | **15 MB** | 100 MB+ | 200 MB+ |
| **DOM Extract** | **Zero-Copy** | JSON Serialize | Slow Bridge |

## Capabilities & Tools

### Vision & Extraction
- **vision_map**: Returns a screenshot overlay with numbered bounding boxes for all interactive elements.
- **snapshot**: Capture the raw HTML snapshot (YAML/Markdown optimized for AI).
- **screenshot**: Capture a visual image of the page.
- **extract**: Get structured data from the DOM.
- **markdown**: Convert the current page content to Markdown.
- **sitemap**: Analyze site structure via robots.txt, sitemaps, and page semantic analysis.

### Navigation & Lifecycle
- **navigate**: Visit a specific URL.
- **go_back** / **go_forward**: Traverse browser history.
- **wait**: Pause execution or wait for specific conditions.
- **new_tab**: Open a new browser tab.
- **switch_tab**: Switch focus to a specific tab.
- **close_tab**: Close the current or specified tab.
- **tab_list**: List all open tabs.
- **close**: Terminate the browser session.

### Interaction
- **click**: Click elements via CSS selectors or DOM indices.
- **input**: Type text into fields.
- **press_key**: Send specific keyboard events.
- **hover**: Hover over elements.
- **scroll**: Scroll the viewport.
- **select**: Choose options in dropdowns.

### State & Debugging
- **cookies**: Manage session cookies (get/set).
- **local_storage**: Manage local storage data.
- **debug**: Access console logs and debug information.

## Usage

This skill is specialized for complex web interactions that require maintaining state (like being logged in), handling dynamic JavaScript content, or managing multiple pages simultaneously. It offers higher performance and control compared to standard fetch-based tools.
