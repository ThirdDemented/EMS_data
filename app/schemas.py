"""Pydantic schemas for request and response validation."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IncidentBase(BaseModel):
    incident_number: str = Field(..., max_length=64)
    occurred_at: datetime
    location: str = Field(..., max_length=255)
    incident_type: str = Field(..., max_length=100)
    severity: str = Field(..., max_length=50)
    description: Optional[str] = None
    responders: Optional[str] = None
    status: str = Field(..., max_length=50)


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    occurred_at: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=255)
    incident_type: Optional[str] = Field(None, max_length=100)
    severity: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    responders: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)


class Incident(IncidentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
