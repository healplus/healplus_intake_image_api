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
PROFILE_VERSION = "1.1.0"
SOFTWARE_VERSION = "0.2.0"
CANONICAL_BASE = "https://healplus.com.br/fhir"


def _versioned(url: str) -> str:
    """Versiona referências canônicas sem alterar a identidade da definição."""
    return f"{url.split('|', 1)[0]}|{PROFILE_VERSION}"


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
        "url": url.split("|", 1)[0],
        "version": PROFILE_VERSION,
        "name": name,
        "title": title,
        "status": "active",
        "date": "2026-11-16",
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
        "differential": {
            "element": [{"id": resource_type, "path": resource_type}, *elements]
        },
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
            {"id": "Media.content.size", "path": "Media.content.size", "min": 1},
            {
                "id": "Media.content.hash", "path": "Media.content.hash", "min": 1,
                "short": "SHA-1 dos bytes JPEG em Base64, conferido pelo servidor",
            },
            {"id": "Media.width", "path": "Media.width", "min": 1},
            {"id": "Media.height", "path": "Media.height", "min": 1},
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
            {"id": "Bundle.identifier", "path": "Bundle.identifier", "min": 1},
            {"id": "Bundle.identifier.system", "path": "Bundle.identifier.system", "min": 1},
            {"id": "Bundle.identifier.value", "path": "Bundle.identifier.value", "min": 1},
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
            {"id": "Task.code", "path": "Task.code", "min": 1},
            {"id": "Task.input", "path": "Task.input", "min": 1},
            {
                "id": "Task.input.value[x]", "path": "Task.input.value[x]",
                "type": [{"code": "Reference", "targetProfile": [
                    _versioned(HEALPLUS_MEDIA_PROFILE)
                ]}],
            },
            {
                "id": "Task.output.value[x]", "path": "Task.output.value[x]",
                "type": [{"code": "Reference", "targetProfile": [
                    f"{CANONICAL_BASE}/StructureDefinition/HealPlusResultadoQualidadeImagem|{PROFILE_VERSION}"
                ]}],
            },
            {"id": "Task.businessStatus", "path": "Task.businessStatus"},
            {"id": "Task.executionPeriod", "path": "Task.executionPeriod"},
            {"id": "Task.restriction.period", "path": "Task.restriction.period", "min": 1},
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

QUALITY_PROFILE = f"{CANONICAL_BASE}/StructureDefinition/HealPlusResultadoQualidadeImagem"
QUALITY_DEVICE_PROFILE = f"{CANONICAL_BASE}/StructureDefinition/HealPlusModeloQualidadeImagem"
QUALITY_PROVENANCE_PROFILE = f"{CANONICAL_BASE}/StructureDefinition/HealPlusProvenienciaAnaliseQualidade"

