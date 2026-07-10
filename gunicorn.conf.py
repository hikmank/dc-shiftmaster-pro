"""Gunicorn configuration for DC-ShiftMaster Pro.

Reads bind address from SHIFTMASTER_HOST / SHIFTMASTER_PORT env vars.
Uses gevent workers to support long-lived WebSocket connections.
"""

import multiprocessing
import os

# --- Bind ---
_host = os.environ.get("SHIFTMASTER_HOST", "0.0.0.0")
_port = os.environ.get("SHIFTMASTER_PORT", "5000")
bind = f"{_host}:{_port}"

# --- Worker class (gevent for WebSocket support) ---
worker_class = "gevent"

# --- Worker count: 2–4× CPU cores is a good starting point ---
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# --- Timeouts ---
timeout = 120  # higher than default to accommodate WebSocket upgrades
graceful_timeout = 30

# --- Logging ---
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# --- WSGI app entry point ---
wsgi_app = "dc_shiftmaster_html.server:create_app()"
