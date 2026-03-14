---
name: experiment-runner-run
description: Run survival arena experiments
---
# Experiment Runner (proj-012)

> Adaptive experiment runner for survival arena. Runs experiments one by one, analyzes results, commits. Between experiments -- human/AI decides what to change next.

## Workflow (adaptive)

```
1. --status        → view what's been done
2. --next          → run the next pending experiment
3. Analysis        → view analysis.json, understand the result
4. Decision        → what to change? (only environment conditions, not behavior)
5. Edit YAML       → modify the next experiment or add a new one
6. Repeat from #2
```

**Rule:** we only change conditions (pressure, resources, architecture). Never hardcode agent behavior.

## When to use

- "run experiment" / "next experiment"
- "what is the experiment status"
- "run EXP-011c"
- "run the next 2 experiments"
- proj-012 experiment pipeline

## Dependencies

- Python 3, PyYAML (`pip install pyyaml`)
- Claude CLI (for LLM queries in the arena)
- Git (for committing results)

## Paths

| What | Path |
|------|------|
| Arena | `$AGENTS_PATH/survival-arena/arena.py` |
| Orchestrator | `$AGENTS_PATH/survival-arena/run_experiments.py` |
| Plan (YAML) | `$AGENTS_PATH/survival-arena/experiments.yaml` |
| Results | `$AGENTS_PATH/survival-arena/experiment_results.json` |
| Logs | `$AGENTS_PATH/survival-arena/logs/experiments/` |
| Documentation | `$PROJECT_ROOT/projects/docs/proj-012-agi-consciousness/` |

## How to execute

### Next experiment (main mode)

```bash
cd $AGENTS_PATH/survival-arena
python3 run_experiments.py --next
```

### Next N experiments

```bash
python3 run_experiments.py --next 2
```

### View status

```bash
python3 run_experiments.py --status
```

### Run a specific experiment

```bash
python3 run_experiments.py --experiment EXP-011c
```

### Run all pending (batch mode)

```bash
python3 run_experiments.py --resume
```

### View commands without running

```bash
python3 run_experiments.py --dry-run --next 3
```

### Check arena config

```bash
python3 arena.py --config-dump --upkeep-base 0 --architecture single
```

## arena.py parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--upkeep-base N` | Pressure: maintenance cost per turn | 2 |
| `--regen-rate N` | Resource regeneration rate per turn | 3 |
| `--num-nodes N` | Number of resource nodes (distributed across clusters) | 12 |
| `--child-ratio F` | Child token share | 0.35 |
| `--repro-threshold N` | Reproduction threshold | 120 |
| `--repro-cost N` | Reproduction cost | 70 |
| `--architecture TYPE` | single / dual-same / dual-split / dual-kahneman | dual-kahneman |
| `--experiment-id ID` | Identifier for logs | - |
| `--config-dump` | Show config as JSON and exit | - |
| `--model MODEL` | haiku / sonnet | sonnet |
| `--turns N` | Number of turns | 50 |
| `--seed N` | Random seed | - |
| `--parallel N` | Parallel LLM calls | 4 |

## run_experiments.py parameters

| Parameter | Description |
|-----------|-------------|
| `--next [N]` | Run next N pending (default: 1) |
| `--status` | Show status and exit |
| `--phase P2` | Run a specific phase |
| `--experiment EXP-011c` | Run a single experiment |
| `--resume` | Run all pending (batch) |
| `--dry-run` | Show commands without executing |
| `--plan FILE` | Path to experiments.yaml |

## Phases (roadmap, adapts as we go)

| Phase | What we test | Initial experiments |
|-------|-------------|---------------------|
| P1 | Validation of v4.2c (map + clusters) | 3 |
| P2 | Yerkes-Dodson (pressure) | 5 |
| P3 | Architecture (phase transition) | 4 |
| P4 | Emergent parenting | 3 |
| P5 | Model phenotypes | 4 |
| P6 | Long evolution (200t) | 2 |

## What the orchestrator does for each experiment

1. Reads config from experiments.yaml (merge: defaults < phase < experiment)
2. Builds CLI command for arena.py
3. Runs subprocess, timeout 2 hours
4. Analyzes JSONL
5. Saves to `logs/experiments/EXP-XXX/` (config.json, analysis.json, console.txt)
6. Updates experiment_results.json
7. Commits to git
8. On error -- retries 2 times, 30s backoff

## Analysis results

For each experiment computes:
- Shannon entropy (action distribution diversity)
- Social action % (TRADE + COMMUNICATE + REPRODUCE)
- MOVE+GATHER % (survival focus)
- GATHER success rate (v4.2c: do agents understand the map)
- MOVE % (migration to clusters)
- Dual-system distribution (panic/normal/strategic %)
- Parent-child trades
- NAP detection (alliance/pact/peace keywords)
- Population dynamics (start/end/max/min)
- Reproductions count
- Max generation reached

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pyyaml not found` | `pip3 install pyyaml` |
| Timeout on 200t experiment | Increase timeout in run_experiments.py (7200 -> 14400) |
| Rate limit from API | Decrease `--parallel` (4 -> 2) |
| Cannot find log | Check that arena.py creates a file in logs/ |
| Git commit failed | Check that you're on main, no conflicts |

## Related skills

- `git-workflow` -- commit procedure
