"""Construção de eventos FHIR de auditoria sem conteúdo clínico ou segredos."""

from datetime import datetime, timezone
from uuid import uuid4

from healplus_intake_image_api.models.avaliacao_ferida import EventoAuditoria


def submission_event(client_id: str, task_id: str) -> EventoAuditoria:
    """Evento persistido na mesma transação da criação da Task."""
    event_id = str(uuid4())
    now = datetime.now(timezone.utc)
    return EventoAuditoria(identificador=event_id, cliente_id=client_id, registrado_em=now, recurso_json={
        "resourceType": "AuditEvent", "id": event_id,
        "type": {"system": "http://terminology.hl7.org/CodeSystem/audit-event-type", "code": "rest"},
        "action": "C", "recorded": now.isoformat(), "outcome": "0", "outcomeDesc": "Intake persistido",
        "agent": [{"who": {"identifier": {"system": "https://healplus.com.br/fhir/NamingSystem/api-client", "value": client_id}}, "requestor": True}],
        "source": {"observer": {"identifier": {"system": "https://healplus.com.br/fhir/NamingSystem/service", "value": "healplus-intake-image-api"}}},
        "entity": [{"what": {"reference": f"Task/{task_id}"}}],
    })
