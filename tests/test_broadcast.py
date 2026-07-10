"""Unit tests for dc_shiftmaster_html.broadcast — WebSocket broadcast module."""

import json

import pytest

from dc_shiftmaster_html.broadcast import (
    _clients,
    add_client,
    broadcast_coverage_event,
    remove_client,
)


class _MockWebSocket:
    """Minimal mock WebSocket with a send method that records messages."""

    def __init__(self, *, should_fail=False):
        self.sent: list[str] = []
        self.should_fail = should_fail

    def send(self, message: str) -> None:
        if self.should_fail:
            raise ConnectionError("mock send failure")
        self.sent.append(message)


@pytest.fixture(autouse=True)
def _clear_clients():
    """Ensure the module-level _clients set is empty before and after each test."""
    _clients.clear()
    yield
    _clients.clear()


# ---------------------------------------------------------------------------
# add_client / remove_client
# ---------------------------------------------------------------------------


class TestAddRemoveClient:
    def test_add_client_adds_to_set(self):
        ws = _MockWebSocket()
        add_client(ws)
        assert ws in _clients

    def test_add_multiple_clients(self):
        ws1 = _MockWebSocket()
        ws2 = _MockWebSocket()
        add_client(ws1)
        add_client(ws2)
        assert len(_clients) == 2

    def test_remove_client_removes_from_set(self):
        ws = _MockWebSocket()
        add_client(ws)
        remove_client(ws)
        assert ws not in _clients

    def test_remove_nonexistent_client_is_safe(self):
        ws = _MockWebSocket()
        # Should not raise — uses discard internally
        remove_client(ws)
        assert len(_clients) == 0


# ---------------------------------------------------------------------------
# broadcast_coverage_event
# ---------------------------------------------------------------------------


class TestBroadcastCoverageEvent:
    def test_sends_json_to_all_clients(self):
        ws1 = _MockWebSocket()
        ws2 = _MockWebSocket()
        add_client(ws1)
        add_client(ws2)

        broadcast_coverage_event("created", 42)

        for ws in (ws1, ws2):
            assert len(ws.sent) == 1
            payload = json.loads(ws.sent[0])
            assert payload["event"] == "created"
            assert payload["request_id"] == 42
            assert "timestamp" in payload

    def test_message_contains_required_fields(self):
        ws = _MockWebSocket()
        add_client(ws)

        broadcast_coverage_event("claimed", 7)

        payload = json.loads(ws.sent[0])
        assert set(payload.keys()) == {"event", "request_id", "timestamp"}

    def test_failing_client_is_removed(self):
        good_ws = _MockWebSocket()
        bad_ws = _MockWebSocket(should_fail=True)
        add_client(good_ws)
        add_client(bad_ws)

        broadcast_coverage_event("unclaimed", 99)

        # The good client received the message
        assert len(good_ws.sent) == 1
        # The bad client was removed from the set
        assert bad_ws not in _clients
        # The good client is still in the set
        assert good_ws in _clients

    def test_no_clients_does_not_raise(self):
        # Should be a no-op when no clients are connected
        broadcast_coverage_event("cancelled", 1)
