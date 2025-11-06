import json
import asyncio
from typing import Optional
from asyncio_mqtt import Client
from deps import SessionLocal

from domain.models import SensorEvent, Command
from application.services import AccessService
from adapters.ws import manager
from domain.SpotAllocator import SpotAllocator, SpotAllocatorIndexBuilder  

BROKER_HOST = "mosquitto"
TOPIC_EVENTS = "sensors/+/events"
TOPIC_CMDS = "actuators/{device_id}/commands"

# --- Actuator que reutiliza el MISMO client MQTT ---
class MqttActuator:
    def __init__(self, client: Optional[Client] = None):
        self.client: Optional[Client] = client

    def set_client(self, client: Optional[Client]):
        self.client = client

    async def publish_command(self, cmd: Command) -> None:
        if not self.client:
            raise RuntimeError("MQTT client not started")
        topic = TOPIC_CMDS.format(device_id=cmd.device_id)
        payload = cmd.model_dump()  # si usás Pydantic v1: cmd.dict()
        print(f"[MQTT] publish → {topic} {payload}")
        await self.client.publish(topic, json.dumps(payload))

# --- Repositorio mínimo en memoria ---
class InMemoryEventRepo:
    def __init__(self):
        self._seen = set()
        self._events = []
    async def save_event(self, ev: SensorEvent) -> None:
        self._seen.add(ev.event_id)
        self._events.append(ev)
    async def seen_event(self, event_id: str) -> bool:
        return event_id in self._seen

# --- SINGLETONS compartidos por toda la app ---
_client: Optional[Client] = None
mqtt_actuator = MqttActuator()          # ← sin client, se inyecta en start_mqtt
event_repo = InMemoryEventRepo()
spot_allocator = SpotAllocator(SpotAllocatorIndexBuilder())        # ← instancia ÚNICA y correcta

_consume_task: Optional[asyncio.Task] = None

async def start_mqtt(on_event):
    """Conecta al broker, se suscribe y procesa eventos de sensores."""
    global _client, _consume_task

    async def _consume():
        global _client
        async with Client(BROKER_HOST) as client:
            _client = client
            mqtt_actuator.set_client(client)     # ← inyección
            service = AccessService(mqtt_actuator, event_repo, spot_allocator, SessionLocal)

            async with client.unfiltered_messages() as messages:
                await client.subscribe(TOPIC_EVENTS)
                print("[MQTT] subscribed to", TOPIC_EVENTS)
                async for msg in messages:
                    try:
                        data = json.loads(msg.payload.decode())
                        ev = SensorEvent(**data)
                        await service.handle_sensor_event(ev)
                        await on_event(data)
                    except Exception:
                        import traceback; traceback.print_exc()

    _consume_task = asyncio.create_task(_consume())

async def stop_mqtt():
    global _consume_task
    if _consume_task:
        _consume_task.cancel()
        _consume_task = None
