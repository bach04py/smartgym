#!/usr/bin/env python3
"""
Network Diagnostics Script for Raspberry Pi
Run this to quickly identify connection issues
"""

import socket
import requests
import sys
from datetime import datetime

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_test(name, status, details=""):
    symbol = "✓" if status else "✗"
    print(f"{symbol} {name}")
    if details:
        print(f"  → {details}")

def test_network():
    """Test basic network connectivity"""
    print_header("NETWORK CONNECTIVITY")
    
    # Test 1: Get hostname and IPs
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print_test(True, f"Raspberry Pi IP: {local_ip}")
    except Exception as e:
        print_test(False, f"Failed to get local IP: {e}")
        return False
    
    return True

def test_server(server_ip, server_port=8000):
    """Test connection to server"""
    print_header(f"TESTING SERVER CONNECTION: {server_ip}:{server_port}")
    
    # Test 1: Socket connection
    print("\n[1] Socket Connection Test")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((server_ip, server_port))
        sock.close()
        
        if result == 0:
            print_test(True, f"Server is reachable at {server_ip}:{server_port}")
            socket_ok = True
        else:
            print_test(False, f"Server is NOT reachable", 
                      f"Error code: {result}")
            socket_ok = False
    except Exception as e:
        print_test(False, f"Socket test failed: {e}")
        socket_ok = False
    
    # Test 2: HTTP connection
    print("\n[2] HTTP Connection Test")
    try:
        response = requests.get(
            f"http://{server_ip}:{server_port}/",
            timeout=5
        )
        print_test(True, f"HTTP connection successful",
                  f"Status code: {response.status_code}")
        http_ok = True
    except requests.exceptions.ConnectionError:
        print_test(False, "HTTP connection refused",
                  "Server might not be running or port is blocked")
        http_ok = False
    except requests.exceptions.Timeout:
        print_test(False, "HTTP request timed out",
                  "Server is not responding")
        http_ok = False
    except Exception as e:
        print_test(False, f"HTTP test failed: {e}")
        http_ok = False
    
    # Test 3: API endpoint
    print("\n[3] API Status Test")
    try:
        response = requests.get(
            f"http://{server_ip}:{server_port}/api/status",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print_test(True, "API is accessible")
            print(f"  → Connected: {data.get('connected')}")
            print(f"  → Messages: {data.get('total_messages')}")
            api_ok = True
        else:
            print_test(False, f"API returned status {response.status_code}")
            api_ok = False
    except Exception as e:
        print_test(False, f"API test failed: {e}")
        api_ok = False
    
    # Test 4: Diagnostics endpoint
    print("\n[4] Diagnostics Endpoint Test")
    try:
        response = requests.get(
            f"http://{server_ip}:{server_port}/api/diagnostics",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print_test(True, "Diagnostics endpoint accessible")
            server_info = data.get('server_info', {})
            print(f"  → Server Hostname: {server_info.get('hostname')}")
            print(f"  → Server IPs: {server_info.get('local_ips')}")
            print(f"  → Platform: {server_info.get('platform')}")
            diag_ok = True
        else:
            print_test(False, f"Diagnostics returned {response.status_code}")
            diag_ok = False
    except Exception as e:
        print_test(False, f"Diagnostics test failed: {e}")
        diag_ok = False
    
    return socket_ok and http_ok and api_ok

def test_api_send(server_ip, server_port=8000):
    """Test sending data to API"""
    print_header("TESTING DATA SEND")
    
    try:
        payload = {
            "device_id": "rpi-test",
            "heart_rate": 85,
            "beat_count": 10,
            "beat_time": 20.0,
            "timestamp": 1234567890
        }
        
        response = requests.post(
            f"http://{server_ip}:{server_port}/api/heart-rate",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            print_test(True, "Data sent successfully")
            print(f"  → Response: {response.json()}")
            return True
        else:
            print_test(False, f"Server returned {response.status_code}",
                      f"Response: {response.text}")
            return False
    except Exception as e:
        print_test(False, f"Send test failed: {e}")
        return False

def main():
    print("\n" + "█"*60)
    print("  SMARTGYM NETWORK DIAGNOSTICS")
    print("█"*60)
    
    # Get server IP from user
    default_ip = "192.168.10.77"
    server_ip = input(f"\nEnter server IP (default {default_ip}): ").strip()
    if not server_ip:
        server_ip = default_ip
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting diagnostics...\n")
    
    # Run tests
    network_ok = test_network()
    connection_ok = test_server(server_ip)
    send_ok = test_api_send(server_ip) if connection_ok else False
    
    # Summary
    print_header("SUMMARY")
    print_test(network_ok, "Network Connectivity")
    print_test(connection_ok, f"Connection to {server_ip}:8000")
    print_test(send_ok, "Data Sending")
    
    if network_ok and connection_ok and send_ok:
        print("\n✓ ALL TESTS PASSED - System is ready!")
        print("  Your server IP is: " + server_ip)
        print("  Update your Raspberry Pi script with this IP")
        return 0
    else:
        print("\n✗ Some tests failed - see details above")
        print("\nCommon fixes:")
        print("  1. Check server is running: uvicorn app:app --host 0.0.0.0 --port 8000")
        print("  2. Verify IP with: ipconfig (Windows) or ifconfig (Linux)")
        print("  3. Check Windows Defender allows port 8000")
        print("  4. Ensure Raspberry Pi and server are on same network")
        return 1

if __name__ == "__main__":
    sys.exit(main())
