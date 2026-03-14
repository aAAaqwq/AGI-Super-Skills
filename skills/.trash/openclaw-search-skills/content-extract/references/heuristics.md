# Extraction heuristics (probe → fallback)

This file defines **when to accept web_fetch output** vs **when to fallback to MinerU**.

## Accept web_fetch when

- HTTP status is 200 and extracted markdown has meaningful body content.
- Content length is not trivially small (rule of thumb: > 2k chars for articles; adjust by site).
- Does NOT look like a captcha/interstitial page.

## Force fallback to MinerU (MinerU-HTML) when

### Domain whitelist (skip probe)

If URL host matches the whitelist in `domain-whitelist.md`, **skip probe** and go straight to MinerU.

See: `references/domain-whitelist.md`

### Obvious interstitial / anti-bot patterns

If web_fetch markdown contains any of:
- "环境异常"
- "完成验证"
- "拖动下方滑块"
- "验证码"
- "请在微信客户端打开"
- "访问过于频繁"

### Content too thin / nav-only

- Content length < 800 chars and URL is expected to be an article.
- Extracted text is mostly navigation items / footer.

### fetch failure

- web_fetch returns 401/403/429/5xx.
- web_fetch times out repeatedly.

## MinerU failure fallback (future)

If MinerU fails to fetch protected pages:
- Ask for a mirror URL, OR
- Use browser relay to export HTML, then add "upload HTML then parse" flow.

(Upload flow is not implemented yet in OpenClaw A-route.)
