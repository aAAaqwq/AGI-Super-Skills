---
name: stripe-webhook
description: Manage AI Kitchen Pro Stripe webhook — deploy, test, switch test/prod, view logs
---
# Stripe Webhook (AI Kitchen Pro)

> Cloudflare Worker that receives Stripe checkout.session.completed events, sends TG notifications, and updates CRM via GitHub API.

## When to use

- Deploy or redeploy the webhook worker
- Switch between test and prod Stripe mode
- Test the payment notification flow
- Debug webhook failures
- View worker logs

## Dependencies

- External: Node.js, wrangler CLI (`npm i -g wrangler`), Cloudflare account
- Other skills: `git-workflow` (for commits)

## Paths

| What | Path |
|------|------|
| Worker code | `$WEBHOOK_PATH/src/index.js` |
| Wrangler config | `$WEBHOOK_PATH/wrangler.toml` |
| Secrets (.env) | `$WEBHOOK_PATH/.env` |
| GitHub repo | `your-org/your-webhook` |

## Architecture

```
Stripe checkout.session.completed
    → Cloudflare Worker (your-webhook.your-project.workers.dev/stripe)
        → 1. TG notification to Ivan (@your_pay_bot)
        → 2. CRM update (people.csv + activities.csv via GitHub API)
        → 3. Email (via Stripe receipt, no custom code)
```

## Secrets (Cloudflare Worker)

| Secret | Description |
|--------|-------------|
| `STRIPE_WEBHOOK_SECRET` | Signing secret (whsec_...) — different for test vs prod |
| `TELEGRAM_BOT_TOKEN` | @your_pay_bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram user ID |
| `GITHUB_TOKEN` | PAT with repo write access |

## How to execute

### Deploy

```bash
cd $WEBHOOK_PATH
npx wrangler deploy
```

### Switch to TEST mode

```bash
# Read test secret from .env
grep STRIPE_TEST_WEBHOOK_SECRET $WEBHOOK_PATH/.env
# Set it
echo "<test_whsec>" | npx wrangler secret put STRIPE_WEBHOOK_SECRET
```

### Switch to PROD mode

```bash
grep STRIPE_LIVE_WEBHOOK_SECRET $WEBHOOK_PATH/.env
echo "<prod_whsec>" | npx wrangler secret put STRIPE_WEBHOOK_SECRET
```

### Send test webhook (simulate payment)

```python
import hmac, hashlib, time, json, urllib.request

secret = "<STRIPE_WEBHOOK_SECRET>"  # test or prod
payload = json.dumps({
    "id": "evt_test_123",
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_test_abc",
            "object": "checkout.session",
            "amount_total": 10100,  # $101
            "currency": "usd",
            "customer_details": {"email": "test@example.com", "name": "Test User"},
            "customer_email": "test@example.com",
            "custom_fields": [{"key": "telegram_username", "text": {"value": "test_user"}}],
            "metadata": {"product_id": "prod_XXXXXXXXXXXX"}
        }
    }
})

timestamp = str(int(time.time()))
signature = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()

req = urllib.request.Request(
    "https://your-webhook.your-project.workers.dev/stripe",
    data=payload.encode(),
    headers={
        "Content-Type": "application/json",
        "Stripe-Signature": f"t={timestamp},v1={signature}",
        "User-Agent": "Stripe/1.0",
    },
    method="POST",
)
resp = urllib.request.urlopen(req, timeout=15)
print(resp.read().decode())
```

### View live logs

```bash
cd $WEBHOOK_PATH
npx wrangler tail
```

## Stripe Products

| Product ID (PROD) | Product ID (TEST) | Name | Price |
|---|---|---|---|
| prod_XXXXXXXXXXXX | prod_TEST_XXXXXXX | Tier 1 Basic | $101/mo |
| prod_YYYYYYYYYYYY | prod_TEST_YYYYYYY | Tier 2 Premium | $500 |
| prod_ZZZZZZZZZZZZ | prod_TEST_ZZZZZZZ | Tier 3 Enterprise | $1000 |

## Webhook Endpoints

| Mode | Endpoint ID | Signing Secret |
|------|-------------|----------------|
| PROD | `<YOUR_PROD_ENDPOINT_ID>` | `<YOUR_PROD_WEBHOOK_SECRET>` |
| TEST | `<YOUR_TEST_ENDPOINT_ID>` | `<YOUR_TEST_WEBHOOK_SECRET>` |

## Tier detection logic

Worker matches tier by: 1) `metadata.product_id` → TIER_MAP, 2) fallback by amount ($101/$500/$1000).

## Limitations

- CRM update goes directly to `main` branch (no PR) — acceptable for webhook automation
- No retry logic — Stripe retries failed webhooks automatically
- `custom_fields` telegram_username depends on Stripe checkout form having this field configured
- GitHub OAuth token (gho_) may expire — if CRM updates fail, refresh via `gh auth login`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| TG notification not arriving | Check TELEGRAM_BOT_TOKEN, ensure /start was sent to bot |
| CRM update failing | Check GITHUB_TOKEN validity (`gh auth status`), check UTF-8 in CSV |
| Invalid signature (400) | Wrong STRIPE_WEBHOOK_SECRET — check test vs prod mode |
| SSL handshake failure | New subdomain — wait 2-5 min for cert provisioning |

## Related skills

- `payment-tracker-run` — payment follow-up automation
- `log-activity` — manual CRM activity logging
