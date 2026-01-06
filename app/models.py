"""SQLAlchemy models for the EMS data application."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


class EMSIncident(Base):
    """Represents an EMS incident stored in the database."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_number = Column(String(64), unique=True, nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    location = Column(String(255), nullable=False)
    incident_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    responders = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
