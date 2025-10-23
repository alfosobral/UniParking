from fastapi import APIRouter, HTTPException
from domain.models import Command, SensorEvent
from application.services import AccessService
from adapters.mqtt_client import mqtt_actuator, event_repo, spot_allocator  # ← importar de mqtt_client

api_router = APIRouter()

@api_router.post("/commands/open")
async def open_barrier(cmd: Command):
    cmd.action = "OPEN"
    await mqtt_actuator.publish_command(cmd)
    return {"status": "sent", "request_id": cmd.request_id}

@api_router.post("/commands/close")
async def close_barrier(cmd: Command):
    cmd.action = "CLOSE"
    await mqtt_actuator.publish_command(cmd)
    return {"status": "sent", "request_id": cmd.request_id}

@api_router.post("/sensors/events")
async def ingest_event(ev: SensorEvent):
    service = AccessService(mqtt_actuator, event_repo, spot_allocator)
    await service.handle_sensor_event(ev)
    return {"accepted": True, "event_id": ev.event_id}
