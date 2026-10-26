"""Primitivas FHIR R4 reutilizáveis na API HealPlus."""

import base64
import binascii
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
            raise ValueError(
                "Reference requer reference ou identifier"
            )
        return self


class Attachment(FHIRResource):
    """Tipo FHIR Attachment para conteúdo binário incorporado."""

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
            raise ValueError(
                "content.data deve conter dados Base64 válidos"
            ) from error
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
            raise ValueError(
                "content.hash deve conter dados Base64 válidos"
            ) from error
        return value


def resource_json(resource: FHIRResource) -> dict[str, Any]:
    """Serializa um schema FHIR com seus nomes padrão de elementos JSON."""
    return resource.model_dump(by_alias=True, exclude_none=True, mode="json")
