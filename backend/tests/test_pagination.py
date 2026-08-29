import pytest
from src.core.security import get_current_user_with_role, require_active_subscription

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer mock_token"}

class MockData:
    def __init__(self, data, count):
        self.data = data
        self.count = count

class MockQuery:
    def __init__(self, data):
        self.data = data
        
    def eq(self, *args, **kwargs): return self
    def neq(self, *args, **kwargs): return self
    def order(self, *args, **kwargs): return self
    def or_(self, *args, **kwargs): return self
    def lt(self, *args, **kwargs): return self
    
    def limit(self, n):
        self.limit_val = n
        return self
        
    def range(self, start, end):
        self.range_val = (start, end)
        return self
        
    def execute(self):
        data = list(self.data)
        if hasattr(self, "range_val"):
            data = data[self.range_val[0]:self.range_val[1] + 1]
        elif hasattr(self, "limit_val"):
            data = data[:self.limit_val]
        return MockData(data, len(self.data))

class MockTable:
    def __init__(self, data):
        self.data = data
        
    def select(self, *args, **kwargs):
        return MockQuery(self.data)

class MockSupabase:
    def __init__(self, data):
        self.data = data
        
    def table(self, name):
        return MockTable(self.data)

def test_patients_pagination(client, auth_headers, monkeypatch):
    from src.core.security import AuthenticatedUser
    from src.main import app
    
    mock_user = AuthenticatedUser(
        user_id="mock_user_id",
        email="test@example.com",
        role="owner",
        clinic_id="17641801-58ed-49b1-9f75-d6d46fbe78c5",
        clinic_name="Mock Clinic"
    )
    
    # Setup dependency overrides
    app.dependency_overrides[get_current_user_with_role] = lambda: mock_user
    app.dependency_overrides[require_active_subscription] = lambda: mock_user
    
    mock_patients = [
        {"id": f"p{i}", "name": f"Patient {i}", "created_at": f"2026-06-11T12:00:{i:02d}Z"}
        for i in range(10)
    ]
    
    monkeypatch.setattr("src.api.routers.patients_router.supabase_read", MockSupabase(mock_patients))
    
    try:
        # 1. Test default pagination (no limit/page/cursor)
        response = client.get("/api/v1/patients", headers=auth_headers)
        assert response.status_code == 200, f"Error: {response.content}"
        res_data = response.json()
        assert "data" in res_data
        assert "meta" in res_data
        assert res_data["meta"]["limit"] == 50
        assert len(res_data["data"]) == 10
        assert "next_cursor" not in res_data["meta"]
        
        # 2. Test limit/cursor pagination (next_cursor should be generated)
        response = client.get("/api/v1/patients?limit=5", headers=auth_headers)
        assert response.status_code == 200
        res_data = response.json()
        assert len(res_data["data"]) == 5
        assert res_data["meta"]["next_cursor"] == mock_patients[4]["created_at"]
        
        # 3. Test page-based offset pagination
        response = client.get("/api/v1/patients?page=2&limit=4", headers=auth_headers)
        assert response.status_code == 200
        res_data = response.json()
        assert len(res_data["data"]) == 4
        assert res_data["data"][0]["id"] == "p4" # slice [4:8] -> p4, p5, p6, p7
        
        # 4. Test search parameter
        response = client.get("/api/v1/patients?search=John", headers=auth_headers)
        assert response.status_code == 200
        
    finally:
        app.dependency_overrides.clear()

def test_calls_pagination(client, auth_headers, monkeypatch):
    from src.core.security import AuthenticatedUser
    from src.main import app
    
    mock_user = AuthenticatedUser(
        user_id="mock_user_id",
        email="test@example.com",
        role="owner",
        clinic_id="17641801-58ed-49b1-9f75-d6d46fbe78c5",
        clinic_name="Mock Clinic"
    )
    
    app.dependency_overrides[get_current_user_with_role] = lambda: mock_user
    app.dependency_overrides[require_active_subscription] = lambda: mock_user
    
    mock_calls = [
        {"id": f"c{i}", "direction": "inbound", "created_at": f"2026-06-11T12:00:{i:02d}Z"}
        for i in range(10)
    ]
    
    monkeypatch.setattr("src.api.routers.calls_router.supabase_read", MockSupabase(mock_calls))
    
    try:
        # 1. Test limit-based pagination (next_cursor should be generated)
        response = client.get("/api/v1/calls?limit=5", headers=auth_headers)
        assert response.status_code == 200, f"Error: {response.content}"
        res_data = response.json()
        assert "data" in res_data
        assert "meta" in res_data
        assert res_data["meta"]["limit"] == 5
        assert len(res_data["data"]) == 5
        assert res_data["meta"]["next_cursor"] == mock_calls[4]["created_at"]
        
        # 2. Test offset/page pagination
        response = client.get("/api/v1/calls?page=2&limit=3", headers=auth_headers)
        assert response.status_code == 200
        res_data = response.json()
        assert len(res_data["data"]) == 3
        assert res_data["data"][0]["id"] == "c3" # slice [3:6]
        
    finally:
        app.dependency_overrides.clear()

