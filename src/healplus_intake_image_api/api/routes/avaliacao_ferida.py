"""Rotas FHIR de intake e leituras clínicas autenticadas e auditadas."""

from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.orm import Session

from healplus_intake_image_api.core.database import get_db
from healplus_intake_image_api.core.fhir import (
    FHIRJSONResponse, fhir_conditional_response, fhir_response,
    require_fhir_accept, require_async_preference, require_fhir_request_content_type,
)
from healplus_intake_image_api.core.security import AuditedRoute, require_client
from healplus_intake_image_api.schemas.avaliacao_ferida import AvaliacaoFeridaParameters
from healplus_intake_image_api.services.avaliacao_ferida import ler_recurso, submeter_avaliacao_ferida

router = APIRouter(prefix="/api/fhir/r4", tags=["Avaliação clínica de feridas FHIR R4"], route_class=AuditedRoute)


@router.post(
    "/$avaliar-feridas", summary="Submeter avaliação de feridas",
    status_code=202, response_class=FHIRJSONResponse,
    dependencies=[Depends(require_fhir_request_content_type), Depends(require_async_preference)],
    responses={200: {"description": "Reenvio idêntico, mesma Task"}, 409: {"description": "Identifier reutilizado com conteúdo diferente"}},
)
def submeter_avaliacao(
    request: Request,
    parameters: AvaliacaoFeridaParameters = Body(media_type="application/fhir+json"),
    db: Session = Depends(get_db),
    client_id: str = Depends(require_client),
    response_media_type: str = Depends(require_fhir_accept),
):
    """Aceita uma avaliação ou recupera sua Task em um reenvio idêntico."""
    task, created = submeter_avaliacao_ferida(db, parameters.bundle, client_id=client_id)
    request.state.submitted_task_id = task.id
    return fhir_response(
        task, status_code=202 if created else 200,
        headers={"Content-Location": f"/api/fhir/r4/Task/{task.id}", "Retry-After": "2"},
        media_type=response_media_type,
    )


def _read_endpoint(resource_type: str):
    def read_resource(
        resource_id: str,
        db: Session = Depends(get_db),
        client_id: str = Depends(require_client),
        if_none_match: str | None = Header(default=None),
        if_modified_since: str | None = Header(default=None),
        response_media_type: str = Depends(require_fhir_accept),
    ):
        resource = ler_recurso(db, resource_type, resource_id, client_id=client_id)
        response = fhir_conditional_response(
            resource, if_none_match=if_none_match, if_modified_since=if_modified_since,
            media_type=response_media_type,
        )
        if resource_type == "Task" and resource["status"] in {"accepted", "in-progress"}:
            response.headers["Retry-After"] = "2"
        return response

    read_resource.__name__ = f"read_{resource_type.lower()}"
    return read_resource


for _resource_type in ("Task", "Bundle", "Media", "Patient", "Practitioner", "Encounter", "Condition", "Observation", "Device", "Provenance"):
    router.add_api_route(
        f"/{_resource_type}/{{resource_id}}", _read_endpoint(_resource_type),
        methods=["GET"], response_class=FHIRJSONResponse, summary=f"Consultar {_resource_type}",
    )
