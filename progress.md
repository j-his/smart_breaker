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
| 7. Attention | DONE | MultiHeadAttention + InterpretableAttention (shared V, averaged weights) |
| 8. Encoder/decoder | DONE | TemporalEncoder (2 layers) + TemporalDecoder (last layer interpretable) |
| 9. Prediction heads | DONE | 4 heads: QuantileForecast, NILM, AnomalyVAE, DayType |
| 10. TFT assembly | DONE | Full TFT wired, 383K params (CPU), 24/24 tests passing |
| 11. Losses | DONE | QuantileLoss, VAELoss, UncertaintyWeightedLoss — all verified |
| 12. Training pipeline | DONE | TFTTrainer + train_model.py + finetune_model.py, 5.2M params GPU, 80 epochs on RTX 5070 Ti |
| 13. Inference engine | DONE | InferenceEngine with debouncing, post-processing, real checkpoint verified |
| 14. Grid/TOU rates | DONE | PG&E E-TOU-C rates, CAISO solar/wind model, GridCache with TTL, 4/4 tests |
| 15. Calendar parser | DONE | iCal + JSON parsing, appliance inference from keywords, 4/4 tests |
| 16. Optimizer bridge | DONE | CalendarEvent ↔ MILP task dict conversion, 4/4 tests |
| 17. MILP optimizer | DONE | OR-Tools CP-SAT, cost+carbon objective, breaker constraint, 4/4 tests |
| 18. Optimizer orchestrator | DONE | End-to-end pipeline: grid→bridge→MILP→results, 3/3 tests |
| 19. Calendar generator | DONE | iCal export with moved-event annotations, WS envelope, 3/3 tests |
| 20. Ingestion layer | DONE | Pydantic validator, ring buffer, hardware fallback, receiver singletons — 9/9 tests |
| 21. WebSocket manager | DONE | ConnectionManager with async lock, broadcast, make_envelope — 3/3 tests |
| 22. REST routes | DONE | 10 endpoints: health, dashboard, forecast, schedule, tasks, calendar, sensor, settings, insights, attention — 7/7 tests |
| 23. Main app | DONE | FastAPI + CORS + WS /ws/live + /ws/chat + synthetic data loop — 3/3 tests |
| 24. Background scheduler + cache | DONE | optimization_loop (900s), grid_refresh_loop (300s), TTLCache — 4/4 tests |
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
