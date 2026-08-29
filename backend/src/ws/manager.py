from enum import Enum
from fastapi import WebSocket

from src.core.logger import log


class WebSocketEvent(str, Enum):
    CONNECTED = "CONNECTED"
    NEW_CALL = "NEW_CALL"
    APPOINTMENT_ADDED = "APPOINTMENT_ADDED"
    APPOINTMENT_UPDATED = "APPOINTMENT_UPDATED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    PATIENT_ADDED = "PATIENT_ADDED"
    PATIENT_UPDATED = "PATIENT_UPDATED"
    WAITLIST_ADDED = "WAITLIST_ADDED"
    WAITLIST_REMOVED = "WAITLIST_REMOVED"
    SMS_SENT = "SMS_SENT"
    SMS_DELIVERED = "SMS_DELIVERED"
    SMS_FAILED = "SMS_FAILED"
    SMS_RECEIVED = "SMS_RECEIVED"
    DASHBOARD_STATS_UPDATED = "DASHBOARD_STATS_UPDATED"
    PRIOR_AUTH_CREATED = "PRIOR_AUTH_CREATED"
    PRIOR_AUTH_UPDATED = "PRIOR_AUTH_UPDATED"
    OUTBOUND_CALL_TRIGGERED = "OUTBOUND_CALL_TRIGGERED"
    OUTBOUND_CALL_COMPLETED = "OUTBOUND_CALL_COMPLETED"
    STAFF_LOGIN = "STAFF_LOGIN"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    EMERGENCY_ACCESS = "EMERGENCY_ACCESS"
    AUDIT_LOG_ENTRY = "AUDIT_LOG_ENTRY"


class TenantRoomManager:
    def __init__(self):
        # Maps tenant_id to a set of connected WebSockets
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = set()
        self.active_connections[tenant_id].add(websocket)
        log.info(f"WebSocket connected for tenant {tenant_id}")
        await self.broadcast_event(tenant_id, WebSocketEvent.CONNECTED, {"tenant_id": tenant_id})

    def disconnect(self, websocket: WebSocket, tenant_id: str):
        if tenant_id in self.active_connections:
            self.active_connections[tenant_id].discard(websocket)
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]
        log.info(f"WebSocket disconnected for tenant {tenant_id}")

    async def broadcast_event(self, tenant_id: str, event: WebSocketEvent, data: dict):
        message = {
            "event": event.value,
            "data": data
        }
        if tenant_id in self.active_connections:
            websockets = list(self.active_connections[tenant_id])
            for ws in websockets:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    log.warning(f"Error broadcasting {event.value} to WS for tenant {tenant_id}: {str(e)}")
                    self.disconnect(ws, tenant_id)

    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        """
        Alias/compatibility method for raw dictionary broadcasts.
        Sends a dict payload directly to active connections.
        """
        if tenant_id in self.active_connections:
            websockets = list(self.active_connections[tenant_id])
            for ws in websockets:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    log.warning(f"Error broadcasting message to WS for tenant {tenant_id}: {str(e)}")
                    self.disconnect(ws, tenant_id)

tenant_room_manager = TenantRoomManager()
