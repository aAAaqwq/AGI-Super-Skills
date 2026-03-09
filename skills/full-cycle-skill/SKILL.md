---
name: Full Cycle Developer
slug: full-cycle
version: 3.0.0
description: >
  Full cycle mode: code → test → review → fix → push.
  Главная сессия молча оркестрирует всё: developer-субагент, 4 ревью-роли параллельно,
  fix-субагент. Пользователь видит только итоговый PR.
metadata: {"openclaw":{"requires":{"bins":["git"]}}}
---

## When to Use

Triggered when user says:
- "full cycle для [проект] [задача/issue]"
- "сделай full cycle"
- "работай в full cycle режиме"

## Prompts Location

All role prompts live in `/opt/projects/llm-review-prompts/prompts/`.
Select the right language variant based on project stack from `AGENTS.md`.

```
prompts/
├── developer/   dotnet | rust | python | go
├── architect/   dotnet | rust | python | go
├── tester/      manual | e2e | autotests
├── reviewer/    general
└── security/    general
```

---

## Execution Mode — ГЛАВНАЯ СЕССИЯ КАК ОРКЕСТРАТОР

Пользователь видит **только один итоговый Output**.
Главная сессия молча выполняет все шаги — без промежуточных сообщений.

### Схема оркестрации

```
ГЛАВНАЯ СЕССИЯ (молча)
│
├── Шаг 1-3: sessions_spawn(developer-субагент)  → ждёт → [diff, tests green]
│
├── Шаг 4: sessions_spawn × 4 (параллельно):
│   ├── Developer review  → sessionKey_dev
│   ├── Architect review  → sessionKey_arch
│   ├── Tester review     → sessionKey_test
│   └── Security review   → sessionKey_sec
│   └── Ждёт все 4 через subagents(action="list")
│   └── Забирает результаты через sessions_history
│
├── Шаг 4e: Final review — inline в главной сессии
│   (читает промпт reviewer/general.md + PREVIOUS_REVIEWS из 4 ролей)
│
├── Шаг 5: sessions_spawn(fix-субагент)
│   (передаёт агрегированные BLOCKING/MUST HAVE явно в task)
│   → ждёт → [tests green, commit]
│
└── Шаг 6: создаёт PR → Output пользователю
```

### Правила главной сессии

- **НЕ отправлять промежуточных сообщений** пользователю между шагами
- Вызовы инструментов идут молча — только итог
- Если что-то пошло не так → сообщить причину + что успело закоммититься

---

## Execution Pipeline

```
1-3. DEVELOP   — developer-субагент: INIT + код + тесты → green
4.   REVIEW    — 4 ревью-субагента параллельно → главная сессия агрегирует → Final inline
5.   FIX       — fix-субагент получает BLOCKING список явно → фиксит → тесты green
6.   PUSH      — главная сессия открывает PR → Output
```

---

## Шаг 1-3: Developer-субагент

Главная сессия спавнит субагент с task:

```
## DEVELOPER SUBAGENT — <project> <task>

INIT:
- git fetch origin && git pull origin main && git checkout -b <branch>
- Прочитать: AGENTS.md, docs/, ROADMAP.md
- memory_search("<project> architecture decisions")
- memory_search("<task topic> patterns")
- Загрузить TASK_CONTEXT из issue или описания

DEVELOP:
- Читать prompts/developer/<stack>.md
- Написать реализацию следуя Critical Rules из AGENTS.md

TEST:
- Читать prompts/tester/autotests.md
- Написать тесты — каждый тест должен падать при сломанной реализации
- Запустить тесты → должны быть green
- Не заканчивать пока тесты красные

LINT (обязательно для Python):
- python3 -m ruff check src/ tests/ 2>&1 | head -30
- Исправить все ошибки ruff перед коммитом
- Не коммитить с красным ruff

ЕСЛИ ROADMAP есть — прочитать, найти текущий пункт, запомнить для architect.

DOCS (ОБЯЗАТЕЛЬНО перед финальным коммитом):
- Обновить AGENTS.md: статус задачи, новые решения, pitfalls (раздел Status + Pitfalls)
- Если изменился публичный API или CLI — обновить README (EN + RU секция)
- Если архитектурное решение — добавить запись в docs/ или соответствующий .md
- Если ROADMAP.md / BACKLOG.md — отметить пункт выполненным (✅)
- Не коммитить реализацию без обновлённых доков

Output: один блок в конце:
BRANCH: <branch-name>
STACK: <python|rust|dotnet|go>
TESTS: <N passed>
LINT: ruff clean / <N errors>
DOCS: AGENTS.md updated / README updated / skipped (reason)
DIFF_SUMMARY: <3-5 строк что изменилось>
```

