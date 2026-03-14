---
name: linkedin-cdp
description: LinkedIn CDP: Input-only automation (mouse, keyboard, screenshots). Zero DOM access.
---
# LinkedIn CDP Automation

> LinkedIn automation via Chrome DevTools Protocol. Input-only (mouse/keyboard/screenshots). Zero DOM access.

## When to use

- "collect messages from linkedin" -> `LinkedInMessages`
- "who messaged me on linkedin" -> `LinkedInMessages`
- "write on linkedin" -> `LinkedInMessages.send_message()`
- "find on linkedin" -> `LinkedInSearch`
- "view profile" -> `LinkedInProfile`
- "send connection request" -> `LinkedInConnect`
- "show connection requests" -> `LinkedInConnect.screenshot_invitations()`

## Dependencies

- External: Chrome, `pip install websocket-client requests`
- Chrome must run with `--remote-debugging-port=9222` (separate instance)

## Paths

| What | Path |
|------|------|
| Script | `$HOME/linkedin-cdp/linkedin_cdp.py` |
| Modules | `$HOME/linkedin-cdp/linkedin_*.py` |
| Rate limiter | `$HOME/linkedin-cdp/rate_limiter.py` |
| Screenshots | `/tmp/li_screenshots/shot_*.jpg` |

## How to execute

### Step 0: Chrome Launch

**IMPORTANT:** Use the binary path directly, NOT `open -a 'Google Chrome'`.
`open -a` on macOS opens a tab in existing Chrome instead of a separate instance.

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  '--remote-allow-origins=*' \
  --user-data-dir="$HOME/chrome-debug-profile" \
  "https://www.linkedin.com" > /dev/null 2>&1 &
```

Run in background (`run_in_background: true`), then verify:
```bash
sleep 3 && curl -s "http://localhost:9222/json/version"
```

- `--user-data-dir` MUST differ from user's main Chrome profile
- `$HOME/chrome-debug-profile` persists login session between runs
- Don't connect CDP while user logs in. Wait for login to complete.

### Step 1: Calibration (REQUIRED on first run per session)

Every session may have different window size / DPR. On first run, take a calibration screenshot
and determine the coordinate mapping:

```python
import sys, subprocess, time
sys.path.insert(0, '$HOME/linkedin-cdp')
from linkedin_cdp import LinkedInBot

bot = LinkedInBot()
bot.connect()

# Take calibration screenshot — returns file path
path = bot.take_screenshot()
print(path)  # /tmp/li_screenshots/shot_0001.jpg

# Get image dimensions to determine DPR
result = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', path],
                       capture_output=True, text=True)
print(result.stdout)
bot.close()
```

Then read the calibration screenshot with Read tool. Calculate:
- **DPR** = image_width / expected_viewport_width (typically 2 on Retina Mac)
- **CSS coordinates** = image_pixel_coordinates / DPR

Store the DPR for all subsequent coordinate calculations in this session.

### Step 2: Coordinate System

All `click_at()`, `_click()` calls use **CSS coordinates**, not image pixels.

**Formula:** `CSS_coord = image_pixel_coord / DPR`

Typical Retina Mac (DPR=2, viewport ~1531x801):
- Screenshot: 3062x1602 pixels
- To click where you see something at image pixel (600, 400): click CSS (300, 200)

### Step 3: Use modules

```python
import sys
sys.path.insert(0, '$HOME/linkedin-cdp')
from linkedin_cdp import LinkedInBot

bot = LinkedInBot()
bot.connect()

