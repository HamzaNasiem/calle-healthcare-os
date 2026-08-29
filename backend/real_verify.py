import sys
sys.path.insert(0, '.')

print("Testing imports...")

try:
    from src.core.logger import log, correlation_id
    print("[OK] logger imported - structured JSON logging active")
except Exception as e:
    print(f"[FAIL] logger: {e}")

try:
    from src.core.config import settings
    print(f"[OK] config loaded - NODE_ENV={settings.NODE_ENV}")
    print(f"     SLACK_WEBHOOK_URL configured: {bool(settings.SLACK_WEBHOOK_URL)}")
    print(f"     SENTRY_DSN configured: {bool(settings.SENTRY_DSN)}")
except Exception as e:
    print(f"[FAIL] config: {e}")

try:
    from src.core.database import supabase, supabase_read
    print(f"[OK] supabase clients loaded")
    print(f"     Read replica same as master: {id(supabase) == id(supabase_read)}")
except Exception as e:
    print(f"[FAIL] database: {e}")

try:
    from src.core.resilience import CircuitBreaker
    cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout_seconds=30)
    print(f"[OK] CircuitBreaker - state={cb.state}")
except Exception as e:
    print(f"[FAIL] resilience: {e}")

try:
    from src.core.cache import local_cache
    local_cache.set("test_key", "test_val", ttl=10)
    val = local_cache.get("test_key")
    print(f"[OK] LocalCache - set/get working: {val == 'test_val'}")
except Exception as e:
    print(f"[FAIL] cache: {e}")

try:
    from src.services.audit_service import audit_service
    print(f"[OK] audit_service imported")
except Exception as e:
    print(f"[FAIL] audit_service: {e}")

try:
    from src.services.slack_service import slack_service
    print(f"[OK] slack_service imported - webhook_url set: {bool(slack_service.webhook_url)}")
except Exception as e:
    print(f"[FAIL] slack_service: {e}")

try:
    from src.jobs.scheduler import scheduler, run_cron_with_lock
    print(f"[OK] scheduler imported - running={scheduler.running}")
except Exception as e:
    print(f"[FAIL] scheduler: {e}")

try:
    from src.main import app
    routes = [r.path for r in app.routes]
    has_v1 = any("/api/v1/" in r for r in routes)
    has_metrics = any("metrics" in r for r in routes)
    has_health = any(r == "/health" for r in routes)
    print(f"[OK] FastAPI app loaded")
    print(f"     /api/v1/ routes present: {has_v1}")
    print(f"     /metrics endpoint present: {has_metrics}")
    print(f"     /health endpoint present: {has_health}")
    print(f"     Total routes: {len(routes)}")
except Exception as e:
    print(f"[FAIL] main app: {e}")

print("\nVerification complete.")
