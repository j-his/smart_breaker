# EnergyAI / smart_breaker API Specification
<!-- Optimized for LLM consumption. No prose. Schemas, types, constraints, annotations only. -->
<!-- Backend: Python/FastAPI | Base URL: http://localhost:8000 -->
<!-- Protocol: REST (JSON) + WebSocket -->

---

## Constants

```
VOLTAGE              = 120        # volts; backend multiplies amps * 120 to get watts
NUM_CHANNELS         = 4          # fixed; indices 0-3
BREAKER_LIMIT        = 7200       # watts; max total draw across all channels

# Grid color thresholds (TOU price in cents/kWh)
GRID_GREEN           = price <= 15
GRID_YELLOW          = 16 <= price <= 25
GRID_RED             = price > 25

# Time-of-Use periods (hour of day, 24h)
SUPER_OFF_PEAK       = [0, 7)     # midnight to 7 AM
OFF_PEAK             = [7, 16) + [21, 24)
PEAK                 = [16, 21)   # 4 PM to 9 PM
```

---

## Types

### ChannelReading

```
{
  channel_id:         int          // range: 0-3, index into 4-channel breaker
  assigned_zone:      string       // human label, e.g. "Kitchen"
  assigned_appliance: string       // human label, e.g. "Dishwasher"
  current_amps:       float        // AMPS, not watts. Backend converts: watts = amps * 120
}
```

### SensorReading

```
{
  device_id:          string       // unique hardware identifier
  timestamp:          string       // ISO8601, e.g. "2026-02-28T14:30:00Z"
  channels:           ChannelReading[4]  // MUST be exactly 4 elements, indices 0-3
}
```

### GridSnapshot

```
{
  renewable_pct:              float    // range: 0-100, percentage of grid from renewables
  carbon_intensity_gco2_kwh:  float    // range: 80-500, grams CO2 per kWh
  tou_price_cents_kwh:        float    // range: 5-50, current price in cents per kWh
  tou_period:                 string   // enum: "peak" | "off_peak" | "super_off_peak"
  status:                     string   // enum: "green" | "yellow" | "red" (derived from price thresholds)
}
```

### GridHour

```
GridSnapshot + {
  hour:                       int      // range: 0-23, hour of day
}
```

### OptimizedEvent

```
{
  event_id:                   string   // UUID v4
  title:                      string   // task/event name
  original_start:             string   // ISO8601, user's requested start
  original_end:               string   // ISO8601, user's requested end
  optimized_start:            string   // ISO8601, AI-recommended start
  optimized_end:              string   // ISO8601, AI-recommended end
  channel_id:                 int|null // range: 0-3 or null if unassigned
  estimated_watts:            float    // estimated power consumption in watts
  savings_cents:              float    // >= 0, money saved by optimization
  carbon_avoided_g:           float    // >= 0, grams CO2 avoided by optimization
  reason:                     string   // LLM-generated natural language explanation
  grid_status_at_time:        string   // enum: "green" | "yellow" | "red" at optimized time
  is_deferrable:              bool     // true = can be moved to cheaper/greener window
  was_moved:                  bool     // true = optimized times differ from original
}
```

### OptimizationResult

```
{
  optimized_events:           OptimizedEvent[]
  total_savings_cents:        float    // sum of all event savings
  total_carbon_avoided_g:     float    // sum of all carbon avoided
  optimization_confidence:    float    // range: 0.0-1.0, model confidence score
}
```

### Insight

```
{
  message:                    string   // human-readable insight text
  category:                   string   // enum: "schedule_optimization" | "anomaly" | "grid_status"
  severity:                   string   // enum: "info" | "warning" | "critical"
  insight_id:                 string   // optional; present when TTS audio follows via WebSocket
}
```

### TTSAudio

```
{
  audio:                      string   // base64-encoded raw MP3 bytes; empty string "" on final message
  format:                     string   // always "mp3_44100_128" (MP3, 44100 Hz, 128 kbps)
  insight_id:                 string   // correlates to Insight.insight_id
  is_final:                   bool     // true = last chunk, audio field is empty ""
}
```

### JsonEvent (used in calendar import)

```
{
  title:                      string   // required; event name
  start:                      string   // required; ISO8601
  end:                        string   // required; ISO8601
  channel_id:                 int|null // optional; 0-3 or null
  power_watts:                float|null  // optional; estimated watts
  is_deferrable:              bool|null   // optional; null defaults to server heuristic
}
```

---

## REST Endpoints

### GET /api/health

Purpose: connectivity check, hardware status

