# Frontend Implementation Plan — Full Pipeline Wiring

## Context

The backend is 100% complete (115/115 tests, all REST + WebSocket contracts implemented). The iOS app is ~30% done — good SwiftUI UI shells and Codable data models, but zero networking. This plan wires every view to the backend so the entire frontend-backend pipeline works end-to-end. After this, the only remaining integration is the ESP32 hardware, which should be plug-and-play since both sides follow the same API spec.

**Key constraints:**
- Preserve all of the teammate's aesthetic choices (colors, typography, spacing, component patterns, no explicit animations)
- Keep ViewModels embedded in their view files (match existing pattern)
- 5 tabs: Device, Calendar, Insights, Settings, About — Chat is a floating button/sheet from any tab
- TTS: accumulate audio chunks then play once complete
- Test with backend DEMO_MODE=true + add XCTest unit tests for networking layer
- Hardware integration must be plug-and-play later (iOS never talks to ESP32 directly — only to the backend)

## Execution Protocol

**For EACH step below**, the agent MUST:
1. Read the step requirements from this plan
2. Ask the user **at least 3 clarifying questions** before writing code
3. Wait for answers, then create a detailed subplan for the step
4. Implement the step
5. Commit and push after each step completes
6. Update `progress.md` with the step status
7. Verify the step works (build, test, or manual check)

**Branch:** All work on `dev/frontend`

---

## Step 1: Add New Models to Models.swift

**File:** `breakerios/breakerios/Models.swift`
**Action:** Append new types after the existing demo data extensions. Do NOT modify any existing types.

**New types to add:**

```swift
// MARK: - WebSocket Envelope Types

struct SensorUpdateData: Codable {
    let deviceId: String
    let timestamp: String
    let simulated: Bool
    let totalWatts: Float
    let channels: [LiveChannel]
}

struct GridStatusUpdate: Codable {
    let current: GridSnapshot
    let forecastNext3h: [GridHour]
}

struct AnomalyAlert: Codable, Identifiable {
    let channelId: Int
    let assignedZone: String
    let assignedAppliance: String
    let currentWatts: Float
    let expectedWatts: Float
    let deviationPct: Float?
    let message: String
    var id: String { "\(channelId)-\(currentWatts)" }
}

struct TTSAudioChunk: Codable {
    let audio: String
    let format: String
    let insightId: String
    let isFinal: Bool
}

// MARK: - Chat Types

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: ChatRole
    var text: String
    let timestamp: Date
}

enum ChatRole {
    case user, assistant
}

// MARK: - REST Request/Response Types

struct HealthResponse: Codable {
    let status: String
    let hardwareConnected: Bool
    let bufferFill: String
    let wsClients: Int
    let timestamp: String
}

struct ForecastResponse: Codable {
    let gridForecast24h: [GridHour]
}

struct TaskRequest: Codable {
    let title: String
    let channelId: Int?
    let estimatedWatts: Int?
    let estimatedDurationMin: Int?
    let deadline: String?
    let isDeferrable: Bool?
    let priority: String?
}

struct TaskResponse: Codable {
    let eventId: String
    let message: String
}

struct SettingsRequest: Codable {
    let alpha: Double?
    let beta: Double?
}

struct SettingsResponse: Codable {
    let alpha: Double
    let beta: Double
}

struct InsightsResponse: Codable {
    let insights: [Insight]
}

struct CalendarImportResponse: Codable {
    let eventsImported: Int
    let deferrableEvents: Int
    let nonDeferrableEvents: Int
    let message: String
}

// MARK: - Loading State

enum LoadingState: Equatable {
    case idle, loading, loaded, error(String)
}
```

**WebSocket envelope decoding strategy:** Two-pass decode. First decode `{"type": String}` only. Then based on type string, decode full envelope with typed data field:
```swift
private struct WSTypeOnly: Decodable { let type: String }
private struct WSTypedEnvelope<T: Decodable>: Decodable {
    let type: String; let timestamp: String; let data: T
}
```

**Why these models work:** The existing TOUPeriod enum already has custom raw values for snake_case (`offPeak = "off_peak"`). Using JSONDecoder with `.convertFromSnakeCase` handles all other property names. Every field was verified against the actual backend route implementations in `routes.py` and `websocket.py`.

**Depends on:** Nothing
**Parallel with:** Nothing — this is the foundation

---

## Step 2: APIClient Service

**File to create:** `breakerios/breakerios/Services/APIClient.swift`

