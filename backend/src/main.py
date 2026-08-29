from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import httpx
from typing import Any

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import uuid

# Patch fastapi's _IncludedRouter to prevent prometheus-fastapi-instrumentator crash on newer FastAPI/Starlette versions
try:
    from fastapi.routing import _IncludedRouter
    _IncludedRouter.path = ""
except Exception:
    pass

from prometheus_fastapi_instrumentator import Instrumentator

from .api.router import api_router, root_api_router
from .api.v1 import prior_auth
from .core.config import settings
from .core.security import get_current_user, get_current_user_with_role
from .core.logger import log, correlation_id

# Initialize Sentry APM Performance Monitoring
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastAPIIntegration
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastAPIIntegration()],
            traces_sample_rate=1.0,
        )
        log.info("[Sentry] Performance monitoring initialized successfully on API server.")
    except ImportError:
        log.warning("[Sentry] WARNING: sentry-sdk package not installed. Skipping Sentry initialization.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    try:
        log.info(f"[Startup] SUPABASE_URL: {settings.SUPABASE_URL}")
        log.info(f"[Startup] SUPABASE_SERVICE_KEY: ...{settings.SUPABASE_SERVICE_KEY[-10:]}")
        log.info(f"[Startup] SUPABASE_ANON_KEY: ...{settings.SUPABASE_ANON_KEY[-10:]}")
    except Exception as e:
        log.warning(f"[Startup] Config log warning: {e}")

    # ── Start Background Job Scheduler ─────────────────────────────────────────
    # Runs: 24h reminders, CALL-E confirmation calls, recording purge, waitlist expiry
    try:
        from .services.scheduler import start_scheduler
        start_scheduler()
        log.info("[Scheduler] APScheduler started — all background jobs active.")
    except ImportError:
        log.warning("[Scheduler] scheduler.py not found — background jobs will NOT run.")
    except Exception as sched_err:
        log.error(f"[Scheduler] Failed to start: {sched_err}")


    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    try:
        from .services.scheduler import scheduler
        if scheduler.running:
            scheduler.shutdown(wait=False)
            log.info("[Scheduler] APScheduler stopped cleanly.")
    except Exception:
        pass


app = FastAPI(
    title="Bytelytic OS",
    description="AI Receptionist & Clinic Management API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=True  # allow trailing-slash redirects that preserve Authorization headers (307 redirect)
)

# Initialize Global Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS configuration
if settings.NODE_ENV == "production":
    origins = [
        "https://dashboard-two-jade-54.vercel.app",  # Production Vercel frontend
    ]
else:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://dashboard-two-jade-54.vercel.app",  # Production Vercel frontend
    ]

