"""Autenticação provisionada para ambientes controlados e auditoria de acesso."""

import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, Request
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from healplus_intake_image_api.core.config import settings
from healplus_intake_image_api.core.database import get_db
from healplus_intake_image_api.models.avaliacao_ferida import EventoAuditoria
from healplus_intake_image_api.services.avaliacao_ferida import FHIRRequestError

bearer = HTTPBearer(auto_error=False)


def require_client(request: Request,
                   credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    """Autentica tokens provisionados sem aceitar IDs declarados pelo cliente."""
    if authorized := getattr(request.state, "authorized_client", None):
        return authorized
    request.state.client_id = "anonymous"
    if not settings.api_client_tokens:
        raise FHIRRequestError(503, "security", "Configure API_CLIENT_TOKENS antes de usar os recursos clínicos")
    if settings.require_https and request.url.scheme != "https":
        raise FHIRRequestError(403, "security", "HTTPS obrigatório neste ambiente")
    if credentials is None:
        raise FHIRRequestError(401, "login", "Token Bearer obrigatório")
    supplied = hashlib.sha256(credentials.credentials.encode()).digest()
    matched = None
    for client_id, secret in settings.api_client_tokens.items():
        expected = hashlib.sha256(secret.get_secret_value().encode()).digest()
        if secrets.compare_digest(supplied, expected):
            matched = client_id
    if matched is None:
        raise FHIRRequestError(401, "login", "Credencial inválida")
    request.state.client_id = matched
    request.state.authorized_client = matched
    return matched


def record_access(db: Session, request: Request, status_code: int) -> None:
    """Grava AuditEvent R4 sem token, query string ou conteúdo da requisição."""
    event_id = str(uuid4())
    now = datetime.now(timezone.utc)
    client_id = getattr(request.state, "client_id", "anonymous")
    # A rota parametrizada evita registrar texto arbitrário ou informações de pacientes.
    route = request.scope.get("route")
    route_path = getattr(route, "path", "clinical-access")
    action = "R" if request.method == "GET" else "C"
    payload = {
        "resourceType": "AuditEvent", "id": event_id,
        "type": {"system": "http://terminology.hl7.org/CodeSystem/audit-event-type", "code": "rest"},
        "action": action, "recorded": now.isoformat(),
        "outcome": "0" if status_code < 400 else "4",
        "outcomeDesc": f"HTTP {status_code}",
        "agent": [{"who": {"identifier": {"system": "https://healplus.com.br/fhir/NamingSystem/api-client", "value": client_id}}, "requestor": True}],
        "source": {"observer": {"identifier": {"system": "https://healplus.com.br/fhir/NamingSystem/service", "value": "healplus-intake-image-api"}}},
        "entity": [{"name": route_path}],
    }
    # IDs do servidor são UUID; não copie parâmetros arbitrários para a trilha.
    from uuid import UUID
    for resource_id in request.path_params.values():
        try:
            safe_id = str(UUID(str(resource_id)))
        except ValueError:
            continue
        payload["entity"].append({"what": {"identifier": {"system": "urn:ietf:rfc:4122", "value": safe_id}}})
    if task_id := getattr(request.state, "submitted_task_id", None):
        payload["entity"].append({"what": {"reference": f"Task/{task_id}"}})
    db.add(EventoAuditoria(identificador=event_id, cliente_id=client_id, registrado_em=now, recurso_json=payload))
    db.commit()


class AuditedRoute(APIRoute):
    """Audita leituras, inclusive 304, submissões e recusas de autenticação."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def audited(request: Request):
            # Uma sessão independente cobre também JSON inválido e falhas que
            # ocorrem antes de FastAPI resolver as dependências da operação.
            provider = request.app.dependency_overrides.get(get_db, get_db)
            with contextmanager(provider)() as db:
                status_code = 500
                try:
                    credentials = await bearer(request)
                    require_client(request, credentials)
                    response = await original(request)
                    status_code = response.status_code
                    return response
                except Exception as error:
                    status_code = getattr(error, "status_code", 422 if hasattr(error, "errors") else 500)
                    raise
                finally:
                    try:
                        if status_code >= 400:
                            db.rollback()
                        record_access(db, request, status_code)
                    except Exception as error:
                        db.rollback()
                        # Falhar fechado: nenhuma leitura clínica sem trilha persistida.
                        if status_code < 400:
                            raise FHIRRequestError(503, "transient", "Auditoria indisponível") from error

        return audited
