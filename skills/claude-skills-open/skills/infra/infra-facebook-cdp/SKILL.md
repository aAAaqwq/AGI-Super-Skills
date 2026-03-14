---
name: infra-facebook-cdp
description: Facebook CDP automation: comments, data collection
---
# Skill: Facebook CDP Automation

**ID:** `infra-facebook-cdp`
**Domain:** infra
**Repo:** https://github.com/your-org/your-facebook-cdp (private)

---

## Description

Facebook automation via Chrome DevTools Protocol. Comment collection, replying to comments, CSV export.

---

## Path

```
$HOME/facebook-cdp/
```

---

## Capabilities

1. **Comment collection** -- all comments from a post including nested replies
2. **Reply to comments** -- reply to a specific comment by author name
3. **CSV export** -- saving collected comments

---

## Usage

### 1. Launch Chrome with remote debugging

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    '--remote-allow-origins=*'
```

### 2. Log in to Facebook manually

### 3. Collect comments

```python
from facebook_comments import collect_post_comments

comments = collect_post_comments(
    "https://www.facebook.com/post/123",
    output_file="comments.csv"
)
```

### 4. Reply to a comment

```python
from facebook_comments import FacebookComments

fb = FacebookComments()
fb.connect()
fb.reply_to_comment("Author Name", "Reply text")
fb.close()
```

---

## Comment data structure

```python
{
    "author_name": "Author name",
    "author_profile_url": "https://facebook.com/...",
    "comment_text": "Comment text",
    "is_reply": False,  # True if this is a reply
    "timestamp": "Feb 6, 2026"
}
```

---

## Dependencies

- Python 3.8+
- `requests`, `websocket-client`
- Chrome with remote debugging

---

## Related skills

- `linkedin-cdp` -- similar tool for LinkedIn
