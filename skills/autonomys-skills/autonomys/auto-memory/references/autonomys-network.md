# Autonomys Network Overview

## What Is It

Autonomys is an L1 blockchain (like Bitcoin or Ethereum, but different). Its superpower is permanent storage — when you put data on it, that data stays there forever as part of how the network operates.

It's not stored on servers or special storage nodes. It's distributed across the network — hundreds of users ("farmers") running plain old commodity hardware and pledging disk space. The consensus mechanism is Proof-of-Archival-Storage (PoAS).

## Auto Drive

Auto Drive is the developer-facing storage interface built on top of the Autonomys Distributed Storage Network (DSN). It works like a decentralized version of file hosting:

- **Upload** any file → get a CID
- **Download** any file → use the CID
- **Permanent** — data doesn't expire
- **Content-addressed** — same content = same CID

Your agent can get its own free API key at https://ai3.storage (sign in with Google/GitHub → Developers → Create API Key).

## How the Pieces Fit Together

```
┌─────────────────────────────────────────────────┐
│  auto-memory skill                              │
│  Linked-list memory chains, resurrection logic  │
│  (this skill — shell scripts in scripts/)       │
├─────────────────────────────────────────────────┤
│  Auto Drive                                     │
│  Developer API for upload/download by CID       │
│  (Autonomys product — api.auto-drive.autonomys) │
├─────────────────────────────────────────────────┤
│  Autonomys DSN                                  │
│  Permanent distributed storage via PoAS         │
│  (the network itself — farmers, consensus)      │
└─────────────────────────────────────────────────┘
```

- **Autonomys DSN** is the infrastructure — the decentralized storage network where data is archived permanently by farmers.
- **Auto Drive** is the product built on top of the DSN — the API and dashboard that lets developers upload and download files by CID.
- **auto-memory** is this OpenClaw skill — it uses Auto Drive to store agent memories as a linked-list chain and provides resurrection (rebuilding full agent context from a single CID).

The `AUTO_DRIVE_API_KEY` env var authenticates with the Auto Drive service. The auto-memory skill wraps that service with memory-chain logic.

## Key Links

- Auto Drive Dashboard: https://ai3.storage
- Public Gateway: https://gateway.autonomys.xyz
- API Docs: https://mainnet.auto-drive.autonomys.xyz/api/docs
- SDK Docs: https://develop.autonomys.xyz/sdk/auto-drive/overview_setup
- GitHub (Auto SDK): https://github.com/autonomys/auto-sdk
- GitHub (Auto Drive): https://github.com/autonomys/auto-drive

## Autonomys Agents Framework

The Autonomys Agents framework (https://github.com/autonomys/autonomys-agents) is an experimental system for building AI agents that maintain permanent memory on the Autonomys Network. Key features:

- Agents store experiences as linked-list entries on-chain
- Each experience gets a CID pointing to the previous one
- "Resurrection" reconstructs an agent's full history from one CID
- Supports multiple LLM providers (Anthropic, OpenAI, DeepSeek, etc.)
- YAML-based character system for agent personalities

This skill brings the core storage and resurrection capabilities from that framework into any OpenClaw agent.
