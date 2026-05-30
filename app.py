from fastapi import FastAPI
from fastapi import WebSocket
from fastapi import Request, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
import asyncio
import logging
import time
import socket
import platform
import sqlite3
import os
import secrets

# =========================================
# LOGGING SETUP
# =========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# =========================================
# TEMPLATE
# =========================================

templates = Jinja2Templates(
    directory="templates"
)

# =========================================
# STATIC FILES
# =========================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# =========================================
# DATA MODELS
# =========================================

class HeartRatePayload(BaseModel):
    heart_rate: int
    device_id: str
    protocol: str = None
    timestamp: float = None


class CustomerPayload(BaseModel):
    device_id: str
    customer_name: str
    pt_name: str
    phone_number: str | None = None
    gender: str | None = None
    weight_kg: float | None = None
    birthday: str | None = None

# =========================================
# GLOBAL DATA
# =========================================

# Store data for multiple devices
devices_data = {}  # Format: {device_id: {heart_rate, timestamp, received_at}}
latest_data = {}

connection_status = {
    "connected": False,
    "last_received": None,
    "last_error": None,
    "error_count": 0,
    "total_messages": 0,
    "timeout_threshold": 10  # seconds
}

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "app.db"))
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "30"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(24*3600)))
sessions = {}  # In-memory session store: {token: {created, expires}}

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def generate_session_token():
    return secrets.token_urlsafe(32)


def verify_token(token: str) -> bool:
    # verify presence and expiry
    if token not in sessions:
        return False
    meta = sessions.get(token)
    expires = meta.get("expires")
    if expires and time.time() > expires:
        # expired - remove
        try:
            del sessions[token]
        except KeyError:
            pass
        return False
    return True


def require_auth(request: Request):
    """Raise 401 if request has no valid bearer token or token query param."""
    # check Authorization header first
    auth = request.headers.get("authorization")
    token = None
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1].strip()
    # fallback to query param
    if not token:
        token = request.query_params.get("token")

    if not token or not verify_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

