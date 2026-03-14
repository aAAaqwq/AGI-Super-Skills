# Memory Chain & Resurrection Pattern

## Concept

Agent memories are stored as a **linked list on permanent decentralized storage**. Each memory entry is a JSON experience containing a `header.previousCid` pointer to the entry before it.

This means an agent can be fully reconstructed from a single piece of information: the CID of its most recent experience.

## Experience Structure

Each memory node follows the Autonomys Agents format:

```json
{
  "header": {
    "agentName": "openclaw-agent",
    "agentVersion": "1.0.0",
    "timestamp": "2026-02-13T21:00:00.000Z",
    "previousCid": "bafk...previous_entry_cid"
  },
  "data": {
    "type": "memory",
    "content": "The decision or observation to remember"
  }
}
```

The first entry (genesis) has `header.previousCid: null`.

The `data` field is flexible — it can contain any JSON structure. When saving a plain string via the save-memory script, it is wrapped as `{"type": "memory", "content": "..."}`. When saving a JSON file, the file's contents become the `data` field directly.

## Chain Traversal

To resurrect:

1. Start with the head CID (the most recent experience)
2. Download the JSON from that CID
3. Read `header.previousCid`
4. Download that entry
5. Repeat until `header.previousCid` is `null`
6. You now have the complete history from newest to oldest

The recall script also supports root-level `previousCid` for backward compatibility with older chain formats.

## Why This Works

- **Immutable:** Once stored, a CID's content never changes
- **Permanent:** The Autonomys DSN stores data as part of consensus — it doesn't expire
- **Self-referencing:** Each entry contains everything needed to find the rest
- **Portable:** Any system with HTTP access can walk the chain
- **Verifiable:** CIDs are content-addressed hashes — tamper-proof by design

## Local State

The state file (default: `$OPENCLAW_WORKSPACE/memory/autodrive-state.json`) tracks the current chain head:

```json
{
  "lastCid": "bafk...latest",
  "lastUploadTimestamp": "2026-02-13T21:00:00.000Z",
  "chainLength": 5
}
```

**Back up the `lastCid` value.** It's the single key to your agent's entire history.

## On-Chain CID Registry (Optional)

For true resurrection resilience — surviving even the loss of all local state — store the latest CID in a smart contract on Autonomys EVM. See the companion project: [openclaw-memory-chain](https://github.com/autojeremy/openclaw-memory-chain).

The contract is at `0x51DAedAFfFf631820a4650a773096A69cB199A3c` on Autonomys Mainnet (Chain ID 870). It provides:

- `updateHead(string cid)` — write your latest CID (scoped to your wallet)
- `getHead(address agent)` — read any agent's chain head

## Origin

This pattern comes from the Autonomys Agents framework (github.com/autonomys/autonomys-agents), where agents store "experiences" as on-chain linked lists. The framework calls this process "resurrection" — walking the chain from any CID back to genesis to rebuild full agent context.

Reference implementation paths:

- `core/src/blockchain/agentExperience/autoDrive.ts` — upload/download experiences
- `core/src/blockchain/agentExperience/cidManager.ts` — CID chain management (local + on-chain)
- `core/src/blockchain/agentExperience/types.ts` — type definitions
