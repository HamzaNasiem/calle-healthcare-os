import asyncio
import base64
import io
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pyotp
import qrcode
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import local_cache

# Additional custom error from our contract
from src.core.exceptions import APIException
from src.core.logger import log
from src.core.security import (
    create_access_token,
    get_current_user_with_role,
    require_permission,
    verify_password,
)
from src.core.tenant_context import set_tenant_id
from src.db.engine import get_db
from src.middleware.rate_limit import limiter
from src.models.user import User
from src.models.user_session import UserSession

# Import strict schemas
from src.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LoginResponseData,
    MfaSetupData,
    MfaSetupResponse,
    MfaVerifyRequest,
    SessionInfo,
    SessionsResponse,
    SessionsResponseData,
    TokenData,
    TokenResponse,
    UserResponse,
    MeResponse,
)
from src.schemas.common import GenericResponse, GenericResponseData
from src.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
@limiter.limit("50/minute")
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == req.email)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        # Cannot log to audit chain without a valid tenant_id — just log warning
        log_ip = request.client.host if request.client else "unknown"
        log.warning(f"[Auth] Failed login attempt for unknown email from {log_ip}")
        raise APIException("AUTH_INVALID_CREDENTIALS", "Invalid email or password.", 401)
        
    if user.locked_until and user.locked_until > datetime.now(UTC):
        raise APIException("AUTH_ACCOUNT_LOCKED", f"Account locked until {user.locked_until}", 423)

    if not verify_password(req.password, user.hashed_password):
        user.failed_login_count += 1
        # Set tenant context so audit chain can write to correct tenant DB
        set_tenant_id(user.tenant_id)
        log_ip = request.client.host if request.client else "unknown"

        if user.failed_login_count >= 5:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
            await audit_service.log(
                action="USER_LOCKED",
                actor_id=user.id,
                target_table="users",
                target_id=user.id,
                actor_type="system",
                ingress_ip=log_ip,
                change_reason="5 failed login attempts",
                outcome="SUCCESS"
            )
        await db.commit()
        await audit_service.log(
            action="FAILED_LOGIN",
            actor_id=user.id,
            target_table="users",
            target_id=user.id,
            actor_type="user",
            ingress_ip=log_ip,
            change_reason="Invalid password",
            outcome="FAILURE"
        )
        # Check brute force attack
        from src.services.breach_service import breach_service
        await breach_service.detect_brute_force(
            db=db,
            tenant_id=user.tenant_id,
            email=user.email,
            ip_address=log_ip
        )
        raise APIException("AUTH_INVALID_CREDENTIALS", "Invalid email or password.", 401)
        
    # Reset lock and update last login
    if user.failed_login_count > 0:
        user.failed_login_count = 0
        user.locked_until = None

    user.last_login_at = datetime.now(UTC)

    # STEP 8 FIX: Enforce MFA at the API level — do NOT bypass if user has MFA enabled.
    if user.mfa_enabled:
        await db.commit()
        # Store user_id in cache keyed by a one-time mfa_token (5 min TTL)
        mfa_token = secrets.token_urlsafe(32)
        local_cache.set(f"mfa_step_{mfa_token}", str(user.id), ttl=300)

        set_tenant_id(user.tenant_id)
        asyncio.create_task(audit_service.log(
            action="MFA_CHALLENGE_ISSUED",
            actor_id=user.id,
            target_table="users",
            target_id=user.id,
            actor_type="user",
            actor_email=user.email,
            actor_role=user.role,
            ingress_ip=request.client.host if request.client else "unknown",
            change_reason="MFA required — challenge issued",
            outcome="PENDING"
        ))

        from fastapi.responses import JSONResponse
        mfa_response = LoginResponse(
            success=True,
            data=LoginResponseData(
                mfa_required=True,
                mfa_setup_needed=False,
                mfa_token=mfa_token,
                user_id=user.id,
                access_token=None
            )
        )
        return JSONResponse(content=mfa_response.model_dump(mode='json'))

    # No MFA — issue full session directly
    session_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    
    new_session = UserSession(
        session_id=session_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("User-Agent", "unknown"),
        expires_at=expires_at,
        is_active=True
    )
    db.add(new_session)
    await db.commit()
    
    # Initialize idle timeout session in cache (3 mins)
    local_cache.set(f"sess_active:{session_id}", "active", ttl=180)

    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role, "sid": session_id},
        expires_delta=timedelta(minutes=15)
    )
    refresh_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role, "type": "refresh", "sid": session_id},
        expires_delta=timedelta(days=7)
    )

    set_tenant_id(user.tenant_id)
    asyncio.create_task(audit_service.log(
        action="SUCCESSFUL_LOGIN",
        actor_id=user.id,
        target_table="users",
        target_id=user.id,
        actor_type="user",
        actor_email=user.email,
        actor_role=user.role,
        session_id=session_id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason="Login without MFA (MFA not configured)",
        outcome="SUCCESS"
    ))
    
    login_response = LoginResponse(
        success=True,
        data=LoginResponseData(
            mfa_required=False,
            mfa_setup_needed=False,
            mfa_token=None,
            user_id=user.id,
            access_token=access_token
        )
    )
    from fastapi.responses import JSONResponse
    response = JSONResponse(content=login_response.model_dump(mode='json'))
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days in seconds
    )
    return response

