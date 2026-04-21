---
name: command-registry-integration
description: Integrate new chat commands into OpenClaw's formal command registry
---

# command-registry-integration

Integrate a new chat command into OpenClaw’s formal command registry and command handling chain so it appears in `/commands`, supports native slash registration where applicable, and avoids brittle text-intercept hacks.

## Use this when

- You need a real built-in chat command such as `/foo`
- The command must appear in `/commands`
- The command should ride the formal command detection / registry / handler path
- You want the smallest-source-change path for adding a command

## Do NOT use this when

- A plugin command is enough and you do **not** need a built-in source command
- A skill command (`/skill name`) already solves the problem
- You are trying to intercept plain text with ad-hoc regexes outside the command pipeline

## Source map: where to look first

1. `src/auto-reply/commands-registry.data.ts`
   - Source of truth for built-in command registry entries
   - Controls `/commands` visibility and native command metadata
2. `src/auto-reply/commands-registry.ts`
   - Detection, normalization, arg parsing, native spec export
3. `src/auto-reply/reply/commands-core.ts`
   - Main built-in handler chain
4. `src/auto-reply/reply/commands-*.ts`
   - Concrete handlers; add the new command here
5. `src/auto-reply/status.ts`
   - `/commands` and `/help` rendering tests depend on registry descriptions
6. Tests:
   - `src/auto-reply/commands-registry.test.ts`
   - `src/auto-reply/reply/commands.test.ts`
   - `src/auto-reply/status.test.ts`

## Minimal integration path

### 1) Add registry entry

In `commands-registry.data.ts`, add a `defineChatCommand({...})` entry with:
- `key`
- `nativeName`
- `description`
- `textAlias` or `textAliases`
- `category`
- `args` / `argsParsing` / `acceptsArgs` only if needed

This is what makes the command:
- detectable from text
- eligible for native slash export
- visible in `/commands`

### 2) Implement a focused handler

Create `src/auto-reply/reply/commands-<name>.ts`.

Typical shape:
- early return if text commands disabled
- early return if normalized command doesn’t match `/name`
- auth gate via `rejectUnauthorizedCommand(...)` if needed
- parse args minimally
- return `{ shouldContinue: false, reply: { text } }`

Prefer **bridging to existing logic** over reimplementation.

Examples:
- shell out to an existing Python/CLI script with `execFile`
- call an existing library/service helper
- keep formatting logic close to existing implementation if already standardized elsewhere

### 3) Wire into the command chain

In `commands-core.ts`:
- import the handler
- insert it into `HANDLERS`

Keep ordering intentional:
- before generic fallthrough
- near related info/status/tool handlers

### 4) Add minimal regression tests

At minimum cover:
- registry/list visibility (`/commands` rendering contains the command)
- handler routing (`/foo ...` reaches your handler and parses args as expected)

Good minimal test pattern:
- mock `node:child_process` if bridging to CLI/Python
- call `handleCommands(buildCommandTestParams(...))`
- assert invoked argv + reply text

## Acceptance checklist

- [ ] `commands-registry.data.ts` contains the new command entry
- [ ] `/commands` output includes the command
- [ ] text command detection works
- [ ] native name is set if native slash export is desired
- [ ] handler is connected in `commands-core.ts`
- [ ] auth gating is correct
- [ ] args route correctly
- [ ] tests cover registry visibility and execution path
- [ ] no duplicate business logic if an existing script/helper already exists

## Common pitfalls

### 1) Added handler, forgot registry entry
Result: command may work only in ad-hoc paths, but won’t appear in `/commands` or native registration.

### 2) Added registry entry, forgot handler
Result: command is detected and listed but falls through to agent flow.

### 3) Wrong scope / nativeName
If you want native slash command support, do not leave it text-only by accident.

### 4) Re-implementing existing business logic
If a Python/CLI script already exists, bridge to it first. Reimplementation increases drift.

### 5) Missing tests for descriptions
`/commands` assertions often depend on exact description strings from the registry.

### 6) Ad-hoc regex interception
Do not bolt text interception onto unrelated stages. Use the command registry + handler chain.

## Recommended implementation pattern

For existing external logic (best for MVP):
1. registry entry
2. handler file
3. `execFile` bridge to existing script
4. test mocked subprocess call

For pure in-repo logic:
1. registry entry
2. handler file
3. call existing TS helper/service
4. test reply payload

## Verification commands

From the repo root, usually:

```bash
pnpm vitest run src/auto-reply/commands-registry.test.ts src/auto-reply/reply/commands.test.ts src/auto-reply/status.test.ts
```

Or project standard test runner if customized in `package.json`.

## Deliverable template

When done, report:
- files changed
- command execution chain
- how to verify
- any blockers / follow-ups

## Example outputs to mention

- `/commands` now shows `/yourcommand`
- `/yourcommand --json` routes to existing implementation
- native slash metadata exported via `nativeName`
