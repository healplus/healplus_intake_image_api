"""Análise técnica demonstrativa e fila durável de qualidade de fotografias.

Os limiares v0 são de engenharia, sem validação clínica. Não se detectam cartão,
ferida, tom de pele ou diagnóstico. Critérios não implementados são explícitos.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import io
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import PIL
from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from healplus_intake_image_api.core.config import settings
from healplus_intake_image_api.models.avaliacao_ferida import (
    EntradaPacote,
    ImagemClinica,
    TarefaAnalise,
)

logger = logging.getLogger(__name__)
CONTRACT_VERSION = "1.1.0"
ALGORITHM_VERSION = "0.1.0"
PREPROCESSING_VERSION = "grayscale-thumbnail-512-v1"
PROTOCOL = "https://healplus.com.br/fhir/protocolo/qualidade-tecnica-demonstrativa|0.1.0"
PROFILE_BASE = "https://healplus.com.br/fhir/StructureDefinition/"
SYSTEM_BASE = "https://healplus.com.br/fhir/CodeSystem/"
ASSISTIVE_NOTE = (
    "Resultado técnico assistivo sobre a fotografia. Não avalia a ferida, não "
    "diagnostica, não infere dor e não define conduta. Limiares demonstrativos "
    "sem validação clínica; referência física, cor, enquadramento e privacidade "
    "visual exigem revisão humana."
)
UNSUPPORTED_CRITERIA = (
    "referencia-escala-detectada", "referencia-cor-detectada", "desvio-cor-delta-e",
    "resolucao-espacial", "angulo-captura", "reflexo", "enquadramento",
    "ita-pele-perilesional",
)


@dataclass(frozen=True)
class QualityThresholds:
    """Limiar v0 de demonstração, fixo e igual para todas as imagens."""

    min_sharpness: float = 100.0
    min_dimension: int = 512
    max_clipped_fraction: float = 0.40
    dark_pixel: int = 10
    bright_pixel: int = 245
    score_accept: float = 0.75
    score_caution: float = 0.55


THRESHOLDS = QualityThresholds()


class InvalidImageError(ValueError):
    """Arquivo persistido não pode ser decodificado para análise."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _instant(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def concept(system: str, code: str, text: str | None = None) -> dict:
    """Cria codificação HealPlus versionada."""
    result = {"coding": [{"system": SYSTEM_BASE + system, "version": CONTRACT_VERSION, "code": code}]}
    if text:
        result["text"] = text
    return result


def _quantity(value: float, unit: str = "1") -> dict:
    return {"value": round(value, 6), "system": "http://unitsofmeasure.org", "code": unit}


def _metric(code: str, value: float, *, low: float | None = None,
            high: float | None = None, unit: str = "1", text: str = "") -> dict:
    reference_range = {"text": text or "Limiar técnico demonstrativo v0, sem validação clínica"}
    if low is not None:
        reference_range["low"] = _quantity(low, unit)
    if high is not None:
        reference_range["high"] = _quantity(high, unit)
    interpretation = "L" if low is not None and value < low else "H" if high is not None and value > high else "N"
    return {
        "code": concept("criterio-qualidade-imagem", code),
        "valueQuantity": _quantity(value, unit),
        "referenceRange": [reference_range],
        "interpretation": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
            "code": interpretation,
        }]}],
    }