class MfaSetupRequest(BaseModel):
    mfa_token: str

@router.post("/mfa/setup", response_model=MfaSetupResponse)
@limiter.limit("15/minute")
async def setup_mfa(req: MfaSetupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Generate QR code and backup codes for first-time MFA setup. Requires mfa_token."""
    user_id_str = local_cache.get(f"mfa_step_{req.mfa_token}")
    if not user_id_str:
        raise APIException("AUTH_MFA_INVALID", "Invalid or expired MFA token.", 401)
        
    stmt = select(User).where(User.id == uuid.UUID(user_id_str))
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise APIException("VALIDATION_ERROR", "User not found.", 400)
        
    if user.mfa_enabled:
        raise APIException("VALIDATION_ERROR", "MFA is already enabled.", 400)
        
    # Generate new secret
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    
    # Generate 8 backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
    user.mfa_backup_codes = json.dumps(backup_codes)
    
    await db.commit()
    
    # Generate QR Code image
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="ByteLytic OS")
    qr = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return MfaSetupResponse(
        success=True,
        data=MfaSetupData(
            qr_code_url=qr_b64,
            manual_entry_key=secret,
            backup_codes=backup_codes
        )
    )

class MFASetupVerifyRequest(BaseModel):
    mfa_token: str
    totp_code: str

@router.post("/mfa/setup/verify", response_model=GenericResponse)
@limiter.limit("30/minute")
async def verify_mfa_setup(req: MFASetupVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Confirm the first-time MFA setup."""
    user_id_str = local_cache.get(f"mfa_step_{req.mfa_token}")
    if not user_id_str:
        raise APIException("AUTH_MFA_INVALID", "Invalid or expired MFA token.", 401)
        
    stmt = select(User).where(User.id == uuid.UUID(user_id_str))
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise APIException("VALIDATION_ERROR", "User not found.", 400)
    if not user.mfa_secret:
        raise APIException("VALIDATION_ERROR", "MFA setup not initiated.", 400)
        
    totp = pyotp.TOTP(user.mfa_secret)
    # STEP 6 FIX: Removed "123456" backdoor — all TOTP codes must now be cryptographically verified.
    if not totp.verify(req.totp_code, valid_window=6):
        raise APIException("AUTH_MFA_INVALID", "Invalid TOTP code.", 401)
        
    user.mfa_enabled = True
    await db.commit()
    
    return GenericResponse(success=True, data=GenericResponseData(message="MFA enabled successfully."))

@router.post("/mfa/verify", response_model=TokenResponse)
@limiter.limit("50/minute")
async def verify_mfa(req: MfaVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user_id_str = local_cache.get(f"mfa_step_{req.mfa_token}")
    if not user_id_str:
        raise APIException("AUTH_MFA_INVALID", "Invalid or expired MFA token.", 401)
        
    stmt = select(User).where(User.id == uuid.UUID(user_id_str))
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user or not user.mfa_enabled or not user.mfa_secret:
        # STEP 1 FIX: Removed print(user.email) — never log PHI (email) to stdout.
        log.warning("[Auth] MFA verify attempt for user_id=%s — MFA not configured", user.id if user else "unknown")
        raise APIException("VALIDATION_ERROR", "MFA not enabled or user not found.", 400)
    else:
        totp = pyotp.TOTP(user.mfa_secret)
        # STEP 6 FIX: Removed "123456" backdoor — TOTP must be cryptographically valid.
        is_valid_totp = totp.verify(req.totp_code, valid_window=6)
    
    used_backup_code = False
    
    if not is_valid_totp:
        # Check backup codes
        backup_codes_str = user.mfa_backup_codes
        if backup_codes_str:
            try:
                backup_codes = json.loads(backup_codes_str)
                if req.totp_code in backup_codes:
                    is_valid_totp = True
                    used_backup_code = True
                    # Remove the used backup code
                    backup_codes.remove(req.totp_code)
                    user.mfa_backup_codes = json.dumps(backup_codes)
            except json.JSONDecodeError:
                pass
                
    if not is_valid_totp:
        set_tenant_id(user.tenant_id)
        await audit_service.log(
            action="FAILED_LOGIN",
            actor_id=user.id,
            target_table="users",
            target_id=user.id,
            actor_type="user",
            ingress_ip=request.client.host if request.client else "unknown",
            change_reason="Invalid MFA code",
            outcome="FAILURE"
        )
        raise APIException("AUTH_MFA_INVALID", "Invalid or expired verification code.", 401)
        
    # Valid! Consume token
    local_cache.invalidate(f"mfa_step_{req.mfa_token}")
        
    # Update last login
    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = request.client.host if request.client else "unknown"
    
    # Create DB Session record
    session_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    
    new_session = UserSession(
        session_id=session_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("User-Agent", "unknown"),
        expires_at=expires_at,
        is_active=True
    )
    db.add(new_session)
    await db.commit()
    
    # Initialize idle timeout session in cache (3 mins)
    local_cache.set(f"sess_active:{session_id}", "active", ttl=180)
    
    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role, "sid": session_id},
        expires_delta=timedelta(minutes=15)
    )
    refresh_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role, "type": "refresh", "sid": session_id},
        expires_delta=timedelta(days=7)
    )
    
    set_tenant_id(user.tenant_id)
    await audit_service.log(
        action="SUCCESSFUL_LOGIN",
        actor_id=user.id,
        target_table="users",
        target_id=user.id,
        actor_type="user",
        actor_email=user.email,
        actor_role=user.role,
        session_id=session_id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason="Used backup code" if used_backup_code else "Used TOTP",
        outcome="SUCCESS"
    )
    
    # Set refresh token as httpOnly cookie (HIPAA: never expose refresh token in response body)
    token_response = TokenResponse(
        success=True,
        data=TokenData(
            access_token=access_token,
            expires_in=900,
            user=UserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                tenant_id=user.tenant_id,
                full_name=user.full_name or ""
            )
        )
    )
    
    # Return response with httpOnly cookie for refresh token
    from fastapi.responses import JSONResponse
    response = JSONResponse(content=token_response.model_dump(mode='json'))
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days in seconds
    )
    return response

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("5/minute")
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    # Simulating extracting from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise APIException("AUTH_REFRESH_EXPIRED", "Missing refresh token", 401)
    
    # Decode and validate refresh token
    from src.core.security import decode_access_token
    try:
        payload = decode_access_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError()
    except Exception:
        raise APIException("AUTH_REFRESH_EXPIRED", "Invalid refresh token", 401)

    # Issue new access token
    access_token = create_access_token(
        data={"sub": payload.get("sub"), "tenant_id": payload.get("tenant_id"), "role": payload.get("role"), "sid": payload.get("sid")},
        expires_delta=timedelta(minutes=15)
    )
    # Issue new refresh token (rotation)
    new_refresh_token = create_access_token(
        data={"sub": payload.get("sub"), "tenant_id": payload.get("tenant_id"), "role": payload.get("role"), "type": "refresh", "sid": payload.get("sid")},
        expires_delta=timedelta(days=7)
    )
    
    token_response = TokenResponse(
        success=True,
        data=TokenData(
            access_token=access_token,
            expires_in=900
        )
    )
    
    from fastapi.responses import JSONResponse
    response = JSONResponse(content=token_response.model_dump(mode='json'))
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60
    )
    return response

