# Google Deep Research 3 — Paid Ad Technical Specifications

> Source: Google Deep Research PDF, "Paid Ad Technical Specifications Request", February 2026
> 20 pages — Complete creative specs, safe zones, character limits, encoding requirements

---

## Google Ads Specifications

### Responsive Search Ads (RSA)

| Component | Limit | Notes |
|-----------|-------|-------|
| Headlines | 3-15 per RSA | Minimum 3, recommended 12-15 for "Excellent" Ad Strength |
| Headline length | 30 characters | Including spaces |
| Descriptions | 2-4 per RSA | Minimum 2, recommended 4 |
| Description length | 90 characters | Including spaces |
| Display URL paths | 2 paths, 15 chars each | Auto-populated from final URL |
| Final URL | Required | Must match landing page |

**Pinning Strategy:**
- Pin 1 headline to Position 1 (brand/main keyword)
- Pin 1 headline to Position 2 (secondary angle)
- Leave Position 3 unpinned for algorithm testing
- Never pin all positions (kills Ad Strength)
- Each pinned position should have 2-3 variants

**Dynamic Insertion Syntax:**
```
{KeyWord:Default Text}          // Keyword insertion (capitalizes each word)
{keyword:default text}          // lowercase
{KEYWORD:DEFAULT TEXT}           // UPPERCASE
{Keyword:Default}               // Sentence case

{COUNTDOWN(2026/03/31 00:00:00, "en-US", 3)}  // Countdown timer
{LOCATION(City)}                               // Location insertion
{CUSTOMIZER.attribute:default}                 // Ad customizer
```

### Performance Max Asset Groups

| Asset Type | Specs | Max Per Group |
|-----------|-------|---------------|
| Marketing Image | 1200×628 (1.91:1) | 20 images total |
| Square Image | 1200×1200 (1:1) | (included in 20) |
| Portrait Image | 960×1200 (4:5) | (included in 20) |
| Logo (landscape) | 1200×300 (4:1) | 5 logos total |
| Logo (square) | 1200×1200 (1:1) | (included in 5) |
| Video (landscape) | 1920×1080 (16:9) | 5 videos total |
| Video (square) | 1080×1080 (1:1) | (included in 5) |
| Video (vertical) | 1080×1920 (9:16) | 5 vertical videos |
| Headlines | 30 chars | 5 headlines |
| Long Headlines | 90 chars | 5 long headlines |
| Descriptions | 90 chars | 5 descriptions |
| Short Description | 60 chars | 1 |
| Business Name | 25 chars | 1 |
| Call to Action | Predefined list | 1 |
| Final URL | Required | 1 per group |

**Image Requirements:**
- Minimum file size: 128×128 (will be upscaled, not recommended)
- Maximum file size: 5120×5120
- Max file weight: 5 MB
- Formats: JPG, PNG
- No text overlays > 20% of image area (recommendation, not hard rule)

**Video Requirements:**
- Minimum duration: 10 seconds
- Maximum duration: No hard limit (60s recommended for most)
- Minimum resolution: 480p
- Recommended: 1080p or higher
- Format: MP4, MOV
- Max file size: 256 MB

### YouTube Ad Specifications

| Format | Aspect Ratio | Min Resolution | Duration | Skip |
|--------|-------------|---------------|----------|------|
| Skippable In-Stream | 16:9 | 1920×1080 | 12s-3min (rec: 15-30s) | After 5s |
| Non-Skippable In-Stream | 16:9 | 1920×1080 | 15-20s (max 30s) | No |
| Bumper | 16:9 | 1920×1080 | ≤6s | No |
| In-Feed (Discovery) | 16:9 | 1920×1080 | Any | N/A (click to play) |
| YouTube Shorts | 9:16 | 1080×1920 | ≤60s | Swipe |

**YouTube Shorts Safe Zones:**
```
┌──────────────────────┐
│                      │  ← Top: Profile/search (0-80px)
│                      │
│   ╔══════════════╗   │
│   ║              ║   │
│   ║  SAFE ZONE   ║   │  ← Center: 1080×1420px
│   ║  (content)   ║   │     (primary visible area)
│   ║              ║   │
│   ╚══════════════╝   │
│                      │
│ ████████████████████ │  ← Bottom 25% (480px): UI overlay
│ ████████████████████ │     (like, comment, share, music)
└──────────────────────┘
```
- Bottom 480px = reserved for TikTok-style UI elements
- Right side: Action buttons overlay
- Keep all critical content in center 1080×1420px area

