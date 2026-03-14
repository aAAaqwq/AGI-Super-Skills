# Proxmox Ops

Battle-tested Proxmox VE management toolkit — helper scripts, API patterns, and operational knowledge built from running a 46-guest cluster daily.

Works standalone, or as a knowledge base for AI coding agents (Claude Code, Claude Desktop, OpenClaw, Cursor, etc).

## What's Inside

- **Helper script** (`pve.sh`) with auto node discovery from VMID — no need to know which node a VM lives on
- **Disk resize end-to-end** — API call + in-guest filesystem steps (parted, pvresize, lvextend, resize2fs/xfs_growfs)
- **Guest agent IP discovery** — jq one-liner to pull IPv4 from qemu-guest-agent
- **vmstate snapshot warning** — why `vmstate=1` can freeze your VM and starve I/O on the whole node
- **Operational safety gates** — read-only vs reversible vs destructive, with explicit confirmation guidance
- **Separate provisioning reference** — create, clone, template, delete in its own doc

## Requirements

- `curl`
- `jq`
- Proxmox VE API token ([how to create one](https://pve.proxmox.com/wiki/User_Management#pveum_tokens))

## Setup

```bash
cat > ~/.proxmox-credentials <<'EOF'
PROXMOX_HOST=https://<your-proxmox-ip>:8006
PROXMOX_TOKEN_ID=user@pam!tokenname
PROXMOX_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
EOF
chmod 600 ~/.proxmox-credentials
```

## Quick Start

```bash
# Cluster overview
./scripts/pve.sh status

# List all VMs
./scripts/pve.sh vms

# Start/stop by VMID (auto-discovers node)
./scripts/pve.sh start 200
./scripts/pve.sh stop 200

# Snapshots
./scripts/pve.sh snap 200 before-update
./scripts/pve.sh snapshots 200
```

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Full reference — API patterns, workflows, safety notes |
| `scripts/pve.sh` | Helper script with auto node discovery |
| `references/provisioning.md` | Create, clone, template, and delete operations |

## Using with AI Agents

The knowledge is in plain markdown and shell scripts — no framework lock-in. Here's how to wire it into your setup:

### Claude Code

Clone into your project and reference it in your project memory. Claude Code auto-loads `CLAUDE.md` at session start, so a one-liner is all you need:

```bash
git clone https://github.com/eddygk/proxmox-ops-skill.git proxmox-ops
echo "For Proxmox operations, read proxmox-ops/SKILL.md and proxmox-ops/references/provisioning.md" >> CLAUDE.md
```

Or add it as a modular rule:

```bash
mkdir -p .claude/rules
cp proxmox-ops/SKILL.md .claude/rules/proxmox.md
```

### Claude Desktop (Projects)

1. Create a new Project (or open an existing one)
2. Click **"Set custom instructions"** and add: *"For Proxmox operations, follow the knowledge files."*
3. Upload `SKILL.md` and `references/provisioning.md` as project knowledge files

### OpenClaw / ClawHub

```bash
clawhub install proxmox-ops
```

### Cursor / Windsurf / Other Agents

Drop `SKILL.md` into your project's context directory or reference it in whatever custom instructions mechanism your editor supports. The content is standard markdown — it works anywhere.

## Credits

The `scripts/pve.sh` helper script originates from [weird-aftertaste/proxmox](https://clawhub.com/skills/proxmox) on ClawHub and is used with appreciation. This skill extends it with additional operational patterns, provisioning workflows, disk resize guidance, and guest agent support.

Additional reference material drawn from [mSarheed/proxmox-full](https://clawhub.com/skills/proxmox-full).

## License

MIT
