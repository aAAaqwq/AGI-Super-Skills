---
name: remote-access
description: ttyd + Tailscale for mobile terminal access
---
# Infra Remote Access

> Access Claude Code from your phone via ttyd + Tailscale

## When to use

- "I want to use my phone"
- "remote access"
- "mobile access"
- Setting up a new device

## Components

| Tool | Purpose |
|------|---------|
| **ttyd** | Web terminal (browser access to shell) |
| **Tailscale** | Private VPN network (secure connection) |

## Installation

```bash
# Mac
brew install ttyd tailscale
```

On phone:
- iOS: App Store → Tailscale
- Android: Google Play → Tailscale

---

## IMPORTANT: Tailscale on Mac

Tailscale via brew **requires sudo** for VPN tunnel. There are two options:

### Option 1: Mac App Store (recommended)

Download Tailscale from Mac App Store -- it has all permissions and persists the session.

```bash
# Check status
tailscale status
tailscale ip -4
```

### Option 2: Userspace mode (without sudo)

If using brew version and no sudo:

```bash
# Stop brew service
brew services stop tailscale

# Start in userspace mode
/usr/local/opt/tailscale/bin/tailscaled --tun=userspace-networking --state=/tmp/tailscale.state --socket=/tmp/tailscaled.sock &

# Connect (NOTE: different socket!)
tailscale --socket=/tmp/tailscaled.sock up

# Check status
tailscale --socket=/tmp/tailscaled.sock status
tailscale --socket=/tmp/tailscaled.sock ip -4
```

**Downsides of userspace mode:**
- New session = requires browser authorization
- Must specify `--socket=/tmp/tailscaled.sock` in every command
- Does not work as a full VPN (Tailscale traffic only)

---

## Setup

### Step 1: Tailscale

```bash
# If Mac App Store version:
tailscale up
tailscale ip -4
# Example: 100.x.x.x

# If userspace mode:
tailscale --socket=/tmp/tailscaled.sock up
# Open the authorization URL in browser
tailscale --socket=/tmp/tailscaled.sock ip -4
```

On phone:
1. Install Tailscale from App Store / Play Store
2. Log in with the same account
3. Ensure both devices are online in `tailscale status`

### Step 2: ttyd

```bash
# Stop if already running
pkill ttyd

# Basic launch
ttyd -W -p 7681 bash

# For Claude Code directly
ttyd -W -p 7681 claude

# With authorization (recommended for security)
ttyd -c user:password -W -p 7681 claude
```

**Parameters:**
- `-W` -- allow write (input) -- REQUIRED
- `-p 7681` -- port
- `-c user:pass` -- Basic Auth

### Step 3: Access from phone

On phone, open in browser:
```
http://<tailscale-ip>:7681
```

Example:
```
http://100.x.x.x:7681
```

---

## Quick Start (copy-paste)

```bash
# 1. Check/start Tailscale
tailscale status || tailscale up
TSIP=$(tailscale ip -4)
echo "Tailscale IP: $TSIP"

# 2. Start ttyd
pkill ttyd 2>/dev/null
ttyd -W -p 7681 bash &

# 3. Done!
echo "Open on phone: http://$TSIP:7681"
```

---

## Auto-start ttyd

```bash
mkdir -p ~/Library/LaunchAgents

cat > ~/Library/LaunchAgents/com.ttyd.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ttyd</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ttyd</string>
        <string>-W</string>
        <string>-p</string>
        <string>7681</string>
        <string>bash</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.ttyd.plist
```

---

## Status check

```bash
# Tailscale
tailscale status
# or for userspace:
tailscale --socket=/tmp/tailscaled.sock status

# ttyd process
pgrep -l ttyd

# Port
lsof -i :7681
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `tailscaled requires root` | Use userspace mode or Mac App Store version |
| `failed to connect to local tailscaled` | Restart: `brew services restart tailscale` or start userspace mode |
| Phone cannot see Mac | Check `tailscale status` -- both must be online |
| ttyd not connecting | Check `pgrep ttyd`, restart |
| Port occupied | `lsof -i :7681`, change port to `-p 7682` |
| No input in terminal | Add `-W` parameter |
| New Tailscale authorization | Open URL in browser, log in |

---

## Security

- Tailscale encrypts all traffic (WireGuard)
- ttyd is accessible only via Tailscale IP (not public)
- Additionally -- Basic Auth: `-c user:password`
- Do not use on public IP!

---

## Current configuration

```
Mac IP: 100.x.x.x
ttyd port: 7681
URL: http://100.x.x.x:7681
```

---

## Related skills

- `google-auth` -- if you need Google API from phone
- `telegram-session` -- Telegram from phone
