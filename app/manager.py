# 08.07.25

import serial
import json
import time 
from queue import Queue, Empty
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, pyqtSlot, QMutex

from app.device import DEVICE_MAP
from app.mock_serial import MockSerial
from app.logger import get_logger


class I2CManager(QObject):
    device_changed = pyqtSignal()
    
    def __init__(self, port=None, developer_mode=False):
        super().__init__()
        try:
            if developer_mode:
                self.ser = MockSerial(port)
            else:
                self.ser = serial.Serial(port, 115200, timeout=1.0, write_timeout=1.0)

        except Exception as e:
            print(f"Serial init error: {e}")
            if developer_mode:
                self.ser = MockSerial(port)
            else:
                raise
        
        # Inizializza il logger
        self.logger = get_logger()
        self.logger.system_log(f"I2CManager initialized with port: {port}, developer_mode: {developer_mode}")
        
        self.response_queue = Queue()
        self.lock = QMutex()
        self.running = [True]
        self.is_paused = True
        
        # Initialize and start the thread pool
        self.threadpool = QThreadPool.globalInstance()
        self.serial_worker = SerialWorker(self.ser, self.response_queue, self.running, self.logger)
        self.threadpool.start(self.serial_worker)
        
        # Initialize devices
        self.devices = []
        self.current_device = None
        self.is_active = False
        self._initialize()
    
    def _initialize(self):
        """Initialize device list with retries"""
        max_retries = 2

        for attempt in range(max_retries):
            time.sleep(0.5)
            self.devices = self.get_devices()
            if self.devices:
                self.logger.system_log("Found devices during initialization", {"devices": self.devices})

                # Auto-select first device
                if self.devices:
                    first_dev = self.devices[0]
                    self.logger.system_log("Auto-selecting first device", {"device": first_dev})
                    self.select_device(first_dev['addr7'])
                return
            
        self.devices = []
    
    def send_command(self, cmd):
        """Track pause state when sending commands and log the command"""
        if cmd.get("action") == "pause":
            self.is_paused = True
        elif cmd.get("action") == "resume":
            self.is_paused = False
        if cmd.get("action") == "resume":
            self.is_active = True
        elif cmd.get("action") == "pause":
            self.is_active = False
            
        # Log the command being sent without timestamp (only to JSON)
        self.logger.command_log(cmd)
            
        self.lock.lock()
        try:
            cmd_str = json.dumps(cmd) + '\n'
            self.ser.write(cmd_str.encode())
        finally:
            self.lock.unlock()
    
    def wait_response(self, action, timeout=1.0):
        """Wait for specific response with enhanced logging and diagnostics"""
        start = time.time()
        stored_responses = []
        iterations = 0
        
        if action == "get_devices":
            self.logger.system_log(f"Waiting for '{action}' response", {"timeout": timeout})
        
        while time.time() - start < timeout:
            try:
                response = self.response_queue.get(timeout=0.01)
                
                if response.get("action") == action:
                    # Success! Got the response we're looking for
                    if action == "get_devices":
                        elapsed = time.time() - start
                        self.logger.system_log(f"Found '{action}' response", {"elapsed": elapsed})
                    
                    # Put back any other responses we collected
                    while stored_responses:
                        self.response_queue.put(stored_responses.pop(0))
                    
                    return response
                else:
                    self.logger.system_log("Received unexpected response", {
                        "expected_action": action,
                        "received_action": response.get("action")
                    })
                    stored_responses.append(response)
            except Empty:
                iterations += 1
                time.sleep(0.01)
        
        elapsed = time.time() - start
        self.logger.error_log(f"TIMEOUT waiting for '{action}' response", {
            "elapsed": elapsed,
            "iterations": iterations
        })
        
        # Log what responses we did find during the wait
        if stored_responses:
            self.logger.system_log(f"Found {len(stored_responses)} unrelated responses while waiting", {
                "responses_count": len(stored_responses),
                "responses": stored_responses  # Log the actual responses in JSON
            })
        else:
            self.logger.system_log("No other responses received during wait period")
        
        # Put back any responses we collected
        while stored_responses:
            self.response_queue.put(stored_responses.pop(0))
            
        return None

    def rescan_devices(self):
        self.send_command({"action": "scan"})
        return self.wait_response("scan")
    
    def select_device(self, addr7):
        """Select device and create appropriate device instance"""
        if self.is_paused:
            self.send_command({"action": "resume"})
            response = self.wait_response("resume")
            if response and response.get("status") == "OK":
                self.is_paused = False
        
        # Now select the device
        self.send_command({"action": "select", "addr": addr7})
        response = self.wait_response("select")

        if response and response.get("status") == "OK":
            device_name = response.get("name")
            if device_name in DEVICE_MAP:
                self.current_device = DEVICE_MAP[device_name](self, addr7)
                self.logger.system_log("Device selected", {"name": device_name, "address": f"0x{addr7:02X}"})
                self.device_changed.emit()
                return True
        
        self.logger.system_log("Failed to select device", {"response": response})
        self.current_device = None
        return False

    def bulk_rw(self, reads=None, writes=None):
        """Improved bulk read/write with better thread safety"""
        if not self.running:
            return None
            
        cmd = {"action": "bulk_rw"}
        if reads:
            cmd["reads"] = reads
            
        if writes:
            cmd["writes"] = writes
            
        try:
            self.send_command(cmd)
            response = self.wait_response("bulk_rw", timeout=1.0)
            
            if not response:
                return None
                
            if response.get("status") == "PAUSED":
                return None
                
            return response
                
        except Exception as e:
            self.logger.error_log("Bulk RW error", e)
            return None

    def monitor(self):
        """Monitoraggio valori in modalità console"""
        print("Starting monitor mode...")
        self.send_command({"action": "resume"})
        
        try:
            while True:
                if self.current_device:
                    measurements = self.current_device.get_measurements()

        except KeyboardInterrupt:
            print("\nStopping monitor...")

        finally:
            print("Pausing I2C communication...")
            self.send_command({"action": "pause"})
            time.sleep(0.01)
    
    def _send_pause(self):
        """Send pause command directly without logging"""
        try:
            if self.ser and self.ser.is_open:
                cmd_str = json.dumps({"action": "pause"}) + '\n'
                self.ser.write(cmd_str.encode())
                time.sleep(0.01)
        except:
            pass
    
    def close(self):
        """Improved close with better resource management"""
        try:
            self.logger.system_log("Closing I2CManager")
            self._send_pause()
            
            # Signal worker to stop
            self.running[0] = False
            
            # Wait for the threadpool to finish (optional, could cause brief blocking)
            self.threadpool.waitForDone(500)  # Wait max 500ms
            
            # Clear the response queue
            while not self.response_queue.empty():
                try:
                    self.response_queue.get_nowait()
                except Empty:
                    break
            
            # Close the serial port
            if hasattr(self, 'ser') and self.ser and self.ser.is_open:
                self.ser.close()
                self.logger.system_log("Serial port closed")
            
            # Log session summary
            summary = self.logger.get_session_summary()
            self.logger.system_log("Session summary", summary)
            
        except Exception as e:
            self.logger.error_log("Error during close", e)

    def get_device_info(self, addr7):
        """Get device name from firmware"""
        self.send_command({"action": "get_status"})
        response = self.wait_response("get_status")
        if response:
            return response.get("device_name", "Unknown")
        return "Unknown"
    
    def get_devices(self):
        """Get list of devices from firmware with improved debugging"""
        self.logger.system_log("STARTING DEVICE DETECTION")
        
        # First, clear any pending data
        while not self.response_queue.empty():
            try:
                discarded = self.response_queue.get_nowait()
                self.logger.system_log("Discarding pending response", {"action": discarded.get('action', 'unknown')})
            except Empty:
                break
        
        # Try with multiple retries and increasing timeouts
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            # Calculate a longer timeout for later attempts
            timeout = 1.0 * attempt  # Progressively increase timeout
            
            self.logger.system_log("Device detection attempt", {
                "attempt": attempt, 
                "max_retries": max_retries, 
                "timeout": timeout
            })
            self.send_command({"action": "get_devices"})
            
            # Wait for response
            response = self.wait_response("get_devices", timeout=timeout)
            
            if response and 'devices' in response and 'names' in response:
                devices = [
                    {"addr7": addr, "name": name} 
                    for addr, name in zip(
                        response["devices"],
                        response["names"]
                    )
                ]
                self.logger.system_log("Device detection success", {"devices_found": len(devices)})
                return devices
            
            # Wait before retry
            if attempt < max_retries:
                retry_wait = 0.5 * attempt  # Progressively increase wait time
                self.logger.system_log("Retrying device detection", {"retry_wait": retry_wait})
                time.sleep(retry_wait)
        
        self.logger.system_log("Device detection failed after all attempts")
        return []
    
    def list_devices(self):
        """Display available I2C devices with names"""
        print("\nAvailable I2C devices:")
        print("----------------------")
        for i, dev in enumerate(self.devices):
            addr = dev['addr7']
            name = dev.get('name', 'Unknown')
            print(f"{i}: {name:<15} (Address: 0x{addr:02X})")
        return self.devices
    
    def interactive_select(self):
        """Let user select a device by name or number"""
        devices = self.list_devices()
        if not devices:
            print("No devices found!")
            return False
            
        while True:
            try:
                choice = input("\nSelect device by number or name (or 'q' to quit): ").strip()
                if choice.lower() == 'q':
                    return False
                
                # Try to match by number
                try:
                    idx = int(choice)
                    if 0 <= idx < len(devices):
                        self.select_device(devices[idx]['addr7'])
                        print(f"Selected {devices[idx].get('name', 'Unknown')} at address 0x{devices[idx]['addr7']:02X}")
                        return True
                    
                except ValueError:
                    matches = [(i, dev) for i, dev in enumerate(devices) if choice.lower() in dev.get('name', '').lower()]
                    
                    if len(matches) == 1:
                        idx, dev = matches[0]
                        self.select_device(dev['addr7'])
                        print(f"Selected {dev.get('name', 'Unknown')} at address 0x{dev['addr7']:02X}")
                        return True
                    
                    elif len(matches) > 1:
                        print("Multiple matches found. Please be more specific or use the number:")
                        for i, dev in matches:
                            print(f"{i}: {dev.get('name', 'Unknown')} (Address: 0x{dev['addr7']:02X})")
                    else:
                        print("Device not found! Please try again.")
                        
            except Exception as e:
                print(f"Error: {e}")
                print("Please enter a valid number or name")
    
    def write_register(self, reg, value):
        """Write single register wrapper"""
        response = self.bulk_rw(writes=[{"reg": reg, "value": value}])
        return response and response.get("status") == "OK"
        
    def read_register(self, reg):
        """Read single register wrapper"""
        response = self.bulk_rw(reads=[reg])
        return response["values"][0] if response and "values" in response else None


