from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
import asyncio
import time
import httpx
from collections import defaultdict
from typing import Any, List, Optional, Dict
from pydantic import BaseModel, field_validator
from ...services.onboarding_service import onboarding_service
from ...core.database import supabase, supabase_read, auth_client
from ...core.security import get_current_user, validate_password_strength, validate_phone_format
from ...services.audit_service import audit_service
from ...services.session_service import session_service
from ...core.config import settings
from ...services.phonenumber_service import phonenumber_service
from ...services.voice_service import voice_service
from ...core.logger import log


# ─────────────────────────────────────────
# Brute-Force Rate Limiter (Redis-Free)
# ─────────────────────────────────────────
class BruteForceLimiter:
    def __init__(self):
        # IP -> list of failed attempt timestamps
        self.failed_attempts = defaultdict(list)
        
    def is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        # Keep only attempts in last 15 minutes (900 seconds)
        self.failed_attempts[ip] = [t for t in self.failed_attempts[ip] if now - t < 900]
        return len(self.failed_attempts[ip]) >= 5
        
    def record_fail(self, ip: str) -> None:
        self.failed_attempts[ip].append(time.time())
        
    def reset(self, ip: str) -> None:
        self.failed_attempts.pop(ip, None)

limiter = BruteForceLimiter()

router = APIRouter(prefix="/auth", tags=["auth"])

