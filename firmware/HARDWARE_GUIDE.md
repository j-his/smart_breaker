# EnergyAI Smart Breaker — Hardware Setup Guide

Everything you need to flash the ESP32-S3, wire the hardware, and test the system independently.

---

## 1. BLE Protocol Spec

The ESP32 advertises as **EnergyAI-XXYY** (where XXYY = last 2 bytes of the MAC address in hex, e.g. `EnergyAI-1A2B`). It exposes one GATT service with 5 characteristics:

| UUID | Name | Access | Data Format |
|------|------|--------|-------------|
| `12340001-...-987654` | **Service** | — | Primary service |
| `12340002-...-987654` | WiFi SSID | Write | UTF-8 string, max 32 chars |
| `12340003-...-987654` | WiFi Password | Write | UTF-8 string, max 64 chars |
| `12340004-...-987654` | WiFi Status | Read / Notify | 1 byte (see table below) |
| `12340005-...-987654` | Breaker State | Read / Notify | 1 byte bitmap |
| `12340006-...-987654` | Breaker Command | Write | 2 bytes |

Full UUID base: `1234000X-1234-5678-9ABC-FEDCBA987654` (replace X with 1–6).

### WiFi Status Byte

| Value | Meaning |
|-------|---------|
| `0x00` | Disconnected |
| `0x01` | Connecting |
| `0x02` | Connected |
| `0x03` | Failed |

### Breaker State Byte

Bitmap — bit N corresponds to channel N (0–3). `1` = relay ON, `0` = relay OFF.

Example: `0b00001011` → CH0 ON, CH1 ON, CH2 OFF, CH3 ON.

### Breaker Command (Write)

2 bytes: `[channel_id, state]`
- `channel_id`: 0–3
- `state`: 0 = OFF, non-zero = ON

---

## 2. WiFi Configuration Flow

1. On boot, the ESP32 tries to auto-connect using credentials saved in NVS (non-volatile storage).
2. If no saved credentials exist, it waits for BLE writes.
3. Write the SSID to characteristic `12340002`, then write the password to `12340003`.
4. Writing the password automatically triggers `wifi_connect()`.
5. Subscribe to characteristic `12340004` (WiFi Status) for connection updates.
6. Once connected (`0x02`), credentials are persisted in NVS — they survive reboots.

NVS namespace: `"wifi"`, keys: `"ssid"` and `"pass"`.

Connection timeout: 15 seconds. Auto-reconnect delay: 5 seconds.

---

## 3. GPIO Pin Map

### CT Clamp ADC Inputs (Analog)

| Channel | GPIO | Sensor |
|---------|------|--------|
| CH0 | 8 | SCT-013-000 |
| CH1 | 14 | SCT-013-000 |
| CH2 | 16 | SCT-013-000 |
| CH3 | 18 | SCT-013-000 |

### Relay Outputs (Digital, Active HIGH)

| Channel | GPIO |
|---------|------|
| CH0 | 21 |
| CH1 | 17 |
| CH2 | 19 |
| CH3 | 15 |

HIGH = relay ON, LOW = relay OFF. All relays initialize to ON at startup.

### Button Inputs (Digital, INPUT_PULLUP)

| Channel | GPIO | Status |
|---------|------|--------|
| CH0 | **TBD** | See conflict note below |
| CH1 | **TBD** | See conflict note below |
| CH2 | 20 | Ready |
| CH3 | 38 | Ready |

Debounce: 50 ms (software). Buttons use FALLING-edge interrupts.

### I2C Bus (OLEDs + Multiplexer)

| Signal | GPIO |
|--------|------|
| SDA | 3 |
| SCL | 9 |

Multiplexer: TCA9548A at address `0x70`. Each OLED is an SSD1306 128x32 at address `0x3C`. I2C clock: 400 kHz.

### E-ink Display (Bit-banged SPI)

| Signal | GPIO |
|--------|------|
| MOSI | 12 |
| CLK | 11 |
| CS | 47 |
| DC | 46 |
| RST | 45 |
| BUSY | 48 |
| POWER | 7 |