class SerialWorker(QRunnable):
    """Worker class for handling serial port communication in a separate thread using QThreadPool"""
    
    def __init__(self, ser, queue, running_flag, logger=None):
        super().__init__()
        self.ser = ser
        self.response_queue = queue
        self.running_flag = running_flag
        self.buffer = ""
        self.logger = logger or get_logger()
        
    @pyqtSlot()
    def run(self):
        """Main worker method to read from serial port and process data"""
        self.logger.system_log("SerialWorker started")
        
        while self.running_flag[0]:
            if not self.ser.is_open:
                time.sleep(0.1)
                continue
                
            try:
                if self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting)
                    if data:
                        decoded = data.decode(errors='ignore')
                        self.buffer += decoded
                        
                        while '\n' in self.buffer:
                            line, self.buffer = self.buffer.split('\n', 1)
                            try:
                                line = line.strip()
                                if line:  # Skip empty lines
                                    response = json.loads(line)
                                    # Log the received response without timestamp (only to JSON)
                                    self.logger.response_log(response)
                                    self.response_queue.put(response)
                            except json.JSONDecodeError:
                                error_msg = f"Invalid JSON: {line[:50]}..."
                                self.logger.error_log(error_msg)
            except serial.SerialException as e:
                self.logger.error_log("Serial error", e)
            except Exception as e:
                self.logger.error_log("Worker error", e)
                
            time.sleep(0.001)