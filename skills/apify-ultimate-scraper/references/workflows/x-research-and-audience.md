# X/Twitter research and audience workflows

Use these workflows for public tweets, profiles, relations, lists, and
communities. Never bypass private profiles or platform access controls.

## Actor selection

| Need | Actor |
|------|-------|
| Tweets, profiles, lists, threads, replies, quotes, or articles | [Xquik X Tweet Scraper](https://apify.com/xquik/x-tweet-scraper) |
| Followers, following, verified followers, list members, list followers, community members, or overlap | [Xquik X Follower Scraper](https://apify.com/xquik/x-follower-scraper) |

Use Actor IDs `xquik/x-tweet-scraper` and `xquik/x-follower-scraper`.

## Before every run

1. Fetch the current input schema:

       apify actors info "ACTOR_ID" --input --json 2>/dev/null

2. Fetch current pricing and deprecation status:

       apify actors info "ACTOR_ID" --json 2>/dev/null

3. Ask for targets and a result limit.
4. Set `maxItems` on every run.
5. Follow the cost confirmation rules in `../gotchas.md`.
6. Never put `APIFY_TOKEN` inside Actor input or output.

Do not hardcode pricing. The Actor listing and CLI response are authoritative.

## Tweet research

**When:** The user wants recent posts, mentions, profile timelines, lists,
threads, replies, quotes, articles, retweeters, or favoriters.

Start with search mode:

```json
{
  "mode": "search",
  "searchTerms": [
    "\"AI agents\" since:2026-01-01 until:2026-02-01",
    "from:openai since:2026-01-01 until:2026-02-01"
  ],
  "maxItems": 100,
  "outputVariant": "rich",
  "fieldStyle": "camelCase",
  "outputPreset": "nested",
  "includeSearchTerms": true,
  "queryType": "Latest + Top"
}
```

`maxItems` applies across all `searchTerms` in one run. Use separate runs when
each term needs its own guaranteed quota.

Choose a direct mode when the target is already known:

| Target | Mode |
|--------|------|
| One post or several post IDs | `tweet` or `tweets` |
| Profile timeline | `profileTweets` |
| Profile replies, media, or likes | `profileReplies`, `profileMedia`, or `profileLikes` |
| X list timeline | `listTweets` |
| Article, replies, quotes, or thread | `article`, `replies`, `quotes`, or `thread` |
| Users who reposted or liked a post | `retweeters` or `favoriters` |

Dataset rows may contain tweet data or diagnostic fields. A row with `status`
and `message` is not a tweet. Report it as an empty, invalid, aborted, or failed
target.

## Audience relations and overlap

**When:** The user wants public account relations or overlapping audiences.

For overlap across follower lists:

```json
{
  "twitterHandles": ["brand_a", "brand_b"],
  "relation": "followers",
  "maxItems": 200,
  "maxItemsPerTarget": 100,
  "outputMode": "compact",
  "includeTargetMetadata": true,
  "overlapMode": true
}
```

Supported relations are:

- `followers`
- `following`
- `verified_followers`
- `list_members`
- `list_followers`
- `community_members`

Use `listIds` for list relations. Use `communityIds` for community members.
Use `relations` when one target needs several relation types.

`maxItems` applies across the complete run. `maxItemsPerTarget` prevents one
large target from consuming the full limit.

`overlapMode: true` merges duplicate profiles. It adds source target, relation,
URL, and overlap metadata. Use `dedupeMode: "none"` when each target needs a
separate row.

## Interpretation boundaries

- A follow does not prove endorsement, intent, or current interest.
- Public relation data can be incomplete or unavailable.
- Compare normalized handles or user IDs, not display names.
- Preserve `sourceTarget` and `sourceRelation` for auditability.
- Report filtered, duplicate, unavailable, and diagnostic rows separately.

Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.
