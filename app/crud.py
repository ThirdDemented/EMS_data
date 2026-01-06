"""CRUD helpers for the EMS data application."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, schemas


class IncidentAlreadyExistsError(ValueError):
    """Raised when attempting to create an incident with a duplicate incident number."""


def get_incident(session: Session, incident_id: int) -> Optional[models.EMSIncident]:
    return session.get(models.EMSIncident, incident_id)


def get_incident_by_number(
    session: Session, incident_number: str
) -> Optional[models.EMSIncident]:
    statement = select(models.EMSIncident).where(
        models.EMSIncident.incident_number == incident_number
    )
    return session.scalar(statement)


def list_incidents(
    session: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    incident_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> Iterable[models.EMSIncident]:
    statement = select(models.EMSIncident)
    if incident_type:
        statement = statement.where(models.EMSIncident.incident_type == incident_type)
    if severity:
        statement = statement.where(models.EMSIncident.severity == severity)
    if status:
        statement = statement.where(models.EMSIncident.status == status)
    statement = statement.offset(skip).limit(limit)
    return session.scalars(statement)


def create_incident(
    session: Session, incident_in: schemas.IncidentCreate
) -> models.EMSIncident:
    incident = models.EMSIncident(**incident_in.model_dump())
    session.add(incident)
    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover - depends on db state
        session.rollback()
        raise IncidentAlreadyExistsError("Incident number already exists") from exc
    session.refresh(incident)
    return incident


def update_incident(
    session: Session, incident: models.EMSIncident, incident_in: schemas.IncidentUpdate
) -> models.EMSIncident:
    update_data = incident_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(incident, field, value)
    incident.updated_at = datetime.now(timezone.utc)
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def delete_incident(session: Session, incident: models.EMSIncident) -> None:
    session.delete(incident)
    session.commit()
