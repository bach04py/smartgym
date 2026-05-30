"""
FIXED ANT+ HEART RATE SENDER FOR RASPBERRY PI
With built-in diagnostics and proper retry logic
"""

from openant.easy.node import Node
from openant.devices.scanner import Scanner
from openant.devices.utilities import auto_create_device
from openant.devices import ANTPLUS_NETWORK_KEY

import requests
import time
import socket
from datetime import datetime

# ==============================
# CONFIGURATION
# ==============================

# !!!!! IMPORTANT: UPDATE THIS IP !!!!
# Run: ipconfig (Windows) or ifconfig (Linux) on your server
# Look for IPv4 Address in your network adapter
SERVER_IP = "192.168.10.77"  # <-- CORRECT IP FOR THIS NETWORK
SERVER_PORT = 8000
API_URL = f"http://{SERVER_IP}:{SERVER_PORT}/api/heart-rate"

# Timeout and retry settings
REQUEST_TIMEOUT = 10  # Increased from 3 to 10 seconds
MAX_RETRIES = 3
RETRY_DELAY = 0.5  # seconds

# Logging
LOG_FILE = "/home/pi/heart_rate.log"  # Change path if needed
devices = {}

stats = {
    "sent": 0,
    "failed": 0,
    "last_error": None,
    "last_error_time": None
}

# ==============================
# LOGGING FUNCTIONS
# ==============================

