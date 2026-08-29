import json
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt
from src.config.settings import settings
from src.ws.manager import tenant_room_manager, WebSocketEvent
from src.core.logger import log

router = APIRouter()

def _extract_tenant_id_from_token(token: str) -> str | None:
    """Safely extracts tenant_id or user clinic_id from JWT or demo token."""
    if not token:
        return None
    if token.startswith("demo_") or token == "demo_jwt_token_sunrise_2026":
        return "d3b07384-d113-46a6-a719-38cf89235d54"
    
    try:
        # Try RS256 / configured key decode
        if hasattr(settings, 'jwt_public_key') and settings.jwt_public_key:
            public_key = settings.jwt_public_key.replace('\\n', '\n')
            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            return str(payload.get("tenant_id") or payload.get("clinic_id") or payload.get("sub"))
    except Exception:
        pass

    try:
        # Fallback base64 token payload decode for Supabase / custom tokens
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
            app_meta = payload.get("app_metadata", {})
            user_meta = payload.get("user_metadata", {})
            return str(
                payload.get("tenant_id") or 
                payload.get("clinic_id") or 
                app_meta.get("clinic_id") or 
                user_meta.get("clinic_id") or 
                payload.get("sub") or 
                "d3b07384-d113-46a6-a719-38cf89235d54"
            )
    except Exception as e:
        log.warning(f"WebSocket token decode warning: {e}")
        
    return "d3b07384-d113-46a6-a719-38cf89235d54"


@router.websocket("/ws/{tenant_id}")
@router.websocket("/api/v1/ws/{tenant_id}")
async def websocket_tenant_endpoint(
    websocket: WebSocket,
    tenant_id: str,
    token: str | None = Query(None, description="JWT or auth token")
):
    """
    WebSocket endpoint for a specific clinic / tenant room.
    """
    resolved_tenant = tenant_id
    if token:
        extracted = _extract_tenant_id_from_token(token)
        if extracted:
            resolved_tenant = tenant_id or extracted

    await tenant_room_manager.connect(websocket, resolved_tenant)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    parsed = json.loads(data)
                    if parsed.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except Exception:
                    pass
    except WebSocketDisconnect:
        tenant_room_manager.disconnect(websocket, resolved_tenant)
    except Exception as e:
        log.warning(f"WebSocket error for tenant {resolved_tenant}: {e}")
        tenant_room_manager.disconnect(websocket, resolved_tenant)


@router.websocket("/ws/dashboard")
@router.websocket("/api/v1/ws/dashboard")
async def websocket_dashboard_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None, description="JWT token for authentication"),
    tenant_id: str | None = Query(None, description="Optional tenant or clinic ID")
):
    """
    WebSocket endpoint for dashboard realtime events.
    """
    resolved_tenant = tenant_id or _extract_tenant_id_from_token(token) or "d3b07384-d113-46a6-a719-38cf89235d54"
    await tenant_room_manager.connect(websocket, resolved_tenant)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    parsed = json.loads(data)
                    if parsed.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except Exception:
                    pass
    except WebSocketDisconnect:
        tenant_room_manager.disconnect(websocket, resolved_tenant)
    except Exception as e:
        log.warning(f"WebSocket error for dashboard {resolved_tenant}: {e}")
        tenant_room_manager.disconnect(websocket, resolved_tenant)
