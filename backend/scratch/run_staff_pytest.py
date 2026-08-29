import os
import sys
import pytest

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

if __name__ == "__main__":
    test_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "test_staff.py")
    ret = pytest.main(["-v", "-s", test_path])
    sys.exit(ret)
