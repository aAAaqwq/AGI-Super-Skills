# Cloudflare Origin Server Certificate

## What is it?

Cloudflare Origin Server Certificate is a TLS certificate issued by Cloudflare specifically for encryption between Cloudflare's edge servers and your origin server.

## Key Points

| Aspect | Detail |
|--------|--------|
| **Browser Trust** | NOT trusted by browsers (for CF→Origin only) |
| **Valid For** | Cloudflare to your server communication |
| **Validity** | Up to 15 years |
| **Cost** | Free |
| **Requires** | Cloudflare Proxy or Tunnel |

## When to Use

- Your site is behind **Cloudflare Proxy** (orange cloud in DNS)
- Your site uses **Cloudflare Tunnel**
- You need end-to-end encryption from CF to origin

## Download Steps

1. **Cloudflare Dashboard** → **SSL/TLS** → **Origin Server**
2. Click **Create Certificate**
3. Configure:
   - **Hostnames**: `*.yourdomain.com` and `yourdomain.com`
   - **Validity**: 15 years
   - **Key Type**: RSA (2048)
4. Click **Create**
5. Copy two parts:

### Origin Certificate (save as `nginx.crt`)
```
-----BEGIN CERTIFICATE-----
MIIEpDCCA4ygAwIBAgIUZK...
-----END CERTIFICATE-----
```

### Private Key (save as `nginx.key`)
```
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0B...
-----END PRIVATE KEY-----
```

## File Formats

- Certificate: `.crt` or `.pem` (same content, different extension)
- Private Key: `.key`

## Security Notes

- **NEVER commit** private keys to git
- Add `*.key` to `.gitignore`
- Certificates can be public, but keys must be private
