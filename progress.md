# EnergyAI Progress Tracker

> Updated after every task. Single source of truth for project status.

## Status Legend
- TODO — Not started
- IN PROGRESS — Currently being worked on
- DONE — Completed and verified
- BLOCKED — Cannot proceed (see notes)

## Tasks

| Task | Status | Notes |
|---|---|---|
| 0. CLAUDE.md + progress.md + dev branch | DONE | Project initialized |
| 1. Project scaffold | DONE | Directory structure, requirements, conftest |
| 2. Configuration | DONE | config.py with model profiles, GPU detect, TTS flags |
| 3. Event bus | DONE | 4/4 tests passing |
| 4. Data generator | DONE | 86,400 rows, 173 calendar events, 8/8 tests |
| 4b. API docs for teammates | DONE | 3 docs (2548 lines): API_GUIDE, API_SPEC_FOR_AI, JSON_FORMATS |
| 5. Feature engine | DONE | 53 past / 10 future / 8 static features, 3/3 tests |
| 6. Model components (GRN/GLU/VSN) | DONE | 3 nn.Modules (GLU, GRN, VSN), 6/6 tests |
| 7. Attention | TODO | |
| 8. Encoder/decoder | TODO | |
| 9. Prediction heads | TODO | |
| 10. TFT assembly | TODO | |
| 11. Losses | TODO | |
| 12. Training pipeline | TODO | |
| 13. Inference engine | TODO | |
| 14. Grid/TOU rates | TODO | |
| 15. Calendar parser | TODO | |
| 16. Optimizer bridge | TODO | |
| 17. MILP optimizer | TODO | |
| 18. Optimizer orchestrator | TODO | |
| 19. Calendar generator | TODO | |
| 20. Ingestion layer | TODO | |
| 21. WebSocket manager | TODO | |
| 22. REST routes | TODO | |
| 23. Main app | TODO | |
| 24. Background scheduler + cache | TODO | |
| 25. LLM context | TODO | |
| 26. LLM chat | TODO | |
| 27. LLM narrator | TODO | |
| 27b. ElevenLabs TTS | TODO | |
| 28. Monte Carlo robustness | TODO | |
| 29. Demo mode controller | TODO | |
| 30. Wire event bus + update main | TODO | |
| 31. API docs (human) | TODO | |
| 32. API docs (AI) | TODO | |
| 33. WebSocket test page | TODO | |
| 34. Database layer | TODO | |
| 35. Smoke test script | TODO | |
| 36. Run all tests | TODO | |

## Checklists

### Pre-Hackathon
- [ ] DigitalOcean account created + $200 credits claimed
- [ ] ElevenLabs Discord joined + Creator Plan coupon redeemed
- [ ] Groq API key obtained
- [ ] SSH key uploaded to DigitalOcean
- [ ] RTX 4090 tested with PyTorch CUDA

### Demo Day
- [ ] Model trained (AMD or local GPU)
- [ ] Backend starts cleanly with DEMO_MODE=true
- [ ] TTS speaks insights aloud
- [ ] iOS app connects and receives WebSocket data
- [ ] Smoke test passes 9/9
