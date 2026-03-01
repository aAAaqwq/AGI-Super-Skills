# Deployment Profile Intake

Use this only when the user wants help with local models, councils, OpenClaw routing, or deployment design.

## Core questions

### Host layout
- primary host: laptop / desktop / home server / VPS / mixed
- always-on host available: yes / no
- local-only, remote-only, or hybrid setup
- one machine or several machines

### Operating system
- OS and version
- containerization available: yes / no
- sandboxing constraints
- filesystem / path constraints if relevant

### Compute
- CPU model / core count
- RAM
- GPU model
- VRAM
- storage type and free space

### Runtime
- target max decision latency
- acceptable cloud dependency
- privacy constraints
- internet reliability
- power / sleep constraints

### OpenClaw / agent capabilities
- web_search available
- web_fetch available
- browser available
- cron available
- node host available
- sub-agents available
- separate worker agents available

## Routing heuristics

### Keep it simple when:
- no always-on host
- weak local hardware
- tiny account
- no strong need for local inference
- user mainly wants strategy review

### Consider mixed local/cloud when:
- always-on host exists
- user wants strategic critique plus deterministic execution
- local hardware can support light or medium local models
- browser / web collection is needed regularly

### Consider councils only when:
- user already has a complex stack, or
- the strategy genuinely benefits from multiple viewpoints, or
- there is a need for explicit critique / synthesis / veto roles

## Deployment anti-patterns

Reject or warn on:
- cloud reasoning inside per-trade hot path
- no-cache repeated expensive calls
- no degradation mode
- one giant agent doing everything with no separation of concerns
- complex councils on tiny accounts with no measurable edge benefit
