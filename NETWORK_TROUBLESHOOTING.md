# Network Troubleshooting Guide

## Problem
Your Raspberry Pi gets: **Connection to 192.168.1.77 timed out**

This means the Raspberry Pi cannot reach your server machine.

## Diagnosis Steps

### Step 1: Find Your Server's Actual IP Address

**On Windows (Server Machine):**
```powershell
ipconfig
```
Look for something like:
```
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . : 192.168.1.100
```

**On Linux/Mac (Server Machine):**
```bash
ifconfig
# or
hostname -I
```

### Step 2: Verify Raspberry Pi Can Reach Server

**From Raspberry Pi terminal:**
```bash
ping 192.168.1.77
```

Expected output:
```
PING 192.168.1.77 (192.168.1.77): 56 data bytes
64 bytes from 192.168.1.77: seq=0 ttl=64 time=5.123 ms
```

If you get "timeout" or "unreachable", then:
- **Wrong IP address** → Use the IP from Step 1
- **Different networks** → Both devices need to be on same WiFi/network
- **Firewall blocking** → See Step 4

### Step 3: Test Server is Running and Reachable

**From Raspberry Pi terminal:**
```bash
curl http://192.168.1.77:8000/
```

Expected response:
```html
<!DOCTYPE html>
...
```

If you get:
- **Connection refused** → Server not running
- **Connection timeout** → Firewall or wrong IP
- **No route to host** → Different network

### Step 4: Check Firewall (Windows)

**Open Windows Defender Firewall:**
1. Search "Windows Defender Firewall" in Start menu
2. Click "Allow an app through firewall"
3. Click "Change settings"
4. Click "Allow another app..."
5. Find "Python" or "uvicorn" 
6. Add it with:
   - ✓ Private
   - ✓ Public
7. Click "Add"

**Alternative (PowerShell as Admin):**
```powershell
New-NetFirewallRule -DisplayName "Allow FastAPI 8000" `
    -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### Step 5: Ensure Server Listens on All Interfaces

**Your current command is correct:**
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

This listens on ALL network interfaces.

### Step 6: Network Connection Issues

**If on same WiFi:**
- Both Raspberry Pi and server machine must be on **same WiFi network**
- Check SSID matches

**If on different networks:**
- Use a static routing solution or
- Use a service like ngrok for remote access:
  ```bash
  ngrok http 8000
  # Use the provided URL in Raspberry Pi script
  ```

## Solution Checklist

✓ Step 1: Find actual server IP (e.g., `192.168.1.100`)
✓ Step 2: Update script with correct IP:
```python
SERVER_IP = "192.168.1.100"  # Your actual IP
```
✓ Step 3: Test ping works from Raspberry Pi
✓ Step 4: Test curl works from Raspberry Pi
✓ Step 5: Check Windows firewall allows port 8000
✓ Step 6: Restart uvicorn server after firewall changes

## Common Causes & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Connection timeout | Wrong IP | Update SERVER_IP to match ipconfig |
| Connection refused | Server not running | Run `uvicorn app:app --host 0.0.0.0 --port 8000` |
| Timeout after 3s | Firewall blocking | Allow port 8000 in Windows Defender |
| Works locally, not remote | Listening on localhost only | Ensure `--host 0.0.0.0` is used |
| Can ping but not curl | Wrong port | Check server runs on port 8000 |

## Quick Test (No Real Raspberry Pi)

On your Windows machine, test from PowerShell:
```powershell
# Test if server is accessible locally
curl http://localhost:8000/
curl http://192.168.1.100:8000/  # Use YOUR IP

# Test API
curl -Method POST http://192.168.1.100:8000/api/heart-rate `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"device_id": "test", "heart_rate": 85, "timestamp": 1234567890}'
```

Expected response:
```json
{"status":"ok","message":"Data received successfully"}
```

## Advanced: Use Improved Script

Replace your old script with `rpi_sender_improved.py` which includes:
- Automatic connectivity testing
- Retry logic (3 attempts)
- Better error messages
- Detailed diagnostics
- Statistics tracking

Just update this line:
```python
SERVER_IP = "192.168.1.100"  # Your ACTUAL IP from ipconfig
```

Then run it - it will test connectivity first and tell you exactly what's wrong!
