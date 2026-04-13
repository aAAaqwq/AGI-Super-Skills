---
name: tailscale-operator
description: Manage, connect to, and troubleshoot devices on a Tailscale tailnet. Use when a user asks to connect to a device over Tailscale, find a device IP, SSH into a tailnet node, fix SSH auth failures, set up public-key login, enable Tailscale SSH, diagnose permission or sudo issues, or operate remote Macs/Linux hosts over the tailnet.
---

# Tailscale Operator

**Author:** Daniel Li  
**Copyright © Daniel Li. All rights reserved.**

Use this skill for **fast path tailnet ops**: find the device, get connected, recover SSH, then solve permissions.

The goal is not to produce a long diagnosis. The goal is to restore a working remote path as fast as possible.

## Default data sources

Check these first:
- Shared tailnet inventory: `/home/aa/.openclaw/shared/tailnet/README.md`
- Device records: `/home/aa/.openclaw/shared/tailnet/devices/*.md`
- Local notes: `/home/aa/.openclaw/workspace-ops/TOOLS.md`

Treat the shared tailnet inventory as the source of truth for:
- device aliases / nicknames
- Tailscale IPs
- SSH usernames
- any known-good SSH command
- platform notes (macOS/Linux, sudo caveats, network quirks)

If the user gives a nickname like `小m`, `studio`, `aa`, or a human name tied to a device, first map it to a documented device record. If multiple matches are plausible, confirm before acting.

If the target device is not documented, say so clearly and ask for one of:
- Tailscale IP
- device name
- SSH username
- exact SSH command

## Quickstart

When speed matters, default to this sequence:

```bash
# 1) find the documented device record first
# 2) test tailnet reachability

tailscale ping 100.x.y.z

# 3) try the known-good SSH path
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 user@100.x.y.z

# 4) verify identity once in
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 user@100.x.y.z 'hostname; whoami; uname -a'
```

If step 2 fails, fix Tailscale first.
If step 2 works but step 3 fails, fix SSH auth / sshd / Tailscale SSH.

## Core workflow

### Decision tree

1. **Resolve the target device first**
   - Read `shared/tailnet/devices/*.md`
   - Prefer the documented SSH command exactly as stored
   - Do not improvise usernames or addresses until the inventory has been checked

2. **Test Tailscale reachability before deep SSH debugging**
   - Fast path:
     - `tailscale ping <ip-or-name>` when available
     - `ping -c 1 100.x.y.z`
     - `nc -vz 100.x.y.z 22`
   - This separates “tailnet is broken/offline” from “tailnet works but SSH is broken”

3. **Try the simplest known-good SSH command**
   - Example:
     - `ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 user@100.x.y.z`

4. **If SSH fails, classify fast by exact error text**
   - `Permission denied (publickey)` → key/auth problem
   - `Operation timed out` / `No route to host` → device offline, Tailscale broken, ACL, firewall, wrong IP
   - `Host key verification failed` → stale `known_hosts` entry or rebuilt machine
   - `Connection refused` → sshd not listening, Tailscale SSH not enabled, firewall, wrong port
   - asks for password but none known → key missing, wrong user, or password auth fallback
   - `sudo: a password is required` → account has sudo but needs password
   - `not in the sudoers file` → privilege problem; need another admin path

5. **Apply the fastest safe fix**
   - Fix host key mismatch
   - Try documented alternate username if one exists
   - Install public key on remote account
   - Use Tailscale SSH if ordinary SSH is the blocker and the tailnet policy allows it
   - For permissions, prefer an existing admin account over changing system policy

6. **Verify and leave a stable path**
   - Re-test SSH
   - Confirm the remote host identity: `hostname; whoami; uname -a`
   - If a new working path was discovered, record it in the device note

## Fast fixes by failure mode

### Error → fastest next command

| Failure mode | Likely cause | Fastest next command |
|---|---|---|
| `Host key verification failed` | stale host key | `ssh-keygen -R 100.x.y.z` |
| `Permission denied (publickey)` | wrong user/key or missing public key | `ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 user@100.x.y.z` |
| timeout / `No route to host` | node offline / Tailscale broken / wrong IP | `tailscale ping 100.x.y.z` |
| `Connection refused` | SSH service closed / disabled | `nc -vz 100.x.y.z 22` |
| asks for password unexpectedly | key auth not working | `cat ~/.ssh/id_ed25519.pub` |
| `sudo: a password is required` | sudo works but needs password | stop and ask for the admin password |
| `not in the sudoers file` | wrong account / no admin rights | switch to an existing admin account |

Then follow the detailed branch below.

### 1) `Host key verification failed`

Use:
```bash
ssh-keygen -R 100.x.y.z
ssh-keygen -R hostname
```
Then reconnect.

### 2) `Permission denied (publickey)`

Try, in order:
1. Confirm username from device notes
2. Force the intended key:
```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 user@100.x.y.z
```
3. If you already have another path onto the machine, install your key:
```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo 'YOUR_PUBLIC_KEY' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```
4. On macOS/Linux, verify ownership:
```bash
chown -R "$USER":$(id -gn) ~/.ssh
```

### 3) `Connection refused`

Check whether the host is up but SSH is closed.

