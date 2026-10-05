"""Rotas HTTP FHIR R4 para o intake de imagens clínicas do HealPlus."""

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from healplus_intake_image_api.core.database import get_db
from healplus_intake_image_api.core.fhir import (
    FHIRJSONResponse,
    fhir_conditional_response,
    fhir_response,
    require_fhir_accept,
    require_async_preference,
    require_fhir_request_content_type,
)
from healplus_intake_image_api.schemas.image import SubmitMediaParameters
from healplus_intake_image_api.services.image import (
    read_bundle,
    read_media,
    read_task,
    submit_media,
)

router = APIRouter(
    prefix="/api/fhir/r4",
    tags=["Intake de imagens FHIR R4"],
)


@router.post(
    "/$submit-media",
    summary="Submeter imagens para análise",
    description=(
        "Recebe um recurso `Parameters` com um `Bundle` do tipo `collection` "
        "contendo uma ou mais imagens clínicas `Media` em JPEG. A submissão "
        "cria uma `Task` FHIR para acompanhamento assíncrono."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    response_class=FHIRJSONResponse,
    dependencies=[
        Depends(require_fhir_request_content_type),
        Depends(require_async_preference),
    ],
)
def submit(
    parameters: SubmitMediaParameters,
    db: Session = Depends(get_db),
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Aceita um Bundle FHIR de imagens e cria uma Task de análise assíncrona.

    Args:
        parameters: Entrada de `$submit-media` com um único Bundle.
        db: Sessão do banco de dados.
        response_media_type: Tipo de mídia negociado para a resposta.

    Returns:
        Task FHIR aceita com URL para consulta.

    Raises:
        409: Já existe um recurso FHIR com o identificador submetido.
        415: O Content-Type da requisição não é FHIR JSON.
        422: A entrada não atende ao perfil FHIR HealPlus.
        503: O banco de dados está indisponível.
    """
    task = submit_media(db, parameters.bundle)
    return fhir_response(
        task,
        status_code=status.HTTP_202_ACCEPTED,
        headers={
            "Content-Location": f"/api/fhir/r4/Task/{task.id}",
            "Retry-After": "10",
        },
        media_type=response_media_type,
    )


@router.get(
    "/Task/{task_id}",
    summary="Consultar análise",
    description="Retorna a Task FHIR que acompanha uma análise de imagens.",
    response_class=FHIRJSONResponse,
)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém a Task FHIR que acompanha uma análise de imagens."""
    return fhir_conditional_response(
        read_task(db, task_id),
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        media_type=response_media_type,
    )


@router.get(
    "/Bundle/{bundle_id}",
    summary="Consultar Bundle submetido",
    description="Retorna o Bundle FHIR persistido para o intake de imagens.",
    response_class=FHIRJSONResponse,
)
def get_bundle(
    bundle_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém um Bundle FHIR collection submetido."""
    return fhir_conditional_response(
        read_bundle(db, bundle_id),
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        media_type=response_media_type,
    )


@router.get(
    "/Media/{media_id}",
    summary="Consultar imagem clínica",
    description="Retorna o recurso FHIR Media persistido para a imagem clínica.",
    response_class=FHIRJSONResponse,
)
def get_media(
    media_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém um recurso FHIR Media submetido."""
    return fhir_conditional_response(
        read_media(db, media_id),
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        media_type=response_media_type,
    )
