import pytest
import sys
import os
from unittest.mock import MagicMock

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "mock_service_key")
os.environ.setdefault("SUPABASE_ANON_KEY", "mock_anon_key")
os.environ.setdefault("RETELL_API_KEY", "mock_retell_key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "mock_google_id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "mock_google_secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/google/callback")
os.environ.setdefault("OPENROUTER_API_KEY", "mock_openrouter_key")
os.environ.setdefault("API_BASE_URL", "http://localhost:3000")
os.environ.setdefault("DASHBOARD_URL", "http://localhost:5173")

# 1. Create Mock database client
mock_db = MagicMock()
mock_db_read = MagicMock()

# Mock admin auth user creation
mock_user = MagicMock()
mock_user.id = "mock-user-id"
mock_user.email = "mock-email@example.com"

# Create helper function to mock create_user with conditional exceptions
def mock_create_user(user_data):
    email = user_data.get("email")
    if not email:
        raise Exception("Email is required")
    user = MagicMock()
    user.id = "mock-user-id"
    user.email = email
    res = MagicMock()
    res.user = user
    return res

mock_db.auth.admin.create_user.side_effect = mock_create_user
mock_db.auth.get_user.return_value = MagicMock(user=mock_user)

# Mock select/insert/update/delete chains
mock_execute_res = MagicMock()
mock_execute_res.data = []
mock_execute_res.count = 0

class MockQuery:
    def __init__(self, res):
        self._res = res
    def __getattr__(self, name):
        if name == "execute":
            return lambda: self._res
        return lambda *args, **kwargs: self

# Mock table select chain
mock_table_mock = MagicMock()
mock_table_mock.select.side_effect = lambda *args, **kwargs: MockQuery(mock_execute_res)
mock_table_mock.insert.side_effect = lambda *args, **kwargs: MockQuery(mock_execute_res)
mock_table_mock.update.side_effect = lambda *args, **kwargs: MockQuery(mock_execute_res)
mock_table_mock.delete.side_effect = lambda *args, **kwargs: MockQuery(mock_execute_res)

mock_db.table.return_value = mock_table_mock
mock_db_read.table.return_value = mock_table_mock

# Put mocks into sys.modules and patch before import
import src.core.database
src.core.database.supabase = mock_db
src.core.database.supabase_read = mock_db_read
src.core.database.auth_client = mock_db

import src.core.security
src.core.security.auth_client = mock_db
src.core.security.supabase = mock_db

from src.main import app
from fastapi.testclient import TestClient

@pytest.fixture(scope="module")
def client():
    # Set raise_server_exceptions=False to return server exceptions as HTTP 500 status responses
    with TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False) as c:
        yield c
