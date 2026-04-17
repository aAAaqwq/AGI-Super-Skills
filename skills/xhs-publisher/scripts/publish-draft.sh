#!/bin/bash

# Unset proxy variables for CDP connection
unset ALL_PROXY all_proxy https_proxy http_proxy

# Publish to draft
python3 publish.py \
  --article "/home/aa/clawd/projects/MediaClaw/output/articles/2026-04-17/ai-life-buddy/xhs/article.md" \
  --cover "/home/aa/clawd/projects/MediaClaw/output/articles/2026-04-17/ai-life-buddy/xhs/cover-3x4.jpg" \
  --images "/home/aa/clawd/projects/MediaClaw/output/articles/2026-04-17/ai-life-buddy/素材/*.jpg" "/home/aa/clawd/projects/MediaClaw/output/articles/2026-04-17/ai-life-buddy/素材/*.png" \
  --decision draft