def log_message(msg, level="INFO"):
    """Log to console and file"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {msg}"
    print(log_line)
    
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_line + "\n")
    except:
        pass

# ==============================
# DIAGNOSTIC FUNCTIONS
# ==============================

def test_server_connectivity():
    """Test if server is reachable"""
    log_message("Testing server connectivity...", "TEST")
    
    # Test 1: Socket connection
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((SERVER_IP, SERVER_PORT))
        sock.close()
        
        if result == 0:
            log_message(f"✓ Server socket reachable at {SERVER_IP}:{SERVER_PORT}", "TEST")
            return True
        else:
            log_message(f"✗ Server socket NOT reachable (error: {result})", "ERROR")
            log_message(f"  → Check if IP is correct: {SERVER_IP}", "ERROR")
            log_message(f"  → Verify server is running", "ERROR")
            return False
    except Exception as e:
        log_message(f"✗ Socket test failed: {e}", "ERROR")
        return False

def test_http_connection():
    """Test HTTP connection"""
    try:
        response = requests.get(
            f"http://{SERVER_IP}:{SERVER_PORT}/",
            timeout=5
        )
        log_message(f"✓ HTTP connection successful (status: {response.status_code})", "TEST")
        return True
    except requests.exceptions.Timeout:
        log_message("✗ HTTP connection timed out", "ERROR")
        return False
    except requests.exceptions.ConnectionError:
        log_message("✗ HTTP connection refused - server not responding", "ERROR")
        return False
    except Exception as e:
        log_message(f"✗ HTTP test failed: {e}", "ERROR")
        return False

def test_api_endpoint():
    """Test API endpoint"""
    try:
        response = requests.get(
            f"http://{SERVER_IP}:{SERVER_PORT}/api/status",
            timeout=5
        )
        if response.status_code == 200:
            log_message(f"✓ API endpoint accessible", "TEST")
            return True
        else:
            log_message(f"✗ API returned status {response.status_code}", "ERROR")
            return False
    except Exception as e:
        log_message(f"✗ API test failed: {e}", "ERROR")
        return False

def run_diagnostics():
    """Run all diagnostics before starting"""
    log_message("="*60, "DIAG")
    log_message("RUNNING DIAGNOSTICS", "DIAG")
    log_message("="*60, "DIAG")
    
    test1 = test_server_connectivity()
    test2 = test_http_connection()
    test3 = test_api_endpoint()
    
    log_message("="*60, "DIAG")
    
    if test1 and test2 and test3:
        log_message("✓ ALL DIAGNOSTICS PASSED - Ready to send data", "INFO")
        return True
    else:
        log_message("✗ DIAGNOSTICS FAILED - Check configuration", "ERROR")
        log_message("", "ERROR")
        log_message("TROUBLESHOOTING:", "ERROR")
        log_message("1. Verify correct IP on server: ipconfig (Windows) or ifconfig (Linux)", "ERROR")
        log_message("2. Update SERVER_IP variable in this script", "ERROR")
        log_message("3. Check Windows Defender Firewall allows port 8000", "ERROR")
        log_message("4. Ensure server is running: uvicorn app:app --host 0.0.0.0 --port 8000", "ERROR")
        log_message("5. Verify both devices on same network", "ERROR")
        return False

# ==============================
# SEND FUNCTION WITH RETRY
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
                stats["sent"] += 1
                stats["last_error"] = None
                log_message(
                    f"✓ HR: {payload['heart_rate']} BPM | Sent: {stats['sent']} | Failed: {stats['failed']}",
                    "SUCCESS"
                )
                return True
            else:
                error = f"HTTP {response.status_code}"
                if attempt == MAX_RETRIES:
                    stats["failed"] += 1
                    stats["last_error"] = error
                    stats["last_error_time"] = datetime.now().isoformat()
                    log_message(
                        f"✗ HR: {payload['heart_rate']} BPM | {error} | Attempts: {attempt}/{MAX_RETRIES}",
                        "ERROR"
                    )
                    return False
                else:
                    log_message(f"  → Retry {attempt}/{MAX_RETRIES}...", "RETRY")
                    time.sleep(RETRY_DELAY)
        
        except requests.exceptions.Timeout:
            error = f"Request timeout ({REQUEST_TIMEOUT}s)"
            if attempt == MAX_RETRIES:
                stats["failed"] += 1
                stats["last_error"] = error
                stats["last_error_time"] = datetime.now().isoformat()
                log_message(
                    f"✗ HR: {payload['heart_rate']} BPM | {error}",
                    "ERROR"
                )
                return False
            else:
                log_message(f"  → Timeout, retry {attempt}/{MAX_RETRIES}...", "RETRY")
                time.sleep(RETRY_DELAY)
        
        except requests.exceptions.ConnectionError as e:
            error = "Connection refused"
            if attempt == MAX_RETRIES:
                stats["failed"] += 1
                stats["last_error"] = error
                stats["last_error_time"] = datetime.now().isoformat()
                log_message(
                    f"✗ HR: {payload['heart_rate']} BPM | {error}",
                    "ERROR"
                )
                log_message(
                    f"  → Check if server IP is correct: {SERVER_IP}",
                    "ERROR"
                )
                return False
            else:
                log_message(f"  → Connection error, retry {attempt}/{MAX_RETRIES}...", "RETRY")
                time.sleep(RETRY_DELAY)
        
        except Exception as e:
            error = str(e)
            if attempt == MAX_RETRIES:
                stats["failed"] += 1
                stats["last_error"] = error
                stats["last_error_time"] = datetime.now().isoformat()
                log_message(f"✗ Unexpected error: {error}", "ERROR")
                return False
            else:
                log_message(f"  → Error, retry {attempt}/{MAX_RETRIES}...", "RETRY")
                time.sleep(RETRY_DELAY)
    
    return False

# ==============================
# MAIN ANT+ SCANNER
# ==============================

def main():
    log_message("="*60, "INFO")
    log_message("RASPBERRY PI ANT+ HEART RATE SENDER", "INFO")
    log_message("="*60, "INFO")
    log_message(f"Server: {SERVER_IP}:{SERVER_PORT}", "INFO")
    log_message(f"Timeout: {REQUEST_TIMEOUT}s per request", "INFO")
    log_message(f"Max retries: {MAX_RETRIES}", "INFO")
    log_message(f"Log file: {LOG_FILE}", "INFO")
    
    # Run diagnostics first
    if not run_diagnostics():
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            log_message("Aborted by user", "INFO")
            return
    
    log_message("Starting ANT+ scanner...", "INFO")
    log_message("Listening for ANT+ devices...", "INFO")
    
    node = Node()
    node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
    
    scanner = Scanner(node, device_id=0, device_type=120)
    
    def on_found(device_tuple):
        device_id, device_type, transmission_type = device_tuple
        log_message(f"Found device #{device_id}", "DEVICE")
        
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
            log_message(f"Connected to device #{device_id}", "DEVICE")
            
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
                    log_message(f"Parse error: {e}", "ERROR")
            
            dev.on_device_data = on_device_data
        
        except Exception as e:
            log_message(f"Auto create error: {e}", "ERROR")
    
    scanner.on_found = on_found
    
    try:
        node.start()
    
    except KeyboardInterrupt:
        log_message("Stopped by user", "INFO")
    
    finally:
        log_message("="*60, "INFO")
        log_message("STATISTICS", "INFO")
        log_message("="*60, "INFO")
        log_message(f"Messages sent: {stats['sent']}", "INFO")
        log_message(f"Send failures: {stats['failed']}", "INFO")
        if stats['last_error']:
            log_message(f"Last error: {stats['last_error']}", "INFO")
            log_message(f"Last error time: {stats['last_error_time']}", "INFO")
        log_message("="*60, "INFO")
        
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
