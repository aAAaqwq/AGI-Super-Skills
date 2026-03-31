---
name: brand-voice
description: "Enforce brand tone and style consistency across all content creation skills. Load brand profiles from workspace/brand/profiles/, apply tone rules (preferred and forbidden expressions), and validate written content against the selected voice. Use when the user mentions brand voice, tone consistency, style guide compliance, or needs to switch writing profiles via --voice."
author: 무펭이 🐧
---

# brand-voice

Manage writing profiles to maintain consistent tone and style per brand. Selectable via `--voice` option in all content creation skills.

## Brand Profiles

### 🐧 무펭이 (Default)
- **Tone**: Friendly and casual
- **Style**: Informal, emoji usage 🐧
- **Format**: Core points only, mix in humor
- **Examples**:
  - ❌ "Hello! Today I'll introduce MUFI Photobooth's new features."
  - ✅ "Yo MUFI Photobooth new feature dropped 🐧 This is insane fr"

### 🎯 MUFI Official
- **Tone**: Professional and polite
- **Style**: Formal language, formal expressions
- **Format**: Clean and clear, for B2B/official channels
- **Examples**:
  - ✅ "MUFI Photobooth is the optimal solution for university festivals. Easy setup and intuitive UI enable anyone to use it easily."

### 👤 Hyungnim Personal
- **Tone**: Casual but insightful
- **Style**: Mix casual/formal, experience-centered
- **Format**: Flow of thought, insights worth sharing
- **Examples**:
  - ✅ "Running booths at festivals, what I realized is that people ultimately want 'fun'. No matter how good the tech, if UX is complex, they won't use it."

## Profile File Location

**Location**: `workspace/brand/profiles/`

Each profile `.md` file defines: Tone, Style, Format, Forbidden Expressions, Preferred Expressions, and Examples. See existing profiles (`mupengyi.md`, `mufi-official.md`, `hyungnim.md`) for the expected structure.

## Writing Skill Integration

These skills support `--voice` option:

- **copywriting**: Caption/copy writing
- **cardnews**: Card news text
- **social-publisher**: SNS posts
- **mail**: Email writing
- **content-recycler**: Content recycling

### Usage Examples

```
"Write Insta caption --voice mufi-official"
→ Write in MUFI official tone

"Create card news --voice mupengyi"
→ Create in 무펭이 style

"Write Threads post in Hyungnim tone"
→ Use Hyungnim personal profile
```

## Profile Switching Guide

### Platform Recommendations
- **Instagram MUFI official account** → `mufi-official`
- **Instagram personal account** → `hyungnim`
- **Threads** → `mupengyi` (casual)
- **Discord/DM** → `mupengyi`
- **Official email** → `mufi-official`
- **Blog posts** → `hyungnim` (insight-focused)

### Situation Recommendations
- **Product introduction** → `mufi-official`
- **Daily sharing** → `mupengyi` or `hyungnim`
- **Customer service** → `mufi-official`
- **Community engagement** → `mupengyi`

## Workflow

1. **Determine profile** — resolve from `--voice` flag, or use platform defaults (see Profile Switching Guide above)
2. **Load profile** — read the matching `.md` from `workspace/brand/profiles/`
3. **Write content** — apply the profile's tone, style, format, and preferred expressions
4. **Validate** — check that no forbidden expressions appear and tone matches the target profile
5. **Flag mismatches** — warn if content drifts from the selected voice before finalizing

## Integration Notes

Keep the integration contract lightweight but explicit:

- **Pre-check** — before a writing skill runs, confirm the selected profile (or default) is known
- **Post-check** — after drafting, validate forbidden/preferred expressions and overall tone fit
- **Usage logging (optional)** — if the workspace tracks writing activity, record the selected voice/profile for later review

This skill does not require a specific hook engine or event bus implementation, but any automation around it should preserve the same pre-check → write → validate flow.

## Adding New Profiles

To create a new brand profile, add a `.md` file to `workspace/brand/profiles/` following the same structure (Tone, Style, Format, Forbidden Expressions, Preferred Expressions, Examples).

---

> 🐧 Built by **무펭이** — [Mupengism](https://github.com/mupeng) ecosystem skill
