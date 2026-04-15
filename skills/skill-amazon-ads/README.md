# skill-amazon-ads-optimizer

> **OpenClaw Agent Skill** — Amazon Ads API v3 integration. List profiles, manage Sponsored Products campaigns, monitor budgets and performance — all from your AI agent.

---

## What It Does

| Script | What it does |
|--------|-------------|
| `ads.js` | List profiles, view all campaigns, get budget summary |

Automate your daily advertising operations:
- Pull live campaign status and budgets
- Identify active vs paused campaigns
- Export campaign data for analysis
- Feed into bid optimization workflows

---

## Quick Start

```bash
# 1. Create credentials file: amazon-ads-api.json
{
  "lwaClientId": "amzn1.application-oa2-client.YOUR_ADS_CLIENT_ID",
  "lwaClientSecret": "YOUR_ADS_SECRET",
  "refreshToken": "Atzr|YOUR_TOKEN",
  "profileId": "YOUR_ADS_PROFILE_ID",
  "region": "eu"
}

# 2. Get your profile ID
node scripts/ads.js --profiles

# 3. View all campaigns
node scripts/ads.js --campaigns

# 4. Get budget summary
node scripts/ads.js --summary
```

---

## Usage Examples

```bash
# List all advertiser profiles (run first to get your profileId)
node scripts/ads.js --profiles

# List all Sponsored Products campaigns
node scripts/ads.js --campaigns
node scripts/ads.js --campaigns --out campaigns.json

# Summary: active campaigns + total daily budget
node scripts/ads.js --summary
```

**Example output:**
```
📊 Amazon Ads Summary

Active campaigns : 3
Paused campaigns : 1
Total daily budget: 15.00

  [ENABLED] Manual | Exact | Product A — 5/day (MANUAL)
  [ENABLED] Manual | Phrase | Product B — 5/day (MANUAL)
  [ENABLED] Auto | Launch — 5/day (AUTO)
  [PAUSED]  Old Campaign — 0/day (MANUAL)
```

---

## API Endpoints by Region

| Region | Endpoint |
|--------|---------|
| North America | `advertising-api.amazon.com` |
| Europe / Middle East | `advertising-api-eu.amazon.com` |
| Far East | `advertising-api-fe.amazon.com` |

---

## Important Notes

- The Ads API uses a **separate LWA app** from SP-API — different Client ID/Secret
- You must set `profileId` in credentials (run `--profiles` to find yours)
- Tokens are fetched fresh per run — no stale token issues
- Requires `Advertising` permission scope on your LWA app

---

## Part of the Zero2AI Skill Library

Built and battle-tested in production. Part of a growing open-source library of AI agent skills for e-commerce automation.

- 🔗 [skill-amazon-spapi](https://github.com/Zero2Ai-hub/skill-amazon-spapi) — Orders, inventory & listings
- 🔗 [skill-amazon-listing-optimizer](https://github.com/Zero2Ai-hub/skill-amazon-listing-optimizer) — Image audit & fix

---

**Built by [Zero2AI](https://zeerotoai.com) · Published on [ClawHub](https://clawhub.ai)**
