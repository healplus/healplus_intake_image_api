"""Opt-in PostgreSQL integration validation in a dedicated Docker container.

Run with the project's development dependencies installed:
    .venv/Scripts/python.exe scripts/verify_postgres.py

Never uses compose or an existing database. A random password stays in process
memory/environment; the published database port is bound only to 127.0.0.1.
"""

import base64
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from threading import Barrier
import time
from datetime import datetime, timezone

from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.engine import URL

WORKSPACE = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
CONTAINER = "healplus-quality-check-" + secrets.token_hex(6)
PASSWORD = secrets.token_urlsafe(32) + "%:@"
CONTAINER_ID = None
engine = None
results = {}


def run(args, *, env=None, check=True):
    result = subprocess.run(args, cwd=WORKSPACE, env=env, text=True, capture_output=True)
    if check and result.returncode:
        safe = redact(result.stdout + result.stderr)
        raise RuntimeError(f"Command {args[0]} failed ({result.returncode}): {safe}")
    return result


def redact(value):
    value = value.replace(PASSWORD, "[REDACTED]")
    if "url" in globals():
        value = value.replace(url, "[REDACTED_DATABASE_URL]")
    return value


def stage(message):
    print(message, flush=True)


def alembic(*args, check=True):
    completed = run([str(PYTHON), "-m", "alembic", *args], env=environment, check=check)
    if completed.returncode:
        stage(redact(completed.stdout + completed.stderr))
    return completed


