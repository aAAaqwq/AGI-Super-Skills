# Auto-Drive API Reference

## Base URLs

- **API (uploads, objects, accounts - requires key):** `https://mainnet.auto-drive.autonomys.xyz/api`
- **Download API:** `https://public.auto-drive.autonomys.xyz/api`
- **Public Gateway (no key):** `https://gateway.autonomys.xyz`
- **Dashboard & Key Management:** `https://ai3.storage` — sign in with Google/GitHub, then Developers → Create API Key

## Authentication

All API requests (uploads, file management) require:

```
Authorization: Bearer <AUTO_DRIVE_API_KEY>
X-Auth-Provider: apikey
```

Gateway downloads are public and need no auth.

## Upload Flow (3 steps)

### 1. Create upload

```
POST /uploads/file
Content-Type: application/json
Body: {"filename": "name.ext", "mimeType": "application/octet-stream", "uploadOptions": {}}
Note: For compression use {"uploadOptions": {"compression": {"algorithm": "ZLIB"}}}
Response: {"id": "<uploadId>"}
```

### 2. Upload chunk(s)

```
POST /uploads/file/<uploadId>/chunk
Content-Type: multipart/form-data
Fields: file (binary), index (integer, start at 0)
```

### 3. Complete upload

```
POST /uploads/<uploadId>/complete
Response: {"cid": "<cid>"}
```

## Download

### Via Download API

```
GET https://public.auto-drive.autonomys.xyz/api/downloads/<cid>
Response: binary stream (decompresses server-side if compressed)
Note: Auth is optional. Authenticated requests get user-level access; unauthenticated
      requests are limited to ~100 MiB per file (exact limit may vary).
```

### Via Gateway (public, no auth needed)

```
GET https://gateway.autonomys.xyz/file/<cid>
Note: No decompression — files returned as stored.
```

## Object Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/objects/roots` | GET | List root objects (query: scope, limit, offset) |
| `/objects/search?cid=<query>` | GET | Search by CID or name |
| `/objects/<cid>/summary` | GET | Get object summary |
| `/objects/<cid>/metadata` | GET | Get object metadata |
| `/objects/<cid>/status` | GET | Get upload status |
| `/objects/<cid>/delete` | POST | Soft-delete object |
| `/objects/<cid>/restore` | POST | Restore deleted object |
| `/objects/<cid>/publish` | POST | Publish object |

## Account

```
GET /accounts/@me
Returns: account info, limits, credits
```

## Free Tier Limits

The free API key from ai3.storage includes a **20 MB per month upload limit** on mainnet. Downloads via the public gateway are unlimited. If uploads start failing mid-month, the agent has likely hit this cap. The agent can check remaining credits via `GET /accounts/@me`.

## CIDs (Content Identifiers)

Every upload returns a CID — a unique, content-addressed hash. The same content always produces the same CID. CIDs are permanent; data stored on the Autonomys DSN cannot be deleted.

## SDK Alternative

For TypeScript/JavaScript projects, the `@autonomys/auto-drive` npm package provides a typed SDK:

```ts
import { createAutoDriveApi, fs } from '@autonomys/auto-drive'
import { NetworkId } from '@autonomys/auto-utils'

const api = createAutoDriveApi({ apiKey: 'your-key', network: NetworkId.MAINNET })
const cid = await fs.uploadFileFromFilepath(api, './file.txt', { compression: true })
```
