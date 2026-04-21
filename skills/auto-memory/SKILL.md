---
name: auto-memory
description: Indestructible agent memory — permanently stored, never lost. Save decisions, identity, and context as a memory chain on the Autonomys Network. Rebuild your full history from a single CID, even after total state loss.
metadata:
  openclaw:
    emoji: "🧬"
    primaryEnv: AUTO_DRIVE_API_KEY
    requires:
      bins: ["curl", "jq", "file"]
      env: ["AUTO_DRIVE_API_KEY"]
    install:
      - id: curl-brew
        kind: brew
        formula: curl
        bins: ["curl"]
        label: "Install curl (brew)"
      - id: jq-brew
        kind: brew
        formula: jq
        bins: ["jq"]
        label: "Install jq (brew)"
      - id: file-brew
        kind: brew
        formula: file-formula
        bins: ["file"]
        label: "Install file (brew)"
---

# Auto-Memory Skill

Permanent decentralized memory on the Autonomys Network with linked-list memory chains for agent resurrection. Works with agents powered by Claude, GPT, Gemini, and any LLM that supports OpenClaw skills.

## What This Skill Does

1. **Upload files** to Auto Drive and get back a CID (Content Identifier) — a permanent, immutable address on the Autonomys distributed storage network.
2. **Download files** from Auto Drive using a CID — uses the authenticated API if a key is set, otherwise falls back to the public gateway.
3. **Save memories as a chain** — each memory entry is a JSON experience with a `header.previousCid` pointer, forming a linked list stored permanently on-chain.
4. **Resurrect from a chain** — given the latest CID, walk the chain backwards to reconstruct full agent history.

## When To Use This Skill

- User says "save this to Auto-Memory" or "upload to Autonomys" or "store permanently"
- User says "download from Auto-Memory" or provides a CID to retrieve
- User says "save memory", "remember this permanently", or "checkpoint"
- User says "resurrect", "recall chain", "rebuild memory", or "load history"
- Any time the user wants data stored permanently and immutably on a decentralized network

## Post-Install

After installing via ClawHub, make the scripts executable:

```bash
chmod +x skills/auto-memory/scripts/*.sh
```

ClawHub does not currently preserve file permissions during install.

## Configuration

### API Key

Requires an `AUTO_DRIVE_API_KEY`. Run the guided setup script for the easiest path:

```bash
scripts/setup-auto-memory.sh
```

