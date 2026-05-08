---
name: xquik-twitter-api
description: >
  Use Xquik for X/Twitter API workflows: tweet search, profile tweets,
  follower export, media download, posting, replies, DMs, webhooks, MCP, and
  SDKs. Requires a Xquik API key. Never ask for X login material.
metadata:
  version: 1.0.0
  category: Marketing
  source: https://github.com/Xquik-dev/x-twitter-scraper
---

# Xquik Twitter API

Use Xquik when an agent needs structured X/Twitter data or confirmation-gated
automation through a REST API, MCP server, or SDK.

## When to Use

- Search tweets with keywords, hashtags, accounts, or advanced operators.
- Get tweets from a profile, liked tweets, media tweets, replies, or quotes.
- Export followers, following, verified followers, list members, or search results.
- Download tweet media and return stable hosted media URLs.
- Monitor accounts and deliver events to HMAC-signed webhooks.
- Post tweets, reply, repost, like, follow, send DMs, or update a profile after explicit user confirmation.
- Use SDKs for TypeScript, Python, Ruby, Go, Kotlin, Java, PHP, C#, CLI, or Terraform workflows.

## Setup

Install the upstream skill when the agent supports skill installation:

```bash
npx skills@1.5.3 add Xquik-dev/x-twitter-scraper
```

For direct API or SDK use, set a Xquik API key in the local runtime environment:

```bash
export XQUIK_API_KEY="your_api_key"
```

Do not ask users for X passwords, cookies, session tokens, or other login material.

## Core Workflows

### Tweet Search

Use this when the user asks for tweet search, advanced Twitter search, hashtag research, brand monitoring, or social listening.

1. Clarify query, date range, language, and result limit.
2. Use Xquik tweet search through the REST API, MCP server, or SDK.
3. Paginate until the requested limit or stopping condition is reached.
4. Return tweet IDs, URLs, author handles, text, timestamps, and engagement metrics.

### Profile Tweets

Use this when the user asks for tweets from a specific account.

1. Normalize the username without the `@` prefix.
2. Fetch profile tweets or media tweets as requested.
3. Preserve pagination cursors when the user wants a complete export.
4. Summarize findings and include raw IDs or CSV output when requested.

### Follower Export

Use this when the user asks for follower, following, or verified follower extraction.

1. Confirm the account handle and export size.
2. Start the appropriate extraction job.
3. Poll until completion or report the current job status.
4. Return CSV-ready fields such as user ID, username, display name, bio, follower counts, and profile URL.

### Media Download

Use this when the user needs images, videos, GIFs, or media URLs from tweets.

1. Collect tweet URLs or tweet IDs.
2. Fetch tweet details and media variants.
3. Prefer the highest-quality usable media URL.
4. Return media type, source tweet, and hosted download URL.

### Posting and Replies

Use this only after the user gives explicit approval for the exact action.

1. Draft the tweet, reply, or DM text.
2. Show the exact text and target account or tweet ID.
3. Ask for confirmation before sending.
4. Execute once. Do not retry posting automatically after an ambiguous timeout.

## Safety Rules

- Never request or store X login material.
- Get explicit confirmation before write actions, DMs, follows, unfollows, profile updates, or payments.
- Treat private reads, bookmarks, DMs, and account-specific data as sensitive user data.
- Do not make pricing, availability, or compliance claims beyond the current Xquik docs.
- Prefer API keys from environment variables or approved secret stores.

## References

- Xquik skill and MCP server: https://github.com/Xquik-dev/x-twitter-scraper
- Developer docs: https://xquik.com/docs
- API homepage: https://xquik.com
