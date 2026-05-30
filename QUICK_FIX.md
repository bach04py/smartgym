# QUICK FIX - Connection Timeout Issue

## The Problem
```
API ERROR: Connection to 192.168.1.77 timed out (connect timeout=3)
```

This means Raspberry Pi **cannot reach** your server at that IP.

## The Solution - 3 Steps

### Step 1️⃣: Find Your Server's Real IP

**On your Windows server machine, open PowerShell and run:**
```powershell
ipconfig
```

Look for **IPv4 Address** under your active network. Example:
```
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . : 192.168.1.100  ← THIS IS YOUR IP
```

### Step 2️⃣: Verify Connectivity (From Raspberry Pi)

```bash
ping 192.168.1.100
```

If you see responses → Your IP is correct ✓
If you see "timeout" → Try a different approach (see troubleshooting)

### Step 3️⃣: Update the Script

**Replace this line in your Raspberry Pi script:**
```python
SERVER_IP = "192.168.1.77"  # ← OLD (not working)
```

**With your actual IP:**
```python
SERVER_IP = "192.168.1.100"  # ← NEW (from ipconfig)
```

Then restart your script!

---

## If Still Not Working

### Check Server is Running
```bash
# On Windows server:
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Check Firewall (Windows)
1. Search for "Windows Defender Firewall"
2. Click "Allow an app through firewall"
3. Find **Python** in the list
4. ✓ Check both "Private" and "Public"
5. Click OK

### Get Server Diagnostics
Access from any browser:
```
http://192.168.1.100:8000/api/diagnostics
```

This shows your actual IP addresses!

---

## Use the Improved Script

Copy your Raspberry Pi code to `rpi_sender_improved.py` which includes:
- ✓ Automatic IP validation
- ✓ Retry logic (tries 3 times before failing)
- ✓ Better error messages
- ✓ Connection testing before start

Just update the IP and it will diagnose the problem!

---

## Network Checklist

- [ ] Server and Raspberry Pi on **same WiFi network**
- [ ] Found correct IP from `ipconfig`
- [ ] Pinged from Raspberry Pi successfully
- [ ] Windows Defender allows port 8000
- [ ] FastAPI server running on `0.0.0.0:8000`
- [ ] Updated script with correct IP
- [ ] Restarted Raspberry Pi script

## Still Need Help?

Read full guide: `NETWORK_TROUBLESHOOTING.md`