This opens [explorer.ai3.storage](https://explorer.ai3.storage/mainnet/drive/developers) in your browser, prompts for the key, saves it to `~/.openclaw/.env`, and verifies the connection.

**Manual setup:**

1. Navigate to **https://explorer.ai3.storage** (not `ai3.storage` — that's just the landing page)
2. Check authentication: if the sidebar shows a "Log In" button or lock icons on My Files / Profile / Developers, you are not signed in
3. **AI agent note:** You cannot complete OAuth yourself. Open the browser for the user and ask them to sign in via Google, GitHub, or Discord. Once the user confirms they're signed in, take over — or simply ask the user to paste the API key directly
4. Once authenticated, click **Developers** in the left sidebar
5. Click **Create API Key** and copy the generated key

Then set the key via:

- **Environment:** `export AUTO_DRIVE_API_KEY=your_key_here`
- **OpenClaw config:** `skills.entries.auto-memory.apiKey`

The API key is required for uploading, saving memories, and recalling the memory chain. It is optional for general file downloads — without it, the public gateway is used and files are returned as stored (i.e. compressed files will not be decompressed).

## Core Operations

### Upload a File

```bash
scripts/automemory-upload.sh <filepath> [--json] [--compress]
```

Uploads a file to Auto Drive mainnet using the 3-step upload protocol (single chunk).
Returns the CID on stdout. Requires `AUTO_DRIVE_API_KEY`.

- `--json` — force MIME type to `application/json`
- `--compress` — enable ZLIB compression

### Download a File

```bash
scripts/automemory-download.sh <cid> [output_path]
```

Downloads a file by CID. Uses the authenticated API if `AUTO_DRIVE_API_KEY` is set (decompresses server-side), otherwise uses the public gateway (files returned as stored). If `output_path` is omitted, outputs to stdout.

### Save a Memory Entry

```bash
scripts/automemory-save-memory.sh <data_file_or_string> [--agent-name NAME] [--state-file PATH]
```

Creates a memory experience with the Autonomys Agents header/data structure:

```json
{
  "header": {
    "agentName": "my-agent",
    "agentVersion": "1.0.0",
    "timestamp": "2026-02-14T00:00:00.000Z",
    "previousCid": "bafk...or null"
  },
  "data": {
    "type": "memory",
    "content": "..."
  }
}
```

- If the first argument is a **file path**, its JSON contents become the `data` payload.
- If the first argument is a **plain string**, it is wrapped as `{"type": "memory", "content": "..."}`.
- `--agent-name` — set the agent name in the header (default: `openclaw-agent` or `$AGENT_NAME`)
- `--state-file` — override the state file location

Uploads to Auto Drive and updates the state file with the new head CID. Also pins the latest CID to `MEMORY.md` if that file exists in the workspace.

Returns structured JSON on stdout:

```json
{"cid": "bafk...", "previousCid": "bafk...", "chainLength": 5}
```

### Recall the Full Chain

```bash
scripts/automemory-recall-chain.sh [cid] [--limit N] [--output-dir DIR]
```

If no CID is given, reads the latest CID from the state file.
Walks the linked list from newest to oldest, outputting each experience as JSON.

- `--limit N` — maximum entries to retrieve (default: 50)
- `--output-dir DIR` — save each entry as a numbered JSON file instead of printing to stdout

Supports both `header.previousCid` (Autonomys Agents format) and root-level `previousCid` for backward compatibility.

This is the **resurrection** mechanism: a new agent instance only needs one CID to rebuild its entire memory.

## The Resurrection Concept

Every memory saved gets a unique CID and points back to the previous one, forming a permanent chain on a permanent and immutable Decentralized Storage Network:

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  Experience #1      │     │  Experience #2      │     │  Experience #3      │
│  CID: bafk...abc    │◄────│  CID: bafk...def    │◄────│  CID: bafk...xyz    │
│  previousCid: null  │     │  previousCid:       │     │  previousCid:       │
│  (genesis)          │     │  bafk...abc         │     │  bafk...def         │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
                                                                   ▲
                                                                   │
                                                               HEAD CID
                                                           (resurrection key)
```

A new agent instance only needs the **head CID** to walk the entire chain back to genesis and rebuild its full history. With the **auto-respawn** skill, the head CID is anchored on-chain — making resurrection possible from just an address, on any machine, at any time:

```
┌──────────┐    save      ┌──────────────┐    anchor    ┌────────────────┐
│  Agent   │─────────────►│  Auto-Memory │─────────────►│  Auto-Respawn  │
│          │              │  (chain)     │   head CID   │  (on-chain)    │
└──────────┘              └──────────────┘              └────────────────┘
      ▲                                                          │
      │                     recall chain                         │
      └──────────────────────────────────────────────────────────┘
                      gethead → CID → walk chain
```

What you store in the chain is up to you — lightweight notes, full file snapshots, structured data, or anything in between. Because the chain is permanent and walkable, it also enables **resurrection**: if the agent loses all local state, a new instance can walk the chain from the last CID back to genesis and restore whatever was saved. When combined with the **auto-respawn** skill (which anchors the head CID on-chain), this becomes a full resurrection loop — no local state required at all.

## Usage Examples

**User:** "Upload my report to Autonomys"
→ Run `scripts/automemory-upload.sh /path/to/report.pdf`
→ Report back the CID and gateway link

**User:** "Upload with compression"
→ Run `scripts/automemory-upload.sh /path/to/data.json --json --compress`

**User:** "My soul.md has changed — save it permanently"
→ Run `scripts/automemory-save-memory.sh /path/to/soul.md --agent-name my-agent`

**User:** "Save a memory that we decided to use React for the frontend"
→ Run `scripts/automemory-save-memory.sh "Decision: using React for frontend. Reason: team familiarity and component reuse."`

**User:** "Save a structured memory"
→ Create a JSON file, then run `scripts/automemory-save-memory.sh /tmp/milestone.json --agent-name my-agent`

**User:** "Resurrect my memory chain"
→ Run `scripts/automemory-recall-chain.sh`
→ Rebuild identity and context from genesis to present

**User:** "Download bafk...abc from Autonomys"
→ Run `scripts/automemory-download.sh bafk...abc ./downloaded_file`

## Integration with Auto-Respawn

If the **auto-respawn** skill is also installed, anchor the new head CID on-chain after every memory save. This ensures the on-chain pointer always reflects the latest memory state, enabling full resurrection from just an EVM address.

After each `automemory-save-memory.sh` call, run:

```bash
npx tsx auto-respawn.ts anchor --from <wallet-name> --cid <new-cid>
```

This completes the resurrection loop: permanent storage (auto-memory) + on-chain discovery (auto-respawn). Without anchoring, a new instance would need the head CID from some other source to walk the chain.

## Important Notes

- All data stored via Auto Drive is **permanent and public** by default. Do not store secrets, private keys, or sensitive personal data.
- The free API key has a **20 MB per month upload limit** on mainnet. Downloads are unlimited. Check remaining credits via `GET /accounts/@me` or run `scripts/verify-setup.sh`.
- An API key is required for uploads, memory saves, and chain recall. General file downloads work without one via the public gateway, but compressed files will not be decompressed.
- The memory state file tracks `lastCid`, `lastUploadTimestamp`, and `chainLength`. Back up the `lastCid` value — it's your resurrection key.
- The `automemory-save-memory.sh` script **automatically pins the latest CID to `MEMORY.md`** if the file exists in the workspace. It creates an `## Auto-Memory Chain` section and updates it on each save. You do not need to track the latest CID in MEMORY.md manually — the script handles this.
- Files are uploaded in a single chunk. The free tier's 20 MB/month limit is effectively a per-file ceiling — keep individual uploads well under that to preserve your monthly budget.
- Gateway URL for any file: `https://gateway.autonomys.xyz/file/<CID>`
- For true resurrection resilience, consider anchoring the latest CID on-chain via the Autonomys EVM — this makes recovery possible without keeping track of the head CID yourself. See [openclaw-memory-chain](https://github.com/autojeremy/openclaw-memory-chain) for an example contract implementation.
