# Contributing to openclaw-crypto-ai-quant

We welcome contributions. This guide covers the essentials.

## Reporting Issues

Use GitHub Issues. When reporting bugs, please include:

- Steps to reproduce
- Expected vs actual behaviour
- Backtest results if the issue is strategy-related

## Development Setup

```bash
# Python (>=3.12, managed by uv)
uv sync --dev

# Rust backtester (CPU)
cd backtester && cargo build --release

# Rust backtester (GPU, requires CUDA toolkit)
python3 tools/build_mei_backtester.py --gpu

# Rust WebSocket sidecar
cd ws_sidecar && cargo build --release

# Rust Hub dashboard
cd hub && cargo build --release
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for full setup details.

## Code Style

### Python

Enforced by `ruff` (line-length 120, Python 3.12 target):

```bash
uv run ruff check engine strategy exchange live tools tests monitor
uv run ruff format engine strategy exchange live tools tests monitor
```

### Rust

Must pass `cargo fmt` and `cargo clippy`:

```bash
cargo fmt --check
cargo clippy -- -D warnings
```

## Testing

### Python

```bash
uv run pytest
```

Coverage is enforced for `sqlite_logger`, `heartbeat`, `risk`, and `executor` modules (see `pyproject.toml` for thresholds).

### Rust

```bash
cd backtester && cargo test
cd ws_sidecar && cargo test
cd hub && cargo test
```

### Strategy Changes

Strategy changes must include backtest evidence (sweep results or replay comparison showing before/after metrics).

### Indicator Changes (Rust)

After modifying indicator logic in the Rust backtester:

1. Run `dump-indicators` to export Rust output
2. Compare against Python `ta` library output
3. Ensure all indicators match within 0.00005 absolute error

## Pull Requests

1. One logical change per PR (atomic PRs)
2. Ensure all tests and lint checks pass
3. Write clear commit messages (conventional commits preferred: `feat:`, `fix:`, `refactor:`, `docs:`)
4. For strategy parameter changes: include before/after backtest metrics in the PR description
5. Complete the risk checklist in the PR template

## Security

- NEVER commit secrets (private keys, wallet addresses, API keys)
- Use `.env.example`, `config/secrets.json.example`, and `systemd/*.env.example` as templates
- Report security vulnerabilities privately via GitHub Security Advisories

## Disclaimer

This software is for educational and research purposes. Trading cryptocurrencies involves significant risk. The authors are not responsible for any financial losses incurred through use of this software.
