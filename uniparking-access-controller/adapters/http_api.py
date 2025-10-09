from fastapi import APIRouter, HTTPException
from domain.models import Command, SensorEvent
from application.services import AccessService
from adapters.mqtt_client import mqtt_actuator, event_repo

"""
Endpoints REST (y eventualmente webhook)

Aqui el programa de AC publica comandos a actuadores MQTT (programas que inteactuan 
con el broker).

    - POST /v1/commands/open|close publica comandos para la barrera
    - POST /v1/sensors/events es un webhook opcional por si algun sensor se comunica
    por HTTP (no MQTT)

Internamente instancia AccessService y le pasa dependencias (actuador MQTT (broker) + repo de eventos).
Esta clase se importa desde application.services.py
"""

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
    service = AccessService(mqtt_actuator, event_repo)
    await service.handle_sensor_event(ev)
    return {"accepted": True, "event_id": ev.event_id}
