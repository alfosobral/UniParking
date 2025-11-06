from domain.models import SensorEvent, Command, CommandMessage, DecisionMessage
from typing import Protocol
from adapters.repo_postgres import AuthorizationRepo
from adapters.ws import manager
from fastapi.encoders import jsonable_encoder
from domain.SpotAllocator import SpotAllocator
from adapters.ws import SPOT_FEED_ROOM
from datetime import datetime, timezone
from sqlalchemy import text
from deps import engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import IntegrityError, DBAPIError


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
    def __init__(self, actuator: ActuatorOut, repo: EventRepo, spot_allocator: SpotAllocator, session_factory: async_sessionmaker[AsyncSession]):
        self.actuator = actuator
        self.repo = repo
        self.spot_allocator = spot_allocator
        self.session_factory = session_factory  

    async def _is_plate_authorized(self, plate: str) -> str | None:
        stmt = text('SELECT car_type FROM cars WHERE plate = :plate LIMIT 1')
        async with self.session_factory() as session:
            res = await session.execute(stmt, {"plate": plate})
            return res.scalar_one_or_none()

 

    async def handle_sensor_event(self, ev: SensorEvent):
        # 0) Dedupe
        if await self.repo.seen_event(ev.event_id):
            return
        await self.repo.save_event(ev)

        # 1) Mostrar SIEMPRE el evento en el WS (room del gate)
        await manager.send_room(f"gate:{ev.device_id}", {
            "type": "sensor_event",
            "device_id": ev.device_id,
            "payload": ev.model_dump() if hasattr(ev, "model_dump") else jsonable_encoder(ev),
        })

        # 2) Solo procesamos lecturas de matrícula
        if ev.type != "PLATE_READ":
            return

        plate = ev.payload.get("plate")
        car_type = await self._is_plate_authorized(plate)

        if not car_type:
            # DENY
            await manager.send_room(f"gate:{ev.device_id}", {
                "type": "decision",
                "device_id": ev.device_id,
                "payload": {"result": "DENY", "plate": plate}
            })
            await manager.send_room(
                SPOT_FEED_ROOM,
                {
                    "type": "spot_assigned",
                    "payload": {
                        "spot": "ACCESO DENEGADO",
                        "plate": plate,
                        "gate_id": ev.device_id,
                        "event_id": ev.event_id,
                        "assigned_at": datetime.now(timezone.utc).isoformat(),
                    }
                }
            )
            return

        # 3) ALLOW → abrir barrera y asignar spot
        cmd = Command(device_id=ev.device_id, action="OPEN", reason="ENTRY_AUTHORIZED")
        await self.actuator.publish_command(cmd)

        await manager.send_room(f"gate:{ev.device_id}", {
            "type": "command",
            "device_id": ev.device_id,
            "payload": cmd.model_dump() if hasattr(cmd, "model_dump") else jsonable_encoder(cmd),
        })
        await manager.send_room(f"gate:{ev.device_id}", {
            "type": "decision",
            "device_id": ev.device_id,
            "payload": {"result": "ALLOW", "plate": plate}
        })

        # 4) Buscar spot + persistir allocation en una transacción
        async with self.session_factory() as session:
            try:
                # 4.1 Encontrar spot disponible según tipo
                spot_code: str | None = await self.spot_allocator.find_spot(session, car_type)
                if not spot_code:
                    # Sin spots disponibles
                    await manager.send_room(
                        SPOT_FEED_ROOM,
                        {
                            "type": "spot_assigned",
                            "payload": {
                                "spot": "SIN DISPONIBILIDAD",
                                "plate": plate,
                                "gate_id": ev.device_id,
                                "event_id": ev.event_id,
                                "assigned_at": datetime.now(timezone.utc).isoformat(),
                            }
                        }
                    )
                    return

                # 4.2 Insertar allocation (el trigger ocupará el spot)
                q = text("""
                    INSERT INTO public.allocation (spot_code, assigned_plate, assigned_at)
                    VALUES (:spot_code, :assigned_plate, NOW())
                """)
                await session.execute(q, {"spot_code": spot_code, "assigned_plate": plate})
                await session.commit()

                # 4.3 Notificar a la feed
                await manager.send_room(
                    SPOT_FEED_ROOM,
                    {
                        "type": "spot_assigned",
                        "payload": {
                            "spot": spot_code,
                            "plate": plate,
                            "gate_id": ev.device_id,
                            "event_id": ev.event_id,
                            "assigned_at": datetime.now(timezone.utc).isoformat(),
                        }
                    }
                )

            except IntegrityError as ie:
                # Puede ser: UNIQUE(plate) ya asignada, PK(spot_code) ocupado, etc.
                await session.rollback()
                await manager.send_room(
                    SPOT_FEED_ROOM,
                    {
                        "type": "spot_assigned",
                        "payload": {
                            "spot": "CONFLICTO_ASIGNACION",
                            "plate": plate,
                            "gate_id": ev.device_id,
                            "event_id": ev.event_id,
                            "error": "placa o spot ya asignados",
                            "assigned_at": datetime.now(timezone.utc).isoformat(),
                        }
                    }
                )
            except DBAPIError as dbex:
                # Puede capturar la excepción del trigger: spot no disponible
                await session.rollback()
                await manager.send_room(
                    SPOT_FEED_ROOM,
                    {
                        "type": "spot_assigned",
                        "payload": {
                            "spot": "ERROR_DB",
                            "plate": plate,
                            "gate_id": ev.device_id,
                            "event_id": ev.event_id,
                            "error": str(dbex.__cause__ or dbex),
                            "assigned_at": datetime.now(timezone.utc).isoformat(),
                        }
                    }
                )
            except Exception as ex:
                await session.rollback()
                await manager.send_room(
                    SPOT_FEED_ROOM,
                    {
                        "type": "spot_assigned",
                        "payload": {
                            "spot": "ERROR",
                            "plate": plate,
                            "gate_id": ev.device_id,
                            "event_id": ev.event_id,
                            "error": str(ex),
                            "assigned_at": datetime.now(timezone.utc).isoformat(),
                        }
                    }
                )



