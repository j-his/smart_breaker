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

uint8_t ImageBW[27200];      // Declare an array of 27200 bytes to store black and white image data

uint8_t ImageTest[27200];
void clear_all();

uint8_t square[4900];
uint8_t square2[4900];

void display_image(uint8_t *image, int x, int y, int w, int h);
void draw_image_to_buffer(uint8_t *image, int x, int y, int w, int h);
void update_screen();

void setup() {
  Serial.begin(115200);
  Wire.begin(3, 9); // Initialize I2C with SDA=3, SCL=9 for the TCA9548A multiplexer

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

  pinMode(21, OUTPUT);
  pinMode(17, OUTPUT);
  pinMode(19, OUTPUT);
  pinMode(15, OUTPUT);

  EPD_GPIOInit();            // Initialize the GPIO pin configuration for the EPD electronic ink screen
  Paint_NewImage(ImageBW, EPD_W, EPD_H, Rotation, WHITE); // Create a new image buffer with dimensions EPD_W x EPD_H and a white background
  Paint_Clear(WHITE);        // Clear the image buffer and fill it with white

  /************************ Fast refresh screen operation in partial refresh mode ************************/
  EPD_FastMode1Init();       // Initialize the EPD screen's fast mode 1
  EPD_Display_Clear();       // Clear the screen content
  EPD_Update();              // Update the screen display

  // display_image(gImage_device_interface2, 0, 0, 792, 272);
  delay(1000);
  
  // Center coordinates for a 70x70 square on a 792x272 screen
  // x = (792 - 70) / 2 = 361
  // y = (272 - 70) / 2 = 101
  draw_image_to_buffer(square, 361, 101, 70, 70);
  update_screen();
  delay(1000);
  
  // Add more black squares around the center
  draw_image_to_buffer(square, 261, 101, 70, 70); // Left square
  update_screen();
  digitalWrite(21, HIGH);
  delay(1000);
  digitalWrite(21, LOW);

  draw_image_to_buffer(square, 461, 101, 70, 70); // Right square
  update_screen();
  digitalWrite(17, HIGH);
  delay(1000);
  digitalWrite(17, LOW);

  draw_image_to_buffer(square, 361, 21,  70, 70); // Top square
  update_screen();
  digitalWrite(19, HIGH);
  delay(1000);
  digitalWrite(19, LOW);

  draw_image_to_buffer(square, 361, 181, 70, 70); // Bottom square
  update_screen();
  digitalWrite(15, HIGH);
  delay(1000);
  digitalWrite(15, LOW);
  
  delay(5000);               // Wait for 5000 milliseconds (5 seconds)

  clear_all();               // Call the clear_all function to clear the screen content
}


void loop() {
  // Main loop function
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 1000) {
    lastUpdate = millis();

    // Screen 1: Displays text and a counter
    tcaSelect(0);
    displays[0].clearDisplay();
    displays[0].setTextSize(1);
    displays[0].setCursor(0,0);
    displays[0].println("Breaker 1: Normal");
    displays[0].print("Uptime: ");
    displays[0].print(millis() / 1000);
    displays[0].println("s");
    displays[0].display();

    // Screen 2: Displays a line
    tcaSelect(1);
    displays[1].clearDisplay();
    displays[1].setTextSize(1);
    displays[1].setCursor(0,0);
    displays[1].println("Breaker 2: Alert");
    displays[1].drawLine(0, 16, 127, 31, SSD1306_WHITE);
    displays[1].display();

    // Screen 3: Displays a rectangle
    tcaSelect(2);
    displays[2].clearDisplay();
    displays[2].setTextSize(1);
    displays[2].setCursor(0,0);
    displays[2].println("Breaker 3: Off");
    displays[2].drawRect(10, 10, 100, 20, SSD1306_WHITE);
    displays[2].display();

    // Screen 4: Displays a circle
    tcaSelect(3);
    displays[3].clearDisplay();
    displays[3].setTextSize(1);
    displays[3].setCursor(0,0);
    displays[3].println("Breaker 4: On");
    displays[3].drawCircle(64, 16, 15, SSD1306_WHITE);
    displays[3].display();
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