# Vocabulários técnicos do algoritmo demonstrativo. Estes códigos não descrevem
# tecido, diagnóstico, dor ou conduta clínica.
TERMINOLOGY: dict[str, dict[str, str]] = {
    "veredito-qualidade-imagem": {
        "aceita": "Todos os critérios técnicos implementados foram satisfeitos.",
        "aceita-com-ressalva": "A imagem requer revisão, inclusive por critérios não avaliados.",
        "rejeitada": "Ao menos um critério técnico eliminatório implementado falhou.",
    },
    "criterio-qualidade-imagem": {
        "escore-global": "Escore técnico demonstrativo entre zero e um; não é probabilidade clínica.",
        "nitidez": "Variância do Laplaciano na imagem de luminância processada.",
        "exposicao-media": "Média da luminância dos pixels processados.",
        "pixels-subexpostos": "Fração de pixels no limiar inferior de luminância.",
        "pixels-saturados": "Fração de pixels no limiar superior de luminância.",
        "resolucao-menor-dimensao": "Menor dimensão da imagem original em pixels.",
        "integridade-arquivo": "O arquivo foi decodificado e os metadados declarados conferidos.",
        "referencia-escala-detectada": "Presença de referência física; não calculada pelo algoritmo v0.",
        "referencia-cor-detectada": "Presença de cartão de cor; não calculada pelo algoritmo v0.",
        "desvio-cor-delta-e": "Desvio de cor calibrado; não calculado pelo algoritmo v0.",
        "resolucao-espacial": "Pixels por unidade física; não calculado pelo algoritmo v0.",
        "angulo-captura": "Ângulo em relação à superfície; não calculado pelo algoritmo v0.",
        "reflexo": "Reflexo especular; não calculado pelo algoritmo v0.",
        "enquadramento": "Enquadramento clínico; não calculado pelo algoritmo v0.",
        "ita-pele-perilesional": "ITA perilesional; não coletado nem calculado pelo algoritmo v0.",
        "motivo-rejeicao": "Motivo técnico de rejeição ou ressalva.",
        "orientacao-recaptura": "Orientação técnica em português para nova captura ou revisão.",
    },
    "motivo-rejeicao-imagem": {
        "desfocada": "Nitidez inferior ao limiar demonstrativo.",
        "baixa-resolucao": "Menor dimensão em pixels inferior ao limiar demonstrativo.",
        "subexposta": "Luminância abaixo do limiar ou fração de pixels escuros excessiva.",
        "superexposta": "Luminância acima do limiar ou fração de pixels saturados excessiva.",
        "criterios-nao-avaliados": "O algoritmo v0 não avaliou todos os critérios clínicos de captura.",
    },
    "orientacao-recaptura": {
        "estabilizar-e-focar": "Estabilize o aparelho e ajuste o foco antes de fotografar novamente.",
        "aumentar-resolucao": "Use uma captura de maior resolução, sem ampliar artificialmente os pixels.",
        "ajustar-iluminacao": "Ajuste a iluminação e evite áreas excessivamente claras ou escuras.",
        "revisar-criterios-nao-avaliados": "Revise manualmente escala, cor, reflexos, ângulo e enquadramento.",
    },
    "tarefa-analise": {
        "imagem-avaliada": "Media submetida à análise técnica.",
        "resultado-qualidade-imagem": "Observation gerada pela análise técnica da imagem.",
        "analise-qualidade-imagem": "Executar a análise técnica das imagens da submissão.",
    },
    "motivo-falha-analise": {
        "tempo-esgotado": "O prazo máximo da Task foi ultrapassado.",
        "limite-tentativas": "O número máximo de tentativas técnicas foi atingido.",
        "falha-tecnica": "Falha técnica recuperável ou inesperada na execução.",
        "imagem-invalida": "O conteúdo persistido não pôde ser processado como imagem válida.",
    },
    "atividade-proveniencia": {
        "analise-qualidade-imagem": "Execução do algoritmo técnico de qualidade sobre a imagem de origem.",
        "captura-dados-clinicos": "Registro do conjunto de dados clínicos submetido pelo cliente.",
    },
    "avaliacao-ferida": {
        "resultado-qualidade-imagem": "Resultado técnico assistivo da fotografia.",
        "analise-automatizada-qualidade-imagem": "Método automático experimental de avaliação técnica.",
    },
}

CODE_SYSTEMS = {
    name: {
        "resourceType": "CodeSystem", "id": name,
        "url": f"{CANONICAL_BASE}/CodeSystem/{name}",
        "version": PROFILE_VERSION, "name": "HealPlus" + "".join(p.title() for p in name.split("-")),
        "status": "draft", "experimental": True, "date": "2026-11-16",
        "publisher": "HealPlus", "caseSensitive": True, "content": "complete",
        "count": len(codes),
        "concept": [{"code": code, "display": code, "definition": definition}
                    for code, definition in codes.items()],
    }
    for name, codes in TERMINOLOGY.items()
}
# O sistema de avaliação clínica contém outros códigos fora deste catálogo.
CODE_SYSTEMS["avaliacao-ferida"]["content"] = "fragment"
VALUE_SETS = {
    name: {
        "resourceType": "ValueSet", "id": name,
        "url": f"{CANONICAL_BASE}/ValueSet/{name}",
        "version": PROFILE_VERSION, "name": CODE_SYSTEMS[name]["name"],
        "status": "draft", "experimental": True,
        "compose": {"include": [{
            "system": f"{CANONICAL_BASE}/CodeSystem/{name}",
            "version": PROFILE_VERSION,
            "concept": [{"code": code} for code in codes],
        }]},
    }
    for name, codes in TERMINOLOGY.items()
}

