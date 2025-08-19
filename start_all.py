#!/usr/bin/env python3
"""
Unified starter for the Options Trading application.

Responsibilities:
- Verify environment and database connectivity
- Ensure tables exist
- Start FastAPI backend
- Start/stop Zerodha WebSocket automatically during market hours (IST)

Usage:
  python start_all.py

Notes:
- Reads trade symbols from `user_config.txt` inside `Kite_WebSocket.py` logic
- WebSocket runs once for all users; backend only reads from DB
"""

from __future__ import annotations

import os
import sys
import time
import threading
import subprocess
import requests
from datetime import datetime
from typing import Optional

import psycopg2
import pytz



from dotenv import load_dotenv
load_dotenv()

# Ensure project root on sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Lazy import of app internals
def _import_app_bits():
    from app.database import Base, engine  # type: ignore
    return Base, engine

def _backend_ws_status() -> bool:
    try:
        resp = requests.get("http://127.0.0.1:8000/websocket/status/public", timeout=3)
        data = resp.json() if resp.ok else {}
        return bool(data.get("running", False))
    except Exception:
        return False


def _backend_ws_start() -> bool:
    try:
        resp = requests.post("http://127.0.0.1:8000/websocket/start", timeout=5)
        return resp.ok
    except Exception:
        return False


def _backend_ws_stop() -> bool:
    try:
        resp = requests.post("http://127.0.0.1:8000/websocket/stop", timeout=5)
        return resp.ok
    except Exception:
        return False


# —— Configuration ——————————————————————————————————————————————————————
IST = pytz.timezone("Asia/Kolkata")
MARKET_START_HH_MM = (9, 15)   # 9:15 AM IST
MARKET_STOP_HH_MM = (15, 31)   # 3:31 PM IST


# —— Health checks and setup —————————————————————————————————————————————
def check_database_connection() -> bool:
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            port=os.getenv("PGPORT", "5432"),
            dbname=os.getenv("PGDATABASE", "database_name"),
            user=os.getenv("PGUSER", "username"),
            password=os.getenv("PGPASSWORD", "password"),
        )
        conn.close()
        print("✅ Database connection successful")
        return True
    except Exception as exc:
        print(f"❌ Database connection failed: {exc}")
        print("   Ensure PostgreSQL is running and credentials are correct")
        return False


def create_tables() -> bool:
    try:
        Base, engine = _import_app_bits()
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified")
        return True
    except Exception as exc:
        print(f"❌ Failed to create tables: {exc}")
        return False


# —— Backend (FastAPI) ————————————————————————————————————————————————
def start_backend_process() -> subprocess.Popen:
    print("🚀 Starting FastAPI backend on http://localhost:8000 …")
    # Use uvicorn as a child process for isolation/reload support
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.api:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
        "--log-level",
        "info",
    ]
    return subprocess.Popen(cmd, cwd=ROOT_DIR)


# —— Market-hours WebSocket controller ———————————————————————————————
def is_market_hours(now_ist: Optional[datetime] = None) -> bool:
    now = now_ist or datetime.now(IST)
    if now.weekday() >= 5:  # 5,6 => Sat/Sun
        return False
    start = now.replace(hour=MARKET_START_HH_MM[0], minute=MARKET_START_HH_MM[1], second=0, microsecond=0)
    stop = now.replace(hour=MARKET_STOP_HH_MM[0], minute=MARKET_STOP_HH_MM[1], second=0, microsecond=0)
    return start <= now <= stop


def websocket_controller_loop(stop_event: threading.Event) -> None:
    print("📡 WebSocket controller running (auto start/stop during market hours)…")
    last_state: Optional[bool] = None
    while not stop_event.is_set():
        try:
            running = _backend_ws_status()

            in_hours = is_market_hours()

            # Log on state changes only
            if last_state is None or last_state != (in_hours and True):
                now_s = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z")
                print(f"🕘 {now_s} | Market hours: {in_hours} | WS running: {running}")
                last_state = in_hours and True

            if in_hours and not running:
                print("▶️  Starting WebSocket service…")
                try:
                    _backend_ws_start()
                    print("✅ WebSocket started")
                except Exception as exc:
                    print(f"❌ Failed to start WebSocket: {exc}")

            if not in_hours and running:
                print("⏹️  Stopping WebSocket service…")
                try:
                    _backend_ws_stop()
                    print("✅ WebSocket stopped")
                except Exception as exc:
                    print(f"❌ Failed to stop WebSocket: {exc}")

        except Exception as exc:
            print(f"❌ Controller error: {exc}")

        # Sleep with stop-event awareness
        for _ in range(60):
            if stop_event.is_set():
                break
            time.sleep(1)


# —— Main ——————————————————————————————————————————————————————————————
def main() -> int:
    print("🎯 Starting Options Trading application")
    print("=" * 60)
    print(f"📍 Working directory: {ROOT_DIR}")
    print(f"🕘 Time (IST): {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')}")

    if not check_database_connection():
        return 1
    if not create_tables():
        return 1

    # Start backend server
    backend_proc = start_backend_process()

    # Start WS controller loop
    stop_event = threading.Event()
    controller_thread = threading.Thread(target=websocket_controller_loop, args=(stop_event,), daemon=True)
    controller_thread.start()

    print("✅ Startup complete. Press Ctrl+C to stop.")

    try:
        # Wait for backend to exit
        backend_proc.wait()
        return backend_proc.returncode or 0
    except KeyboardInterrupt:
        print("\n🛑 Shutting down…")
        stop_event.set()
        try:
            # Best-effort stop of WebSocket via backend API
            _backend_ws_stop()
        except Exception:
            pass
        try:
            backend_proc.terminate()
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())


