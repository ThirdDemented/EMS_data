"""FastAPI application exposing EMS incident data management endpoints."""
from __future__ import annotations

from typing import Generator, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import SessionLocal, engine

# Create the database tables on startup if they do not exist yet.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EMS Data Service",
    description=(
        "An API for storing and retrieving emergency medical service incidents."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/incidents",
    response_model=List[schemas.Incident],
    summary="List incidents with optional filters",
)
def list_incidents(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    incident_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
):
    incidents = crud.list_incidents(
        db,
        skip=skip,
        limit=limit,
        incident_type=incident_type,
        severity=severity,
        status=status,
    )
    return list(incidents)


@app.post(
    "/incidents",
    response_model=schemas.Incident,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new incident",
)
def create_incident(
    *, db: Session = Depends(get_db), incident_in: schemas.IncidentCreate
):
    if crud.get_incident_by_number(db, incident_in.incident_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident number already exists",
        )
    incident = crud.create_incident(db, incident_in)
    return incident


@app.get(
    "/incidents/{incident_id}",
    response_model=schemas.Incident,
    summary="Retrieve an incident by its unique identifier",
)
def get_incident(*, db: Session = Depends(get_db), incident_id: int):
    incident = crud.get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return incident


@app.put(
    "/incidents/{incident_id}",
    response_model=schemas.Incident,
    summary="Replace an incident",
)
def update_incident(
    *,
    db: Session = Depends(get_db),
    incident_id: int,
    incident_in: schemas.IncidentCreate,
):
    incident = crud.get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    update_data = schemas.IncidentUpdate(**incident_in.model_dump())
    updated_incident = crud.update_incident(db, incident, update_data)
    return updated_incident


@app.patch(
    "/incidents/{incident_id}",
    response_model=schemas.Incident,
    summary="Partially update an incident",
)
def patch_incident(
    *,
    db: Session = Depends(get_db),
    incident_id: int,
    incident_in: schemas.IncidentUpdate,
):
    incident = crud.get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    updated_incident = crud.update_incident(db, incident, incident_in)
    return updated_incident


@app.delete(
    "/incidents/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an incident",
)
def delete_incident(*, db: Session = Depends(get_db), incident_id: int):
    incident = crud.get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    crud.delete_incident(db, incident)
    return None
