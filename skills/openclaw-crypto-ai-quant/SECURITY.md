# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest on `master` | Yes |
| Older releases | No |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, report them privately:

1. **Email**: security@openclaw.io
2. **GitHub**: Use [private vulnerability reporting](https://github.com/fol2/openclaw-crypto-ai-quant/security/advisories/new)

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact (especially anything related to trading, funds, or key exposure)
- Suggested fix (if any)

### Response timeline

- **Acknowledgement**: within 48 hours
- **Initial assessment**: within 1 week
- **Fix or mitigation**: depends on severity, but critical issues targeting funds or keys are treated as P0

## Scope

The following are in scope:

- Trading engine logic (`engine/`, `strategy/`, `live/`)
- Exchange adapters and order execution (`exchange/`, `live/trader.py`)
- Key/secret handling (anything touching `secrets.json`, `.env`, API keys)
- Risk manager bypasses (`engine/risk.py`)
- Kill-switch circumvention
- WebSocket sidecar and data integrity (`ws_sidecar/`)
- Rust backtester and PyO3 bridge (`backtester/`)

## Disclosure Policy

We follow coordinated disclosure. We ask reporters to give us reasonable time to address the issue before public disclosure.

Once a fix is released, we will credit the reporter (unless they prefer anonymity) in the release notes.
