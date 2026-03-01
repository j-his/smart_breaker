#include "eink_display.h"
#include "config.h"
#include <Arduino.h>

// GDEY0213B74 e-ink display via bit-banged SPI
// Resolution: 250x122

#define EINK_WIDTH  250
#define EINK_HEIGHT 122

// Framebuffer (1 bit per pixel, packed in bytes)
static uint8_t framebuffer[(EINK_WIDTH * EINK_HEIGHT + 7) / 8];

// --- Low-level SPI bit-bang ---

static void spi_write_byte(uint8_t data) {
    for (int i = 7; i >= 0; i--) {
        digitalWrite(EINK_MOSI, (data >> i) & 1);
        digitalWrite(EINK_CLK, HIGH);
        digitalWrite(EINK_CLK, LOW);
    }
}

static void eink_send_cmd(uint8_t cmd) {
    digitalWrite(EINK_DC, LOW);
    digitalWrite(EINK_CS, LOW);
    spi_write_byte(cmd);
    digitalWrite(EINK_CS, HIGH);
}

static void eink_send_data(uint8_t data) {
    digitalWrite(EINK_DC, HIGH);
    digitalWrite(EINK_CS, LOW);
    spi_write_byte(data);
    digitalWrite(EINK_CS, HIGH);
}

static void eink_wait_busy() {
    unsigned long start = millis();
    while (digitalRead(EINK_BUSY) == HIGH) {
        delay(10);
        if (millis() - start > 10000) {
            Serial.println("[E-ink] Busy timeout");
            break;
        }
    }
}

static void eink_power_on() {
    digitalWrite(EINK_POWER, HIGH);
    delay(100);
}

static void eink_power_off() {
    // Send deep sleep command before cutting power
    eink_send_cmd(0x10); // Enter deep sleep
    eink_send_data(0x01);
    delay(100);
    digitalWrite(EINK_POWER, LOW);
}

// --- Framebuffer operations ---

static void fb_clear() {
    memset(framebuffer, 0xFF, sizeof(framebuffer)); // White
}

static void fb_set_pixel(int x, int y, bool black) {
    if (x < 0 || x >= EINK_WIDTH || y < 0 || y >= EINK_HEIGHT) return;
    int idx = (y * EINK_WIDTH + x) / 8;
    int bit = 7 - (x % 8);
    if (black) {
        framebuffer[idx] &= ~(1 << bit);
    } else {
        framebuffer[idx] |= (1 << bit);
    }
}

// Simple 5x7 font rendering for digits and basic chars
static const uint8_t FONT_5X7[][5] = {
    {0x3E,0x51,0x49,0x45,0x3E}, // 0
    {0x00,0x42,0x7F,0x40,0x00}, // 1
    {0x42,0x61,0x51,0x49,0x46}, // 2
    {0x21,0x41,0x45,0x4B,0x31}, // 3
    {0x18,0x14,0x12,0x7F,0x10}, // 4
    {0x27,0x45,0x45,0x45,0x39}, // 5
    {0x3C,0x4A,0x49,0x49,0x30}, // 6
    {0x01,0x71,0x09,0x05,0x03}, // 7
    {0x36,0x49,0x49,0x49,0x36}, // 8
    {0x06,0x49,0x49,0x29,0x1E}, // 9
    {0x00,0x36,0x36,0x00,0x00}, // : (10)
    {0x00,0x00,0x00,0x00,0x00}, // space (11)
    {0x7F,0x09,0x09,0x09,0x01}, // F (12) [placeholder for text]
    {0x7E,0x11,0x11,0x11,0x7E}, // A (13)
    {0x00,0x08,0x08,0x08,0x00}, // - (14)
    {0x7F,0x41,0x41,0x22,0x1C}, // D (15)
    {0x60,0x60,0x00,0x00,0x00}, // . (16)
    {0x3E,0x41,0x41,0x41,0x22}, // C (17)
    {0x7F,0x08,0x14,0x22,0x41}, // K (18)
    {0x3E,0x41,0x41,0x51,0x32}, // G (19)
    {0x7F,0x49,0x49,0x49,0x36}, // B (20)
    {0x40,0x40,0x40,0x40,0x40}, // _ (21)
    {0x7F,0x01,0x01,0x01,0x01}, // L (22)
    {0x7F,0x49,0x49,0x49,0x41}, // E (23)
    {0x7F,0x02,0x0C,0x02,0x7F}, // W (24)
    {0x01,0x01,0x7F,0x01,0x01}, // T (25)
    {0x7F,0x08,0x08,0x08,0x7F}, // H (26)
};

