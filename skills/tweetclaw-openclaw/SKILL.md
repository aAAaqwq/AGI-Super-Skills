---
name: tweetclaw-openclaw
description: >
  Use TweetClaw from OpenClaw for X/Twitter automation: tweet search, reply
  search, follower export, user lookup, monitors, webhooks, giveaway draws,
  media workflows, and approval-gated posting. Requires local Xquik
  configuration. Never ask for X login material.
metadata:
  version: 1.0.0
  category: Marketing
  source: https://github.com/Xquik-dev/tweetclaw
---

# TweetClaw OpenClaw

Use TweetClaw when an OpenClaw agent needs structured X/Twitter data or
approval-gated X/Twitter actions through the Xquik API.

## When to Use

- Search tweets by keyword, hashtag, account, or advanced query.
- Search tweet replies, quote tweets, retweeters, and favoriters.
- Export followers, following, verified followers, list members, or search results.
- Look up users, profile tweets, timelines, bookmarks, notifications, or trends.
- Upload or download media through authenticated Xquik workflows.
- Create monitors, webhooks, giveaway draws, or extraction jobs after user approval.
- Post tweets, post tweet replies, like, retweet, follow, DM, or update profiles only after explicit confirmation.

## Setup

Install the OpenClaw plugin:

```bash
openclaw plugins install @xquik/tweetclaw
```

Configure a local Xquik API key for account-backed workflows:

```bash
openclaw config set plugins.entries.tweetclaw.config.apiKey "$XQUIK_API_KEY"
```

For accountless read-only MPP mode, configure a local signing key instead:

```bash
openclaw config set plugins.entries.tweetclaw.config.tempoSigningKey "$MPP_SIGNING_KEY"
```

Allow the TweetClaw tools when the active OpenClaw tool profile excludes
external plugin tools:

```bash
openclaw config set tools.alsoAllow '["explore", "tweetclaw"]'
```

## Safety Rules

- Keep API keys, signing keys, cookies, and account credentials out of prompts and committed files.
- Use `explore` first to find the exact endpoint, parameters, response shape, cost, and MPP eligibility.
- Before any visible, paid, bulk, private, recurring, or state-changing action, summarize the account, target, action, text or media, limit, and estimated credits.
- Wait for explicit user confirmation before posting, replying, deleting, liking, retweeting, following, sending DMs, uploading media, creating monitors, creating webhooks, running draws, or starting extraction jobs.
- MPP mode is read-only. Do not use it for writes, monitors, webhooks, media downloads, private account data, extraction jobs, draws, billing, or support actions.
- Do not ask the user for X login material. Send account connection, API-key creation, billing, and credit top-up tasks to the Xquik dashboard.

## Examples

Search tweets:

```text
User: Search recent tweets about AI agents.
Agent: Use explore to find /api/v1/x/tweets/search, then call tweetclaw with the query and limit.
```

Export followers:

```text
User: Export the followers for @example.
Agent: Confirm the target account and export limit, then call the follower extraction endpoint.
```

Post a reply:

```text
User: Reply to this tweet with the launch note.
Agent: Draft the exact reply text, show the target tweet and connected account, then wait for explicit approval before sending.
```

## References

- TweetClaw GitHub: https://github.com/Xquik-dev/tweetclaw
- npm package: https://www.npmjs.com/package/@xquik/tweetclaw
- ClawHub listing: https://clawhub.ai/kriptoburak/xquik-tweetclaw
