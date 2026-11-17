"""Regressões de limites de streaming e transações de auditoria."""

from contextlib import contextmanager

import pytest
from sqlalchemy import event, select

from healplus_intake_image_api.core.config import Settings, settings
from healplus_intake_image_api.core.database import get_db
from healplus_intake_image_api.main import app
from healplus_intake_image_api.models.avaliacao_ferida import EventoAuditoria, PacoteFHIR
from test_fhir_avaliacao_ferida import client, intake_payload


def _session():
    return contextmanager(app.dependency_overrides[get_db])()


def test_chunked_body_limit_is_checked_without_content_length(client, monkeypatch):
    monkeypatch.setattr(settings, "max_request_bytes", 1024)
    response = client.post("/api/fhir/r4/$avaliar-feridas", content=(b"x" * 600 for _ in range(2)),
                           headers={"Content-Type": "application/fhir+json"})
    assert response.status_code == 413
    assert response.json()["resourceType"] == "OperationOutcome"


@pytest.mark.parametrize("content,headers,expected", [
    (b"{invalid", {"Content-Type": "application/fhir+json"}, 422),
    (b"{}", {"Content-Type": "text/plain"}, 415),
    (b"{}", {"Content-Type": "application/fhir+json", "Prefer": "return=minimal"}, 400),
])
def test_invalid_submissions_are_audited_before_payload_validation(client, content, headers, expected):
    response = client.post("/api/fhir/r4/$avaliar-feridas", content=content, headers=headers)
    assert response.status_code == expected
    with _session() as db:
        records = list(db.scalars(select(EventoAuditoria)))
        assert len(records) == 1
        assert records[0].cliente_id == "test-client"
        assert records[0].recurso_json["outcomeDesc"] == f"HTTP {expected}"


def test_no_clinical_data_is_returned_if_access_audit_cannot_be_written(client, intake_payload, monkeypatch):
    response = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload,
                           headers={"Content-Type": "application/fhir+json"})
    from healplus_intake_image_api.core import security

    def unavailable(*args):
        raise RuntimeError("synthetic audit outage")

    monkeypatch.setattr(security, "record_access", unavailable)
    read = client.get(response.headers["content-location"])
    assert read.status_code == 503
    assert read.json()["resourceType"] == "OperationOutcome"
    assert "focus" not in read.json()


def test_submission_and_creation_audit_are_committed_atomically(client, intake_payload):
    def fail_creation(mapper, connection, target):
        if target.recurso_json.get("outcomeDesc") == "Intake persistido":
            raise RuntimeError("synthetic creation audit outage")

    event.listen(EventoAuditoria, "before_insert", fail_creation)
    try:
        response = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload,
                               headers={"Content-Type": "application/fhir+json"})
    finally:
        event.remove(EventoAuditoria, "before_insert", fail_creation)
    assert response.status_code >= 500
    with _session() as db:
        assert db.scalar(select(PacoteFHIR)) is None


def test_nonmatching_etag_takes_precedence_over_future_modified_since(client, intake_payload):
    response = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload,
                           headers={"Content-Type": "application/fhir+json"})
    read = client.get(response.headers["content-location"], headers={
        "If-None-Match": 'W/"different"', "If-Modified-Since": "Wed, 01 Jan 2031 00:00:00 GMT",
    })
    assert read.status_code == 200


def test_shared_compose_dotenv_and_reserved_legacy_owner(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("DATABASE_URL=sqlite://\nPOSTGRES_PASSWORD=synthetic\n", encoding="utf-8")
    assert Settings(_env_file=dotenv).database_url == "sqlite://"
    with pytest.raises(ValueError, match="cliente"):
        Settings(_env_file=dotenv, api_client_tokens={"__legacy__:x": "x" * 40})


def test_persisted_bundle_has_resolvable_fhir_references(client, intake_payload, monkeypatch):
    base = "https://api.example.test/api/fhir/r4"
    monkeypatch.setattr(settings, "fhir_base_url", base)
    response = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload,
                           headers={"Content-Type": "application/fhir+json", "Host": "untrusted.invalid"})
    assert response.status_code == 202
    bundle = client.get("/api/fhir/r4/" + response.json()["focus"]["reference"]).json()
    identities = {entry["fullUrl"] for entry in bundle["entry"]}
    assert all(url.startswith(base + "/") for url in identities)

    def check(value):
        if isinstance(value, dict):
            if "reference" in value:
                assert base + "/" + value["reference"] in identities
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(bundle)