# ─────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str
    clinicName: str
    specialty: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = "America/Chicago"
    doctorName: Optional[str] = None
    doctorCredentials: Optional[str] = None
    doctorPhone: Optional[str] = None
    businessHours: Optional[Dict[str, Any]] = None
    appointmentTypes: Optional[List[Dict[str, Any]]] = None

    @field_validator("doctorPhone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v:
            validate_phone_format(v)
        return v

class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class RefreshRequest(BaseModel):
    refresh_token: str = ""

class RevokeSessionRequest(BaseModel):
    session_id: str

# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@router.post("/signup")
async def signup(req: SignupRequest, request: Request):
    log.info(f"[auth.signup] Received signup request for email: {req.email}, clinicName: {req.clinicName}")
    
    # 1. IP extraction
    x_forwarded_for = request.headers.get("x-forwarded-for")
    ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else (request.client.host if request.client else "unknown")
    
    # 2. Rate limit check
    if limiter.is_rate_limited(ip):
        await audit_service.log(
            clinic_id=None,
            user_id=None,
            user_email=req.email,
            action="security.signup_rate_limited",
            resource_type="auth",
            details={"reason": "rate_limited", "ip": ip},
            request=request
        )
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again in 15 minutes.")
        
    # 3. Backend Password complexity validation
    try:
        validate_password_strength(req.password)
    except ValueError as ve:
        limiter.record_fail(ip)
        await audit_service.log(None, None, req.email, "auth.signup_invalid_password", request=request)
        raise HTTPException(status_code=400, detail=str(ve))
        
    res = await onboarding_service.process_signup(
        owner_email=req.email,
        password=req.password,
        clinic_name=req.clinicName,
        specialty=req.specialty or None,
        city=req.city or None,
        timezone=req.timezone or "America/Chicago",
        doctor_name=req.doctorName or None,
        doctor_credentials=req.doctorCredentials or None,
        doctor_phone=req.doctorPhone or None,
        business_hours=req.businessHours or None,
        appointment_types=req.appointmentTypes or None,
    )
    
    if not res.get("success"):
        error_msg = res.get("error", "Signup failed")
        # Clean up common Supabase error messages for the user
        if "already registered" in error_msg or "already been registered" in error_msg:
            error_msg = "This email is already registered. Please sign in instead."
        elif "User not allowed" in error_msg:
            error_msg = "Signup is not allowed for this email. Please use a different email address."
        log.warning(f"[auth.signup] Signup failed for {req.email}: {error_msg}")
        limiter.record_fail(ip)
        await audit_service.log(
            clinic_id=None,
            user_id=None,
            user_email=req.email,
            action="auth.signup_failed",
            resource_type="auth",
            details={"reason": str(error_msg), "ip": ip},
            request=request
        )
        return JSONResponse(status_code=400, content={"error": error_msg, "detail": error_msg})
    
    # Sign the new user in to get an access token
    token = None
    login_res = None
    user_id = None
    clinic_id = res.get("data", {}).get("clinicId")
    try:
        login_res = await asyncio.get_event_loop().run_in_executor(
            None, lambda: auth_client.auth.sign_in_with_password({"email": req.email, "password": req.password})
        )
        if login_res.session:
            token = login_res.session.access_token
            user_id = str(login_res.user.id) if login_res.user else None
            if user_id:
                # Track session
                ua = request.headers.get("user-agent")
                await session_service.create_session(user_id, req.email, clinic_id, ip, ua)
                await audit_service.log(
                    clinic_id=clinic_id,
                    user_id=user_id,
                    user_email=req.email,
                    action="auth.signup",
                    resource_type="auth",
                    details={"clinic_name": req.clinicName, "ip": ip},
                    request=request
                )
    except Exception as login_e:
        log.error(f"[auth.signup] Auto-login failed after signup: {str(login_e)}")
        
    limiter.reset(ip)
    return {
        "token": token,
        "refreshToken": login_res.session.refresh_token if token and login_res and login_res.session else None,
        "clinicId": clinic_id,
        "clinicName": req.clinicName,
        "timezone": req.timezone or "America/Chicago",
        "role": "owner",
        "userEmail": req.email,
        "userId": user_id if token else None,
    }


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    email_clean = (req.email or "").strip().lower()

    # 1. IP extraction
    x_forwarded_for = request.headers.get("x-forwarded-for")
    ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else (request.client.host if request.client else "unknown")

    # Always allow admin@sunriseclinic.com to bypass rate limit
    if email_clean == "admin@sunriseclinic.com":
        limiter.reset(ip)

    # 2. Rate limit check
    if limiter.is_rate_limited(ip):
        await audit_service.log(
            clinic_id=None,
            user_id=None,
            user_email=email_clean,
            action="security.login_failed",
            resource_type="auth",
            details={"reason": "rate_limited", "ip": ip},
            request=request
        )
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please try again in 15 minutes.")

    DEMO_EMAILS = [
        "admin@callehealthcare.com",
        "admin@sunriseclinic.com",
        "owner@sunrisehealth.com",
        "demo@bytelytic.com",
        "owner@oakridgeclinic.com"
    ]
    VALID_DEMO_PASSWORDS = [
        "Admin@12345!",
        "Password123!",
        "Password123",
        "password",
        "admin123",
        "123456",
        "owner123"
    ]

    # 3. Verified demo admin check
    if email_clean in DEMO_EMAILS:
        if req.password in VALID_DEMO_PASSWORDS or req.password == "Password123!":
            limiter.reset(ip)
            from ...core.security import create_access_token
            token_payload = {
                "sub": "demo-user-001",
                "email": email_clean,
                "clinic_id": "d3b07384-d113-46a6-a719-38cf89235d54",
                "role": "owner",
                "tenant_id": "d3b07384-d113-46a6-a719-38cf89235d54",
            }
            real_jwt = create_access_token(token_payload)

            await audit_service.log(
                clinic_id="d3b07384-d113-46a6-a719-38cf89235d54",
                user_id="demo-user-001",
                user_email=email_clean,
                action="security.login_success",
                resource_type="auth",
                details={"ip": ip, "role": "owner", "auth_method": "demo_verified"},
                request=request
            )
            return {
                "token":        real_jwt,
                "refreshToken": "demo_refresh_token_sunrise_2026",
                "clinicId":     "d3b07384-d113-46a6-a719-38cf89235d54",
                "clinicName":   "Oakridge Physical Therapy & Wellness",
                "timezone":     "America/Chicago",
                "role":         "owner",
                "userEmail":    email_clean,
                "userId":       "demo-user-001",
            }
        else:
            limiter.record_fail(ip)
            await audit_service.log(
                clinic_id=None,
                user_id=None,
                user_email=email_clean,
                action="security.login_failed",
                resource_type="auth",
                details={"reason": "invalid_password", "ip": ip},
                request=request
            )
            raise HTTPException(status_code=400, detail="Incorrect password. For demo access use: Password123!")

    # 4. Standard Local Database Authentication
    try:
        import hashlib as _hashlib
        from ...core.database import LocalPostgresClient as _LPGC
        _db = _LPGC()

        result = _db.execute(
            "SELECT id, hashed_password, role, is_active, is_deleted FROM users "
            "WHERE lower(email) = lower(%s) AND is_deleted = false LIMIT 1",
            (email_clean,)
        )

        if not result or not result[0]:
            limiter.record_fail(ip)
            await audit_service.log(None, None, email_clean, "security.login_failed",
                resource_type="auth", details={"reason": "user_not_found", "ip": ip}, request=request)
            raise HTTPException(status_code=400, detail="Incorrect email or password.")

        user_row   = result[0]
        user_id_str = str(user_row["id"])
        stored_hash = user_row["hashed_password"]
        role        = user_row.get("role") or "owner"
        is_active   = user_row.get("is_active", True)
        clinic_id   = "d3b07384-d113-46a6-a719-38cf89235d54"

        if not is_active:
            raise HTTPException(status_code=400, detail="Account is inactive. Please contact support.")

        # Verify password (SHA-256)
        input_hash = _hashlib.sha256(req.password.encode()).hexdigest()
        if input_hash != stored_hash:
            limiter.record_fail(ip)
            await audit_service.log(None, None, email_clean, "security.login_failed",
                resource_type="auth", details={"reason": "wrong_password", "ip": ip}, request=request)
            raise HTTPException(status_code=400, detail="Incorrect email or password.")

        # Fetch clinic info
        clinic_result = _db.execute(
            "SELECT name, timezone FROM clinics WHERE id::text = %s LIMIT 1", (clinic_id,)
        )
        clinic_name = "Oakridge Physical Therapy & Wellness"
        timezone    = "America/Chicago"
        if clinic_result and clinic_result[0]:
            clinic_name = clinic_result[0].get("name", clinic_name)
            timezone    = clinic_result[0].get("timezone", timezone)

        # Create real JWT
        from ...core.security import create_access_token as _cat
        token_payload = {
            "sub":       user_id_str,
            "email":     email_clean,
            "clinic_id": clinic_id,
            "role":      role,
            "tenant_id": clinic_id,
        }
        real_jwt = _cat(token_payload)

        limiter.reset(ip)
        ua = request.headers.get("user-agent")
        await session_service.create_session(user_id_str, email_clean, clinic_id, ip, ua)
        await audit_service.log(
            clinic_id=clinic_id,
            user_id=user_id_str,
            user_email=email_clean,
            action="security.login_success",
            resource_type="auth",
            details={"ip": ip, "role": role, "auth_method": "local_db"},
            request=request,
        )

        return {
            "token":        real_jwt,
            "refreshToken": real_jwt[:20] + "_ref",
            "clinicId":     clinic_id,
            "clinicName":   clinic_name,
            "timezone":     timezone,
            "role":         role,
            "userEmail":    email_clean,
            "userId":       user_id_str,
        }
    except HTTPException:
        raise
    except Exception as e:
        limiter.record_fail(ip)
        await audit_service.log(None, None, email_clean, "security.login_failed",
            resource_type="auth", details={"reason": "db_error", "error": str(e)[:120], "ip": ip}, request=request)
        raise HTTPException(status_code=400, detail="Incorrect email or password.")



@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, request: Request):
    """
    Supabase se password reset email bhejo.
    Security ke liye hamesha 200 return karo — chahe email registered ho ya na ho.
    """
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: auth_client.auth.reset_password_email(
                req.email,
                options={"redirect_to": f"{settings.DASHBOARD_URL or 'https://app.bytelytic.com'}/reset-password"}
            )
        )
        print(f"[auth.forgot_password] Reset email requested for: {req.email}")
        await audit_service.log(None, None, req.email, "auth.forgot_password_requested", request=request)
    except Exception as e:
        # Log karo but user ko mat batao — security reason
        print(f"[auth.forgot_password] Error (suppressed): {str(e)}")
    
    # Hamesha success return karo (security best practice)
    return {"message": "If this email is registered, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, request: Request):
    """
    Supabase token ke sath naya password set karo.
    """
    if not req.token:
        raise HTTPException(status_code=400, detail="Reset token is missing.")
        
    # Backend Password complexity check
    try:
        validate_password_strength(req.new_password)
    except ValueError as ve:
        await audit_service.log(None, None, None, "auth.password_reset_invalid_password", request=request)
        raise HTTPException(status_code=400, detail=str(ve))
    
    try:
        # Token se user authenticate karo (using the standard anon client)
        auth_res = await asyncio.get_event_loop().run_in_executor(
            None, lambda: auth_client.auth.get_user(req.token)
        )
        if not auth_res.user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
        
        user_id = auth_res.user.id
        email = auth_res.user.email
        
        # Naya password update karo — Supabase admin client se
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.auth.admin.update_user_by_id(
                user_id,
                {"password": req.new_password}
            )
        )
        print(f"[auth.reset_password] Password reset for user: {email}")
        
        # Invalidate all active sessions for security after password change!
        await session_service.revoke_all_sessions(str(user_id))
        
        await audit_service.log(None, str(user_id), email, "auth.password_reset_success", request=request)
        return {"message": "Password updated successfully."}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[auth.reset_password] Error: {str(e)}")
        await audit_service.log(None, None, None, "auth.password_reset_failed", request=request)
        raise HTTPException(status_code=400, detail="Failed to reset password. The link may have expired.")


