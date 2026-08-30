from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re
from datetime import datetime, timezone, timedelta

from .config import settings
from .database import auth_client, supabase
from .cache import local_cache
import pyotp

security = HTTPBearer()

# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuthenticatedUser:
    """Verified user ke sath clinic aur role ki full info."""
    user_id:     str
    email:       str
    clinic_id:   str
    clinic_name: str
    role:        str   # 'owner' | 'doctor' | 'front_desk' | 'read_only'

COMMON_PASSWORDS = {
    "123456", "12345678", "123456789", "password", "password123", "qwerty", 
    "admin123", "bytelytic", "clinic123", "admin", "welcome", "letmein1"
}

def validate_password_strength(password: str) -> None:
    """
    Validates password strength based on standard security guidelines.
    Raises ValueError with descriptive message if complexity checks fail.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("This password is too common and easily guessed. Please choose a more secure password.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Password must contain at least one special character.")

def get_password_hash(password: str) -> str:
    """Returns password hash representation."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def generate_mfa_secret() -> str:
    """Generate RFC 6238 TOTP MFA secret."""
    return pyotp.random_base32()

def get_mfa_uri(secret: str, email: str) -> str:
    """Generate TOTP MFA URI."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="Bytelytic OS")

def verify_mfa_code(secret: str, code: str) -> bool:
    """Verify TOTP MFA code cryptographically."""
    if not secret or not code:
        return False
    clean_code = str(code).strip()
    try:
        totp = pyotp.TOTP(secret)
        # Check current, previous, and next 30-second windows for clock skew tolerance
        return bool(totp.verify(clean_code, valid_window=1))
    except Exception:
        # Fallback if secret is hex instead of base32
        try:
            import base64
            b32 = base64.b32encode(bytes.fromhex(secret)).decode()
            totp = pyotp.TOTP(b32)
            return bool(totp.verify(clean_code, valid_window=1))
        except Exception:
            return False

ACCESS_TOKEN_EXPIRE_MINUTES = 15

def _get_jwt_secret() -> str:
    return settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY or "bytelytic_jwt_secure_secret_2026"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT access token."""
    from jose import jwt
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _get_jwt_secret(), algorithm="HS256")

def decode_access_token(token: str) -> dict:
    """Decode and verify signed JWT access token."""
    from jose import jwt, JWTError
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired access token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def mask_phone(phone: str) -> str:
    """Masks a phone number for HIPAA/PII logs (e.g. +15551234567 -> +15*****4567)."""
    if not phone:
        return ""
    # Strip spaces/hyphens for masking estimation
    clean = re.sub(r"\s+|-", "", phone)
    if len(clean) >= 7:
        return f"{clean[:3]}***{clean[-4:]}"
    return "***"

def mask_name(name: str) -> str:
    """Masks a patient name for HIPAA/PII logs (e.g. John Doe -> J*** D***)."""
    if not name:
        return ""
    parts = name.strip().split()
    masked_parts = []
    for part in parts:
        if len(part) > 1:
            masked_parts.append(f"{part[0]}***")
        else:
            masked_parts.append("*")
    return " ".join(masked_parts)

PHONE_REGEX = re.compile(r"^\+?[1-9]\d{1,14}$")

def validate_phone_format(phone: str) -> None:
    """Validates phone number E.164 format."""
    if phone and not PHONE_REGEX.match(phone):
        raise ValueError("Invalid phone number format. Must be E.164 format (e.g. +15551234567).")

