# Workflow

## Standard Pipeline

```
[1] Spawn Writer → wait for announce
    ↓
[2] Verify output in OUTPUT/{project}/
    ↓
[3] Parallel spawn: Reviewers → wait for ALL
    ↓
[4] Spawn Scorer → wait for announce
    ↓
[5] Read score-report.md → parse JSON → extract total_score
    ↓
[6] Decision:
    ├── score >= threshold → ✅ PASS
    ├── score < threshold AND round < max → spawn Fixer → back to [3]
    └── score < threshold AND round >= max → ❌ FAIL
```

## Spawn Patterns

### Writer
```javascript
sessions_spawn({
  agentId: "writer",
  runtime: "subagent",
  task: "Create content on: {topic}. Output to: OUTPUT/{project}/"
})
```

### Reviewers (Parallel)
```javascript
sessions_spawn({
  agentId: "fact-reviewer",
  task: "Review OUTPUT/{project}/article.md. Write review-fact.md"
})

sessions_spawn({
  agentId: "style-reviewer",
  task: "Review OUTPUT/{project}/article.md. Write review-style.md"
})
```

### Scorer
```javascript
sessions_spawn({
  agentId: "scorer",
  task: "Score OUTPUT/{project}/. Read article.md and review reports."
})
```

### Fixer
```javascript
sessions_spawn({
  agentId: "fixer",
  task: "Fix article{-vN}.md based on reviews. Output: article-v{N+1}.md"
})
```

## Reading Score Reports

Score report starts with JSON:
```json
{
  "total_score": 8.5,
  "publishable": true,
  "dimensions": { ... }
}
```

Extract by finding first `{` to matching `}`.

## Decision Gate

```
IF score >= threshold AND publishable:
    → Notify human: score + files
ELIF round < max_rounds:
    → Spawn fixer
    → Increment round
    → Back to reviewers
ELSE:
    → Notify human: highest score + issues
```

## Communication Rules

**Report to human**:
- ✅ Product passed
- ❌ Failed after max rounds
- ⚠️ Agent anomaly

**Don't bother human**:
- Normal running
- Mid-cycle progress
- File operations