Таймаут: `runTimeoutSeconds=900`

После завершения — забрать `BRANCH`, `STACK`, `TESTS`, `DIFF_SUMMARY` из `sessions_history`.

---

## Шаг 4: 4 ревью-субагента параллельно

Получить diff:
```bash
cd <project_root> && git diff origin/main...<branch> 2>&1 | head -400
```

Прочитать промпты заранее (главная сессия):
```bash
cat /opt/projects/llm-review-prompts/prompts/developer/<stack>.md
cat /opt/projects/llm-review-prompts/prompts/architect/<stack>.md
cat /opt/projects/llm-review-prompts/prompts/tester/manual.md
cat /opt/projects/llm-review-prompts/prompts/security/general.md
```

Спавнить все 4 одновременно, каждый с task содержащим:
- Промпт роли (полный текст)
- PROJECT_CONTEXT (AGENTS.md)
- TASK_CONTEXT (описание + AC)
- DIFF (git diff)
- Инструкцию вернуть findings в конце одним блоком

**⚠️ Ограничение scope для ВСЕХ ролей (особенно Security):**
Проверять ТОЛЬКО изменения в DIFF. Pre-existing issues которые существовали до этого MR → не BLOCKING, оформить в MINOR-секции с пометкой `[pre-existing]`. Security не должен блокировать MR из-за проблем которые не введены текущим изменением.

### Task-шаблон для каждой роли

```
## <ROLE> REVIEW

<полный текст промпта роли>

---

PROJECT_CONTEXT:
<содержимое AGENTS.md>

TASK_CONTEXT:
<описание задачи + acceptance criteria>

DIFF:
<git diff>

---

Верни findings одним блоком в конце:
[BLOCKING/MINOR/CRITICAL/HIGH/MEDIUM/MUST HAVE/SHOULD HAVE]: описание, файл:строка, fix
Итого: X blocking, Y minor.
```

Таймаут каждого: `runTimeoutSeconds=1200`

### Ожидание всех 4

```python
# Собрать sessionKeys всех 4 субагентов
role_keys = {
    "developer": key_dev,
    "architect": key_arch,
    "tester":    key_test,
    "security":  key_sec,
}

# Ждать в цикле через subagents(action="list")
while True:
    active = subagents(action="list")["active"]
    active_keys = {s["sessionKey"] for s in active}
    if not any(v in active_keys for v in role_keys.values()):
        break
    exec("sleep 15")

# Забрать результаты
reviews = {}
for role, key in role_keys.items():
    hist = sessions_history(sessionKey=key, limit=2)
    reviews[role] = hist["messages"][-1]["content"]  # последнее сообщение
```

### Шаг 4b (Architect) + ROADMAP

В task для architect добавить:
```
Дополнительно: обнови ROADMAP.md
- Если ROADMAP.md есть → найди текущую задачу и отметь [x], добавь новые пункты если выявлены
- Если нет → создай ROADMAP.md (текущее состояние + ближайшие задачи + дальние планы)
Сохрани изменения: exec("cd <project_root> && git add ROADMAP.md && git commit -m 'docs: update ROADMAP'")
```

### Шаг 4e: Final Review (inline)

Главная сессия сама агрегирует и выносит вердикт:

Собрать PREVIOUS_REVIEWS:
```
## Developer Review
<reviews["developer"]>

## Architect Review
<reviews["architect"]>

## Tester Review
<reviews["tester"]>

## Security Review
<reviews["security"]>
```

Прочитать `prompts/reviewer/general.md`, применить к PREVIOUS_REVIEWS + DIFF.
Вынести вердикт: APPROVE / REQUEST_CHANGES.

---

## Шаг 5: Fix-субагент

Агрегировать все BLOCKING по таблице:

