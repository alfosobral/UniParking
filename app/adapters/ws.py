# adapters/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import defaultdict
import json, traceback
from fastapi.encoders import jsonable_encoder

router = APIRouter()

class WSManager:
    def __init__(self):
        self.active = set()
        self.rooms = defaultdict(set)

    async def connect(self, ws: WebSocket, rooms=None):
        self.active.add(ws)
        for r in rooms or []:
            self.rooms[r].add(ws)
        print(f"[WS] connected. active={len(self.active)} rooms={ {k:len(v) for k,v in self.rooms.items()} }")

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        for r in list(self.rooms):
            self.rooms[r].discard(ws)
        print(f"[WS] disconnected. active={len(self.active)} rooms={ {k:len(v) for k,v in self.rooms.items()} }")

    async def send_all(self, message: dict):
        data = json.dumps(jsonable_encoder(message))
        for ws in list(self.active):
            try:
                await ws.send_text(data)
            except Exception as e:
                print("[WS ERROR] send_all:", e); traceback.print_exc()
                self.disconnect(ws)

    async def send_room(self, room: str, message: dict):
        data = json.dumps(jsonable_encoder(message))
        targets = list(self.rooms.get(room, []))
        print(f"[WS] send_room → {room} (subs={len(targets)})")
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception as e:
                print("[WS ERROR] send_room:", e); traceback.print_exc()
                self.disconnect(ws)

manager = WSManager()

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()  # aceptar SOLO acá
    device_id = ws.query_params.get("device_id")
    rooms = [f"gate:{device_id}"] if device_id else []
    print(f"[WS] join rooms {rooms}")
    await manager.connect(ws, rooms=rooms)
    try:
        while True:
            await ws.receive_text()  # opcional
    except WebSocketDisconnect:
        manager.disconnect(ws)