if settings.DASHBOARD_URL:
    origins.append(settings.DASHBOARD_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Allowed Hosts for Security
allowed_hosts = ["*"]

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Allow Swagger UI CDN resources on API documentation routes
    if request.url.path.startswith(("/docs", "/openapi.json", "/redoc")):
        response.headers["Content-Security-Policy"] = "default-src 'self' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com;"
    else:
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
    if request.url.hostname not in ["localhost", "127.0.0.1"]:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


# Custom Middleware for Correlation IDs (Request Tracing)
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    correlation_id.set(corr_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response

# ─────────────────────────────────────────────────────────────────────────────
# MFA Factors GET — registered BEFORE include_router to win Starlette
# first-match routing. Uses /auth/v1/user with api-version header to get
# factors — this is how Supabase client implements mfa.list_factors() internally.
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/auth/mfa/factors", tags=["auth"])
@app.get("/api/auth/mfa/factors", tags=["auth"])
async def mfa_factors_direct(request: Request):
    """List enrolled MFA factors for the current user via Supabase /auth/v1/user."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}",
        "x-supabase-api-version": "2024-01-01",  # required for factors in response
    }
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(f"{settings.SUPABASE_URL}/auth/v1/user", headers=headers)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        user_data = res.json()
        factors = user_data.get("factors", [])
        totp = [f for f in factors if f.get("factor_type") == "totp"]
        phone = [f for f in factors if f.get("factor_type") == "phone"]
        return {"data": {"all": factors, "totp": totp, "phone": phone}}

from .middleware.phi_url_guard import PHIUrlGuardMiddleware
app.add_middleware(PHIUrlGuardMiddleware)

# Include all routers (both /api prefixed and root level for robustness)
app.include_router(api_router)
app.include_router(root_api_router)

# Initialize Prometheus Exporter
Instrumentator().instrument(app).expose(app)

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    log.error(f"[error.http] {request.method} {request.url.path} status={exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "details": []
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join([str(x) for x in err.get("loc", [])])
        msg = err.get("msg", "Validation error")
        errors.append(f"Field '{loc}': {msg}")
    
    import re
    _PHONE_RE = re.compile(r'\+?[\d\s\-\(\)]{10,17}')
    scrubbed = _PHONE_RE.sub('[PHI_REDACTED]', str(errors))
    log.error(f"[error.validation] Validation error (PHI redacted): {scrubbed}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Validation Error",
            "details": errors
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.critical(f"[error.global] {request.method} {request.url.path} status=500 - {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "details": [str(exc)]
        }
    )

from collections import deque
import threading
import time

ERROR_WINDOW = deque()
LATENCY_WINDOW = deque()
METRICS_LOCK = threading.Lock()

@app.middleware("http")
async def monitor_metrics(request: Request, call_next):
    # Skip health check and static endpoints to avoid polling noise
    if request.url.path in ["/health", "/health/detailed", "/"] or request.url.path.startswith("/static/"):
        return await call_next(request)
        
    start_time = time.time()
    response = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        raise e
    finally:
        duration = time.time() - start_time
        now = time.time()
        
        with METRICS_LOCK:
            # 1. Track errors (5xx)
            if status_code >= 500:
                ERROR_WINDOW.append(now)
                # Clean old errors (older than 60 seconds)
                while ERROR_WINDOW and ERROR_WINDOW[0] < now - 60:
                    ERROR_WINDOW.popleft()
                # Check threshold: if > 5 errors/minute -> alert
                if len(ERROR_WINDOW) > 5:
                    from .core.cache import local_cache
                    last_alert = local_cache.get("metrics_error_alert_time")
                    if not last_alert:
                        local_cache.set("metrics_error_alert_time", now, ttl=300) # 5 min cooldown
                        from .services.slack_service import slack_service
                        import asyncio
                        asyncio.create_task(slack_service.alert(
                            message="High Error Rate Detected (> 5 errors/min)",
                            level="critical",
                            details={"errors_last_minute": len(ERROR_WINDOW), "last_failed_path": request.url.path}
                        ))
            
            # 2. Track latency (sliding window of 5 minutes)
            LATENCY_WINDOW.append((now, duration))
            # Clean old latency records (older than 300 seconds / 5 minutes)
            while LATENCY_WINDOW and LATENCY_WINDOW[0][0] < now - 300:
                LATENCY_WINDOW.popleft()
                
            # If we have at least 10 requests, check average latency
            if len(LATENCY_WINDOW) >= 10:
                avg_latency = sum(d for t, d in LATENCY_WINDOW) / len(LATENCY_WINDOW)
                if avg_latency > 2.0:
                    from .core.cache import local_cache
                    last_alert = local_cache.get("metrics_latency_alert_time")
                    if not last_alert:
                        local_cache.set("metrics_latency_alert_time", now, ttl=300) # 5 min cooldown
                        from .services.slack_service import slack_service
                        import asyncio
                        asyncio.create_task(slack_service.alert(
                            message="High API Latency Detected (> 2.0s average)",
                            level="warning",
                            details={"avg_latency_seconds": round(avg_latency, 2), "sample_size": len(LATENCY_WINDOW)}
                        ))

@app.get("/")
async def root():
    return {"message": "Welcome to Bytelytic OS API", "status": "online"}


@app.get("/health")
async def health():
    try:
        from .core.database import supabase_read
        res = supabase_read.table("clinics").select("id").limit(1).execute()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        log.error(f"Deep DB health check failed: {str(e)}")
        
    return {
        "status": "healthy", 
        "database": db_status, 
        "message": "Bytelytic OS API is online"
    }


@app.get("/health/detailed")
async def health_detailed():
    import anyio
    import asyncio
    import datetime
    from twilio.rest import Client as TwilioClient
    from retell import Retell as RetellClient
    from .core.database import supabase_read
    from .core.config import settings
    
    db_status = "unknown"
    twilio_status = "unknown"
    retell_status = "unknown"
    
    # 1. Check database
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics").select("id").limit(1).execute()
        )
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        log.error(f"Detailed health check - DB failed: {str(e)}")

    # 2. Check Twilio
    try:
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # Fetch simple account details to verify credentials
            account = await anyio.to_thread.run_sync(
                lambda: twilio_client.api.v2010.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
            )
            twilio_status = "healthy" if account.status == "active" else f"unhealthy: account status is {account.status}"
        else:
            twilio_status = "unconfigured"
    except Exception as e:
        twilio_status = f"unhealthy: {str(e)}"
        log.error(f"Detailed health check - Twilio failed: {str(e)}")

    # 3. Check Retell AI
    try:
        if settings.RETELL_API_KEY:
            retell_client = RetellClient(api_key=settings.RETELL_API_KEY)
            # Call agent.list with limit 1 to check connectivity
            agents = await anyio.to_thread.run_sync(
                lambda: retell_client.agent.list()
            )
            retell_status = "healthy"
        else:
            retell_status = "unconfigured"
    except Exception as e:
        retell_status = f"unhealthy: {str(e)}"
        log.error(f"Detailed health check - Retell failed: {str(e)}")

    overall = "healthy"
    if "unhealthy" in db_status or "unhealthy" in twilio_status or "unhealthy" in retell_status:
        overall = "unhealthy"

    response_payload = {
        "status": overall,
        "database": db_status,
        "twilio": twilio_status,
        "retell": retell_status,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    if overall == "unhealthy":
        return JSONResponse(
            status_code=503,
            content=response_payload
        )

    return response_payload


@app.get("/export/patients.csv", tags=["Export"])
async def export_patients_csv_shortcut(
    auth: Any = Depends(get_current_user_with_role)
):
    """
    Direct shortcut route to export patients as CSV.
    """
    # Lazily import router function to prevent circular imports
    from .api.routers.patients_router import export_patients_csv
    
    return await export_patients_csv(auth)


@app.get("/export/appointments.csv", tags=["Export"])
async def export_appointments_csv_shortcut(
    auth: Any = Depends(get_current_user_with_role)
):
    """
    Direct shortcut route to export appointments as CSV.
    """
    from .api.routers.appointments_router import export_appointments_csv
    
    return await export_appointments_csv(auth)
