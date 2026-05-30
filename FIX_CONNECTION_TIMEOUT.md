# Connection Still Failing? Here's Why and How to Fix It

## The Problem

Even though diagnostics say "ready", Raspberry Pi still gets **connection timeout to 192.168.1.77**.

**Root cause**: **192.168.1.77 is the WRONG IP address for your server**

---

## Step 1: Find Your REAL Server IP

### On Windows (Your Server Machine)

Open **PowerShell** and run:
```powershell
ipconfig
```

Look for output like:
```
Ethernet adapter Ethernet:
   Connection-specific DNS Suffix: 
   IPv4 Address. . . . . . . . . . : 192.168.1.100 ← USE THIS
   Subnet Mask . . . . . . . . . . : 255.255.255.0
```

**Copy the IPv4 Address** (e.g., `192.168.1.100`)

---

## Step 2: Verify from Raspberry Pi

SSH into Raspberry Pi and run:
```bash
ping 192.168.1.100
```

**Expected output:**
```
PING 192.168.1.100 (192.168.1.100): 56 data bytes
64 bytes from 192.168.1.100: seq=0 ttl=64 time=5.123 ms
```

**If you see "timeout" or "unreachable":**
- ❌ Wrong network or firewall blocking
- Check if both devices on same WiFi

---

## Step 3: Test with curl

From Raspberry Pi:
```bash
curl http://192.168.1.100:8000/
```

**Should return HTML page of your dashboard**

If not:
- ❌ Server not running
- ❌ Wrong IP  
- ❌ Firewall blocking port 8000

---

## Step 4: Update Your Script

### Option A: Use the new fixed script (RECOMMENDED)

```bash
# Copy the fixed script to Raspberry Pi
scp rpi_sender_fixed.py pi@raspberry:/home/pi/

# Then edit it:
nano /home/pi/rpi_sender_fixed.py
```

**Change this line (around line 13):**
```python
SERVER_IP = "192.168.1.77"  # ← WRONG
```

**To your actual IP:**
```python
SERVER_IP = "192.168.1.100"  # ← Correct (from ipconfig)
```

**Save and run:**
```bash
python3 rpi_sender_fixed.py
```

It will:
- ✓ Run diagnostics first
- ✓ Show exactly what's working/failing
- ✓ Retry 3 times on failure
- ✓ Use 10-second timeout (not 3)
- ✓ Log everything to `/home/pi/heart_rate.log`

### Option B: Quick fix your current script

Just change one line:
```python
API_URL = "http://192.168.1.77:8000/api/heart-rate"  # ← OLD
```

To:
```python
API_URL = "http://192.168.1.100:8000/api/heart-rate"  # ← NEW
```

---

## Why Diagnostics Passed But Script Failed

The diagnostics script might:
1. Have run on your local server machine (not Raspberry Pi)
2. Not actually test full network path
3. Test different network interfaces

The actual sender script fails because **192.168.1.77 doesn't exist** on your network.

---

## Windows Firewall Check

If you updated IP but still get errors:

1. Search **"Windows Defender Firewall"** in Start menu
2. Click **"Allow an app through firewall"**
3. Click **"Change settings"**
4. Click **"Allow another app..."**
5. Find **Python.exe** → Click it
6. Make sure ✓ **Private** and ✓ **Public** are checked
7. Click OK

**OR in PowerShell (as Admin):**
```powershell
New-NetFirewallRule -DisplayName "Allow FastAPI 8000" `
    -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

---

## Server Check

Make sure server is running:
```bash
# On Windows server machine:
cd D:\smartgym
uvicorn app:app --host 0.0.0.0 --port 8000
```

You should see:
```
Uvicorn running on http://0.0.0.0:8000
```

---

## Quick Checklist

- [ ] Ran `ipconfig` and got IPv4 address (e.g., 192.168.1.100)
- [ ] Updated `SERVER_IP` to correct IP in script
- [ ] Ran `ping 192.168.1.100` from Raspberry Pi - SUCCESS
- [ ] Ran `curl http://192.168.1.100:8000/` - Got HTML response
- [ ] Windows Firewall allows port 8000
- [ ] FastAPI server running on Windows machine
- [ ] Restarted Raspberry Pi script with new IP
- [ ] Monitor log file: `/home/pi/heart_rate.log`

---

## If Still Not Working

1. **Check server machine IP didn't change:**
   ```powershell
   ipconfig
   ```

2. **Verify you're on same network:**
   - Both should be on same WiFi SSID
   - Run `ipconfig` on Windows - should see device on same subnet

3. **Test from Windows:**
   ```powershell
   # Test from your Windows server machine:
   curl http://192.168.1.100:8000/api/status
   ```
   Should return JSON response

4. **Check logs:**
   On Raspberry Pi:
   ```bash
   cat /home/pi/heart_rate.log
   ```

5. **Get network diagnostics on Raspberry Pi:**
   ```bash
   python3 diagnose_network.py
   # Enter your IP when prompted
   ```

---

## Last Resort: Use Improved Script

The `rpi_sender_fixed.py` includes:
- Built-in diagnostics that run FIRST
- Proper timeout (10 seconds instead of 3)
- Retry logic (3 attempts with backoff)
- Detailed logging to file
- Better error messages

Just update the IP and use this instead!