```
Response 200:
{
  status:               string       // e.g. "ok"
  hardware_connected:   bool         // true if Arduino/sensor bridge is live
  buffer_fill:          string       // human-readable buffer status
  ws_clients:           int          // number of active WebSocket connections
  timestamp:            string       // ISO8601
}
```

---

### GET /api/dashboard

Purpose: full app state in one call (initial load)

```
Response 200:
{
  current_power: {
    ch0_watts:          float        // channel 0 current draw in watts
    ch1_watts:          float        // channel 1 current draw in watts
    ch2_watts:          float        // channel 2 current draw in watts
    ch3_watts:          float        // channel 3 current draw in watts
    total_watts:        float        // sum of all channels
  }
  grid:                 GridSnapshot // current grid conditions
  hardware_connected:   bool
  optimization:         OptimizationResult | null  // null if no schedule exists yet
}
```

---

### GET /api/forecast

Purpose: 24-hour grid forecast for schedule planning

```
Response 200:
{
  grid_forecast_24h:    GridHour[24] // exactly 24 elements, one per hour (0-23)
}
```

---

### GET /api/schedule

Purpose: retrieve current optimized schedule

```
Response 200:
OptimizationResult
```

---

### POST /api/tasks

Purpose: add a single deferrable task for optimization

```
Request body:
{
  title:                    string     // REQUIRED
  channel_id:               int|null   // optional; 0-3 or null
  estimated_watts:          float      // default: 1000
  estimated_duration_min:   int        // default: 60
  deadline:                 string|null // ISO8601 or null (no deadline)
  is_deferrable:            bool       // default: true
  priority:                 string     // enum: "low" | "medium" | "high"; default: "medium"
}

Response 200:
{
  event_id:                 string     // UUID of created event
  message:                  string     // confirmation message
}
```

---

### POST /api/calendar/import

Purpose: bulk import events (iCal string or JSON array)

```
Request body (provide one or both):
{
  ical_data:                string|null   // raw iCal (.ics) string
  json_events:              JsonEvent[]|null  // array of JsonEvent objects
}

Response 200:
{
  events_imported:          int
  deferrable_events:        int
  non_deferrable_events:    int
  message:                  string
}
```

---

### POST /api/sensor

Purpose: ingest a sensor reading from hardware (Arduino/ESP32)

```
Request body:
SensorReading              // channels array MUST have exactly 4 elements

Response 200:
{
  status:                   "ok"
}
```

---

### POST /api/settings

Purpose: adjust optimization weights

```
Request body (all fields optional):
{
  alpha:                    float|null   // cost weight (higher = prioritize savings)
  beta:                     float|null   // carbon weight (higher = prioritize green)
}

Response 200:
{
  alpha:                    float        // current alpha after update
  beta:                     float        // current beta after update
}
```

---

### GET /api/insights

Purpose: retrieve AI-generated insights

```
Response 200:
{
  insights:                 Insight[]
}
```

---

### GET /api/attention

Purpose: retrieve ML attention weights and anomaly detection data

```
Response 200 (when ML data available):
{
  attention_weights:          float[]    // per-hour attention weights from the TFT model
  day_type:                   string     // e.g. "weekday", "weekend", "holiday"
  anomaly_score:              float      // 0.0-1.0, higher = more anomalous
}

Response 200 (fallback, no ML data):
{
  attention_weights:          float[]    // empty array []
  message:                    string     // "No ML data yet"
}
```

---

## WebSocket: ws://localhost:8000/ws/live

Direction: **server -> client** (push only, client does not send)

Envelope format for ALL messages:

```
{
  type:                     string     // message type discriminator (see below)
  timestamp:                string     // ISO8601
  data:                     object     // type-specific payload
}
```

### Message types and their data payloads:

```
type: "sensor_update"
data: {
  channels: [                          // array of 4
    {
      channel_id:           int        // 0-3
      assigned_zone:        string
      assigned_appliance:   string
      current_watts:        float      // NOTE: watts here (already converted)
      is_active:            bool       // true if drawing power
    }
  ]
  total_watts:              float
}

type: "calendar_update"
data: OptimizationResult               // full re-optimized schedule

type: "grid_status"
data: {
  current:                  GridSnapshot
  forecast_next_3h:         GridHour[3]
}

type: "insight"
data: Insight

type: "anomaly_alert"
data: {
  channel_id:               int        // which channel triggered
  assigned_zone:            string
  assigned_appliance:       string
  current_watts:            float
  expected_watts:           float
  deviation_pct:            float      // how far off from expected
  message:                  string     // human-readable alert
}

type: "ml_status"
data: {
  model_loaded:             bool
  last_training:            string     // ISO8601 or "never"
  accuracy:                 float|null
}

type: "tts_audio"
data: TTSAudio
```

