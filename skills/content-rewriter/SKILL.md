---
name: content-rewriter
version: 1.0.0
description: "Cross-platform content repurposer. Takes one piece of content and rewrites it for multiple Chinese social media platforms, adapting tone, format, length, and style."
author: ai-agent-store
license: MIT
platforms:
  - openclaw
  - cursor
  - claude-code
  - codex-cli
tags:
  - content
  - repurpose
  - rewrite
  - social-media
  - chinese
price: 9
---

# Content Rewriter — 内容多平台改写器

Repurpose one piece of content across multiple platforms with native formatting.

## When to Activate

Trigger when the user mentions: 改写, rewrite, 转载, cross-post, 多平台分发, repurpose, 内容复用.

## Workflow

1. Accept original content + list of target platforms
2. Rewrite for each target platform independently

## Rewriting Rules

### → 小红书 (from any platform)
- Shorten to 300-800 characters
- Add emoji every 2-3 sentences
- Title: "number + keyword + emoji" format
- Short paragraphs (1-3 sentences each)
- Add 5-10 hashtags
- Tone: bestie sharing / personal experience

### → 知乎 (from any platform)
- Expand to 1000-2000 characters
- Add logical structure (thesis → evidence → conclusion)
- Include data citations and case studies
- Tone: professional but approachable
- Open with a direct answer to the core question

### → 公众号 (from any platform)
- 1500-3000 characters
- Add subtitles for sections
- Open with empathy (pain point / story)
- Close with elevation
- Tone: deep but readable

### → 抖音 Script (from any platform)
- Compress to 200-500 character oral script
- First 3 seconds must hook
- Conversational, avoid written language
- Mark pauses and tone shifts
- End with comment-driving CTA

## Output Format
Generate each platform version as a standalone, ready-to-publish piece. Label each with platform name and word count.

## Guidelines
- Rewriting ≠ translating — match platform-native voice
- Each version must be independently publishable
- Check platform-specific banned words
