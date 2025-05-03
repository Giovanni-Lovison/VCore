#include <Arduino.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_SSD1306.h>

#define I2C_SDA 21
#define I2C_SCL 22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1
#define BULK_BUFFER_SIZE 64
#define JSON_CAPACITY 256

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

struct DeviceInfo {
    uint8_t addr7;
    String name;
};

struct KnownDevice {
    uint8_t addr;
    const char* name;
};

DeviceInfo devices[16];
uint8_t num_devices = 0;
uint8_t current_device_idx = 0;
uint32_t start_runtime;
bool is_paused = true;
uint32_t reads_counter = 0;
uint32_t last_stats_update = 0;
uint16_t reads_per_second = 0;

String get_device_name(uint8_t addr7) {
    static const KnownDevice KNOWN_DEVICES[] = {
        {0x24, "uP9512"},  // 8-bit: 0x48 >> 1
        {0x25, "uP9512"},  // 8-bit: 0x4A >> 1
        {0x26, "uP9512"},  // 8-bit: 0x4C >> 1
        {0x27, "uP9512"},  // 8-bit: 0x4E >> 1
        {0x20, "uP9512"},  // 8-bit: 0x40 >> 1
        {0x3C, "SSD1306"}  // 8-bit: 0x78 >> 1
    };
    
    for(const auto& dev : KNOWN_DEVICES) {
        if(addr7 == dev.addr) return String(dev.name);
    }
    return "Unknown";
}

void update_display_stats() {
    static uint32_t last_update = 0;
    if(millis() - last_update < 200) return;
    last_update = millis();
    
    display.clearDisplay();
    display.setTextSize(1);
    
    uint32_t runtime = (millis() - start_runtime) / 1000;
    
    if(is_paused) {
        // In pausa mostra solo l'uptime grande centrato
        display.setTextSize(2);
        display.setCursor((SCREEN_WIDTH - 64)/2, 12);
        display.printf("%02d:%02d", runtime/60, runtime%60);
    } else if(num_devices > 0) {
        // In monitoring mostra uptime piccolo e stats
        display.setCursor(0,0);
        display.printf("Up: %02d:%02d", runtime/60, runtime%60);
        
        display.setCursor(0,8);
        display.printf("Dev: 0x%02X (%s)", 
                      devices[current_device_idx].addr7,
                      devices[current_device_idx].name.c_str());
        
        display.setCursor(0,16);
        display.printf("Time: %.2fms", reads_counter / 1000.0f);
        
        display.setCursor(0,24);
        display.printf("I/O: %d/s", reads_per_second);
    }
    
    display.display();
}

void scan_i2c_devices() {
    num_devices = 0;
    for(uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if(Wire.endTransmission() == 0) {
            if(num_devices < 16) {
                devices[num_devices] = {addr, get_device_name(addr)};
                num_devices++;
            }
        }
    }
}

void handle_bulk_rw(JsonDocument& cmd, JsonDocument& res) {
    if(is_paused) {
        res["status"] = "PAUSED";
        return;
    }
    
    uint8_t addr7 = devices[current_device_idx].addr7;
    uint32_t start_time = micros();
    
    // Process reads
    if(cmd.containsKey("reads")) {
        JsonArray reads = cmd["reads"];
        size_t count = min(reads.size(), (size_t)BULK_BUFFER_SIZE);
        uint8_t buffer[BULK_BUFFER_SIZE];
        
        // Read each register individually for better reliability
        for(size_t i = 0; i < count; i++) {
            Wire.beginTransmission(addr7);
            Wire.write(reads[i].as<uint8_t>());
            Wire.endTransmission(false);
            
            if(Wire.requestFrom(addr7, (uint8_t)1) == 1) {
                buffer[i] = Wire.read();
            }
        }
        
        JsonArray values = res.createNestedArray("values");
        for(size_t i = 0; i < count; i++) {
            values.add(buffer[i]);
        }
        reads_counter = micros() - start_time;
    }
    
    // Process writes
    if(cmd.containsKey("writes")) {
        JsonArray writes = cmd["writes"];
        Wire.beginTransmission(addr7);
        for(JsonVariant v : writes) {
            Wire.write(v["reg"].as<uint8_t>());
            Wire.write(v["value"].as<uint8_t>());
        }
        uint8_t err = Wire.endTransmission();
        res["write_status"] = err;
    }
    
    // Update statistics - modificare questa parte
    uint32_t now = millis();
    if(now - last_stats_update >= 1000) {
        // Count both reads and writes
        uint32_t total_ops = 0;
        if(cmd.containsKey("reads")) total_ops += cmd["reads"].size();
        if(cmd.containsKey("writes")) total_ops += cmd["writes"].size();
        
        reads_per_second = total_ops;  // ora conta tutte le operazioni I2C
        last_stats_update = now;
    }
    
    res["status"] = "OK";
    res["timing_us"] = micros() - start_time;
}

