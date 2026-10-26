"""Integration tests for the FHIR R4 wound assessment intake contract."""

import copy
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
    """Return a valid Parameters request for the $avaliar-feridas operation."""
    payload = {
        "resourceType": "Parameters",
        "parameter": [
            {
                "name": "bundle",
                "resource": {
                    "resourceType": "Bundle",
                    "id": "assessment-001",
                    "type": "collection",
                    "entry": [
                        {
                            "fullUrl": "urn:uuid:patient-001",
                            "resource": {
                                "resourceType": "Patient",
                                "id": "patient-001",
                                "identifier": [
                                    {
                                        "system": "https://healplus.com.br/fhir/NamingSystem/paciente",
                                        "value": "PSEUD-00001",
                                    }
                                ],
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:practitioner-001",
                            "resource": {
                                "resourceType": "Practitioner",
                                "id": "practitioner-001",
                                "identifier": [
                                    {
                                        "system": "https://healplus.com.br/fhir/NamingSystem/profissional",
                                        "value": "PROF-00001",
                                    }
                                ],
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:encounter-001",
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "encounter-001",
                                "status": "finished",
                                "class": {
                                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                                    "code": "AMB",
                                },
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "period": {"start": "2026-10-19T21:50:00Z"},
                                "participant": [
                                    {
                                        "individual": {
                                            "reference": "urn:uuid:practitioner-001"
                                        }
                                    }
                                ],
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:wound-001",
                            "resource": {
                                "resourceType": "Condition",
                                "id": "wound-001",
                                "clinicalStatus": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                            "code": "active",
                                        }
                                    ]
                                },
                                "verificationStatus": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                            "code": "confirmed",
                                        }
                                    ]
                                },
                                "category": [
                                    {
                                        "coding": [
                                            {
                                                "system": "https://healplus.com.br/fhir/CodeSystem/categoria-condicao",
                                                "code": "ferida",
                                            }
                                        ]
                                    }
                                ],
                                "code": {
                                    "coding": [
                                        {
                                            "system": "https://healplus.com.br/fhir/CodeSystem/tipo-ferida",
                                            "code": "ulcera-venosa",
                                        }
                                    ]
                                },
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "recordedDate": "2026-10-19T22:00:00Z",
                                "recorder": {
                                    "reference": "urn:uuid:practitioner-001"
                                },
                                "bodySite": [
                                    {
                                        "coding": [
                                            {
                                                "system": "https://healplus.com.br/fhir/CodeSystem/localizacao-anatomica",
                                                "code": "maleolo-medial-esquerdo",
                                            }
                                        ]
                                    }
                                ],
                            },
                        },
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
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "createdDateTime": "2026-10-19T21:55:00Z",
                                "operator": {"reference": "urn:uuid:practitioner-001"},
                                "bodySite": {
                                    "coding": [
                                        {
                                            "system": "https://healplus.com.br/fhir/CodeSystem/localizacao-anatomica",
                                            "code": "maleolo-medial-esquerdo",
                                        }
                                    ]
                                },
                                "content": {
                                    "contentType": "image/jpeg",
                                    "data": "/9j/4AAQ",
                                },
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:obs-dim",
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-dim",
                                "status": "final",
                                "category": [
                                    {
                                        "coding": [
                                            {
                                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                                "code": "exam",
                                            }
                                        ]
                                    }
                                ],
                                "code": {
                                    "coding": [
                                        {
                                            "system": "https://healplus.com.br/fhir/CodeSystem/avaliacao-ferida",
                                            "code": "dimensoes-ferida",
                                        }
                                    ]
                                },
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "focus": [{"reference": "urn:uuid:wound-001"}],
                                "effectiveDateTime": "2026-10-19T22:00:00Z",
                                "issued": "2026-10-19T22:10:00Z",
                                "performer": [
                                    {"reference": "urn:uuid:practitioner-001"}
                                ],
                                "bodySite": {
                                    "coding": [
                                        {
                                            "system": "https://healplus.com.br/fhir/CodeSystem/localizacao-anatomica",
                                            "code": "maleolo-medial-esquerdo",
                                        }
                                    ]
                                },
                                "derivedFrom": [{"reference": "urn:uuid:media-001"}],
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:obs-tecido",
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-tecido",
                                "status": "final",
                                "category": [
                                    {
                                        "coding": [
                                            {
                                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                                "code": "exam",
                                            }
                                        ]
                                    }
                                ],
                                "code": {
                                    "coding": [
                                        {
                                            "system": "https://healplus.com.br/fhir/CodeSystem/avaliacao-ferida",
                                            "code": "tecido-ferida",
                                        }
                                    ]
                                },
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "focus": [{"reference": "urn:uuid:wound-001"}],
                                "effectiveDateTime": "2026-10-19T22:00:00Z",
                                "issued": "2026-10-19T22:10:00Z",
                                "performer": [
                                    {"reference": "urn:uuid:practitioner-001"}
                                ],
                                "bodySite": {"coding": [{"code": "maleolo-medial-esquerdo"}]},
                                "derivedFrom": [{"reference": "urn:uuid:media-001"}],
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:obs-inf",
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-inf",
                                "status": "final",
                                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam"}]}],
                                "code": {"coding": [{"system": "https://healplus.com.br/fhir/CodeSystem/avaliacao-ferida", "code": "sinais-infeccao-ferida"}]},
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "focus": [{"reference": "urn:uuid:wound-001"}],
                                "effectiveDateTime": "2026-10-19T22:00:00Z",
                                "issued": "2026-10-19T22:10:00Z",
                                "performer": [{"reference": "urn:uuid:practitioner-001"}],
                                "bodySite": {"coding": [{"code": "maleolo-medial-esquerdo"}]},
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:obs-exs",
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-exs",
                                "status": "final",
                                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam"}]}],
                                "code": {"coding": [{"system": "https://healplus.com.br/fhir/CodeSystem/avaliacao-ferida", "code": "exsudato-ferida"}]},
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "focus": [{"reference": "urn:uuid:wound-001"}],
                                "effectiveDateTime": "2026-10-19T22:00:00Z",
                                "issued": "2026-10-19T22:10:00Z",
                                "performer": [{"reference": "urn:uuid:practitioner-001"}],
                                "bodySite": {"coding": [{"code": "maleolo-medial-esquerdo"}]},
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:obs-bord",
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-bord",
                                "status": "final",
                                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam"}]}],
                                "code": {"coding": [{"system": "https://healplus.com.br/fhir/CodeSystem/avaliacao-ferida", "code": "bordas-ferida"}]},
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "focus": [{"reference": "urn:uuid:wound-001"}],
                                "effectiveDateTime": "2026-10-19T22:00:00Z",
                                "issued": "2026-10-19T22:10:00Z",
                                "performer": [{"reference": "urn:uuid:practitioner-001"}],
                                "bodySite": {"coding": [{"code": "maleolo-medial-esquerdo"}]},
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:obs-pele",
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-pele",
                                "status": "final",
                                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam"}]}],
                                "code": {"coding": [{"system": "https://healplus.com.br/fhir/CodeSystem/avaliacao-ferida", "code": "pele-perilesional"}]},
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "focus": [{"reference": "urn:uuid:wound-001"}],
                                "effectiveDateTime": "2026-10-19T22:00:00Z",
                                "issued": "2026-10-19T22:10:00Z",
                                "performer": [{"reference": "urn:uuid:practitioner-001"}],
                                "bodySite": {"coding": [{"code": "maleolo-medial-esquerdo"}]},
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:obs-qualidade",
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-qualidade",
                                "status": "final",
                                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam"}]}],
                                "code": {"coding": [{"system": "https://healplus.com.br/fhir/CodeSystem/avaliacao-ferida", "code": "qualidade-captura-imagem"}]},
                                "subject": {"reference": "urn:uuid:patient-001"},
                                "encounter": {"reference": "urn:uuid:encounter-001"},
                                "focus": [{"reference": "urn:uuid:wound-001"}],
                                "effectiveDateTime": "2026-10-19T22:00:00Z",
                                "issued": "2026-10-19T22:10:00Z",
                                "performer": [{"reference": "urn:uuid:practitioner-001"}],
                                "bodySite": {"coding": [{"code": "maleolo-medial-esquerdo"}]},
                                "derivedFrom": [{"reference": "urn:uuid:media-001"}],
                            },
                        },
                        {
                            "fullUrl": "urn:uuid:prov-001",
                            "resource": {
                                "resourceType": "Provenance",
                                "id": "prov-001",
                                "target": [
                                    {"reference": "urn:uuid:encounter-001"},
                                    {"reference": "urn:uuid:wound-001"},
                                    {"reference": "urn:uuid:media-001"},
                                    {"reference": "urn:uuid:obs-dim"},
                                ],
                                "recorded": "2026-10-19T22:10:00Z",
                                "activity": {"coding": [{"code": "captura-dados-clinicos"}]},
                                "agent": [
                                    {
                                        "type": {"coding": [{"code": "author"}]},
                                        "who": {"reference": "urn:uuid:practitioner-001"},
                                    }
                                ],
                            },
                        },
                    ],
                },
            }
        ],
    }
    uuid_map = {
        "urn:uuid:patient-001": "urn:uuid:10000000-0000-1000-8000-000000000001",
        "urn:uuid:practitioner-001": "urn:uuid:20000000-0000-4000-8000-000000000001",
        "urn:uuid:encounter-001": "urn:uuid:30000000-0000-4000-8000-000000000001",
        "urn:uuid:wound-001": "urn:uuid:40000000-0000-4000-8000-000000000001",
        "urn:uuid:media-001": "urn:uuid:50000000-0000-4000-8000-000000000001",
        "urn:uuid:obs-dim": "urn:uuid:60000000-0000-4000-8000-000000000001",
        "urn:uuid:obs-tecido": "urn:uuid:60000000-0000-4000-8000-000000000002",
        "urn:uuid:obs-inf": "urn:uuid:60000000-0000-4000-8000-000000000003",
        "urn:uuid:obs-exs": "urn:uuid:60000000-0000-4000-8000-000000000004",
        "urn:uuid:obs-bord": "urn:uuid:60000000-0000-4000-8000-000000000005",
        "urn:uuid:obs-pele": "urn:uuid:60000000-0000-4000-8000-000000000006",
        "urn:uuid:obs-qualidade": "urn:uuid:60000000-0000-4000-8000-000000000007",
        "urn:uuid:prov-001": "urn:uuid:70000000-0000-4000-8000-000000000001",
    }

    def _replace_urn(value):
        if isinstance(value, dict):
            return {k: _replace_urn(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_replace_urn(v) for v in value]
        if isinstance(value, str):
            return uuid_map.get(value, value)
        return value

    return _replace_urn(payload)


def test_submit_wound_assessment_persists_fhir_resources(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """The operation persists Bundle and Media resources and returns a Task."""
    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
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
    resources_by_id = {
        item["resource"]["id"]: item["resource"] for item in bundle_response.json()["entry"]
    }
    assert (
        "https://healplus.com.br/fhir/StructureDefinition/HealPlusImagemClinica"
        in resources_by_id["media-001"]["meta"]["profile"]
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
        "/api/fhir/r4/$avaliar-feridas",
        json={"resourceType": "Parameters", "parameter": []},
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )
    unsupported = client.post(
        "/api/fhir/r4/$avaliar-feridas",
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
    media = next(
        item["resource"]
        for item in intake_payload["parameter"][0]["resource"]["entry"]
        if item["resource"]["resourceType"] == "Media"
    )
    media["subject"] = {
        "identifier": {"system": "https://healplus.com.br/patients", "value": "12345"}
    }

    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 422
    assert response.json()["resourceType"] == "OperationOutcome"


def test_requires_all_mandatory_observation_profiles(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """Reject payloads missing required Observation codes."""
    entry = intake_payload["parameter"][0]["resource"]["entry"]
    intake_payload["parameter"][0]["resource"]["entry"] = [
        item
        for item in entry
        if item["resource"].get("id") != "obs-qualidade"
    ]

    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 422
    assert response.json()["resourceType"] == "OperationOutcome"


def test_allows_additional_comorbidity_conditions(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """Accept Bundle with additional non-wound Condition resources."""
    intake_payload["parameter"][0]["resource"]["entry"].append(
        {
            "fullUrl": "urn:uuid:90000000-0000-4000-8000-000000000001",
            "resource": {
                "resourceType": "Condition",
                "id": "comorbidity-001",
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "verificationStatus": {"coding": [{"code": "confirmed"}]},
                "category": [{"coding": [{"code": "comorbidade"}]}],
                "code": {"coding": [{"code": "diabetes"}]},
                "subject": {"reference": "urn:uuid:10000000-0000-4000-8000-000000000001"},
                "encounter": {"reference": "urn:uuid:30000000-0000-4000-8000-000000000001"},
                "recordedDate": "2026-10-19T22:00:00Z",
                "recorder": {"reference": "urn:uuid:20000000-0000-4000-8000-000000000001"},
                "bodySite": [{"coding": [{"code": "na"}]}],
            },
        }
    )

    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 202


def test_rejects_observation_focus_outside_wound_condition(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """Reject Observation.focus references that do not target the wound Condition."""
    obs_dim = next(
        item["resource"]
        for item in intake_payload["parameter"][0]["resource"]["entry"]
        if item["resource"].get("id") == "obs-dim"
    )
    obs_dim["focus"] = [{"reference": "urn:uuid:media-001"}]

    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 422
    assert response.json()["resourceType"] == "OperationOutcome"


def test_rejects_duplicate_resource_identity_in_bundle(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """The payload must not contain duplicate resourceType/id pairs."""
    original = next(
        item
        for item in intake_payload["parameter"][0]["resource"]["entry"]
        if item["resource"].get("id") == "obs-dim"
    )
    duplicate_entry = copy.deepcopy(original)
    duplicate_entry["fullUrl"] = "urn:uuid:90000000-0000-4000-8000-000000000042"
    intake_payload["parameter"][0]["resource"]["entry"].append(duplicate_entry)

    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 422
    assert response.json()["issue"][0]["code"] == "invalid"


def test_rejects_any_encounter_participant_not_matching_practitioner(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """All Encounter participants must reference the request Practitioner."""
    encounter = next(
        item["resource"]
        for item in intake_payload["parameter"][0]["resource"]["entry"]
        if item["resource"].get("resourceType") == "Encounter"
    )
    encounter["participant"].append(
        {
            "individual": {
                "reference": "urn:uuid:10000000-0000-1000-8000-000000000001"
            }
        }
    )

    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )

    assert response.status_code == 422
    assert response.json()["issue"][0]["code"] == "invalid"


def test_submit_wound_assessment_allows_missing_async_preference(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """A operação assíncrona permite a ausência do cabeçalho Prefer."""
    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={"Content-Type": "application/fhir+json"},
    )

    assert response.status_code == 202


def test_content_negotiation_returns_requested_json_representation(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """The server honors application/json when it is the accepted format."""
    response = client.post(
        "/api/fhir/r4/$avaliar-feridas",
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

    metadata = client.get("/api/fhir/r4/metadata", headers=headers).json()
    assert metadata["resourceType"] == "CapabilityStatement"
    resource_types = {
        item["type"] for item in metadata["rest"][0]["resource"]
    }
    assert {"Task", "Bundle", "Encounter", "Condition", "Observation", "Media"} <= resource_types
    assert (
        client.get(
            "/api/fhir/r4/OperationDefinition/avaliar-feridas",
            headers=headers,
        ).json()["resourceType"]
        == "OperationDefinition"
    )
    profile = client.get(
        "/api/fhir/r4/StructureDefinition/HealPlusImagemClinica",
        headers=headers,
    ).json()
    assert profile["fhirVersion"] == "4.0.1"
    assert profile["id"] == "HealPlusImagemClinica"
    assert profile["name"] == "HealPlusImagemClinica"
    assert profile["title"] == "Imagem Clínica HealPlus"
    assert profile["language"] == "pt-BR"
    assert "fotografia clínica JPEG" in profile["description"]
    assert (
        client.get(
            "/api/fhir/r4/StructureDefinition/HealPlusAtendimentoAvaliacaoFerida",
            headers=headers,
        ).json()["type"]
        == "Encounter"
    )
    assert (
        client.get(
            "/api/fhir/r4/StructureDefinition/HealPlusDimensoesFerida",
            headers=headers,
        ).json()["type"]
        == "Observation"
    )


def test_reads_encounter_condition_and_observation_resources(
    client: TestClient,
    intake_payload: dict,
) -> None:
    """Read endpoints return persisted clinical resources declared in conformance."""
    submit = client.post(
        "/api/fhir/r4/$avaliar-feridas",
        json=intake_payload,
        headers={
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
            "Prefer": "respond-async",
        },
    )
    assert submit.status_code == 202

    encounter = client.get(
        "/api/fhir/r4/Encounter/encounter-001",
        headers={"Accept": "application/fhir+json"},
    )
    condition = client.get(
        "/api/fhir/r4/Condition/wound-001",
        headers={"Accept": "application/fhir+json"},
    )
    observation = client.get(
        "/api/fhir/r4/Observation/obs-dim",
        headers={"Accept": "application/fhir+json"},
    )

    assert encounter.status_code == 200
    assert condition.status_code == 200
    assert observation.status_code == 200
    assert encounter.json()["resourceType"] == "Encounter"
    assert condition.json()["resourceType"] == "Condition"
    assert observation.json()["resourceType"] == "Observation"


def test_internal_persistence_names_are_in_brazilian_portuguese() -> None:
    """The ORM exposes Portuguese tables and column names for internal storage."""
    tables = Base.metadata.tables

    assert {
        "pacotes_fhir",
        "entradas_pacote",
        "imagens_clinicas",
        "codificacoes_tipo_imagem",
        "tarefas_analise",
    } <= set(tables)
    assert {
        "identificador",
        "sistema_identificador",
        "valor_identificador",
        "recurso_json",
        "id_versao",
        "atualizado_em",
    } <= set(tables["pacotes_fhir"].columns.keys())
    assert {
        "pacote_id",
        "referencia_sujeito",
        "referencia_atendimento",
        "tipo_conteudo",
        "conteudo",
    } <= set(tables["imagens_clinicas"].columns.keys())
