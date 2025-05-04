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
uint32_t start_runtime = 0;  // Inizializzato a 0
bool is_paused = true;
uint32_t reads_counter = 0;
uint32_t last_stats_update = 0;
uint16_t reads_per_second = 0;
uint32_t total_ops = 0;      // Add this after other global variables
uint32_t ops_last_second = 0;
uint32_t total_time_us = 0;
uint32_t avg_access_time_us = 0;

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
    
    uint32_t current_time = millis() - start_runtime;
    
    if(is_paused) {
        // In pausa mostra il tempo dettagliato
        uint32_t hours = current_time / 3600000;
        uint32_t minutes = (current_time % 3600000) / 60000;
        uint32_t seconds = (current_time % 60000) / 1000;

        display.setTextSize(2);  // Dimensione testo più grande
        display.setCursor((SCREEN_WIDTH - 96)/2, 10);  // Meglio centrato verticalmente
        display.printf("%02d:%02d:%02d", hours, minutes, seconds);
        
    } else if(num_devices > 0) {
        // In monitoring mostra uptime normale e stats
        uint32_t runtime = current_time / 1000;
        display.setCursor(0,0);
        display.printf("Up: %02d:%02d", runtime/60, runtime%60);
        
        display.setCursor(0,8);
        display.printf("Dev: (%s)", devices[current_device_idx].name.c_str());
        
        display.setCursor(0,16);
        display.printf("t/op: %luus", avg_access_time_us);
        
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
    uint32_t start_time = micros();
    
    if(is_paused) {
        res["status"] = "PAUSED";
        res["error"] = "Device monitoring is paused";
        return;
    }
    
    uint8_t addr7 = devices[current_device_idx].addr7;
    bool success = true;
    uint32_t op_count = 0;  // Count operations in this call
    
    // Process reads
    if(cmd.containsKey("reads")) {
        JsonArray reads = cmd["reads"];
        size_t count = min(reads.size(), (size_t)BULK_BUFFER_SIZE);
        op_count += count;  // Add reads to operation count
        uint8_t buffer[BULK_BUFFER_SIZE];
        
        for(size_t i = 0; i < count && success; i++) {
            uint8_t reg = reads[i].as<uint8_t>();
            
            // Complete transaction for each register
            Wire.beginTransmission(addr7);
            Wire.write(reg);
            if(Wire.endTransmission(true) != 0) {
                success = false;
                break;
            }
            
            // Read single byte
            if(Wire.requestFrom(addr7, (uint8_t)1) != 1) {
                success = false;
                break;
            }
            
            buffer[i] = Wire.read();
        }
        
        if(success) {
            JsonArray values = res.createNestedArray("values");
            for(size_t i = 0; i < count; i++) {
                values.add(buffer[i]);
            }
            res["status"] = "OK";
        } else {
            res["status"] = "ERROR";
            res["error"] = "Read failed";
        }
    }
    
    // Process writes
    if(cmd.containsKey("writes")) {
        JsonArray writes = cmd["writes"];
        op_count += writes.size();  // Add writes to operation count
        Wire.beginTransmission(addr7);
        for(JsonVariant v : writes) {
            Wire.write(v["reg"].as<uint8_t>());
            Wire.write(v["value"].as<uint8_t>());
        }
        uint8_t err = Wire.endTransmission();
        res["write_status"] = err;
    }
    
    // Update statistics
    uint32_t elapsed = micros() - start_time;
    total_time_us += elapsed;
    total_ops += op_count;
    
    uint32_t now = millis();
    if(now - last_stats_update >= 1000) {
        reads_per_second = (total_ops - ops_last_second);
        ops_last_second = total_ops;
        avg_access_time_us = (total_ops > 0) ? (total_time_us / total_ops) : 0;
        last_stats_update = now;
    }
    
    res["status"] = "OK";
    res["timing_us"] = elapsed;
    res["op_count"] = op_count;
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
        bool found = false;
        for(uint8_t i=0; i<num_devices; i++) {
            if(devices[i].addr7 == target) {
                current_device_idx = i;
                found = true;
                res["selected"] = devices[current_device_idx].addr7;
                res["name"] = devices[current_device_idx].name;
                res["status"] = "OK";
                break;
            }
        }
        if (!found) {
            res["status"] = "ERROR";
            res["error"] = "Device not found";
        }
    }
    else if(strcmp(action, "bulk_rw") == 0) handle_bulk_rw(cmd, res);
    else if(strcmp(action, "pause") == 0) {
        is_paused = true;
        res["status"] = "OK";
    }
    else if(strcmp(action, "resume") == 0) {
        is_paused = false;
        res["status"] = "OK";
    }
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
    
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0,0);
    display.println("Ready...");
    display.display();
    
    scan_i2c_devices();
    is_paused = true;  // Sempre in pausa all'avvio
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
