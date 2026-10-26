"""Recursos de conformidade FHIR publicados pelo servidor HealPlus."""

from fastapi import APIRouter, Depends

from healplus_intake_image_api.core.fhir import (
    FHIRJSONResponse,
    fhir_response,
    require_fhir_accept,
)
from healplus_intake_image_api.schemas.avaliacao_ferida import (
    HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE,
    HEALPLUS_MEDIA_PROFILE,
)
from healplus_intake_image_api.schemas.task import HEALPLUS_ANALYSIS_TASK_PROFILE
from healplus_intake_image_api.services.avaliacao_ferida import FHIRRequestError

FHIR_BASE_PATH = "/api/fhir/r4"
HEALPLUS_PATIENT_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusPaciente"
)
HEALPLUS_PRACTITIONER_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusProfissional"
)
HEALPLUS_DEVICE_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusDispositivoAnalise"
)
HEALPLUS_ENCOUNTER_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusAtendimentoAvaliacaoFerida"
)
HEALPLUS_CONDITION_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusFerida"
)
HEALPLUS_PROVENANCE_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusProvenienciaAvaliacao"
)
HEALPLUS_OBSERVATION_PROFILES: dict[str, str] = {
    "HealPlusDimensoesFerida": "https://healplus.com.br/fhir/StructureDefinition/HealPlusDimensoesFerida",
    "HealPlusTecidoFerida": "https://healplus.com.br/fhir/StructureDefinition/HealPlusTecidoFerida",
    "HealPlusSinaisInfeccaoFerida": "https://healplus.com.br/fhir/StructureDefinition/HealPlusSinaisInfeccaoFerida",
    "HealPlusExsudatoFerida": "https://healplus.com.br/fhir/StructureDefinition/HealPlusExsudatoFerida",
    "HealPlusDorFerida": "https://healplus.com.br/fhir/StructureDefinition/HealPlusDorFerida",
    "HealPlusBordasFerida": "https://healplus.com.br/fhir/StructureDefinition/HealPlusBordasFerida",
    "HealPlusPelePerilesional": "https://healplus.com.br/fhir/StructureDefinition/HealPlusPelePerilesional",
    "HealPlusQualidadeCapturaImagem": "https://healplus.com.br/fhir/StructureDefinition/HealPlusQualidadeCapturaImagem",
}

router = APIRouter(
    tags=["Conformidade FHIR R4"],
)