PROFILES["HealPlusResultadoQualidadeImagem"] = _definicao_estrutura(
    url=QUALITY_PROFILE, resource_id="HealPlusResultadoQualidadeImagem",
    name="HealPlusResultadoQualidadeImagem", title="Resultado técnico de qualidade de imagem",
    description=("Resultado experimental assistivo da fotografia. Critérios não implementados "
                 "usam dataAbsentReason; não avalia ferida, dor, diagnóstico ou conduta."),
    resource_type="Observation", elements=[
        {"id": "Observation.status", "path": "Observation.status", "fixedCode": "preliminary"},
        {"id": "Observation.category", "path": "Observation.category", "min": 1},
        {"id": "Observation.subject", "path": "Observation.subject", "min": 1},
        {"id": "Observation.encounter", "path": "Observation.encounter", "min": 1},
        {"id": "Observation.focus", "path": "Observation.focus", "min": 1, "max": "1",
         "type": [{"code": "Reference", "targetProfile": [_versioned(HEALPLUS_MEDIA_PROFILE)]}]},
        {"id": "Observation.derivedFrom", "path": "Observation.derivedFrom", "min": 1},
        {"id": "Observation.device", "path": "Observation.device", "min": 1,
         "type": [{"code": "Reference", "targetProfile": [_versioned(QUALITY_DEVICE_PROFILE)]}]},
        {"id": "Observation.method", "path": "Observation.method", "min": 1},
        {"id": "Observation.value[x]", "path": "Observation.value[x]", "min": 1,
         "type": [{"code": "CodeableConcept"}], "binding": {"strength": "required",
             "valueSet": f"{CANONICAL_BASE}/ValueSet/veredito-qualidade-imagem|{PROFILE_VERSION}"}},
        {"id": "Observation.component", "path": "Observation.component", "min": 1},
        {"id": "Observation.component.code", "path": "Observation.component.code",
         "binding": {"strength": "required",
             "valueSet": f"{CANONICAL_BASE}/ValueSet/criterio-qualidade-imagem|{PROFILE_VERSION}"}},
        {"id": "Observation.note", "path": "Observation.note", "min": 1},
    ],
)
PROFILES["HealPlusModeloQualidadeImagem"] = _definicao_estrutura(
    url=QUALITY_DEVICE_PROFILE, resource_id="HealPlusModeloQualidadeImagem",
    name="HealPlusModeloQualidadeImagem", title="Algoritmo de qualidade de imagem",
    description="Algoritmo experimental registrado pelo servidor, com versões e hash real do artefato.",
    resource_type="Device", elements=[
        {"id": "Device.identifier", "path": "Device.identifier", "min": 1},
        {"id": "Device.version", "path": "Device.version", "min": 1},
        {"id": "Device.version.type", "path": "Device.version.type", "min": 1},
        {"id": "Device.version.value", "path": "Device.version.value", "min": 1},
    ],
)
PROFILES["HealPlusProvenienciaAnaliseQualidade"] = _definicao_estrutura(
    url=QUALITY_PROVENANCE_PROFILE, resource_id="HealPlusProvenienciaAnaliseQualidade",
    name="HealPlusProvenienciaAnaliseQualidade", title="Proveniência da análise de qualidade",
    description="Vincula resultado, fotografia original, algoritmo e protocolo versionado.",
    resource_type="Provenance", elements=[
        {"id": "Provenance.target", "path": "Provenance.target", "min": 1},
        {"id": "Provenance.agent", "path": "Provenance.agent", "min": 1},
        {"id": "Provenance.entity", "path": "Provenance.entity", "min": 1},
        {"id": "Provenance.policy", "path": "Provenance.policy", "min": 1},
    ],
)