**Singleton REST client:**
- `@MainActor class APIClient` with `static let shared`
- `baseURL: String` reads from `UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:8000"`
- Shared `JSONDecoder` with `.convertFromSnakeCase`, shared `JSONEncoder` with `.convertToSnakeCase`
- Generic `get<T: Decodable>(_ path: String) async throws -> T`
- Generic `post<B: Encodable, R: Decodable>(_ path: String, body: B) async throws -> R`

**Convenience methods:**
- `getHealth() -> HealthResponse` — GET /api/health
- `getDashboard() -> DashboardResponse` — GET /api/dashboard
- `getForecast() -> ForecastResponse` — GET /api/forecast
- `getSchedule() -> OptimizationResult` — GET /api/schedule
- `getInsights() -> InsightsResponse` — GET /api/insights
- `addTask(_ task: TaskRequest) -> TaskResponse` — POST /api/tasks
- `updateSettings(_ req: SettingsRequest) -> SettingsResponse` — POST /api/settings
- `importCalendar(icalData: String) -> CalendarImportResponse` — POST /api/calendar/import

**Error type:** `APIError` enum with cases: `invalidURL`, `networkError(Error)`, `decodingError(Error)`, `serverError(Int, String?)`

**Depends on:** Step 1
**Parallel with:** Steps 3, 4

---

## Step 3: WebSocketManager Service (/ws/live)

**File to create:** `breakerios/breakerios/Services/WebSocketManager.swift`

**Singleton WebSocket manager for the /ws/live endpoint:**
- `@MainActor class WebSocketManager: ObservableObject` with `static let shared`
- `@Published var isConnected = false`
- Typed Combine `PassthroughSubject` publishers for each message type:
  - `sensorUpdate: PassthroughSubject<SensorUpdateData, Never>`
  - `gridStatusUpdate: PassthroughSubject<GridStatusUpdate, Never>`
  - `calendarUpdate: PassthroughSubject<OptimizationResult, Never>`
  - `insightReceived: PassthroughSubject<Insight, Never>`
  - `anomalyReceived: PassthroughSubject<AnomalyAlert, Never>`
  - `ttsChunkReceived: PassthroughSubject<TTSAudioChunk, Never>`

**Connection management:**
- `connect()` — build ws:// URL from APIClient.shared.baseURL, create URLSessionWebSocketTask, resume, start receive loop
- `disconnect()` — cancel task, set isConnected = false
- `receiveMessage()` — recursive async loop: receive -> handleMessage -> receiveMessage. On error -> reconnect
- `handleMessage(_ data: Data)` — two-pass envelope decode: read type field, then switch to decode correct data type, send to corresponding subject
- `reconnect()` — exponential backoff: delay = min(2^attempts, 30 seconds), then call connect()

**Message type routing in handleMessage:**
| Envelope type | Decoded as | Published to |
|---|---|---|
| `sensor_update` | `WSTypedEnvelope<SensorUpdateData>` | `sensorUpdate` |
| `grid_status` | `WSTypedEnvelope<GridStatusUpdate>` | `gridStatusUpdate` |
| `calendar_update` | `WSTypedEnvelope<OptimizationResult>` | `calendarUpdate` |
| `insight` | `WSTypedEnvelope<Insight>` | `insightReceived` |
| `anomaly_alert` | `WSTypedEnvelope<AnomalyAlert>` | `anomalyReceived` |
| `tts_audio` | `WSTypedEnvelope<TTSAudioChunk>` | `ttsChunkReceived` |

**Depends on:** Step 1
**Parallel with:** Steps 2, 4

---

## Step 4: ChatWebSocketManager Service (/ws/chat)

**File to create:** `breakerios/breakerios/Services/ChatWebSocketManager.swift`

**Separate WebSocket for the /ws/chat bidirectional endpoint:**
- `@MainActor class ChatWebSocketManager: ObservableObject` with `static let shared`
- `@Published var isConnected = false`
- `responseChunk: PassthroughSubject<(chunk: String, done: Bool, fullMessage: String?), Never>`

**Methods:**
- `connect()` — connect to ws://{host}/ws/chat
- `disconnect()`
- `sendMessage(_ text: String)` — encode `{"message": text}`, send as .string
- `receiveMessage()` — recursive loop
- `handleMessage(_ data: Data)` — decode chat_response envelope: if `done == false`, emit `(chunk, false, nil)`. If `done == true`, emit `("", true, fullMessage)`

**Depends on:** Step 1
**Parallel with:** Steps 2, 3