---

## WebSocket: ws://localhost:8000/ws/chat

Direction: **bidirectional** (client sends messages, server streams responses)

### Client sends:

```
{
  message:                  string     // user's chat message
}
```

### Server responds (streamed):

```
// Intermediate chunks (0 or more):
{
  type:                     "chat_response"
  data: {
    chunk:                  string     // partial text
    done:                   false
  }
}

// Final message (exactly 1):
{
  type:                     "chat_response"
  data: {
    message:                string     // complete assembled response
    done:                   true
  }
}
```

---

## iOS Integration Annotations

### App Lifecycle

```
ON_APP_LAUNCH:
  1. GET /api/dashboard                → populate all UI panels
  2. Connect ws://BASE/ws/live         → keep open for real-time updates
  3. Connect ws://BASE/ws/chat         → keep open for chat feature

ON_FOREGROUND_RESUME:
  1. GET /api/dashboard                → refresh stale data
  2. Reconnect WebSockets if closed
```

### User Actions -> API Calls

```
USER_ADDS_TASK:
  POST /api/tasks {title, channel_id?, estimated_watts, estimated_duration_min, deadline?, is_deferrable, priority}
  → display event_id confirmation
  → schedule auto-refreshes via ws/live calendar_update

USER_IMPORTS_CALENDAR:
  POST /api/calendar/import {ical_data? | json_events?}
  → display events_imported count
  → schedule auto-refreshes via ws/live calendar_update

USER_ADJUSTS_SETTINGS:
  POST /api/settings {alpha?, beta?}
  → update displayed weights

USER_SENDS_CHAT:
  Send via ws/chat: {message: "..."}
  → stream chunks into chat bubble
  → finalize on done:true
```

### WebSocket -> UI Mapping

```
sensor_update:
  channels[].is_active     → channel icon color: true=green, false=gray
  channels[].current_watts → per-channel watt label
  total_watts              → main power display / gauge

calendar_update:
  optimized_events[]       → rebuild schedule list view
  .was_moved == true       → highlight/badge as "rescheduled"
  .savings_cents           → show savings per event
  total_savings_cents      → header savings summary
  total_carbon_avoided_g   → header carbon summary

grid_status:
  current.status           → donut chart / ring color (green/yellow/red)
  current.tou_price_cents_kwh → price label
  current.renewable_pct    → renewable percentage label
  forecast_next_3h[]       → mini forecast bar chart

insight:
  severity == "critical"   → red banner / alert
  severity == "warning"    → yellow banner
  severity == "info"       → subtle notification
  message                  → banner text

anomaly_alert:
  → show warning banner immediately
  → include channel_id, assigned_appliance, message
  → option to dismiss or view details

tts_audio:
  → accumulate base64 chunks into Data buffer
  → on first chunk: begin AVAudioPlayer playback
  → on is_final == true: flush remaining buffer, stop accumulating
  → correlate via insight_id to highlight the spoken insight in UI

ml_status:
  → update model status indicator (loaded/training/accuracy)
```

### Swift Type Stubs

