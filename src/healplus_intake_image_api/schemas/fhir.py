"""Primitivas FHIR R4 reutilizáveis na API HealPlus."""

import base64
import binascii
import hashlib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from healplus_intake_image_api.core.image_validation import (
    MAX_BASE64_LENGTH,
    MAX_IMAGE_BYTES,
    inspect_jpeg,
)


class FHIRResource(BaseModel):
    """Schema base que preserva elementos FHIR ainda não indexados pela API."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Meta(FHIRResource):
    """Metadados de um recurso FHIR."""

    version_id: str | None = Field(default=None, alias="versionId")
    last_updated: datetime | None = Field(default=None, alias="lastUpdated")
    profile: list[str] = Field(default_factory=list)

    @field_validator("profile")
    @classmethod
    def require_versioned_healplus_profiles(cls, values: list[str]) -> list[str]:
        """Identifica a versão de cada perfil local declarado pelo emissor."""
        for value in values:
            if value.startswith("https://healplus.com.br/fhir/StructureDefinition/"):
                _canonical, separator, version = value.partition("|")
                if not separator or not version.strip() or "|" in version:
                    raise ValueError("meta.profile HealPlus requer canonical|versão")
        return values


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

    @model_validator(mode="after")
    def require_local_terminology_version(self) -> "Coding":
        """Não aceita codificação HealPlus cujo significado não seja versionado."""
        if self.system and self.system.startswith("https://healplus.com.br/fhir/CodeSystem/"):
            if not self.version or not self.version.strip():
                raise ValueError("Coding.version é obrigatório para CodeSystem HealPlus")
        return self


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
    data: str = Field(min_length=1, max_length=MAX_BASE64_LENGTH)
    url: str | None = None
    size: int = Field(ge=1, le=MAX_IMAGE_BYTES, strict=True)
    hash: str
    title: str | None = None
    creation: datetime | None = None

    @field_validator("data")
    @classmethod
    def validate_base64_data(cls, value: str) -> str:
        """Valida que Attachment.data seja um valor base64Binary."""
        try:
            data = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError(
                "content.data deve conter dados Base64 válidos"
            ) from error
        inspect_jpeg(data)
        return value

    @field_validator("size")
    @classmethod
    def validate_file_size(cls, value: int, info: ValidationInfo) -> int:
        """Confere Attachment.size com o arquivo efetivamente recebido."""
        encoded = info.data.get("data")
        if encoded is not None and len(base64.b64decode(encoded, validate=True)) != value:
            raise ValueError("Media.content.size diverge do tamanho do JPEG recebido")
        return value

    @field_validator("hash")
    @classmethod
    def validate_base64_hash(cls, value: str, info: ValidationInfo) -> str:
        """Confere o SHA-1 Base64 de Attachment.hash, conforme FHIR R4."""
        try:
            digest = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError(
                "content.hash deve conter dados Base64 válidos"
            ) from error
        if len(digest) != 20:
            raise ValueError("Media.content.hash deve conter o SHA-1 de 20 bytes em Base64")
        encoded = info.data.get("data")
        if encoded is not None:
            expected = hashlib.sha1(base64.b64decode(encoded, validate=True)).digest()
            if digest != expected:
                raise ValueError("Media.content.hash diverge do SHA-1 do JPEG recebido")
        return value


def resource_json(resource: FHIRResource) -> dict[str, Any]:
    """Serializa nomes FHIR omitindo nulos e arrays vazios, proibidos em R4."""
    def omit_empty_arrays(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: omit_empty_arrays(nested)
                for key, nested in value.items()
                if not isinstance(nested, list) or nested
            }
        if isinstance(value, list):
            return [omit_empty_arrays(nested) for nested in value]
        return value

    return omit_empty_arrays(resource.model_dump(by_alias=True, exclude_none=True, mode="json"))
