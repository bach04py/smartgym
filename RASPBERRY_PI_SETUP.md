# Raspberry Pi 5 Heart Rate Data Sender Setup

## Server Requirements

Make sure your FastAPI server is running:
```bash
cd d:\smartgym
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Raspberry Pi Code (Python)

### Option 1: Simple HTTP POST (Recommended for Testing)

```python
import requests
import time
import json

# Configuration
SERVER_IP = "192.168.1.100"  # Change to your server IP
SERVER_PORT = 8000
DEVICE_ID = "rpi5-001"

def send_heart_rate(heart_rate):
    """Send heart rate data to server"""
    try:
        url = f"http://{SERVER_IP}:{SERVER_PORT}/api/heart-rate"
        
        payload = {
            "heart_rate": int(heart_rate),
            "device_id": DEVICE_ID,
            "timestamp": time.time()
        }
        
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            print(f"✓ Sent: {heart_rate} BPM")
        else:
            print(f"✗ Error: {response.json()}")
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to server at {SERVER_IP}:{SERVER_PORT}")
    except requests.exceptions.Timeout:
        print("✗ Request timeout")
    except Exception as e:
        print(f"✗ Error: {e}")

# Main loop - Send heart rate every second
if __name__ == "__main__":
    print(f"Connecting to {SERVER_IP}:{SERVER_PORT}")
    print(f"Device ID: {DEVICE_ID}")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            # TODO: Replace with actual sensor reading
            heart_rate = read_from_sensor()  # Your sensor function
            send_heart_rate(heart_rate)
            time.sleep(1)  # Send every second
    
    except KeyboardInterrupt:
        print("\nStopped")
```

### Option 2: With Sensor Library (e.g., MAX30102)

```python
import requests
import time
from max30102 import MAX30102  # Example sensor library

SERVER_IP = "192.168.1.100"
DEVICE_ID = "rpi5-001"

sensor = MAX30102()

while True:
    try:
        heart_rate = sensor.get_heart_rate()
        
        if heart_rate > 0:  # Valid reading
            response = requests.post(
                f"http://{SERVER_IP}:8000/api/heart-rate",
                json={
                    "heart_rate": heart_rate,
                    "device_id": DEVICE_ID,
                    "timestamp": time.time()
                },
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✓ {heart_rate} BPM")
            else:
                print(f"✗ Server error: {response.json()}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    
    time.sleep(1)
```

## Installation on Raspberry Pi

```bash
# Install required packages
sudo apt-get update
sudo apt-get install python3-pip

# Install requests library
pip3 install requests

# (Optional) Install sensor library
pip3 install max30102  # or your specific sensor library
```

## Troubleshooting

### Check if server is reachable:
```bash
ping 192.168.1.100
curl http://192.168.1.100:8000/
```

### View server status:
```
http://192.168.1.100:8000/api/status
```

Expected response:
```json
{
  "connected": true,
  "last_received": 1716444000.123,
  "last_error": null,
  "error_count": 0,
  "total_messages": 42,
  "latest_data": {...}
}
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Connection refused | Server not running | Start server with `uvicorn` |
| Cannot connect | Wrong IP address | Update `SERVER_IP` to match your server |
| Timeout | Network issue | Check network connection, increase timeout |
| "Invalid heart rate" | Heart rate > 300 BPM | Check sensor calibration |
| "Missing field" | Incomplete JSON payload | Ensure all required fields sent |

## Dashboard

Access the real-time dashboard at:
```
http://192.168.1.100:8000/
```

You'll see:
- Current heart rate (BPM)
- Device ID
- Connection status (GREEN = Connected, RED = Disconnected)
- Last error message (if any)
- Total messages & error count