try:
    stage("Creating dedicated ephemeral PostgreSQL 16 container " + CONTAINER)
    docker_environment = dict(os.environ, POSTGRES_PASSWORD=PASSWORD)
    created = run(["docker", "create", "--name", CONTAINER,
                   "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER=quality_check",
                   "--env", "POSTGRES_DB=quality_check", "--tmpfs", "/var/lib/postgresql/data:rw,noexec,nosuid,size=256m",
                   "-p", "127.0.0.1::5432", "postgres:16-alpine"], env=docker_environment)
    CONTAINER_ID = created.stdout.strip()
    run(["docker", "start", CONTAINER_ID])
    bound = run(["docker", "port", CONTAINER_ID, "5432/tcp"]).stdout.strip()
    assert bound.startswith("127.0.0.1:")
    port = int(bound.rsplit(":", 1)[1])
    url = URL.create("postgresql+psycopg", username="quality_check", password=PASSWORD,
                     host="127.0.0.1", port=port, database="quality_check").render_as_string(hide_password=False)
    environment = dict(os.environ, DATABASE_URL=url, PYTHONPATH=str(WORKSPACE / "src"))
    os.environ["DATABASE_URL"] = url
    os.environ["PYTHONPATH"] = str(WORKSPACE / "src")
    sys.path[:0] = [str(WORKSPACE / "src"), str(WORKSPACE / "tests")]
    engine = create_engine(url, pool_pre_ping=True)
    ready = False
    for attempt in range(80):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            ready = True
            break
        except Exception:
            time.sleep(0.5)
    assert ready, "Dedicated PostgreSQL did not start"
    stage("PostgreSQL ready; applying initial migration")
    alembic("upgrade", "20261021_01")
    metadata = MetaData()
    metadata.reflect(engine)
    packages = metadata.tables["pacotes_fhir"]
    entries = metadata.tables["entradas_pacote"]
    images = metadata.tables["imagens_clinicas"]
    tasks = metadata.tables["tarefas_analise"]
    now = datetime.now(timezone.utc)
    encoded = base64.b64encode(b"synthetic legacy JPEG bytes").decode()
    media = {"resourceType": "Media", "id": "legacy-image", "content": {"contentType": "image/jpeg", "data": encoded}}
    bundle = {"resourceType": "Bundle", "id": "legacy-package", "type": "collection", "entry": [{"fullUrl": "urn:uuid:00000000-0000-4000-8000-000000000001", "resource": media}]}
    with engine.begin() as connection:
        connection.execute(packages.insert().values(identificador="legacy-package", sistema_identificador="urn:test:legacy", valor_identificador="same-local-key", recurso_json=bundle, atualizado_em=now))
        connection.execute(entries.insert().values(pacote_id="legacy-package", indice_entrada=0, url_completa=bundle["entry"][0]["fullUrl"], tipo_recurso="Media", recurso_id="legacy-image", recurso_json=media))
        connection.execute(images.insert().values(identificador="legacy-image", pacote_id="legacy-package", estado="completed", referencia_sujeito="Patient/legacy-patient", tipo_conteudo="image/jpeg", conteudo=encoded, recurso_json=media, atualizado_em=now))
        connection.execute(tasks.insert().values(identificador="legacy-task", pacote_id="legacy-package", estado="accepted", recurso_json={"resourceType": "Task", "status": "accepted"}, criado_em=now, atualizado_em=now))
    stage("Legacy snapshot inserted; applying quality migration")
    alembic("upgrade", "head")
    metadata = MetaData()
    metadata.reflect(engine)
    packages = metadata.tables["pacotes_fhir"]
    entries = metadata.tables["entradas_pacote"]
    images = metadata.tables["imagens_clinicas"]
    with engine.connect() as connection:
        old_package = connection.execute(select(packages)).mappings().one()
        old_entry = connection.execute(select(entries)).mappings().one()
        old_image = connection.execute(select(images)).mappings().one()
    assert old_package["cliente_id"] == "__legacy__:legacy-package"
    assert "data" not in old_package["recurso_json"]["entry"][0]["resource"]["content"]
    assert "data" not in old_entry["recurso_json"]["content"]
    assert "data" not in old_image["recurso_json"]["content"]
    assert old_image["conteudo"] == encoded
    results["legacy_upgrade_single_image_copy"] = "passed"
    from sqlalchemy.orm import Session
    from healplus_intake_image_api.repositories.avaliacao_ferida import get_imagem, get_pacote
    from healplus_intake_image_api.core.config import Settings
    from pydantic import ValidationError
    with Session(engine) as db:
        assert get_pacote(db, "legacy-package", client_id="test-client") is None
        assert get_imagem(db, "legacy-image", client_id="test-client") is None
    try:
        Settings(database_url=url, api_client_tokens={"__legacy__:legacy-package": "x" * 40})
    except ValidationError:
        pass
    else:
        raise AssertionError("Reserved legacy principal must not be configurable")
    results["legacy_client_quarantine"] = "passed"
    stage("Upgrade data and legacy isolation passed; validating downgrade restoration")
    alembic("downgrade", "20261021_01")
    with engine.connect() as connection:
        old_package = connection.execute(text("SELECT recurso_json FROM pacotes_fhir WHERE identificador = 'legacy-package'")).scalar_one()
        old_entry = connection.execute(text("SELECT recurso_json FROM entradas_pacote WHERE recurso_id = 'legacy-image'")).scalar_one()
        old_image = connection.execute(text("SELECT recurso_json FROM imagens_clinicas WHERE identificador = 'legacy-image'")).scalar_one()
    assert old_package["entry"][0]["resource"]["content"]["data"] == encoded
    assert old_entry["content"]["data"] == encoded
    assert old_image["content"]["data"] == encoded
    results["downgrade_restores_legacy_json"] = "passed"
    alembic("upgrade", "head")
    results["downgrade_upgrade_cycle"] = "passed"
    stage("Downgrade and upgrade cycle passed; checking model/schema agreement")
    check_result = alembic("check", check=False)
    results["alembic_check"] = "passed" if check_result.returncode == 0 else "failed"
    stage("Running real PostgreSQL intake, replay and worker integration")
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from healplus_intake_image_api.core.config import settings
    from healplus_intake_image_api.core.database import get_db
    from healplus_intake_image_api.main import app
    from healplus_intake_image_api.models.avaliacao_ferida import PacoteFHIR
    from healplus_intake_image_api.services.quality import process_task
    from test_fhir_avaliacao_ferida import intake_payload
    settings.api_client_tokens = {"migration-check-client": SecretStr("c" * 40)}
    def override_get_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_get_db
    payload = intake_payload.__wrapped__()
    with TestClient(app, headers={"Authorization": "Bearer " + "c" * 40}) as client:
        first = client.post("/api/fhir/r4/$avaliar-feridas", json=payload, headers={"Content-Type": "application/fhir+json"})
        assert first.status_code == 202, first.text
        task_id = first.json()["id"]
        replay = client.post("/api/fhir/r4/$avaliar-feridas", json=payload, headers={"Content-Type": "application/fhir+json"})
        assert replay.status_code == 200 and replay.json()["id"] == task_id
        with Session(engine) as db:
            assert process_task(db, task_id)
        task_response = client.get(first.headers["content-location"])
        assert task_response.status_code == 200 and task_response.json()["status"] == "completed"
        result_ref = task_response.json()["output"][0]["valueReference"]["reference"]
        assert client.get("/api/fhir/r4/" + result_ref).status_code == 200
        assert client.get("/api/fhir/r4/Media/legacy-image").status_code == 404
        stage("Checking concurrent identical POSTs and concurrent workers on PostgreSQL")
        concurrent_payload = copy.deepcopy(payload)
        concurrent_payload["parameter"][0]["resource"]["identifier"]["value"] += "-concurrent"
        gate = Barrier(2)
        def post_same_submission():
            gate.wait(timeout=10)
            return client.post("/api/fhir/r4/$avaliar-feridas", json=concurrent_payload,
                               headers={"Content-Type": "application/fhir+json"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(post_same_submission)
            second_future = pool.submit(post_same_submission)
            responses = [first_future.result(timeout=30), second_future.result(timeout=30)]
        assert sorted(response.status_code for response in responses) == [200, 202]
        assert responses[0].json()["id"] == responses[1].json()["id"]
        concurrent_task = responses[0].json()["id"]
        gate = Barrier(2)
        def worker_same_task():
            gate.wait(timeout=10)
            with Session(engine) as db:
                return process_task(db, concurrent_task)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(worker_same_task)
            second_future = pool.submit(worker_same_task)
            worked = [first_future.result(timeout=30), second_future.result(timeout=30)]
        assert sorted(worked) == [False, True]
        finished = client.get("/api/fhir/r4/Task/" + concurrent_task).json()
        assert finished["status"] == "completed" and len(finished["output"]) == 1
        results["postgres_concurrent_idempotency_and_worker_claim"] = "passed"
    app.dependency_overrides.clear()
    results["postgres_http_intake_replay_worker_output"] = "passed"
    stage(json.dumps(results, ensure_ascii=True))
    assert check_result.returncode == 0, "Alembic schema check detected drift"
finally:
    if engine is not None:
        engine.dispose()
    if CONTAINER_ID:
        identity = run(["docker", "inspect", "--format", "{{.Id}} {{.Name}}", CONTAINER_ID]).stdout.strip()
        expected = CONTAINER_ID + " /" + CONTAINER
        assert identity == expected, "Container identity check failed; refusing cleanup"
        run(["docker", "rm", "-f", CONTAINER_ID])
        stage("Removed only verified dedicated container " + CONTAINER)
