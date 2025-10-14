from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict
from datetime import datetime
import uuid

"""
Contratos del dominio (Pydantic): SensorEvent, Command, tipos de evento, timestamps, etc.

Pydantic es una biblioteca de Python para la validación y serialización de datos que 
utiliza sugerencias de tipo para definir modelos de datos. Permite crear clases con 
atributos de tipo específico y automáticamente valida, convierte y asegura que los datos 
coincidan con esos tipos, reduciendo errores y haciendo el código más robusto, legible y 
fácil de depurar. 
"""

EventType = Literal["PLATE_READ", "LOOP_TRIGGER", "BARRIER_STATE", "HEALTH"]

class SensorEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    timestamp: datetime
    type: EventType
    payload: Dict

class Command(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    action: Literal["OPEN", "CLOSE"]
    reason: Optional[str] = None
    issued_at: datetime = Field(default_factory=datetime.utcnow)