| Роль | Фиксить до MR | В issue |
|------|--------------|---------|
| Developer | BLOCKING | MINOR, SUGGESTION |
| Architect | BLOCKING | MINOR |
| Tester | MUST HAVE | SHOULD HAVE → issue |
| Security | CRITICAL, HIGH | MEDIUM → issue, LOW → ignore |

### Цикл fix → review (повторять до чистоты)

```
review_round = 1
MAX_ROUNDS = 3

while blocking_count > 0:
    if review_round > MAX_ROUNDS:
        → прервать, сообщить пользователю: "Не удалось устранить все BLOCKING за 3 итерации"
    fix_subagent(blocking_list)
    review_round += 1
    повторить шаг 4 (все 4 роли + 4e) → получить новый blocking_count
```

**После каждого fix-субагента — ОБЯЗАТЕЛЬНО повторить полное ревью шаг 4** (все 4 роли параллельно + 4e Final). Не считать ветку чистой только на основании "fix применён" — новые изменения могут внести новые BLOCKING.

Переходить к Step 6 только когда `blocking_count == 0` по результатам ревью.

### ⚠️ КРИТИЧЕСКОЕ ПРАВИЛО: НЕ ПРЕРЫВАТЬ ЦИКЛ

**Главная сессия НЕ должна отправлять промежуточные результаты ревью пользователю.**

Цикл `develop → review → fix → review → ...` выполняется полностью автономно.
Пользователь НЕ должен пинговать агента чтобы продолжить — это провал оркестрации.

Единственные случаи когда можно писать пользователю до PR:
1. `MAX_ROUNDS` исчерпан — объяснить что не получилось и передать управление
2. Фатальная ошибка (тесты красные и fix-субагент не может починить за 3 попытки)
3. Неоднозначность в задаче, которую нельзя разрешить без решения пользователя

Во всех остальных случаях — молча запустить следующий шаг.

### 🔔 Обязательный самопинг через cron (anti-freeze)

**Проблема:** главная сессия может "замереть" после запуска субагентов — completion event не всегда поднимает сессию. Без внешнего триггера цикл остановится.

**Правило:** запустил группу субагентов → сразу поставил два cron. Без исключений.

**Тайминг cron-ов:**

| Тип субагентов | Таймаут | Cron 1 | Cron 2 |
|---|---|---|---|
| 4 ревью-роли | 1200s (20 мин) | T + 20 мин | T + 23 мин |
| Fix-субагент | 600s (10 мин) | T + 12 мин | T + 15 мин |

Логика: cron должен срабатывать **после ожидаемого завершения**, не во время.

**Шаблон cron-текста:**

```
Full-cycle самопинг: раунд {N} ревью <project>/<branch>.
Проверь subagents list (labels содержат '<role>').

Если ВСЕ done → агрегируй sessions_history, подсчитай blocking.
  blocking > 0 → запусти fix-субагент (не пиши пользователю).
  blocking = 0 → создай PR → напиши пользователю итог.

Если ЕСТЬ active → удали этот cron, поставь новый на T+5 мин с тем же текстом.

НЕ пиши пользователю пока нет финального результата (PR или фатальная ошибка).
```

**Самопереносящаяся логика (если субагенты ещё active):**
```python
# В тексте systemEvent cron должен содержать инструкцию:
# "если active → удали себя (cron remove), поставь новый cron на now+5min"
# Это обеспечивает polling без busy-loop
```

- `deleteAfterRun: true` — каждый cron однократный
- Два cron-а: если первый не поднял сессию — второй сработает через 3 мин
- Если главная сессия уже продолжила сама — cron сработает на пустом subagents list → no-op (subagents done, PR уже есть или fix уже запущен)
- Не использовать cron когда субагенты уже вернули результаты в активную сессию — агрегировать немедленно

### Как проверять BLOCKING перед fix-субагентом

Перед тем как запускать fix-субагент, **проверить реальный код** (не доверять слепо выводу ревьюеров):
- Открыть файлы, упомянутые в BLOCKING findings
- Убедиться что проблема действительно есть в коде, а не false alarm
- Ревьюеры без доступа к исходникам часто ошибаются (анализируют по диффу)
- False alarms не нужно фиксить — они не BLOCKING

