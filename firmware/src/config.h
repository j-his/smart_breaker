#pragma once

// ============================================================
// EnergyAI Smart Breaker — ESP32-S3 Configuration
// ============================================================

// --- Device Identity ---
#define DEVICE_NAME_PREFIX "EnergyAI"
#define NUM_CHANNELS 4

// --- CT Clamp ADC Pins (SCT-013-000) ---
#define CT_PIN_CH0 8
#define CT_PIN_CH1 14
#define CT_PIN_CH2 16
#define CT_PIN_CH3 18

static const int CT_PINS[NUM_CHANNELS] = {CT_PIN_CH0, CT_PIN_CH1, CT_PIN_CH2, CT_PIN_CH3};

// --- CT Clamp Calibration ---
#define ADC_RESOLUTION   4095.0f
#define ADC_VREF         3.3f
#define CT_MIDPOINT_V    1.65f
#define CT_BURDEN_R      33.0f     // Burden resistor in ohms
#define CT_TURNS_RATIO   2000.0f   // SCT-013-000 turns ratio
#define MAINS_VOLTAGE    120.0f    // North America
#define CT_SAMPLES       1000      // ~1 AC cycle at 60Hz

// --- Relay GPIOs (Active HIGH) ---
#define RELAY_PIN_CH0 21
#define RELAY_PIN_CH1 17
#define RELAY_PIN_CH2 19
#define RELAY_PIN_CH3 15

static const int RELAY_PINS[NUM_CHANNELS] = {RELAY_PIN_CH0, RELAY_PIN_CH1, RELAY_PIN_CH2, RELAY_PIN_CH3};

// --- Buttons via PCF8574 I2C GPIO Expander ---
// All 4 buttons are read over I2C instead of direct GPIO.
// Buttons wired to P0-P3 on PCF8574 (active LOW, internal pull-up).
#define PCF8574_ADDR 0x20
#define BUTTON_DEBOUNCE_MS 50

// --- I2C (TCA9548A Mux for OLEDs) ---
#define I2C_SDA 3
#define I2C_SCL 9
#define TCA9548A_ADDR 0x70

// --- OLED Displays (SSD1306 128x32) ---
#define OLED_WIDTH  128
#define OLED_HEIGHT 32
#define OLED_ADDR   0x3C

// --- E-ink Display (SPI, bit-banged) ---
#define EINK_MOSI  12
#define EINK_CLK   11
#define EINK_CS    47
#define EINK_DC    46
#define EINK_RST   45
#define EINK_BUSY  48
#define EINK_POWER 7

// --- BLE Service UUIDs ---
#define SERVICE_UUID          "12340001-1234-5678-9ABC-FEDCBA987654"
#define WIFI_SSID_CHAR_UUID   "12340002-1234-5678-9ABC-FEDCBA987654"
#define WIFI_PASS_CHAR_UUID   "12340003-1234-5678-9ABC-FEDCBA987654"
#define WIFI_STATUS_CHAR_UUID "12340004-1234-5678-9ABC-FEDCBA987654"
#define BREAKER_STATE_UUID    "12340005-1234-5678-9ABC-FEDCBA987654"
#define BREAKER_CMD_UUID      "12340006-1234-5678-9ABC-FEDCBA987654"

// --- WiFi ---
#define WIFI_CONNECT_TIMEOUT_MS 15000
#define WIFI_RECONNECT_DELAY_MS 5000

// --- HTTP Backend ---
#define DEFAULT_SERVER_URL "http://192.168.1.100:8000"
#define HTTP_POST_INTERVAL_MS 10000
#define HTTP_TIMEOUT_MS 5000

// --- Task Intervals ---
#define SENSOR_TASK_INTERVAL_MS 10000
#define EINK_TASK_INTERVAL_MS   60000

// --- FreeRTOS ---
#define SENSOR_TASK_STACK 4096
#define EINK_TASK_STACK   4096
#define SENSOR_TASK_PRIORITY 2
#define EINK_TASK_PRIORITY   1
