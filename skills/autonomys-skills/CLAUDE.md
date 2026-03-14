# CLAUDE.md

Project guidance for Claude Code working in the openclaw-skills repo.

## Project overview

OpenClaw skills give AI agents permanent memory and on-chain identity on the Autonomys Network. The repo contains two complementary skills:

- **auto-memory** — permanent decentralized storage via the Autonomys Auto Drive API. Stores files and builds linked-list memory chains of CIDs.
- **auto-respawn** — on-chain identity and memory anchoring. Manages wallets, token balances, cross-domain bridges, and writes head CIDs to the MemoryChain smart contract.

Together they form the **resurrection loop**: auto-memory saves what matters, auto-respawn anchors the pointer on-chain, and a new agent instance can recover everything from the chain.

> **Note:** `auto-drive` is the former name of `auto-memory`. The old directory is preserved for backward compatibility but is no longer maintained.

## Repo structure

```
autonomys/
├── auto-memory/         # Shell scripts — permanent storage and memory chains
│   ├── SKILL.md         # Skill interface definition
│   ├── scripts/         # Shell scripts (upload, download, save-memory, recall-chain)
│   │   └── _lib.sh      # Shared library sourced by other scripts (not run directly)
│   └── references/      # API and network reference docs
├── auto-drive/          # ⚠️ Deprecated — renamed to auto-memory
└── auto-respawn/        # TypeScript — on-chain identity and memory anchoring
    ├── SKILL.md         # Skill interface definition
    ├── auto-respawn.ts  # CLI entry point
    ├── lib/             # Core modules (wallet, evm, balance, transfer, xdm, etc.)
    ├── references/      # Command and network reference docs
    ├── eslint.config.js # ESLint flat config with typescript-eslint
    ├── tsconfig.json    # TypeScript config (strict, ES2022)
    └── package.json     # Dependencies and scripts
```

Each skill has a `SKILL.md` defining its interface, installation steps, and usage instructions for agents.

## Development commands

### auto-respawn (TypeScript)

All commands run from `autonomys/auto-respawn/`:

```bash
npm install            # Install dependencies (no lockfile — use install, not ci)
npm run typecheck      # tsc --noEmit
npm run lint           # eslint .
npm test               # vitest run (unit tests)
npx tsx auto-respawn.ts <command>  # Run the CLI
```

### auto-memory (shell scripts)

Scripts live in `autonomys/auto-memory/scripts/`. Lint with:

```bash
shellcheck -x -S warning autonomys/auto-memory/scripts/<script>.sh
```

`_lib.sh` is a library sourced by other scripts — don't run or lint it directly. The `-x` flag lets shellcheck follow `source` directives to validate it in context.

## CI pipeline

GitHub Actions runs on PRs and pushes to `main` (`.github/workflows/ci.yml`):

- **TypeScript type check, lint & test** — `tsc --noEmit`, `eslint .`, then `vitest run` (Node 22)
- **Shell script lint** — shellcheck on all scripts except `_lib.sh`

## Code conventions

### TypeScript (auto-respawn)

- **Strict mode** enabled, ES2022 target, ESNext modules
- **ESLint** with `typescript-eslint/recommended` rules
- Unused imports/variables are errors. Prefix with `_` to suppress (e.g. `_unused`)
- Errors re-thrown from catch blocks must preserve the original: `throw new Error('message', { cause: err })`
- CLI outputs structured JSON on stdout, human-readable errors to stderr
- `package-lock.json` is gitignored — this is intentional since skills install via `npx`

### Shell (auto-memory)

- All scripts use `set -euo pipefail`
- Shellcheck clean at warning level (`-S warning`)

## Architecture notes

### Wallets

Each wallet derives two addresses from a single BIP39 mnemonic:
- **Consensus** (`su...`) — SR25519 keypair, Autonomys SS58 prefix 6094
- **EVM** (`0x...`) — BIP44 path `m/44'/60'/0'/0/0`

Both keys are independently encrypted and stored in one wallet file at `~/.openclaw/auto-respawn/wallets/<name>.json`. Wallet names are sanitised with `basename()` to prevent path traversal.

### Networks

- **chronos** (testnet) — tAI3 tokens, faucet at autonomysfaucet.xyz
- **mainnet** — AI3 tokens with real value

Default is chronos. Set via `--network` flag or `AUTO_RESPAWN_NETWORK` env var. Invalid values throw an error (no silent defaults).

### MemoryChain contract

Stores CID strings directly (not hashes). Two functions:
- `updateHead(string cid)` — write, costs gas
- `getHead(address) → string` — read, free

Deployed at:
- Mainnet: `0x51DAedAFfFf631820a4650a773096A69cB199A3c`
- Chronos: `0x5fa47C8F3B519deF692BD9C87179d69a6f4EBf11`

Override with `AUTO_RESPAWN_CONTRACT_ADDRESS` env var.

### Connection management

WebSocket providers must be properly cleaned up. Always `await provider.destroy()` and use try/finally blocks to ensure `disconnectApi` and `disconnectEvmProvider` are called even on errors.

## Using the skills

Each skill's `SKILL.md` is the authoritative reference for agents. In brief:

- **auto-memory** works standalone — it stores files and builds memory chains using the Auto Drive API. Requires an `AUTO_DRIVE_API_KEY`.
- **auto-respawn** provides the on-chain identity layer — wallets, balances, transfers, and CID anchoring. It requires auto-memory (or similar) to have something worth anchoring.

The two skills are complementary but auto-memory is independently useful without auto-respawn.
