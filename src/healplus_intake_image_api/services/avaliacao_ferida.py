"""Serviços de intake, idempotência e leitura restrita ao cliente autenticado."""

import hashlib
import json
import logging
from typing import Any

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from healplus_intake_image_api.repositories import avaliacao_ferida as repo
from healplus_intake_image_api.schemas.avaliacao_ferida import FHIRBundleCreate, resource_json
from healplus_intake_image_api.schemas.task import TaskResponse

logger = logging.getLogger(__name__)


class FHIRRequestError(Exception):
    """Erro da aplicação renderizado como OperationOutcome."""

    def __init__(self, status_code: int, issue_code: str, diagnostics: str,
                 expression: list[str] | None = None) -> None:
        self.status_code = status_code
        self.issue_code = issue_code
        self.diagnostics = diagnostics
        self.expression = expression or []
        super().__init__(diagnostics)


def _existing(db: Session, bundle: FHIRBundleCreate, client_id: str, fingerprint: str) -> TaskResponse | None:
    existing = repo.find_submission(db, client_id=client_id, system=bundle.identifier.system, value=bundle.identifier.value)
    if existing is None:
        return None
    if existing.conteudo_sha256 != fingerprint:
        raise FHIRRequestError(409, "conflict", "Bundle.identifier já utilizado com conteúdo diferente", ["Bundle.identifier"])
    return TaskResponse.model_validate(existing.tarefa.recurso_json)


def submeter_avaliacao_ferida(db: Session, bundle: FHIRBundleCreate, *, client_id: str) -> tuple[TaskResponse, bool]:
    """Retorna Task e indicador de criação; retries idênticos reutilizam a Task."""
    fingerprint = hashlib.sha256(json.dumps(resource_json(bundle), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    try:
        existing = _existing(db, bundle, client_id, fingerprint)
        if existing:
            return existing, False
        task = repo.criar_avaliacao(db, bundle, client_id=client_id, fingerprint=fingerprint)
        return TaskResponse.model_validate(task.recurso_json), True
    except IntegrityError as error:
        db.rollback()
        # A restrição única arbitra também dois POSTs simultâneos.
        existing = _existing(db, bundle, client_id, fingerprint)
        if existing:
            return existing, False
        raise FHIRRequestError(409, "conflict", "Conflito de identidade na submissão") from error
    except FHIRRequestError:
        raise
    except OperationalError as error:
        db.rollback()
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error
    except Exception as error:
        db.rollback()
        logger.error("Falha interna na submissão (%s)", type(error).__name__)
        raise FHIRRequestError(500, "exception", "Não foi possível persistir a avaliação") from error


def ler_recurso(db: Session, resource_type: str, resource_id: str, *, client_id: str) -> Any:
    """Retorna apenas recursos pertencentes ao cliente; demais IDs recebem 404."""
    try:
        if resource_type == "Task":
            task = repo.get_tarefa(db, resource_id, client_id=client_id)
            resource = task.recurso_json if task else None
        elif resource_type == "Bundle":
            bundle = repo.get_pacote(db, resource_id, client_id=client_id)
            resource = repo.hydrate_bundle(bundle) if bundle else None
        elif resource_type == "Media":
            media = repo.get_imagem(db, resource_id, client_id=client_id)
            resource = repo.hydrate_media(media) if media else None
        else:
            resource = repo.get_recurso_entrada(db, resource_type=resource_type, resource_id=resource_id, client_id=client_id)
        if resource is None:
            raise FHIRRequestError(404, "not-found", "Recurso não encontrado")
        return resource
    except FHIRRequestError:
        raise
    except OperationalError as error:
        db.rollback()
        raise FHIRRequestError(503, "transient", "Banco de dados indisponível") from error


def ler_tarefa(db: Session, resource_id: str, *, client_id: str) -> Any:
    return ler_recurso(db, "Task", resource_id, client_id=client_id)


def ler_pacote(db: Session, resource_id: str, *, client_id: str) -> Any:
    return ler_recurso(db, "Bundle", resource_id, client_id=client_id)


def ler_imagem(db: Session, resource_id: str, *, client_id: str) -> Any:
    return ler_recurso(db, "Media", resource_id, client_id=client_id)