---

## Step 5: Wire DeviceView to Live Data

**File:** `breakerios/breakerios/DeviceView.swift`

**Changes to DeviceViewModel (embedded in file):**
- Add `@Published var loadingState: LoadingState = .idle`
- Add `private var cancellables = Set<AnyCancellable>()`
- Add `import Combine` at top of file

**Rewrite `startMonitoring()`:**
1. Set `loadingState = .loading`
2. Try `APIClient.shared.getDashboard()` — on success, map CurrentPower fields to [LiveChannel] using default zone/appliance names, set gridSnapshot and totalWatts. On failure, fall back to existing demo data.
3. Set `loadingState = .loaded`
4. Subscribe to `WebSocketManager.shared.sensorUpdate.sink { }` — update channels, totalWatts
5. Subscribe to `WebSocketManager.shared.gridStatusUpdate.sink { }` — update gridSnapshot
6. Subscribe to `WebSocketManager.shared.$isConnected.assign(to: &$isConnected)`
7. Store all subscriptions in `cancellables`

**Remove** the Timer-based `updateLiveReadings()` method — WebSocket replaces it.

**Add to view body:** A `ConnectionStatusBanner` (see Step 12) at the top of the VStack when `!viewModel.isConnected`. An `.overlay { ProgressView() }` when `loadingState == .loading`.

**Keep:** The existing `loadDemoData()` method for preview fallback. The channel cards, grid status card, gauge — all untouched aesthetically.

**Helper:** `channelsFromDashboard(_ d: DashboardResponse) -> [LiveChannel]` — maps ch0-3_watts from CurrentPower to LiveChannel array using channel config defaults.

**Depends on:** Steps 2, 3
**Parallel with:** Steps 6, 7

---

## Step 6: Wire CalendarView to REST + Live Updates

**File:** `breakerios/breakerios/CalendarView.swift`

**Changes to CalendarViewModel:**
- Add `@Published var loadingState: LoadingState = .idle`
- Add `@Published var showingImport = false`
- Add `private var cancellables = Set<AnyCancellable>()`

**Rewrite `loadData()`:**
1. Set `loadingState = .loading`
2. Parallel async fetch: `async let forecastResult = APIClient.shared.getForecast()` + `async let scheduleResult = APIClient.shared.getSchedule()`
3. Assign results (fall back to demo data on error)
4. Set `loadingState = .loaded`
5. Subscribe to `WebSocketManager.shared.calendarUpdate.sink { }` — update optimization

**Add `addTask(title:channelId:estimatedWatts:durationMinutes:)`:**
- Build `TaskRequest`, call `APIClient.shared.addTask()`. Schedule update comes via WebSocket.

**Add `importCalendar(from url: URL)`:**
- Read .ics file contents from URL (with security-scoped resource access)
- POST to `/api/calendar/import` with `{"ical_data": contents}`
- Show success/error

**Wire AddTaskView:**
- Pass a closure `onAdd: (String, Int?, Int, Int) async -> Void` from CalendarView
- Closure calls `viewModel.addTask(...)`, then dismisses the sheet

**Add to view body:**
- Import button (SF Symbol `square.and.arrow.down`) next to the "+" button
- `.fileImporter(isPresented: $viewModel.showingImport, allowedContentTypes: [.calendarEvent])` modifier
- Loading overlay, error banner

**Depends on:** Steps 2, 3
**Parallel with:** Steps 5, 7

---

## Step 7: Wire SettingsView to Backend

**File:** `breakerios/breakerios/SettingsView.swift`

**Changes to SettingsViewModel:**
- Add `@Published var connectionTestResult: String?`
- Add `@Published var isSaving = false`

**Init:** Load serverURL, alpha, beta, alert toggles, channel configs from UserDefaults.

**Rewrite `testConnection()`:**
- Call `APIClient.shared.getHealth()`
- On success: `isConnected = true`, set `connectionTestResult = "Connected! Buffer: \(health.bufferFill), \(health.wsClients) client(s)"`
- On failure: `isConnected = false`, set result to error description

**Add `saveSettings()`:**
- Save serverURL to UserDefaults
- POST `/api/settings` with `{alpha, beta}`
- Save channel configs to UserDefaults as JSON data

**View changes:**
- Make serverURL editable (TextField)
- Show connectionTestResult text below Test Connection button
- Add Save button in optimization weights section
- Add NavigationLink to AboutView at the bottom of the Settings form

**Depends on:** Step 2
**Parallel with:** Steps 5, 6

