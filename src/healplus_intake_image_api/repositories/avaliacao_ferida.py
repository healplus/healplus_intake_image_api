"""Persistência de intake com identidade do servidor e uma cópia da imagem."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from healplus_intake_image_api.core.config import settings
from healplus_intake_image_api.core.audit import submission_event
from healplus_intake_image_api.models.avaliacao_ferida import (
    CodificacaoTipoImagem, EntradaPacote, ImagemClinica, PacoteFHIR, TarefaAnalise,
)
from healplus_intake_image_api.schemas.avaliacao_ferida import (
    HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE, HEALPLUS_MEDIA_PROFILE,
    FHIRBundleCreate, resource_json,
)
from healplus_intake_image_api.schemas.task import HEALPLUS_ANALYSIS_TASK_PROFILE

PROFILE_VERSION = "1.1.0"


def _com_meta_servidor(resource: dict, *, resource_id: str, profile: str, last_updated: datetime) -> dict:
    """Adiciona identidade e versão de perfil gerenciadas pelo servidor."""
    result = deepcopy(resource)
    result["id"] = resource_id
    meta = result.setdefault("meta", {})
    profiles = list(meta.get("profile", []))
    if profile:
        canonical = f"{profile}|{PROFILE_VERSION}"
        profiles = [p for p in profiles if p.split("|")[0] != profile]
        profiles.append(canonical)
    meta.update(versionId="1", lastUpdated=last_updated.isoformat().replace("+00:00", "Z"))
    if profiles:
        meta["profile"] = profiles
    result["meta"] = meta
    return result


def _rewrite_references(value: object, identities: dict[str, str]) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("reference"), str):
            value["reference"] = identities.get(value["reference"], value["reference"])
        for child in value.values():
            _rewrite_references(child, identities)
    elif isinstance(value, list):
        for child in value:
            _rewrite_references(child, identities)


def find_submission(db: Session, *, client_id: str, system: str, value: str) -> PacoteFHIR | None:
    return db.scalar(select(PacoteFHIR).where(
        PacoteFHIR.cliente_id == client_id,
        PacoteFHIR.sistema_identificador == system,
        PacoteFHIR.valor_identificador == value,
    ))


def criar_avaliacao(db: Session, bundle: FHIRBundleCreate, *, client_id: str, fingerprint: str) -> TarefaAnalise:
    """Persiste IDs UUID e referências resolvidas sem duplicar Attachment.data."""
    now = datetime.now(timezone.utc)
    bundle_id = str(uuid4())
    payload = _com_meta_servidor(resource_json(bundle), resource_id=bundle_id,
                               profile=HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE, last_updated=now)
    db_bundle = PacoteFHIR(
        identificador=bundle_id, cliente_id=client_id, conteudo_sha256=fingerprint,
        sistema_identificador=bundle.identifier.system, valor_identificador=bundle.identifier.value,
        instante=bundle.timestamp, atualizado_em=now,
    )
    identities: dict[str, str] = {}
    for entry in payload["entry"]:
        resource = entry["resource"]
        server_id = str(uuid4())
        relative = f'{resource["resourceType"]}/{server_id}'
        identities[entry["fullUrl"]] = relative
        if resource.get("id"):
            identities[f'{resource["resourceType"]}/{resource["id"]}'] = relative
        resource["id"] = server_id
    _rewrite_references(payload, identities)
    # Referências relativas só resolvem em Bundles com fullUrl RESTful.
    # A base vem da configuração, jamais de um Host arbitrário da requisição.
    for entry in payload["entry"]:
        resource = entry["resource"]
        entry["fullUrl"] = f'{settings.fhir_base_url}/{resource["resourceType"]}/{resource["id"]}'
    media_refs = []
    subject_reference = None
    for index, entry in enumerate(payload["entry"]):
        resource = entry["resource"]
        kind = resource["resourceType"]
        profile = HEALPLUS_MEDIA_PROFILE if kind == "Media" else ""
        resource = _com_meta_servidor(resource, resource_id=resource["id"], profile=profile, last_updated=now)
        if kind == "Patient":
            subject_reference = f'Patient/{resource["id"]}'
        if kind == "Media":
            media_refs.append(f'Media/{resource["id"]}')
            data = resource["content"].pop("data")
            db_bundle.imagens.append(ImagemClinica(
                identificador=resource["id"], url_completa=entry["fullUrl"], estado=resource["status"],
                referencia_sujeito=resource["subject"]["reference"],
                referencia_atendimento=resource["encounter"]["reference"],
                criado_em=datetime.fromisoformat(resource["createdDateTime"].replace("Z", "+00:00")),
                tipo_conteudo=resource["content"]["contentType"], conteudo=data,
                recurso_json=deepcopy(resource), atualizado_em=now,
                codificacoes_tipo=[CodificacaoTipoImagem(sistema=c.get("system"), codigo=c.get("code"), exibicao=c.get("display"))
                                   for c in resource["type"].get("coding", [])],
            ))
        entry["resource"] = deepcopy(resource)
        db_bundle.entradas.append(EntradaPacote(
            indice_entrada=index, url_completa=entry["fullUrl"], tipo_recurso=kind,
            recurso_id=resource["id"], recurso_json=deepcopy(resource),
        ))
    db_bundle.recurso_json = payload
    task_id = str(uuid4())
    deadline = now + timedelta(seconds=settings.analysis_timeout_seconds)
    task_payload = _com_meta_servidor({
        "resourceType": "Task", "status": "accepted", "intent": "order",
        "focus": {"reference": f"Bundle/{bundle_id}"},
        "code": {"coding": [{"system": "https://healplus.com.br/fhir/CodeSystem/tarefa-analise", "version": "1.1.0", "code": "analise-qualidade-imagem"}]},
        "authoredOn": now.isoformat().replace("+00:00", "Z"), "lastModified": now.isoformat().replace("+00:00", "Z"),
        "restriction": {"period": {"end": deadline.isoformat().replace("+00:00", "Z")}},
        "input": [{"type": {"coding": [{"system": "https://healplus.com.br/fhir/CodeSystem/tarefa-analise", "version": "1.1.0", "code": "imagem-avaliada"}]}, "valueReference": {"reference": ref}} for ref in media_refs],
        "for": {"reference": subject_reference},
    }, resource_id=task_id, profile=HEALPLUS_ANALYSIS_TASK_PROFILE, last_updated=now)
    task = TarefaAnalise(identificador=task_id, estado="accepted", referencia_sujeito=subject_reference,
                        recurso_json=task_payload, criado_em=now, atualizado_em=now,
                        deadline_at=deadline, attempts=0)
    db_bundle.tarefa = task
    db.add(db_bundle)
    db.add(submission_event(client_id, task_id))
    db.commit()
    db.refresh(task)
    return task


def get_tarefa(db: Session, task_id: str, *, client_id: str) -> TarefaAnalise | None:
    return db.scalar(select(TarefaAnalise).join(PacoteFHIR).where(
        TarefaAnalise.identificador == task_id, PacoteFHIR.cliente_id == client_id))


def get_pacote(db: Session, bundle_id: str, *, client_id: str) -> PacoteFHIR | None:
    return db.scalar(select(PacoteFHIR).where(PacoteFHIR.identificador == bundle_id, PacoteFHIR.cliente_id == client_id))


def get_imagem(db: Session, media_id: str, *, client_id: str) -> ImagemClinica | None:
    return db.scalar(select(ImagemClinica).join(PacoteFHIR).where(
        ImagemClinica.identificador == media_id, PacoteFHIR.cliente_id == client_id))


def hydrate_media(media: ImagemClinica) -> dict:
    payload = deepcopy(media.recurso_json)
    payload["content"]["data"] = media.conteudo
    return payload


def hydrate_bundle(bundle: PacoteFHIR) -> dict:
    """Reconstitui o snapshot original, sem incorporar resultados posteriores."""
    payload = deepcopy(bundle.recurso_json)
    media_by_id = {media.identificador: media for media in bundle.imagens}
    for entry in payload["entry"]:
        resource = entry["resource"]
        if resource["resourceType"] == "Media":
            entry["resource"] = hydrate_media(media_by_id[resource["id"]])
    return payload


def get_recurso_entrada(db: Session, *, resource_type: str, resource_id: str, client_id: str) -> dict | None:
    entry = db.scalar(select(EntradaPacote).join(PacoteFHIR).where(
        EntradaPacote.tipo_recurso == resource_type, EntradaPacote.recurso_id == resource_id,
        PacoteFHIR.cliente_id == client_id))
    return deepcopy(entry.recurso_json) if entry else None