@router.post("/logout", response_class=Response, status_code=204)
async def logout(request: Request, db: AsyncSession = Depends(get_db), response: Response = None):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if token:
        local_cache.set(f"blacklist_{token}", "true", ttl=15*60)
        
        # Decode token to get session_id and user_id
        from src.core.security import decode_access_token
        try:
            payload = decode_access_token(token)
            sid = payload.get("sid")
            uid = payload.get("sub")
            tid = payload.get("tenant_id")
            role = payload.get("role")
            
            if sid and tid:
                # 1. Clear session from DB
                stmt = select(UserSession).where(
                    UserSession.session_id == sid,
                    UserSession.tenant_id == uuid.UUID(tid)
                )
                result = await db.execute(stmt)
                session = result.scalars().first()
                if session:
                    session.is_active = False
                    session.revoked_at = datetime.now(UTC)
                    session.revoke_reason = "user_logout"
                    await db.commit()
                
                # 2. Clear from Cache
                local_cache.invalidate(f"sess_active:{sid}")
                
                # 3. Audit Log
                set_tenant_id(uuid.UUID(tid))
                await audit_service.log(
                    action="LOGOUT",
                    actor_id=uuid.UUID(uid),
                    target_table="user_sessions",
                    actor_type="user",
                    actor_role=role,
                    session_id=sid,
                    change_reason="User manually logged out",
                    outcome="SUCCESS"
                )
        except Exception as e:
            log.warning(f"[Auth] Logout session invalidation failed: {e}")

    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie("refresh_token")
    return resp

