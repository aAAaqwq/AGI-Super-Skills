---
name: zsxq-publisher
description: "Publish and manage content on 知识星球 (zsxq.com). Supports talk posts, Q&A, long articles, file sharing, digest/bookmark, homework tasks, and tag management. Use when publishing content to 知识星球, creating/editing posts (话题/问答/长文章/作业), uploading files/images/audio, managing digests/精华, batch publishing or scheduling posts, formatting content for 知识星球 (supports limited Markdown). Triggers: 知识星球, zsxq, 发帖, 星球, 精华帖, 星球发布."
---

# 知识星球智能发布

Publish content to 知识星球 via API or browser automation.

## Authentication

Requires a valid `zsxq_access_token` cookie. Get it by:

1. Open `https://wx.zsxq.com` in browser
2. Login via WeChat QR scan
3. Open DevTools → Application → Cookies → find `zsxq_access_token`
4. Set env var: `export ZSXQ_ACCESS_TOKEN="your_token"`
   Or store in config file (see `references/config.md`)

Token expires. Re-scan QR when API returns 401.

## Content Types

| Type | topic_type | API field | Char limit | Description |
|------|-----------|-----------|------------|-------------|
| 话题 (Talk) | `talk` | `type` | 50,000 chars | General post, text+images+files |
| 问答 (Q&A) | `q&a` | `type` | 50,000 chars | Question format, star-owner can answer |
| 作业 (Task) | `task` | `type` | 50,000 chars | Homework/assignment with deadline |
| 长文章 (Article) | — | separate endpoint | 100,000 chars | Web-only, rich editor, Markdown support |

**长文章 is web-only**: Publish via browser (`scripts/publish_article.py`), not the topics API.

## Quick Start

### 1. Publish a Talk Post

```bash
python3 scripts/publish.py --type talk \
  --group-id GROUP_ID \
  --text "Hello from AI agent!" \
  --tags "AI,自动化" \
  --image /path/to/image.png
```

### 2. Publish a Q&A

```bash
python3 scripts/publish.py --type qa \
  --group-id GROUP_ID \
  --text "如何使用API批量发帖？" \
  --tags "API,教程"
```

### 3. Publish a Task

```bash
python3 scripts/publish.py --type task \
  --group-id GROUP_ID \
  --text "完成本周阅读任务\n\n阅读《AI未来》第3-5章" \
  --deadline "2026-03-25 23:59"
```

### 4. Publish Long Article (browser required)

```bash
python3 scripts/publish_article.py \
  --group-url "https://wx.zsxq.com/group/GROUP_ID" \
  --title "AI Agent开发指南" \
  --text-file article.md \
  --image /path/to/cover.png
```

### 5. Upload Files/Images

```bash
python3 scripts/upload.py \
  --group-id GROUP_ID \
  --file /path/to/report.pdf \
  --text "本周研报"
```

## Publishing SOP

### Pre-publish Checklist

1. Check `ZSXQ_ACCESS_TOKEN` is valid: `python3 scripts/publish.py --check-auth`
2. Confirm `GROUP_ID` (get from URL: `wx.zsxq.com/group/{GROUP_ID}`)
3. Prepare content within character limits
4. Add relevant tags (max 3 tags per post)
5. Attach images if needed (JPG/PNG, recommended ≤ 5MB each, max 9 images)

### Post-publish

1. Verify post appears in group
2. Set as digest/精华 if needed (star-owner only, via API or browser)
3. Add to appropriate topic category

## API Reference

Base URL: `https://api.zsxq.com`

### Create Topic (Talk/Q&A/Task)

```
POST /v2/groups/{group_id}/topics
Content-Type: application/json
Cookie: zsxq_access_token={token}

{
  "req_data": {
    "topic": {
      "type": "talk|q&a|task",
      "title": "optional title",
      "text": "post content (supports limited Markdown)",
      "image_count": 1,
      "images": [{"file_size": 12345, "width": 800, "height": 600}],
      "file": {"file_key": "xxx"} // for file attachments
    },
    "task": {  // only for type=task
      "owner_user_id": 0,
      "dead_line": "2026-03-25 23:59"
    }
  }
}
```

### Upload Image

```
POST /v2/files/{group_id}/images
Content-Type: multipart/form-data
Cookie: zsxq_access_token={token}

file: (binary)
```

Returns: `{"resp_data": {"upload_key": "xxx", "width": 800, "height": 600}}`

### Upload File

```
POST /v2/files/{group_id}/files
Content-Type: multipart/form-data
Cookie: zsxq_access_token={token}

file: (binary)
```

Returns: `{"resp_data": {"file": {"file_key": "xxx", "name": "file.pdf"}}}`

### Get Topics List

```
GET /v1.10/groups/{group_id}/topics?scope=all&count=20
Cookie: zsxq_access_token={token}
```

`scope` options: `all|digests|questions|tasks`

### Set as Digest (精华)

```
POST /v2/topics/{topic_id}/digest
Cookie: zsxq_access_token={token}
```

### Get Group List (user's groups)

```
GET /v2/groups
Cookie: zsxq_access_token={token}
```

## Content Formatting

### Supported Markdown

- `**bold**`, `*italic*`
- `# heading` (long articles only)
- `` `code` ``, code blocks with ```
- Ordered/unordered lists
- Links: `[text](url)` (long articles only)
- Tables (long articles only)

### NOT Supported

- Image embedding via Markdown (use API upload)
- HTML tags
- Math formulas
- Mermaid diagrams

### Image Specs

- Formats: JPG, PNG, GIF
- Recommended size: ≤ 5MB per image
- Max images per post: 9
- Long articles: insert via editor, no limit on count

### File Specs

- Max file size: 200MB
- Supported: PDF, DOCX, XLSX, PPTX, ZIP, MP3, MP4
- Audio: MP3 recommended, max 30min

## Browser Publishing (for Long Articles)

Long articles cannot be created via API. Use `scripts/publish_article.py`:

1. Navigates to group page
2. Clicks "长文章" button
3. Fills title and content
4. Uploads cover image
5. Publishes

Requires Playwright: `pip install playwright && playwright install chromium`

## Templates

See `assets/` for content templates:
- `assets/talk-template.md` — Standard talk post
- `assets/qa-template.md` — Question format
- `assets/task-template.md` — Homework/assignment
- `assets/article-template.md` — Long article structure

## Error Handling

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| 401 | Token expired | Re-login, get new token |
| 403 | No permission | Check if user is group member/owner |
| 429 | Rate limited | Wait, retry after cooldown |
| 500 | Server error | Retry with exponential backoff |

## Reference

- Full API details: `references/api.md`
- Config guide: `references/config.md`