---

## Step 8: InsightsView (new)

**File to create:** `breakerios/breakerios/InsightsView.swift`

**Contains InsightsViewModel (embedded) + InsightCard + AnomalyCard sub-views.**

**InsightsViewModel:**
- `@Published var insights: [Insight] = []`
- `@Published var anomalies: [AnomalyAlert] = []`
- `@Published var loadingState: LoadingState = .idle`
- `@Published var playingInsightId: String?`
- `loadData()`: GET /api/insights, then subscribe to `WebSocketManager.shared.insightReceived` and `anomalyReceived`
- `refresh()`: re-fetch from REST

**InsightCard design (matches existing card pattern exactly):**
- VStack(alignment: .leading, spacing: 12) -> .padding() -> RoundedRectangle(cornerRadius: 12).fill(Color(.secondarySystemBackground))
- Severity-colored border: `.strokeBorder(severityColor.opacity(0.3), lineWidth: 1.5)`
- Severity color: info=.blue, warning=.yellow, critical=.red
- Category icon: scheduleOptimization="calendar.badge.clock", anomaly="exclamationmark.triangle.fill", gridStatus="bolt.circle.fill"
- Status capsule for severity label (Capsule().fill(severityColor.opacity(0.1)))
- Speaker icon when TTS is playing that insight

**AnomalyCard design:**
- Same card structure but with red tint: `Color.red.opacity(0.05)` background, red border
- Shows current watts in large rounded font (.system(size: 28, weight: .bold, design: .rounded)) + expected watts in .caption
- Warning triangle icon + zone/appliance labels

**Empty state:** `ContentUnavailableView("No Insights Yet", systemImage: "sparkles", description: ...)`

**NavigationStack -> ScrollView -> VStack(spacing: 20) — matches existing pattern.**

**Depends on:** Steps 2, 3
**Parallel with:** Step 9

---

## Step 9: ChatView (floating sheet)

**File to create:** `breakerios/breakerios/ChatView.swift`

**Contains ChatViewModel (embedded) + ChatBubble sub-view.**

**Access pattern:** Floating button in ContentView (not a tab). A persistent overlay button (SF Symbol "bubble.left.and.bubble.right.fill" in a blue circle) positioned bottom-right. Tapping opens a `.sheet` with ChatView.

**ChatViewModel:**
- `@Published var messages: [ChatMessage] = []`
- `@Published var inputText = ""`
- `@Published var isStreaming = false`
- `connect()`: call `ChatWebSocketManager.shared.connect()`, subscribe to `responseChunk`
- `send()`: append user message, append empty assistant message, call `ChatWebSocketManager.shared.sendMessage(text)`, set isStreaming = true
- On chunk received (done=false): append chunk text to last assistant message
- On done (done=true): replace last assistant message text with fullMessage, set isStreaming = false

**ChatBubble design (matches existing card system):**
- User bubbles: RoundedRectangle(cornerRadius: 12), Color.blue fill, white text
- Assistant bubbles: RoundedRectangle(cornerRadius: 12), Color(.secondarySystemBackground) fill, .primary text
- .font(.body) for message text
- Max width: 280pt
- Spacing: 12pt between bubbles (LazyVStack spacing)

**Input bar:** HStack with TextField ("Ask about your energy...") + send button (arrow.up.circle.fill). Disabled when empty or streaming.

**Auto-scroll:** ScrollViewReader + onChange of messages.count -> scrollTo last message.

**Depends on:** Step 4
**Parallel with:** Step 8

---

## Step 10: TTS Audio Player

**File to create:** `breakerios/breakerios/Services/TTSPlayer.swift`

**`@MainActor class TTSPlayer: ObservableObject` with `static let shared`:**
- `@Published var isPlaying = false`
- `@Published var currentInsightId: String?`
- Private `audioData = Data()` buffer
- Private `audioPlayer: AVAudioPlayer?`

**`startListening()`:** Subscribe to `WebSocketManager.shared.ttsChunkReceived`. On each chunk:
- If `!isFinal`: base64-decode audio, append to `audioData` buffer. Track `insightId`.
- If `isFinal`: play accumulated buffer via AVAudioPlayer. Set `isPlaying = true`. On completion, set `isPlaying = false`, clear `currentInsightId`.

**AVAudioSession setup:** `.playback` category, `.spokenAudio` mode.

**Connection:** `TTSPlayer.shared.startListening()` called in ContentView `.task {}`. InsightsViewModel reads `TTSPlayer.shared.currentInsightId` to show speaker icon on the active insight card.

