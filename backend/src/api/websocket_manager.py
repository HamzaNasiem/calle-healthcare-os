import json

from fastapi import WebSocket

from ..core.logger import log


class ConnectionManager:
    def __init__(self):
        # clinic_id -> list of WebSockets
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, clinic_id: str):
        await websocket.accept()
        if clinic_id not in self.active_connections:
            self.active_connections[clinic_id] = []
        self.active_connections[clinic_id].append(websocket)
        log.info(f"[WebSocket] Connected client for clinic {clinic_id}")

    def disconnect(self, websocket: WebSocket, clinic_id: str):
        if clinic_id in self.active_connections:
            if websocket in self.active_connections[clinic_id]:
                self.active_connections[clinic_id].remove(websocket)
            if not self.active_connections[clinic_id]:
                del self.active_connections[clinic_id]
        log.info(f"[WebSocket] Disconnected client from clinic {clinic_id}")

    async def broadcast_to_clinic(self, clinic_id: str, message: dict):
        if clinic_id in self.active_connections:
            connections = self.active_connections[clinic_id]
            payload = json.dumps(message)
            for connection in connections:
                try:
                    await connection.send_text(payload)
                except Exception as e:
                    log.warning(f"[WebSocket] Broadcast failed: {e}")

ws_manager = ConnectionManager()
