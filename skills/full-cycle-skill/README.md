# full-cycle-skill

> Automated development skill for OpenClaw AI agents: idea → code → test → lint → 4-role parallel review → fix → PR

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-blue)](https://openclaw.ai)

---

## What is this?

A skill for [OpenClaw](https://openclaw.ai) that automates the full development cycle:

1. **Developer subagent** writes code, tests, fixes lint, updates docs
2. **4 parallel reviewers** (Python Dev / Architect / QA / Security) review the diff independently
3. **Orchestrator** (main session) aggregates results, counts blocking findings
4. **Fix subagent** (if needed) fixes all blocking findings
5. **PR created** — user sees only the final result

The cycle repeats review → fix up to 3 rounds. Each round reviewers only see the new diff.

## Pipeline

```
User: "full cycle для my-project implement feature X"
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  MAIN SESSION (silent orchestrator)                      │
│                                                          │
│  Step 1-3: [developer subagent]                         │
│    └─ git checkout -b feature/X                         │
│    └─ implement + tests (green) + lint (clean)          │
│    └─ update AGENTS.md + README                         │
│                                                          │
│  Step 4: [4 parallel review subagents]                  │
│    ├─ Developer role  ──┐                               │
│    ├─ Architect role  ──┤──► aggregate BLOCKING         │
│    ├─ QA/Tester role  ──┤    count                      │
│    └─ Security role   ──┘                               │
│    └─ Step 4e: Final inline review                      │
│                                                          │
│  Step 5: (if BLOCKING > 0)                              │
│    └─ [fix subagent] → fixes → re-review               │
│    └─ repeat up to 3 rounds                             │
│                                                          │
│  Step 6: gh pr create → output to user                  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
User sees: ✅ PR: https://github.com/...
```

See [docs/how-it-works.md](docs/how-it-works.md) for the full detailed pipeline.

## Quick Start

### 1. Install OpenClaw

See [openclaw.ai](https://openclaw.ai) or [docs.openclaw.ai](https://docs.openclaw.ai)

### 2. Install this skill

Copy `SKILL.md` to your OpenClaw workspace:

```bash
mkdir -p ~/.openclaw/workspace/skills/full-cycle
cp SKILL.md ~/.openclaw/workspace/skills/full-cycle/SKILL.md
```

Or install via clawhub (when published):

```
/install-skill full-cycle
```

### 3. Set up role prompts

The skill requires role prompts at `/opt/projects/llm-review-prompts/prompts/`:

```
prompts/
├── developer/   python.md | rust.md | dotnet.md | go.md
├── architect/   python.md | rust.md | dotnet.md | go.md
├── tester/      autotests.md
├── reviewer/    general.md
└── security/    general.md
```

See [docs/setup-for-agents.md](docs/setup-for-agents.md) for prompt templates.

### 4. Trigger

```
full cycle для <project> <task description>
```

Examples:
```
full cycle для gitlab-reviewer fix ruff lint (#11)
full cycle для my-api implement JWT authentication
full cycle для my-service refactor database layer
```

## How it works

See [docs/how-it-works.md](docs/how-it-works.md)

## Anti-freeze cron pattern

See [docs/cron-anti-freeze.md](docs/cron-anti-freeze.md)

## Adapting for your stack

See [docs/stack-customization.md](docs/stack-customization.md)

---

---

# full-cycle-skill (RU)

> Скилл автоматизации разработки для AI-агентов OpenClaw: идея → код → тесты → линтинг → 4 роли параллельного ревью → фикс → PR

## Что это?

Скилл для [OpenClaw](https://openclaw.ai), который автоматизирует полный цикл разработки:

1. **Developer-субагент** пишет код, тесты, исправляет линтинг, обновляет документацию
2. **4 параллельных ревьюера** (Python Dev / Архитектор / QA / Security) проверяют diff независимо
3. **Оркестратор** (главная сессия) агрегирует результаты, считает blocking-находки
4. **Fix-субагент** (при необходимости) исправляет все blocking
5. **Создаётся PR** — пользователь видит только финальный результат

Цикл повторяет ревью → фикс до 3 раундов. В каждом раунде ревьюеры видят только новый diff.

## Быстрый старт

### 1. Установить OpenClaw

Смотри [openclaw.ai](https://openclaw.ai) или [docs.openclaw.ai](https://docs.openclaw.ai)

### 2. Установить скилл

```bash
mkdir -p ~/.openclaw/workspace/skills/full-cycle
cp SKILL.md ~/.openclaw/workspace/skills/full-cycle/SKILL.md
```

### 3. Настроить промпты ролей

Скилл требует промпты ролей в `/opt/projects/llm-review-prompts/prompts/`:

```
prompts/
├── developer/   python.md | rust.md | dotnet.md | go.md
├── architect/   python.md | rust.md | dotnet.md | go.md
├── tester/      autotests.md
├── reviewer/    general.md
└── security/    general.md
```

Шаблоны промптов — в [docs/setup-for-agents.md](docs/setup-for-agents.md).

### 4. Запустить

```
full cycle для <проект> <описание задачи>
```

Примеры:
```
full cycle для gitlab-reviewer исправить ruff lint (#11)
full cycle для my-api реализовать JWT авторизацию
```

## Как работает

Смотри [docs/how-it-works.md](docs/how-it-works.md)

## Паттерн anti-freeze через cron

Смотри [docs/cron-anti-freeze.md](docs/cron-anti-freeze.md)

## Адаптация под свой стек

Смотри [docs/stack-customization.md](docs/stack-customization.md)
