"""Schemas FHIR R4 usados pela API HealPlus de avaliação de feridas."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from healplus_intake_image_api.schemas.fhir import (
    Attachment,
    CodeableConcept,
    FHIRResource,
    Identifier,
    Meta,
    Reference,
    resource_json,
)

FHIR_MEDIA_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/media-type"
FHIR_OBSERVATION_CATEGORY_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/observation-category"
)
HEALPLUS_MEDIA_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusImagemClinica"
)
HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusAvaliacaoFerida"
)

REQUIRED_OBSERVATION_CODES = {
    "dimensoes-ferida",
    "tecido-ferida",
    "sinais-infeccao-ferida",
    "exsudato-ferida",
    "bordas-ferida",
    "pele-perilesional",
    "qualidade-captura-imagem",
}
UUID_PATTERN = (
    r"^urn:uuid:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _coding_codes(value: CodeableConcept | None) -> set[str]:
    if value is None:
        return set()
    return {coding.code for coding in value.coding if coding.code}


def _resolve_reference(
    reference: str | None,
    *,
    by_full_url: dict[str, FHIRResource],
    by_type_id: dict[str, FHIRResource],
) -> FHIRResource | None:
    if reference is None:
        return None
    if reference.startswith("urn:uuid:"):
        return by_full_url.get(reference)
    return by_type_id.get(reference)


def _is_wound_condition(condition: "ConditionResource") -> bool:
    return any(
        coding.code == "ferida"
        for category in condition.category
        for coding in category.coding
    )


class StrictIdentifier(Identifier):
    system: str
    value: str


class PatientResource(FHIRResource):
    resource_type: Literal["Patient"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    identifier: list[StrictIdentifier] = Field(min_length=1)


class PractitionerResource(FHIRResource):
    resource_type: Literal["Practitioner"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    identifier: list[StrictIdentifier] = Field(default_factory=list)


class DeviceName(FHIRResource):
    name: str
    type: str


class DeviceResource(FHIRResource):
    resource_type: Literal["Device"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    status: str
    manufacturer: str
    device_name: list[DeviceName] = Field(alias="deviceName", min_length=1)
    version: str


class EncounterClass(FHIRResource):
    system: str
    code: str
    display: str | None = None


class Period(FHIRResource):
    start: datetime
    end: datetime | None = None


class EncounterParticipant(FHIRResource):
    individual: Reference


class EncounterResource(FHIRResource):
    resource_type: Literal["Encounter"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    status: str
    class_fhir: EncounterClass = Field(alias="class")
    subject: Reference
    period: Period
    participant: list[EncounterParticipant] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_required_references(self) -> "EncounterResource":
        if self.subject.reference is None:
            raise ValueError("Encounter.subject.reference é obrigatório")
        return self


class ConditionResource(FHIRResource):
    resource_type: Literal["Condition"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    clinical_status: CodeableConcept = Field(alias="clinicalStatus")
    verification_status: CodeableConcept = Field(alias="verificationStatus")
    category: list[CodeableConcept] = Field(min_length=1)
    code: CodeableConcept
    subject: Reference
    encounter: Reference
    onset_date_time: datetime | None = Field(default=None, alias="onsetDateTime")
    recorded_date: datetime = Field(alias="recordedDate")
    recorder: Reference
    body_site: list[CodeableConcept] = Field(alias="bodySite", min_length=1)

    @model_validator(mode="after")
    def validate_required_references(self) -> "ConditionResource":
        if self.subject.reference is None:
            raise ValueError("Condition.subject.reference é obrigatório")
        if self.encounter.reference is None:
            raise ValueError("Condition.encounter.reference é obrigatório")
        if self.recorder.reference is None:
            raise ValueError("Condition.recorder.reference é obrigatório")
        return self


class MediaCreate(FHIRResource):
    """Recurso FHIR R4 Media restrito pelo perfil HealPlus."""

    resource_type: Literal["Media"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    status: Literal["completed"]
    type: CodeableConcept
    subject: Reference
    encounter: Reference
    created_date_time: datetime = Field(alias="createdDateTime")
    operator: Reference
    body_site: CodeableConcept = Field(alias="bodySite")
    content: Attachment

    @model_validator(mode="after")
    def validate_profile_rules(self) -> "MediaCreate":
        if self.subject.reference is None:
            raise ValueError("Media.subject.reference é obrigatório")
        if self.encounter.reference is None:
            raise ValueError("Media.encounter.reference é obrigatório")
        if self.operator.reference is None:
            raise ValueError("Media.operator.reference é obrigatório")
        if self.content.url is not None:
            raise ValueError(
                "Media.content.url não é permitido neste perfil de entrada"
            )
        if not any(
            coding.system == FHIR_MEDIA_TYPE_SYSTEM and coding.code == "image"
            for coding in self.type.coding
        ):
            raise ValueError(
                "Media.type.coding deve incluir a codificação media-type#image"
            )
        return self


class ObservationComponent(FHIRResource):
    code: CodeableConcept
    value_quantity: dict[str, Any] | None = Field(default=None, alias="valueQuantity")
    value_codeable_concept: CodeableConcept | None = Field(
        default=None,
        alias="valueCodeableConcept",
    )
    value_boolean: bool | None = Field(default=None, alias="valueBoolean")
    value_integer: int | None = Field(default=None, alias="valueInteger")
    data_absent_reason: CodeableConcept | None = Field(
        default=None,
        alias="dataAbsentReason",
    )


class ObservationResource(FHIRResource):
    resource_type: Literal["Observation"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    status: Literal["final", "preliminary"]
    category: list[CodeableConcept] = Field(min_length=1)
    code: CodeableConcept
    subject: Reference
    encounter: Reference
    focus: list[Reference] = Field(min_length=1)
    effective_date_time: datetime = Field(alias="effectiveDateTime")
    issued: datetime
    performer: list[Reference] = Field(min_length=1)
    body_site: CodeableConcept = Field(alias="bodySite")
    method: CodeableConcept | None = None
    device: Reference | None = None
    derived_from: list[Reference] = Field(default_factory=list, alias="derivedFrom")
    value_codeable_concept: CodeableConcept | None = Field(
        default=None,
        alias="valueCodeableConcept",
    )
    value_integer: int | None = Field(default=None, alias="valueInteger")
    component: list[ObservationComponent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_observation_rules(self) -> "ObservationResource":
        if self.subject.reference is None:
            raise ValueError("Observation.subject.reference é obrigatório")
        if self.encounter.reference is None:
            raise ValueError("Observation.encounter.reference é obrigatório")
        if any(item.reference is None for item in self.focus):
            raise ValueError("Observation.focus.reference é obrigatório")
        if any(item.reference is None for item in self.performer):
            raise ValueError("Observation.performer.reference é obrigatório")
        if not any(
            coding.system == FHIR_OBSERVATION_CATEGORY_SYSTEM and coding.code == "exam"
            for category in self.category
            for coding in category.coding
        ):
            raise ValueError(
                "Observation.category deve incluir a codificação "
                "observation-category#exam"
            )
        return self

    @property
    def observation_code(self) -> str | None:
        codes = _coding_codes(self.code)
        return next(iter(codes), None)


class ProvenanceAgent(FHIRResource):
    type: CodeableConcept
    who: Reference

    @model_validator(mode="after")
    def validate_who(self) -> "ProvenanceAgent":
        if self.who.reference is None:
            raise ValueError("Provenance.agent.who.reference é obrigatório")
        return self


class ProvenanceResource(FHIRResource):
    resource_type: Literal["Provenance"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    target: list[Reference] = Field(min_length=1)
    recorded: datetime
    activity: CodeableConcept
    agent: list[ProvenanceAgent] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_targets(self) -> "ProvenanceResource":
        if any(item.reference is None for item in self.target):
            raise ValueError("Provenance.target.reference é obrigatório")
        return self


AssessmentEntryResource = Annotated[
    PatientResource
    | PractitionerResource
    | DeviceResource
    | EncounterResource
    | ConditionResource
    | MediaCreate
    | ObservationResource
    | ProvenanceResource,
    Field(discriminator="resource_type"),
]


class BundleEntryCreate(FHIRResource):
    """FHIR Bundle.entry que contém recursos clínicos da avaliação."""

    full_url: str = Field(alias="fullUrl", pattern=UUID_PATTERN)
    resource: AssessmentEntryResource
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_collection_rules(self) -> "BundleEntryCreate":
        if self.request is not None or self.response is not None:
            raise ValueError(
                "Bundle.entry.request/response não são permitidos para "
                "Bundle.collection"
            )
        return self


class FHIRBundleCreate(FHIRResource):
    """Bundle FHIR collection restrito pelo perfil de avaliação HealPlus."""

    resource_type: Literal["Bundle"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")
    meta: Meta | None = None
    identifier: Identifier | None = None
    type: Literal["collection"]
    timestamp: datetime | None = None
    entry: Annotated[list[BundleEntryCreate], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_entries(self) -> "FHIRBundleCreate":
        by_full_url: dict[str, FHIRResource] = {}
        by_type_id: dict[str, FHIRResource] = {}

        patients: list[PatientResource] = []
        practitioners: list[PractitionerResource] = []
        encounters: list[EncounterResource] = []
        conditions: list[ConditionResource] = []
        media: list[MediaCreate] = []
        observations: list[ObservationResource] = []
        provenances: list[ProvenanceResource] = []

        for entry in self.entry:
            if entry.full_url in by_full_url:
                raise ValueError("Os valores de Bundle.entry.fullUrl devem ser únicos")
            by_full_url[entry.full_url] = entry.resource
            resource_id = getattr(entry.resource, "id", None)
            if resource_id:
                key = f"{entry.resource.resource_type}/{resource_id}"
                if key in by_type_id:
                    raise ValueError(
                        f"Identidade de recurso duplicada no Bundle: {key}"
                    )
                by_type_id[key] = entry.resource

            resource = entry.resource
            if isinstance(resource, PatientResource):
                patients.append(resource)
            elif isinstance(resource, PractitionerResource):
                practitioners.append(resource)
            elif isinstance(resource, EncounterResource):
                encounters.append(resource)
            elif isinstance(resource, ConditionResource):
                conditions.append(resource)
            elif isinstance(resource, MediaCreate):
                media.append(resource)
            elif isinstance(resource, ObservationResource):
                observations.append(resource)
            elif isinstance(resource, ProvenanceResource):
                provenances.append(resource)

        if len(patients) != 1:
            raise ValueError("O Bundle deve conter exatamente um recurso Patient")
        if len(practitioners) != 1:
            raise ValueError(
                "O Bundle deve conter exatamente um recurso Practitioner"
            )
        if len(encounters) != 1:
            raise ValueError("O Bundle deve conter exatamente um recurso Encounter")
        if not conditions:
            raise ValueError("O Bundle deve conter ao menos um recurso Condition")
        if len(provenances) != 1:
            raise ValueError("O Bundle deve conter exatamente um recurso Provenance")
        if not media:
            raise ValueError("O Bundle deve conter ao menos um recurso Media")

        patient = patients[0]
        encounter = encounters[0]
        wound_conditions = [item for item in conditions if _is_wound_condition(item)]
        if len(wound_conditions) != 1:
            raise ValueError(
                "O Bundle deve conter exatamente uma Condition de ferida "
                "(código de categoria 'ferida')"
            )
        condition = wound_conditions[0]
        practitioner = practitioners[0]

        required_codes_missing = REQUIRED_OBSERVATION_CODES.copy()
        for item in observations:
            code = item.observation_code
            if code:
                required_codes_missing.discard(code)

            subject_target = _resolve_reference(
                item.subject.reference,
                by_full_url=by_full_url,
                by_type_id=by_type_id,
            )
            if subject_target is not patient:
                raise ValueError(
                    "Observation.subject deve referenciar o paciente do Bundle"
                )

            encounter_target = _resolve_reference(
                item.encounter.reference,
                by_full_url=by_full_url,
                by_type_id=by_type_id,
            )
            if encounter_target is not encounter:
                raise ValueError(
                    "Observation.encounter deve referenciar o atendimento do Bundle"
                )

            focus_target = _resolve_reference(
                item.focus[0].reference,
                by_full_url=by_full_url,
                by_type_id=by_type_id,
            )
            if focus_target is not condition:
                raise ValueError(
                    "Observation.focus deve referenciar a Condition de ferida"
                )

            for source in item.derived_from:
                target = _resolve_reference(
                    source.reference,
                    by_full_url=by_full_url,
                    by_type_id=by_type_id,
                )
                if not isinstance(target, MediaCreate):
                    raise ValueError(
                        "Observation.derivedFrom deve referenciar um recurso Media"
                    )

            if code == "qualidade-captura-imagem" and not item.derived_from:
                raise ValueError(
                    "Observation qualidade-captura-imagem requer derivedFrom"
                )

        if required_codes_missing:
            missing = ", ".join(sorted(required_codes_missing))
            raise ValueError(
                f"Faltam códigos obrigatórios de Observation no Bundle: {missing}"
            )

        for item in media:
            subject_target = _resolve_reference(
                item.subject.reference,
                by_full_url=by_full_url,
                by_type_id=by_type_id,
            )
            if subject_target is not patient:
                raise ValueError(
                    "Media.subject deve referenciar o paciente do Bundle"
                )
            encounter_target = _resolve_reference(
                item.encounter.reference,
                by_full_url=by_full_url,
                by_type_id=by_type_id,
            )
            if encounter_target is not encounter:
                raise ValueError(
                    "Media.encounter deve referenciar o atendimento do Bundle"
                )

        condition_patient = _resolve_reference(
            condition.subject.reference,
            by_full_url=by_full_url,
            by_type_id=by_type_id,
        )
        if condition_patient is not patient:
            raise ValueError(
                "Condition.subject deve referenciar o paciente do Bundle"
            )
        condition_encounter = _resolve_reference(
            condition.encounter.reference,
            by_full_url=by_full_url,
            by_type_id=by_type_id,
        )
        if condition_encounter is not encounter:
            raise ValueError(
                "Condition.encounter deve referenciar o atendimento do Bundle"
            )

        encounter_patient = _resolve_reference(
            encounter.subject.reference,
            by_full_url=by_full_url,
            by_type_id=by_type_id,
        )
        if encounter_patient is not patient:
            raise ValueError(
                "Encounter.subject deve referenciar o paciente do Bundle"
            )
        for item in encounter.participant:
            participant = item.individual.reference
            participant_target = _resolve_reference(
                participant,
                by_full_url=by_full_url,
                by_type_id=by_type_id,
            )
            if participant_target is not practitioner:
                raise ValueError(
                    "Encounter.participant.individual deve referenciar Practitioner"
                )

        provenance = provenances[0]
        for target_ref in provenance.target:
            target = _resolve_reference(
                target_ref.reference,
                by_full_url=by_full_url,
                by_type_id=by_type_id,
            )
            if target is None:
                raise ValueError(
                    "Provenance.target deve referenciar um recurso do Bundle"
                )

        return self

    @property
    def patient_reference(self) -> str:
        for entry in self.entry:
            resource = entry.resource
            if isinstance(resource, PatientResource):
                return f"Patient/{resource.id}"
        raise ValueError("Recurso Patient não encontrado")


class AvaliacaoFeridaParameter(FHIRResource):
    """Parâmetro Bundle de entrada da operação `$avaliar-feridas`."""

    name: Literal["bundle"]
    resource: FHIRBundleCreate


class AvaliacaoFeridaParameters(FHIRResource):
    """Requisição FHIR Parameters para a operação `$avaliar-feridas` HealPlus."""

    resource_type: Literal["Parameters"] = Field(alias="resourceType")
    parameter: list[AvaliacaoFeridaParameter]

    @model_validator(mode="after")
    def validate_bundle_parameter(self) -> "AvaliacaoFeridaParameters":
        if len(self.parameter) != 1:
            raise ValueError(
                "$avaliar-feridas requer exatamente um parâmetro 'bundle'"
            )
        return self

    @property
    def bundle(self) -> FHIRBundleCreate:
        return self.parameter[0].resource


class OperationOutcomeIssue(FHIRResource):
    severity: Literal["fatal", "error", "warning", "information"]
    code: str
    diagnostics: str | None = None
    expression: list[str] = Field(default_factory=list)


class OperationOutcome(FHIRResource):
    resource_type: Literal["OperationOutcome"] = Field(alias="resourceType")
    issue: Annotated[list[OperationOutcomeIssue], Field(min_length=1)]


def operation_outcome(
    *,
    severity: Literal["fatal", "error", "warning", "information"],
    code: str,
    diagnostics: str,
    expression: list[str] | None = None,
) -> OperationOutcome:
    return OperationOutcome(
        resourceType="OperationOutcome",
        issue=[
            OperationOutcomeIssue(
                severity=severity,
                code=code,
                diagnostics=diagnostics,
                expression=expression or [],
            )
        ],
    )
