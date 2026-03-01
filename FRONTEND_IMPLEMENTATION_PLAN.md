# Frontend Implementation Plan — EnergyAI iOS App

> **Branch:** `dev/frontend`
> **Starting point:** Backend 100% complete (115 tests), iOS app ~30% complete (UI shells, data models, zero networking)

---

## Current State

### What Exists (from `origin/ios`)
- SwiftUI tab-based app: Device, Calendar, Settings, About
- All Codable data models matching API types (Models.swift)
- 3 ViewModels (Device, Calendar, Settings) with @Published state
- Demo data generators for all model types
- Channel power cards, grid status display, optimization summary
- 24h forecast horizontal scroll, optimization weight sliders
- Xcode project compiles and runs with mock data

### What's Missing
- **Zero networking code** — no URLSession, no API client, no error handling
- **Zero WebSocket code** — no live data streaming, no chat
- **Chat UI** — no view or ViewModel for Brain 2 (LLM) interaction
- **Insights display** — model exists but no UI to show insights
- **Anomaly alert UI** — no push/local notification handling
- **TTS audio playback** — no AVFoundation integration for Brain 3 voice
- **Calendar import flow** — no .ics file picker or upload
- **Loading/error states** — views assume data is always present
- **Settings persistence** — nothing saved to UserDefaults or backend

---

## Implementation Tasks

### Task F1: API Client Foundation
**Goal:** Create a reusable networking layer that all views share.

**Files to create:**
- `breakerios/breakerios/Services/APIClient.swift` — singleton with base URL, JSON decoder, generic request methods
- `breakerios/breakerios/Services/APIError.swift` — typed error enum (network, decoding, serverError, unauthorized)

**Endpoints to wrap:**
| Method | Path | Used By |
|--------|------|---------|
| GET | `/api/health` | Settings (connection test) |
| GET | `/api/dashboard` | DeviceView |
| GET | `/api/forecast` | CalendarView |
| GET | `/api/schedule` | CalendarView |
| GET | `/api/insights` | InsightsView (new) |
| GET | `/api/attention` | InsightsView (new) |
| POST | `/api/sensor` | Hardware bridge (future) |
| POST | `/api/settings` | SettingsView |
| POST | `/api/tasks` | CalendarView (Add Task) |
| POST | `/api/calendar/import` | CalendarView (import flow) |

**Key decisions:**
- async/await with URLSession (no third-party deps)
- Configurable base URL from SettingsViewModel
- Automatic snake_case ↔ camelCase key conversion via JSONDecoder strategy

---

### Task F2: WebSocket Manager — Live Data Stream
**Goal:** Real-time sensor data and grid updates via `/ws/live`.

**Files to create:**
- `breakerios/breakerios/Services/WebSocketManager.swift` — URLSessionWebSocketTask wrapper

**Behavior:**
- Connect to `ws://{host}:8000/ws/live`
- Parse envelope: `{ "type": "...", "data": {...}, "ts": "..." }`
- Route by type: `sensor_update`, `grid_update`, `forecast_update`, `optimization_update`, `insight`, `anomaly_alert`, `tts_chunk`, `tts_final`
- Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s)
- Publish decoded payloads via Combine publishers or @Published properties
- DeviceViewModel subscribes to sensor_update + grid_update
- CalendarViewModel subscribes to optimization_update + forecast_update

---

### Task F3: WebSocket Manager — Chat Stream
**Goal:** Bidirectional chat with Brain 2 (LLM) via `/ws/chat`.

**Files to create/modify:**
- Extend `WebSocketManager` or create `ChatWebSocketManager.swift`

**Protocol:**
- Client sends: `{ "message": "user text here" }`
- Server streams back: `{ "type": "chat_token", "data": { "token": "..." } }` (per-token streaming)
- Server sends final: `{ "type": "chat_done", "data": { "full_response": "..." } }`
- Handle `chat_error` envelope type

---

### Task F4: Wire DeviceView to Live Data
**Goal:** Replace demo data in DeviceViewModel with real WebSocket stream.

**Changes to `DeviceView.swift`:**
- Inject WebSocketManager
- Replace `startMonitoring()` timer with WebSocket subscription
- Update channels from `sensor_update` envelopes
- Update gridSnapshot from `grid_update` envelopes
- Show connection state from WebSocketManager.isConnected
- Add loading skeleton when no data received yet
- Add error banner when disconnected

---

### Task F5: Wire CalendarView to REST + Live Updates
**Goal:** Load schedule/forecast from REST, receive live optimization updates.

**Changes to `CalendarView.swift`:**
- On appear: fetch GET `/api/forecast` and GET `/api/schedule`
- Subscribe to `optimization_update` and `forecast_update` from WebSocket
- Wire "Add Task" sheet to POST `/api/tasks`
- Add pull-to-refresh
- Add loading and error states

---

### Task F6: Wire SettingsView to Backend
**Goal:** Persist settings to backend and validate connection.

