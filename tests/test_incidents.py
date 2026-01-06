from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app import models
from app.main import app, get_db

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_function() -> None:
    app.dependency_overrides[get_db] = override_get_db


def teardown_function() -> None:
    app.dependency_overrides.clear()
    # Clear tables between tests
    with engine.begin() as connection:
        for table in reversed(models.Base.metadata.sorted_tables):
            connection.execute(table.delete())


client = TestClient(app)


def test_create_and_list_incident():
    payload = {
        "incident_number": "INC-001",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "location": "123 Main St",
        "incident_type": "Cardiac",
        "severity": "High",
        "description": "Patient experiencing chest pains.",
        "responders": "Unit A",
        "status": "open",
    }

    response = client.post("/incidents", json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["incident_number"] == payload["incident_number"]

    list_response = client.get("/incidents")
    assert list_response.status_code == 200
    incidents = list_response.json()
    assert len(incidents) == 1
    assert incidents[0]["incident_number"] == payload["incident_number"]


def test_get_update_patch_and_delete_incident():
    payload = {
        "incident_number": "INC-002",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "location": "456 Elm St",
        "incident_type": "Trauma",
        "severity": "Medium",
        "description": "Vehicle accident.",
        "responders": "Unit B",
        "status": "open",
    }

    create_response = client.post("/incidents", json=payload)
    assert create_response.status_code == 201
    incident_id = create_response.json()["id"]

    get_response = client.get(f"/incidents/{incident_id}")
    assert get_response.status_code == 200

    update_payload = payload | {
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "status": "closed",
    }
    put_response = client.put(f"/incidents/{incident_id}", json=update_payload)
    assert put_response.status_code == 200
    assert put_response.json()["status"] == "closed"

    patch_response = client.patch(
        f"/incidents/{incident_id}", json={"severity": "Low"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["severity"] == "Low"

    delete_response = client.delete(f"/incidents/{incident_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/incidents/{incident_id}")
    assert missing_response.status_code == 404
