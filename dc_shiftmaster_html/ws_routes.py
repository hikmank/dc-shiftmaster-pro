"""WebSocket route definitions for real-time coverage notifications.

Provides an ``init_websocket_routes`` function that registers the
``/ws/coverage`` WebSocket endpoint on a ``flask_sock.Sock`` instance.
"""

import logging

from dc_shiftmaster_html.broadcast import add_client, remove_client

logger = logging.getLogger(__name__)


def init_websocket_routes(sock):
    """Register WebSocket routes on the given Sock instance.

    Args:
        sock: A ``flask_sock.Sock`` instance bound to the Flask app.
    """

    @sock.route("/ws/coverage")
    def coverage_ws(ws):
        """Handle a WebSocket connection for coverage event notifications.

        Adds the client on connect, keeps the connection alive by
        continuously reading from the socket, and removes the client
        when the connection closes or errors.
        """
        add_client(ws)
        try:
            while True:
                # Block until the client sends data or disconnects.
                # We don't process incoming messages — this loop just
                # keeps the connection alive.
                data = ws.receive()
                if data is None:
                    # Client closed the connection gracefully.
                    break
        except Exception:
            logger.debug("WebSocket connection closed or errored.")
        finally:
            remove_client(ws)
