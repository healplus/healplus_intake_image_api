"""Recursos de conformidade FHIR publicados pelo servidor HealPlus."""

from fastapi import APIRouter, Depends

from healplus_intake_image_api.core.fhir import (
    FHIRJSONResponse,
    fhir_response,
    require_fhir_accept,
)
from healplus_intake_image_api.schemas.image import (
    HEALPLUS_IMAGE_INTAKE_BUNDLE_PROFILE,
    HEALPLUS_MEDIA_PROFILE,
)
from healplus_intake_image_api.schemas.task import HEALPLUS_ANALYSIS_TASK_PROFILE
from healplus_intake_image_api.services.image import FHIRRequestError

FHIR_BASE_PATH = "/api/fhir/r4"

router = APIRouter(
    tags=["Conformidade FHIR R4"],
)


def _structure_definition(
    *,
    url: str,
    resource_id: str,
    name: str,
    resource_type: str,
    elements: list[dict],
) -> dict:
    """Cria uma definição completa de perfil FHIR restrito."""
    return {
        "resourceType": "StructureDefinition",
        "id": resource_id,
        "url": url,
        "name": name,
        "title": name,
        "status": "active",
        "date": "2026-10-05",
        "publisher": "HealPlus",
        "description": f"Perfil HealPlus para o recurso FHIR {resource_type}.",
        "fhirVersion": "4.0.1",
        "kind": "resource",
        "abstract": False,
        "type": resource_type,
        "baseDefinition": (
            f"http://hl7.org/fhir/StructureDefinition/{resource_type}"
        ),
        "derivation": "constraint",
        "differential": {"element": elements},
    }


PROFILES = {
    "healplus-media": _structure_definition(
        url=HEALPLUS_MEDIA_PROFILE,
        resource_id="healplus-media",
        name="HealPlusMedia",
        resource_type="Media",
        elements=[
            {"id": "Media.status", "path": "Media.status", "min": 1},
            {"id": "Media.type", "path": "Media.type", "min": 1},
            {"id": "Media.subject", "path": "Media.subject", "min": 1},
            {
                "id": "Media.subject.reference",
                "path": "Media.subject.reference",
                "min": 1,
            },
            {"id": "Media.content", "path": "Media.content", "min": 1},
            {
                "id": "Media.content.contentType",
                "path": "Media.content.contentType",
                "min": 1,
                "fixedCode": "image/jpeg",
            },
            {"id": "Media.content.data", "path": "Media.content.data", "min": 1},
        ],
    ),
    "healplus-image-intake-bundle": _structure_definition(
        url=HEALPLUS_IMAGE_INTAKE_BUNDLE_PROFILE,
        resource_id="healplus-image-intake-bundle",
        name="HealPlusImageIntakeBundle",
        resource_type="Bundle",
        elements=[
            {
                "id": "Bundle.type",
                "path": "Bundle.type",
                "min": 1,
                "fixedCode": "collection",
            },
            {"id": "Bundle.entry", "path": "Bundle.entry", "min": 1},
            {"id": "Bundle.entry.resource", "path": "Bundle.entry.resource", "min": 1},
        ],
    ),
    "healplus-analysis-task": _structure_definition(
        url=HEALPLUS_ANALYSIS_TASK_PROFILE,
        resource_id="healplus-analysis-task",
        name="HealPlusAnalysisTask",
        resource_type="Task",
        elements=[
            {"id": "Task.status", "path": "Task.status", "min": 1},
            {
                "id": "Task.intent",
                "path": "Task.intent",
                "min": 1,
                "fixedCode": "order",
            },
            {"id": "Task.focus", "path": "Task.focus", "min": 1},
        ],
    ),
}

OPERATION_DEFINITION = {
    "resourceType": "OperationDefinition",
    "id": "submit-media",
    "url": "https://healplus.com.br/fhir/OperationDefinition/submit-media",
    "name": "SubmitMedia",
    "title": "Submeter imagens clínicas",
    "status": "active",
    "date": "2026-10-05",
    "publisher": "HealPlus",
    "description": (
        "Submete um Bundle de recursos Media e inicia uma análise assíncrona."
    ),
    "kind": "operation",
    "code": "submit-media",
    "system": True,
    "type": False,
    "instance": False,
    "affectsState": True,
    "parameter": [
        {
            "name": "bundle",
            "use": "in",
            "min": 1,
            "max": "1",
            "type": "Bundle",
            "targetProfile": [HEALPLUS_IMAGE_INTAKE_BUNDLE_PROFILE],
        },
        {
            "name": "return",
            "use": "out",
            "min": 1,
            "max": "1",
            "type": "Task",
            "targetProfile": [HEALPLUS_ANALYSIS_TASK_PROFILE],
        },
    ],
}


@router.get("/api/fhir/r4/metadata", response_class=FHIRJSONResponse)
def metadata(
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Retorna as capacidades implementadas por este servidor FHIR R4."""
    return fhir_response(
        {
            "resourceType": "CapabilityStatement",
            "id": "healplus-image-intake",
            "url": "https://healplus.com.br/fhir/CapabilityStatement/healplus-image-intake",
            "name": "HealPlusImageIntakeCapabilityStatement",
            "title": "Capacidades FHIR R4 do HealPlus",
            "status": "active",
            "date": "2026-10-05",
            "kind": "instance",
            "software": {"name": "API HealPlus de Intake de Imagens"},
            "implementation": {"description": "Intake de imagens FHIR R4 HealPlus"},
            "fhirVersion": "4.0.1",
            "format": ["json"],
            "rest": [
                {
                    "mode": "server",
                    "resource": [
                        {
                            "type": "Task",
                            "profile": HEALPLUS_ANALYSIS_TASK_PROFILE,
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Bundle",
                            "profile": HEALPLUS_IMAGE_INTAKE_BUNDLE_PROFILE,
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Media",
                            "profile": HEALPLUS_MEDIA_PROFILE,
                            "interaction": [{"code": "read"}],
                        },
                    ],
                    "operation": [
                        {
                            "name": "submit-media",
                            "definition": OPERATION_DEFINITION["url"],
                        }
                    ],
                }
            ],
        },
        media_type=response_media_type,
    )


@router.get(
    "/api/fhir/r4/OperationDefinition/submit-media",
    summary="Consultar definição da operação",
    description="Retorna a definição FHIR da operação `$submit-media`.",
    response_class=FHIRJSONResponse,
)
def operation_definition(
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Retorna a definição da operação `$submit-media`."""
    return fhir_response(OPERATION_DEFINITION, media_type=response_media_type)


@router.get(
    "/api/fhir/r4/StructureDefinition/{profile_id}",
    summary="Consultar perfil FHIR",
    description="Retorna um dos perfis FHIR publicados pelo HealPlus.",
    response_class=FHIRJSONResponse,
)
def structure_definition(
    profile_id: str,
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Retorna um perfil FHIR HealPlus."""
    profile = PROFILES.get(profile_id)
    if profile is None:
        raise FHIRRequestError(404, "not-found", "StructureDefinition not found")
    return fhir_response(profile, media_type=response_media_type)
