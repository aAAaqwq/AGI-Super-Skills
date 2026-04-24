# Research: Automation, OpenClaw, ClawHub, and Gemini Integration

**Task #1789** — Research findings for integrating automation features, OpenClaw/ClawHub support, and Gemini API into the `redbook` CLI.

---

## 1. Reference Repo Analysis: `xiaohongshu-ops-skill`

**Repo:** [Xiangyu-CAS/xiaohongshu-ops-skill](https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill)

### Architecture

The reference skill is a **pure-SKILL.md skill** — no npm package, no compiled code. It relies entirely on:

- **Browser automation** via OpenClaw's built-in CDP (Chrome DevTools Protocol) agent
- **Persona-driven replies** defined in `persona.md`
- **Reference docs** for SOPs (publish flows, comment strategies)

```
xiaohongshu-ops-skill/
├── SKILL.md              # Core logic, SOPs, execution rules
├── persona.md            # Account voice, tone, reply style
├── examples/             # Scenario-specific implementations
│   ├── drama-watch/case.md
│   └── reply-examples.md
├── references/           # Operational playbooks
│   ├── xhs-comment-ops.md
│   └── xhs-publish-flows.md
└── README.md
```

### Key Differentiators from `redbook`

| Aspect | `xiaohongshu-ops-skill` | `redbook` |
|--------|------------------------|-----------|
| **Execution** | Browser automation (CDP) | API-based CLI |
| **Authentication** | QR code login, session persists | Cookie extraction from browser |
| **Cover images** | Gemini API generation | `render` command (markdown→PNG) |
| **Comment replies** | AI-generated via persona | Template-based batch reply |
| **Publishing** | Browser automation (reliable) | API (captcha-prone) |
| **Distribution** | ClawHub only | npm + ClawHub |
| **Dependencies** | None (pure text skill) | Node.js ≥ 22, npm packages |

### What We Can Learn

1. **Persona system** — Their `persona.md` approach is elegant. We could add a `--persona <file>` option to `batch-reply` that uses an LLM to generate contextual replies instead of templates.
2. **Browser automation for publishing** — Their CDP approach avoids the captcha issues we face with the API. However, this requires OpenClaw's browser agent, not something we can replicate in a CLI.
3. **Modular reference docs** — Their `references/` directory pattern is useful for teaching the skill complex workflows.

---

## 2. OpenClaw / ClawHub Ecosystem

### How Skills Work

Skills are **text-based instruction bundles** centered around a `SKILL.md` file. OpenClaw loads them and uses the instructions to guide its agent. Skills can:

- Declare required CLI binaries (`requires.bins`)
- Declare required environment variables (`requires.env`)
- Specify installation steps for dependencies (`install` block)
- Restrict to specific OSes (`os`)

### SKILL.md Frontmatter Specification

```yaml
---
name: redbook                           # Skill identifier (slug)
description: "Description here"         # Summary for UI/search
version: 0.2.0                         # Semver
allowed-tools: Bash, Read, Write       # Claude Code tool restrictions
metadata:
  openclaw:
    requires:
      bins:                             # ALL must be on PATH
        - redbook
      env:                              # ALL must be set
        - SOME_API_KEY
      anyBins:                          # At least ONE must exist
        - python
        - python3
      config:                           # Config files the skill reads
        - ~/.config/redbook/config.json
    primaryEnv: SOME_API_KEY            # Main credential env var
    install:
      - kind: node                      # brew | node | go | uv
        package: "@lucasygu/redbook"
        bins: [redbook]
    os: [macos]                         # OS restrictions
    homepage: https://github.com/lucasygu/redbook
    emoji: "📕"
    always: false                       # If true, always active
    skillKey: redbook                   # Override invocation key
tags:
  - xiaohongshu
  - social-media
---
```

### Current `redbook` SKILL.md Status

Our SKILL.md already has correct ClawHub metadata:

```yaml
metadata:
  openclaw:
    requires:
      bins:
        - redbook
    install:
      - kind: node
        package: "@lucasygu/redbook"
        bins: [redbook]
    os: [macos]
    homepage: https://github.com/lucasygu/redbook
```

**What's missing:**
- `emoji` field (cosmetic)
- `requires.env` if we add Gemini API support
- `primaryEnv` for the main API key

### ClawHub Publishing

Publishing happens via CI (already set up in `.github/workflows/npm-publish.yml`):

```bash
clawhub login --token "$CLAWHUB_TOKEN" --no-browser
clawhub publish . --slug redbook --name "redbook" --version "$SKILL_VERSION"
```

The workflow triggers when `SKILL.md` changes on push to main.

### CLI → Skill Invocation Relationship

```
┌──────────────────────────────────────────────┐
│  User (in Claude Code / OpenClaw)            │
│  "Analyze this XHS creator's account"        │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  SKILL.md (loaded by agent)                  │
│  - Reads instructions & analysis modules     │
│  - Knows which `redbook` CLI commands to use │
│  - Has allowed-tools: Bash, Read, Write      │
└──────────────┬───────────────────────────────┘
               │  (dispatches via Bash tool)
               ▼
┌──────────────────────────────────────────────┐
│  `redbook` CLI binary (npm package)          │
│  - redbook search "keyword" --json           │
│  - redbook analyze-viral <url> --json        │
│  - redbook batch-reply <url> --dry-run --json│
└──────────────────────────────────────────────┘
```

The Skill (SKILL.md) is the **brain** — it knows the analysis modules, workflows, and how to interpret results. The CLI is the **hands** — it executes the actual API calls. They are complementary:

- **SKILL.md** tells the agent *what to do and why*
- **CLI binary** does the *how* (API calls, cookie management, signing)
- The agent uses `Bash` tool to invoke CLI commands and parses `--json` output

This is the correct architecture for a CLI-based skill. The reference repo (`xiaohongshu-ops-skill`) takes a different approach — it uses browser automation directly, with no CLI layer.

---

## 3. Gemini API Integration Assessment

### What the Reference Repo Does

The `xiaohongshu-ops-skill` uses Gemini (specifically "Nano Banana" / Gemini 3 Pro Image Preview) for **cover image generation**. The flow:

1. User provides a topic/content
2. Skill generates a prompt for cover image
3. Gemini API generates a 2048×2048 image
4. Browser automation uploads the image to XHS

### Current Gemini API Capabilities

| Model | Resolution | Free Tier | Best For |
|-------|-----------|-----------|----------|
| `gemini-3.1-flash-image-preview` | Up to 4K | ~500 req/day | Fast generation |
| `gemini-3-pro-image-preview` | Up to 4K | Limited | Higher quality |
| Nano Banana 2 | Up to 4K | Via Gemini app | Best text rendering |

**API call (TypeScript):**
```typescript
import { GoogleGenAI } from "@google/genai";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
const response = await ai.models.generateContent({
  model: "gemini-3.1-flash-image-preview",
  contents: "Generate a Xiaohongshu cover image for: [topic]",
  config: {
    responseModalities: ["TEXT", "IMAGE"],
    imageConfig: { aspectRatio: "1:1", imageSize: "2K" }
  }
});
// Image returned as base64-encoded PNG in response parts
```

### Should We Integrate Gemini?

**Recommendation: Yes, but as an optional enhancement (Phase 2)**

| Pro | Con |
|-----|-----|
| Free tier (500 req/day) covers casual use | Adds a dependency (`@google/genai`) |
| Chinese text rendering is strong in Nano Banana | Requires `GEMINI_API_KEY` setup |
| Complements existing `render` command | Publishing via API still triggers captcha |
| Reference repo validates the approach | Image style preferences are subjective |

**Proposed integration path:**

1. **New command: `redbook generate-cover`**
   - Input: topic, style keywords, optional reference image
   - Output: PNG file saved locally
   - Uses Gemini API for generation
   - Requires `GEMINI_API_KEY` env var

2. **Enhance `redbook post` workflow:**
   - If `--generate-cover` flag is set, auto-generate cover before publishing
   - Still use local image files as fallback

3. **SKILL.md updates:**
   ```yaml
   metadata:
     openclaw:
       requires:
         env:
           - GEMINI_API_KEY    # Optional, for cover generation
       primaryEnv: GEMINI_API_KEY
   ```

4. **New Module L: AI Cover Generation**
   - Composable with Module J (Viral Replication) and Module H (Content Brainstorm)
   - Extracts visual style from viral notes → generates matching covers

---

## 4. Automation Feature Recommendations

### Near-term (can build now)

| Feature | Approach | Effort |
|---------|----------|--------|
| **Persona-based replies** | `--persona <file>` for batch-reply, LLM generates replies | Medium |
| **Scheduled monitoring** | `redbook monitor <noteUrl>` — polls for new comments | Low |
| **Content calendar** | Module L in SKILL.md — workflow for daily content planning | Low (docs only) |

### Medium-term (needs more research)

| Feature | Approach | Blocker |
|---------|----------|---------|
| **Gemini cover generation** | `redbook generate-cover` command | Needs `@google/genai` dep |
| **Auto-publish pipeline** | generate cover → compose post → publish | Captcha on publish API |
| **Comment sentiment analysis** | Classify comments before replying | Needs LLM API |

### Not recommended (yet)

| Feature | Why Not |
|---------|---------|
| **Browser automation** | Requires CDP setup, OpenClaw-specific. Our CLI approach is more portable. |
| **Like/collect/follow automation** | Heavy anti-automation enforcement on XHS. High ban risk. |
| **DM automation** | Not supported by any known API approach. |

---

## 5. Action Items

### Immediate (this PR)
- [x] Research completed and documented

### Next Steps
1. **Add `emoji` field** to SKILL.md frontmatter (`📕` or `📗`)
2. **Add persona-based reply** — extend `batch-reply` with `--persona <file>` option
3. **Add Gemini cover generation** — new `generate-cover` command with optional `@google/genai` dep
4. **Add Module L** to SKILL.md — AI Cover Generation analysis module
5. **Update SKILL.md metadata** — add `requires.env` for `GEMINI_API_KEY` (optional)
6. **Add `redbook monitor`** — simple comment monitoring loop with configurable interval

---

## Sources

- [Xiangyu-CAS/xiaohongshu-ops-skill](https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill) — Reference skill repo
- [ClawHub Skill Format](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md) — SKILL.md specification
- [OpenClaw Skills Docs](https://docs.openclaw.ai/tools/skills) — How skills work
- [ClawHub Registry](https://github.com/openclaw/clawhub) — Skill registry README
- [Gemini Image Generation API](https://ai.google.dev/gemini-api/docs/image-generation) — Nano Banana / Gemini 3.1 Flash Image
- [RedInk + Nano Banana Integration](https://help.apiyi.com/en/redink-nano-banana-pro-integration-tutorial-en.html) — XHS cover generation case study
- [OpenClaw Skills Guide](https://openclawpulse.com/openclaw-skills-guide/) — Installation and usage