# All actions use CSS coordinates
bot.click_at(x, y)        # click + screenshot
bot.type_text("text")      # type with human-like delays
bot.scroll_wheel(delta_y=500)  # scroll (keyword arg only!)
bot.take_screenshot()      # returns file path (JPEG)
bot.navigate_to(url)       # navigate + auto reconnect
bot.reconnect_to_tab()     # reconnect WebSocket after page change
bot.close()
```

## Known Fixed Coordinates (DPR=2, viewport ~1531x801)

These modal/dialog coordinates are **consistent across sessions** at the same viewport size.
Recalibrate if window size changes.

### Connection Request Modal

After clicking "Connect" on a profile:

| Element | CSS (x, y) | Notes |
|---------|-----------|-------|
| "Add a note" button | (751, 239) | White/outline button |
| "Send without a note" button | (911, 239) | Blue button |
| Note text field (click to focus) | (752, 259) | After clicking "Add a note" |
| "Send" button (with note) | (968, 393) | Blue, active after typing |
| "Cancel" button | (889, 393) | |

### Profile Page

| Element | CSS (x, y) | Notes |
|---------|-----------|-------|
| "Connect" button | (~270, 467-499) | y varies by profile layout (banner height, etc.) |
| "Message" button | (~383, 467-499) | Next to Connect |

### Messaging Page

`/messaging/` — conversation list on left, active thread on right.

| Element | CSS (x, y) | Notes |
|---------|-----------|-------|
| "Write a message..." text field | (715, 604) | Click to focus, then type_text() |
| Send button | (885, 724) | Active (blue) only after typing |

### Invitation Manager

`/mynetwork/invitation-manager/` — lists received/sent invitations.

| Element | CSS (x, y) | Notes |
|---------|-----------|-------|
| "Accept" button (first invite) | (~920, 274) | Approximate — verify via screenshot |
| "Ignore" button (first invite) | (~838, 274) | Next to Accept |
| "Received" / "Sent" tabs | (~265, 142) / (~350, 142) | Top of page |

### Search Results

| Element | CSS (x, y) | Notes |
|---------|-----------|-------|
| First result name | (~305, 155) | Approximate — **always verify via screenshot** |
| Second result name | (~305, 280) | Approximate — positions shift with ads/banners |

## Architecture

```
LinkedInBot (linkedin_cdp.py)  -- base class
   |-- CDP core: connect(), _send(), close(), reconnect_to_tab()
   |-- Mouse: _bezier(), _human_path(), _move_to(), _click(), _maybe_fake_hover()
   |-- Keyboard: type_text(), press_key()
   |-- Scroll: scroll_wheel()
   |-- Screenshot: take_screenshot() -> path, take_screenshot_base64(), save_screenshot()
   |-- Navigation: navigate_to(), wait_for_page()
   |-- Convenience: click_at(x,y) -> screenshot, scroll_and_screenshot()
   |
   +-- LinkedInMessages   (linkedin_messages.py)
   +-- LinkedInSearch      (linkedin_search.py)
   +-- LinkedInProfile     (linkedin_profile.py)
   +-- LinkedInConnect     (linkedin_connect.py)
```

## Modules

| File | Class | Key Methods |
|------|-------|-------------|
| `linkedin_cdp.py` | `LinkedInBot` | `click_at()`, `type_text()`, `scroll_wheel()`, `take_screenshot()` -> path, `take_screenshot_base64()`, `navigate_to()` |
| `linkedin_messages.py` | `LinkedInMessages` | `screenshot_conversations()`, `open_conversation()`, `send_message()`, `collect_screenshots()` |
| `linkedin_search.py` | `LinkedInSearch` | `search_people()`, `search_companies()`, `next_page()` |
| `linkedin_profile.py` | `LinkedInProfile` | `view_profile()`, `screenshot_full_profile()`, `scroll_to_section()` |
| `linkedin_connect.py` | `LinkedInConnect` | `view_profile()`, `send_connection_note()`, `screenshot_invitations()`, `accept_invitation()` |
| `rate_limiter.py` | `RateLimiter` | `can_search()`, `can_view_profile()`, `wait_if_needed()` |

## Examples

### Search → Profile → Connect with Note (full flow)

```python
import sys, time
sys.path.insert(0, '$HOME/linkedin-cdp')
from linkedin_cdp import LinkedInBot

bot = LinkedInBot()
bot.connect()

# 1. Search
bot.navigate_to('https://www.linkedin.com/search/results/people/?keywords=Name%20Company')
time.sleep(4)
bot.reconnect_to_tab()
time.sleep(2)
# take_screenshot() returns file path — read with Read tool to find coordinates

# 2. Click profile (coordinates from screenshot / DPR)
path = bot.click_at(305, 155)  # first result — verify from screenshot!
time.sleep(4)
bot.reconnect_to_tab()
# Read path with Read tool to verify correct profile

# 3. Click Connect (~270, 467-499 — verify from screenshot)
bot.click_at(270, 499)
time.sleep(2)
# Modal appears

# 4. Click "Add a note" (fixed coordinate)
bot.click_at(751, 239)
time.sleep(1.5)

# 5. Click text field + type note
bot._click(752, 259)
time.sleep(0.5)
bot.type_text("Hi Name, personalized note here...")
time.sleep(1)

# 6. Click Send (fixed coordinate)
bot.click_at(968, 393)
# Done — verify "Pending" status + "Invitation sent" toast