def _definicao_estrutura(
    *,
    url: str,
    resource_id: str,
    name: str,
    title: str,
    description: str,
    resource_type: str,
    elements: list[dict],
) -> dict:
    """Cria uma definição completa de perfil FHIR restrito."""
    return {
        "resourceType": "StructureDefinition",
        "id": resource_id,
        "url": url,
        "name": name,
        "title": title,
        "status": "active",
        "date": "2026-10-05",
        "publisher": "HealPlus",
        "description": description,
        "language": "pt-BR",
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
    "HealPlusPaciente": _definicao_estrutura(
        url=HEALPLUS_PATIENT_PROFILE,
        resource_id="HealPlusPaciente",
        name="HealPlusPaciente",
        title="Paciente HealPlus",
        description="Perfil HealPlus para identificação mínima do paciente.",
        resource_type="Patient",
        elements=[
            {"id": "Patient.identifier", "path": "Patient.identifier", "min": 1},
            {
                "id": "Patient.identifier.system",
                "path": "Patient.identifier.system",
                "min": 1,
            },
            {
                "id": "Patient.identifier.value",
                "path": "Patient.identifier.value",
                "min": 1,
            },
        ],
    ),
    "HealPlusProfissional": _definicao_estrutura(
        url=HEALPLUS_PRACTITIONER_PROFILE,
        resource_id="HealPlusProfissional",
        name="HealPlusProfissional",
        title="Profissional HealPlus",
        description="Perfil HealPlus para profissional da avaliação.",
        resource_type="Practitioner",
        elements=[{"id": "Practitioner.identifier", "path": "Practitioner.identifier"}],
    ),
    "HealPlusDispositivoAnalise": _definicao_estrutura(
        url=HEALPLUS_DEVICE_PROFILE,
        resource_id="HealPlusDispositivoAnalise",
        name="HealPlusDispositivoAnalise",
        title="Dispositivo de Análise HealPlus",
        description="Perfil HealPlus para dispositivo/modelo de análise assistiva.",
        resource_type="Device",
        elements=[
            {"id": "Device.status", "path": "Device.status", "min": 1},
            {"id": "Device.manufacturer", "path": "Device.manufacturer", "min": 1},
        ],
    ),
    "HealPlusAtendimentoAvaliacaoFerida": _definicao_estrutura(
        url=HEALPLUS_ENCOUNTER_PROFILE,
        resource_id="HealPlusAtendimentoAvaliacaoFerida",
        name="HealPlusAtendimentoAvaliacaoFerida",
        title="Atendimento de Avaliação de Ferida",
        description="Perfil HealPlus para Encounter da avaliação.",
        resource_type="Encounter",
        elements=[
            {"id": "Encounter.subject", "path": "Encounter.subject", "min": 1},
            {"id": "Encounter.period.start", "path": "Encounter.period.start", "min": 1},
        ],
    ),
    "HealPlusFerida": _definicao_estrutura(
        url=HEALPLUS_CONDITION_PROFILE,
        resource_id="HealPlusFerida",
        name="HealPlusFerida",
        title="Ferida HealPlus",
        description="Perfil HealPlus para Condition da ferida avaliada.",
        resource_type="Condition",
        elements=[
            {"id": "Condition.subject", "path": "Condition.subject", "min": 1},
            {"id": "Condition.encounter", "path": "Condition.encounter", "min": 1},
            {"id": "Condition.bodySite", "path": "Condition.bodySite", "min": 1},
        ],
    ),
    "HealPlusImagemClinica": _definicao_estrutura(
        url=HEALPLUS_MEDIA_PROFILE,
        resource_id="HealPlusImagemClinica",
        name="HealPlusImagemClinica",
        title="Imagem Clínica HealPlus",
        description=(
            "Perfil HealPlus para fotografia clínica JPEG associada a uma "
            "avaliação de ferida."
        ),
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
    "HealPlusAvaliacaoFerida": _definicao_estrutura(
        url=HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE,
        resource_id="HealPlusAvaliacaoFerida",
        name="HealPlusAvaliacaoFerida",
        title="Bundle de Avaliação de Ferida HealPlus",
        description=(
            "Perfil HealPlus para Bundle FHIR collection de avaliação clínica "
            "de feridas."
        ),
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
    "HealPlusTarefaAnalise": _definicao_estrutura(
        url=HEALPLUS_ANALYSIS_TASK_PROFILE,
        resource_id="HealPlusTarefaAnalise",
        name="HealPlusTarefaAnalise",
        title="Tarefa de Análise HealPlus",
        description=(
            "Perfil HealPlus para Task de acompanhamento assíncrono da análise "
            "de imagens clínicas."
        ),
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
    "HealPlusProvenienciaAvaliacao": _definicao_estrutura(
        url=HEALPLUS_PROVENANCE_PROFILE,
        resource_id="HealPlusProvenienciaAvaliacao",
        name="HealPlusProvenienciaAvaliacao",
        title="Proveniência da Avaliação",
        description="Perfil HealPlus para Provenance da submissão clínica.",
        resource_type="Provenance",
        elements=[
            {"id": "Provenance.target", "path": "Provenance.target", "min": 1},
            {"id": "Provenance.agent", "path": "Provenance.agent", "min": 1},
        ],
    ),
}
for profile_name, profile_url in HEALPLUS_OBSERVATION_PROFILES.items():
    PROFILES[profile_name] = _definicao_estrutura(
        url=profile_url,
        resource_id=profile_name,
        name=profile_name,
        title=profile_name.replace("HealPlus", "").strip(),
        description=f"Perfil HealPlus para observação clínica {profile_name}.",
        resource_type="Observation",
        elements=[
            {"id": "Observation.status", "path": "Observation.status", "min": 1},
            {"id": "Observation.code", "path": "Observation.code", "min": 1},
            {"id": "Observation.subject", "path": "Observation.subject", "min": 1},
            {"id": "Observation.focus", "path": "Observation.focus", "min": 1},
        ],
    )

OPERATION_DEFINITION = {
    "resourceType": "OperationDefinition",
    "id": "avaliar-feridas",
    "url": "https://healplus.com.br/fhir/OperationDefinition/avaliar-feridas",
    "name": "AvaliarFeridas",
    "title": "Submeter avaliação de feridas",
    "status": "active",
    "date": "2026-10-05",
    "publisher": "HealPlus",
    "description": (
        "Submete um Bundle de avaliação clínica de feridas e inicia uma "
        "análise assíncrona."
    ),
    "kind": "operation",
    "code": "avaliar-feridas",
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
            "targetProfile": [HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE],
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
def metadados(
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Retorna as capacidades implementadas por este servidor FHIR R4."""
    return fhir_response(
        {
            "resourceType": "CapabilityStatement",
            "id": "healplus-avaliacao-ferida-intake",
            "url": "https://healplus.com.br/fhir/CapabilityStatement/healplus-avaliacao-ferida-intake",
            "name": "HealPlusAvaliacaoFeridaIntakeCapabilityStatement",
            "title": "Capacidades FHIR R4 do HealPlus",
            "status": "active",
            "date": "2026-10-05",
            "kind": "instance",
            "software": {"name": "API HealPlus de Avaliação de Feridas"},
            "implementation": {
                "description": "Intake de avaliação clínica de feridas FHIR R4 HealPlus"
            },
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
                            "profile": HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE,
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Encounter",
                            "profile": HEALPLUS_ENCOUNTER_PROFILE,
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Condition",
                            "profile": HEALPLUS_CONDITION_PROFILE,
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Observation",
                            "profile": HEALPLUS_OBSERVATION_PROFILES[
                                "HealPlusDimensoesFerida"
                            ],
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
                            "name": "avaliar-feridas",
                            "definition": OPERATION_DEFINITION["url"],
                        }
                    ],
                }
            ],
        },
        media_type=response_media_type,
    )


@router.get(
    "/api/fhir/r4/OperationDefinition/avaliar-feridas",
    summary="Consultar definição da operação",
    description="Retorna a definição FHIR da operação `$avaliar-feridas`.",
    response_class=FHIRJSONResponse,
)
def definicao_operacao(
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Retorna a definição da operação `$avaliar-feridas`."""
    return fhir_response(OPERATION_DEFINITION, media_type=response_media_type)


@router.get(
    "/api/fhir/r4/StructureDefinition/{profile_id}",
    summary="Consultar perfil FHIR",
    description="Retorna um dos perfis FHIR publicados pelo HealPlus.",
    response_class=FHIRJSONResponse,
)
def definicao_estrutura(
    profile_id: str,
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Retorna um perfil FHIR HealPlus."""
    profile = PROFILES.get(profile_id)
    if profile is None:
        raise FHIRRequestError(
            404,
            "not-found",
            "StructureDefinition não encontrada",
        )
    return fhir_response(profile, media_type=response_media_type)
