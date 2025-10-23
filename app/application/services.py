from domain.models import SensorEvent, Command, CommandMessage, DecisionMessage
from typing import Protocol
from adapters.repo_postgres import AuthorizationRepo
from adapters.ws import manager
from fastapi.encoders import jsonable_encoder

"""
Logica de la aplicacion sin detalles de red/DB:
1) Deduplica: detecta y elimina eventos duplicados (repo.seen(ev.event_id))
2) Persiste: registra el evento (repo.save(ev))
3) Aplica reglas mínimas: si el evento es del tipo "PLATE_READ" y _is_plate_authorized,
mite Command(OPEN) hacia el broker para que la barrera lo reciba y se abra.

"""

class ActuatorOut(Protocol):
    async def publish_command(self, cmd: Command) -> None: ...

class EventRepo(Protocol):
    async def save_event(self, ev: SensorEvent) -> None: ...
    async def seen_event(self, event_id: str) -> bool: ...

class AccessService:
    def __init__(self, actuator: ActuatorOut, repo: EventRepo):
        self.actuator = actuator
        self.repo = repo
        #self.auth_repo = auth_repo   

    async def _is_plate_authorized(self, plate: str) -> bool:
        return plate in ["SBA1234"]

    """if not plate:
        return False
    return await self.auth_repo.is_plate_active(plate)"""     

    async def handle_sensor_event(self, ev: SensorEvent):
    # 0) dedupe
        if await self.repo.seen_event(ev.event_id):
            return
        await self.repo.save_event(ev)

        # 1) mostrar SIEMPRE el evento en el WS (room del gate)
        await manager.send_room(f"gate:{ev.device_id}", {
            "type": "sensor_event",
            "device_id": ev.device_id,
            "payload": ev.model_dump() if hasattr(ev, "model_dump") else jsonable_encoder(ev),
        })

        if ev.type != "PLATE_READ":
            return

        plate = ev.payload.get("plate")
        print(plate)
        ok = await self._is_plate_authorized(plate)
        print(ok)

        if not ok:
            # decisión DENY → room (y opcional: broadcast)
            await manager.send_room(f"gate:{ev.device_id}", {
                "type": "decision",
                "device_id": ev.device_id,
                "payload": {"result": "DENY", "plate": plate}
            })
            # opcional:
            # await manager.send_all({"type":"decision","device_id":ev.device_id,"payload":{"result":"DENY","plate":plate}})
            return
        else:# ok → publicar comando + notificar
            cmd = Command(device_id=ev.device_id, action="OPEN", reason="ENTRY_AUTHORIZED")
            await self.actuator.publish_command(cmd)

            await manager.send_room(f"gate:{ev.device_id}", {
                "type": "command",
                "device_id": ev.device_id,
                "payload": cmd.model_dump() if hasattr(cmd, "model_dump") else jsonable_encoder(ev),
            })

            await manager.send_room(f"gate:{ev.device_id}", {
                "type": "decision",
                "device_id": ev.device_id,
                "payload": {"result": "ALLOW", "plate": plate}
            })
                    