### Google Ads Extensions / Assets

| Extension Type | Character Limits | Max Count | Notes |
|---------------|-----------------|-----------|-------|
| Sitelink | Link text: 25 chars, Desc: 35 chars ×2 | 20 per campaign | Min 4 recommended |
| Callout | 25 characters | 20 per campaign | Min 4 recommended |
| Structured Snippet | Header: predefined, Value: 25 chars | 2 per campaign | Choose relevant header |
| Image | 1:1 (1200×1200) or 1.91:1 (1200×628) | 20 per campaign | Min 1MB, PNG/JPG |
| Call | Phone number | 1 per campaign | With call tracking |
| Lead Form | Headline: 30 chars, Desc: 200 chars | 1 per campaign | Privacy policy URL required |
| Price | Header: 25 chars, Desc: 25 chars | 8 items | Min 3 items |
| Promotion | Item: 20 chars | 1 per campaign | Can schedule dates |
| Location | Business Profile linked | N/A | Requires GMB |

### Ad Strength Scoring Logic

Google calculates Ad Strength for RSAs based on:

1. **Headline uniqueness** — Measured via Levenshtein distance between headlines
   - Headlines too similar to each other = penalty
   - Each headline should take a different angle/value prop

2. **Keyword inclusion** — Headlines should contain primary keywords from ad group
   - At least 2-3 headlines should include exact/close keyword variants

3. **Headline count** — More unique headlines = better
   - 3-7 headlines = Poor to Average
   - 8-10 headlines = Good
   - 11-15 headlines = Excellent potential

4. **Description variety** — Different selling points in each description

5. **Performance correlation:**
   - "Excellent" Ad Strength RSAs show ~12% higher conversion rate vs "Poor"
   - Not a guarantee — test "Good" vs "Excellent" for your account

---

## Meta Ads Specifications

### Image Specifications

| Placement | Recommended Ratio | Recommended Size | Max File Size |
|-----------|------------------|-----------------|---------------|
| Feed | 4:5 (preferred) | 1080×1350 | 30 MB |
| Feed | 1:1 (supported) | 1080×1080 | 30 MB |
| Stories / Reels | 9:16 | 1080×1920 | 30 MB |
| Right Column | 1:1 | 1080×1080 | 30 MB |
| Marketplace | 1:1 | 1080×1080 | 30 MB |
| Search Results | 1:1 | 1080×1080 | 30 MB |

**Image Rules:**
- No explicit 20% text rule (removed) but AI still penalizes text-heavy images
- Recommended: Keep text to <20% of image area for best delivery
- Formats: JPG, PNG (PNG for graphics with text)
- Minimum width: 600px (1080px recommended)

### Video Specifications

| Placement | Aspect Ratio | Min Resolution | Max Duration | Max File Size |
|-----------|-------------|---------------|-------------|---------------|
| Feed | 4:5 (preferred) | 1080×1350 | 241 minutes | 4 GB |
| Feed | 1:1 | 1080×1080 | 241 minutes | 4 GB |
| Stories | 9:16 | 1080×1920 | 120 seconds | 4 GB |
| Reels | 9:16 | 1080×1920 | 90 seconds (rec: 15-30s) | 4 GB |
| In-Stream | 16:9 | 1920×1080 | 15 min | 4 GB |

**Reels Safe Zone:**
```
┌──────────────────────┐
│                      │  ← Top: Account name + caption preview
│                      │
│   ╔══════════════╗   │
│   ║              ║   │
│   ║  SAFE ZONE   ║   │  ← Center: 1080×1300px
│   ║  (content)   ║   │     (primary visible area)
│   ║              ║   │
│   ╚══════════════╝   │
│                      │
│ ████████████████████ │  ← Bottom 35% (~670px): CTA, caption,
│ ████████████████████ │     music, reactions overlay
│ ████████████████████ │
└──────────────────────┘
```

**Video Encoding:**
- Codec: H.264 (most compatible)
- Audio: AAC, 128kbps+, stereo
- Frame rate: 30fps (standard), 60fps (supported)
- Bitrate: 4Mbps+ for 1080p

### Carousel Specifications

| Component | Limit |
|-----------|-------|
| Cards | 2-10 per carousel |
| Card aspect ratio | 1:1 (all cards must match) |
| Card size | 1080×1080 |
| Primary Text | 125 characters (recommended, 2200 max) |
| Headline | 40 characters per card |
| Description | 20 characters per card |
| URL | 1 per card (can be different) |

