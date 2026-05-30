#!/usr/bin/env python3
"""
Raspberry Pi Helper - Find and test the correct server IP
Run this on Raspberry Pi to automatically find your server
"""

import socket
import requests
import time
from datetime import datetime

def get_local_gateway():
    """Try to detect the gateway/server IP range"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Extract network prefix (e.g., 192.168.1 from 192.168.1.100)
        parts = local_ip.split('.')
        network = '.'.join(parts[:3])
        
        return network, local_ip
    except:
        return None, None

def scan_network():
    """Scan local network for server"""
    print("\n" + "="*60)
    print("RASPBERRY PI - AUTO DETECT SERVER IP")
    print("="*60)
    
    network, local_ip = get_local_gateway()
    
    if not network:
        print("\n✗ Failed to detect local network")
        print("Please manually enter your server IP")
        ip = input("Server IP: ").strip()
        return ip
    
    print(f"\nLocal IP: {local_ip}")
    print(f"Network: {network}.0/24")
    print(f"\nScanning for server on {network}.* (this may take 30 seconds)...\n")
    
    found_servers = []
    
    # Scan common IPs (excluding 1 which is usually gateway, and last few which are broadcast)
    for i in range(2, 250):
        ip = f"{network}.{i}"
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, 8000))
            sock.close()
            
            if result == 0:
                # Port 8000 is open, test if it's our server
                try:
                    response = requests.get(
                        f"http://{ip}:8000/api/status",
                        timeout=2
                    )
                    if response.status_code == 200:
                        data = response.json()
                        found_servers.append({
                            'ip': ip,
                            'status': data.get('connected'),
                            'messages': data.get('total_messages', 0)
                        })
                        print(f"✓ Found SmartGym server at {ip}:8000")
                except:
                    pass
        except:
            pass
    
    if found_servers:
        print("\n" + "="*60)
        print("FOUND SERVERS:")
        print("="*60)
        for i, server in enumerate(found_servers, 1):
            print(f"\n{i}. {server['ip']}:8000")
            print(f"   Status: {'Connected' if server['status'] else 'Disconnected'}")
            print(f"   Messages: {server['messages']}")
        
        if len(found_servers) == 1:
            return found_servers[0]['ip']
        else:
            choice = input("\nSelect server number (1, 2, etc): ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(found_servers):
                    return found_servers[idx]['ip']
            except:
                pass
    
    else:
        print("\n✗ No SmartGym servers found on network")
        print("\nPossible reasons:")
        print("  1. Server is not running")
        print("  2. Server is on different network")
        print("  3. Firewall is blocking port 8000")
        print("  4. IP address is static")
        
        print("\nEnter server IP manually:")
        ip = input("Server IP: ").strip()
        return ip

def test_server(ip):
    """Test connection to found server"""
    print("\n" + "="*60)
    print(f"TESTING {ip}:8000")
    print("="*60)
    
    # Test 1: Socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, 8000))
        sock.close()
        if result == 0:
            print("✓ Socket connection OK")
        else:
            print(f"✗ Socket connection failed (error {result})")
            return False
    except Exception as e:
        print(f"✗ Socket error: {e}")
        return False
    
    # Test 2: HTTP
    try:
        response = requests.get(f"http://{ip}:8000/", timeout=5)
        print(f"✓ HTTP connection OK (status {response.status_code})")
    except Exception as e:
        print(f"✗ HTTP error: {e}")
        return False
    
    # Test 3: API
    try:
        response = requests.get(f"http://{ip}:8000/api/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API OK - Server is {'CONNECTED' if data['connected'] else 'DISCONNECTED'}")
            print(f"  Messages received: {data['total_messages']}")
            return True
        else:
            print(f"✗ API returned {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ API error: {e}")
        return False

def main():
    ip = scan_network()
    
    if ip:
        print(f"\nTesting {ip}...")
        if test_server(ip):
            print("\n" + "="*60)
            print("✓ SUCCESS!")
            print("="*60)
            print(f"\nUpdate your Raspberry Pi sender script with:")
            print(f"\n  SERVER_IP = \"{ip}\"")
            print(f"\nOr if using the fixed script:")
            print(f"  Edit rpi_sender_fixed.py and change:")
            print(f"  SERVER_IP = \"192.168.1.77\"")
            print(f"  To:")
            print(f"  SERVER_IP = \"{ip}\"")
            print("\nThen restart the sender!")
            return 0
        else:
            print("\n✗ Connection test failed")
            return 1
    else:
        print("\n✗ No IP provided")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
