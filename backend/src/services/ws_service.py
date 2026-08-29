import asyncio

from fastapi import WebSocket

from src.core.logger import log


class TenantRoomManager:
    def __init__(self):
        # Maps tenant_id -> list of active WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}
        # A lock to ensure thread-safe operations on the connection dictionary
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str):
        await websocket.accept()
        async with self._lock:
            if tenant_id not in self.active_connections:
                self.active_connections[tenant_id] = []
            self.active_connections[tenant_id].append(websocket)
        log.info(f"[WS] Client connected to room {tenant_id}. Total in room: {len(self.active_connections[tenant_id])}")

    async def disconnect(self, websocket: WebSocket, tenant_id: str):
        async with self._lock:
            if tenant_id in self.active_connections and websocket in self.active_connections[tenant_id]:
                self.active_connections[tenant_id].remove(websocket)
                log.info(f"[WS] Client disconnected from room {tenant_id}. Remaining: {len(self.active_connections[tenant_id])}")
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]

    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        """
        Broadcast a JSON message to all connected clients in the specified tenant room.
        Any failed connections are silently ignored and will be cleaned up on their own disconnect event.
        """
        # Read-only access to the list length
        if tenant_id not in self.active_connections:
            return
            
        connections = self.active_connections[tenant_id].copy()
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                log.warning(f"[WS] Failed to send message to a client in {tenant_id}: {e}")

ws_manager = TenantRoomManager()
