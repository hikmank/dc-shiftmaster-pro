"""WebSocket broadcast module for real-time coverage event notifications.

Maintains a thread-safe set of connected WebSocket clients and provides
functions to add, remove, and broadcast messages to all connected clients.
"""

import json
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Thread-safe set of active WebSocket connections
_clients: set = set()
_clients_lock = threading.Lock()


def add_client(ws) -> None:
    """Add a WebSocket connection to the connected client set."""
    with _clients_lock:
        _clients.add(ws)
    logger.info("WebSocket client added. Total clients: %d", len(_clients))


def remove_client(ws) -> None:
    """Remove a WebSocket connection from the connected client set."""
    with _clients_lock:
        _clients.discard(ws)
    logger.info("WebSocket client removed. Total clients: %d", len(_clients))


def broadcast_coverage_event(event_type: str, request_id: int) -> None:
    """Broadcast a coverage event to all connected WebSocket clients.

    Builds a JSON message containing the event type, request ID, and an
    ISO-8601 timestamp, then sends it to every client in the set. Any
    client that raises an exception on send is removed from the set.

    Args:
        event_type: The type of coverage event (created, claimed, unclaimed, cancelled).
        request_id: The ID of the coverage request that triggered the event.
    """
    message = json.dumps({
        "event": event_type,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    with _clients_lock:
        clients_snapshot = set(_clients)

    dead_clients = []
    for client in clients_snapshot:
        try:
            client.send(message)
        except Exception:
            logger.warning("Failed to send to WebSocket client; removing.")
            dead_clients.append(client)

    if dead_clients:
        with _clients_lock:
            for client in dead_clients:
                _clients.discard(client)