@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """
    Supabase refresh token se naya access token lo.
    Frontend axios interceptor is endpoint ko call karta hai jab 401 aata hai.
    """
    # Pehle request body check karo, phir cookie
    refresh_tok = req.refresh_token
    
    if not refresh_tok:
        raise HTTPException(status_code=401, detail="No refresh token provided.")
    
    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None, lambda: auth_client.auth.refresh_session(refresh_tok)
        )
        if not res.session:
            raise HTTPException(status_code=401, detail="Refresh token expired. Please log in again.")
        
        return {
            "token": res.session.access_token,
            "refreshToken": res.session.refresh_token,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")


@router.get("/me")
async def get_me(user: Any = Depends(get_current_user)):
    """
    Current logged-in user profile fetch karo.
    """
    if getattr(user, 'id', '') == "demo-user-001" or getattr(user, 'email', '') == "admin@sunriseclinic.com":
        return {
            "email":      getattr(user, 'email', 'admin@sunriseclinic.com'),
            "userId":     "demo-user-001",
            "role":       "owner",
            "clinicId":   "d3b07384-d113-46a6-a719-38cf89235d54",
            "clinicName": "Sunrise Medical Clinic",
            "timezone":   "America/Chicago",
        }
    try:
        email = getattr(user, 'email', 'admin@sunriseclinic.com')
        user_id = str(getattr(user, 'id', 'demo-user-001'))

        # Clinic dhundho
        clinic = None
        try:
            clinic_res = supabase_read.table("clinics").select("id, name, timezone").eq("owner_email", email).execute()
            clinic = clinic_res.data[0] if clinic_res.data else None
        except Exception:
            pass

        # Role dhundho (clinic_users table se)
        role = "owner"  # default
        try:
            if clinic:
                cu_res = supabase_read.table("clinic_users").select("role").eq("supabase_user_id", user_id).eq("clinic_id", clinic["id"]).execute()
                if cu_res.data:
                    role = cu_res.data[0].get("role", "owner")
        except Exception:
            pass

        return {
            "email":      email,
            "userId":     user_id,
            "role":       role,
            "clinicId":   clinic["id"]       if clinic else "d3b07384-d113-46a6-a719-38cf89235d54",
            "clinicName": clinic["name"]     if clinic else "Sunrise Medical Clinic",
            "timezone":   clinic["timezone"] if clinic else "America/Chicago",
        }
    except Exception as e:
        return {
            "email":      getattr(user, 'email', 'admin@sunriseclinic.com'),
            "userId":     "demo-user-001",
            "role":       "owner",
            "clinicId":   "demo-clinic-001",
            "clinicName": "Sunrise Medical Clinic",
            "timezone":   "America/Chicago",
        }


@router.get("/sessions")
async def get_sessions(user: Any = Depends(get_current_user)):
    """
    List all active sessions for the current authenticated user.
    """
    return {"data": await session_service.get_active_sessions(str(user.id))}


@router.post("/sessions/revoke")
async def revoke_session(req: RevokeSessionRequest, user: Any = Depends(get_current_user)):
    """
    Revoke/terminate a specific login session.
    """
    success = await session_service.revoke_session(req.session_id, str(user.id))
    if not success:
        raise HTTPException(status_code=400, detail="Failed to revoke session or session not found.")
    return {"success": True, "message": "Session revoked successfully."}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(user: Any = Depends(get_current_user)):
    """
    Log out of all other devices except this one.
    """
    sessions = await session_service.get_active_sessions(str(user.id))
    current_session_id = sessions[0]["id"] if sessions else None
    
    await session_service.revoke_all_sessions(str(user.id), exclude_session_id=current_session_id)
    return {"success": True, "message": "Logged out from all other devices successfully."}


@router.get("/audit-logs")
async def get_audit_logs(user: Any = Depends(get_current_user), limit: int = 50):
    """
    Fetch real-time audit logs for the user's clinic.
    """
    try:
        clinic_res = supabase_read.table("clinics").select("id").eq("owner_email", user.email).execute()
        if not clinic_res.data:
            return {"data": []}
        
        clinic_id = clinic_res.data[0]["id"]
        
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("audit_logs")
            .select("*")
            .eq("clinic_id", clinic_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"data": res.data or []}
    except Exception as e:
        print(f"[auth.audit_logs] Error: {str(e)}")
        return {"data": []}


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Config & MFA & Google Onboarding Suite
# ─────────────────────────────────────────────────────────────────────────────

def get_user_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header.")
    return auth_header[7:].strip()


# ─── Google Calendar OAuth ──────────────────────────────────────────────
@router.get("/google")
async def google_oauth_redirect(request: Request, token: str = ""):
    """
    Start Google Calendar OAuth flow.
    Frontend calls: GET /auth/google?token=<jwt>
    Redirects user to Google OAuth consent screen.
    """
    from fastapi.responses import RedirectResponse
    import urllib.parse

    # Store JWT in state param so callback can identify clinic
    state = token  # In production use encrypted state

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_oauth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """
    Google OAuth callback — exchanges code for refresh_token and saves to clinic.
    """
    from fastapi.responses import HTMLResponse

    dashboard_url = settings.DASHBOARD_URL or "https://dashboard-two-jade-54.vercel.app"

    if error:
        return HTMLResponse(f'<script>window.location="{dashboard_url}/settings?google=error&msg={error}"</script>')

    if not code:
        return HTMLResponse(f'<script>window.location="{dashboard_url}/settings?google=error&msg=no_code"</script>')

    # Verify state (JWT) to get clinic
    token = state
    clinic_id = None
    try:
        auth_header = f"Bearer {token}"
        mock_req = type("MockReq", (), {"headers": {"authorization": auth_header}})()
        user_data = await get_current_user(mock_req)
        if hasattr(user_data, "email"):
            clinic_res = supabase_read.table("clinics").select("id").eq("owner_email", user_data.email).execute()
            if clinic_res.data:
                clinic_id = clinic_res.data[0]["id"]
    except Exception:
        pass

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                }
            )
        token_data = token_res.json()
        refresh_token = token_data.get("refresh_token")

        if refresh_token and clinic_id:
            from ...core.database import update_clinic
            update_clinic(clinic_id, {
                "google_refresh_token": refresh_token
            })
            print(f"[auth.google] Calendar connected for clinic {clinic_id}")
            return HTMLResponse(f'<script>window.location="{dashboard_url}/settings?google=success&tab=integrations"</script>')
        else:
            return HTMLResponse(f'<script>window.location="{dashboard_url}/settings?google=error&msg=no_refresh_token"</script>')
    except Exception as e:
        print(f"[auth.google.callback] Error: {e}")
        return HTMLResponse(f'<script>window.location="{dashboard_url}/settings?google=error&msg=exchange_failed"</script>')


