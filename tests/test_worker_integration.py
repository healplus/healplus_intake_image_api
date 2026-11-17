"""Fluxo HTTP de intake, worker, resultado e isolamento entre clientes."""

import base64
import copy
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import select

from test_fhir_avaliacao_ferida import client, intake_payload
from healplus_intake_image_api.core.database import get_db
from healplus_intake_image_api.main import app
from healplus_intake_image_api.models.avaliacao_ferida import EntradaPacote, EventoAuditoria, PacoteFHIR
from healplus_intake_image_api.services import quality


HEADERS = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}


def process_in_test_database(task_id):
    with contextmanager(app.dependency_overrides[get_db])() as db:
        assert quality.process_task(db, task_id)


def test_intake_worker_results_replay_and_client_isolation(client, intake_payload):
    response = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers=HEADERS)
    assert response.status_code == 202, response.text
    accepted = response.json()
    task_path = response.headers["content-location"]
    old_etag = response.headers["etag"]
    assert "output" not in accepted
    assert "partOf" not in accepted
    initial_get = client.get(task_path)
    assert initial_get.headers["etag"] == old_etag
    assert initial_get.json() == accepted
    bundle_reference = accepted["focus"]["reference"]
    bundle_before = client.get("/api/fhir/r4/" + bundle_reference)
    snapshot = copy.deepcopy(bundle_before.json())
    original_image = next(e["resource"] for e in snapshot["entry"] if e["resource"]["resourceType"] == "Media")
    process_in_test_database(accepted["id"])

    completed_response = client.get(task_path, headers={"If-None-Match": old_etag})
    assert completed_response.status_code == 200
    completed = completed_response.json()
    assert completed["status"] == "completed"
    assert completed_response.headers["etag"] != old_etag
    assert client.get(task_path, headers={"If-None-Match": completed_response.headers["etag"]}).status_code == 304
    assert completed["businessStatus"]["coding"][0]["code"] == "rejeitada"
    result_ref = completed["output"][0]["valueReference"]["reference"]
    result_response = client.get("/api/fhir/r4/" + result_ref)
    assert result_response.status_code == 200
    result = result_response.json()
    assert result["focus"] == [{"reference": "Media/" + original_image["id"]}]
    assert result["device"]["reference"].startswith("Device/")
    assert client.get("/api/fhir/r4/" + result["device"]["reference"]).status_code == 200
    assert client.get("/api/fhir/r4/" + result_ref, headers={"Authorization": "Bearer " + "b" * 40}).status_code == 404

    replay = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers=HEADERS)
    assert replay.status_code == 200
    assert replay.json()["id"] == accepted["id"]
    assert replay.json()["status"] == "completed"
    assert replay.json()["output"] == completed["output"]
    bundle_after = client.get("/api/fhir/r4/" + bundle_reference)
    assert bundle_after.json() == snapshot
    assert bundle_after.headers["etag"] == bundle_before.headers["etag"]
    image_after = client.get("/api/fhir/r4/Media/" + original_image["id"]).json()
    assert image_after["content"]["data"] == original_image["content"]["data"]
    assert base64.b64decode(image_after["content"]["data"])
    assert "private" in result_response.headers["cache-control"]
    with contextmanager(app.dependency_overrides[get_db])() as db:
        assert len(db.scalars(select(PacoteFHIR)).all()) == 1
        provenance = db.scalars(select(EntradaPacote).where(EntradaPacote.tipo_recurso == "Provenance")).all()
        analysis_provenance = [p for p in provenance if p.recurso_json.get("activity", {}).get("coding", [{}])[0].get("code") == "analise-qualidade-imagem"]
        assert len(analysis_provenance) == 1
        assert db.scalars(select(EventoAuditoria)).all()


def test_poll_by_modified_since_observes_completion_in_same_second(client, intake_payload, monkeypatch):
    response = client.post("/api/fhir/r4/$avaliar-feridas", json=intake_payload, headers=HEADERS)
    assert response.status_code == 202, response.text
    accepted = response.json()
    created = datetime.fromisoformat(accepted["meta"]["lastUpdated"].replace("Z", "+00:00"))
    monkeypatch.setattr(quality, "utc_now", lambda: created.replace(microsecond=999999))
    process_in_test_database(accepted["id"])
    updated = client.get(response.headers["content-location"], headers={"If-Modified-Since": response.headers["last-modified"]})
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"
