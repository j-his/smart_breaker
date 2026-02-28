# EnergyAI — Smart Home Energy Monitoring & Optimization

## Project Overview
EnergyAI is a smart home energy monitoring and optimization system built for Hack for Humanity 2026. Three-brain AI architecture: Brain 1 (ML/TFT) makes decisions, Brain 2 (LLM/Groq) explains them, Brain 3 (Voice/ElevenLabs) speaks them aloud. ESP32 hardware with 4-channel breaker box feeds real-time data to a Python/FastAPI backend that streams to an iOS app via WebSocket.

## GitHub Repository
https://github.com/j-his/smart_breaker

## Tech Stack
- Python 3.11+, FastAPI, PyTorch (ROCm + CUDA), Google OR-Tools
- Groq API (OpenAI SDK) — GPT-OSS 120B chat, GPT-OSS 20B narrator
- ElevenLabs SDK — eleven_flash_v2_5 TTS
- SQLite via aiosqlite, icalendar, pandas/numpy, Pydantic

## Plan & Reference Documents
- **Implementation plan:** See `IMPLEMENTATION_PLAN.md` in project root (also at parent directory level)
- **API guide (human):** `docs/API_GUIDE.md`
- **API spec (AI):** `docs/API_SPEC_FOR_AI.md`

**IMPORTANT:** When implementing any system, ALWAYS read the implementation plan first for exact code, test steps, and commit messages. Do not guess — the plan specifies everything.

## Pre-Step Protocol: Ask Before Building
**Before implementing EACH step**, the agent MUST:
1. Read the step requirements from the plan
2. Think about what's ambiguous (mechanics, edge cases, priorities)
3. Ask the user **at least 2 clarification questions** using AskUserQuestion before writing any subplan or code
4. Wait for answers before writing any code
5. Err on the side of asking too many questions rather than making assumptions

**This is non-negotiable.** Even if a task seems straightforward, find at least 2 meaningful questions to ask. Good questions reveal hidden assumptions and prevent rework.

## Superpowers Skills
**ALWAYS check and use superpowers skills before any task.** Key skills:
- `superpowers:brainstorming` — before any creative/feature work
- `superpowers:test-driven-development` — before writing implementation code
- `superpowers:systematic-debugging` — before fixing any bug
- `superpowers:verification-before-completion` — before claiming work is done
- `superpowers:requesting-code-review` — after completing major features
- `superpowers:executing-plans` — when implementing the plan
- `superpowers:dispatching-parallel-agents` — when 2+ independent tasks exist
- `superpowers:subagent-driven-development` — for parallel task execution

## Key Architecture Rules
1. **Three-brain separation** — ML (backend/ml/), LLM (backend/llm/), Voice (backend/tts/) are independent modules
2. **Event bus** for cross-system communication — never couple modules directly
3. **Async everything** — all I/O goes through asyncio, use AsyncElevenLabs/AsyncOpenAI clients
4. **Hardware fallback** — synthetic data kicks in automatically when ESP32 is offline
5. **Feature flags** — DEMO_MODE, ELEVENLABS_TTS_ENABLED, etc. in config.py
6. **Config is king** — ALL constants, API keys, model profiles live in backend/config.py

## GPU Training
- **Primary:** DigitalOcean MI300X (ROCm7) — `docker exec -it rocm bash` then train
- **Fallback:** Local RTX 4090 (CUDA) — `DEVICE=cuda python scripts/train_model.py`
- PyTorch ROCm uses the same `torch.cuda` API — no code changes between AMD and NVIDIA

## Parallel Sub-Step Development
For every task, analyze whether sub-steps can be developed in parallel:
1. Identify sub-tasks with no logical dependencies
2. If parallelizable: create separate git worktrees, develop simultaneously, merge sequentially
3. Always commit or stash uncommitted changes before creating worktree branches
4. Coordinator pre-defines shared contracts before dispatch

## Progress Tracking
- **Progress file:** `progress.md` in project root
- **ALWAYS update progress.md after completing each task/sub-task** — not just major steps
- Mark tasks as: TODO, IN PROGRESS, DONE, or BLOCKED
- Include brief notes about what was done
- This file is the single source of truth for project status

## Git Commit Rules
- **Do NOT add a Co-Authored-By line** to commit messages. No Opus co-author tags.
- Keep commit messages concise and descriptive.

## Git Branching Strategy
- **Main branch:** `main` — do NOT commit directly to main
- **Development sub-branch:** Work happens on a development sub-branch (e.g., `dev/backend`)
- **Feature branches:** Branch off the dev sub-branch for each task (e.g., `dev/backend/task-01-scaffold`)
- **Merge flow:** feature branch → dev sub-branch → main (only after all development is complete)
- **NEVER push directly to main** — all work merges to the dev sub-branch first
- When creating worktrees for parallel development, always branch from the dev sub-branch, not main

## Testing Protocol
- `python -m pytest tests/ -v` after every task — all tests must pass
- `python scripts/smoke_test.py` for end-to-end validation (requires server running)
- `docs/ws_test.html` for browser-based WebSocket testing

## Prize Tracks
| Track | Key Evidence |
|---|---|
| Grand Prize | Full 3-brain AI, real hardware, live demo |
| Future Unicorn | Revenue model, market size, live hardware product |
| Responsible AI | Interpretable attention, explainable decisions, carbon tracking |
| AMD (stretch) | Model trained on DigitalOcean MI300X |
| ElevenLabs | Voice Brain 3 speaks insights aloud |

## Build Order
Follow the numbered tasks in IMPLEMENTATION_PLAN.md sequentially. Each task has verify steps — complete them before moving on.
