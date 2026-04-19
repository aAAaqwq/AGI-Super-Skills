# Contributing to AGI Super Team

Thank you for your interest in contributing! This guide covers how to add skills, agents, and improvements.

## Adding a Skill

### Directory Structure
```
skills/
└── your-skill-name/
    └── SKILL.md          # Required: skill definition
    └── scripts/          # Optional: helper scripts
    └── assets/           # Optional: images, templates
```

### SKILL.md Format
```markdown
# Skill Name

One-line description of what this skill does.

## When to Use
- Trigger condition 1
- Trigger condition 2

## Instructions
Step-by-step guidance for the AI agent.

## Examples
Concrete usage examples.
```

### Guidelines
- **One skill = one purpose** — keep it focused
- **Concrete, not vague** — include specific commands, file paths, parameters
- **Language**: English or Chinese, pick one per skill (don't mix)
- **No credentials**: never include API keys, tokens, or passwords
- **No binary files > 1MB**: use links to external assets instead
- **Test locally**: verify the skill works with OpenClaw before submitting

## Adding an Agent

### Directory Structure
```
agents/
└── your-agent-id/
    ├── SOUL.md          # Required: personality, mentor, philosophy
    ├── AGENTS.md        # Required: role, responsibilities, collaboration
    └── TOOLS.md         # Optional: skill index with ../skills/ links
```

### Guidelines
- Each agent should have a distinct **spirit mentor** that shapes their thinking style
- Include a 32-thinking framework skill if possible
- Reference skills via relative paths (`../skills/skill-name/`)
- Keep SOUL.md concise — personality, not documentation

## Reporting Issues

When reporting bugs, include:
1. What you expected to happen
2. What actually happened
3. OpenClaw version and model you're using
4. Any relevant logs or error messages

## PR Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit with clear messages: `git commit -m "add: new skill for X"`
4. Push and open a PR
5. Respond to review feedback

## Code of Conduct

- Be respectful and constructive
- Focus on the technical merit of contributions
- No personal attacks or political content in skills
- Keep skills vendor-neutral where possible

Thank you for making this project better! 🚀
