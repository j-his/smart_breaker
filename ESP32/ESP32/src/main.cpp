#include <Arduino.h>         // Include the core Arduino library to provide basic Arduino functionality
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "EPD.h"             // Include the EPD library for controlling the electronic ink screen (E-Paper Display)
#undef WHITE
#undef BLACK
#define WHITE 0xFF
#define BLACK 0x00
#include "pic_home.h"        // Include the header file containing image data
// #include "img/device_interface2.h" // Include the header file containing additional image data

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET    -1
#define TCAADDR       0x70

Adafruit_SSD1306 displays[4] = {
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET),
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET),
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET),
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET)
};

void tcaSelect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(TCAADDR);
  Wire.write(1 << i);
  Wire.endTransmission();
}

// --------- Pin Configuration ----------
const int ctPins[4] = {8, 14, 16, 18};
const int buttonPins[4] = {1, 2, 4, 6};
const int relayPins[4] = {15, 17, 19, 21};

// --------- Button & Relay State ----------
volatile bool relayState[4] = {false, false, false, false};
int buttonState[4] = {HIGH, HIGH, HIGH, HIGH};
int lastButtonReading[4] = {HIGH, HIGH, HIGH, HIGH};
unsigned long lastDebounceTime[4] = {0, 0, 0, 0};
unsigned long debounceDelay = 50;

volatile bool needEpdUpdate = false;

// 4 blocks distributed horizontally across the 792 pixel width
// 792 / 4 = 198 pixels per block. 
// Center of each block for a 70px square is: (198 - 70) / 2 = 64
const int relayX[4] = {64, 262, 460, 658};
const int relayY[4] = {101, 101, 101, 101};

// --------- CT Parameters ----------
const float BURDEN = 100.0;     // ohms
const float TURNS  = 2000.0;    // CT ratio
const float ADC_REF = 3.3;      
const int   ADC_MAX = 4095;     

uint8_t ImageBW[27200];      // Declare an array of 27200 bytes to store black and white image data

uint8_t ImageTest[27200];
void clear_all();

uint8_t square[4900];
uint8_t square2[4900];

void display_image(uint8_t *image, int x, int y, int w, int h);
void draw_image_to_buffer(uint8_t *image, int x, int y, int w, int h);
void update_screen();

