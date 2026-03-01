# JSON Message Formats — EnergyAI / smart_breaker

> Single source of truth for every JSON shape flowing between the ESP32 hardware, Python backend, and iOS app.

---

## Table of Contents

- [1. Hardware → Backend](#1-hardware--backend)
  - [SensorReading (POST /api/sensor)](#sensorreading)
- [2. iOS → Backend (REST)](#2-ios--backend-rest)
  - [TaskRequest (POST /api/tasks)](#taskrequest)
  - [CalendarImportRequest (POST /api/calendar/import)](#calendarimportrequest)
  - [SettingsRequest (POST /api/settings)](#settingsrequest)
- [3. iOS → Backend (WebSocket)](#3-ios--backend-websocket)
  - [ChatMessage (ws://host/ws/chat)](#chatmessage)
- [4. Backend → iOS (WebSocket: ws://host/ws/live)](#4-backend--ios-websocket-wshostwslive)
  - [Envelope](#envelope)
  - [sensor_update](#sensor_update)
  - [calendar_update](#calendar_update)
  - [grid_status](#grid_status)
  - [insight](#insight)
  - [anomaly_alert](#anomaly_alert)
  - [tts_audio](#tts_audio)
  - [ml_status](#ml_status)
- [5. Backend → iOS (WebSocket: ws://host/ws/chat)](#5-backend--ios-websocket-wshostwschat)
  - [chat_response](#chat_response)
- [6. Backend REST Responses](#6-backend-rest-responses)
  - [GET /api/health](#get-apihealth)
  - [GET /api/dashboard](#get-apidashboard)
  - [GET /api/forecast](#get-apiforecast)
  - [GET /api/schedule](#get-apischedule)
  - [POST /api/tasks (response)](#post-apitasks-response)
  - [POST /api/calendar/import (response)](#post-apicalendarimport-response)
  - [POST /api/sensor (response)](#post-apisensor-response)
  - [POST /api/settings (response)](#post-apisettings-response)
  - [GET /api/attention](#get-apiattention)
  - [GET /api/insights](#get-apiinsights)
- [7. Shared Sub-Schemas](#7-shared-sub-schemas)
  - [ChannelReading](#channelreading)
  - [LiveChannel](#livechannel)
  - [OptimizedEvent](#optimizedevent)
  - [GridSnapshot](#gridsnapshot)
  - [GridHour](#gridhour)
  - [Insight](#insight-object)
- [8. Constants](#8-constants)

---

## 1. Hardware → Backend

### SensorReading

**Endpoint:** `POST /api/sensor`
**Direction:** ESP32 → Backend
**Content-Type:** `application/json`

> NOTE: The hardware sends **current in amps**, not watts. The backend multiplies by 120 V to derive power.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `device_id` | string | non-empty | Unique identifier of the ESP32 device |
| `timestamp` | string | ISO 8601 UTC | Time the reading was taken |
| `channels` | array[ChannelReading] | length = 4 | One entry per CT-clamp channel |

**ChannelReading**

| Field | Type | Constraints | Description |
|---|---|---|---|
| `channel_id` | integer | 0 – 3 | Physical channel index |
| `assigned_zone` | string | non-empty | Room / area label |
| `assigned_appliance` | string | non-empty | Appliance identifier |
| `current_amps` | float | >= 0 | RMS current in amperes |

```json
{
  "device_id": "esp32-demo-001",
  "timestamp": "2026-02-28T18:30:00Z",
  "channels": [
    { "channel_id": 0, "assigned_zone": "kitchen",      "assigned_appliance": "inductive_stove",   "current_amps": 4.32  },
    { "channel_id": 1, "assigned_zone": "laundry_room",  "assigned_appliance": "dryer",             "current_amps": 20.0  },
    { "channel_id": 2, "assigned_zone": "garage",        "assigned_appliance": "ev_charger",        "current_amps": 0.0   },
    { "channel_id": 3, "assigned_zone": "bedroom",       "assigned_appliance": "air_conditioning",  "current_amps": 15.0  }
  ]
}
```

---

## 2. iOS → Backend (REST)

### TaskRequest

**Endpoint:** `POST /api/tasks`
**Direction:** iOS → Backend
**Content-Type:** `application/json`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `title` | string | non-empty | Human-readable task name |
| `channel_id` | integer | 0 – 3 | Target channel for the task |
| `estimated_watts` | integer | > 0 | Expected power draw in watts |
| `estimated_duration_min` | integer | > 0 | Expected run time in minutes |
| `deadline` | string | ISO 8601 UTC | Must be completed by this time |
| `is_deferrable` | boolean | — | Whether the optimizer may reschedule |
| `priority` | string | "low" \| "medium" \| "high" | Scheduling priority hint |

```json
{
  "title": "Run Dishwasher",
  "channel_id": 0,
  "estimated_watts": 1200,
  "estimated_duration_min": 90,
  "deadline": "2026-03-01T06:00:00Z",
  "is_deferrable": true,
  "priority": "low"
}
```

---

### CalendarImportRequest

**Endpoint:** `POST /api/calendar/import`
**Direction:** iOS → Backend
**Content-Type:** `application/json`

Two mutually exclusive formats — send **one** of the following top-level keys:

#### Variant A: JSON events

| Field | Type | Constraints | Description |
|---|---|---|---|
| `json_events` | array[CalendarEvent] | length >= 1 | Structured event list |

**CalendarEvent**

| Field | Type | Constraints | Description |
|---|---|---|---|
| `title` | string | non-empty | Event name |
| `start` | string | ISO 8601 UTC | Scheduled start time |
| `end` | string | ISO 8601 UTC, > start | Scheduled end time |
| `channel_id` | integer | 0 – 3 | Target channel |
| `power_watts` | integer | > 0 | Expected power draw in watts |
| `is_deferrable` | boolean | — | Whether the optimizer may reschedule |

```json
{
  "json_events": [
    {
      "title": "Run Dryer",
      "start": "2026-02-28T18:00:00Z",
      "end": "2026-02-28T19:00:00Z",
      "channel_id": 1,
      "power_watts": 2400,
      "is_deferrable": true
    }
  ]
}
```

#### Variant B: iCal data

| Field | Type | Constraints | Description |
|---|---|---|---|
| `ical_data` | string | valid iCalendar (RFC 5545) | Raw iCal payload |

```json
{
  "ical_data": "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:Run Dryer\nDTSTART:20260228T180000Z\nDTEND:20260228T190000Z\nEND:VEVENT\nEND:VCALENDAR"
}
```

---

### SettingsRequest

**Endpoint:** `POST /api/settings`
**Direction:** iOS → Backend
**Content-Type:** `application/json`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `alpha` | float | 0.0 – 1.0, alpha + beta = 1.0 | Weight for cost optimization |
| `beta` | float | 0.0 – 1.0, alpha + beta = 1.0 | Weight for carbon optimization |

```json
{
  "alpha": 0.7,
  "beta": 0.3
}
```

---

## 3. iOS → Backend (WebSocket)

### ChatMessage

**Endpoint:** `ws://host/ws/chat`
**Direction:** iOS → Backend

| Field | Type | Constraints | Description |
|---|---|---|---|
| `message` | string | non-empty | User's natural-language question or command |

```json
{
  "message": "Why did you move the dryer?"
}
```

---

## 4. Backend → iOS (WebSocket: ws://host/ws/live)

### Envelope

All messages on the live WebSocket share this envelope:

| Field | Type | Constraints | Description |
|---|---|---|---|
| `type` | string | see message types below | Discriminator for the payload |
| `timestamp` | string | ISO 8601 UTC | Server time when the message was emitted |
| `data` | object | varies by type | Payload (schema defined per type) |

```json
{
  "type": "<message_type>",
  "timestamp": "2026-02-28T18:30:00Z",
  "data": { }
}
```

Valid `type` values: `sensor_update`, `calendar_update`, `grid_status`, `insight`, `anomaly_alert`, `tts_audio`, `ml_status`

---

### sensor_update

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `total_watts` | float | >= 0 | Sum of all channel power |
| `channels` | array[LiveChannel] | length = 4 | Per-channel live snapshot |

**LiveChannel**

| Field | Type | Constraints | Description |
|---|---|---|---|
| `channel_id` | integer | 0 – 3 | Channel index |
| `assigned_zone` | string | non-empty | Room / area |
| `assigned_appliance` | string | non-empty | Appliance name |
| `current_watts` | float | >= 0 | Current power draw in watts (already multiplied by 120 V) |
| `is_active` | boolean | — | True if current_watts > 0 |

**Additional envelope field:**

| Field | Type | Constraints | Description |
|---|---|---|---|
| `simulated` | boolean | — | True when data comes from the simulator, false from real hardware |

```json
{
  "type": "sensor_update",
  "timestamp": "2026-02-28T18:30:00Z",
  "simulated": false,
  "data": {
    "total_watts": 4717.2,
    "channels": [
      { "channel_id": 0, "assigned_zone": "kitchen",      "assigned_appliance": "inductive_stove",  "current_watts": 518.4,  "is_active": true  },
      { "channel_id": 1, "assigned_zone": "laundry_room",  "assigned_appliance": "dryer",            "current_watts": 2400.0, "is_active": true  },
      { "channel_id": 2, "assigned_zone": "garage",        "assigned_appliance": "ev_charger",       "current_watts": 0.0,    "is_active": false },
      { "channel_id": 3, "assigned_zone": "bedroom",       "assigned_appliance": "air_conditioning", "current_watts": 1800.0, "is_active": true  }
    ]
  }
}
```

---

### calendar_update

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `optimized_events` | array[OptimizedEvent] | >= 0 items | Events after optimization pass |
| `total_savings_cents` | float | >= 0 | Aggregate dollar savings in cents |
| `total_carbon_avoided_g` | float | >= 0 | Aggregate CO2 avoided in grams |
| `optimization_confidence` | float | 0.0 – 1.0 | Model confidence in the schedule |

**OptimizedEvent**

| Field | Type | Constraints | Description |
|---|---|---|---|
| `event_id` | string | UUID v4 | Unique event identifier |
| `title` | string | non-empty | Human-readable event name |
| `original_start` | string | ISO 8601 UTC | Originally requested start |
| `original_end` | string | ISO 8601 UTC | Originally requested end |
| `optimized_start` | string | ISO 8601 UTC | Optimizer-chosen start |
| `optimized_end` | string | ISO 8601 UTC | Optimizer-chosen end |
| `channel_id` | integer | 0 – 3 | Target channel |
| `estimated_watts` | integer | > 0 | Power draw in watts |
| `savings_cents` | float | >= 0 | Cost saved by rescheduling |
| `carbon_avoided_g` | float | >= 0 | CO2 avoided in grams |
| `reason` | string | non-empty | Plain-English explanation of why the event was moved |
| `grid_status_at_time` | string | "green" \| "yellow" \| "red" | Grid color at the optimized time |
| `is_deferrable` | boolean | — | Whether the event was marked deferrable |
| `was_moved` | boolean | — | True if optimized times differ from original |

```json
{
  "type": "calendar_update",
  "timestamp": "2026-02-28T18:35:00Z",
  "data": {
    "optimized_events": [
      {
        "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Run Dryer",
        "original_start": "2026-02-28T18:00:00Z",
        "original_end": "2026-02-28T19:00:00Z",
        "optimized_start": "2026-02-28T02:00:00Z",
        "optimized_end": "2026-02-28T03:00:00Z",
        "channel_id": 1,
        "estimated_watts": 2400,
        "savings_cents": 38.4,
        "carbon_avoided_g": 156.2,
        "reason": "Moved to super off-peak for 63% savings",
        "grid_status_at_time": "green",
        "is_deferrable": true,
        "was_moved": true
      }
    ],
    "total_savings_cents": 87.2,
    "total_carbon_avoided_g": 412.8,
    "optimization_confidence": 0.87
  }
}
```

---

### grid_status

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `current` | GridSnapshot | — | Live grid conditions |
| `forecast_next_3h` | array[GridHour] | length = 3 | Hourly forecast for the next 3 hours |

**GridSnapshot**

| Field | Type | Constraints | Description |
|---|---|---|---|
| `renewable_pct` | float | 0.0 – 100.0 | Percentage of grid supply from renewables |
| `carbon_intensity_gco2_kwh` | float | >= 0 | Grams CO2 per kWh |
| `tou_price_cents_kwh` | integer | > 0 | Time-of-use price in cents per kWh |
| `tou_period` | string | "super_off_peak" \| "off_peak" \| "peak" | Current TOU period |
| `status` | string | "green" \| "yellow" \| "red" | Grid color rating |

**GridHour**

| Field | Type | Constraints | Description |
|---|---|---|---|
| `hour` | integer | 0 – 23 | Hour of the day (UTC) |
| `renewable_pct` | float | 0.0 – 100.0 | Forecasted renewable percentage |
| `carbon_intensity_gco2_kwh` | float | >= 0 | Forecasted carbon intensity |
| `tou_price_cents_kwh` | integer | > 0 | TOU price in cents per kWh |
| `tou_period` | string | "super_off_peak" \| "off_peak" \| "peak" | TOU period label |
| `status` | string | "green" \| "yellow" \| "red" | Grid color rating |

```json
{
  "type": "grid_status",
  "timestamp": "2026-02-28T18:30:00Z",
  "data": {
    "current": {
      "renewable_pct": 62.3,
      "carbon_intensity_gco2_kwh": 182.0,
      "tou_price_cents_kwh": 22,
      "tou_period": "off_peak",
      "status": "yellow"
    },
    "forecast_next_3h": [
      {
        "hour": 0,
        "renewable_pct": 35.2,
        "carbon_intensity_gco2_kwh": 327.1,
        "tou_price_cents_kwh": 12,
        "tou_period": "super_off_peak",
        "status": "green"
      },
      {
        "hour": 1,
        "renewable_pct": 33.8,
        "carbon_intensity_gco2_kwh": 334.5,
        "tou_price_cents_kwh": 12,
        "tou_period": "super_off_peak",
        "status": "green"
      },
      {
        "hour": 2,
        "renewable_pct": 31.4,
        "carbon_intensity_gco2_kwh": 341.0,
        "tou_price_cents_kwh": 12,
        "tou_period": "super_off_peak",
        "status": "green"
      }
    ]
  }
}
```

---

### insight

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `message` | string | non-empty | Human-readable insight text |
| `category` | string | e.g. "schedule_optimization" | Classification of the insight |
| `severity` | string | "info" \| "warning" \| "critical" | Importance level |
| `insight_id` | string | non-empty | Stable identifier for deduplication and TTS linkage |

```json
{
  "type": "insight",
  "timestamp": "2026-02-28T18:35:00Z",
  "data": {
    "message": "Your dryer was moved to 2 AM, saving 38¢ and 156g CO2.",
    "category": "schedule_optimization",
    "severity": "info",
    "insight_id": "schedule_optimization_1709164800"
  }
}
```

---

### anomaly_alert

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `channel_id` | integer | 0 – 3 | Channel where anomaly was detected |
| `assigned_zone` | string | non-empty | Room / area |
| `assigned_appliance` | string | non-empty | Appliance name |
| `current_watts` | float | >= 0 | Actual power draw in watts |
| `expected_watts` | float | >= 0 | Expected normal power draw in watts |
| `deviation_pct` | float | >= 0 | Percentage deviation from expected |
| `message` | string | non-empty | Human-readable description |

```json
{
  "type": "anomaly_alert",
  "timestamp": "2026-02-28T18:31:00Z",
  "data": {
    "channel_id": 3,
    "assigned_zone": "bedroom",
    "assigned_appliance": "air_conditioning",
    "current_watts": 2400.0,
    "expected_watts": 1440.0,
    "deviation_pct": 66.7,
    "message": "Unusual power on air_conditioning (2400W vs expected 1440W)"
  }
}
```

---

### tts_audio

Streamed in chunks. The final chunk has an empty `audio` field and `is_final: true`.

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `audio` | string | base64-encoded MP3 data (empty string on final) | Audio chunk payload |
| `format` | string | "mp3" | Audio encoding format |
| `insight_id` | string | non-empty | Links back to the insight being narrated |
| `is_final` | boolean | — | True on the last chunk (audio will be empty) |

**Streaming chunk:**

```json
{
  "type": "tts_audio",
  "timestamp": "2026-02-28T18:35:01Z",
  "data": {
    "audio": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2...",
    "format": "mp3",
    "insight_id": "schedule_optimization_1709164800",
    "is_final": false
  }
}
```

**Final chunk:**

```json
{
  "type": "tts_audio",
  "timestamp": "2026-02-28T18:35:03Z",
  "data": {
    "audio": "",
    "format": "mp3",
    "insight_id": "schedule_optimization_1709164800",
    "is_final": true
  }
}
```

---

### ml_status

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `model_loaded` | boolean | — | Whether the ML model is loaded and running |
| `last_training` | string | ISO 8601 UTC | Timestamp of the last inference/training run |
| `accuracy` | float \| null | 0.0 – 1.0 | Model confidence (day_type_confidence), null if unavailable |

```json
{
  "type": "ml_status",
  "timestamp": "2026-02-28T18:30:00Z",
  "data": {
    "model_loaded": true,
    "last_training": "2026-02-28T18:30:00Z",
    "accuracy": 0.92
  }
}
```

---

## 5. Backend → iOS (WebSocket: ws://host/ws/chat)

### chat_response

Streamed token-by-token. Intermediate chunks carry `done: false`; the final message carries `done: true` with the complete text.

| Field (inside `data`) | Type | Constraints | Description |
|---|---|---|---|
| `chunk` | string | present when `done` = false | Incremental text fragment |
| `message` | string | present when `done` = true | Full assembled response |
| `done` | boolean | — | False during streaming, true on final message |

**Streaming chunk:**

```json
{
  "type": "chat_response",
  "data": {
    "chunk": "I moved",
    "done": false
  }
}
```

**Final message:**

```json
{
  "type": "chat_response",
  "data": {
    "message": "I moved your dryer to 2 AM because electricity is 63% cheaper during the super off-peak window.",
    "done": true
  }
}
```

---

## 6. Backend REST Responses

### GET /api/health

| Field | Type | Constraints | Description |
|---|---|---|---|
| `status` | string | "ok" | Server health status |
| `hardware_connected` | boolean | — | True if an ESP32 has posted recently |
| `buffer_fill` | string | format "N/M" | Readings in ring buffer vs capacity |
| `ws_clients` | integer | >= 0 | Number of connected WebSocket clients |
| `timestamp` | string | ISO 8601 UTC | Server time |

```json
{
  "status": "ok",
  "hardware_connected": false,
  "buffer_fill": "12/96",
  "ws_clients": 1,
  "timestamp": "2026-02-28T18:30:00Z"
}
```

---

### GET /api/dashboard

| Field | Type | Constraints | Description |
|---|---|---|---|
| `current_power` | object | — | Per-channel and total wattage |
| `current_power.ch0_watts` | float | >= 0 | Channel 0 power |
| `current_power.ch1_watts` | float | >= 0 | Channel 1 power |
| `current_power.ch2_watts` | float | >= 0 | Channel 2 power |
| `current_power.ch3_watts` | float | >= 0 | Channel 3 power |
| `current_power.total_watts` | float | >= 0 | Sum of all channels |
| `grid` | GridSnapshot | — | Current grid conditions |
| `hardware_connected` | boolean | — | ESP32 connectivity flag |
| `optimization` | OptimizationResult \| null | — | Latest optimization result, or null if none |

```json
{
  "current_power": {
    "ch0_watts": 518.4,
    "ch1_watts": 2400.0,
    "ch2_watts": 0.0,
    "ch3_watts": 1800.0,
    "total_watts": 4718.4
  },
  "grid": {
    "renewable_pct": 62.3,
    "carbon_intensity_gco2_kwh": 182.0,
    "tou_price_cents_kwh": 22,
    "tou_period": "off_peak",
    "status": "yellow"
  },
  "hardware_connected": false,
  "optimization": null
}
```

---

### GET /api/forecast

| Field | Type | Constraints | Description |
|---|---|---|---|
| `grid_forecast_24h` | array[GridHour] | length = 24 | Hourly grid forecast |

```json
{
  "grid_forecast_24h": [
    {
      "hour": 0,
      "renewable_pct": 35.2,
      "carbon_intensity_gco2_kwh": 327.1,
      "tou_price_cents_kwh": 12,
      "tou_period": "super_off_peak",
      "status": "green"
    }
  ]
}
```

---

### GET /api/schedule

Returns an OptimizationResult (same shape as `calendar_update.data`).

```json
{
  "optimized_events": [],
  "total_savings_cents": 0.0,
  "total_carbon_avoided_g": 0.0,
  "optimization_confidence": 0.0
}
```

---

### POST /api/tasks (response)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `event_id` | string | UUID v4 | ID of the created event |
| `message` | string | non-empty | Confirmation text |

```json
{
  "event_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "message": "Task added and schedule re-optimized"
}
```

---

### POST /api/calendar/import (response)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `events_imported` | integer | >= 0 | Total events processed |
| `deferrable_events` | integer | >= 0 | Count of deferrable events |
| `non_deferrable_events` | integer | >= 0 | Count of non-deferrable events |
| `message` | string | non-empty | Summary text |

```json
{
  "events_imported": 3,
  "deferrable_events": 2,
  "non_deferrable_events": 1,
  "message": "Imported 3 events (2 deferrable, 1 fixed). Schedule re-optimized."
}
```

---

### POST /api/sensor (response)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `status` | string | "ok" | Acknowledgement |

```json
{
  "status": "ok"
}
```

---

### POST /api/settings (response)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `alpha` | float | 0.0 – 1.0 | Echoed cost weight |
| `beta` | float | 0.0 – 1.0 | Echoed carbon weight |

```json
{
  "alpha": 0.7,
  "beta": 0.3
}
```

---

### GET /api/attention

| Field | Type | Constraints | Description |
|---|---|---|---|
| `attention_weights` | array[float] | >= 0 items | Per-hour attention weights from the TFT model |
| `day_type` | string \| null | — | Day classification (e.g. "weekday", "weekend") |
| `anomaly_score` | float \| null | 0.0 – 1.0 | Anomaly detection score |
| `message` | string \| null | — | Present when no ML data is available |

**With ML data:**

```json
{
  "attention_weights": [0.12, 0.08, 0.05, 0.03, 0.02, 0.01, 0.01, 0.04, 0.09, 0.15, 0.18, 0.22],
  "day_type": "weekday",
  "anomaly_score": 0.15
}
```

**Fallback (no ML data):**

```json
{
  "attention_weights": [],
  "message": "No ML data yet"
}
```

---

### GET /api/insights

| Field | Type | Constraints | Description |
|---|---|---|---|
| `insights` | array[Insight] | >= 0 items | List of generated insights |

```json
{
  "insights": [
    {
      "message": "Your dryer was moved to 2 AM, saving 38¢ and 156g CO2.",
      "category": "schedule_optimization",
      "severity": "info",
      "insight_id": "schedule_optimization_1709164800"
    }
  ]
}
```

---

## 7. Shared Sub-Schemas

### ChannelReading

Used in: SensorReading (Hardware → Backend)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `channel_id` | integer | 0 – 3 | Physical channel index |
| `assigned_zone` | string | non-empty | Room / area label |
| `assigned_appliance` | string | non-empty | Appliance identifier |
| `current_amps` | float | >= 0 | RMS current in amperes |

---

### LiveChannel

Used in: sensor_update (Backend → iOS)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `channel_id` | integer | 0 – 3 | Channel index |
| `assigned_zone` | string | non-empty | Room / area |
| `assigned_appliance` | string | non-empty | Appliance name |
| `current_watts` | float | >= 0 | Watts (amps x 120 V) |
| `is_active` | boolean | — | current_watts > 0 |

---

### OptimizedEvent

Used in: calendar_update, GET /api/schedule

| Field | Type | Constraints | Description |
|---|---|---|---|
| `event_id` | string | UUID v4 | Unique event identifier |
| `title` | string | non-empty | Human-readable name |
| `original_start` | string | ISO 8601 UTC | Requested start |
| `original_end` | string | ISO 8601 UTC | Requested end |
| `optimized_start` | string | ISO 8601 UTC | Optimizer start |
| `optimized_end` | string | ISO 8601 UTC | Optimizer end |
| `channel_id` | integer | 0 – 3 | Target channel |
| `estimated_watts` | integer | > 0 | Power draw in watts |
| `savings_cents` | float | >= 0 | Cost saved |
| `carbon_avoided_g` | float | >= 0 | CO2 avoided in grams |
| `reason` | string | non-empty | Explanation |
| `grid_status_at_time` | string | "green" \| "yellow" \| "red" | Grid color at optimized time |
| `is_deferrable` | boolean | — | Deferrable flag |
| `was_moved` | boolean | — | True if times changed |

---

### GridSnapshot

Used in: grid_status.data.current, GET /api/dashboard

| Field | Type | Constraints | Description |
|---|---|---|---|
| `renewable_pct` | float | 0.0 – 100.0 | Renewable percentage |
| `carbon_intensity_gco2_kwh` | float | >= 0 | gCO2/kWh |
| `tou_price_cents_kwh` | integer | > 0 | Cents per kWh |
| `tou_period` | string | "super_off_peak" \| "off_peak" \| "peak" | TOU period |
| `status` | string | "green" \| "yellow" \| "red" | Grid color |

---

### GridHour

Used in: grid_status.data.forecast_next_3h, GET /api/forecast

| Field | Type | Constraints | Description |
|---|---|---|---|
| `hour` | integer | 0 – 23 | Hour of day (UTC) |
| `renewable_pct` | float | 0.0 – 100.0 | Forecasted renewable pct |
| `carbon_intensity_gco2_kwh` | float | >= 0 | Forecasted gCO2/kWh |
| `tou_price_cents_kwh` | integer | > 0 | TOU price |
| `tou_period` | string | "super_off_peak" \| "off_peak" \| "peak" | TOU period |
| `status` | string | "green" \| "yellow" \| "red" | Grid color |

---

### Insight (object)

Used in: insight WS message, GET /api/insights

| Field | Type | Constraints | Description |
|---|---|---|---|
| `message` | string | non-empty | Human-readable text |
| `category` | string | non-empty | Classification |
| `severity` | string | "info" \| "warning" \| "critical" | Importance level |
| `insight_id` | string | non-empty | Stable identifier |

---

## 8. Constants

| Constant | Value | Notes |
|---|---|---|
| VOLTAGE | 120 V | Applied to convert amps → watts |
| NUM_CHANNELS | 4 | Fixed CT-clamp count |
| BREAKER_LIMIT | 7200 W | 60 A x 120 V main breaker capacity |

### Channel Map

| channel_id | Zone | Default Appliance |
|---|---|---|
| 0 | kitchen | inductive_stove |
| 1 | laundry_room | dryer |
| 2 | garage | ev_charger |
| 3 | bedroom | air_conditioning |

### Grid Status Thresholds

| Status | TOU Price (cents/kWh) |
|---|---|
| green | <= 15 |
| yellow | 16 – 25 |
| red | > 25 |

### Time-of-Use Periods

| Period | Hours (UTC) |
|---|---|
| super_off_peak | 00:00 – 07:00 |
| off_peak | 07:00 – 16:00, 21:00 – 00:00 |
| peak | 16:00 – 21:00 |
