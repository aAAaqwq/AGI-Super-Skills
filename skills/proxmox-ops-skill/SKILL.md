---
name: proxmox-ops
description: |
  Ops-focused Proxmox VE management via REST API — monitor, control, provision, and troubleshoot VMs and LXC containers with battle-tested operational patterns.

  Use when asked to:
  - List, start, stop, restart VMs or LXC containers
  - Check node status, cluster health, or resource usage
  - Create, clone, or delete VMs and containers
  - Manage snapshots, backups, storage, or templates
  - Resize disks (API + in-guest filesystem steps)
  - Query guest agent for IP addresses
  - View tasks or system event logs

  Includes helper script (pve.sh) with auto node discovery from VMID, operational safety gates (read-only vs reversible vs destructive), vmstate snapshot warnings, post-resize guest filesystem steps, and a separate provisioning reference.

  Requires: curl, jq.
  Writes: ~/.proxmox-credentials (user-created, API token, mode 600).
  Network: connects to user-configured Proxmox host only (HTTPS, TLS verification disabled for self-signed certs).

  Helper script: scripts/pve.sh (relative to this skill)
  Configuration: ~/.proxmox-credentials
metadata: { "openclaw": { "emoji": "🖥️", "homepage": "https://github.com/eddygk/proxmox-ops-skill", "requires": { "bins": ["curl", "jq"] }, "os": ["darwin", "linux"] } }
---

# Proxmox VE Management

## First-Time Setup

Create a credential file at `~/.proxmox-credentials`:

```bash
cat > ~/.proxmox-credentials <<'EOF'
PROXMOX_HOST=https://<your-proxmox-ip>:8006
PROXMOX_TOKEN_ID=user@pam!tokenname
PROXMOX_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
EOF
chmod 600 ~/.proxmox-credentials
```

**Alternative:** Set `PROXMOX_HOST`, `PROXMOX_TOKEN_ID`, and `PROXMOX_TOKEN_SECRET` as environment variables directly (useful for CI/agent contexts). The helper script checks env vars first, then falls back to sourcing `~/.proxmox-credentials`.

Create API token in Proxmox: Datacenter → Permissions → API Tokens → Add. Use least-privilege: only grant the permissions your workflow requires (e.g., `PVEAuditor` for read-only monitoring, `PVEVMAdmin` for VM control). Disable Privilege Separation only if your workflow requires full API access.

## Auth Header

```bash
source ~/.proxmox-credentials
AUTH="Authorization: PVEAPIToken=$PROXMOX_TOKEN_ID=$PROXMOX_TOKEN_SECRET"
```

## Helper Script

`scripts/pve.sh` auto-discovers nodes from VMID — no need to specify the node for most operations.

```bash
pve.sh status              # Cluster nodes overview
pve.sh vms [node]          # List all VMs (optionally filter by node)
pve.sh lxc <node>          # List LXC containers on node
pve.sh start <vmid>        # Start VM/LXC
pve.sh stop <vmid>         # Force stop VM/LXC
pve.sh shutdown <vmid>     # Graceful shutdown VM/LXC
pve.sh reboot <vmid>       # Reboot VM/LXC
pve.sh snap <vmid> [name]  # Create snapshot (disk-only, safe)
pve.sh snapshots <vmid>    # List snapshots
pve.sh tasks <node>        # Show recent tasks
pve.sh storage <node>      # Show storage status
```

## Workflow

1. **Load credentials** from `~/.proxmox-credentials`
2. **Determine operation type:**
   - **Read-only** (status, list, storage, tasks) → Execute directly
   - **Reversible** (start, stop, reboot, snapshot) → Execute, note UPID for tracking
   - **Destructive** (delete VM, resize disk, rollback snapshot) → Confirm with user first
3. **Query Proxmox API** via curl + API token auth
4. **Parse JSON** with jq
5. **Track async tasks** — create/clone/backup operations return UPID

## Common Operations

### Cluster & Nodes

```bash
# Cluster status
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/cluster/status" | jq

# List nodes with CPU/memory
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes" | jq '.data[] | {node, status, cpu, mem: (.mem/.maxmem*100|round)}'
```

### List VMs & Containers

