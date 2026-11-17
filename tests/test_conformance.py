"""Conformance resources describe the implemented technical contract."""

import base64
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from examples.build_payload import build_payload
from healplus_intake_image_api.api.routes.conformance import CANONICAL_BASE, CODE_SYSTEMS, PROFILE_VERSION
from healplus_intake_image_api.main import app
from healplus_intake_image_api.schemas.avaliacao_ferida import AvaliacaoFeridaParameters
from healplus_intake_image_api.services import quality


def test_synthetic_example_matches_current_input_contract():
    """The documented generator produces a real image and valid clinical envelope."""
    payload = build_payload("documented-example")
    parsed = AvaliacaoFeridaParameters.model_validate(payload)
    assert parsed.bundle.identifier.value == "documented-example"
    resources = [e["resource"] for e in payload["parameter"][0]["resource"]["entry"]]
    assert all(any(label["code"] == "HTEST" for label in resource["meta"]["security"]) for resource in resources)
    media = next(r for r in resources if r["resourceType"] == "Media")
    assert len(base64.b64decode(media["content"]["data"])) == media["content"]["size"]


def test_capabilities_expose_real_software_version_and_authentication_description():
    """Discovery distinguishes provisioned Bearer credentials from an OAuth server."""
    with TestClient(app) as client:
        response = client.get("/api/fhir/r4/metadata")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["software"]["version"] == "0.2.0"
    rest = metadata["rest"][0]
    assert "Bearer" in rest["security"]["description"]
    assert not rest["security"].get("service")
    result_resource = next(r for r in rest["resource"] if r["type"] == "Observation")
    assert any(p.endswith("HealPlusResultadoQualidadeImagem|1.1.0") for p in result_resource["supportedProfile"])


def test_result_profile_focus_and_closed_binding_are_published():
    """Automatic image quality targets Media and has a required technical vocabulary."""
    with TestClient(app) as client:
        response = client.get("/api/fhir/r4/StructureDefinition/HealPlusResultadoQualidadeImagem")
        verdicts = client.get("/api/fhir/r4/ValueSet/veredito-qualidade-imagem").json()
    profile = response.json()
    assert profile["version"] == PROFILE_VERSION
    assert "|" not in profile["url"]
    elements = {element["path"]: element for element in profile["differential"]["element"]}
    assert elements["Observation.focus"]["type"][0]["targetProfile"][0].endswith("HealPlusImagemClinica|1.1.0")
    assert elements["Observation.component.code"]["binding"]["strength"] == "required"
    assert {c["code"] for c in verdicts["compose"]["include"][0]["concept"]} == {
        "aceita", "aceita-com-ressalva", "rejeitada",
    }


def test_worker_output_codes_are_defined_in_published_terminology():
    """The actual generated result cannot silently drift from its closed code catalog."""
    payload = build_payload("output-terminology")
    media = next(e["resource"] for e in payload["parameter"][0]["resource"]["entry"]
                 if e["resource"]["resourceType"] == "Media")
    output = quality.analyze_image(base64.b64decode(media["content"]["data"]), media,
                                   device_id="test-algorithm", issued=datetime.now(timezone.utc))

    def check(value):
        if isinstance(value, dict):
            if str(value.get("system", "")).startswith(CANONICAL_BASE + "/CodeSystem/"):
                name = value["system"].rsplit("/", 1)[1]
                assert name in CODE_SYSTEMS
                assert value["code"] in {concept["code"] for concept in CODE_SYSTEMS[name]["concept"]}
                assert value["version"] == CODE_SYSTEMS[name]["version"]
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(output)
    assert output["status"] == "preliminary"
    assert output["valueCodeableConcept"]["coding"][0]["code"] == "aceita-com-ressalva"


def test_unknown_terminology_returns_fhir_outcome():
    with TestClient(app) as client:
        response = client.get("/api/fhir/r4/CodeSystem/nonexistent")
    assert response.status_code == 404
    assert response.json()["resourceType"] == "OperationOutcome"
