# Agent Instructions Analysis

You are analyzing a developer's AI coding assistant instructions (agents.md) against their actual commit history to find gaps and suggest improvements.

## Project Context

**Project:** {{ project_name }}
**Repository:** {{ repository }}
**Analysis Period:** Last {{ days }} days
**Total Commits:** {{ commit_count }}

## Current Agent Instructions

```markdown
{{ agent_content }}
```

## Commit Pattern Summary

### Commit Types
{{ commit_types }}

### Most Changed Files/Directories
{{ file_patterns }}

### Detected Pain Points
- Reverts/fix commits: {{ revert_count }}
- "Fix typo" or similar: {{ typo_fix_count }}
- Repeated patterns: {{ repeated_patterns }}

### Commit Message Samples
{{ commit_samples }}

## Your Task

Analyze the agent instructions against the commit patterns and identify:

1. **GAPS** - Things the developer does frequently but hasn't documented in their agent instructions
   - Look for commit patterns not reflected in instructions
   - Consider file types worked on but not mentioned
   - Note testing/documentation habits

2. **STRENGTHS** - Instructions that seem to be working well
   - Look for areas with clean commits, no reverts
   - Consistent patterns matching instructions

3. **RECOMMENDATIONS** - Specific additions to improve the agent instructions
   - Be concrete and actionable
   - Use the same style/tone as existing instructions
   - Focus on high-impact improvements

## Output Format

Return JSON:

```json
{
  "gaps": [
    {
      "area": "Testing",
      "observation": "31% of commits touch test files, but testing not mentioned in instructions",
      "impact": "high",
      "suggestion": "Add section: '## Testing\\n- Write unit tests for new functions\\n- Run tests before committing'"
    }
  ],
  "strengths": [
    {
      "area": "TypeScript",
      "observation": "Instructions mention strict mode, and 0 type-related fixes in history",
      "instruction": "Use TypeScript strict mode"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "section": "## Testing",
      "content": "- Write unit tests for all new functions\n- Run `npm test` before committing\n- Aim for 80% coverage on new code"
    }
  ],
  "summary": "Your agents.md covers architecture well but lacks guidance on testing and error handling, which account for 40% of your commits."
}
```

## Guidelines

- Be specific - reference actual commit patterns
- Be constructive - focus on improvements, not criticism
- Be practical - suggest things that will actually help
- Match the existing style of the agent file
- Prioritize by impact (what causes most rework?)

Return ONLY the JSON, no additional text.
