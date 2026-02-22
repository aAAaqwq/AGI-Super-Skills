---
name: fast-browser-use
displayName: Fastest Browser Use
emoji: "⚡"
summary: Rust-powered browser automation that rips through DOMs 10x faster than Puppeteer.
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