### Collection & Instant Experience

| Component | Limit |
|-----------|-------|
| Cover image/video | 1200×628 (1.91:1) or video |
| Product images | 4 minimum, pulled from catalog |
| Headline | 40 characters |
| Instant Experience | Custom built — supports image, video, carousel, form |

### Advantage+ Creative Enhancements

When enabled, Meta may automatically:
- Adjust image brightness and contrast
- Apply art filters
- Crop images to different aspect ratios
- Add music to video ads
- Generate text variations
- Enhance video (templates from static images)

**Recommendation:** Test with A/B split — enable for 50% of budget, compare performance.

### Meta Ad Quality Ranking

Meta provides 3 quality signals in ad reporting:
1. **Quality Ranking** — Perceived quality vs competitors (Above/Below Average)
2. **Engagement Rate Ranking** — Expected engagement vs competitors
3. **Conversion Rate Ranking** — Expected conversion rate vs competitors

All ranked as: Above Average, Average, Below Average (10th, 35th, 55th percentile thresholds)

---

## TikTok Ads Specifications

### Video Specifications

| Ad Type | Min Resolution | Duration | Max File Size | Min Bitrate |
|---------|---------------|----------|---------------|-------------|
| Non-Spark In-Feed | 540×960 (9:16) | 5-60 seconds | 500 MB | 516 kbps |
| Spark Ads | Organic post specs | Organic post specs | N/A | N/A |
| TopView | 720×1280 (9:16) | 5-60 seconds | 500 MB | 2500 kbps |
| Brand Takeover | 720×1280 | 3-5 seconds | 2 MB (image), 500 MB (video) | — |

**Recommended:**
- Resolution: 1080×1920 (9:16)
- File format: MP4, MOV, MPEG, AVI
- Encoding: H.264
- Audio: Required (TikTok is sound-on platform)
- Subtitles/captions: Required (accessibility + silent viewers)

### TikTok Safe Zone

```
┌──────────────────────────┐
│ ████████████████████████ │ ← Top 0-150px: Status bar, account info
│                          │
│   ╔══════════════════╗   │
│   ║                  ║   │
│   ║   SAFE ZONE      ║   │
│   ║                  ║   │  ← X: 40-940px
│   ║   Key content    ║   │     Y: 150-1470px
│   ║   goes here      ║   │
│   ║                  ║   │
│   ╚══════════════════╝   │
│                       ██ │ ← Right 0-140px: Like, comment,
│                       ██ │    share, profile buttons
│ ████████████████████████ │ ← Bottom 0-450px: Caption, music,
│ ████████████████████████ │    CTA button, navigation bar
└──────────────────────────┘
```

**Effective Safe Box Dimensions:**
- X: 40px to 940px (900px wide)
- Y: 150px to 1470px (1320px tall)
- **All critical text, logos, CTAs must be within this box**

### Creative Quality Indicators

TikTok's algorithm scores creative quality based on:
1. **Completion rate** — % of users watching full video
2. **Replay rate** — Users watching more than once
3. **Engagement rate** — Likes, comments, shares relative to views
4. **Click-through rate** — Clicks to landing page
5. **Native feel** — Resemblance to organic content (not ads)

---

## LinkedIn Ads Specifications

### Single Image Ad

| Component | Limit | Notes |
|-----------|-------|-------|
| Image size | 1200×627 (1.91:1) | Recommended |
| Image size | 1080×1080 (1:1) | Supported, better for engagement |
| Max file size | 5 MB | PNG, JPG |
| Intro text | 150 chars (recommended) / 600 max | Truncated after ~150 on mobile |
| Headline | 70 chars (recommended) / 200 max | Truncated after ~70 on feed |
| Description | 100 chars | Below headline (desktop only) |
| CTA Button | Predefined list | Required |

### Video Ad

| Component | Limit | Notes |
|-----------|-------|-------|
| Aspect ratio | 16:9 (landscape), 1:1 (square), 9:16 (vertical - mobile only) |
| File format | MP4 | Required |
| File size | 75 KB - 500 MB | |
| Duration | 3 seconds - 30 minutes | Recommended: 15-30 seconds |
| Resolution | 360p minimum | 720p+ recommended |
| Frame rate | 30fps | Standard |
| Bitrate | >192 kbps | Higher = better quality |

### Document Ad (Carousel-like for PDFs)

