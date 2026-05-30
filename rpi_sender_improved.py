"""
IMPROVED ANT+ HEART RATE SENDER FOR RASPBERRY PI
With error handling, retry logic, and diagnostics
"""

from openant.easy.node import Node
from openant.devices.scanner import Scanner
from openant.devices.utilities import auto_create_device
from openant.devices import ANTPLUS_NETWORK_KEY

import requests
import time
from datetime import datetime
import socket

# ==============================
# CONFIGURATION
# ==============================

# Change this to your server IP (find it with troubleshooting steps below)
SERVER_IP = "192.168.1.77"
SERVER_PORT = 8000
API_URL = f"http://{SERVER_IP}:{SERVER_PORT}/api/heart-rate"

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
REQUEST_TIMEOUT = 5  # seconds (increased from 3)

devices = {}
send_stats = {
    "sent": 0,
    "failed": 0,
    "last_error": None
}

# ==============================
# DIAGNOSTIC FUNCTIONS
# ==============================

def test_server_connectivity():
    """Test if server is reachable"""
    print("\n" + "="*60)
    print("TESTING SERVER CONNECTIVITY")
    print("="*60)
    
    # Test 1: Ping via socket
    print(f"\n[1] Testing connection to {SERVER_IP}:{SERVER_PORT}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((SERVER_IP, SERVER_PORT))
        sock.close()
        
        if result == 0:
            print(f"    ✓ Server is reachable")
        else:
            print(f"    ✗ Server is NOT reachable (code: {result})")
            print(f"    → Check if server is running")
            print(f"    → Check if IP address is correct")
            return False
    except Exception as e:
        print(f"    ✗ Connection test failed: {e}")
        return False
    
    # Test 2: HTTP GET request
    print(f"\n[2] Testing HTTP connection...")
    try:
        response = requests.get(
            f"http://{SERVER_IP}:{SERVER_PORT}/",
            timeout=5
        )
        print(f"    ✓ HTTP connection successful (status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print(f"    ✗ HTTP connection refused")
        print(f"    → Make sure FastAPI server is running")
        return False
    except requests.exceptions.Timeout:
        print(f"    ✗ HTTP request timed out")
        print(f"    → Server might be overloaded or unreachable")
        return False
    except Exception as e:
        print(f"    ✗ HTTP test failed: {e}")
        return False
    
    # Test 3: API status endpoint
    print(f"\n[3] Testing API status endpoint...")
    try:
        response = requests.get(
            f"http://{SERVER_IP}:{SERVER_PORT}/api/status",
            timeout=5
        )
        if response.status_code == 200:
            print(f"    ✓ API is accessible")
            return True
        else:
            print(f"    ✗ API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"    ✗ API test failed: {e}")
        return False

def get_local_ip():
    """Get the Raspberry Pi's local IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "unknown"

# ==============================
# SEND FUNCTION WITH RETRY LOGIC
# ==============================

def send_to_server(payload):
    """Send heart rate data with retry logic"""
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                API_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                send_stats["sent"] += 1
                send_stats["last_error"] = None
                print(f"✓ [{datetime.now().strftime('%H:%M:%S')}] " + 
                      f"HR: {payload['heart_rate']} BPM | Status: OK")
                return True
            else:
                error_msg = f"HTTP {response.status_code}"
                if attempt == MAX_RETRIES:
                    send_stats["failed"] += 1
                    send_stats["last_error"] = error_msg
                    print(f"✗ [{datetime.now().strftime('%H:%M:%S')}] " +
                          f"HR: {payload['heart_rate']} BPM | {error_msg}")
                else:
                    print(f"  → Retry {attempt}/{MAX_RETRIES}...")
                    time.sleep(RETRY_DELAY)
                    
        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            if attempt == MAX_RETRIES:
                send_stats["failed"] += 1
                send_stats["last_error"] = error_msg
                print(f"✗ [{datetime.now().strftime('%H:%M:%S')}] " +
                      f"HR: {payload['heart_rate']} BPM | {error_msg}")
            else:
                print(f"  → Timeout, retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                
        except requests.exceptions.ConnectionError as e:
            error_msg = "Connection refused/unreachable"
            if attempt == MAX_RETRIES:
                send_stats["failed"] += 1
                send_stats["last_error"] = error_msg
                print(f"✗ [{datetime.now().strftime('%H:%M:%S')}] " +
                      f"HR: {payload['heart_rate']} BPM | {error_msg}")
            else:
                print(f"  → Connection error, retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                
        except Exception as e:
            error_msg = str(e)
            if attempt == MAX_RETRIES:
                send_stats["failed"] += 1
                send_stats["last_error"] = error_msg
                print(f"✗ [{datetime.now().strftime('%H:%M:%S')}] " +
                      f"HR: {payload['heart_rate']} BPM | ERROR: {error_msg}")
            else:
                print(f"  → Error, retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
    
    return False

# ==============================
# MAIN ANT+ SCANNER
# ==============================

def main():
    
    print("="*60)
    print("RASPBERRY PI ANT+ HEART RATE SENDER")
    print("="*60)
    print(f"\nServer: {SERVER_IP}:{SERVER_PORT}")
    print(f"Local IP: {get_local_ip()}")
    print(f"Timeout: {REQUEST_TIMEOUT}s per request")
    print(f"Retries: {MAX_RETRIES} attempts")
    
    # Test connectivity before starting
    if not test_server_connectivity():
        print("\n" + "!"*60)
        print("TROUBLESHOOTING STEPS:")
        print("!"*60)
        print("\n1. Verify server IP:")
        print("   On your server machine, run: ipconfig (Windows) or ifconfig (Linux)")
        print("   Look for 'IPv4 Address' in your network")
        print("\n2. Update SERVER_IP in this script")
        print("\n3. Check firewall:")
        print("   - Windows: Allow port 8000 in Windows Defender")
        print("   - Linux: sudo ufw allow 8000")
        print("\n4. Test from Raspberry Pi:")
        print("   ping 192.168.1.77")
        print("   curl http://192.168.1.77:8000/")
        print("\n5. Make sure server is running:")
        print("   uvicorn app:app --host 0.0.0.0 --port 8000")
        print("!"*60)
        
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            return
    
    print("\n" + "="*60)
    print("STARTING ANT+ SCANNER")
    print("="*60)
    
    node = Node()
    
    node.set_network_key(
        0x00,
        ANTPLUS_NETWORK_KEY
    )
    
    scanner = Scanner(
        node,
        device_id=0,
        device_type=120
    )
    
    def on_found(device_tuple):
        
        device_id, device_type, transmission_type = device_tuple
        
        print(f"\n→ FOUND DEVICE #{device_id}")
        
        if device_id in devices:
            return
        
        try:
            
            dev = auto_create_device(
                node,
                device_id,
                device_type,
                transmission_type
            )
            
            devices[device_id] = dev
            
            print(f"✓ CONNECTED #{device_id}")
            
            def on_device_data(_, page_name, data):
                
                try:
                    
                    if page_name != "heart_rate":
                        return
                    
                    heart_rate = data.heart_rate
                    
                    if heart_rate <= 0:
                        return
                    
                    payload = {
                        "device_id": device_id,
                        "heart_rate": heart_rate,
                        "beat_count": data.beat_count,
                        "beat_time": data.beat_time,
                        "timestamp": time.time()
                    }
                    
                    send_to_server(payload)
                    
                except Exception as e:
                    print(f"✗ Parse error: {e}")
            
            dev.on_device_data = on_device_data
        
        except Exception as e:
            print(f"✗ Auto create error: {e}")
    
    scanner.on_found = on_found
    
    try:
        print("\nListening for ANT+ devices...\n")
        node.start()
    
    except KeyboardInterrupt:
        print("\n\nSTOPPED BY USER")
    
    finally:
        print("\n" + "="*60)
        print("STATISTICS")
        print("="*60)
        print(f"Messages sent: {send_stats['sent']}")
        print(f"Send failures: {send_stats['failed']}")
        if send_stats['last_error']:
            print(f"Last error: {send_stats['last_error']}")
        print("="*60)
        
        try:
            scanner.close_channel()
        except:
            pass
        
        for dev in devices.values():
            try:
                dev.close_channel()
            except:
                pass
        
        try:
            node.stop()
        except:
            pass

if __name__ == "__main__":
    main()
