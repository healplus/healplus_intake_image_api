"""Integrações de autenticação, isolamento de clientes e trilha de acesso."""

import json
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import select

from healplus_intake_image_api.core.config import settings
from healplus_intake_image_api.core.database import get_db
from healplus_intake_image_api.main import app
from healplus_intake_image_api.models.avaliacao_ferida import EventoAuditoria, PacoteFHIR
from test_fhir_avaliacao_ferida import client, intake_payload


OTHER_AUTH = {"Authorization": "Bearer " + "b" * 40}
FHIR_HEADERS = {"Content-Type": "application/fhir+json"}


def _audit_records() -> list[dict]:
    with contextmanager(app.dependency_overrides[get_db])() as db:
        return [event.recurso_json for event in db.scalars(select(EventoAuditoria)).all()]


def test_requires_bearer_token(client: TestClient) -> None:
    client.headers.pop("Authorization")
    response = client.get("/api/fhir/r4/Task/00000000-0000-4000-8000-000000000001")
    assert response.status_code == 401
    assert response.json()["resourceType"] == "OperationOutcome"
    assert response.json()["issue"][0]["code"] == "login"
    assert _audit_records()[0]["outcomeDesc"] == "HTTP 401"


def test_rejects_unknown_bearer_token(client: TestClient) -> None:
    response = client.get("/api/fhir/r4/Task/missing", headers={"Authorization": "Bearer invalid-secret"})
    assert response.status_code == 401
    serialized = json.dumps(_audit_records())
    assert "invalid-secret" not in serialized
    assert "anonymous" in serialized


def test_fails_closed_when_no_clients_are_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_client_tokens", {})
    response = client.get("/api/fhir/r4/Task/missing")
    assert response.status_code == 503
    assert response.json()["resourceType"] == "OperationOutcome"


def test_requires_https_when_enabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "require_https", True)
    response = client.get("/api/fhir/r4/Task/missing", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 403
    assert response.json()["issue"][0]["code"] == "security"


def test_every_clinical_resource_is_isolated_by_authenticated_client(client: TestClient, intake_payload: dict) -> None:
    bundle = intake_payload["parameter"][0]["resource"]
    bundle["entry"].append({
        "fullUrl": "urn:uuid:80000000-0000-4000-8000-000000000001",
        "resource": {
            "resourceType": "Device", "id": "camera-001", "status": "active",
            "manufacturer": "Sintético", "deviceName": [{"name": "Demo", "type": "model-name"}],
            "version": [{"value": "1.0.0"}],
        },
    })
    submit = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers=FHIR_HEADERS)
    assert submit.status_code == 202
    task = submit.json()
    bundle_url = f"/api/fhir/r4/{task['focus']['reference']}"
    stored_bundle = client.get(bundle_url).json()
    urls = [submit.headers["content-location"], bundle_url] + [
        f"/api/fhir/r4/{entry['resource']['resourceType']}/{entry['resource']['id']}"
        for entry in stored_bundle["entry"]
    ]
    for url in urls:
        assert client.get(url).status_code == 200
        denied = client.get(url, headers=OTHER_AUTH)
        assert denied.status_code == 404
        assert denied.json()["resourceType"] == "OperationOutcome"


def test_idempotency_identifier_is_scoped_to_each_client(client: TestClient, intake_payload: dict) -> None:
    first = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers=FHIR_HEADERS)
    second = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers={**FHIR_HEADERS, **OTHER_AUTH})
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["focus"] != second.json()["focus"]
    assert client.get(second.headers["content-location"]).status_code == 404
    assert client.get(first.headers["content-location"], headers=OTHER_AUTH).status_code == 404
    with contextmanager(app.dependency_overrides[get_db])() as db:
        assert len(db.scalars(select(PacoteFHIR)).all()) == 2


def test_audits_submission_reads_and_conditional_reads_without_payload(client: TestClient, intake_payload: dict) -> None:
    submit = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers=FHIR_HEADERS)
    assert submit.status_code == 202
    url = submit.headers["content-location"]
    read = client.get(url)
    unchanged = client.get(url, headers={"If-None-Match": read.headers["etag"]})
    assert read.status_code == 200
    assert unchanged.status_code == 304
    events = _audit_records()
    assert [event["outcomeDesc"] for event in events if event["outcomeDesc"].startswith("HTTP ")] == ["HTTP 202", "HTTP 200", "HTTP 304"]
    assert any(event["outcomeDesc"] == "Intake persistido" for event in events)
    assert [event["action"] for event in events if event["outcomeDesc"].startswith("HTTP ")] == ["C", "R", "R"]
    assert all(event["resourceType"] == "AuditEvent" for event in events)
    assert all(event["agent"][0]["who"]["identifier"]["value"] == "test-client" for event in events)
    serialized = json.dumps(events)
    assert "a" * 40 not in serialized
    assert "b" * 40 not in serialized
    assert "PSEUD-00001" not in serialized
    assert "Authorization" not in serialized


def test_rejects_payload_larger_than_configured_limit(client: TestClient, intake_payload: dict, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_request_bytes", 1024)
    response = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers=FHIR_HEADERS)
    assert response.status_code == 413
    assert response.json()["resourceType"] == "OperationOutcome"