**Depends on:** Step 3
**Parallel with:** Steps 5-9

---

## Step 11: Update ContentView + App Entry

**File:** `breakerios/breakerios/ContentView.swift`

**New tab bar (5 tabs) + floating chat button:**

```
TabView(selection: $selectedTab) {
    DeviceView()     .tag(0)  // "bolt.circle.fill"
    CalendarView()   .tag(1)  // "calendar"
    InsightsView()   .tag(2)  // "sparkles"
    SettingsView()   .tag(3)  // "gear"
    AboutView()      .tag(4)  // "info.circle"
}
.overlay(alignment: .bottomTrailing) {
    // Floating chat button
    Button { showingChat = true } label: {
        Image(systemName: "bubble.left.and.bubble.right.fill")
            .font(.title2)
            .foregroundStyle(.white)
            .frame(width: 56, height: 56)
            .background(Circle().fill(Color.blue))
            .shadow(radius: 4)
    }
    .padding(.trailing, 20)
    .padding(.bottom, 80)  // above tab bar
}
.sheet(isPresented: $showingChat) {
    ChatView()
}
.task {
    WebSocketManager.shared.connect()
    TTSPlayer.shared.startListening()
}
```

**Add:** `@State private var showingChat = false`

**Depends on:** Steps 8, 9, 10
**Parallel with:** Step 12

---

## Step 12: Reusable Loading/Error Components

**File to create:** `breakerios/breakerios/Components/StatusBanners.swift`

**Two small reusable views (matching existing design system):**

**ConnectionStatusBanner:**
- Shows when WebSocket disconnected
- Red dot (8pt) + "Reconnecting to server..." in .caption
- Red-tinted background (Color.red.opacity(0.05))

**ErrorBanner:**
- Shows on REST fetch failure
- Yellow warning triangle + error message in .caption + "Retry" button
- Card background: Color(.secondarySystemBackground), cornerRadius 12

**Apply to all view files:** Add ConnectionStatusBanner at top of VStack in DeviceView, CalendarView, InsightsView. Each view already gets a ProgressView overlay from steps 5-8.

**Depends on:** Steps 5-9
**Parallel with:** Step 11

---

## Step 13: XCTest Unit Tests

**File to create:** `breakerios/breakeriosTests/NetworkingTests.swift`
**File to modify:** `breakerios/breakeriosTests/breakeriosTests.swift` (update with real tests)

**APIClientTests:**
- Test JSON decoding: create sample JSON strings matching each backend endpoint response, decode with the shared decoder, assert fields match
- Test DashboardResponse decoding from snake_case JSON
- Test ForecastResponse decoding (24 GridHour elements)
- Test OptimizationResult decoding with OptimizedEvent array
- Test Insight decoding with enum raw values (InsightCategory, InsightSeverity)
- Test SensorUpdateData decoding (WebSocket sensor_update envelope data)
- Test GridStatusUpdate decoding
- Test AnomalyAlert decoding
- Test HealthResponse decoding
- Test edge cases: OptimizationResult with empty events, optional fields as null

**WebSocketTests:**
- Test envelope type routing: given a JSON string with `"type": "sensor_update"`, verify the two-pass decode correctly identifies the type and extracts data
- Test each envelope type decoding
- Test malformed JSON handling (should not crash)

**Depends on:** Step 1 (models must exist)
**Parallel with:** Steps 2-12

---

## Step 14: Xcode Project Configuration

**File:** `breakerios/breakerios.xcodeproj/project.pbxproj`

New files must be added to the Xcode project's build phases. When creating files:
- Create a `Services/` group in the Xcode project navigator containing: APIClient.swift, WebSocketManager.swift, ChatWebSocketManager.swift, TTSPlayer.swift
- Create a `Components/` group containing: StatusBanners.swift
- Add ChatView.swift and InsightsView.swift to the main breakerios group
- Add test files to the breakeriosTests target

This happens automatically if files are created inside the project directory and added via Xcode, but since we're working from CLI, we need to ensure the pbxproj file is updated.

**Note:** This Xcode project uses PBXFileSystemSynchronizedRootGroup which means it auto-discovers files in the breakerios/ directory. No manual pbxproj edits needed — just create files in the right folders.

**Depends on:** All file creation steps

---

## Dependency Graph & Build Order