class MFAEnrollRequest(BaseModel):
    friendly_name: str = "Bytelytic OS"
    factor_type: str = "totp"


class MFAVerifyRequest(BaseModel):
    factor_id: str
    code: str


class MFAUnenrollRequest(BaseModel):
    factor_id: str


class GoogleOnboardingRequest(BaseModel):
    clinicName: str
    specialty: str = ""
    city: str = ""
    timezone: str = "America/Chicago"
    doctorName: str = ""
    doctorCredentials: str = ""
    doctorPhone: str = ""
    businessHours: dict = {}
    appointmentTypes: list = []


@router.get("/config")
async def get_config():
    """
    Serve public Supabase configurations dynamically to the client.
    """
    return {
        "supabaseUrl": settings.SUPABASE_URL,
        "supabaseAnonKey": settings.SUPABASE_ANON_KEY
    }


# GET /mfa/factors — manual Bearer check (no HTTPBearer Depends to avoid 405 conflict)
# Uses /auth/v1/user with x-supabase-api-version: 2024-01-01 to get factors array
# (Supabase deprecated GET /auth/v1/factors; list_factors() internally calls /auth/v1/user)
@router.get("/mfa/factors")
async def get_mfa_factors(request: Request):
    """List enrolled MFA factors for the current user."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}",
        "x-supabase-api-version": "2024-01-01",
    }
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{settings.SUPABASE_URL}/auth/v1/user", headers=headers)
        if res.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        user_data = res.json()
        factors = user_data.get("factors", [])
        totp = [f for f in factors if f.get("factor_type") == "totp"]
        phone = [f for f in factors if f.get("factor_type") == "phone"]
        return {"data": {"all": factors, "totp": totp, "phone": phone}}

@router.post("/mfa/enroll")
async def enroll_mfa(request: Request, user: Any = Depends(get_current_user)):
    """
    Enroll a new MFA factor on behalf of the user.
    """
    token = get_user_token(request)
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}"
    }
    body = {
        "friendly_name": "Bytelytic OS",
        "factor_type": "totp",
        "issuer": "Bytelytic"
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{settings.SUPABASE_URL}/auth/v1/factors", headers=headers, json=body)
        if res.status_code >= 400:
            raise HTTPException(status_code=res.status_code, detail=res.json().get("msg", "Failed to enroll factor."))
        
        data = res.json()
        if data.get("totp") and data["totp"].get("qr_code"):
            qr = data["totp"]["qr_code"]
            if qr.startswith("<svg") or qr.startswith("%3Csvg"):
                import urllib.parse
                if not qr.startswith("%3Csvg"):
                    qr = urllib.parse.quote(qr)
                data["totp"]["qr_code"] = f"data:image/svg+xml;utf-8,{qr}"
        return data


@router.post("/mfa/verify")
async def verify_mfa(req: MFAVerifyRequest, request: Request, user: Any = Depends(get_current_user)):
    """
    Challenge and verify the newly enrolled factor to activate it.
    """
    token = get_user_token(request)
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Challenge factor
        chal_res = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/factors/{req.factor_id}/challenge", 
            headers=headers
        )
        if chal_res.status_code >= 400:
            raise HTTPException(
                status_code=chal_res.status_code, 
                detail=chal_res.json().get("msg", "Failed to challenge factor.")
            )
        
        challenge_id = chal_res.json().get("id")
        
        # 2. Verify code
        body = {
            "challenge_id": challenge_id,
            "code": req.code
        }
        ver_res = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/factors/{req.factor_id}/verify",
            headers=headers,
            json=body
        )
        if ver_res.status_code >= 400:
            raise HTTPException(
                status_code=ver_res.status_code, 
                detail=ver_res.json().get("msg", "Incorrect verification code.")
            )
        
        return ver_res.json()


@router.post("/mfa/unenroll")
async def unenroll_mfa(req: MFAUnenrollRequest, request: Request, user: Any = Depends(get_current_user)):
    """
    Disable and remove an MFA factor for the user.
    """
    token = get_user_token(request)
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}"
    }
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{settings.SUPABASE_URL}/auth/v1/factors/{req.factor_id}", headers=headers)
        if res.status_code >= 400:
            raise HTTPException(status_code=res.status_code, detail=res.json().get("msg", "Failed to disable MFA."))
        return {"success": True, "message": "MFA factor removed successfully."}


@router.post("/google-onboarding")
async def google_onboarding(req: GoogleOnboardingRequest, request: Request, user: Any = Depends(get_current_user)):
    """
    Onboards a user who signed up via Google OAuth but does not have a clinic yet.
    1. Create Clinic Record
    2. Provision phone number + Retell agent (best effort)
    3. Register session & audit log
    """
    email = user.email
    user_id = str(user.id)
    
    # Check if clinic already exists
    clinic_res = supabase_read.table("clinics").select("id").eq("owner_email", email).execute()
    if clinic_res.data:
        raise HTTPException(status_code=400, detail="Clinic already exists for this account.")
        
    print(f"[auth.google-onboarding] Onboarding Google user {email} with clinic {req.clinicName}")
    
    # ── Step 1: Create Clinic record ───────────────────────────────
    try:
        raw_appts = req.appointmentTypes or []
        cleaned_appts = []
        if isinstance(raw_appts, list):
            for a in raw_appts:
                if isinstance(a, dict) and a.get("name"):
                    dur = a.get("duration_minutes") or a.get("duration") or 30
                    try:
                        dur = max(5, int(dur))
                    except (ValueError, TypeError):
                        dur = 30
                    fee_v = a.get("fee") if a.get("fee") is not None else a.get("price", 0)
                    try:
                        fee_v = max(0.0, float(fee_v))
                    except (ValueError, TypeError):
                        fee_v = 0.0
                    cleaned_appts.append({
                        "name": str(a.get("name")).strip(),
                        "duration": dur,
                        "duration_minutes": dur,
                        "fee": fee_v
                    })
        final_appt_types = cleaned_appts if cleaned_appts else [
            {"name": "Initial Evaluation", "duration": 60, "duration_minutes": 60, "fee": 150.0},
            {"name": "Follow-up", "duration": 30, "duration_minutes": 30, "fee": 75.0}
        ]

        c_insert = supabase.table("clinics").insert({
            "name": req.clinicName,
            "owner_email": email,
            "timezone": req.timezone or "America/Chicago",
            "specialty": req.specialty,
            "city": req.city,
            "primary_doctor_name": req.doctorName,
            "primary_doctor_credentials": req.doctorCredentials,
            "primary_doctor_phone": req.doctorPhone,
            "business_hours": req.businessHours,
            "appointment_types": final_appt_types
        }).execute()
        
        if not c_insert.data:
            raise Exception("Failed to insert clinic record")
            
        clinic = c_insert.data[0]
        clinic_id = clinic["id"]
        
    except Exception as db_e:
        print(f"[auth.google-onboarding] Database error creating clinic: {str(db_e)}")
        raise HTTPException(status_code=500, detail="Failed to create clinic record.")
        
    # ── Step 2: Provisioning (Deferred under Lazy Model A) ────
    clinic["phone_number"] = None
    clinic["retell_agent_id"] = None
        
    # ── Step 3: Session & Auditing ────────────────────────
    x_forwarded_for = request.headers.get("x-forwarded-for")
    ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else (request.client.host if request.client else "unknown")
    ua = request.headers.get("user-agent")
    
    await session_service.create_session(user_id, email, clinic_id, ip, ua)
    await audit_service.log(clinic_id, user_id, email, "auth.signup_success", request=request)
    
    token = get_user_token(request)
    
    return {
        "token": token,
        "clinicId": clinic_id,
        "clinicName": clinic["name"],
        "timezone": clinic["timezone"],
        "role": "owner",
        "userEmail": email,
        "userId": user_id
    }



