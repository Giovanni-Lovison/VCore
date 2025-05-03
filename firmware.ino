#include <Arduino.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_GFX.h>

#define I2C_SDA 21
#define I2C_SCL 22
#define MAX_DEVICES 10
#define BULK_BUFFER_SIZE 32
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1

#define V_LSB 0.01f
#define I_LSB 0.01f
#define R_SHUNT 0.003f
#define T_LSB 0.008f
#define T_SENS 0.0127f

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

struct DeviceInfo {
    uint8_t addr7;
    uint8_t addr8;
    String name;
};

DeviceInfo devices[MAX_DEVICES];
uint8_t num_devices = 0;
uint8_t current_device = 0;

String get_device_name(uint8_t addr7) {
    const std::pair<uint8_t, const char*> KNOWN_DEVICES[] = {
        {0x25, "uP9512"}, {0x4C, "uP9512"}, 
        {0x4E, "uP9512"}, {0x40, "uP9512"},
        {0x3C, "OLED"}
    };

    for(auto& dev : KNOWN_DEVICES)
        if(addr7 == dev.first) return dev.second;
    return "Unknown";
}

void scan_i2c() {
    num_devices = 0;
    for(uint8_t addr = 1; addr < 127 && num_devices < MAX_DEVICES; addr++) {
        Wire.beginTransmission(addr);
        if(Wire.endTransmission() == 0) {
            devices[num_devices] = {
                addr,
                static_cast<uint8_t>(addr << 1),
                get_device_name(addr)
            };
            num_devices++;
        }
    }
}

void update_display_operation(const char* op, uint8_t addr, size_t count) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0,0);
    
    display.println("I2C Monitor");
    display.println("-------------");
    display.printf("Dev: 0x%02X\n", addr);
    display.printf("Op: %s\n", op);
    display.printf("Regs: %d\n", count);
    
    display.display();
}

// Add this new function after update_display_operation
void update_display_device(uint8_t addr7, const String& name) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0,0);
    
    display.println("I2C Monitor");
    display.printf("Dev: 0x%02X (%s)\n", addr7, name.c_str());
    display.println("Monitoring...");
    
    display.display();
}

uint8_t readRegister(uint8_t addr7, uint8_t reg) {
    Wire.beginTransmission(addr7);
    Wire.write(reg);
    if(Wire.endTransmission(false) != 0) {
        return 0;
    }
    
    if(Wire.requestFrom(addr7, (uint8_t)1) != 1) {
        return 0;
    }
    
    uint8_t value = Wire.read();
    Wire.endTransmission();
    return value;
}

void handle_bulk_rw(JsonDocument& doc, JsonDocument& resp) {
    uint8_t addr7 = current_device >> 1;
    
    if(doc.containsKey("writes")) {
        JsonArray writes = doc["writes"];
        size_t write_count = min(writes.size(), static_cast<size_t>(BULK_BUFFER_SIZE/2));
        update_display_operation("WRITE", addr7, write_count);
        
        Wire.beginTransmission(current_device);
        for(size_t i=0; i<write_count; i++) {
            Wire.write(writes[i]["reg"]);
            Wire.write(writes[i]["value"]);
        }
        uint8_t error = Wire.endTransmission();
        resp["written"] = (error == 0) ? write_count * 2 : 0;
    }
    
    if(doc.containsKey("reads")) {
        JsonArray reads = doc["reads"];
        size_t read_count = min(reads.size(), static_cast<size_t>(BULK_BUFFER_SIZE));
        update_display_operation("READ", addr7, read_count);
        
        JsonArray values = resp.createNestedArray("values");
        
        for(size_t i=0; i<read_count; i++) {
            uint8_t reg = reads[i];
            uint8_t value = readRegister(addr7, reg);
            values.add(value);
            Serial.printf("Read reg 0x%02X = 0x%02X\n", reg, value);
        }
    }
    resp["status"] = "OK";
}

// Modify handle_serial() to update display on device selection
void handle_serial() {
    if(Serial.available() > 0) {
        String json_str = Serial.readStringUntil('\n');
        StaticJsonDocument<512> doc;
        StaticJsonDocument<512> resp;
        
        if(deserializeJson(doc, json_str)) {
            resp["status"] = "JSON Error";
            serializeJson(resp, Serial);
            Serial.println();
            return;
        }

        const char* action = doc["action"];
        
        if(strcmp(action, "scan") == 0) {
            scan_i2c();
            resp["status"] = "OK";
            JsonArray devArray = resp.createNestedArray("devices");
            for(uint8_t i=0; i<num_devices; i++) {
                JsonObject dev = devArray.createNestedObject();
                dev["addr7"] = devices[i].addr7;
                dev["addr8"] = devices[i].addr8;
                dev["name"] = devices[i].name;
            }
        }
        else if(strcmp(action, "select") == 0) {
            uint8_t addr7 = doc["addr"];
            bool found = false;
            for(uint8_t i=0; i<num_devices; i++) {
                if(devices[i].addr7 == addr7) {
                    current_device = addr7 << 1;  // Store 8-bit address
                    update_display_device(addr7, devices[i].name);
                    Serial.printf("Selected device 0x%02X\n", addr7);
                    found = true;
                    break;
                }
            }
            resp["status"] = found ? "OK" : "Device not found";
        }
        else if(strcmp(action, "bulk_rw") == 0) {
            handle_bulk_rw(doc, resp);
        }

        serializeJson(resp, Serial);
        Serial.println();
    }
}

void setup() {
    Serial.begin(115200);
    Wire.begin(I2C_SDA, I2C_SCL, 400000);
    scan_i2c();
    
    if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        Serial.println("SSD1306 allocation failed");
    }
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.println("Ready");
    display.display();
}

void loop() {
    handle_serial();
    delay(1);
}