Это экономит раунды и не вносит лишних изменений в код.

Если BLOCKING = 0 с первого раза → fix-субагент не нужен, сразу Step 6.

Если BLOCKING > 0 → спавнить fix-субагент с task:

```
## FIX SUBAGENT — <project> <branch>

cd <project_root> && git checkout <branch>

Исправить следующие BLOCKING findings:

<нумерованный список с файл:строка и конкретным fix для каждого>

После каждого fix — запустить тесты:
<команда запуска тестов>
Не коммитить пока тесты красные.

Запустить линтер (Python):
python3 -m ruff check src/ tests/ 2>&1 | head -30
Исправить все ошибки ruff. Не коммитить с красным ruff.

Обновить документацию (ОБЯЗАТЕЛЬНО):
- AGENTS.md: добавить найденные pitfalls, обновить статус
- README / docs: если fix затронул поведение — обновить соответствующую секцию

После всех fix:
git add -A
git commit -m "fix: <краткое описание>"
git push https://KoshelevDV:$(gh auth token)@github.com/KoshelevDV/<repo>.git <branch>

Создать сводный issue для MINOR/MEDIUM:
gh issue create --repo KoshelevDV/<repo> \
  --title "Minor: <feature>" \
  --body "<список>"

Output в конце:
TESTS: <N passed>
LINT: ruff clean / <N errors>
FIXES: <N blocking fixed>
ISSUE: <url или none>
```

Таймаут: `runTimeoutSeconds=600`

---

## Шаг 5.5: Обновление документации (после fix, перед PR)

После того как blocking_count == 0 и тесты зелёные — обновить документацию проекта:

```bash
cd <project_root>

# 1. AGENTS.md — обновить статус, стек, питфолы, новые решения
# Добавить в секцию Status: что реализовано, что изменилось
# Добавить в Pitfalls: нетривиальные находки из ревью

# 2. README.md — если добавлены новые возможности (config options, API endpoints, etc.)
# Обновить секцию конфигурации, добавить пример использования новой фичи

# 3. Коммит документации
git add AGENTS.md README.md
git commit -m "docs: update AGENTS.md and README for <feature>"
git push ...
```

**Что обновлять в AGENTS.md:**
- `## Status` — отметить фичу как реализованную
- `## Pitfalls` — добавить нетривиальные ограничения, найденные в ходе ревью
- Стек, если добавились новые зависимости

**Что обновлять в README.md:**
- Новые config options (с примером YAML)
- Новые API endpoints
- Изменения в поведении

Если ничего принципиально не изменилось (только внутренние фиксы) — достаточно AGENTS.md.

---

## Шаг 6: PUSH + Output

Главная сессия создаёт PR:
```bash
gh pr create \
  --title "<type>: <description>" \
  --body "..." \
  --base main --head <branch>
```

Затем отправляет **единственное сообщение пользователю**:

```
✅ Full cycle завершён — <project> / <branch>

Tests:   <N passed / Y total>
Commits: <N>

Self-review:
  Developer  — <N blocking fixed, M minor → issue>
  Architect  — <N blocking fixed>
  QA/Manual  — <N ACs covered, M missing → issue>
  Security   — CLEAR / <N critical fixed>
  Final      — APPROVE ✅ / REQUEST_CHANGES ⚠️

PR: <url>
Issues: <url или none>
```

---

## Severity Table (обязательно)

| Роль | = BLOCKING | → issue |
|------|-----------|---------|
| Developer | BLOCKING | MINOR, SUGGESTION |
| Architect | BLOCKING | MINOR |
| Tester | MUST HAVE | SHOULD HAVE, NICE TO HAVE |
| Security | CRITICAL, HIGH | MEDIUM, LOW |

**MUST HAVE от tester = BLOCKING** — недостающий тест для AC = незавершённая фича.

---

## Rules

- **НЕ отправлять промежуточных сообщений** пользователю (только итог)
- **Никогда не пушить с красными тестами**
- **BLOCKING и CRITICAL/HIGH фиксить до MR**
- **MINOR → один сводный issue, не коммит**
- **docs/ читать всегда** в developer-субагенте
- **TASK_CONTEXT обязателен** — без него developer-субагент не начинает
- **git fetch перед checkout** — всегда от актуального remote
