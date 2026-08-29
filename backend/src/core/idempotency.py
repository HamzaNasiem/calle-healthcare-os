from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.exceptions import APIException
from src.models.idempotency import IdempotencyKey


def idempotent(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Extract request and db from kwargs
        request: Request = kwargs.get("request")
        db: AsyncSession = kwargs.get("db")
        
        if not request or not db:
            # If not injected, just run the function
            return await func(*args, **kwargs)
            
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # Enforce idempotency key presence
            raise APIException("MISSING_IDEMPOTENCY_KEY", "Idempotency-Key header is required for this operation", 400)
            
        # Get tenant_id from user if available
        user = kwargs.get("user")
        tenant_id = getattr(user, "tenant_id", None) if user else None
        
        # Check if key exists
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.key == idempotency_key,
            IdempotencyKey.tenant_id == tenant_id
        )
        existing = await db.scalar(stmt)
        
        if existing:
            # Return cached response
            return JSONResponse(
                status_code=int(existing.status_code),
                content=existing.response_body
            )
            
        # Execute the actual endpoint
        response = await func(*args, **kwargs)
        
        # Note: in a real SV implementation, we would extract the status code and dict from the response
        # FastAPI endpoints usually return Pydantic models, which get converted to JSON by the framework later.
        # So we have to dump the model to a dict if it's a BaseModel.
        
        body_dict = {}
        status_code = getattr(response, "status_code", None)
        if not status_code:
            route = request.scope.get("route")
            if route and hasattr(route, "status_code") and route.status_code:
                status_code = route.status_code
            else:
                status_code = 201 if request.method == "POST" else 200
        
        if hasattr(response, "model_dump"):
            body_dict = response.model_dump(mode="json")
        elif isinstance(response, dict):
            body_dict = response
        
        # Save to DB
        new_key = IdempotencyKey(
            key=idempotency_key,
            user_id=getattr(user, "id", None) if user else None,
            tenant_id=tenant_id,
            status_code=str(status_code),
            response_body=body_dict
        )
        db.add(new_key)
        # We don't commit here, it commits with the main transaction or via the endpoint
        
        return response
        
    return wrapper
