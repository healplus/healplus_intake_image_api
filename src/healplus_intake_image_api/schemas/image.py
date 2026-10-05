"""Schemas FHIR R4 usados pela API HealPlus de intake de imagens clínicas."""

import base64
import binascii
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

FHIR_MEDIA_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/media-type"
HEALPLUS_MEDIA_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/healplus-media"
)
HEALPLUS_IMAGE_INTAKE_BUNDLE_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/healplus-image-intake-bundle"
)


class FHIRResource(BaseModel):
    """Schema base que preserva elementos FHIR ainda não indexados pela API."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Meta(FHIRResource):
    """Metadados de um recurso FHIR."""

    version_id: str | None = Field(default=None, alias="versionId")
    last_updated: datetime | None = Field(default=None, alias="lastUpdated")
    profile: list[str] = Field(default_factory=list)


class Identifier(FHIRResource):
    """Tipo de dado FHIR Identifier."""

    use: str | None = None
    type: "CodeableConcept | None" = None
    system: str | None = None
    value: str | None = None


class Coding(FHIRResource):
    """Tipo de dado FHIR Coding."""

    system: str | None = None
    version: str | None = None
    code: str | None = None
    display: str | None = None
    user_selected: bool | None = Field(default=None, alias="userSelected")


class CodeableConcept(FHIRResource):
    """Tipo de dado FHIR CodeableConcept."""

    coding: list[Coding] = Field(default_factory=list)
    text: str | None = None


class Reference(FHIRResource):
    """Tipo de dado FHIR Reference."""

    reference: str | None = None
    type: str | None = None
    identifier: Identifier | None = None
    display: str | None = None

    @model_validator(mode="after")
    def require_reference_or_identifier(self) -> "Reference":
        """Garante que a referência consiga identificar um recurso de destino."""
        if self.reference is None and self.identifier is None:
            raise ValueError("A Reference requires either reference or identifier")
        return self


class Attachment(FHIRResource):
    """Tipo FHIR Attachment para a imagem clínica JPEG incorporada."""

    content_type: Literal["image/jpeg"] = Field(alias="contentType")
    language: str | None = None
    data: str = Field(min_length=1)
    url: str | None = None
    size: int | None = Field(default=None, ge=0)
    hash: str | None = None
    title: str | None = None
    creation: datetime | None = None

    @field_validator("data")
    @classmethod
    def validate_base64_data(cls, value: str) -> str:
        """Valida que Attachment.data seja um valor base64Binary."""
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("content.data must contain valid Base64 data") from error
        return value

    @field_validator("hash")
    @classmethod
    def validate_base64_hash(cls, value: str | None) -> str | None:
        """Valida que Attachment.hash seja um valor base64Binary."""
        if value is None:
            return value
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("content.hash must contain valid Base64 data") from error
        return value


class MediaCreate(FHIRResource):
    """Recurso FHIR R4 Media restrito pelo perfil de imagens HealPlus."""

    resource_type: Literal["Media"] = Field(alias="resourceType")
    id: Annotated[str | None, Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")] = None
    meta: Meta | None = None
    identifier: list[Identifier] = Field(default_factory=list)
    status: Literal[
        "preparation",
        "in-progress",
        "not-ready",
        "suspended",
        "aborted",
        "completed",
        "entered-in-error",
        "unknown",
    ]
    type: CodeableConcept
    modality: CodeableConcept | None = None
    view: CodeableConcept | None = None
    subject: Reference
    encounter: Reference | None = None
    created_date_time: datetime | None = Field(default=None, alias="createdDateTime")
    issued: datetime | None = None
    operator: Reference | None = None
    reason_code: list[CodeableConcept] = Field(default_factory=list, alias="reasonCode")
    body_site: CodeableConcept | None = Field(default=None, alias="bodySite")
    device_name: str | None = Field(default=None, alias="deviceName")
    device: Reference | None = None
    height: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    frames: int | None = Field(default=None, ge=0)
    duration: float | None = Field(default=None, ge=0)
    content: Attachment

    @field_validator("type")
    @classmethod
    def validate_image_type(cls, value: CodeableConcept) -> CodeableConcept:
        """Exige que Media.type inclua a codificação padrão para imagem."""
        if not any(
            coding.system == FHIR_MEDIA_TYPE_SYSTEM and coding.code == "image"
            for coding in value.coding
        ):
            raise ValueError(
                "type.coding must include the FHIR media-type 'image' coding"
            )
        return value

    @model_validator(mode="after")
    def validate_profile_references(self) -> "MediaCreate":
        """Exige a referência literal do paciente definida pelo perfil HealPlus."""
        if self.subject.reference is None:
            raise ValueError("subject.reference is required by the HealPlus profile")
        return self


class BundleEntryCreate(FHIRResource):
    """FHIR Bundle.entry que contém uma imagem clínica."""

    full_url: str | None = Field(default=None, alias="fullUrl")
    resource: MediaCreate


class FHIRBundleCreate(FHIRResource):
    """Bundle FHIR collection restrito pelo perfil de intake HealPlus."""

    resource_type: Literal["Bundle"] = Field(alias="resourceType")
    id: Annotated[str | None, Field(pattern=r"^[A-Za-z0-9\-.]{1,64}$")] = None
    meta: Meta | None = None
    identifier: Identifier | None = None
    type: Literal["collection"]
    timestamp: datetime | None = None
    entry: Annotated[list[BundleEntryCreate], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_entries(self) -> "FHIRBundleCreate":
        """Exige full URLs únicos e um único paciente por análise."""
        full_urls = [entry.full_url for entry in self.entry if entry.full_url]
        if len(full_urls) != len(set(full_urls)):
            raise ValueError("Bundle.entry.fullUrl values must be unique")

        subject_references = {
            entry.resource.subject.reference
            for entry in self.entry
            if entry.resource.subject.reference is not None
        }
        if len(subject_references) > 1:
            raise ValueError("All Media resources must reference the same subject")
        return self


class SubmitMediaParameter(FHIRResource):
    """Parâmetro Bundle de entrada da operação `$submit-media`."""

    name: Literal["bundle"]
    resource: FHIRBundleCreate


class SubmitMediaParameters(FHIRResource):
    """Requisição FHIR Parameters para a operação `$submit-media` HealPlus."""

    resource_type: Literal["Parameters"] = Field(alias="resourceType")
    parameter: list[SubmitMediaParameter]

    @model_validator(mode="after")
    def validate_bundle_parameter(self) -> "SubmitMediaParameters":
        """Exige exatamente um parâmetro Bundle de entrada."""
        if len(self.parameter) != 1:
            raise ValueError("$submit-media requires exactly one 'bundle' parameter")
        return self

    @property
    def bundle(self) -> FHIRBundleCreate:
        """Retorna o Bundle submetido à operação."""
        return self.parameter[0].resource


class OperationOutcomeIssue(FHIRResource):
    """Elemento FHIR OperationOutcome.issue."""

    severity: Literal["fatal", "error", "warning", "information"]
    code: str
    diagnostics: str | None = None
    expression: list[str] = Field(default_factory=list)


class OperationOutcome(FHIRResource):
    """Recurso FHIR OperationOutcome."""

    resource_type: Literal["OperationOutcome"] = Field(alias="resourceType")
    issue: Annotated[list[OperationOutcomeIssue], Field(min_length=1)]


def operation_outcome(
    *,
    severity: Literal["fatal", "error", "warning", "information"],
    code: str,
    diagnostics: str,
    expression: list[str] | None = None,
) -> OperationOutcome:
    """Cria um recurso FHIR OperationOutcome."""
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


def resource_json(resource: FHIRResource) -> dict[str, Any]:
    """Serializa um schema FHIR com seus nomes padrão de elementos JSON."""
    return resource.model_dump(by_alias=True, exclude_none=True, mode="json")
