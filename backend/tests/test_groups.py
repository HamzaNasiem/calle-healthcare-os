"""
Tests for Phase 8 Multi-Location Clinic Groups — groups_router.py
All endpoints require get_current_user_with_role auth (owner role).
DB calls are mocked via monkeypatch on src.core.database.
"""
import pytest
from unittest.mock import MagicMock

# conftest.py already patches src.core.database and imports the app.
from src.main import app
from src.core.security import get_current_user_with_role, AuthenticatedUser
from fastapi.testclient import TestClient


# ------------------------------------------------------------------------------
# Shared fixtures
# ------------------------------------------------------------------------------

MOCK_AUTH = AuthenticatedUser(
    user_id="user-001",
    email="owner@example.com",
    clinic_id="clinic-001",
    clinic_name="Test Clinic",
    role="owner",
)


def _make_dep_override():
    """Returns a FastAPI dependency override for get_current_user_with_role."""
    async def _override():
        return MOCK_AUTH
    return _override


@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False) as c:
        yield c


# ------------------------------------------------------------------------------
# Helper: build a chainable supabase mock that returns desired data
# ------------------------------------------------------------------------------

def _mock_supabase(data=None, count=0):
    """Return a mock supabase client whose chainable calls resolve to data."""
    mock = MagicMock()
    result = MagicMock()
    result.data = data if data is not None else []
    result.count = count

    chain = MagicMock()
    chain.execute.return_value = result
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    mock.table.return_value = chain
    return mock, result


# ------------------------------------------------------------------------------
# Test 1 — POST /groups  (create group, 201)
# ------------------------------------------------------------------------------