```swift
// -- Sensor --
struct ChannelReading: Codable {
    let channelId: Int           // 0-3
    let assignedZone: String
    let assignedAppliance: String
    let currentAmps: Float       // AMPS; multiply by 120 for watts
}

struct SensorReading: Codable {
    let deviceId: String
    let timestamp: String        // ISO8601
    let channels: [ChannelReading]  // exactly 4
}

// -- Grid --
enum GridStatus: String, Codable {
    case green, yellow, red
}

enum TOUPeriod: String, Codable {
    case peak, off_peak, super_off_peak
}

struct GridSnapshot: Codable {
    let renewablePct: Float             // 0-100
    let carbonIntensityGco2Kwh: Float   // 80-500
    let touPriceCentsKwh: Float         // 5-50
    let touPeriod: TOUPeriod
    let status: GridStatus
}

struct GridHour: Codable {
    let hour: Int                       // 0-23
    let renewablePct: Float
    let carbonIntensityGco2Kwh: Float
    let touPriceCentsKwh: Float
    let touPeriod: TOUPeriod
    let status: GridStatus
}

// -- Optimization --
struct OptimizedEvent: Codable {
    let eventId: String                 // UUID
    let title: String
    let originalStart: String           // ISO8601
    let originalEnd: String
    let optimizedStart: String
    let optimizedEnd: String
    let channelId: Int?                 // 0-3 or nil
    let estimatedWatts: Float
    let savingsCents: Float             // >= 0
    let carbonAvoidedG: Float           // >= 0
    let reason: String                  // LLM-generated
    let gridStatusAtTime: GridStatus
    let isDeferrable: Bool
    let wasMoved: Bool
}

struct OptimizationResult: Codable {
    let optimizedEvents: [OptimizedEvent]
    let totalSavingsCents: Float
    let totalCarbonAvoidedG: Float
    let optimizationConfidence: Float   // 0.0-1.0
}

// -- Insights & TTS --
enum InsightCategory: String, Codable {
    case schedule_optimization, anomaly, grid_status
}

enum InsightSeverity: String, Codable {
    case info, warning, critical
}

struct Insight: Codable {
    let message: String
    let category: InsightCategory
    let severity: InsightSeverity
    let insightId: String?              // present when TTS follows
}

struct TTSAudio: Codable {
    let audio: String                   // base64 MP3; empty on final
    let format: String                  // "mp3_44100_128"
    let insightId: String
    let isFinal: Bool
}

// -- Dashboard --
struct CurrentPower: Codable {
    let ch0Watts: Float
    let ch1Watts: Float
    let ch2Watts: Float
    let ch3Watts: Float
    let totalWatts: Float
}

struct DashboardResponse: Codable {
    let currentPower: CurrentPower
    let grid: GridSnapshot
    let hardwareConnected: Bool
    let optimization: OptimizationResult?
}

// -- Tasks --
enum TaskPriority: String, Codable {
    case low, medium, high
}

struct CreateTaskRequest: Codable {
    let title: String
    let channelId: Int?
    var estimatedWatts: Float = 1000
    var estimatedDurationMin: Int = 60
    let deadline: String?               // ISO8601 or nil
    var isDeferrable: Bool = true
    var priority: TaskPriority = .medium
}

struct CreateTaskResponse: Codable {
    let eventId: String
    let message: String
}

// -- Calendar Import --
struct JsonEvent: Codable {
    let title: String
    let start: String                   // ISO8601
    let end: String                     // ISO8601
    let channelId: Int?
    let powerWatts: Float?
    let isDeferrable: Bool?
}

struct CalendarImportRequest: Codable {
    let icalData: String?
    let jsonEvents: [JsonEvent]?
}

struct CalendarImportResponse: Codable {
    let eventsImported: Int
    let deferrableEvents: Int
    let nonDeferrableEvents: Int
    let message: String
}

// -- WebSocket Envelope --
struct WSEnvelope<T: Codable>: Codable {
    let type: String
    let timestamp: String               // ISO8601
    let data: T
}

// -- WebSocket: sensor_update data --
struct LiveChannel: Codable {
    let channelId: Int
    let assignedZone: String
    let assignedAppliance: String
    let currentWatts: Float             // NOTE: watts, already converted
    let isActive: Bool
}

struct SensorUpdateData: Codable {
    let channels: [LiveChannel]         // 4 elements
    let totalWatts: Float
}

// -- WebSocket: anomaly_alert data --
struct AnomalyAlertData: Codable {
    let channelId: Int
    let assignedZone: String
    let assignedAppliance: String
    let currentWatts: Float
    let expectedWatts: Float
    let deviationPct: Float
    let message: String
}

// -- WebSocket: chat --
struct ChatRequest: Codable {
    let message: String
}

struct ChatResponseData: Codable {
    let chunk: String?                  // present when done == false
    let message: String?                // present when done == true
    let done: Bool
}

// -- Settings --
struct SettingsRequest: Codable {
    let alpha: Float?
    let beta: Float?
}

struct SettingsResponse: Codable {
    let alpha: Float
    let beta: Float
}

// -- Health --
struct HealthResponse: Codable {
    let status: String
    let hardwareConnected: Bool
    let bufferFill: String
    let wsClients: Int
    let timestamp: String
}
```

### CodingKeys Note

```
Backend uses snake_case JSON keys.
Swift uses camelCase properties.
Use JSONDecoder.keyDecodingStrategy = .convertFromSnakeCase
and JSONEncoder.keyEncodingStrategy = .convertToSnakeCase
to avoid writing manual CodingKeys for every struct.
```

---

## Arduino / ESP32 Integration Note

```
The hardware sends SensorReading via POST /api/sensor.
Each reading MUST contain exactly 4 ChannelReading entries.
current_amps is the raw CT clamp reading in amperes.
The backend handles all conversion: watts = current_amps * 120.
Do NOT send watts from hardware. Send amps only.
Recommend POST interval: 1-2 seconds.
Content-Type: application/json.
```
