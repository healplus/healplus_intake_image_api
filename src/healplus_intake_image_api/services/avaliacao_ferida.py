"""Serviços de aplicação para entrada de avaliações FHIR de feridas."""

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from healplus_intake_image_api.models.avaliacao_ferida import TarefaAnalise
from healplus_intake_image_api.repositories.avaliacao_ferida import (
    criar_avaliacao as repo_criar_avaliacao,
    get_imagem as repo_get_imagem,
    get_pacote as repo_get_pacote,
    get_recurso_entrada as repo_get_recurso_entrada,
    get_tarefa as repo_get_tarefa,
)
from healplus_intake_image_api.schemas.avaliacao_ferida import FHIRBundleCreate
from healplus_intake_image_api.schemas.task import TaskResponse

logger = logging.getLogger(__name__)


class FHIRRequestError(Exception):
    """Erro da aplicação renderizado como um FHIR OperationOutcome."""

    def __init__(
        self,
        status_code: int,
        issue_code: str,
        diagnostics: str,
        expression: list[str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.issue_code = issue_code
        self.diagnostics = diagnostics
        self.expression = expression or []
        super().__init__(diagnostics)


def _resposta_tarefa(task: TarefaAnalise) -> TaskResponse:
    """Desserializa o recurso Task persistido."""
    return TaskResponse.model_validate(task.recurso_json)


def submeter_avaliacao_ferida(db: Session, bundle: FHIRBundleCreate) -> TaskResponse:
    """Persiste um Bundle de avaliação de ferida e cria sua Task de análise aceita.

    Args:
        db: Sessão do banco de dados.
        bundle: Bundle HealPlus de avaliação de ferida validado.

    Retorna:
        Task FHIR no status aceito.

    Gera:
        FHIRRequestError: Se não for possível persistir o Bundle.
    """
    try:
        task = repo_criar_avaliacao(db, bundle)
        logger.info(
            "Bundle FHIR de avaliação de ferida aceito",
            extra={"task_id": task.identificador, "entry_count": len(bundle.entry)},
        )
        return _resposta_tarefa(task)
    except IntegrityError as error:
        db.rollback()
        logger.exception(
            "Conflito de identidade de recurso FHIR ao submeter Bundle de avaliação de ferida"
        )
        raise FHIRRequestError(
            409,
            "duplicate",
            "Já existe um recurso Bundle com o identificador informado",
        ) from error
    except OperationalError as error:
        db.rollback()
        logger.exception(
            "Banco de dados indisponível ao submeter Bundle de avaliação de ferida"
        )
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        db.rollback()
        logger.exception(
            "Erro inesperado ao submeter Bundle de avaliação de ferida"
        )
        raise FHIRRequestError(
            500,
            "exception",
            "Não foi possível processar o Bundle FHIR submetido",
        ) from error


def ler_tarefa(db: Session, task_id: str) -> TaskResponse:
    """Obtém uma Task de análise pelo identificador FHIR."""
    try:
        task = repo_get_tarefa(db, task_id)
        if task is None:
            raise FHIRRequestError(404, "not-found", "Task não encontrada")
        return _resposta_tarefa(task)
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Banco de dados indisponível ao ler Task %s", task_id)
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        logger.exception("Erro inesperado ao ler Task %s", task_id)
        raise FHIRRequestError(500, "exception", "Não foi possível ler a Task") from error


def ler_pacote(db: Session, bundle_id: str) -> dict[str, Any]:
    """Obtém um Bundle FHIR submetido pelo identificador."""
    try:
        bundle = repo_get_pacote(db, bundle_id)
        if bundle is None:
            raise FHIRRequestError(404, "not-found", "Bundle não encontrado")
        return bundle.recurso_json
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Banco de dados indisponível ao ler Bundle %s", bundle_id)
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        logger.exception("Erro inesperado ao ler Bundle %s", bundle_id)
        raise FHIRRequestError(500, "exception", "Não foi possível ler o Bundle") from error


def ler_imagem(db: Session, media_id: str) -> dict[str, Any]:
    """Obtém um recurso FHIR Media submetido pelo identificador."""
    try:
        media = repo_get_imagem(db, media_id)
        if media is None:
            raise FHIRRequestError(404, "not-found", "Recurso Media não encontrado")
        return media.recurso_json
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Banco de dados indisponível ao ler Media %s", media_id)
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        logger.exception("Erro inesperado ao ler Media %s", media_id)
        raise FHIRRequestError(500, "exception", "Não foi possível ler o recurso Media") from error


def ler_atendimento(db: Session, encounter_id: str) -> dict[str, Any]:
    """Obtém um recurso FHIR Encounter submetido pelo identificador."""
    try:
        resource = repo_get_recurso_entrada(
            db,
            resource_type="Encounter",
            resource_id=encounter_id,
        )
        if resource is None:
            raise FHIRRequestError(404, "not-found", "Recurso Encounter não encontrado")
        return resource
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Banco de dados indisponível ao ler Encounter %s", encounter_id)
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        logger.exception("Erro inesperado ao ler Encounter %s", encounter_id)
        raise FHIRRequestError(500, "exception", "Não foi possível ler o recurso Encounter") from error


def ler_condicao(db: Session, condition_id: str) -> dict[str, Any]:
    """Obtém um recurso FHIR Condition submetido pelo identificador."""
    try:
        resource = repo_get_recurso_entrada(
            db,
            resource_type="Condition",
            resource_id=condition_id,
        )
        if resource is None:
            raise FHIRRequestError(404, "not-found", "Recurso Condition não encontrado")
        return resource
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Banco de dados indisponível ao ler Condition %s", condition_id)
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        logger.exception("Erro inesperado ao ler Condition %s", condition_id)
        raise FHIRRequestError(
            500,
            "exception",
            "Não foi possível ler o recurso Condition",
        ) from error


def ler_observacao(db: Session, observation_id: str) -> dict[str, Any]:
    """Obtém um recurso FHIR Observation submetido pelo identificador."""
    try:
        resource = repo_get_recurso_entrada(
            db,
            resource_type="Observation",
            resource_id=observation_id,
        )
        if resource is None:
            raise FHIRRequestError(
                404,
                "not-found",
                "Recurso Observation não encontrado",
            )
        return resource
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception(
            "Banco de dados indisponível ao ler Observation %s",
            observation_id,
        )
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        logger.exception("Erro inesperado ao ler Observation %s", observation_id)
        raise FHIRRequestError(
            500,
            "exception",
            "Não foi possível ler o recurso Observation",
        ) from error
