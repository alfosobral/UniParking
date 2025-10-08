from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict
from datetime import datetime
import uuid

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
