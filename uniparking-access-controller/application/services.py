from domain.models import SensorEvent, Command
from typing import Protocol

class ActuatorOut(Protocol):
    async def publish_command(self, cmd: Command) -> None: ...

class EventRepo(Protocol):
    async def save_event(self, ev: SensorEvent) -> None: ...
    async def seen_event(self, event_id: str) -> bool: ...

class AccessService:
    def __init__(self, actuator: ActuatorOut, repo: EventRepo):
        self.actuator = actuator
        self.repo = repo

    async def handle_sensor_event(self, ev: SensorEvent):
        # Dedupe
        if await self.repo.seen_event(ev.event_id):
            return
        await self.repo.save_event(ev)

        # Reglas mínimas (ejemplo trivial)
        if ev.type == "PLATE_READ":
            plate = ev.payload.get("plate")
            ok = await self._is_plate_authorized(plate)
            if ok:
                cmd = Command(device_id=ev.device_id, action="OPEN", reason="ENTRY_AUTHORIZED")
                await self.actuator.publish_command(cmd)

    async def _is_plate_authorized(self, plate: str) -> bool:
        # TODO: consultar al servicio de Autorizaciones o cache local
        return plate is not None and len(plate) >= 5