Useful checks on the remote side (if you have console/another path):
```bash
sudo systemctl status ssh
sudo systemctl status sshd
sudo ss -ltnp | grep ':22'
```
On macOS:
```bash
sudo systemsetup -getremotelogin
sudo systemsetup -setremotelogin on
sudo launchctl list | grep ssh
```

### 4) Timeout / no route

Suspect Tailscale before SSH.

From the local side, prefer these checks first:
```bash
tailscale ping 100.x.y.z
ping -c 1 100.x.y.z
nc -vz 100.x.y.z 22
```

If you have another path onto the remote side, check:
```bash
tailscale status
tailscale ip -4
tailscale whois 100.x.y.z
```
If deeper Tailscale diagnosis is needed on the node itself, use:
```bash
tailscale netcheck
tailscale status --json
```
If the node is missing/offline, ask the user to wake it, log in, or open Tailscale.

### 5) Password prompt but goal is no-password login

Set up public-key auth or Tailscale SSH.

#### Preferred: install your SSH public key
Display local public key if needed:
```bash
cat ~/.ssh/id_ed25519.pub
```
Install it on the target account's `~/.ssh/authorized_keys`.

#### Alternate: Tailscale SSH
Use when normal `sshd` management is painful and Tailscale policy allows it.

Prefer this branch when:
- the node is clearly online in Tailscale
- ordinary SSH is blocked by key setup, user mismatch, or disabled `sshd`
- the user wants the fastest passwordless path

Useful checks:
```bash
tailscale status --json
tailscale ping 100.x.y.z
tailscale up
```
Decision rule:
- if tailnet policy already allows Tailscale SSH, prefer enabling/using it over spending too long fixing legacy `sshd`
- if tailnet policy does **not** allow it or cannot be changed quickly, fall back to standard `sshd` + `authorized_keys`

## Permission / sudo playbook

### Fast rule
- If the user only needs ordinary commands, do **not** touch sudo first.
- If the requested task needs system changes, say early that admin rights are required.
- If sudo needs a password and none is available, stop escalating and say exactly that.

### Case A: user has sudo, but password is required
- This is normal on many macOS/Linux hosts.
- Fastest route: ask for the account password or switch to an already-admin session.
- Do **not** weaken sudo policy just to avoid the password.

### Case B: user is not in sudoers
- Find an existing admin account first.
- On macOS, an admin user can add another admin user:
```bash
sudo dseditgroup -o edit -a username -t user admin
```
- On Linux:
```bash
sudo usermod -aG sudo username
# or on some distros
sudo usermod -aG wheel username
```
- Only do this with clear user approval.

### Case C: file permission blocks key usage
Check:
```bash
ls -ld ~/.ssh
ls -l ~/.ssh
```
Typical safe permissions:
- `~/.ssh` = `700`
- `authorized_keys` = `600`
- private key = `600`

## Preferred command patterns

### Standard SSH over tailnet
```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 user@100.x.y.z
```

### Quick remote sanity check
```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 user@100.x.y.z 'hostname; whoami; uname -a'
```

### Copy local public key when password login is temporarily available
```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@100.x.y.z
```
If `ssh-copy-id` is unavailable, append manually.

## macOS specifics

For Macs, check these early:
- Remote Login enabled
- correct account short name
- FileVault/login state if the machine was just rebooted
- Tailscale app running and signed in
- whether an admin password or physical unlock is still required after reboot

Common commands:
```bash
scutil --get ComputerName
whoami
systemsetup -getremotelogin
```

## Tailnet troubleshooting heuristics

Use the fastest likely fix, not a long generic checklist.

- If the IP changed recently, re-read `tailscale ip -4` on the remote node or ask the user for the new IP.
- If the device exists in inventory but SSH fails, prefer fixing auth over replacing the whole connection method.
- If multiple devices match the same human label, confirm the exact host before making changes.
- If `tailscale ping` fails, stop deep SSH debugging and fix tailnet reachability first.
- If `tailscale ping` works but TCP 22 fails, focus on SSH/Tailscale SSH rather than general network theory.
- For recurring tasks, update the relevant `shared/tailnet/devices/*.md` file with the working command/path.

## Record-back rules

When new durable facts are discovered, write them back to the relevant device note when appropriate:
- confirmed Tailscale IP
- confirmed SSH username
- confirmed working SSH command
- whether passwordless public-key auth works
- whether Tailscale SSH is enabled/usable
- whether sudo requires a password
- platform-specific caveats (for example: network is slow, needs physical unlock after reboot)

Do not write uncertain guesses back into the inventory.

## Do not do these by default

- Do not modify sudo policy just to avoid a password prompt.
- Do not promote a user to admin/sudoers without explicit approval.
- Do not wipe or replace the remote `~/.ssh` directory to "fix" login.
- Do not change firewall/network settings before confirming the actual failure mode.
- Do not operate on an ambiguously matched device name.

## Output style

When helping the user:
- State the likely root cause in one line.
- Give the **fastest next command** first.
- Only expand into deeper branching steps if that command fails.
- If access is impossible without user action (password, physical unlock, admin approval), say exactly what is needed.

## What success looks like

A good outcome is not just “I diagnosed it”. A good outcome is one of:
- SSH works now
- Tailscale SSH works now
- public key installed and future logins are passwordless
- sudo/admin path is known and documented
- blocker is explicit and minimal (e.g. “need admin password once on the Mac console”)