```bash
# Cluster-wide (all VMs + LXC)
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/cluster/resources?type=vm" | jq '.data[] | {node, vmid, name, type, status}'

# VMs on specific node
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu" | jq '.data[] | {vmid, name, status}'

# LXC on specific node
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/lxc" | jq '.data[] | {vmid, name, status}'
```

### VM/Container Control

```bash
# Start / Stop / Shutdown / Reboot
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/status/start"
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/status/stop"
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/status/shutdown"
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/status/reboot"

# For LXC: replace /qemu/ with /lxc/
```

### Snapshots

**⚠️ vmstate parameter:** Do NOT include `vmstate=1` unless you specifically need to preserve running process state.
- `vmstate=1` freezes the VM and causes heavy I/O — can starve other guests on the same node
- For pre-change backups, omit vmstate (defaults to disk-only, no I/O spike)

```bash
# List snapshots
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/snapshot" | jq

# Create snapshot (disk-only, safe)
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/snapshot" \
  -d "snapname=snap1" -d "description=Before update"

# Rollback
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/snapshot/{snapname}/rollback"

# Delete snapshot
curl -ks -X DELETE -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/snapshot/{snapname}"
```

### Disk Resize

```bash
# Get current disk config
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/config" | jq

# Resize disk (use absolute size, NOT relative — +10G fails regex validation)
curl -ks -X PUT -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/resize" \
  -d "disk=scsi0" -d "size=20G" | jq
```

**Post-resize inside VM:**
1. Fix GPT: `parted /dev/sda print` → Fix
2. Resize partition: `parted /dev/sda resizepart 3 100%`
3. If LVM: `pvresize /dev/sda3 && lvextend -l +100%FREE /dev/vg/root`
4. Resize filesystem: `resize2fs /dev/mapper/vg-root` (ext4) or `xfs_growfs /` (xfs)

### Guest Agent (IP Discovery)

```bash
# Get VM network interfaces (requires qemu-guest-agent)
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces" | \
  jq -r '.data.result[] | select(.name != "lo") | .["ip-addresses"][] | select(.["ip-address-type"] == "ipv4") | .["ip-address"]' | head -1
```

Always query guest agent for current IP — don't hardcode IPs.

### Storage & Backups

```bash
# List storage
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/storage" | jq '.data[] | {storage, type, active, used_fraction: (.used/.total*100|round|tostring + "%")}'

# List backups
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/storage/{storage}/content?content=backup" | jq

# Start backup
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/vzdump" \
  -d "vmid={vmid}" -d "storage={storage}" -d "mode=snapshot"
```

### Tasks

```bash
# Recent tasks
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/tasks" | jq '.data[:10] | .[] | {upid, type, status, user}'

# Task log
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/tasks/{upid}/log" | jq -r '.data[].t'
```

## Provisioning

For create VM, create LXC, clone, convert to template, and delete operations:

→ See [references/provisioning.md](references/provisioning.md)

## Security Notes

- **Credential file** (`~/.proxmox-credentials`) is user-created, not auto-generated by this skill. Must be mode 600 (`chmod 600 ~/.proxmox-credentials`). Rotate tokens immediately if exposed
- **TLS verification disabled** (`-k` / `--insecure`) — Proxmox VE uses self-signed certificates by default ([Proxmox docs](https://pve.proxmox.com/wiki/Certificate_Management)). If you deploy a trusted CA cert on your Proxmox node, remove the `-k` flag from curl commands and pve.sh
- **Least-privilege tokens** — create tokens with only the roles your workflow needs. `PVEAuditor` for monitoring, `PVEVMAdmin` for VM ops. Full-access tokens are not required for most operations
- **Network scope** — all API calls target `PROXMOX_HOST` only. No external endpoints. Verify by reviewing `scripts/pve.sh` (small, readable). In agent contexts, restrict network access to your Proxmox hosts only
- **API tokens** don't need CSRF tokens for POST/PUT/DELETE
- **Power and delete operations are destructive** — confirm with user first
- **Never expose credentials** in responses

## Notes

- Replace `{node}`, `{vmid}`, `{storage}`, `{snapname}` with actual values
- Task operations return UPID for tracking async jobs
- Use `qemu` for VMs, `lxc` for containers in endpoint paths