**Changes to `SettingsView.swift`:**
- `testConnection()` → call GET `/api/health`, parse response
- Save button → POST `/api/settings` with `{ alpha, beta, channel_configs }`
- Persist serverURL to UserDefaults
- Show success/failure feedback

---

### Task F7: Calendar Import Flow
**Goal:** Let users import .ics calendar files for schedule optimization.

**New UI in CalendarView:**
- "Import Calendar" button
- Document picker (UTType.calendarEvent) via UIDocumentPickerViewController
- Upload raw .ics data to POST `/api/calendar/import`
- Show imported events in the optimization list
- Handle errors (invalid format, no deferrable events found)

---

### Task F8: Chat UI (Brain 2 — LLM)
**Goal:** New tab or sheet for conversational AI interaction.

**Files to create:**
- `breakerios/breakerios/ChatView.swift` — chat bubble UI + input field
- `breakerios/breakerios/ChatViewModel.swift` — manages ChatWebSocketManager

**Features:**
- Message list with user/assistant bubbles
- Streaming token display (typewriter effect)
- Auto-scroll to bottom on new messages
- Send button + keyboard handling
- Context: chat is aware of current energy state (dashboard data sent as context)

**Navigation:** Add as 5th tab or as a floating button/sheet accessible from any tab

---

### Task F9: Insights & Anomaly Alerts
**Goal:** Display Brain 2 insights and handle anomaly notifications.

**Files to create:**
- `breakerios/breakerios/InsightsView.swift` — list of insight cards
- `breakerios/breakerios/InsightsViewModel.swift`

**Data sources:**
- REST: GET `/api/insights` for historical insights
- WebSocket: `insight` envelope type for live insights
- WebSocket: `anomaly_alert` envelope type for urgent alerts

**UI:**
- Insight cards with severity color coding (info=blue, warning=yellow, critical=red)
- Anomaly alerts as banners or modal alerts
- Optional: integrate into DeviceView as a collapsible section

---

### Task F10: TTS Audio Playback (Brain 3 — Voice)
**Goal:** Play spoken insights from ElevenLabs TTS stream.

**Integration:**
- WebSocket `tts_chunk` events contain base64-encoded audio fragments
- WebSocket `tts_final` signals end of utterance
- Decode base64 → Data → AVAudioPlayer or AVAudioEngine
- Queue chunks for gapless playback
- Settings toggle: enable/disable voice narration
- Visual indicator when TTS is playing

---

### Task F11: Loading States & Error Handling
**Goal:** Polish all views with proper loading/error/empty states.

**Per-view changes:**
- Loading: skeleton shimmer or ProgressView while awaiting first data
- Error: retry button + error description banner
- Empty: friendly message when no schedule/insights exist yet
- Network offline: persistent banner with reconnection status

---

### Task F12: Polish & Demo Prep
**Goal:** Final touches for hackathon demo.

- Ensure demo mode works without backend (toggle in Settings)
- App icon and launch screen
- Smooth animations and transitions
- Test on physical device
- Prepare demo script showing all 3 brains in action

---

## Suggested Build Order

```
F1 (API Client) ──→ F4 (Device wiring) ──→ F11 (Loading states)
       │                                          │
       ├──→ F5 (Calendar wiring) ──→ F7 (Import)  ├──→ F12 (Polish)
       │                                          │
       └──→ F6 (Settings wiring)                  │
                                                   │
F2 (WS Live) ──→ F4 (Device wiring)               │
       │                                          │
       └──→ F9 (Insights) ──→ F10 (TTS) ──────────┘

F3 (WS Chat) ──→ F8 (Chat UI) ────────────────────┘
```

**Critical path:** F1 → F2 → F4 → F5 → F8 → F11 → F12

**Parallelizable pairs:**
- F1 + F2 (REST client and WebSocket manager are independent)
- F4 + F6 (Device wiring and Settings wiring touch different files)
- F8 + F9 (Chat UI and Insights UI are independent views)
- F7 + F10 (Calendar import and TTS are independent features)

---

## File Structure (Target)

```
breakerios/breakerios/
├── breakeriosApp.swift
├── ContentView.swift
├── Models.swift
├── Views/
│   ├── DeviceView.swift        (existing, modified)
│   ├── CalendarView.swift      (existing, modified)
│   ├── SettingsView.swift      (existing, modified)
│   ├── AboutView.swift         (existing, unchanged)
│   ├── ChatView.swift          (new)
│   └── InsightsView.swift      (new)
├── ViewModels/
│   ├── DeviceViewModel.swift   (extracted from DeviceView)
│   ├── CalendarViewModel.swift (extracted from CalendarView)
│   ├── SettingsViewModel.swift (extracted from SettingsView)
│   ├── ChatViewModel.swift     (new)
│   └── InsightsViewModel.swift (new)
└── Services/
    ├── APIClient.swift         (new)
    ├── APIError.swift          (new)
    └── WebSocketManager.swift  (new)
```

> **Note:** ViewModels are currently embedded inside their view files. They can be extracted to separate files as part of each task or as a dedicated refactor step.
