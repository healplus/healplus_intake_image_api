"""Qualidade demonstrativa real e recuperação da fila persistida."""

import base64
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from threading import Event

import pytest
from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from healplus_intake_image_api.core.database import Base
from healplus_intake_image_api.models.avaliacao_ferida import EntradaPacote, ImagemClinica, PacoteFHIR, TarefaAnalise
from healplus_intake_image_api.services import quality


def jpeg(kind="sharp") -> bytes:
    image = Image.new("RGB", (640, 640), (110, 110, 110))
    if kind != "dark":
        draw = ImageDraw.Draw(image)
        for x in range(0, 640, 8):
            for y in range(0, 640, 8):
                draw.rectangle((x, y, x + 7, y + 7), fill=(80, 80, 80) if (x + y) % 16 else (180, 180, 180))
    else:
        image.paste((0, 0, 0), (0, 0, 640, 640))
    if kind == "blurred":
        image = image.filter(ImageFilter.GaussianBlur(12))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=95)
    return output.getvalue()


def media(raw: bytes) -> dict:
    return {"resourceType": "Media", "id": str(uuid4()), "status": "completed",
            "createdDateTime": "2026-11-16T12:00:00Z", "subject": {"reference": "Patient/patient"},
            "encounter": {"reference": "Encounter/encounter"},
            "content": {"contentType": "image/jpeg", "size": len(raw),
                        "hash": base64.b64encode(hashlib.sha1(raw).digest()).decode()}}


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def queued_task(db, *, raw=None, state="accepted", attempts=0, lease=None, deadline=None):
    raw = raw if raw is not None else jpeg()
    resource = media(raw)
    now = datetime.now(timezone.utc)
    package = PacoteFHIR(identificador=str(uuid4()), cliente_id="test-client", recurso_json={"resourceType": "Bundle"})
    package.imagens.append(ImagemClinica(identificador=resource["id"], estado="completed", referencia_sujeito="Patient/patient",
                           tipo_conteudo="image/jpeg", conteudo=base64.b64encode(raw).decode(), recurso_json=resource))
    task = TarefaAnalise(identificador=str(uuid4()), estado=state, attempts=attempts,
                         lease_expires_at=lease, deadline_at=deadline or now + timedelta(minutes=2), criado_em=now,
                         recurso_json={"resourceType": "Task", "status": state, "meta": {"versionId": "1"}})
    package.tarefa = task
    db.add(package)
    db.commit()
    return task


def verdict(observation):
    return observation["valueCodeableConcept"]["coding"][0]["code"]


def test_metrics_discriminate_blur_and_report_unsupported_criteria():
    sharp = jpeg()
    blurry = jpeg("blurred")
    assert quality.measure_image(sharp)["sharpness"] > quality.measure_image(blurry)["sharpness"] * 10
    result = quality.analyze_image(sharp, media(sharp), device_id="algorithm")
    assert verdict(result) == "aceita-com-ressalva"
    assert len([c for c in result["component"] if "dataAbsentReason" in c]) == len(quality.UNSUPPORTED_CRITERIA)
    assert all("referenceRange" in c for c in result["component"] if "valueQuantity" in c)
    assert verdict(quality.analyze_image(blurry, media(blurry), device_id="algorithm")) == "rejeitada"


def test_completed_task_outputs_and_provenance_are_atomic_and_stable(db):
    task = queued_task(db)
    task_id = task.identificador
    assert quality.process_next_task(db)
    db.refresh(task)
    assert task.estado == "completed"
    assert task.attempts == 1
    assert task.id_versao == 3
    assert task.recurso_json["businessStatus"]["coding"][0]["code"] == "aceita-com-ressalva"
    assert task.recurso_json["executionPeriod"]["end"]
    assert len(task.recurso_json["input"]) == len(task.recurso_json["output"]) == 1
    outputs = db.scalars(select(EntradaPacote).where(EntradaPacote.pacote_id == task.pacote_id)).all()
    assert {e.tipo_recurso for e in outputs} == {"Device", "Provenance", "Observation"}
    provenance = next(e.recurso_json for e in outputs if e.tipo_recurso == "Provenance")
    assert provenance["entity"][0]["what"]["identifier"]["value"].startswith("ni:///sha-256;")
    snapshot = task.recurso_json
    assert not quality.process_task(db, task_id)
    assert not quality.process_next_task(db)
    assert task.recurso_json == snapshot
    assert len(db.scalars(select(EntradaPacote)).all()) == 3


def test_rejected_photo_completes_task_instead_of_failing(db):
    task = queued_task(db, raw=jpeg("dark"))
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "completed"
    assert task.recurso_json["businessStatus"]["coding"][0]["code"] == "rejeitada"


