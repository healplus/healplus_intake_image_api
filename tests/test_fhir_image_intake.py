"""Integration tests for the FHIR R4 clinical image intake contract."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from healplus_intake_image_api.core.database import Base, get_db
from healplus_intake_image_api.main import app


@pytest.fixture
def client() -> Generator[TestClient]:
    """Create an isolated API client backed by a shared SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def intake_payload() -> dict:
    """Return a valid Parameters request for the $submit-media operation."""
    return {
        "resourceType": "Parameters",
        "parameter": [
            {
                "name": "bundle",
                "resource": {
                    "resourceType": "Bundle",
                    "type": "collection",
                    "entry": [
                        {
                            "fullUrl": "urn:uuid:media-001",
                            "resource": {
                                "resourceType": "Media",
                                "id": "media-001",
                                "status": "completed",
                                "type": {
                                    "coding": [
                                        {
                                            "system": (
                                                "http://terminology.hl7.org/"
                                                "CodeSystem/media-type"
                                            ),
                                            "code": "image",
                                        }
                                    ]
                                },
                                "subject": {"reference": "Patient/12345"},
                                "content": {
                                    "contentType": "image/jpeg",
                                    "data": "/9j/4AAQ",
                                },
                            },
                        }
                    ],
                },
            }
        ],
    }


def test_submit_media_persists_fhir_resources(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """The operation persists Bundle and Media resources and returns a Task."""
    response = client.post(
        "/api/fhir/r4/$submit-media",
        json=intake_payload,
        headers={
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 202
    assert response.headers["content-type"].startswith("application/fhir+json")
    assert response.headers["retry-after"] == "10"
    task = response.json()
    assert task["resourceType"] == "Task"
    assert task["status"] == "accepted"
    assert response.headers["content-location"].endswith(task["id"])

    task_response = client.get(
        response.headers["content-location"],
        headers={"Accept": "application/fhir+json"},
    )
    bundle_response = client.get(
        f"/api/fhir/r4/{task['focus']['reference']}",
        headers={"Accept": "application/fhir+json"},
    )
    media_response = client.get(
        "/api/fhir/r4/Media/media-001",
        headers={"Accept": "application/fhir+json"},
    )

    assert task_response.json()["status"] == "accepted"
    assert bundle_response.json()["resourceType"] == "Bundle"
    assert bundle_response.json()["entry"][0]["resource"]["id"] == "media-001"
    assert (
        "https://healplus.com.br/fhir/StructureDefinition/healplus-media"
        in bundle_response.json()["entry"][0]["resource"]["meta"]["profile"]
    )
    assert media_response.json()["resourceType"] == "Media"
    assert "etag" in media_response.headers
    assert "last-modified" in media_response.headers

    unchanged = client.get(
        "/api/fhir/r4/Media/media-001",
        headers={
            "Accept": "application/fhir+json",
            "If-None-Match": media_response.headers["etag"],
        },
    )
    assert unchanged.status_code == 304


def test_invalid_fhir_request_returns_operation_outcome(client: TestClient) -> None:
    """FHIR validation and media type failures use OperationOutcome responses."""
    invalid = client.post(
        "/api/fhir/r4/$submit-media",
        json={"resourceType": "Parameters", "parameter": []},
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )
    unsupported = client.post(
        "/api/fhir/r4/$submit-media",
        json={},
        headers={"Content-Type": "application/json"},
    )

    assert invalid.status_code == 422
    assert invalid.json()["resourceType"] == "OperationOutcome"
    assert invalid.json()["issue"][0]["expression"] == ["Parameters"]
    assert unsupported.status_code == 415
    assert unsupported.json()["issue"][0]["code"] == "not-supported"


def test_profile_requires_a_literal_patient_reference(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """The published Media profile requires subject.reference."""
    media = intake_payload["parameter"][0]["resource"]["entry"][0]["resource"]
    media["subject"] = {
        "identifier": {"system": "https://healplus.com.br/patients", "value": "12345"}
    }

    response = client.post(
        "/api/fhir/r4/$submit-media",
        json=intake_payload,
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 422
    assert response.json()["resourceType"] == "OperationOutcome"


def test_submit_media_requires_async_preference(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """The asynchronous FHIR operation requires Prefer: respond-async."""
    response = client.post(
        "/api/fhir/r4/$submit-media",
        json=intake_payload,
        headers={"Content-Type": "application/fhir+json"},
    )

    assert response.status_code == 400
    assert response.json()["issue"][0]["code"] == "required"


def test_content_negotiation_returns_requested_json_representation(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """The server honors application/json when it is the accepted format."""
    response = client.post(
        "/api/fhir/r4/$submit-media",
        json=intake_payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 202
    assert response.headers["content-type"].startswith("application/json")


def test_conformance_resources_are_published(client: TestClient) -> None:
    """The server publishes its declared capabilities, operation, and profiles."""
    headers = {"Accept": "application/fhir+json"}

    assert (
        client.get("/api/fhir/r4/metadata", headers=headers).json()["resourceType"]
        == "CapabilityStatement"
    )
    assert (
        client.get(
            "/api/fhir/r4/OperationDefinition/submit-media",
            headers=headers,
        ).json()["resourceType"]
        == "OperationDefinition"
    )
    assert (
        client.get(
            "/api/fhir/r4/StructureDefinition/healplus-media",
            headers=headers,
        ).json()["fhirVersion"]
        == "4.0.1"
    )
