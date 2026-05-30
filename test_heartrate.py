"""
Test Script - Simulate Raspberry Pi sending heart rate data
Run this to test the server without needing actual Raspberry Pi hardware
"""

import requests
import time
import random
import json
from datetime import datetime

# Configuration
SERVER_URL = "http://localhost:8000/api/heart-rate"
STATUS_URL = "http://localhost:8000/api/status"
DEVICE_ID = "rpi5-test"

def get_simulated_heart_rate():
    """Generate realistic heart rate data for testing"""
    # Simulate heart rate: 60-100 BPM with some variation
    base_rate = random.randint(60, 100)
    variation = random.randint(-5, 5)
    return max(40, min(150, base_rate + variation))

def send_data(heart_rate):
    """Send heart rate data to server"""
    try:
        payload = {
            "heart_rate": heart_rate,
            "device_id": DEVICE_ID,
            "timestamp": time.time()
        }
        
        response = requests.post(SERVER_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            print(f"✓ [{datetime.now().strftime('%H:%M:%S')}] Sent: {heart_rate} BPM")
        else:
            print(f"✗ Server error: {response.status_code} - {response.json()}")
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to server at {SERVER_URL}")
        print("   Make sure server is running: uvicorn app:app --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"✗ Error: {e}")

def get_status():
    """Fetch and display server status"""
    try:
        response = requests.get(STATUS_URL, timeout=5)
        status = response.json()
        
        print("\n" + "="*50)
        print("SERVER STATUS")
        print("="*50)
        print(f"Connected: {'✓ YES' if status['connected'] else '✗ NO'}")
        print(f"Total Messages: {status['total_messages']}")
        print(f"Total Errors: {status['error_count']}")
        if status['last_error']:
            print(f"Last Error: {status['last_error']}")
        if status['latest_data']:
            print(f"Latest Data: {json.dumps(status['latest_data'], indent=2)}")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"✗ Failed to get status: {e}")

def test_invalid_data():
    """Test error handling with invalid data"""
    print("\nTesting error handling...\n")
    
    test_cases = [
        {"device_id": "test", "heart_rate": -10},  # Negative heart rate
        {"device_id": "test", "heart_rate": 400},  # Too high
        {"device_id": "test"},  # Missing heart_rate
        {"heart_rate": 85},  # Missing device_id
    ]
    
    for payload in test_cases:
        try:
            response = requests.post(SERVER_URL, json=payload, timeout=5)
            if response.status_code != 200:
                print(f"✓ Error caught: {response.json()['message']}")
        except Exception as e:
            print(f"✗ Error: {e}")

if __name__ == "__main__":
    print("SmartGym Heart Rate Test Script")
    print("================================\n")
    
    mode = input("Choose mode:\n1. Continuous stream (20 seconds)\n2. Single test\n3. Error handling test\n> ").strip()
    
    if mode == "1":
        print(f"\nSending heart rate data for 20 seconds...\n")
        start_time = time.time()
        
        while time.time() - start_time < 20:
            heart_rate = get_simulated_heart_rate()
            send_data(heart_rate)
            time.sleep(1)
        
        print("\nTest complete!\n")
        get_status()
        
    elif mode == "2":
        heart_rate = get_simulated_heart_rate()
        send_data(heart_rate)
        get_status()
        
    elif mode == "3":
        test_invalid_data()
        get_status()
    
    else:
        print("Invalid choice")