def measure_image(image_bytes: bytes) -> dict[str, float]:
    """Mede variância laplaciana e saturação em escala de cinza de até 512 px.

    O thumbnail preserva proporção, nunca amplia e usa LANCZOS. Não se modifica
    o arquivo original. As métricas não medem foco da ferida nem calibração.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            if source.format != "JPEG":
                raise InvalidImageError("JPEG esperado")
            width, height = source.size
            if width * height > getattr(settings, "max_image_pixels", 24_000_000):
                raise InvalidImageError("Imagem excede limite de pixels")
            source.load()
            gray = source.convert("L")
            gray.thumbnail((512, 512), Image.Resampling.LANCZOS)
            data = list(gray.tobytes())
            sample_width, sample_height = gray.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as error:
        raise InvalidImageError("JPEG persistido inválido") from error
    if sample_width < 3 or sample_height < 3:
        raise InvalidImageError("Imagem insuficiente para medir nitidez")
    lap_sum = lap_square_sum = count = 0
    for y in range(1, sample_height - 1):
        for x in range(1, sample_width - 1):
            index = y * sample_width + x
            lap = (data[index - 1] + data[index + 1] + data[index - sample_width]
                   + data[index + sample_width] - 4 * data[index])
            lap_sum += lap
            lap_square_sum += lap * lap
            count += 1
    return {
        "sharpness": max(0.0, lap_square_sum / count - (lap_sum / count) ** 2),
        "exposure": sum(data) / (len(data) * 255),
        "dark_fraction": sum(v <= THRESHOLDS.dark_pixel for v in data) / len(data),
        "bright_fraction": sum(v >= THRESHOLDS.bright_pixel for v in data) / len(data),
        "min_dimension": min(width, height),
    }


def analyze_image(image_bytes: bytes, media: dict, *, device_id: str,
                  issued: datetime | None = None, metadata_reference: str | None = None) -> dict:
    """Produz Observation técnica FHIR, sem inferência clínica nem cartão fictício."""
    issued = issued or utc_now()
    measured = measure_image(image_bytes)
    sharpness_score = min(1.0, measured["sharpness"] / THRESHOLDS.min_sharpness)
    resolution_score = min(1.0, measured["min_dimension"] / THRESHOLDS.min_dimension)
    clipped = max(measured["dark_fraction"], measured["bright_fraction"])
    exposure_score = max(0.0, 1.0 - clipped)
    score = 0.55 * sharpness_score + 0.25 * exposure_score + 0.20 * resolution_score
    failures = []
    if measured["sharpness"] < THRESHOLDS.min_sharpness:
        failures.append(("desfocada", "estabilizar-e-focar", "Apoie o aparelho, ajuste o foco e aguarde a imagem estabilizar."))
    if measured["min_dimension"] < THRESHOLDS.min_dimension:
        failures.append(("baixa-resolucao", "aumentar-resolucao", "Capture novamente com resolução maior e sem reduzir a imagem."))
    if measured["dark_fraction"] > THRESHOLDS.max_clipped_fraction:
        failures.append(("subexposta", "ajustar-iluminacao", "Aumente a iluminação difusa e evite sombras sobre a região fotografada."))
    if measured["bright_fraction"] > THRESHOLDS.max_clipped_fraction:
        failures.append(("superexposta", "ajustar-iluminacao", "Reduza a luz direta e evite áreas brancas sem detalhe."))
    # Critérios essenciais ainda não implementados impedem um aceite irrestrito.
    verdict = "rejeitada" if failures or score < THRESHOLDS.score_caution else "aceita-com-ressalva"
    components = [
        _metric("escore-global", score, low=THRESHOLDS.score_accept),
        _metric("nitidez", measured["sharpness"], low=THRESHOLDS.min_sharpness,
                text="Variância do laplaciano 4-vizinhos, cinza, thumbnail LANCZOS até 512 px; limiar demonstrativo"),
        _metric("exposicao-media", measured["exposure"], low=0, high=1,
                text="Média de intensidade normalizada; faixa matemática, sem limiar clínico"),
        _metric("pixels-subexpostos", measured["dark_fraction"], high=THRESHOLDS.max_clipped_fraction,
                text=f"Fração de pixels cinza <= {THRESHOLDS.dark_pixel}; limiar demonstrativo"),
        _metric("pixels-saturados", measured["bright_fraction"], high=THRESHOLDS.max_clipped_fraction,
                text=f"Fração de pixels cinza >= {THRESHOLDS.bright_pixel}; limiar demonstrativo"),
        _metric("resolucao-menor-dimensao", measured["min_dimension"], low=THRESHOLDS.min_dimension, unit="{pixel}"),
        {"code": concept("criterio-qualidade-imagem", "integridade-arquivo"), "valueBoolean": True,
         "referenceRange": [{"text": "JPEG decodificável obrigatório; SHA-1 validado no intake"}]},
    ]
    components[0]["referenceRange"].append({"low": _quantity(THRESHOLDS.score_caution), "text": "Limiar técnico demonstrativo de ressalva"})
    for criterion in UNSUPPORTED_CRITERIA:
        components.append({"code": concept("criterio-qualidade-imagem", criterion), "dataAbsentReason": {"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/data-absent-reason", "code": "unsupported",
        }]}})
    failures.append(("criterios-nao-avaliados", "revisar-criterios-nao-avaliados",
                     "Solicite revisão humana da escala, cor, enquadramento e privacidade visual; estes critérios não foram calculados."))
    for reason, guidance, text in failures:
        components.extend([
            {"code": concept("criterio-qualidade-imagem", "motivo-rejeicao"),
             "valueCodeableConcept": concept("motivo-rejeicao-imagem", reason)},
            {"code": concept("criterio-qualidade-imagem", "orientacao-recaptura"),
             "valueCodeableConcept": concept("orientacao-recaptura", guidance, text)},
        ])
    meta = {"versionId": "1", "lastUpdated": _instant(issued),
            "profile": [PROFILE_BASE + "HealPlusResultadoQualidadeImagem|" + CONTRACT_VERSION]}
    if media.get("meta", {}).get("security"):
        meta["security"] = copy.deepcopy(media["meta"]["security"])
    media_ref = {"reference": "Media/" + media["id"]}
    result = {
        "resourceType": "Observation", "id": str(uuid4()), "meta": meta, "status": "preliminary",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "imaging"}]}],
        "code": concept("avaliacao-ferida", "resultado-qualidade-imagem"),
        "focus": [media_ref], "derivedFrom": [media_ref],
        "effectiveDateTime": media["createdDateTime"], "issued": _instant(issued),
        "method": concept("avaliacao-ferida", "analise-automatizada-qualidade-imagem"),
        "device": {"reference": "Device/" + device_id},
        "valueCodeableConcept": concept("veredito-qualidade-imagem", verdict),
        "component": components, "note": [{"text": ASSISTIVE_NOTE}],
    }
    for field in ("subject", "encounter"):
        if media.get(field):
            result[field] = copy.deepcopy(media[field])
    if metadata_reference:
        result["derivedFrom"].append({"reference": metadata_reference})
    return result


def algorithm_device(device_id: str, now: datetime) -> dict:
    """Identifica código e configuração realmente executados, sem pesos fictícios."""
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config_hash = hashlib.sha256(json.dumps(asdict(THRESHOLDS), sort_keys=True).encode()).hexdigest()
    return {
        "resourceType": "Device", "id": device_id,
        "meta": {"versionId": "1", "lastUpdated": _instant(now), "profile": [PROFILE_BASE + "HealPlusModeloQualidadeImagem|" + CONTRACT_VERSION]},
        "contained": [{"resourceType": "DeviceDefinition", "id": "quality-algorithm", "manufacturerString": "HealPlus", "modelNumber": ALGORITHM_VERSION}],
        "definition": {"reference": "#quality-algorithm"}, "status": "active", "manufacturer": "HealPlus",
        "deviceName": [{"name": "Qualidade técnica demonstrativa sem modelo treinado", "type": "user-friendly-name"}],
        "identifier": [{"system": "https://healplus.com.br/fhir/NamingSystem/algoritmo-sha256", "value": source_hash}],
        "version": [
            {"type": {"text": "algoritmo"}, "value": ALGORITHM_VERSION},
            {"type": {"text": "codigo-sha256"}, "value": source_hash},
            {"type": {"text": "pre-processamento"}, "value": PREPROCESSING_VERSION},
            {"type": {"text": "limiares-sha256"}, "value": config_hash},
            {"type": {"text": "Pillow"}, "value": PIL.__version__},
            {"type": {"text": "api"}, "value": getattr(settings, "api_version", "0.2.0")},
        ],
    }


def _provenance(observation: dict, media: dict, image_bytes: bytes, device_id: str, now: datetime) -> dict:
    sha256 = base64.urlsafe_b64encode(hashlib.sha256(image_bytes).digest()).decode().rstrip("=")
    return {
        "resourceType": "Provenance", "id": str(uuid4()),
        "meta": {"versionId": "1", "lastUpdated": _instant(now), "profile": [PROFILE_BASE + "HealPlusProvenienciaAnaliseQualidade|" + CONTRACT_VERSION]},
        "target": [{"reference": "Observation/" + observation["id"]}],
        "recorded": _instant(now), "policy": [PROTOCOL],
        "activity": concept("atividade-proveniencia", "analise-qualidade-imagem"),
        "agent": [{"type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type", "code": "performer"}]},
                   "who": {"reference": "Device/" + device_id}}],
        "entity": [{"role": "source", "what": {"reference": "Media/" + media["id"],
                    "identifier": {"system": "urn:ietf:rfc:6920", "value": "ni:///sha-256;" + sha256}}}],
    }


def _task_payload(task: TarefaAnalise, status: str, now: datetime) -> dict:
    payload = copy.deepcopy(task.recurso_json)
    payload.update({"status": status, "lastModified": _instant(now)})
    payload.setdefault("meta", {}).update({"versionId": str(task.id_versao + 1), "lastUpdated": _instant(now)})
    payload["meta"]["profile"] = [PROFILE_BASE + "HealPlusTarefaAnalise|" + CONTRACT_VERSION]
    payload["code"] = concept("tarefa-analise", "analise-qualidade-imagem")
    if task.deadline_at:
        payload["restriction"] = {"period": {"end": _instant(task.deadline_at)}}
    return payload


def _eligible(now: datetime):
    return or_(
        and_(TarefaAnalise.estado == "accepted", or_(TarefaAnalise.next_attempt_at.is_(None), TarefaAnalise.next_attempt_at <= now)),
        and_(TarefaAnalise.estado == "in-progress", or_(TarefaAnalise.lease_expires_at.is_(None), TarefaAnalise.lease_expires_at <= now)),
    )


def _fail_unclaimed(db: Session, task: TarefaAnalise, now: datetime, reason: str) -> bool:
    payload = _task_payload(task, "failed", now)
    payload["statusReason"] = concept("motivo-falha-analise", reason)
    payload.setdefault("executionPeriod", {})["end"] = _instant(now)
    changed = db.execute(update(TarefaAnalise).where(
        TarefaAnalise.identificador == task.identificador, _eligible(now), TarefaAnalise.attempts == task.attempts,
    ).values(estado="failed", recurso_json=payload, id_versao=task.id_versao + 1,
             atualizado_em=now, lease_expires_at=None, next_attempt_at=None, last_error=reason),
             execution_options={"synchronize_session": False}).rowcount
    db.commit()
    db.expire_all()
    return bool(changed)


def process_task(db: Session, task_id: str) -> bool:
    """Reivindica e processa uma Task com lease, fencing, retry e limite de prazo.

    Retorna False se outra instância já detém o trabalho ou se a Task é terminal.
    As saídas e o estado completed são gravados numa única transação.
    """
    now = utc_now()
    db.expire_all()
    task = db.get(TarefaAnalise, task_id)
    if task is None or task.estado not in {"accepted", "in-progress"}:
        db.rollback()
        return False
    if task.estado == "accepted" and task.next_attempt_at and _utc(task.next_attempt_at) > now:
        db.rollback()
        return False
    if task.estado == "in-progress" and task.lease_expires_at and _utc(task.lease_expires_at) > now:
        db.rollback()
        return False
    deadline = _utc(task.deadline_at or (_utc(task.criado_em) + timedelta(seconds=getattr(settings, "analysis_timeout_seconds", 120))))
    if deadline <= now:
        return _fail_unclaimed(db, task, now, "tempo-esgotado")
    if task.attempts >= getattr(settings, "analysis_max_attempts", 3):
        return _fail_unclaimed(db, task, now, "limite-tentativas")
    generation = task.attempts + 1
    lease = min(deadline, now + timedelta(seconds=getattr(settings, "analysis_lease_seconds", 60)))
    payload = _task_payload(task, "in-progress", now)
    payload.pop("statusReason", None)
    payload.setdefault("executionPeriod", {}).setdefault("start", _instant(now))
    changed = db.execute(update(TarefaAnalise).where(
        TarefaAnalise.identificador == task_id, _eligible(now), TarefaAnalise.attempts == task.attempts,
    ).values(estado="in-progress", attempts=generation, deadline_at=deadline, lease_expires_at=lease,
             next_attempt_at=None, recurso_json=payload, id_versao=task.id_versao + 1, atualizado_em=now),
             execution_options={"synchronize_session": False}).rowcount
    db.commit()
    db.expire_all()
    if not changed:
        return False
    try:
        task = db.get(TarefaAnalise, task_id)
        images = list(task.pacote.imagens)
        if not images:
            raise InvalidImageError("Task sem imagem")
        device_id = str(uuid4())
        resources = [algorithm_device(device_id, now)]
        observations = []
        for image in images:
            try:
                raw = base64.b64decode(image.conteudo, validate=True)
            except (binascii.Error, ValueError) as error:
                raise InvalidImageError("Base64 persistido inválido") from error
            media = copy.deepcopy(image.recurso_json)
            attachment = media.get("content", {})
            if attachment.get("size") is not None and attachment["size"] != len(raw):
                raise InvalidImageError("Tamanho persistido divergente")
            if attachment.get("hash") and attachment["hash"] != base64.b64encode(hashlib.sha1(raw).digest()).decode():
                raise InvalidImageError("Hash persistido divergente")
            metadata_reference = None
            for entry in task.pacote.entradas:
                entry_json = entry.recurso_json
                if entry.tipo_recurso == "Observation" and any(
                    coding.get("code") == "metadados-captura-imagem"
                    for coding in entry_json.get("code", {}).get("coding", [])
                ) and any(ref.get("reference") in {"Media/" + image.identificador, image.url_completa}
                          for ref in entry_json.get("derivedFrom", [])):
                    metadata_reference = "Observation/" + entry.recurso_id
                    break
            observation = analyze_image(raw, media, device_id=device_id, metadata_reference=metadata_reference)
            observations.append(observation)
            resources.extend([observation, _provenance(observation, media, raw, device_id, utc_now())])
        finished = utc_now()
        if finished >= deadline:
            return _finish_error(db, task_id, generation, "tempo-esgotado", transient=False)
        task = db.get(TarefaAnalise, task_id)
        payload = _task_payload(task, "completed", finished)
        verdicts = [obs["valueCodeableConcept"]["coding"][0]["code"] for obs in observations]
        verdict = max(verdicts, key={"aceita": 0, "aceita-com-ressalva": 1, "rejeitada": 2}.get)
        payload["businessStatus"] = concept("veredito-qualidade-imagem", verdict)
        payload["executionPeriod"]["end"] = _instant(finished)
        payload["input"] = [{"type": concept("tarefa-analise", "imagem-avaliada"), "valueReference": {"reference": "Media/" + img.identificador}} for img in images]
        payload["output"] = [{"type": concept("tarefa-analise", "resultado-qualidade-imagem"), "valueReference": {"reference": "Observation/" + obs["id"]}} for obs in observations]
        payload.pop("statusReason", None)
        changed = db.execute(update(TarefaAnalise).where(
            TarefaAnalise.identificador == task_id, TarefaAnalise.estado == "in-progress",
            TarefaAnalise.attempts == generation, TarefaAnalise.lease_expires_at > finished,
        ).values(estado="completed", recurso_json=payload, id_versao=task.id_versao + 1,
                 atualizado_em=finished, lease_expires_at=None, next_attempt_at=None, last_error=None),
                 execution_options={"synchronize_session": False}).rowcount
        if not changed:
            db.rollback()
            return False
        max_index = db.scalar(select(func.max(EntradaPacote.indice_entrada)).where(EntradaPacote.pacote_id == task.pacote_id))
        for index, resource in enumerate(resources, start=(max_index if max_index is not None else -1) + 1):
            db.add(EntradaPacote(pacote_id=task.pacote_id, indice_entrada=index,
                                 url_completa=f"urn:uuid:{resource['id']}", tipo_recurso=resource["resourceType"],
                                 recurso_id=resource["id"], recurso_json=resource))
        db.commit()
        db.expire_all()
        logger.info("Análise técnica concluída", extra={"task_id": task_id, "attempt": generation})
        return True
    except InvalidImageError:
        db.rollback()
        return _finish_error(db, task_id, generation, "imagem-invalida", transient=False)
    except Exception:
        db.rollback()
        # Não persistir mensagens arbitrárias: bibliotecas podem incluir dados clínicos.
        logger.warning("Falha técnica na análise", extra={"task_id": task_id, "attempt": generation})
        return _finish_error(db, task_id, generation, "falha-tecnica", transient=True)


def _finish_error(db: Session, task_id: str, generation: int, reason: str, *, transient: bool) -> bool:
    now = utc_now()
    task = db.get(TarefaAnalise, task_id)
    if task is None or task.estado != "in-progress" or task.attempts != generation:
        db.rollback()
        return False
    deadline = _utc(task.deadline_at)
    delay = getattr(settings, "analysis_retry_base_seconds", 2) * 2 ** (generation - 1)
    retry_at = now + timedelta(seconds=delay)
    retry = transient and generation < getattr(settings, "analysis_max_attempts", 3) and retry_at < deadline
    if now >= deadline:
        reason = "tempo-esgotado"
        retry = False
    elif transient and generation >= getattr(settings, "analysis_max_attempts", 3):
        reason = "limite-tentativas"
    state = "accepted" if retry else "failed"
    payload = _task_payload(task, state, now)
    payload["statusReason"] = concept("motivo-falha-analise", reason)
    if not retry:
        payload.setdefault("executionPeriod", {})["end"] = _instant(now)
    changed = db.execute(update(TarefaAnalise).where(
        TarefaAnalise.identificador == task_id, TarefaAnalise.estado == "in-progress", TarefaAnalise.attempts == generation,
    ).values(estado=state, recurso_json=payload, id_versao=task.id_versao + 1, atualizado_em=now,
             lease_expires_at=None, next_attempt_at=retry_at if retry else None, last_error=reason),
             execution_options={"synchronize_session": False}).rowcount
    db.commit()
    db.expire_all()
    return bool(changed)


def process_next_task(db: Session) -> bool:
    """Processa o próximo trabalho elegível na fila persistida no banco."""
    now = utc_now()
    task_id = db.scalar(select(TarefaAnalise.identificador).where(_eligible(now)).order_by(TarefaAnalise.criado_em).limit(1))
    db.rollback()
    return process_task(db, task_id) if task_id else False
