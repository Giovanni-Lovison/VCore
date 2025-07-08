# 08.07.25

import serial
import json
import time
from serial.tools import list_ports
import argparse

def find_port():
    """Find the CH340 port or allow manual specification"""
    for port in list_ports.comports():
        if 'CH340' in port.description:
            print(f"[*] Found CH340 device at {port.device}")
            return port.device
    
    print("[!] No CH340 device found")
    return None

def send_command(ser, cmd):
    """Send a command to the device"""
    cmd_str = json.dumps(cmd) + '\n'
    print(f"\n[>] Sending: {cmd}")
    ser.write(cmd_str.encode())

def read_response(ser, timeout=5.0, verbose=False):
    """Read response with timeout and verbose debugging"""
    start_time = time.time()
    buffer = ""
    responses = []
    
    while time.time() - start_time < timeout:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            if data:
                decoded = data.decode(errors='ignore')
                if verbose:
                    print(f"[Raw] Received: {decoded.strip()}")
                buffer += decoded
                
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():  # Only process non-empty lines
                        try:
                            response = json.loads(line.strip())
                            print(f"[<] Response: {json.dumps(response, indent=2)}")
                            responses.append(response)
                        except json.JSONDecodeError:
                            print(f"[!] Invalid JSON: {line.strip()}")
        
        # Small sleep to avoid high CPU usage
        time.sleep(0.01)
    
    if not responses:
        print(f"[!] No response received within {timeout} seconds")
    
    return responses

def test_get_devices(port=None, baud=115200, timeout=5.0, verbose=False):
    """Test the get_devices command with detailed debugging"""
    if port is None:
        port = find_port()
        if port is None:
            print("[!] No port specified or found. Use --port to specify manually.")
            return False
    
    try:
        # Connect to the port with increased timeouts
        print(f"[*] Opening {port} at {baud} baud")
        ser = serial.Serial(port, baud, timeout=1.0, write_timeout=1.0)
        
        # Wait for the device to initialize
        time.sleep(1.0)
        
        # Clear any pending data
        if ser.in_waiting:
            ser.reset_input_buffer()
            print(f"[*] Cleared input buffer")
        
        # Send a pause command to reset the device state
        print("[*] Sending pause command to reset device state")
        send_command(ser, {"action": "pause"})
        time.sleep(0.5)
        read_response(ser, timeout=1.0, verbose=verbose)
        
        # Send a resume command
        print("[*] Sending resume command")
        send_command(ser, {"action": "resume"})
        time.sleep(0.5)
        read_response(ser, timeout=1.0, verbose=verbose)
        
        # Send the get_devices command
        print(f"[*] Testing get_devices command (timeout: {timeout}s)")
        send_command(ser, {"action": "get_devices"})
        
        # Read and print the response with detailed info
        responses = read_response(ser, timeout=timeout, verbose=verbose)
        
        # Check if we got a valid get_devices response
        for resp in responses:
            if resp.get("action") == "get_devices" and "devices" in resp and "names" in resp:
                devices = [{"addr7": addr, "name": name} 
                          for addr, name in zip(resp["devices"], resp["names"])]
                print(f"[*] SUCCESS! Found {len(devices)} devices:")
                for i, dev in enumerate(devices):
                    print(f"    {i}: {dev['name']} (Address: 0x{dev['addr7']:02X})")
                return True
        
        print("[!] Failed to get valid device information")
        return False
        
    except serial.SerialException as e:
        print(f"[!] Serial error: {e}")
        return False
    except Exception as e:
        print(f"[!] Error: {e}")
        return False
    finally:
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print("[*] Serial port closed")
        except:
            pass

def test_bulk_rw(port=None, baud=115200, addr=None, verbose=False):
    """Test bulk read/write operations on a selected device"""
    if port is None:
        port = find_port()
        if port is None:
            print("[!] No port specified or found. Use --port to specify manually.")
            return False
    
    try:
        # Connect to the port
        print(f"[*] Opening {port} at {baud} baud")
        ser = serial.Serial(port, baud, timeout=1.0, write_timeout=1.0)
        
        # Wait for the device to initialize
        time.sleep(1.0)
        
        # Clear any pending data
        if ser.in_waiting:
            ser.reset_input_buffer()
            print(f"[*] Cleared input buffer")
        
        # Get devices first
        print("[*] Getting device list...")
        send_command(ser, {"action": "get_devices"})
        responses = read_response(ser, timeout=2.0, verbose=verbose)
        
        device_addr = addr
        if device_addr is None:
            # Find the first device if none specified
            for resp in responses:
                if resp.get("action") == "get_devices" and "devices" in resp:
                    if resp["devices"]:
                        device_addr = resp["devices"][0]
                        device_name = resp["names"][0] if "names" in resp and resp["names"] else "Unknown"
                        print(f"[*] Using first device: {device_name} (0x{device_addr:02X})")
                        break
        
        if device_addr is None:
            print("[!] No device found or specified. Use --addr to specify.")
            return False
        
        # Select the device
        print(f"[*] Selecting device at address 0x{device_addr:02X}")
        send_command(ser, {"action": "select", "addr": device_addr})
        read_response(ser, timeout=1.0, verbose=verbose)
        
        # Test bulk read - choose common registers based on likely device types
        test_registers = [0x00, 0x01, 0x2D, 0x2C]  # Common registers
        print(f"[*] Testing bulk read of registers: {[f'0x{r:02X}' for r in test_registers]}")
        send_command(ser, {"action": "bulk_rw", "reads": test_registers})
        read_response(ser, timeout=2.0, verbose=verbose)
        
        return True
        
    except serial.SerialException as e:
        print(f"[!] Serial error: {e}")
        return False
    except Exception as e:
        print(f"[!] Error: {e}")
        return False
    finally:
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print("[*] Serial port closed")
        except:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test VCore Monitor serial communication")
    parser.add_argument("--port", help="Serial port to use (auto-detect if not specified)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Response timeout in seconds (default: 5.0)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed debugging output")
    parser.add_argument("--test", choices=["get_devices", "bulk_rw"], default="get_devices",
                        help="Test to run (default: get_devices)")
    parser.add_argument("--addr", type=lambda x: int(x, 0), help="Device address for bulk_rw test (hex or decimal)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"VCore Monitor Serial Communication Test")
    print("=" * 60)
    
    if args.test == "get_devices":
        test_get_devices(args.port, args.baud, args.timeout, args.verbose)
    elif args.test == "bulk_rw":
        test_bulk_rw(args.port, args.baud, args.addr, args.verbose)
