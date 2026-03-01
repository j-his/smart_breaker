# EnergyAI Smart Breaker -- API Guide

> **For iOS and hardware teammates.**
> Last updated: 2026-02-28

Hey team! This is the single source of truth for talking to the Smart Breaker
backend. Everything here is based on the FastAPI server running at
**localhost:8000**. If something looks wrong or you hit an edge case that isn't
covered, ping the backend channel and we'll update this doc.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Constants & Conventions](#constants--conventions)
3. [Channel Assignments](#channel-assignments)
4. [Grid Status Color Guide](#grid-status-color-guide)
5. [REST Endpoints](#rest-endpoints)
   - [GET /api/health](#get-apihealth)
   - [GET /api/dashboard](#get-apidashboard)
   - [GET /api/forecast](#get-apiforecast)
   - [GET /api/schedule](#get-apischedule)
   - [POST /api/tasks](#post-apitasks)
   - [POST /api/calendar/import](#post-apicalendarimport)
   - [POST /api/sensor](#post-apisensor)
   - [POST /api/settings](#post-apisettings)
   - [GET /api/insights](#get-apiinsights)
6. [WebSocket: Live Data](#websocket-live-data-wslocalhost8000wslive)
7. [WebSocket: Chat](#websocket-chat-wslocalhost8000wschat)
8. [TTS Audio Streaming (iOS)](#tts-audio-streaming-ios)

---

## Quick Start

### 1. Install dependencies

```bash
cd smart_breaker
pip install -r requirements.txt
```

### 2. Run the backend

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The server is now live at **http://localhost:8000**. You can hit the auto-docs
at http://localhost:8000/docs if you want the interactive Swagger UI.

### 3. Verify it's working

```bash
curl http://localhost:8000/api/health
```

You should get back something like:

```json
{
  "status": "ok",
  "hardware_connected": false,
  "buffer_fill": "0/96",
  "ws_clients": 0,
  "timestamp": "2026-02-28T14:30:00.000Z"
}
```

If you see that, you're good to go.

---

## Constants & Conventions

These are baked into the backend. Keep them handy.

| Constant         | Value                                              |
| ---------------- | -------------------------------------------------- |
| VOLTAGE          | 120 V                                              |
| NUM_CHANNELS     | 4                                                  |
| BREAKER_LIMIT    | 7200 W (60 A x 120 V)                             |
| TOU: super off-peak | 12:00 AM -- 7:00 AM                              |
| TOU: off-peak    | 7:00 AM -- 4:00 PM and 9:00 PM -- 12:00 AM        |
| TOU: peak        | 4:00 PM -- 9:00 PM                                |

**Important for hardware folks:** The sensor endpoint accepts current in
**amps**, not watts. The backend multiplies by 120 V internally to get watts.

All timestamps are ISO 8601 strings in UTC unless otherwise noted.

---

## Channel Assignments

Every sensor reading has four channels. Here's what they map to in our demo
setup:

| Channel | Zone         | Appliance        | Typical Wattage |
| ------- | ------------ | ---------------- | --------------- |
| Ch 0    | Kitchen      | Inductive Stove  | 1800 W          |
| Ch 1    | Laundry Room | Dryer            | 2400 W          |
| Ch 2    | Garage       | EV Charger       | 3600 W          |
| Ch 3    | Bedroom      | Air Conditioning | 1800 W          |

The total breaker limit is 7200 W across all four channels.

---

## Grid Status Color Guide

The backend classifies the current electricity price into three tiers. Use
these colors in the iOS UI to give users an at-a-glance read of the grid:

| Color    | Price Range   | TOU Period     | What It Means                              |
| -------- | ------------- | -------------- | ------------------------------------------ |
| `green`  | <= 15 c/kWh   | Super off-peak | Cheapest power -- run everything you can    |
| `yellow` | 16--25 c/kWh  | Off-peak       | Moderate pricing -- be selective            |
| `red`    | > 25 c/kWh    | Peak           | Expensive -- defer non-essential loads      |

The grid status string (e.g. `"green"`) is returned in the dashboard response
and also pushed over the live WebSocket.

---

## REST Endpoints

All REST endpoints live under the `/api` prefix. Every response is JSON.

---

### GET /api/health

A lightweight health check. Use this for connectivity tests, loading screens,
or keep-alive pings.

**curl:**

```bash
curl http://localhost:8000/api/health
```

**Response (200):**

```json
{
  "status": "ok",
  "hardware_connected": true,
  "buffer_fill": "12/96",
  "ws_clients": 2,
  "timestamp": "2026-02-28T14:30:00.000Z"
}
```

| Field                | Type   | Description                                           |
| -------------------- | ------ | ----------------------------------------------------- |
| status               | string | Always `"ok"` if the server is up                     |
| hardware_connected   | bool   | Whether the ESP32 / sensor hardware is actively connected |
| buffer_fill          | string | How many sensor readings are in the rolling buffer (e.g. 12 out of 96) |
| ws_clients           | int    | Number of active WebSocket connections                 |
| timestamp            | string | Current server time, ISO 8601                         |

---

### GET /api/dashboard

The main payload for the home screen. Returns live power readings, grid
status, and the latest optimization result.

**curl:**

```bash
curl http://localhost:8000/api/dashboard
```

**Response (200):**

```json
{
  "current_power": {
    "ch0_watts": 1750.5,
    "ch1_watts": 0.0,
    "ch2_watts": 3580.2,
    "ch3_watts": 1200.0,
    "total_watts": 6530.7
  },
  "grid_status": "red",
  "hardware_connected": true,
  "optimization": {
    "recommended_action": "Defer EV charging to super off-peak (12 AM - 7 AM)",
    "potential_savings_cents": 42,
    "carbon_avoided_g": 180,
    "confidence": 0.87
  }
}
```

| Field                          | Type   | Description                                              |
| ------------------------------ | ------ | -------------------------------------------------------- |
| current_power.ch0_watts        | float  | Kitchen / Inductive Stove power draw                     |
| current_power.ch1_watts        | float  | Laundry Room / Dryer power draw                          |
| current_power.ch2_watts        | float  | Garage / EV Charger power draw                           |
| current_power.ch3_watts        | float  | Bedroom / Air Conditioning power draw                    |
| current_power.total_watts      | float  | Sum of all channels                                      |
| grid_status                    | string | One of `"green"`, `"yellow"`, `"red"`                    |
| hardware_connected             | bool   | Whether sensor hardware is online                        |
| optimization                   | object | Latest scheduling recommendation (may be null if no optimization has run) |

---

### GET /api/forecast

Returns the next 24 hours of grid pricing and carbon intensity predictions.
Great for building the timeline chart in the iOS app.

**curl:**

```bash
curl http://localhost:8000/api/forecast
```

**Response (200):**

```json
{
  "grid_forecast_24h": [
    {
      "hour": 0,
      "time_label": "12:00 AM",
      "price_cents_kwh": 8.2,
      "carbon_g_kwh": 210,
      "tou_period": "super_off_peak",
      "grid_status": "green"
    },
    {
      "hour": 1,
      "time_label": "1:00 AM",
      "price_cents_kwh": 7.9,
      "carbon_g_kwh": 205,
      "tou_period": "super_off_peak",
      "grid_status": "green"
    },
    {
      "hour": 16,
      "time_label": "4:00 PM",
      "price_cents_kwh": 32.1,
      "carbon_g_kwh": 480,
      "tou_period": "peak",
      "grid_status": "red"
    },
    {
      "hour": 23,
      "time_label": "11:00 PM",
      "price_cents_kwh": 14.5,
      "carbon_g_kwh": 250,
      "tou_period": "off_peak",
      "grid_status": "green"
    }
  ]
}
```

The array always contains 24 entries (hours 0 through 23). The example above
is abbreviated for readability.

| Field            | Type   | Description                                     |
| ---------------- | ------ | ----------------------------------------------- |
| hour             | int    | Hour of day (0--23)                              |
| time_label       | string | Human-friendly label                            |
| price_cents_kwh  | float  | Predicted electricity price in cents per kWh    |
| carbon_g_kwh     | int    | Predicted carbon intensity in grams CO2 per kWh |
| tou_period       | string | One of `super_off_peak`, `off_peak`, `peak`      |
| grid_status      | string | Color tier: `green`, `yellow`, or `red`          |

---

### GET /api/schedule

Returns the optimized schedule -- what should run when, and how much money and
carbon the optimization saves.

**curl:**

```bash
curl http://localhost:8000/api/schedule
```

**Response (200):**

```json
{
  "optimized_events": [
    {
      "task_title": "EV Charging",
      "channel_id": 2,
      "start_time": "2026-02-28T01:00:00Z",
      "end_time": "2026-02-28T04:00:00Z",
      "estimated_watts": 3600,
      "tou_period": "super_off_peak",
      "savings_vs_peak_cents": 58
    },
    {
      "task_title": "Laundry",
      "channel_id": 1,
      "start_time": "2026-02-28T02:00:00Z",
      "end_time": "2026-02-28T03:00:00Z",
      "estimated_watts": 2400,
      "tou_period": "super_off_peak",
      "savings_vs_peak_cents": 19
    }
  ],
  "total_savings_cents": 77,
  "total_carbon_avoided_g": 320,
  "optimization_confidence": 0.91
}
```

| Field                     | Type   | Description                                        |
| ------------------------- | ------ | -------------------------------------------------- |
| optimized_events          | array  | List of scheduled tasks with timing details         |
| total_savings_cents       | int    | Total estimated savings compared to running everything at peak |
| total_carbon_avoided_g    | int    | Total grams of CO2 avoided                          |
| optimization_confidence   | float  | Model confidence score (0.0 -- 1.0)                 |

---

### POST /api/tasks

Add a new task for the optimizer to schedule. This is how the iOS app tells the
backend "the user wants to run the dryer sometime today."

**curl:**

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Dry clothes",
    "channel_id": 1,
    "estimated_watts": 2400,
    "estimated_duration_min": 60,
    "deadline": "2026-02-28T21:00:00Z",
    "is_deferrable": true,
    "priority": "medium"
  }'
```

**Request body:**

| Field                  | Type    | Required | Default    | Description                                     |
| ---------------------- | ------- | -------- | ---------- | ----------------------------------------------- |
| title                  | string  | yes      | --         | Human-readable name for the task                |
| channel_id             | int     | no       | null       | Which channel (0--3) this task runs on           |
| estimated_watts        | int     | no       | 1000       | Expected power draw in watts                    |
| estimated_duration_min | int     | no       | 60         | How long the task takes in minutes              |
| deadline               | string  | no       | null       | ISO 8601 deadline (task must finish by this time) |
| is_deferrable          | bool    | no       | true       | Can the optimizer move this task around?        |
| priority               | string  | no       | `"medium"` | One of `"low"`, `"medium"`, `"high"`             |

**Response (201):**

```json
{
  "task_id": "a3f1c2d4-5678-9abc-def0-1234567890ab",
  "title": "Dry clothes",
  "channel_id": 1,
  "estimated_watts": 2400,
  "estimated_duration_min": 60,
  "deadline": "2026-02-28T21:00:00Z",
  "is_deferrable": true,
  "priority": "medium",
  "status": "pending",
  "created_at": "2026-02-28T14:30:00.000Z"
}
```

---

### POST /api/calendar/import

Import events from an iCal feed or a JSON array. The backend figures out which
events are deferrable (things like "run laundry" vs. "dentist appointment") and
feeds the deferrable ones into the optimizer.

**curl (iCal):**

```bash
curl -X POST http://localhost:8000/api/calendar/import \
  -H "Content-Type: application/json" \
  -d '{
    "ical_data": "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Do laundry\nDTSTART:20260228T180000Z\nDTEND:20260228T190000Z\nEND:VEVENT\nEND:VCALENDAR"
  }'
```

**curl (JSON events):**

```bash
curl -X POST http://localhost:8000/api/calendar/import \
  -H "Content-Type: application/json" \
  -d '{
    "json_events": [
      {
        "title": "Charge Tesla",
        "start": "2026-02-28T18:00:00Z",
        "end": "2026-02-28T22:00:00Z"
      },
      {
        "title": "Run dishwasher",
        "start": "2026-02-28T19:00:00Z",
        "end": "2026-02-28T20:00:00Z"
      }
    ]
  }'
```

**Request body:**

| Field       | Type   | Required         | Description                                |
| ----------- | ------ | ---------------- | ------------------------------------------ |
| ical_data   | string | one of these two | Raw iCal string                            |
| json_events | array  | one of these two | Array of objects with title, start, end     |

Send either `ical_data` OR `json_events`, not both.

**Response (200):**

```json
{
  "events_imported": 2,
  "deferrable_count": 2,
  "events": [
    {
      "title": "Charge Tesla",
      "start": "2026-02-28T18:00:00Z",
      "end": "2026-02-28T22:00:00Z",
      "is_deferrable": true
    },
    {
      "title": "Run dishwasher",
      "start": "2026-02-28T19:00:00Z",
      "end": "2026-02-28T20:00:00Z",
      "is_deferrable": true
    }
  ]
}
```

---

### POST /api/sensor

**This is the hardware endpoint.** The ESP32 posts sensor readings here.

Each reading contains four channels of current data in **amps** (not watts).
The backend multiplies by 120 V to convert to watts internally.

**curl:**

```bash
curl -X POST http://localhost:8000/api/sensor \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "esp32-breaker-01",
    "timestamp": "2026-02-28T14:30:05.123Z",
    "channels": [
      {
        "channel_id": 0,
        "zone": "Kitchen",
        "appliance": "Inductive Stove",
        "current_amps": 15.0
      },
      {
        "channel_id": 1,
        "zone": "Laundry Room",
        "appliance": "Dryer",
        "current_amps": 0.0
      },
      {
        "channel_id": 2,
        "zone": "Garage",
        "appliance": "EV Charger",
        "current_amps": 30.0
      },
      {
        "channel_id": 3,
        "zone": "Bedroom",
        "appliance": "Air Conditioning",
        "current_amps": 10.0
      }
    ]
  }'
```

**Request body:**

| Field                      | Type   | Description                                    |
| -------------------------- | ------ | ---------------------------------------------- |
| device_id                  | string | Unique identifier for the hardware device      |
| timestamp                  | string | ISO 8601 timestamp of the reading              |
| channels                   | array  | Exactly 4 channel objects                      |
| channels[].channel_id      | int    | Channel index (0--3)                            |
| channels[].zone            | string | Room / zone name                               |
| channels[].appliance       | string | Appliance name                                 |
| channels[].current_amps    | float  | Current draw in **amps** (NOT watts)           |

**Response (200):**

```json
{
  "received": true,
  "device_id": "esp32-breaker-01",
  "timestamp": "2026-02-28T14:30:05.123Z",
  "total_watts": 6600.0,
  "breaker_utilization": 0.917
}
```

Note: `total_watts` is 6600 because (15 + 0 + 30 + 10) amps x 120 V = 6600 W,
and `breaker_utilization` is 6600 / 7200 = 0.917 (91.7% of breaker capacity).

---

### POST /api/settings

Update the optimizer's cost-vs-carbon weighting. Both values should be between
0 and 1. A higher alpha means the optimizer cares more about saving money; a
higher beta means it cares more about reducing carbon.

**curl:**

```bash
curl -X POST http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "alpha": 0.7,
    "beta": 0.3
  }'
```

**Request body:**

| Field | Type  | Range   | Description                         |
| ----- | ----- | ------- | ----------------------------------- |
| alpha | float | 0.0--1.0 | Weight for cost optimization        |
| beta  | float | 0.0--1.0 | Weight for carbon optimization      |

**Response (200):**

```json
{
  "alpha": 0.7,
  "beta": 0.3,
  "updated_at": "2026-02-28T14:35:00.000Z"
}
```

---

### GET /api/insights

Returns recent AI-generated insights about the user's energy usage. These are
the same insights that get pushed over the live WebSocket and can trigger TTS
narration.

**curl:**

```bash
curl http://localhost:8000/api/insights
```

**Response (200):**

```json
{
  "insights": [
    {
      "insight_id": "ins_001",
      "timestamp": "2026-02-28T14:30:00.000Z",
      "category": "savings",
      "message": "Your EV charged during peak hours yesterday. Shifting to super off-peak could save you about 58 cents per session.",
      "severity": "suggestion"
    },
    {
      "insight_id": "ins_002",
      "timestamp": "2026-02-28T13:00:00.000Z",
      "category": "anomaly",
      "message": "Kitchen power draw spiked to 1800W at 1 PM but no stove task was scheduled. Was that intentional?",
      "severity": "warning"
    }
  ]
}
```

| Field      | Type   | Description                                          |
| ---------- | ------ | ---------------------------------------------------- |
| insight_id | string | Unique ID for correlation with TTS audio chunks      |
| timestamp  | string | When the insight was generated                       |
| category   | string | E.g. `savings`, `anomaly`, `carbon`, `schedule`       |
| message    | string | Human-readable insight text                          |
| severity   | string | One of `info`, `suggestion`, `warning`, `critical`    |

---

## WebSocket: Live Data (`ws://localhost:8000/ws/live`)

This is the main real-time feed. Connect once when the app launches and keep it
open. The backend pushes events as they happen -- you never need to poll.

### Connecting

**JavaScript / Swift pseudocode:**

```
ws = new WebSocket("ws://localhost:8000/ws/live")
```

**wscat (for terminal testing):**

```bash
npx wscat -c ws://localhost:8000/ws/live
```

### Message Types

Every message is a JSON object with a `type` field at the top level. Here's
every type you'll receive:

---

#### sensor_update

Pushed every time the backend receives a new sensor reading from the hardware.
This is your real-time power data.

```json
{
  "type": "sensor_update",
  "data": {
    "timestamp": "2026-02-28T14:30:05.123Z",
    "ch0_watts": 1800.0,
    "ch1_watts": 0.0,
    "ch2_watts": 3600.0,
    "ch3_watts": 1200.0,
    "total_watts": 6600.0,
    "breaker_utilization": 0.917
  }
}
```

---

#### calendar_update

Pushed when calendar events are imported or the schedule is re-optimized.

```json
{
  "type": "calendar_update",
  "data": {
    "action": "events_imported",
    "events_count": 3,
    "next_scheduled": {
      "title": "EV Charging",
      "start_time": "2026-02-28T01:00:00Z",
      "channel_id": 2
    }
  }
}
```

---

#### grid_status

Pushed whenever the grid pricing tier changes (e.g. transitioning from off-peak
to peak).

```json
{
  "type": "grid_status",
  "data": {
    "status": "red",
    "price_cents_kwh": 32.1,
    "carbon_g_kwh": 480,
    "tou_period": "peak",
    "changed_at": "2026-02-28T16:00:00.000Z"
  }
}
```

---

#### insight

A new AI-generated insight is available.

```json
{
  "type": "insight",
  "data": {
    "insight_id": "ins_003",
    "category": "savings",
    "message": "Shifting your dryer to the 2 AM -- 3 AM window tonight would save about 19 cents and avoid 85g of CO2.",
    "severity": "suggestion",
    "timestamp": "2026-02-28T15:00:00.000Z"
  }
}
```

---

#### anomaly_alert

Something unexpected happened with power draw. Show this prominently in the UI.

```json
{
  "type": "anomaly_alert",
  "data": {
    "channel_id": 0,
    "zone": "Kitchen",
    "appliance": "Inductive Stove",
    "expected_watts": 0,
    "actual_watts": 1800.0,
    "message": "Unexpected power draw on Kitchen / Inductive Stove. No task is scheduled for this channel.",
    "severity": "warning",
    "timestamp": "2026-02-28T13:05:00.000Z"
  }
}
```

---

#### tts_audio

Streamed TTS audio chunks. See the dedicated [TTS Audio Streaming](#tts-audio-streaming-ios) section below for the full explanation.

```json
{
  "type": "tts_audio",
  "data": {
    "audio": "SUQzBAAAAAAAI1RTU0UAAAA...",
    "format": "mp3_44100_128",
    "insight_id": "ins_003",
    "is_final": false
  }
}
```

---

#### ml_status

Status updates from the ML pipeline (model training, inference runs, etc.).
Useful for showing a loading indicator while the model is crunching.

```json
{
  "type": "ml_status",
  "data": {
    "stage": "inference",
    "model": "load_forecaster",
    "progress": 0.75,
    "message": "Running 24-hour load forecast...",
    "timestamp": "2026-02-28T14:29:00.000Z"
  }
}
```

---

## WebSocket: Chat (`ws://localhost:8000/ws/chat`)

This powers the conversational AI feature. The user sends a message, and the
backend streams back a response in chunks (like ChatGPT-style streaming).

### Connecting

```bash
npx wscat -c ws://localhost:8000/ws/chat
```

### Sending a message

Send a JSON object with a `message` field:

```json
{
  "message": "Why is my electricity bill so high this month?"
}
```

### Receiving the response

The backend streams back `chat_response` chunks. Each chunk has a `delta`
(the new text) and a `done` flag. Concatenate the deltas to build the full
response.

**Streaming chunk:**

```json
{
  "type": "chat_response",
  "data": {
    "delta": "Based on your usage data, your EV charger ",
    "done": false,
    "message_id": "msg_abc123"
  }
}
```

**Another chunk:**

```json
{
  "type": "chat_response",
  "data": {
    "delta": "has been running during peak hours (4 PM - 9 PM) most days this week. ",
    "done": false,
    "message_id": "msg_abc123"
  }
}
```

**Final chunk:**

```json
{
  "type": "chat_response",
  "data": {
    "delta": "Shifting it to super off-peak could save you around $4.20 this month.",
    "done": true,
    "message_id": "msg_abc123"
  }
}
```

On the iOS side, append each `delta` to the displayed text as it arrives.
When `done` is `true`, the response is complete.

---

## TTS Audio Streaming (iOS)

This section is mainly for the iOS team. When the backend generates an insight,
it can also generate a spoken narration via ElevenLabs. The audio arrives as
a stream of base64-encoded MP3 chunks over the live WebSocket.

### How it works

1. The backend generates an insight and sends it over the `insight` message type.
2. Immediately after, it begins streaming `tts_audio` messages tied to that
   insight's `insight_id`.
3. Each `tts_audio` chunk contains a base64-encoded piece of MP3 audio.
4. The final chunk has `audio` set to an empty string and `is_final` set to
   `true`.

### Message format

**Audio chunk (not final):**

```json
{
  "type": "tts_audio",
  "data": {
    "audio": "SUQzBAAAAAAAI1RTU0UAAAA...",
    "format": "mp3_44100_128",
    "insight_id": "ins_003",
    "is_final": false
  }
}
```

**Final chunk (end of stream):**

```json
{
  "type": "tts_audio",
  "data": {
    "audio": "",
    "format": "mp3_44100_128",
    "insight_id": "ins_003",
    "is_final": true
  }
}
```

| Field      | Type   | Description                                                |
| ---------- | ------ | ---------------------------------------------------------- |
| audio      | string | Base64-encoded MP3 data (empty string on final chunk)      |
| format     | string | Always `mp3_44100_128` (MP3, 44.1 kHz, 128 kbps)           |
| insight_id | string | Correlates this audio to a specific insight                |
| is_final   | bool   | `true` on the last chunk, `false` on all others             |

### iOS Implementation Notes

- **Start playback immediately on the first chunk.** Don't wait for the full
  stream. Decode the base64 to raw bytes and feed them into an AVAudioPlayer
  or AVAudioEngine buffer.
- **Accumulate chunks** by appending decoded bytes to a data buffer. Each
  chunk is a valid continuation of the MP3 stream.
- **Use `insight_id`** to match audio to the corresponding insight card in the
  UI. You might want to show a speaker icon or animation while audio is playing.
- **Clean up on `is_final`:** When you receive the final chunk, you know the
  full audio has been delivered. Flush any remaining buffer and let playback
  finish naturally.
- The format is always 44.1 kHz / 128 kbps MP3, so you can hardcode your
  audio session configuration for that.

### Pseudocode (Swift-ish)

```swift
var audioBuffer = Data()

func onWebSocketMessage(_ message: WSMessage) {
    guard message.type == "tts_audio" else { return }

    let chunk = message.data

    if !chunk.is_final {
        // Decode base64 and append to buffer
        if let audioData = Data(base64Encoded: chunk.audio) {
            audioBuffer.append(audioData)
        }

        // Start playback on first chunk
        if !isPlaying {
            startStreamingPlayback(audioBuffer)
        }
    } else {
        // Final chunk -- flush buffer and finish
        finishPlayback()
        audioBuffer = Data()
    }
}
```

---

## Quick Reference: All Endpoints at a Glance

| Method | Path                 | Description                         |
| ------ | -------------------- | ----------------------------------- |
| GET    | /api/health          | Health check and connection status   |
| GET    | /api/dashboard       | Live power, grid status, optimization |
| GET    | /api/forecast        | 24-hour grid pricing forecast        |
| GET    | /api/schedule        | Optimized task schedule              |
| POST   | /api/tasks           | Add a new task for the optimizer     |
| POST   | /api/calendar/import | Import iCal or JSON events           |
| POST   | /api/sensor          | Submit hardware sensor readings      |
| POST   | /api/settings        | Update cost/carbon weights           |
| GET    | /api/insights        | Recent AI-generated insights         |
| WS     | /ws/live             | Real-time data stream                |
| WS     | /ws/chat             | Conversational AI chat               |

---

That's everything. If you're unsure about something, the FastAPI auto-docs at
http://localhost:8000/docs are interactive and always in sync with the actual
code. Happy building!