def test_multiple_photos_each_get_result_and_task_uses_worst_verdict(db):
    task = queued_task(db)
    dark_bytes = jpeg("dark")
    dark_media = media(dark_bytes)
    task.pacote.imagens.append(ImagemClinica(
        identificador=dark_media["id"], estado="completed", referencia_sujeito="Patient/patient",
        tipo_conteudo="image/jpeg", conteudo=base64.b64encode(dark_bytes).decode(), recurso_json=dark_media,
    ))
    db.commit()
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "completed"
    assert task.recurso_json["businessStatus"]["coding"][0]["code"] == "rejeitada"
    assert len(task.recurso_json["input"]) == len(task.recurso_json["output"]) == 2
    results = db.scalars(select(EntradaPacote).where(EntradaPacote.tipo_recurso == "Observation")).all()
    assert {verdict(result.recurso_json) for result in results} == {"aceita-com-ressalva", "rejeitada"}
    assert len({result.recurso_json["focus"][0]["reference"] for result in results}) == 2


def test_transient_failure_retries_then_completes(db, monkeypatch):
    task = queued_task(db)
    original = quality.analyze_image

    def fail(*args, **kwargs):
        raise RuntimeError("arbitrary sensitive exception never stored")

    monkeypatch.setattr(quality, "analyze_image", fail)
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "accepted"
    assert task.attempts == 1
    assert task.next_attempt_at is not None
    assert task.last_error == "falha-tecnica"
    assert not quality.process_task(db, task.identificador)
    task.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(quality, "analyze_image", original)
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "completed"
    assert task.attempts == 2


def test_expired_lease_is_recovered_and_live_lease_not_stolen(db):
    now = datetime.now(timezone.utc)
    task = queued_task(db, state="in-progress", attempts=1, lease=now + timedelta(seconds=50))
    assert not quality.process_task(db, task.identificador)
    task.lease_expires_at = now - timedelta(seconds=1)
    db.commit()
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "completed"
    assert task.attempts == 2


@pytest.mark.parametrize("expired,attempts,reason", [(True, 0, "tempo-esgotado"), (False, 3, "limite-tentativas")])
def test_deadline_and_attempt_limit_terminate_queue(db, expired, attempts, reason):
    task = queued_task(db, attempts=attempts, deadline=datetime.now(timezone.utc) + timedelta(seconds=-1 if expired else 30))
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "failed"
    assert task.last_error == reason
    assert not db.scalars(select(EntradaPacote)).all()


def test_invalid_persisted_jpeg_fails_without_retry(db):
    task = queued_task(db, raw=b"not a jpeg")
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "failed"
    assert task.last_error == "imagem-invalida"
    assert task.next_attempt_at is None


def test_transient_attempt_exhaustion_finishes_failed(db, monkeypatch):
    task = queued_task(db, attempts=2)
    monkeypatch.setattr(quality, "analyze_image", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failure")))
    assert quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "failed"
    assert task.last_error == "limite-tentativas"


def test_stale_worker_cannot_write_after_new_claim(db, monkeypatch):
    task = queued_task(db)
    original = quality.analyze_image

    def expire_generation(*args, **kwargs):
        # Simula outro worker recuperando a lease e avançando a geração.
        db.execute(quality.update(TarefaAnalise).where(TarefaAnalise.identificador == task.identificador).values(attempts=2),
                   execution_options={"synchronize_session": False})
        db.commit()
        return original(*args, **kwargs)

    monkeypatch.setattr(quality, "analyze_image", expire_generation)
    assert not quality.process_task(db, task.identificador)
    db.refresh(task)
    assert task.estado == "in-progress"
    assert not db.scalars(select(EntradaPacote)).all()


def test_two_sessions_do_not_analyze_same_live_claim(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "queue.sqlite"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        task_id = queued_task(setup).identificador
    started = Event()
    release = Event()
    original = quality.analyze_image

    def pause_analysis(*args, **kwargs):
        started.set()
        assert release.wait(timeout=10)
        return original(*args, **kwargs)

    def worker():
        with Session(engine) as session:
            return quality.process_task(session, task_id)

    monkeypatch.setattr(quality, "analyze_image", pause_analysis)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        try:
            assert started.wait(timeout=10)
            assert pool.submit(worker).result(timeout=10) is False
        finally:
            release.set()
        assert first.result(timeout=10) is True
    with Session(engine) as check:
        assert check.get(TarefaAnalise, task_id).estado == "completed"
        assert len(check.scalars(select(EntradaPacote)).all()) == 3
    engine.dispose()