# =========================================
# DATABASE HELPERS
# =========================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                pt_name TEXT NOT NULL,
                device_id TEXT NOT NULL UNIQUE,
                phone_number TEXT,
                gender TEXT,
                weight_kg REAL,
                birthday TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS heart_rate_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                heart_rate INTEGER NOT NULL,
                protocol TEXT NOT NULL,
                timestamp REAL NOT NULL,
                received_at TEXT NOT NULL,
                beat_count INTEGER,
                beat_time TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )
            """
        )
        conn.commit()

    # Ensure phone_number column exists for customers (migration)
    with get_db_connection() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(customers)").fetchall()]
        if 'phone_number' not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN phone_number TEXT")
            conn.commit()
        # Add new columns for customer profile if missing
        if 'gender' not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN gender TEXT")
            conn.commit()
        if 'weight_kg' not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN weight_kg REAL")
            conn.commit()
        if 'birthday' not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN birthday TEXT")
            conn.commit()
            # if an older age column exists, use it to seed a rough birthday value
            if 'age' in cols:
                rows = conn.execute("SELECT id, age FROM customers WHERE age IS NOT NULL").fetchall()
                for row in rows:
                    try:
                        birth_year = datetime.now().year - int(row['age'])
                        birthday_value = f"{birth_year}-01-01"
                        conn.execute(
                            "UPDATE customers SET birthday = ? WHERE id = ?",
                            (birthday_value, row['id'])
                        )
                    except Exception:
                        continue
                conn.commit()


init_db()


def cleanup_old_records():
    cutoff = time.time() - DATA_RETENTION_DAYS * 86400
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM heart_rate_records WHERE timestamp < ?",
            (cutoff,)
        )
        conn.commit()


def ensure_customer(device_id: str, customer_name: str, pt_name: str) -> int:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, customer_name, pt_name FROM customers WHERE device_id = ?",
            (device_id,)
        ).fetchone()

        now = datetime.now().isoformat()
        if row:
            if row["customer_name"] != customer_name or row["pt_name"] != pt_name:
                conn.execute(
                    "UPDATE customers SET customer_name = ?, pt_name = ?, updated_at = ? WHERE id = ?",
                    (customer_name, pt_name, now, row["id"])
                )
                conn.commit()
            return row["id"]

        cursor = conn.execute(
            "INSERT INTO customers (customer_name, pt_name, device_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (customer_name, pt_name, device_id, now, now)
        )
        conn.commit()
        return cursor.lastrowid

# =========================================
# HELPER FUNCTIONS
# =========================================

def check_connection_timeout():
    """Check if connection timed out"""
    if connection_status["last_received"] is None:
        return False
    
    elapsed = time.time() - connection_status["last_received"]
    if elapsed > connection_status["timeout_threshold"]:
        connection_status["connected"] = False
        return True
    return False

# =========================================
# HOME PAGE
# =========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

    # jinja2 TemplateResponse expects (template_name, context)
    return templates.TemplateResponse("index.html", {"request": request})

# =========================================
# API RECEIVE FROM RASPBERRY PI
# =========================================

@app.post("/api/heart-rate")
async def receive_data(payload: dict):
    """
    Receive heart rate data from Raspberry Pi
    """
    global latest_data, devices_data
    
    try:
        # Validate payload has required fields
        if "heart_rate" not in payload:
            error_msg = "Missing required field: heart_rate"
            logger.warning(error_msg)
            connection_status["last_error"] = error_msg
            connection_status["error_count"] += 1
            return {
                "status": "error",
                "message": error_msg
            }
        
        if "device_id" not in payload:
            error_msg = "Missing required field: device_id"
            logger.warning(error_msg)
            connection_status["last_error"] = error_msg
            connection_status["error_count"] += 1
            return {
                "status": "error",
                "message": error_msg
            }
        
        # Validate heart rate is a reasonable number
        heart_rate = payload.get("heart_rate")
        if not isinstance(heart_rate, (int, float)) or heart_rate < 0 or heart_rate > 300:
            error_msg = f"Invalid heart rate value: {heart_rate}. Expected 0-300 BPM"
            logger.warning(error_msg)
            connection_status["last_error"] = error_msg
            connection_status["error_count"] += 1
            return {
                "status": "error",
                "message": error_msg
            }
        
        device_id = payload.get("device_id")
        # Validate protocol
        protocol = payload.get("protocol")
        if protocol is None:
            error_msg = "Missing required field: protocol"
            logger.warning(error_msg)
            connection_status["last_error"] = error_msg
            connection_status["error_count"] += 1
            return {
                "status": "error",
                "message": error_msg
            }

        # Accept common protocols (BLE and ANT+)
        if protocol not in ("BLE", "ANT+"):
            error_msg = f"Unsupported protocol: {protocol}. Expected 'BLE' or 'ANT+'"
            logger.warning(error_msg)
            connection_status["last_error"] = error_msg
            connection_status["error_count"] += 1
            return {
                "status": "error",
                "message": error_msg
            }

        cleanup_old_records()

        with get_db_connection() as conn:
            mapping = conn.execute(
                "SELECT id, customer_name, pt_name FROM customers WHERE device_id = ?",
                (device_id,)
            ).fetchone()

            if not mapping:
                error_msg = (
                    "Device ID not registered. Add the customer/PT mapping first via /api/customers "
                    "before sending heart rate data."
                )
                logger.warning(error_msg)
                connection_status["last_error"] = error_msg
                connection_status["error_count"] += 1
                return {
                    "status": "error",
                    "message": error_msg
                }

            customer_id = mapping["id"]
            customer = mapping["customer_name"]
            pt_name = mapping["pt_name"]

        # Update device data
        device_data = {
            "device_id": device_id,
            "heart_rate": heart_rate,
            "protocol": protocol,
            "customer": customer,
            "pt_name": pt_name,
            "customer_id": customer_id,
            "beat_count": payload.get("beat_count"),
            "beat_time": payload.get("beat_time"),
            "timestamp": payload.get("timestamp", time.time()),
            "received_at": datetime.now().isoformat()
        }

        # Persist the record in SQLite
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO heart_rate_records (customer_id, device_id, heart_rate, protocol, timestamp, received_at, beat_count, beat_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    customer_id,
                    device_id,
                    heart_rate,
                    protocol,
                    device_data["timestamp"],
                    device_data["received_at"],
                    device_data["beat_count"],
                    device_data["beat_time"]
                )
            )
            conn.commit()
        
        devices_data[str(device_id)] = device_data
        latest_data = device_data  # Keep for backward compatibility
        
        # Update connection status
        connection_status["last_received"] = time.time()
        connection_status["connected"] = True
        connection_status["total_messages"] += 1
        connection_status["last_error"] = None
        
        logger.info(f"✓ Received heart rate: {heart_rate} BPM from device {device_id} (Total devices: {len(devices_data)})")
        
        return {
            "status": "ok",
            "message": "Data received successfully",
            "total_devices": len(devices_data)
        }
    
    except ValueError as e:
        error_msg = f"Value error: {str(e)}"
        logger.error(error_msg)
        connection_status["last_error"] = error_msg
        connection_status["error_count"] += 1
        connection_status["connected"] = False
        return {
            "status": "error",
            "message": error_msg
        }
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        connection_status["last_error"] = error_msg
        connection_status["error_count"] += 1
        connection_status["connected"] = False
        return {
            "status": "error",
            "message": error_msg
        }

# =========================================
# STATUS ENDPOINT
# =========================================

@app.get("/api/status")
async def get_status():
    """
    Get connection status and diagnostics
    """
    check_connection_timeout()
    
    return {
        "connected": connection_status["connected"],
        "last_received": connection_status["last_received"],
        "last_error": connection_status["last_error"],
        "error_count": connection_status["error_count"],
        "total_messages": connection_status["total_messages"],
        "total_devices": len(devices_data),
        "current_time": time.time(),
        "devices": list(devices_data.values())
    }

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, token: str = None):
    """
    Admin dashboard page (requires login token in query param).
    """
    if not token or not verify_token(token):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("admin.html", {"request": request, "token": token})


@app.get("/api/export-db")
async def export_database(request: Request):
    """Download the current SQLite database file.

    This endpoint requires admin auth via Bearer token or token query parameter.
    """
    require_auth(request)

    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database file not found")

    return FileResponse(
        DB_PATH,
        media_type="application/x-sqlite3",
        filename=os.path.basename(DB_PATH),
        headers={"Content-Disposition": f'attachment; filename="{os.path.basename(DB_PATH)}"'}
    )


@app.post("/api/login")
async def login(payload: dict):
    """
    Authenticate with admin password and return a session token.
    """
    password = payload.get("password")
    if not password or password != ADMIN_PASSWORD:
        return {"status": "error", "message": "Invalid password"}

    token = generate_session_token()
    now = time.time()
    sessions[token] = {"created": now, "expires": now + SESSION_TTL_SECONDS}
    return {"status": "ok", "token": token}


@app.post("/api/logout")
async def logout(payload: dict = None, request: Request = None):
    """Invalidate a session token. Accepts JSON {token} or Authorization header."""
    token = None
    if payload and isinstance(payload, dict):
        token = payload.get("token")
    # check header
    if not token and request is not None:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1].strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing token")

    if token in sessions:
        del sessions[token]
    return {"status": "ok", "message": "Logged out"}


@app.get("/api/records")
async def get_records(customer_id: int = None, date: str = None, request: Request = None):
    """
    Retrieve stored heart rate records from the database.
    Optional query params: customer_id, date
    """
    query = [
        "SELECT r.id, r.customer_id, c.customer_name AS customer, c.pt_name,",
        "  r.device_id, r.heart_rate, r.protocol, r.timestamp, r.received_at,",
        "  r.beat_count, r.beat_time",
        "FROM heart_rate_records r",
        "JOIN customers c ON c.id = r.customer_id"
    ]
    params = []

    if customer_id is not None:
        query.append("WHERE r.customer_id = ?")
        params.append(customer_id)

    if date:
        condition = "r.received_at LIKE ?"
        if customer_id is not None:
            query.append(f"AND {condition}")
        else:
            query.append(f"WHERE {condition}")
        params.append(f"{date}%")

    query.append("ORDER BY r.timestamp DESC")

    # require admin auth for records endpoint
    if request is not None:
        require_auth(request)

    with get_db_connection() as conn:
        rows = conn.execute(" ".join(query), tuple(params)).fetchall()
        return [dict(row) for row in rows]


def _compute_sessions_from_timestamps(timestamps, gap_seconds=30*60):
    """Given a list of timestamps (ascending), return list of (start, end, duration_seconds)."""
    if not timestamps:
        return []
    sessions = []
    start = timestamps[0]
    last = timestamps[0]
    for t in timestamps[1:]:
        if t - last > gap_seconds:
            sessions.append((start, last, last - start))
            start = t
        last = t
    sessions.append((start, last, last - start))
    return sessions


@app.get("/api/customers/{customer_id}/stats")
async def customer_stats(customer_id: int, start_date: str = None, end_date: str = None, request: Request = None):
    """Return visit/session stats for a customer between optional start_date and end_date (YYYY-MM-DD).

    Sessions are clusters of heart rate records separated by >30 minutes.
    """
    require_auth(request)

    # determine time window
    now = datetime.now()
    if start_date:
        start_ts = time.mktime(datetime.strptime(start_date, "%Y-%m-%d").timetuple())
    else:
        # default to last 30 days
        start_ts = time.time() - 30 * 86400

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # include entire day
        end_ts = time.mktime((end_dt.replace(hour=23, minute=59, second=59)).timetuple())
    else:
        end_ts = time.time()

    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT timestamp FROM heart_rate_records WHERE customer_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC",
            (customer_id, start_ts, end_ts)
        ).fetchall()
        timestamps = [r["timestamp"] for r in rows]

        sessions = _compute_sessions_from_timestamps(timestamps)

        total_seconds = sum(s[2] for s in sessions)
        total_hours = round(total_seconds / 3600, 2)

        # period of day buckets
        buckets = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
        for s in sessions:
            start_hour = datetime.fromtimestamp(s[0]).hour
            if 5 <= start_hour < 12:
                buckets["morning"] += 1
            elif 12 <= start_hour < 17:
                buckets["afternoon"] += 1
            elif 17 <= start_hour < 22:
                buckets["evening"] += 1
            else:
                buckets["night"] += 1

        # visits count
        visits_count = len(sessions)

        # include session details (convert to ISO)
        session_details = []
        for s in sessions:
            session_details.append({
                "start": datetime.fromtimestamp(s[0]).isoformat(),
                "end": datetime.fromtimestamp(s[1]).isoformat(),
                "duration_seconds": s[2]
            })

        # visits by period (month/week/year) - produce simple monthly counts between range
        visits_by_month = {}
        for s in sessions:
            m = datetime.fromtimestamp(s[0]).strftime("%Y-%m")
            visits_by_month[m] = visits_by_month.get(m, 0) + 1

        return {
            "customer_id": customer_id,
            "period_start": datetime.fromtimestamp(start_ts).isoformat(),
            "period_end": datetime.fromtimestamp(end_ts).isoformat(),
            "visits_count": visits_count,
            "total_hours": total_hours,
            "sessions": session_details,
            "period_of_day": buckets,
            "visits_by_month": visits_by_month
        }


@app.post("/api/customers")
async def add_or_update_customer(payload: CustomerPayload, request: Request):
    """
    Add or update a customer / device mapping.
    """
    # require auth
    require_auth(request)

    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM customers WHERE device_id = ?",
            (payload.device_id,)
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE customers SET customer_name = ?, pt_name = ?, phone_number = ?, gender = ?, weight_kg = ?, birthday = ?, updated_at = ? WHERE id = ?",
                (payload.customer_name, payload.pt_name, payload.phone_number, payload.gender, payload.weight_kg, payload.birthday, now, row["id"]) 
            )
            conn.commit()
            return {"status": "ok", "message": "Customer mapping updated."}

        conn.execute(
            "INSERT INTO customers (customer_name, pt_name, device_id, phone_number, gender, weight_kg, birthday, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (payload.customer_name, payload.pt_name, payload.device_id, payload.phone_number, payload.gender, payload.weight_kg, payload.birthday, now, now)
        )
        conn.commit()
        return {"status": "ok", "message": "Customer mapping created."}


@app.get("/api/customers")
async def get_customers(request: Request):
    """
    Retrieve customer and device mappings.
    """
    require_auth(request)

    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, customer_name AS customer, pt_name, device_id, phone_number, gender, weight_kg, birthday, created_at, updated_at FROM customers ORDER BY customer_name"
        ).fetchall()
        return [dict(row) for row in rows]

# =========================================
# DIAGNOSTICS ENDPOINT
# =========================================

def get_local_ips():
    """Get all local IP addresses"""
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        return ips
    except:
        return []

@app.get("/api/diagnostics")
async def get_diagnostics(request: Request):
    """
    Server diagnostics - helps identify network/connection issues
    """
    # diagnostics contain internal info; require admin auth
    # This endpoint is protected to avoid leaking internals
    # The Request object is available via dependency injection
    # Use require_auth with a dummy Request by reading headers if called via web UI
    # FastAPI will inject Request if provided in params; add it now
    # require admin auth to access diagnostics
    require_auth(request)
    check_connection_timeout()
    
    local_ips = get_local_ips()
    
    return {
        "server_info": {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "local_ips": local_ips,
            "port": 8000,
            "running": True
        },
        "connection_status": {
            "connected": connection_status["connected"],
            "last_received": connection_status["last_received"],
            "timeout_threshold": connection_status["timeout_threshold"],
            "time_since_last_message": None if connection_status["last_received"] is None else time.time() - connection_status["last_received"]
        },
        "statistics": {
            "total_messages": connection_status["total_messages"],
            "total_errors": connection_status["error_count"],
            "latest_data": latest_data
        },
        "troubleshooting": {
            "message": "If Raspberry Pi can't connect, use one of the local_ips above instead of 192.168.1.77",
            "test_command": f"curl http://{local_ips[0] if local_ips else 'SERVER_IP'}:8000/",
            "last_error": connection_status["last_error"]
        }
    }

# =========================================
# WEBSOCKET
# =========================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()
    
    logger.info("WebSocket client connected")

    try:

        while True:
            
            # Check for timeout
            check_connection_timeout()
            
            # Prepare data to send - all devices
            ws_data = {
                "devices": list(devices_data.values()),
                "total_devices": len(devices_data),
                "connection_status": connection_status["connected"],
                "last_error": connection_status["last_error"],
                "total_messages": connection_status["total_messages"],
                "error_count": connection_status["error_count"]
            }

            try:
                await websocket.send_json(ws_data)
            except Exception as send_error:
                logger.debug(f"WebSocket send error: {send_error}")
                break

            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        logger.info("WebSocket client disconnected")