void show_scan_results() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0,0);
    display.println("Found devices:");
    
    for(uint8_t i=0; i < min(num_devices, (uint8_t)4); i++) {
        display.printf("0x%02X: %s\n", 
            devices[i].addr7,
            devices[i].name.c_str());
    }
    display.display();
    delay(3000);  // Show for 3 seconds
}

void process_command(const char* json_str) {
    StaticJsonDocument<JSON_CAPACITY> cmd, res;
    deserializeJson(cmd, json_str);
    
    const char* action = cmd["action"];
    res["action"] = action;
    
    if(strcmp(action, "scan") == 0) {
        scan_i2c_devices();
        JsonArray arr = res.createNestedArray("devices");
        JsonArray names = res.createNestedArray("names");
        for(uint8_t i=0; i<num_devices; i++) {
            arr.add(devices[i].addr7);
            names.add(devices[i].name);
        }
        show_scan_results();  // Show results on OLED
    }
    else if(strcmp(action, "get_devices") == 0) {
        JsonArray arr = res.createNestedArray("devices");
        JsonArray names = res.createNestedArray("names");
        for(uint8_t i=0; i<num_devices; i++) {
            arr.add(devices[i].addr7);
            names.add(devices[i].name);
        }
    }
    else if(strcmp(action, "select") == 0) {
        uint8_t target = cmd["addr"];
        for(uint8_t i=0; i<num_devices; i++) {
            if(devices[i].addr7 == target) {
                current_device_idx = i;
                break;
            }
        }
        res["selected"] = devices[current_device_idx].addr7;
    }
    else if(strcmp(action, "bulk_rw") == 0) handle_bulk_rw(cmd, res);
    else if(strcmp(action, "pause") == 0) is_paused = true;
    else if(strcmp(action, "resume") == 0) is_paused = false;
    else if(strcmp(action, "switch") == 0) {
        current_device_idx = (current_device_idx + 1) % num_devices;
        res["selected"] = devices[current_device_idx].addr7;
    }
    else if(strcmp(action, "get_status") == 0) {
        res["is_paused"] = is_paused;
        res["current_device"] = devices[current_device_idx].addr7;
        res["reads_per_second"] = reads_per_second;
        res["uptime"] = (millis() - start_runtime) / 1000;
    }
    
    serializeJson(res, Serial);
    Serial.println();
}

void setup() {
    Serial.begin(115200);
    Wire.begin(I2C_SDA, I2C_SCL, 400000);  // 400kHz
    display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
    display.setTextColor(SSD1306_WHITE);
    
    scan_i2c_devices();
    start_runtime = millis();
}

void loop() {
    static String buffer;
    while(Serial.available()) {
        char c = Serial.read();
        if(c == '\n') {
            process_command(buffer.c_str());
            buffer = "";
        } else {
            buffer += c;
        }
    }
    
    update_display_stats();
}