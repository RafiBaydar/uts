from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List
from datetime import datetime

class Event(BaseModel):
    topic: str = Field(..., description="Topic name")
    event_id: str = Field(..., description="Unique event id within topic")
    timestamp: datetime = Field(..., description="ISO8601 timestamp")
    source: str = Field(..., description="Publisher source name")
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("topic", "event_id", "source")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v.strip()

class PublishResponse(BaseModel):
    accepted: int
    queued: int
    errors: Optional[List[str]] = None

class StatsResponse(BaseModel):
    received: int
    unique_processed: int
    duplicate_dropped: int
    topics: List[str]
    uptime_seconds: float
    queue_size: int