Model: GDEY0213B74 (2.13" B/W, 250x122 px). Power pin controls display on/off (powered down between refreshes).

### Complete Pin Summary

```
GPIO 0  — (reserved, do not use for buttons)
GPIO 3  — I2C SDA
GPIO 7  — E-ink POWER
GPIO 8  — CT CH0 (analog)
GPIO 9  — I2C SCL
GPIO 11 — E-ink CLK
GPIO 12 — E-ink MOSI
GPIO 14 — CT CH1 (analog)
GPIO 15 — RELAY CH3
GPIO 16 — CT CH2 (analog)
GPIO 17 — RELAY CH1
GPIO 18 — CT CH3 (analog)
GPIO 19 — RELAY CH2
GPIO 20 — BUTTON CH2
GPIO 21 — RELAY CH0
GPIO 38 — BUTTON CH3
GPIO 45 — E-ink RST
GPIO 46 — E-ink DC
GPIO 47 — E-ink CS
GPIO 48 — E-ink BUSY
```

---

## 4. Button Conflict — ACTION REQUIRED

**Problem:** CH0 and CH1 buttons were originally assigned to GPIO 3 and 9, which are already used by I2C (SDA/SCL). They are currently set to GPIO 0 as placeholders and skipped during initialization.

**What to do:**

1. Pick two free GPIOs. Suggested: **GPIO 1** and **GPIO 2** (both available on ESP32-S3-DevKitC-1, no conflicts with the pins above).
2. Update `src/config.h` lines 39–40:
   ```c
   #define BUTTON_PIN_CH0 1   // was 0 (placeholder)
   #define BUTTON_PIN_CH1 2   // was 0 (placeholder)
   ```
3. Wire the physical buttons to the new GPIOs (active LOW with internal pull-up).
4. Rebuild and flash.

Other free GPIOs you could use instead: 4, 5, 6, 10, 13, 39, 40, 41, 42 (verify against your specific DevKitC-1 board variant — some may be used for USB/JTAG).

---

## 5. CT Clamp Calibration

### Hardware Setup (SCT-013-000)

- **Turns ratio:** 2000:1
- **Burden resistor:** 33 ohms (across CT secondary)
- **Midpoint bias:** 1.65V (resistor divider from 3.3V to create DC offset)
- **Mains voltage:** 120V (North America)

### ADC Settings

- Resolution: 12-bit (0–4095)
- Reference voltage: 3.3V
- Samples per reading: 1000 (~1 full AC cycle at 60 Hz)

### Calculation Pipeline

```
raw ADC count
  → voltage:         V = (count × 3.3) / 4095
  → center:          V_centered = V − 1.65
  → RMS:             V_rms = sqrt( sum(V_centered²) / 1000 )
  → secondary amps:  I_sec = V_rms / 33
  → primary amps:    I_pri = I_sec × 2000
  → watts:           P = I_pri × 120
```

Noise floor: readings below 0.1A are zeroed out.

### Adjusting Calibration

All constants are in `src/config.h`:

| Constant | Default | What to Change |
|----------|---------|----------------|
| `CT_BURDEN_R` | 33.0 | If using a different burden resistor |
| `CT_TURNS_RATIO` | 2000.0 | If using a different CT clamp model |
| `CT_MIDPOINT_V` | 1.65 | If your bias circuit uses a different voltage |
| `MAINS_VOLTAGE` | 120.0 | If not in North America (e.g. 230V for EU) |
| `CT_SAMPLES` | 1000 | More samples = smoother, but slower reads |

---

## 6. Relay Wiring

- **Control logic:** Active HIGH — GPIO HIGH turns the relay ON.
- **Default state:** All 4 relays start ON at boot.
- **GPIOs:** CH0=21, CH1=17, CH2=19, CH3=15.

Each relay GPIO drives a relay module (typically via optocoupler or transistor driver). Ensure your relay module accepts 3.3V logic; if it requires 5V logic, add a level shifter.

The relay state bitmap is sent over BLE (characteristic `12340005`) and updates on every state change.

---

## 7. Flashing the Firmware

### Prerequisites

1. Install [PlatformIO CLI](https://platformio.org/install/cli):
   ```bash
   pip install platformio
   ```
2. Connect the ESP32-S3-DevKitC-1 via USB-C.
3. Check which COM port it appears on (Windows: Device Manager → Ports).

### Build & Upload

```bash
cd firmware

# Build
pio run

# Upload (auto-detect port)
pio run -t upload

# Or specify port explicitly
pio run -t upload --upload-port COM3
```

### Serial Monitor

```bash
pio device monitor
```

Baud rate: 115200. You should see boot messages, BLE advertising start, and sensor readings every 10 seconds.

### Build Configuration

- Board: `esp32-s3-devkitc-1`
- Framework: Arduino
- Partition: `huge_app.csv` (needed for BLE + display libraries)
- Key build flags: `CONFIG_BT_NIMBLE_ENABLED=1`, `ARDUINO_USB_CDC_ON_BOOT=1`

### Libraries (auto-installed by PlatformIO)

- NimBLE-Arduino ^1.4.1 (BLE stack)
- Adafruit SSD1306 ^2.5.7 (OLED driver)
- Adafruit GFX Library ^1.11.5 (graphics)
- ArduinoJson ^6.21.3 (JSON for HTTP POST)
- Wire (I2C, built-in)

---

## 8. Testing Checklist

Work through these in order after flashing:

### 8.1 Serial Output Check

- [ ] Open serial monitor (`pio device monitor`)
- [ ] Confirm boot messages appear (WiFi init, BLE start, task creation)
- [ ] Confirm sensor readings print every 10 seconds (CH0–CH3 amps/watts)

### 8.2 BLE Scan

- [ ] Use the iOS app (or nRF Connect / LightBlue on any phone) to scan for BLE devices
- [ ] Find `EnergyAI-XXXX` in the scan results
- [ ] Connect and verify you can see the service UUID `12340001-...`
- [ ] Write a test SSID to characteristic `12340002`
- [ ] Write a test password to characteristic `12340003`
- [ ] Read characteristic `12340004` — should transition from `0x01` (connecting) to `0x02` (connected) or `0x03` (failed)

### 8.3 WiFi Connection

- [ ] After sending valid WiFi credentials via BLE, confirm serial output shows "WiFi connected"
- [ ] Confirm the WiFi status characteristic reads `0x02`
- [ ] Reboot the ESP32 — it should auto-reconnect using saved NVS credentials

### 8.4 Relay Click Test

- [ ] Send a breaker command via BLE: write `[0x00, 0x01]` to characteristic `12340006` → CH0 should click ON
- [ ] Send `[0x00, 0x00]` → CH0 should click OFF
- [ ] Press physical buttons for CH2 and CH3 — relays should toggle
- [ ] Verify serial output logs each relay state change

### 8.5 OLED Display Test

- [ ] Confirm each of the 4 OLEDs shows its channel label (CH0–CH3) and power reading
- [ ] Displays should update every 10 seconds with new sensor data
- [ ] If OLEDs are blank, check I2C wiring (SDA=GPIO 3, SCL=GPIO 9) and TCA9548A address (`0x70`)

### 8.6 E-ink Display Test

- [ ] The e-ink screen should show "SMART BREAKER" title, total power, and per-channel readings
- [ ] Refreshes every 60 seconds
- [ ] Status bar at bottom shows WiFi and BLE connection status (W:C / B:C)

### 8.7 Backend Data POST

- [ ] Start the backend server on your machine (`python -m uvicorn backend.main:app --reload --port 8000`)
- [ ] Update the server URL in NVS if your machine IP differs from `192.168.1.100` (see section 9)
- [ ] Confirm serial output shows HTTP POST success every 10 seconds
- [ ] Check the backend logs for incoming sensor data at `/api/sensor`

---

## 9. Backend Connection

### Server URL

Default: `http://192.168.1.100:8000`

The URL is stored in NVS (namespace `"http"`, key `"url"`). To change it, modify the default in `src/config.h`:

```c
#define DEFAULT_SERVER_URL "http://YOUR_IP:8000"
```

Then rebuild and flash. The new URL will be saved to NVS on first boot.

### POST Endpoint

**URL:** `POST /api/sensor`

**Interval:** Every 10 seconds (when WiFi is connected).

**JSON payload:**

```json
{
  "device_id": "EnergyAI-1A2B",
  "channels": [
    {"channel_id": 0, "current_amps": "1.23"},
    {"channel_id": 1, "current_amps": "2.45"},
    {"channel_id": 2, "current_amps": "0.56"},
    {"channel_id": 3, "current_amps": "0.00"}
  ]
}
```

- `device_id` matches the BLE advertising name.
- `current_amps` is a string (not a float) — the backend parses it.
- POST timeout: 5 seconds.

---

## 10. FreeRTOS Task Architecture

For debugging, it helps to know what runs where:

| Task | Interval | Core | Priority | What It Does |
|------|----------|------|----------|--------------|
| sensorTask | 10 s | 1 | 2 | Read CT clamps → update OLEDs → HTTP POST |
| einkTask | 60 s | 1 | 1 | Refresh e-ink overview display |
| loop() | 10 ms | 0 | — | Poll buttons for debounce |
| NimBLE | auto | 0 | system | BLE advertising + GATT callbacks |

Shared data (`g_amps[]`, `g_watts[]`, `g_totalWatts`) is protected by a FreeRTOS mutex (`dataMutex`).

---

## Quick Reference Card

```
Flash:    cd firmware && pio run -t upload
Monitor:  pio device monitor (115200 baud)
BLE name: EnergyAI-XXYY (last 2 MAC bytes)
Service:  12340001-1234-5678-9ABC-FEDCBA987654
WiFi:     write SSID to 0002, password to 0003, read status from 0004
Relays:   write [channel, state] to 0006, read bitmap from 0005
Backend:  POST /api/sensor every 10s to DEFAULT_SERVER_URL
```
