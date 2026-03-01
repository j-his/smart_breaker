# Save Box

> Created by Team Noise Floor
>
> Hack for Humanity 2026

---

Save Box is a smart, AI-enabled breaker box that allows users to plan, manage, and control their household energy usage. Three-brain AI architecture: ML forecasting, LLM explanations, and voice narration — all connected to physical hardware via an ESP32-S3 smart breaker.

## Architecture

```
ESP32-S3 (CT clamps, relays, OLEDs, e-ink)
    |
    |-- BLE --> iOS App (SwiftUI)
    |              |-- Device monitoring
    |              |-- Calendar optimization
    |              |-- AI insights + chat
    |              +-- Home screen widget
    |
    +-- HTTP POST --> FastAPI Backend
                        |-- Brain 1: TFT model (5.2M params) -- forecasting + anomaly detection
                        |-- Brain 2: Groq LLM -- natural language explanations + chat
                        |-- Brain 3: ElevenLabs TTS -- voice narration
                        |-- OR-Tools MILP optimizer -- schedule optimization
                        +-- WebSocket streaming --> iOS App
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js (optional, for WebSocket test page)
- Xcode 16+ on macOS (for iOS app)
- PlatformIO (for ESP32 firmware)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   GROQ_API_KEY=your_key
#   ELEVENLABS_API_KEY=your_key
#   WATTTIME_USERNAME=your_username
#   WATTTIME_PASSWORD=your_password

# Run the server
DEMO_MODE=true python -m uvicorn backend.main:app --reload --port 8000
```

The server starts at http://localhost:8000. API docs at http://localhost:8000/docs.

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| DEMO_MODE | true | Use synthetic sensor data when no ESP32 is connected |
| MODEL_PROFILE | cpu | Set to `gpu` to use the full 5.2M param TFT model |
| ELEVENLABS_TTS_ENABLED | false | Enable voice narration |
| GROQ_API_KEY | — | Required for AI chat and insight explanations |

### iOS App Setup

```bash
cd breakerios
open breakerios.xcodeproj
```

1. Open in Xcode on macOS
2. Select your development team in Signing & Capabilities
3. Add the Info.plist to the project (contains BLE permissions)
4. Build and run on a physical iPhone (BLE requires real device)

In Settings, configure the server URL to point to your backend (e.g. `http://192.168.1.x:8000`).

To add the widget:
- Add a Widget Extension target in Xcode
- Add the source from `BreakerWidget/BreakerWidget.swift`
- Configure an App Group (`group.com.tongtonginc.breakerios`) for shared UserDefaults

### ESP32 Firmware Setup

```bash
cd firmware

# Install PlatformIO CLI (if not installed)
pip install platformio

# Build
pio run

# Upload to ESP32 (auto-detects port, or specify)
pio run -t upload
# or: pio run -t upload --upload-port COM3

# Monitor serial output
pio device monitor
```

The ESP32 advertises as "EnergyAI-XXXX" over BLE. Pair via the iOS app, enter WiFi credentials, and the device will start posting sensor data to your backend.

### Hardware Wiring

| Function | GPIO | Notes |
|----------|------|-------|
| CT Clamp CH0-3 (ADC) | 8, 14, 16, 18 | SCT-013-000, 1.65V midpoint bias |
| Relay CH0-3 | 21, 17, 19, 15 | Active HIGH |
| I2C SDA/SCL (OLED mux) | 3, 9 | TCA9548A for 4x SSD1306 |
| Button CH2-3 | 20, 38 | CH0-1 TBD (I2C conflict) |
| E-ink SPI | 12, 11, 47, 46, 45, 48 | Bit-banged |
| E-ink Power | 7 | Enable pin |

## Hardware Teammate Quick Start

If you're working on the hardware (ESP32 wiring, CT clamps, relays, displays), see the full guide:

**[firmware/HARDWARE_GUIDE.md](firmware/HARDWARE_GUIDE.md)**

Quick version:

1. Install PlatformIO: `pip install platformio`
2. Flash: `cd firmware && pio run -t upload`
3. Monitor serial: `pio device monitor` (115200 baud)
4. Scan for BLE device `EnergyAI-XXXX` from the iOS app or nRF Connect
5. Send WiFi credentials via BLE → device auto-connects and starts POSTing sensor data
6. **Important:** CH0/CH1 button GPIOs need to be assigned — see the [button conflict section](firmware/HARDWARE_GUIDE.md#4-button-conflict--action-required) in the hardware guide

The guide covers the full BLE protocol, GPIO pin map, CT clamp calibration, relay wiring, and a step-by-step testing checklist.

## Testing

```bash
# Backend unit tests (109 tests)
cd backend
python -m pytest tests/ -v

# Smoke test (requires running server)
python scripts/smoke_test.py

# WebSocket test page
# Open docs/ws_test.html in a browser
```

## Repository Structure

```
smart_breaker/
|-- backend/                 # Python FastAPI backend
|   |-- ml/                  # TFT model, inference, training
|   |-- llm/                 # Groq chat, narrator, context
|   |-- tts/                 # ElevenLabs voice streaming
|   |-- optimizer/           # OR-Tools MILP scheduler
|   |-- ingestion/           # Sensor data + grid status
|   |-- routes/              # REST + WebSocket endpoints
|   +-- config.py            # All configuration
|-- breakerios/              # iOS SwiftUI app
|   +-- breakerios/
|       |-- Services/        # BLE, WebSocket, API, TTS
|       |-- Components/      # Reusable UI components
|       +-- *.swift          # Views + Models
|-- cad/                     # Autodesk Inventor enclosure
|-- firmware/                # ESP32-S3 PlatformIO project
|   +-- src/                 # BLE, WiFi, CT reader, relays, displays
|-- animation/               # Blender assets for promotional materials
|-- data/                    # SQLite backend database
|-- scripts/                 # Training + smoke test scripts
|-- docs/                    # API docs, WS test page
+-- tests/                   # Backend pytest suite
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Server status + hardware connection |
| GET | /api/dashboard | Current power, grid status, optimization |
| GET | /api/forecast | 24-hour grid forecast |
| GET | /api/schedule | Optimized event schedule |
| GET | /api/insights | AI-generated insights |
| GET | /api/attention | TFT attention weights |
| POST | /api/sensor | Receive ESP32 sensor data |
| POST | /api/tasks | Add task for optimization |
| POST | /api/settings | Update optimization weights |
| POST | /api/calendar/import | Import iCal/JSON events |
| WS | /ws/live | Real-time sensor + grid + insight stream |
| WS | /ws/chat | AI chat with streaming responses |

---

(c) 2026

Proudly designed, manufactured, and assembled by Noise Floor in California
