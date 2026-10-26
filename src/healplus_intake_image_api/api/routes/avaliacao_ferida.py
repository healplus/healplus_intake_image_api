"""Rotas HTTP FHIR R4 para avaliação clínica de feridas no HealPlus."""

from fastapi import APIRouter, Body, Depends, Header, Response, status
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
from healplus_intake_image_api.schemas.avaliacao_ferida import AvaliacaoFeridaParameters
from healplus_intake_image_api.services.avaliacao_ferida import (
    ler_atendimento,
    ler_condicao,
    ler_imagem,
    ler_observacao,
    ler_pacote,
    ler_tarefa,
    submeter_avaliacao_ferida,
)

router = APIRouter(
    prefix="/api/fhir/r4",
    tags=["Avaliação clínica de feridas FHIR R4"],
)


@router.post(
    "/$avaliar-feridas",
    summary="Submeter avaliação de feridas",
    description=(
        "Recebe um recurso `Parameters` com um `Bundle` do tipo `collection` "
        "contendo os recursos clínicos da avaliação de ferida em FHIR R4. "
        "A submissão cria uma `Task` FHIR para acompanhamento assíncrono."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    response_class=FHIRJSONResponse,
    dependencies=[
        Depends(require_fhir_request_content_type),
        Depends(require_async_preference),
    ],
)
def submeter_avaliacao(
    parameters: AvaliacaoFeridaParameters = Body(media_type="application/fhir+json"),
    db: Session = Depends(get_db),
    response_media_type: str = Depends(require_fhir_accept),
) -> FHIRJSONResponse:
    """Aceita um Bundle FHIR de avaliação e cria uma Task de análise assíncrona.

    Args:
        parameters: Entrada de `$avaliar-feridas` com um único Bundle.
        db: Sessão do banco de dados.
        response_media_type: Tipo de mídia negociado para a resposta.

    Retorna:
        Task FHIR aceita com URL para consulta.

    Gera:
        409: Já existe um recurso FHIR com o identificador submetido.
        415: O Content-Type da requisição não é FHIR JSON.
        422: A entrada não atende ao perfil FHIR HealPlus.
        503: O banco de dados está indisponível.
    """
    task = submeter_avaliacao_ferida(db, parameters.bundle)
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
def get_tarefa(
    task_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém a Task FHIR que acompanha uma análise de imagens."""
    return fhir_conditional_response(
        ler_tarefa(db, task_id),
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
def get_pacote(
    bundle_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém um Bundle FHIR collection submetido."""
    return fhir_conditional_response(
        ler_pacote(db, bundle_id),
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
def get_imagem(
    media_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém um recurso FHIR Media submetido."""
    return fhir_conditional_response(
        ler_imagem(db, media_id),
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        media_type=response_media_type,
    )


@router.get(
    "/Encounter/{encounter_id}",
    summary="Consultar atendimento",
    description="Retorna o recurso FHIR Encounter persistido.",
    response_class=FHIRJSONResponse,
)
def get_atendimento(
    encounter_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém um recurso FHIR Encounter submetido."""
    return fhir_conditional_response(
        ler_atendimento(db, encounter_id),
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        media_type=response_media_type,
    )


@router.get(
    "/Condition/{condition_id}",
    summary="Consultar condição clínica",
    description="Retorna o recurso FHIR Condition persistido.",
    response_class=FHIRJSONResponse,
)
def get_condicao(
    condition_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém um recurso FHIR Condition submetido."""
    return fhir_conditional_response(
        ler_condicao(db, condition_id),
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        media_type=response_media_type,
    )


@router.get(
    "/Observation/{observation_id}",
    summary="Consultar observação clínica",
    description="Retorna o recurso FHIR Observation persistido.",
    response_class=FHIRJSONResponse,
)
def get_observacao(
    observation_id: str,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
    response_media_type: str = Depends(require_fhir_accept),
) -> Response:
    """Obtém um recurso FHIR Observation submetido."""
    return fhir_conditional_response(
        ler_observacao(db, observation_id),
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        media_type=response_media_type,
    )
