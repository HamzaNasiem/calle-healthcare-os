import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import (
    require_permission,
    get_password_hash,
    validate_password_strength,
)
from src.db.engine import get_db
from src.models.user import User
from src.schemas.users import (
    UserCreateRequest,
    UserUpdateRequest,
    UserInfo,
    UserListData,
    UserListResponse,
)
from src.services.audit_service import audit_service
from src.core.exceptions import APIException

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", response_model=UserListResponse)
async def list_users(
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(
        User.tenant_id == user.tenant_id,
        User.is_deleted == False
    ).order_by(User.created_at.desc())
    res = await db.execute(stmt)
    db_users = res.scalars().all()
    
    out = [
        UserInfo(
            id=u.id,
            email=u.email,
            role=u.role,
            full_name=u.full_name,
            is_active=u.is_active,
            last_login_at=u.last_login_at
        ) for u in db_users
    ]
    return UserListResponse(success=True, data=UserListData(users=out))

@router.post("", response_model=UserInfo, status_code=201)
async def create_user(
    req: UserCreateRequest,
    request: Request,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    # Check if user already exists
    existing_stmt = select(User).where(User.email == req.email)
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalars().first():
        raise APIException("VALIDATION_ERROR", "User with this email already exists.", 400)
        
    try:
        validate_password_strength(req.password)
    except ValueError as e:
        raise APIException("VALIDATION_ERROR", str(e), 400)
        
    new_user = User(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        email=req.email,
        role=req.role,
        full_name=req.full_name,
        hashed_password=get_password_hash(req.password),
        is_active=True
    )
    db.add(new_user)
    await db.flush()
    
    await audit_service.log(
        action="CREATE_USER",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="users",
        target_id=new_user.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason=f"Owner created user {new_user.email} with role {new_user.role}",
        outcome="SUCCESS"
    )
    
    await db.commit()
    
    return UserInfo(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        full_name=new_user.full_name,
        is_active=new_user.is_active,
        last_login_at=new_user.last_login_at
    )

@router.patch("/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: uuid.UUID,
    req: UserUpdateRequest,
    request: Request,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    target_user = res.scalars().first()
    
    if not target_user:
        raise APIException("RESOURCE_NOT_FOUND", "User not found.", 404)
        
    if req.full_name is not None:
        target_user.full_name = req.full_name
    if req.role is not None:
        target_user.role = req.role
    if req.is_active is not None:
        target_user.is_active = req.is_active
        
    await audit_service.log(
        action="UPDATE_USER",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="users",
        target_id=target_user.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason=f"Owner updated user {target_user.email}",
        outcome="SUCCESS"
    )
    
    await db.commit()
    
    return UserInfo(
        id=target_user.id,
        email=target_user.email,
        role=target_user.role,
        full_name=target_user.full_name,
        is_active=target_user.is_active,
        last_login_at=target_user.last_login_at
    )

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission(["owner"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    res = await db.execute(stmt)
    target_user = res.scalars().first()
    
    if not target_user:
        raise APIException("RESOURCE_NOT_FOUND", "User not found.", 404)
        
    # Prevent owner from deleting themselves
    if target_user.id == user.id:
        raise APIException("VALIDATION_ERROR", "You cannot delete your own account.", 400)
        
    target_user.is_deleted = True
    target_user.is_active = False
    
    await audit_service.log(
        action="DELETE_USER",
        actor_id=user.id,
        tenant_id=user.tenant_id,
        target_table="users",
        target_id=target_user.id,
        ingress_ip=request.client.host if request.client else "unknown",
        change_reason=f"Owner deleted user {target_user.email}",
        outcome="SUCCESS"
    )
    
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