static void fb_draw_char(int x, int y, char c, int scale) {
    int idx = -1;
    if (c >= '0' && c <= '9') idx = c - '0';
    else if (c == ':') idx = 10;
    else if (c == ' ') idx = 11;
    else if (c == '.') idx = 16;
    else if (c == '-') idx = 14;
    else if (c == 'W' || c == 'w') idx = 24;
    else if (c == 'k' || c == 'K') idx = 18;
    else if (c == 'C' || c == 'c') idx = 17;
    else if (c == 'H' || c == 'h') idx = 26;
    else if (c == 'T' || c == 't') idx = 25;
    else return;

    if (idx < 0 || idx >= (int)(sizeof(FONT_5X7) / sizeof(FONT_5X7[0]))) return;

    for (int col = 0; col < 5; col++) {
        uint8_t line = FONT_5X7[idx][col];
        for (int row = 0; row < 7; row++) {
            if (line & (1 << row)) {
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        fb_set_pixel(x + col * scale + sx, y + row * scale + sy, true);
                    }
                }
            }
        }
    }
}

static void fb_draw_string(int x, int y, const char* str, int scale) {
    int cx = x;
    while (*str) {
        fb_draw_char(cx, y, *str, scale);
        cx += 6 * scale;
        str++;
    }
}

static void fb_draw_hline(int x, int y, int w) {
    for (int i = 0; i < w; i++) fb_set_pixel(x + i, y, true);
}

// --- Public API ---

void eink_init() {
    pinMode(EINK_MOSI, OUTPUT);
    pinMode(EINK_CLK, OUTPUT);
    pinMode(EINK_CS, OUTPUT);
    pinMode(EINK_DC, OUTPUT);
    pinMode(EINK_RST, OUTPUT);
    pinMode(EINK_BUSY, INPUT);
    pinMode(EINK_POWER, OUTPUT);

    digitalWrite(EINK_CS, HIGH);
    digitalWrite(EINK_CLK, LOW);
    digitalWrite(EINK_POWER, LOW);

    Serial.println("[E-ink] Pins initialized");
}

void eink_update_overview(float totalWatts, float* channelWatts,
                          bool wifiOk, bool bleConnected) {
    eink_power_on();

    // Hardware reset
    digitalWrite(EINK_RST, LOW);
    delay(10);
    digitalWrite(EINK_RST, HIGH);
    delay(10);
    eink_wait_busy();

    // Init sequence (GDEY0213B74)
    eink_send_cmd(0x12); // Software reset
    eink_wait_busy();

    eink_send_cmd(0x01); // Driver output control
    eink_send_data((EINK_HEIGHT - 1) & 0xFF);
    eink_send_data(((EINK_HEIGHT - 1) >> 8) & 0xFF);
    eink_send_data(0x00);

    eink_send_cmd(0x11); // Data entry mode
    eink_send_data(0x03);

    eink_send_cmd(0x44); // Set RAM X address
    eink_send_data(0x00);
    eink_send_data((EINK_WIDTH / 8 - 1) & 0xFF);

    eink_send_cmd(0x45); // Set RAM Y address
    eink_send_data(0x00);
    eink_send_data(0x00);
    eink_send_data((EINK_HEIGHT - 1) & 0xFF);
    eink_send_data(((EINK_HEIGHT - 1) >> 8) & 0xFF);

    // --- Build framebuffer ---
    fb_clear();

    // Title
    fb_draw_string(4, 2, "   SMART BREAKER   ", 1);
    fb_draw_hline(0, 11, EINK_WIDTH);

    // Total power (large)
    char buf[32];
    if (totalWatts >= 1000) {
        snprintf(buf, sizeof(buf), "%.1fkW", totalWatts / 1000.0f);
    } else {
        snprintf(buf, sizeof(buf), "%.0fW", totalWatts);
    }
    fb_draw_string(10, 18, buf, 3);

    fb_draw_hline(0, 44, EINK_WIDTH);

    // Channel readings
    for (int i = 0; i < NUM_CHANNELS; i++) {
        int y = 50 + i * 16;
        snprintf(buf, sizeof(buf), "CH%d:", i);
        fb_draw_string(4, y, buf, 1);

        if (channelWatts[i] >= 1000) {
            snprintf(buf, sizeof(buf), "%.1fkW", channelWatts[i] / 1000.0f);
        } else {
            snprintf(buf, sizeof(buf), "%.0fW", channelWatts[i]);
        }
        fb_draw_string(40, y, buf, 1);
    }

    // Status bar at bottom
    fb_draw_hline(0, 112, EINK_WIDTH);
    snprintf(buf, sizeof(buf), "W:%c  B:%c",
             wifiOk ? 'C' : '-',
             bleConnected ? 'C' : '-');
    fb_draw_string(4, 115, buf, 1);

    // --- Write to display ---
    eink_send_cmd(0x4E); // Set RAM X counter
    eink_send_data(0x00);
    eink_send_cmd(0x4F); // Set RAM Y counter
    eink_send_data(0x00);
    eink_send_data(0x00);

    eink_send_cmd(0x24); // Write RAM
    int totalBytes = (EINK_WIDTH / 8) * EINK_HEIGHT;
    for (int i = 0; i < totalBytes; i++) {
        eink_send_data(framebuffer[i]);
    }

    // Refresh display
    eink_send_cmd(0x22);
    eink_send_data(0xF7);
    eink_send_cmd(0x20);
    eink_wait_busy();

    eink_power_off();
    Serial.println("[E-ink] Display updated");
}
