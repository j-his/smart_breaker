//
// EnergyAI Smart Breaker — ESP32-S3 Main Firmware
//
// FreeRTOS Task Architecture:
//   sensorTask (10s): CT clamp read → OLED update → HTTP POST
//   einkTask (60s):   E-ink overview refresh
//   loop() (10ms):    Button debounce polling
//   NimBLE:           Runs on its own thread automatically
//

#include <Arduino.h>
#include "config.h"
#include "ble_service.h"
#include "wifi_manager.h"
#include "ct_reader.h"
#include "relay_ctrl.h"
#include "button_handler.h"
#include "oled_display.h"
#include "eink_display.h"
#include "http_poster.h"

// Shared sensor data (written by sensorTask, read by einkTask)
static float g_amps[NUM_CHANNELS] = {0};
static float g_watts[NUM_CHANNELS] = {0};
static float g_totalWatts = 0;
static SemaphoreHandle_t dataMutex;

// --- FreeRTOS Tasks ---

void sensorTask(void* param) {
    TickType_t lastWake = xTaskGetTickCount();

    for (;;) {
        float amps[NUM_CHANNELS];
        float watts[NUM_CHANNELS];

        // 1. Read CT clamps
        ct_read_all(amps, watts);

        float total = 0;
        for (int i = 0; i < NUM_CHANNELS; i++) {
            total += watts[i];
        }

        // 2. Update shared data
        if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(100))) {
            memcpy(g_amps, amps, sizeof(amps));
            memcpy(g_watts, watts, sizeof(watts));
            g_totalWatts = total;
            xSemaphoreGive(dataMutex);
        }

        // 3. Update OLEDs
        bool relayStates[NUM_CHANNELS];
        for (int i = 0; i < NUM_CHANNELS; i++) {
            relayStates[i] = relay_get(i);
        }
        oled_update_all(watts, relayStates);

        // 4. POST to backend if WiFi available
        if (wifi_is_connected()) {
            http_post_sensor(amps, NUM_CHANNELS);
        }

        Serial.printf("[Sensor] Total: %.1fW  [%.1f, %.1f, %.1f, %.1f]\n",
                      total, watts[0], watts[1], watts[2], watts[3]);

        vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(SENSOR_TASK_INTERVAL_MS));
    }
}

void einkTask(void* param) {
    // Initial delay to let first sensor reading complete
    vTaskDelay(pdMS_TO_TICKS(15000));

    for (;;) {
        float watts[NUM_CHANNELS];
        float total;

        if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(100))) {
            memcpy(watts, g_watts, sizeof(watts));
            total = g_totalWatts;
            xSemaphoreGive(dataMutex);
        } else {
            total = 0;
            memset(watts, 0, sizeof(watts));
        }

        eink_update_overview(total, watts,
                             wifi_is_connected(),
                             ble_is_connected());

        vTaskDelay(pdMS_TO_TICKS(EINK_TASK_INTERVAL_MS));
    }
}

// --- Arduino Entry Points ---

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("========================================");
    Serial.println("  EnergyAI Smart Breaker - ESP32-S3");
    Serial.println("========================================");

    dataMutex = xSemaphoreCreateMutex();

    // Initialize all subsystems
    Serial.println("[Init] Relay control...");
    relay_init();

    Serial.println("[Init] CT clamp ADC...");
    ct_init();

    Serial.println("[Init] Button handlers...");
    buttons_init();

    Serial.println("[Init] OLED displays...");
    oled_init();

    Serial.println("[Init] E-ink display...");
    eink_init();

    Serial.println("[Init] BLE service...");
    ble_init();

    Serial.println("[Init] WiFi manager...");
    wifi_init();

    Serial.println("[Init] HTTP poster...");
    http_init();

    // Create FreeRTOS tasks
    xTaskCreatePinnedToCore(
        sensorTask, "sensor",
        SENSOR_TASK_STACK, nullptr,
        SENSOR_TASK_PRIORITY, nullptr,
        1  // Run on core 1 (core 0 handles WiFi/BLE)
    );

    xTaskCreatePinnedToCore(
        einkTask, "eink",
        EINK_TASK_STACK, nullptr,
        EINK_TASK_PRIORITY, nullptr,
        1
    );

    Serial.println("[Init] All systems GO");
    Serial.println("========================================");
}

void loop() {
    // Poll buttons at ~10ms intervals
    buttons_poll();
    delay(10);
}