bot.close()
```

### Read Messages

```python
from linkedin_messages import LinkedInMessages
lm = LinkedInMessages()
lm.connect()

path = lm.screenshot_conversations()
# path = '/tmp/li_screenshots/shot_NNNN.jpg' — read with Read tool

path = lm.open_conversation(200, 350)  # coordinates from screenshot
# Read path with Read tool

lm.close()
```

### View Profile (manual scroll)

```python
import time
from linkedin_profile import LinkedInProfile

prof = LinkedInProfile()
prof.connect()
prof.navigate_to('https://linkedin.com/in/username')
time.sleep(4)
prof.reconnect_to_tab()

paths = [prof.take_screenshot()]
for _ in range(4):
    prof.scroll_wheel(delta_y=500)
    time.sleep(1.5)
    paths.append(prof.take_screenshot())
# paths = ['/tmp/li_screenshots/shot_0001.jpg', ...] — read each with Read tool
prof.close()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `WebSocketConnectionClosedException` after navigate | Call `reconnect_to_tab()` — page change breaks WebSocket |
| Click misses target | Verify DPR: `image_pixels / DPR = CSS coords`. Re-run calibration. |
| `screenshot_full_profile()` crashes | Use manual navigate + reconnect + scroll loop (see View Profile example) |
| `scroll_wheel()` TypeError | Use keyword arg only: `scroll_wheel(delta_y=500)`, NOT positional args |
| Chrome opens tab in existing browser | Use binary path directly, NOT `open -a 'Google Chrome'` |
| CDP port conflict | Change `--remote-debugging-port=9223` and update `CDP_PORT` in `linkedin_cdp.py` |
| Modal coordinates wrong | Window resized? Re-run calibration. Fixed coords assume viewport ~1531x801. |

## Practical Tips

1. **LinkedIn URLs from web research are often wrong.** Always search by name + company.
2. **`scroll_wheel()` takes `delta_y` keyword arg only.** Not positional.
3. **After any `navigate_to()` or page-changing click, always `reconnect_to_tab()`.**
4. **Always `sys.path.insert(0, '$HOME/linkedin-cdp')`** before imports.
5. **Screenshots auto-save to `/tmp/li_screenshots/shot_*.jpg`** — read them with Read tool. Old files auto-cleaned (keeps last 50).
6. **One module instance at a time.** Close previous before opening new.
7. **Calibrate DPR on first run.** Don't assume DPR=2 — verify.
8. **No em-dashes in messages.** Never use long dashes (--) in connection notes or messages. People recognize it as AI-generated text. Use commas, periods, or short sentences instead.

## Rate Limits (recommended daily)

| Action | Conservative | Moderate |
|--------|-------------|----------|
| Profile views | 50 | 100 |
| Searches | 20 | 50 |
| Connection requests | 15 | 25 |
| Messages sent | 30 | 50 |

## Security Model

**Zero DOM access** — NEVER `Runtime.evaluate`, `querySelector`, `innerText`.
**Screenshot-based reading** — `Page.captureScreenshot` (JPEG, quality 80) saved to files, not base64 in memory.
**Human-like mouse** — unique Bezier curves, tremor, overshoot, micro-pauses, speed variation.
**Real Chrome** — not headless. Normal fingerprint.
**Rate limiting** — built-in daily caps.
**Human-in-the-loop** — Claude reads screenshots, adds natural irregularity.

### NEVER do

- **NEVER use `Runtime.evaluate`** or CDP Runtime domain — #1 way bots get caught
- **NEVER bypass rate limits** — even if asked to "go faster"
- **NEVER run headless** — always visible Chrome window
- **NEVER automate login** — user logs in manually

## Post-outreach CRM logging (REQUIRED)

After sending a connection request or message, ALWAYS log to CRM:

1. **Company** in `companies.csv` (if new)
2. **Person** in `people.csv` (if new)
3. **Lead** in `leads.csv` (stage=new, source=linkedin, source_direction=outbound)
4. **Activity** in `activities.csv` with the **exact message text** in `notes` field:
   - `type`: outreach
   - `channel`: linkedin
   - `direction`: outbound
   - `subject`: "LinkedIn connection request with note" (or "LinkedIn message")
   - `notes`: the full text of the message sent

Do NOT skip step 4. The message text must be preserved in CRM for follow-up context.

## Related skills

- `add-lead` — add found contacts to CRM
- `update-lead` — update lead status after outreach
- `log-activity` — log activity to activities.csv
- `email-send-bulk` — follow up via email after LinkedIn connect