@router.get("/sessions", response_model=SessionsResponse)
async def get_sessions(request: Request, user: User = Depends(get_current_user_with_role), db: AsyncSession = Depends(get_db)):
    """List all active sessions for the user's tenant."""
    stmt = select(UserSession).where(
        UserSession.tenant_id == user.tenant_id,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.now(UTC)
    ).order_by(UserSession.last_active_at.desc())
    
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    
    session_infos = [
        SessionInfo(
            session_id=s.session_id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at,
            last_active_at=s.last_active_at,
            is_current=False # Simplify for now
        ) for s in sessions
    ]
    
    return SessionsResponse(
        success=True,
        data=SessionsResponseData(sessions=session_infos)
    )

@router.delete("/sessions/{session_id}", response_class=Response, status_code=204)
async def revoke_session(
    session_id: str, 
    user: User = Depends(require_permission(["owner"])), 
    db: AsyncSession = Depends(get_db)
):
    """Owner can revoke any active session remotely."""
    stmt = select(UserSession).where(
        UserSession.session_id == session_id,
        UserSession.tenant_id == user.tenant_id
    )
    result = await db.execute(stmt)
    session = result.scalars().first()
    
    if not session:
        raise APIException("RESOURCE_NOT_FOUND", "Session not found.", 404)
        
    session.is_active = False
    session.revoked_at = datetime.now(UTC)
    session.revoke_reason = "force_revoke_by_owner"
    
    await db.commit()
    
    set_tenant_id(user.tenant_id)
    await audit_service.log(
        action="REVOKE_SESSION",
        actor_id=user.id,
        target_table="user_sessions",
        actor_type="user",
        actor_role=user.role,
        change_reason=f"Session revoked by owner {user.id}",
        outcome="SUCCESS"
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/me", response_model=MeResponse)
async def get_me(user: User = Depends(get_current_user_with_role), db: AsyncSession = Depends(get_db)):
    """Get active authenticated user details and active clinic config"""
    from src.models.tenant import Tenant
    from src.models.tenant_settings import TenantSettings
    
    tenant = await db.get(Tenant, user.tenant_id)
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id)
    settings = (await db.execute(stmt)).scalars().first()
    
    return MeResponse(
        userId=user.id,
        email=user.email,
        role=user.role,
        clinicId=user.tenant_id,
        clinicName=tenant.name if tenant else "ByteLytic Clinic",
        timezone=settings.timezone if settings else "America/Chicago"
    )
