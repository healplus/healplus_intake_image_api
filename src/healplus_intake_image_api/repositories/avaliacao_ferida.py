"""Operações de banco de dados para recursos FHIR de avaliação de feridas HealPlus."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from healplus_intake_image_api.models.avaliacao_ferida import (
    CodificacaoTipoImagem,
    EntradaPacote,
    ImagemClinica,
    PacoteFHIR,
    TarefaAnalise,
)
from healplus_intake_image_api.schemas.avaliacao_ferida import (
    HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE,
    HEALPLUS_MEDIA_PROFILE,
    FHIRBundleCreate,
    MediaCreate,
    resource_json,
)
from healplus_intake_image_api.schemas.task import (
    HEALPLUS_ANALYSIS_TASK_PROFILE,
    TaskStatus,
)


def _com_meta_servidor(
    resource: dict,
    *,
    resource_id: str,
    profile: str,
    last_updated: datetime,
) -> dict:
    """Adiciona identidade e metadados FHIR gerenciados pelo servidor a um dicionário."""
    result = {**resource, "id": resource_id}
    meta = {**result.get("meta", {})}
    profiles = list(meta.get("profile", []))
    if profile and profile not in profiles:
        profiles.append(profile)
    meta.update(
        {
            "versionId": "1",
            "lastUpdated": last_updated.isoformat().replace("+00:00", "Z"),
            "profile": profiles,
        }
    )
    result["meta"] = meta
    return result


def criar_avaliacao(
    db: Session,
    bundle: FHIRBundleCreate,
) -> TarefaAnalise:
    """Persiste um Bundle submetido, seus recursos Media e sua Task de análise.

    Args:
        db: Sessão do banco de dados.
        bundle: Bundle validado da operação $avaliar-feridas.

    Retorna:
        A Task persistida no estado aceito.
    """
    now = datetime.now(timezone.utc)
    bundle_id = bundle.id or str(uuid4())
    bundle_payload = _com_meta_servidor(
        resource_json(bundle),
        resource_id=bundle_id,
        profile=HEALPLUS_WOUND_ASSESSMENT_BUNDLE_PROFILE,
        last_updated=now,
    )
    db_bundle = PacoteFHIR(
        identificador=bundle_id,
        sistema_identificador=bundle.identifier.system if bundle.identifier else None,
        valor_identificador=bundle.identifier.value if bundle.identifier else None,
        instante=bundle.timestamp,
        recurso_json=bundle_payload,
        atualizado_em=now,
    )

    for index, entry in enumerate(bundle.entry):
        resource = entry.resource
        resource_id = getattr(resource, "id", None) or str(uuid4())
        profile = HEALPLUS_MEDIA_PROFILE if isinstance(resource, MediaCreate) else ""
        media_payload = _com_meta_servidor(
            resource_json(resource),
            resource_id=resource_id,
            profile=profile,
            last_updated=now,
        )
        bundle_payload["entry"][index]["resource"] = media_payload
        db_bundle.entradas.append(
            EntradaPacote(
                indice_entrada=index,
                url_completa=entry.full_url,
                tipo_recurso=resource.resource_type,
                recurso_id=resource_id,
                recurso_json=media_payload,
            )
        )
        if not isinstance(resource, MediaCreate):
            continue
        db_bundle.imagens.append(
            ImagemClinica(
                identificador=resource_id,
                url_completa=entry.full_url,
                estado=resource.status,
                referencia_sujeito=resource.subject.reference or "",
                referencia_atendimento=(
                    resource.encounter.reference if resource.encounter else None
                ),
                criado_em=resource.created_date_time,
                tipo_conteudo=resource.content.content_type,
                conteudo=resource.content.data,
                recurso_json=media_payload,
                atualizado_em=now,
                codificacoes_tipo=[
                    CodificacaoTipoImagem(
                        sistema=coding.system,
                        codigo=coding.code,
                        exibicao=coding.display,
                    )
                    for coding in resource.type.coding
                ],
            )
        )

    task_id = str(uuid4())
    subject_reference = bundle.patient_reference
    task_payload = {
        "resourceType": "Task",
        "id": task_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": now.isoformat().replace("+00:00", "Z"),
            "profile": [HEALPLUS_ANALYSIS_TASK_PROFILE],
        },
        "status": TaskStatus.ACCEPTED.value,
        "intent": "order",
        "focus": {"reference": f"Bundle/{bundle_id}"},
        "authoredOn": now.isoformat().replace("+00:00", "Z"),
        "lastModified": now.isoformat().replace("+00:00", "Z"),
    }
    if subject_reference:
        task_payload["for"] = {"reference": subject_reference}

    db_task = TarefaAnalise(
        identificador=task_id,
        estado=TaskStatus.ACCEPTED.value,
        referencia_sujeito=subject_reference,
        recurso_json=task_payload,
        criado_em=now,
        atualizado_em=now,
    )
    db_bundle.tarefa = db_task
    db.add(db_bundle)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_tarefa(db: Session, task_id: str) -> TarefaAnalise | None:
    """Retorna uma Task de análise por seu identificador FHIR."""
    return db.get(TarefaAnalise, task_id)


def get_pacote(db: Session, bundle_id: str) -> PacoteFHIR | None:
    """Retorna um Bundle submetido por seu identificador FHIR."""
    return db.get(PacoteFHIR, bundle_id)


def get_imagem(db: Session, media_id: str) -> ImagemClinica | None:
    """Retorna um recurso Media submetido por seu identificador FHIR."""
    return db.get(ImagemClinica, media_id)


def get_recurso_entrada(
    db: Session,
    *,
    resource_type: str,
    resource_id: str,
) -> dict | None:
    """Retorna o JSON de um recurso persistido por tipo e identificador do Bundle."""
    entry = (
        db.query(EntradaPacote)
        .filter(
            EntradaPacote.tipo_recurso == resource_type,
            EntradaPacote.recurso_id == resource_id,
        )
        .order_by(EntradaPacote.identificador.desc())
        .first()
    )
    if entry is None:
        return None
    return entry.recurso_json