void buttonTask(void *pvParameters) {
  for(;;) {
    for (int i = 0; i < 4; i++) {
      int reading = digitalRead(buttonPins[i]);
      
      if (reading != lastButtonReading[i]) {
        lastDebounceTime[i] = millis();
      }
      
      if ((millis() - lastDebounceTime[i]) > debounceDelay) {
        if (reading != buttonState[i]) {
          buttonState[i] = reading;
          
          if (buttonState[i] == LOW) {
            relayState[i] = !relayState[i];
            digitalWrite(relayPins[i], relayState[i] ? HIGH : LOW);
            needEpdUpdate = true;
          }
        }
      }
      lastButtonReading[i] = reading;
    }
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin(3, 9); // Initialize I2C with SDA=3, SCL=9 for the TCA9548A multiplexer

  analogReadResolution(12);   // 12-bit resolution

  for (int i = 0; i < 4; i++) {
    analogSetPinAttenuation(ctPins[i], ADC_11db);
  }

  for (uint8_t t=0; t<4; t++) {
    tcaSelect(t);
    // Address 0x3C for most 128x32 OLEDs
    if(!displays[t].begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
      Serial.print("SSD1306 allocation failed for screen ");
      Serial.println(t);
    } else {
      displays[t].clearDisplay();
      displays[t].setTextColor(SSD1306_WHITE);
      displays[t].setTextSize(2);
      displays[t].setCursor(0, 0);
      displays[t].print("Screen ");
      displays[t].println(t + 1);
      displays[t].display();
    }
  }

  for(int i = 0; i < 4900; i++) {
    square[i] = 0x00; // 0x00 is BLACK
    square2[i] = 0xFF;
  }
  // Initialization settings, executed once when the program starts
  pinMode(7, OUTPUT);        // Set pin 7 to output mode
  digitalWrite(7, HIGH);     // Set pin 7 to high level to activate the screen power

  for (int i = 0; i < 4; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    pinMode(relayPins[i], OUTPUT);
    digitalWrite(relayPins[i], LOW);
  }

  EPD_GPIOInit();            // Initialize the GPIO pin configuration for the EPD electronic ink screen
  Paint_NewImage(ImageBW, EPD_W, EPD_H, Rotation, WHITE); // Create a new image buffer with dimensions EPD_W x EPD_H and a white background
  Paint_Clear(WHITE);        // Clear the image buffer and fill it with white

  /************************ Fast refresh screen operation in partial refresh mode ************************/
  EPD_FastMode1Init();       // Initialize the EPD screen's fast mode 1
  EPD_Display_Clear();       // Clear the screen content
  EPD_Update();              // Update the screen display

  // Initial draw
  for (int i = 0; i < 4; i++) {
    if (relayState[i]) {
      draw_image_to_buffer(square, relayX[i], relayY[i], 70, 70);
    } else {
      draw_image_to_buffer(square2, relayX[i], relayY[i], 70, 70);
    }
  }
  update_screen();

  xTaskCreatePinnedToCore(
    buttonTask,
    "ButtonTask",
    2048,
    NULL,
    1,
    NULL,
    0
  );
}


void loop() {
  // Main loop function
  if (needEpdUpdate) {
    needEpdUpdate = false;
    for (int i = 0; i < 4; i++) {
      if (relayState[i]) {
        draw_image_to_buffer(square, relayX[i], relayY[i], 70, 70);
      } else {
        draw_image_to_buffer(square2, relayX[i], relayY[i], 70, 70);
      }
    }
    update_screen();
  }

  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 1000) {
    lastUpdate = millis();

    const int samples = 2000;
    double sum[4] = {0,0,0,0};

    for (int i = 0; i < samples; i++) {
      for (int ch = 0; ch < 4; ch++) {
        int raw = analogRead(ctPins[ch]);

        // Center around midpoint (1.65V ≈ 2048 ADC counts)
        double voltage = (raw - (ADC_MAX / 2.0)) * (ADC_REF / ADC_MAX);

        sum[ch] += voltage * voltage;
      }
    }

    double Irms[4];
    for (int ch = 0; ch < 4; ch++) {
      double Vrms = sqrt(sum[ch] / samples);

      // Convert voltage to primary current
      Irms[ch] = ((Vrms / BURDEN) * TURNS)-1.75;

      Serial.print("CT");
      Serial.print(ch);
      Serial.print(": ");
      Serial.print(Irms[ch], 3);
      Serial.print(" A   ");
    }
    Serial.println();

    // Update Screens
    for (uint8_t t = 0; t < 4; t++) {
      tcaSelect(t);
      displays[t].clearDisplay();
      
      String currentStr = String(Irms[t], 2) + "A";
      
      displays[t].setTextSize(3);
      
      // Calculate text width to center it (approx. 12 pixels per character for size 2)
      int textWidth = currentStr.length() * 12;
      int x = (SCREEN_WIDTH - textWidth) / 2;
      
      // Center vertically as well (height is approx 16 pixels for size 2, on a 32px high screen)
      int y = (SCREEN_HEIGHT - 16) / 2;
      
      displays[t].setCursor(x, y);
      displays[t].print(currentStr);

      // Display the small screen/breaker number in the bottom left corner
      displays[t].setTextSize(1);
      displays[t].setCursor(0, SCREEN_HEIGHT - 8); // Size 1 text is 8 pixels high
      displays[t].print(t + 1);

      displays[t].display();
    }
  }
}

void clear_all() {
  // Function to clear the screen content
  EPD_FastMode1Init();       // Initialize the EPD screen's fast mode 1
  EPD_Display_Clear();       // Clear the screen content
  EPD_Update();              // Update the screen display
}

void display_image(uint8_t *image, int x, int y, int w, int h) {
    uint8_t * temp = (uint8_t *)malloc(w * h * sizeof(uint8_t));
    
    // Use && to ensure the entire sprite is within BOTH width and height bounds
    if(x + w <= 792 && y + h <= 272) {
           
      EPD_GPIOInit();            // Reinitialize the GPIO pin configuration for the EPD electronic ink screen
      EPD_FastMode1Init();
      
      // Corrected loop to iterate correctly over x/y coordinates and array indices
      for(int j = 0; j < h; j++) {
        for(int i = 0; i < w; i++) {
          // Draw at coordinate (x+i, y+j) reading from standard row-major 1D array
          Paint_SetPixel(x + i, y + j, image[j * w + i]);
        }
      }
      
      EPD_Display(ImageBW);      // Display the image stored in the ImageBW array
      
      //EPD_FastUpdate();          // Perform a fast update to refresh the screen
      EPD_DeepSleep();           // Set the screen to deep sleep mode to save power
    }
    
    free(temp); // Free the dynamically allocated memory
}

void draw_image_to_buffer(uint8_t *image, int x, int y, int w, int h) {
    if(x + w <= 792 && y + h <= 272) {
      for(int j = 0; j < h; j++) {
        for(int i = 0; i < w; i++) {
          Paint_SetPixel(x + i, y + j, image[j * w + i]);
        }
      }
    }
}

void update_screen() {
    EPD_HW_RESET();
    EPD_Display(ImageBW);      // Display the image stored in the ImageBW array
    EPD_PartUpdate();          // Update part of the screen to show the new content
    EPD_DeepSleep();
}