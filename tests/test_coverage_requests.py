"""Unit tests for coverage request CRUD methods on DatabaseManager."""

import pytest

from dc_shiftmaster.models import CoverageRequest


class TestCreateCoverageRequest:
    """Tests for create_coverage_request."""

    def test_create_returns_id(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        req_id = db.create_coverage_request(uid, "2025-03-15", "day", "Need off")
        assert isinstance(req_id, int)
        assert req_id > 0

    def test_create_stores_fields(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        req_id = db.create_coverage_request(uid, "2025-03-15", "night", "PTO")
        reqs = db.get_coverage_requests()
        assert len(reqs) == 1
        r = reqs[0]
        assert r.id == req_id
        assert r.requester_id == uid
        assert r.date == "2025-03-15"
        assert r.shift_type == "night"
        assert r.note == "PTO"
        assert r.status == "open"
        assert r.claimer_id is None
        assert r.claimed_at is None

    def test_duplicate_raises_value_error(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        db.create_coverage_request(uid, "2025-03-15", "day")
        with pytest.raises(ValueError, match="already exists"):
            db.create_coverage_request(uid, "2025-03-15", "day")

    def test_duplicate_after_cancel_allowed(self, db):
        """Cancelling a request should allow creating a new one for the same slot."""
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        req_id = db.create_coverage_request(uid, "2025-03-15", "day")
        db.cancel_coverage_request(req_id)
        # Should not raise
        new_id = db.create_coverage_request(uid, "2025-03-15", "day")
        assert new_id != req_id

    def test_different_shift_type_allowed(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        db.create_coverage_request(uid, "2025-03-15", "day")
        req_id2 = db.create_coverage_request(uid, "2025-03-15", "night")
        assert req_id2 > 0

    def test_different_user_same_slot_allowed(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        db.create_coverage_request(uid1, "2025-03-15", "day")
        req_id2 = db.create_coverage_request(uid2, "2025-03-15", "day")
        assert req_id2 > 0


class TestGetCoverageRequests:
    """Tests for get_coverage_requests and get_coverage_requests_for_user."""

    def test_empty_returns_empty(self, db):
        assert db.get_coverage_requests() == []

    def test_filter_by_status(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        db.create_coverage_request(uid, "2025-03-15", "day")
        db.create_coverage_request(uid, "2025-03-16", "day")
        assert len(db.get_coverage_requests(status="open")) == 2
        assert len(db.get_coverage_requests(status="claimed")) == 0
        assert len(db.get_coverage_requests(status="cancelled")) == 0

    def test_get_for_user(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        db.create_coverage_request(uid1, "2025-03-15", "day")
        db.create_coverage_request(uid2, "2025-03-16", "night")
        alice_reqs = db.get_coverage_requests_for_user(uid1)
        assert len(alice_reqs) == 1
        assert alice_reqs[0].requester_id == uid1

    def test_returns_coverage_request_dataclass(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        db.create_coverage_request(uid, "2025-03-15", "day", "note")
        reqs = db.get_coverage_requests()
        assert isinstance(reqs[0], CoverageRequest)


class TestClaimCoverageRequest:
    """Tests for claim_coverage_request."""

    def test_claim_sets_status_and_claimer(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        req_id = db.create_coverage_request(uid1, "2025-03-15", "day")
        db.claim_coverage_request(req_id, uid2)
        reqs = db.get_coverage_requests()
        r = reqs[0]
        assert r.status == "claimed"
        assert r.claimer_id == uid2
        assert r.claimed_at is not None

    def test_claim_creates_override(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        req_id = db.create_coverage_request(uid1, "2025-03-15", "day")
        db.claim_coverage_request(req_id, uid2)
        overrides = db.get_overrides(2025)
        match = [o for o in overrides if o.date == "2025-03-15" and o.shift_type == "day"]
        assert len(match) == 1
        assert match[0].name == "Bob B"

    def test_claim_already_claimed_raises(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        req_id = db.create_coverage_request(uid1, "2025-03-15", "day")
        db.claim_coverage_request(req_id, uid2)
        with pytest.raises(ValueError, match="cannot be claimed"):
            db.claim_coverage_request(req_id, uid2)

    def test_claim_cancelled_raises(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        req_id = db.create_coverage_request(uid1, "2025-03-15", "day")
        db.cancel_coverage_request(req_id)
        with pytest.raises(ValueError, match="cannot be claimed"):
            db.claim_coverage_request(req_id, uid2)

    def test_claim_nonexistent_raises(self, db):
        uid = db.create_user("bob", "hash", "Bob", "Bob B")
        with pytest.raises(ValueError, match="not found"):
            db.claim_coverage_request(9999, uid)

    def test_claim_nonexistent_claimer_raises(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        req_id = db.create_coverage_request(uid, "2025-03-15", "day")
        with pytest.raises(ValueError, match="not found"):
            db.claim_coverage_request(req_id, 9999)


class TestUnclaimCoverageRequest:
    """Tests for unclaim_coverage_request."""

    def test_unclaim_reverts_to_open(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        req_id = db.create_coverage_request(uid1, "2025-03-15", "day")
        db.claim_coverage_request(req_id, uid2)
        db.unclaim_coverage_request(req_id)
        reqs = db.get_coverage_requests()
        r = reqs[0]
        assert r.status == "open"
        assert r.claimer_id is None
        assert r.claimed_at is None

    def test_unclaim_removes_override(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        req_id = db.create_coverage_request(uid1, "2025-03-15", "day")
        db.claim_coverage_request(req_id, uid2)
        db.unclaim_coverage_request(req_id)
        overrides = db.get_overrides(2025)
        match = [o for o in overrides if o.date == "2025-03-15" and o.shift_type == "day"]
        assert len(match) == 0

    def test_unclaim_open_raises(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        req_id = db.create_coverage_request(uid, "2025-03-15", "day")
        with pytest.raises(ValueError, match="not claimed"):
            db.unclaim_coverage_request(req_id)

    def test_unclaim_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.unclaim_coverage_request(9999)


class TestCancelCoverageRequest:
    """Tests for cancel_coverage_request."""

    def test_cancel_open_request(self, db):
        uid = db.create_user("alice", "hash", "Alice", "Alice A")
        req_id = db.create_coverage_request(uid, "2025-03-15", "day")
        db.cancel_coverage_request(req_id)
        reqs = db.get_coverage_requests()
        assert reqs[0].status == "cancelled"

    def test_cancel_claimed_request_removes_override(self, db):
        uid1 = db.create_user("alice", "hash", "Alice", "Alice A")
        uid2 = db.create_user("bob", "hash", "Bob", "Bob B")
        req_id = db.create_coverage_request(uid1, "2025-03-15", "day")
        db.claim_coverage_request(req_id, uid2)
        db.cancel_coverage_request(req_id)
        reqs = db.get_coverage_requests()
        assert reqs[0].status == "cancelled"
        overrides = db.get_overrides(2025)
        match = [o for o in overrides if o.date == "2025-03-15" and o.shift_type == "day"]
        assert len(match) == 0

    def test_cancel_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.cancel_coverage_request(9999)
