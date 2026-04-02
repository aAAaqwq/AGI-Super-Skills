# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIGC-Claw is an AI video generation system that transforms user ideas into complete videos through 6 stages: Script → Character/Scene Design → Storyboard → Reference Images → Video Generation → Post-production.

This repository (`aigc-director/`) is an **OpenClaw Agent Skill** that wraps the actual code project:
- **aigc-claw/**: The actual code project containing the backend (Python FastAPI) and frontend (Next.js)
- **SKILL.md**: Workflow rules for the OpenClaw agent
- **references/**: API documentation

Both run locally: backend at `http://localhost:8000`, frontend at `http://localhost:3000`.

## Commands

### Backend
```bash
cd aigc-claw/backend
source venv/bin/activate
python api_server.py
```

### Frontend
```bash
cd aigc-claw/frontend
npm install  # first time only
npm run build
npm start
```

### Health Check
```bash
curl http://localhost:8000/api/health
```

## Architecture

### Backend Core
- **[orchestrator.py](aigc-claw/backend/core/orchestrator.py)**: Workflow engine managing the 6-stage state machine. Controls session state (idle/running/waiting_in_stage/stage_completed/session_completed), persists to `aigc-claw/backend/code/data/sessions/`, and coordinates agent execution.

- **[base_agent.py](aigc-claw/backend/core/agents/base_agent.py)**: Abstract base class for all stage agents. Defines `process(input_data, intervention)` interface that returns `{"payload": ..., "requires_intervention": bool, "stage_completed": bool}`.

### 6 Stage Agents
Each agent handles one workflow stage:
| Agent | File | Stage |
|-------|------|-------|
| ScriptWriterAgent | script_agent.py | script_generation |
| CharacterDesignerAgent | character_agent.py | character_design |
| StoryboardAgent | storyboard_agent.py | storyboard |
| ReferenceGeneratorAgent | reference_agent.py | reference_generation |
| VideoDirectorAgent | video_agent.py | video_generation |
| VideoEditorAgent | editor_agent.py | post_production |

### Tool Clients
External API integrations in `aigc-claw/backend/tool/`:
- **LLM clients**: llm_dashscope.py, llm_deepseek.py, llm_gpt.py, llm_gemini.py
- **Image clients**: image_dashscope.py, image_client.py (Seedream, Jimeng, Wan)
- **Video clients**: video_wan.py, video_kling.py (Wan, Kling)
- **VLM clients**: vlm_dashscope.py, vlm_gemini.py

### Data Storage
- Results: `aigc-claw/backend/code/result/` (image/, video/, script/)
- Session state: `aigc-claw/backend/code/data/sessions/{session_id}.json`

## Workflow (from SKILL.md)

The system uses **9 stop points** where the agent MUST pause and wait for user confirmation before proceeding:

1. Project config confirmation
2. Script suggest_expand (optional)
3. Script logline selection
4. Script mode selection (movie/micro-film)
5. Script generation confirmation
6. Character/scene design confirmation
7. Storyboard confirmation
8. Reference image confirmation
9. Video clip confirmation

After each stage completes, the agent must:
1. Get artifact via `GET /api/project/{session_id}/artifact/{stage}`
2. Present results to user
3. Wait for user confirmation
4. Call `POST /api/project/{session_id}/continue` to proceed

## Key References

The `references/` folder contains detailed API documentation:
- `run_project/` - Service startup instructions
- `workflow/` - 6-stage workflow API docs
- `sandbox/` - Single-shot tools (image generation, video generation)
- `send_message/` - Feishu/WeChat integration

Important files:
- [SKILL.md](SKILL.md) - Contains the complete workflow rules for OpenClaw agent execution
- [README.md](README.md) - Full project documentation including model configuration