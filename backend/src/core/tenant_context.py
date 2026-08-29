"""
Tenant Context
Implements strict tenant isolation using ContextVar.
This ensures the tenant_id is available anywhere in the coroutine hierarchy.
"""
from contextvars import ContextVar
from uuid import UUID

# Per-coroutine context — not shared across async tasks
_current_tenant_id: ContextVar[UUID | None] = ContextVar(
    'current_tenant_id',
    default=None
)

def get_tenant_id() -> UUID:
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise RuntimeError("Tenant context not set — unauthenticated request")
    return tenant_id

def set_tenant_id(tenant_id: UUID) -> None:
    _current_tenant_id.set(tenant_id)