```
Step 1 (Models) ----------+--------------------------------------+
                          |                                      |
           +--------------+----------------+                     |
           v              v                v                     v
    Step 2 (API)   Step 3 (WS)   Step 4 (ChatWS)        Step 13 (Tests)
           |              |                |
           +--------------+                |
           v              v                v
    Step 5 (Device) Step 6 (Cal) Step 7 (Settings)  Step 8 (Insights)  Step 9 (Chat)  Step 10 (TTS)
           |              |              |                |               |              |
           +--------------+--------------+----------------+---------------+--------------+
                                                          |
                                               +----------+
                                               v          v
                                       Step 11 (Tabs) Step 12 (Banners)
                                               |          |
                                               v          v
                                          Step 14 (Xcode project)
```

**Parallelizable waves:**
- Wave 1: Step 1 only (foundation)
- Wave 2: Steps 2 + 3 + 4 + 13 (services + tests, all independent)
- Wave 3: Steps 5 + 6 + 7 + 8 + 9 + 10 (all touch different files)
- Wave 4: Steps 11 + 12 (integration)
- Wave 5: Step 14 (Xcode project file)

---

## Files Summary

### New Files (8)
| File | Purpose |
|---|---|
| `breakerios/breakerios/Services/APIClient.swift` | REST networking singleton |
| `breakerios/breakerios/Services/WebSocketManager.swift` | /ws/live WebSocket + Combine publishers |
| `breakerios/breakerios/Services/ChatWebSocketManager.swift` | /ws/chat bidirectional WebSocket |
| `breakerios/breakerios/Services/TTSPlayer.swift` | TTS audio accumulation + playback |
| `breakerios/breakerios/InsightsView.swift` | Insights UI + InsightsViewModel + InsightCard + AnomalyCard |
| `breakerios/breakerios/ChatView.swift` | Chat UI + ChatViewModel + ChatBubble |
| `breakerios/breakerios/Components/StatusBanners.swift` | ConnectionStatusBanner + ErrorBanner |
| `breakerios/breakeriosTests/NetworkingTests.swift` | Unit tests for decoding + WebSocket routing |

### Modified Files (5)
| File | Changes |
|---|---|
| `breakerios/breakerios/Models.swift` | Add ~100 lines: WebSocket data types, request/response types, LoadingState |
| `breakerios/breakerios/ContentView.swift` | 5-tab layout + floating chat button + WebSocket init in .task |
| `breakerios/breakerios/DeviceView.swift` | Replace timer with WebSocket subscription, add REST initial load, add loading state |
| `breakerios/breakerios/CalendarView.swift` | Wire to REST + WebSocket, add task API call, add calendar import, add loading state |
| `breakerios/breakerios/SettingsView.swift` | Wire testConnection to REST, add saveSettings, UserDefaults persistence, About link |

### Unchanged Files (2)
| File | Why |
|---|---|
| `breakerios/breakerios/AboutView.swift` | No changes — used as-is as NavigationLink target from Settings |
| `breakerios/breakerios/breakeriosApp.swift` | No changes — ContentView handles everything |

---

## Progress Tracking (for progress.md)

| Task | Status | Notes |
|---|---|---|
| F0. Frontend plan + repo prep | DONE | Merged backend->main, created dev/frontend, cleaned junk files |
| F1. New models (WebSocket + REST types) | TODO | Models.swift additions |
| F2. APIClient service | TODO | REST networking singleton |
| F3. WebSocketManager service (/ws/live) | TODO | Combine publishers for each message type |
| F4. ChatWebSocketManager service (/ws/chat) | TODO | Bidirectional chat WebSocket |
| F5. Wire DeviceView to backend | TODO | Replace timer with REST + WebSocket |
| F6. Wire CalendarView to backend | TODO | REST fetch + WebSocket subscription + Add Task API + calendar import |
| F7. Wire SettingsView to backend | TODO | Health check, save settings, UserDefaults persistence |
| F8. InsightsView (new) | TODO | Insights + anomaly display with live WebSocket |
| F9. ChatView (floating sheet) | TODO | Chat UI + streaming responses |
| F10. TTS audio player | TODO | Accumulate chunks + AVAudioPlayer playback |
| F11. ContentView update (tabs + chat FAB) | TODO | 5-tab layout + floating chat button |
| F12. Loading/error banners | TODO | ConnectionStatusBanner + ErrorBanner components |
| F13. XCTest unit tests | TODO | JSON decoding + WebSocket routing tests |
| F14. Xcode project configuration | TODO | Verify auto-discovery works with PBXFileSystemSynchronizedRootGroup |