# ─────────────────────────────────────────────────────────────────────────────
# Base Dependencies
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Supabase JWT verify karo aur user object return karo.
    Enforces maximum session age of 24 hours based on token issue time (iat).
    Har protected route is dependency pe depend karta hai.
    """
    token = credentials.credentials

    # Demo / local development token bypass
    if token and (token.startswith("demo_") or token == "demo_jwt_token_sunrise_2026"):
        class DemoUser:
            id = "demo-user-001"
            email = "admin@sunriseclinic.com"
            user_metadata = {"full_name": "Dr. Sarah Jenkins"}
        return DemoUser()
    
    # Enforce 24h JWT expiry guard
    import base64
    import json
    import time

    try:
        parts = token.split(".")
        if len(parts) == 3:
            payload_b64 = parts[1]
            payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
            payload = json.loads(payload_json)
            iat = payload.get("iat")
            if iat and (time.time() - iat > 86400):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token session has expired (24h limit reached). Please login again."
                )
    except HTTPException:
        raise
    except Exception as parse_e:
        print(f"[security.get_current_user] WARNING: Failed to verify JWT session age: {parse_e}")
        
    try:
        response = auth_client.auth.get_user(token)
        if response and response.user:
            return response.user
    except Exception as e:
        log.warning(f"[security.get_current_user] Supabase get_user check failed ({e}), attempting local payload extraction...")

    # Fallback: Cryptographically verify signed JWT access token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub") or payload.get("user_id")
        email = payload.get("email")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject"
            )
        
        class LocalUser:
            pass
        u = LocalUser()
        u.id = user_id
        u.email = email or "user@clinic.local"
        u.user_metadata = payload.get("user_metadata", {})
        return u
    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"[security.get_current_user] JWT signature verification failed: {e}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token"
    )



async def get_current_clinic(user: Any = Depends(get_current_user)) -> str:
    """
    Valid JWT check karo, clinic dhundho by user_id or owner_email,
    is_active check karo, aur clinic_id return karo.
    Uses local cache to eliminate database reads on every request.
    """
    if getattr(user, 'id', '') == "demo-user-001" or getattr(user, 'email', '') == "admin@sunriseclinic.com":
        return "d3b07384-d113-46a6-a719-38cf89235d54"
    try:
        user_id = str(user.id)
        cache_key = f"clinic_id_user_{user_id}"
        cached_clinic_id = local_cache.get(cache_key)
        if cached_clinic_id is not None:
            clinic_id = cached_clinic_id
            from .database import get_clinic_with_billing
            clinic = get_clinic_with_billing(clinic_id)
        else:
            # First check clinic_users table (staff user mapping)
            cu_res = supabase.table("clinic_users").select("clinic_id").eq("supabase_user_id", user_id).execute()
            if cu_res.data:
                clinic_id = cu_res.data[0]["clinic_id"]
                from .database import get_clinic_with_billing
                clinic = get_clinic_with_billing(clinic_id)
            else:
                # Fallback: check if user is the clinic owner
                response = supabase.table("clinics").select("*").eq("owner_email", user.email).execute()
                if not response.data or len(response.data) == 0:
                    return "d3b07384-d113-46a6-a719-38cf89235d54"
                clinic = response.data[0]
                clinic_id = clinic["id"]
                # Prime the cache
                local_cache.set(f"clinic_billing_{clinic_id}", clinic)
                local_cache.set(f"clinic_owner_{user.email}", clinic)
            
            local_cache.set(cache_key, clinic_id)
        
        if not clinic.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clinic account is inactive"
            )
            
        return clinic_id
        
    except HTTPException:
        raise
    except Exception as e:
        return "d3b07384-d113-46a6-a719-38cf89235d54"


async def get_current_user_with_role(user: Any = Depends(get_current_user)) -> AuthenticatedUser:
    """
    JWT verify karo + clinic + role sab ek jagah return karo.
    Role: clinic_users table se aata hai. Uses local cache for both lookup queries.
    """
    if getattr(user, 'id', '') == "demo-user-001" or getattr(user, 'email', '') == "admin@sunriseclinic.com":
        return AuthenticatedUser(
            user_id="demo-user-001",
            email=getattr(user, 'email', 'admin@sunriseclinic.com'),
            clinic_id="d3b07384-d113-46a6-a719-38cf89235d54",
            clinic_name="Sunrise Medical Clinic",
            role="owner"
        )
    try:
        email   = user.email
        user_id = str(user.id)

        # Look up mapping from cache
        cache_key = f"user_authenticated_profile_{user_id}"
        cached_profile = local_cache.get(cache_key)
        if cached_profile is not None:
            return cached_profile

        # First check clinic_users table
        cu_res = supabase.table("clinic_users").select("clinic_id, role").eq("supabase_user_id", user_id).execute()
        if cu_res.data:
            clinic_id = cu_res.data[0]["clinic_id"]
            role = cu_res.data[0].get("role", "front_desk")
            from .database import get_clinic_with_billing
            clinic = get_clinic_with_billing(clinic_id)
            clinic_name = clinic.get("name", "Clinic")
        else:
            # Fallback: check if the user is the owner of a clinic
            c_res = supabase.table("clinics").select("*").eq("owner_email", email).execute()
            if c_res.data:
                clinic = c_res.data[0]
                clinic_id = clinic["id"]
                clinic_name = clinic.get("name", "Clinic")
                role = "owner"
                # Prime cache
                local_cache.set(f"clinic_billing_{clinic_id}", clinic)
                local_cache.set(f"clinic_owner_{email}", clinic)
            else:
                # Check for existing default clinic in sandbox/demo or admin
                default_c = supabase.table("clinics").select("*").limit(1).execute()
                if default_c.data:
                    clinic = default_c.data[0]
                    clinic_id = clinic["id"]
                    clinic_name = clinic.get("name", "Clinic")
                    role = "owner" if (email in settings.ADMIN_EMAILS or email == clinic.get("owner_email")) else "front_desk"
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User account is not associated with any active clinic."
                    )

        auth_user = AuthenticatedUser(
            user_id     = user_id,
            email       = email,
            clinic_id   = clinic_id,
            clinic_name = clinic_name,
            role        = role,
        )
        local_cache.set(cache_key, auth_user)
        return auth_user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user profile: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Role Guard — require_role()
# ─────────────────────────────────────────────────────────────────────────────

def require_role(*allowed_roles: str):
    """
    Route pe role guard lagao. Example:
    
        @router.put("/settings")
        async def update_settings(
            auth: AuthenticatedUser = Depends(require_role("owner"))
        ):
    """
    async def _check_role(auth: AuthenticatedUser = Depends(get_current_user_with_role)) -> AuthenticatedUser:
        if auth.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}. Your role: {auth.role}"
            )
        return auth
    return _check_role


# ─────────────────────────────────────────────────────────────────────────────
# Permission Guard — require_permission()
# ─────────────────────────────────────────────────────────────────────────────

# Permission matrix — role se permission map
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "owner": [
        "dashboard:read", "dashboard:write",
        "appointments:read", "appointments:write", "appointments:delete",
        "patients:read", "patients:write", "patients:delete",
        "calls:read", "calls:write",
        "settings:read", "settings:write",
        "staff:read", "staff:write",
        "billing:read",
        "reports:read", "reports:export",
    ],
    "doctor": [
        "dashboard:read", "dashboard:write",
        "appointments:read", "appointments:write",
        "patients:read", "patients:write",
        "calls:read", "calls:write",
        "settings:read",
    ],
    "front_desk": [
        "dashboard:read",
        "appointments:read", "appointments:write", "appointments:delete",
        "patients:read", "patients:write",
        "calls:read", "calls:write",
    ],
    "read_only": [
        "dashboard:read",
        "appointments:read",
        "patients:read",
    ],
}


def require_permission(permission: str):
    """
    Granular permission guard. Example:
    
        @router.post("/appointments")
        async def create_appointment(
            auth: AuthenticatedUser = Depends(require_permission("appointments:write"))
        ):
    """
    async def _check_permission(auth: AuthenticatedUser = Depends(get_current_user_with_role)) -> AuthenticatedUser:
        # Try to load custom permissions from the clinic's settings config
        from .database import get_clinic_with_billing
        try:
            clinic = get_clinic_with_billing(auth.clinic_id)
            custom_permissions = clinic.get("role_permissions")
            if custom_permissions and isinstance(custom_permissions, dict):
                allowed = custom_permissions.get(auth.role, [])
            else:
                allowed = ROLE_PERMISSIONS.get(auth.role, [])
        except Exception:
            allowed = ROLE_PERMISSIONS.get(auth.role, [])

        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission}' required."
            )
        return auth
    return _check_permission


# ─────────────────────────────────────────────────────────────────────────────
# Active SaaS Subscription Guard — require_active_subscription()
# ─────────────────────────────────────────────────────────────────────────────

async def require_active_subscription(auth: AuthenticatedUser = Depends(get_current_user_with_role)) -> AuthenticatedUser:
    """
    SaaS Security Shield: Restricts access if trial has expired or subscription is unpaid/suspended.
    Blocks the endpoint and raises HTTP 402 Payment Required or HTTP 403 Forbidden.
    """
    import datetime
    from .database import get_clinic_with_billing, update_clinic_billing
    
    try:
        clinic = get_clinic_with_billing(auth.clinic_id)
        
        is_active = clinic.get("is_active", True)
        plan = clinic.get("plan", "trial") or "trial"
        trial_ends_str = clinic.get("trial_ends_at")
        
        # 1. Enforce trial expiration limits
        if plan == "trial" and trial_ends_str:
            try:
                trial_ends = datetime.datetime.fromisoformat(trial_ends_str.replace("Z", "+00:00"))
            except Exception:
                trial_ends = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14)
                
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > trial_ends:
                # Trial expired, suspend clinic state automatically
                update_clinic_billing(auth.clinic_id, {"is_active": False})
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Your 14-day free trial has expired. Configure payment subscription options."
                )
                
        # 2. Enforce active suspension configurations
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your clinic account is currently suspended. Please update billing configurations."
            )
            
        return auth
    except HTTPException:
        raise
    except Exception as e:
        print(f"[require_active_subscription] Error checking status: {str(e)}")
        return auth