def test_create_group_success(client, monkeypatch):
    created = {"id": "grp-1", "name": "West Coast Group", "owner_email": "owner@example.com"}
    mock_sb, result = _mock_supabase(data=[created])
    result.data = [created]

    monkeypatch.setattr("src.api.routers.groups_router.supabase", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.post("/api/v1/groups", json={"name": "West Coast Group", "owner_email": "owner@example.com"})
        assert r.status_code == 201
        body = r.json()
        assert "data" in body
        assert body["data"]["name"] == "West Coast Group"
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Test 2 — GET /groups  (list groups by owner)
# ------------------------------------------------------------------------------

def test_list_groups_success(client, monkeypatch):
    groups = [
        {"id": "grp-1", "name": "Group A", "owner_email": "owner@example.com"},
        {"id": "grp-2", "name": "Group B", "owner_email": "owner@example.com"},
    ]
    mock_sb, _ = _mock_supabase(data=groups)

    monkeypatch.setattr("src.api.routers.groups_router.supabase_read", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.get("/api/v1/groups")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 2
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Test 3 — GET /groups/{group_id}  (get group + clinics)
# ------------------------------------------------------------------------------

def test_get_group_success(client, monkeypatch):
    group_data = {"id": "grp-1", "name": "Group A", "owner_email": "owner@example.com"}
    clinics_data = [{"id": "clinic-001", "name": "Main Clinic", "group_id": "grp-1"}]

    mock_sb = MagicMock()
    result_group = MagicMock()
    result_group.data = [group_data]
    result_clinics = MagicMock()
    result_clinics.data = clinics_data

    call_count = {"n": 0}

    def _table_side_effect(name):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.select.return_value = chain
        if name == "clinic_groups":
            chain.execute.return_value = result_group
        else:
            chain.execute.return_value = result_clinics
        return chain

    mock_sb.table.side_effect = _table_side_effect
    monkeypatch.setattr("src.api.routers.groups_router.supabase_read", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.get("/api/v1/groups/grp-1")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "clinics" in body["data"]
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Test 4 — POST /groups/{group_id}/add-clinic/{clinic_id}
# ------------------------------------------------------------------------------

def test_add_clinic_to_group_success(client, monkeypatch):
    group_data = {"id": "grp-1", "name": "Group A", "owner_email": "owner@example.com"}
    clinic_data = {"id": "clinic-001", "name": "Main Clinic", "owner_email": "owner@example.com", "group_id": None}
    updated = {**clinic_data, "group_id": "grp-1"}

    mock_read = MagicMock()
    mock_write = MagicMock()

    def _read_table(name):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.select.return_value = chain
        if name == "clinic_groups":
            result = MagicMock()
            result.data = [group_data]
            chain.execute.return_value = result
        else:
            result = MagicMock()
            result.data = [clinic_data]
            chain.execute.return_value = result
        return chain

    def _write_table(name):
        chain = MagicMock()
        chain.update.return_value = chain
        chain.eq.return_value = chain
        result = MagicMock()
        result.data = [updated]
        chain.execute.return_value = result
        return chain

    mock_read.table.side_effect = _read_table
    mock_write.table.side_effect = _write_table

    monkeypatch.setattr("src.api.routers.groups_router.supabase_read", mock_read)
    monkeypatch.setattr("src.api.routers.groups_router.supabase", mock_write)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.post("/api/v1/groups/grp-1/add-clinic/clinic-001")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Test 5 — DELETE /groups/{group_id}/remove-clinic/{clinic_id}
# ------------------------------------------------------------------------------

def test_remove_clinic_from_group_success(client, monkeypatch):
    group_data = {"id": "grp-1", "name": "Group A", "owner_email": "owner@example.com"}
    clinic_data = {"id": "clinic-001", "name": "Main Clinic", "owner_email": "owner@example.com", "group_id": "grp-1"}
    updated = {**clinic_data, "group_id": None}

    mock_read = MagicMock()
    mock_write = MagicMock()

    def _read_table(name):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.select.return_value = chain
        if name == "clinic_groups":
            result = MagicMock()
            result.data = [group_data]
            chain.execute.return_value = result
        else:
            result = MagicMock()
            result.data = [clinic_data]
            chain.execute.return_value = result
        return chain

    def _write_table(name):
        chain = MagicMock()
        chain.update.return_value = chain
        chain.eq.return_value = chain
        result = MagicMock()
        result.data = [updated]
        chain.execute.return_value = result
        return chain

    mock_read.table.side_effect = _read_table
    mock_write.table.side_effect = _write_table

    monkeypatch.setattr("src.api.routers.groups_router.supabase_read", mock_read)
    monkeypatch.setattr("src.api.routers.groups_router.supabase", mock_write)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.delete("/api/v1/groups/grp-1/remove-clinic/clinic-001")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Test 6 — GET /groups/{group_id}/patients  (cross-location lookup)
# ------------------------------------------------------------------------------

def test_get_group_patients_success(client, monkeypatch):
    group_data = {"id": "grp-1", "name": "Group A", "owner_email": "owner@example.com"}
    clinics = [{"id": "clinic-001", "name": "Main Clinic"}, {"id": "clinic-002", "name": "North Branch"}]
    patients = [
        {"id": "pat-1", "name": "Alice", "clinic_id": "clinic-001"},
        {"id": "pat-2", "name": "Bob", "clinic_id": "clinic-002"},
    ]

    mock_sb = MagicMock()
    call_seq = {"i": 0}
    results = [
        MagicMock(data=[group_data]),   # _verify_group_owner
        MagicMock(data=clinics),         # fetch clinics
        MagicMock(data=patients),        # fetch patients
    ]

    def _table_side_effect(name):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.in_.return_value = chain
        idx = call_seq["i"]
        if idx < len(results):
            chain.execute.return_value = results[idx]
        else:
            chain.execute.return_value = MagicMock(data=[])
        call_seq["i"] += 1
        return chain

    mock_sb.table.side_effect = _table_side_effect
    monkeypatch.setattr("src.api.routers.groups_router.supabase_read", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.get("/api/v1/groups/grp-1/patients")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert isinstance(body["data"], list)
        # Patients should be enriched with clinic_name
        for p in body["data"]:
            assert "clinic_name" in p
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Test 7 — GET /groups/{group_id}/stats  (aggregate stats)
# ------------------------------------------------------------------------------

def test_get_group_stats_success(client, monkeypatch):
    group_data = {"id": "grp-1", "name": "Group A", "owner_email": "owner@example.com"}
    clinics = [{"id": "clinic-001"}, {"id": "clinic-002"}]
    calls_data = [{"id": "call-1"}, {"id": "call-2"}]
    appts_data = [{"id": "appt-1"}]
    revenue_data = [{"amount_cents": 5000}, {"amount_cents": 3000}]

    mock_sb = MagicMock()
    call_seq = {"i": 0}
    results = [
        MagicMock(data=[group_data], count=1),    # _verify_group_owner
        MagicMock(data=clinics, count=2),          # fetch clinics
        MagicMock(data=calls_data, count=2),       # calls
        MagicMock(data=appts_data, count=1),       # appointments
        MagicMock(data=revenue_data, count=2),     # revenue
    ]

    def _table_side_effect(name):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.in_.return_value = chain
        idx = call_seq["i"]
        if idx < len(results):
            chain.execute.return_value = results[idx]
        else:
            chain.execute.return_value = MagicMock(data=[], count=0)
        call_seq["i"] += 1
        return chain

    mock_sb.table.side_effect = _table_side_effect
    monkeypatch.setattr("src.api.routers.groups_router.supabase_read", mock_sb)

    app.dependency_overrides[get_current_user_with_role] = _make_dep_override()
    try:
        r = client.get("/api/v1/groups/grp-1/stats")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        data = body["data"]
        assert "total_calls" in data
        assert "total_appointments" in data
        assert "total_revenue_cents" in data
        assert data["total_revenue_cents"] == 8000
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------------------------
# Test 8 — Unauthenticated requests should be blocked (401/403)
# ------------------------------------------------------------------------------

def test_groups_routes_require_auth(client):
    """Verify all group endpoints block unauthenticated callers."""
    endpoints = [
        ("GET", "/api/v1/groups"),
        ("GET", "/api/v1/groups/some-id"),
        ("POST", "/api/v1/groups/some-id/add-clinic/clinic-id"),
        ("DELETE", "/api/v1/groups/some-id/remove-clinic/clinic-id"),
        ("GET", "/api/v1/groups/some-id/patients"),
        ("GET", "/api/v1/groups/some-id/stats"),
    ]
    for method, url in endpoints:
        r = client.request(method, url)
        assert r.status_code in (401, 403), f"Expected 401/403 for {method} {url}, got {r.status_code}"