| Component | Limit |
|-----------|-------|
| File format | PDF, DOC, DOCX, PPT, PPTX |
| File size | 100 MB max |
| Pages | 300 max (10-20 recommended) |
| Intro text | 150 chars recommended |

### Messaging Specs

| Component | Limit |
|-----------|-------|
| Message Ad: Subject | 60 characters |
| Message Ad: Body | 1,500 characters |
| Message Ad: CTA button | 20 characters |
| Conversation Ad: Intro | 500 characters |
| Conversation Ad: CTA buttons | 5 max, 25 chars each |

### Dynamic Ads

| Component | Limit |
|-----------|-------|
| Company name | 25 characters |
| Headline | 50 characters |
| Description | 70 characters |
| CTA | Predefined list |

### LinkedIn Quality Score

LinkedIn uses a CTR-focused quality score:
- Higher CTR relative to competitors = lower CPC
- Relevance score visible in campaign reporting
- Creative engagement (reactions, comments, shares) boost quality
- TLAs inherently score higher due to personal profile trust signals

---

## Microsoft Ads Specifications

### RSA (Responsive Search Ads)

Mirrors Google Ads RSA specs exactly:
| Component | Limit |
|-----------|-------|
| Headlines | 3-15, 30 chars each |
| Descriptions | 2-4, 90 chars each |
| Display paths | 2 paths, 15 chars each |
| Final URL | Required |

### Multimedia Ads (Unique to Microsoft)

| Component | Limit | Notes |
|-----------|-------|-------|
| Image | 1200×628 (1.91:1) | Required |
| Short headline | 30 characters | |
| Long headline | 90 characters | |
| Description | 90 characters | |
| Business name | 25 characters | |

### Extension Specs (Including Microsoft-Unique)

| Extension | Limit | Microsoft-Unique? |
|-----------|-------|-------------------|
| Sitelink | 25 chars link text, 35 chars desc ×2 | No |
| Callout | 25 characters | No |
| Structured Snippet | 25 chars per value | No |
| Image | 1:1 or 1.91:1 | No |
| Action Extension | Predefined actions | **Yes** |
| Filter Link Extension | Category-based deep links | **Yes** |
| Review Extension | Third-party review quote | **Yes** |
| Call | Phone number | No |
| Location | Business profile | No |
| Price | 25 chars header, 25 chars desc | No |
| Promotion | 20 chars item | No |

---

## Cross-Platform Validation Standards

### Universal Safe Zone (All Vertical Video)

For content that will run across TikTok, Reels, Shorts, and Stories:
```
Center safe box: 900×1000px
  X: 40-940px (900px wide)
  Y: 450-1450px (1000px tall)

This is the INTERSECTION of all platform safe zones.
Content placed here is guaranteed visible on ALL platforms.
```

### Character Normalization

For ad copy that will be adapted across platforms:

| Component | Safe Limit | Platform With Strictest Limit |
|-----------|-----------|------------------------------|
| Short headline | 30 characters | Google RSA, Microsoft RSA |
| Long headline | 70 characters | LinkedIn recommended |
| Primary description | 90 characters | Google RSA, Microsoft RSA |
| Short description | 25 characters | Extension callouts |

### File Encoding Standards

| Component | Recommended | Notes |
|-----------|-------------|-------|
| Video codec | H.264 High Profile | Most compatible across all platforms |
| Audio codec | AAC | Universal support |
| Audio level | -14 LUFS (normalized) | Consistent loudness across platforms |
| Container | MP4 | Universal support |
| Frame rate | 30fps | Standard (60fps supported but not needed) |
| Color space | Rec. 709 | Standard for web delivery |
| Bitrate (1080p) | 8-12 Mbps | Balance quality vs file size |
| Bitrate (4K) | 35-45 Mbps | If platform supports |

### Aspect Ratio Master Chart

| Ratio | Dimensions | Used By |
|-------|-----------|---------|
| 16:9 | 1920×1080 | YouTube, Google Display, LinkedIn Landscape |
| 9:16 | 1080×1920 | TikTok, Reels, Shorts, Stories |
| 4:5 | 1080×1350 | Meta Feed (preferred), Pinterest |
| 1:1 | 1080×1080 | Meta Feed, LinkedIn, Carousel |
| 1.91:1 | 1200×628 | Google PMax Marketing, LinkedIn Single Image |
| 4:1 | 1200×300 | Google Logo (landscape) |
