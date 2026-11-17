"""Client isolation, idempotency, durable worker state and access audit."""

from copy import deepcopy

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261116_02"
down_revision = "20261021_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pacotes_fhir") as batch:
        batch.add_column(sa.Column("cliente_id", sa.String(128), nullable=False, server_default="__legacy__"))
        batch.add_column(sa.Column("conteudo_sha256", sa.String(64)))
    bind = op.get_bind()
    # Legados ficam segregados até uma atribuição de propriedade revisada.
    packages = sa.table("pacotes_fhir", sa.column("identificador", sa.String),
                        sa.column("cliente_id", sa.String), sa.column("recurso_json", sa.JSON))
    for row in bind.execute(sa.select(packages.c.identificador, packages.c.recurso_json)).mappings().all():
        payload = deepcopy(row["recurso_json"])
        for entry in payload.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Media":
                resource.get("content", {}).pop("data", None)
        bind.execute(packages.update().where(packages.c.identificador == row["identificador"]).values(
            cliente_id=f'__legacy__:{row["identificador"]}', recurso_json=payload))
    for table_name in ("entradas_pacote", "imagens_clinicas"):
        table = sa.table(table_name, sa.column("identificador"), sa.column("recurso_json", sa.JSON))
        for row in bind.execute(sa.select(table.c.identificador, table.c.recurso_json)).mappings().all():
            payload = deepcopy(row["recurso_json"])
            if payload.get("resourceType") == "Media":
                payload.get("content", {}).pop("data", None)
                bind.execute(table.update().where(table.c.identificador == row["identificador"]).values(recurso_json=payload))
    with op.batch_alter_table("pacotes_fhir") as batch:
        batch.alter_column("cliente_id", server_default=None)
        batch.create_unique_constraint("uq_pacote_cliente_identifier", ["cliente_id", "sistema_identificador", "valor_identificador"])
        batch.create_index("ix_pacotes_fhir_cliente_id", ["cliente_id"])
    with op.batch_alter_table("tarefas_analise") as batch:
        batch.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("deadline_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("last_error", sa.String(255)))
    op.create_table("eventos_auditoria",
        sa.Column("identificador", sa.String(64), primary_key=True),
        sa.Column("cliente_id", sa.String(128), nullable=False),
        sa.Column("registrado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recurso_json", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False))
    op.create_index("ix_eventos_auditoria_cliente_id", "eventos_auditoria", ["cliente_id"])


def downgrade() -> None:
    # Restaurar as cópias JSON permite executar o código anterior após rollback.
    bind = op.get_bind()
    images = sa.table("imagens_clinicas", sa.column("identificador", sa.String), sa.column("conteudo", sa.Text), sa.column("recurso_json", sa.JSON))
    data_by_id = {}
    for row in bind.execute(sa.select(images)).mappings().all():
        data_by_id[row["identificador"]] = row["conteudo"]
        payload = deepcopy(row["recurso_json"])
        payload.setdefault("content", {})["data"] = row["conteudo"]
        bind.execute(images.update().where(images.c.identificador == row["identificador"]).values(recurso_json=payload))
    entries = sa.table("entradas_pacote", sa.column("identificador"), sa.column("recurso_id", sa.String), sa.column("recurso_json", sa.JSON))
    for row in bind.execute(sa.select(entries)).mappings().all():
        payload = deepcopy(row["recurso_json"])
        if payload.get("resourceType") == "Media" and row["recurso_id"] in data_by_id:
            payload.setdefault("content", {})["data"] = data_by_id[row["recurso_id"]]
            bind.execute(entries.update().where(entries.c.identificador == row["identificador"]).values(recurso_json=payload))
    packages = sa.table("pacotes_fhir", sa.column("identificador", sa.String), sa.column("recurso_json", sa.JSON))
    for row in bind.execute(sa.select(packages)).mappings().all():
        payload = deepcopy(row["recurso_json"])
        for entry in payload.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Media" and resource.get("id") in data_by_id:
                resource.setdefault("content", {})["data"] = data_by_id[resource["id"]]
        bind.execute(packages.update().where(packages.c.identificador == row["identificador"]).values(recurso_json=payload))
    op.drop_table("eventos_auditoria")
    with op.batch_alter_table("tarefas_analise") as batch:
        for column in ("attempts", "next_attempt_at", "lease_expires_at", "deadline_at", "last_error"):
            batch.drop_column(column)
    with op.batch_alter_table("pacotes_fhir") as batch:
        batch.drop_constraint("uq_pacote_cliente_identifier", type_="unique")
        batch.drop_index("ix_pacotes_fhir_cliente_id")
        batch.drop_column("cliente_id")
        batch.drop_column("conteudo_sha256")
