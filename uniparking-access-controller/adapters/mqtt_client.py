import json
import asyncio
from asyncio_mqtt import Client
from domain.models import SensorEvent, Command
from application.services import AccessService

BROKER_HOST = "mosquitto"  # o localhost
TOPIC_EVENTS = "sensors/+/events"
TOPIC_CMDS = "actuators/{device_id}/commands"

# Implementaciones simples de puerto
class MqttActuator:
    def __init__(self, client: Client):
        self.client = client
    async def publish_command(self, cmd: Command) -> None:
        topic = TOPIC_CMDS.format(device_id=cmd.device_id)
        await self.client.publish(topic, json.dumps(cmd.model_dump()))

class InMemoryEventRepo:
    def __init__(self):
        self._seen = set()
        self._events = []
    async def save_event(self, ev: SensorEvent) -> None:
        self._seen.add(ev.event_id)
        self._events.append(ev)
    async def seen_event(self, event_id: str) -> bool:
        return event_id in self._seen

_client: Client | None = None
mqtt_actuator: MqttActuator | None = None
event_repo = InMemoryEventRepo()

async def _consume():
    global _client, mqtt_actuator
    async with Client(BROKER_HOST) as client:
        _client = client
        mqtt_actuator = MqttActuator(client)
        service = AccessService(mqtt_actuator, event_repo)
        async with client.unfiltered_messages() as messages:
            await client.subscribe(TOPIC_EVENTS)
            async for msg in messages:
                try:
                    data = json.loads(msg.payload.decode())
                    ev = SensorEvent(**data)
                    await service.handle_sensor_event(ev)
                except Exception:
                    # loggear error
                    pass

_consume_task: asyncio.Task | None = None

async def start_mqtt():
    global _consume_task
    _consume_task = asyncio.create_task(_consume())

async def stop_mqtt():
    global _consume_task
    if _consume_task:
        _consume_task.cancel()