OPERATION_DEFINITION = {
    "resourceType": "OperationDefinition",
    "id": "avaliar-feridas",
    "url": "https://healplus.com.br/fhir/OperationDefinition/avaliar-feridas",
    "version": PROFILE_VERSION,
    "name": "AvaliarFeridas",
    "title": "Submeter avaliação de feridas",
    "status": "active",
    "date": "2026-11-16",
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
            "targetProfile": [_versioned(HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE)],
        },
        {
            "name": "return",
            "use": "out",
            "min": 1,
            "max": "1",
            "type": "Task",
            "targetProfile": [_versioned(HEALPLUS_ANALYSIS_TASK_PROFILE)],
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
            "date": "2026-11-16",
            "version": PROFILE_VERSION,
            "kind": "instance",
            "software": {"name": "API HealPlus de Avaliação de Feridas", "version": SOFTWARE_VERSION},
            "implementation": {
                "description": "Intake de avaliação clínica de feridas FHIR R4 HealPlus"
            },
            "fhirVersion": "4.0.1",
            "format": ["json"],
            "rest": [
                {
                    "mode": "server",
                    "security": {
                        "description": (
                            "Authorization: Bearer com credenciais provisionadas por cliente; "
                            "leituras clínicas restritas ao cliente que submeteu e auditoria persistida. "
                            "Não há emissão de tokens OAuth ou SMART Backend Services neste servidor. "
                            "Use TLS na implantação. Recursos de conformidade são públicos."
                        ),
                    },
                    "resource": [
                        {
                            "type": "Task",
                            "profile": _versioned(HEALPLUS_ANALYSIS_TASK_PROFILE),
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Bundle",
                            "profile": _versioned(HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE),
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Encounter",
                            "profile": _versioned(HEALPLUS_ENCOUNTER_PROFILE),
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Condition",
                            "profile": _versioned(HEALPLUS_CONDITION_PROFILE),
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Observation",
                            "profile": _versioned(HEALPLUS_OBSERVATION_PROFILES[
                                "HealPlusDimensoesFerida"
                            ]),
                            "supportedProfile": [_versioned(QUALITY_PROFILE)],
                            "interaction": [{"code": "read"}],
                        },
                        {
                            "type": "Media",
                            "profile": _versioned(HEALPLUS_MEDIA_PROFILE),
                            "interaction": [{"code": "read"}],
                        },
                        {"type": "Patient", "profile": _versioned(HEALPLUS_PATIENT_PROFILE),
                         "interaction": [{"code": "read"}]},
                        {"type": "Practitioner", "profile": _versioned(HEALPLUS_PRACTITIONER_PROFILE),
                         "interaction": [{"code": "read"}]},
                        {"type": "Device", "supportedProfile": [_versioned(QUALITY_DEVICE_PROFILE)],
                         "interaction": [{"code": "read"}]},
                        {"type": "Provenance", "supportedProfile": [_versioned(QUALITY_PROVENANCE_PROFILE)],
                         "interaction": [{"code": "read"}]},
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


@router.get("/api/fhir/r4/CodeSystem/{terminology_id}", response_class=FHIRJSONResponse)
def sistema_codigos(
    terminology_id: str,
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Publica os códigos técnicos experimentais e suas definições."""
    resource = CODE_SYSTEMS.get(terminology_id)
    if resource is None:
        raise FHIRRequestError(404, "not-found", "CodeSystem não encontrado")
    return fhir_response(resource, media_type=response_media_type)


@router.get("/api/fhir/r4/ValueSet/{terminology_id}", response_class=FHIRJSONResponse)
def conjunto_valores(
    terminology_id: str,
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Publica os conjuntos fechados de códigos da saída técnica."""
    resource = VALUE_SETS.get(terminology_id)
    if resource is None:
        raise FHIRRequestError(404, "not-found", "ValueSet não encontrado")
    return fhir_response(resource, media_type=response_media_type)
