"""Schemas e conjuntos de valores FHIR R4 para Task."""

from datetime import datetime
from enum import Enum

from pydantic import Field

from healplus_intake_image_api.schemas.avaliacao_ferida import (
    CodeableConcept,
    FHIRResource,
    Meta,
    Reference,
)

HEALPLUS_ANALYSIS_TASK_PROFILE = (
    "https://healplus.com.br/fhir/StructureDefinition/HealPlusTarefaAnalise"
)


class TaskStatus(str, Enum):
    """Códigos FHIR R4 de Task.status usados como estados da análise HealPlus."""

    DRAFT = "draft"
    REQUESTED = "requested"
    RECEIVED = "received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    READY = "ready"
    CANCELLED = "cancelled"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    FAILED = "failed"
    COMPLETED = "completed"
    ENTERED_IN_ERROR = "entered-in-error"


class TaskResponse(FHIRResource):
    """Recurso FHIR Task que acompanha uma análise de imagens HealPlus."""

    resource_type: str = Field(default="Task", alias="resourceType")
    id: str
    meta: Meta
    status: TaskStatus
    intent: str = "order"
    focus: Reference
    for_resource: Reference | None = Field(default=None, alias="for")
    authored_on: datetime = Field(alias="authoredOn")
    last_modified: datetime = Field(alias="lastModified")
    status_reason: CodeableConcept | None = Field(default=None, alias="statusReason")
