"""Create initial HealPlus clinical intake schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261021_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all persistence tables used by the current application."""
    op.create_table(
        "pacotes_fhir",
        sa.Column("identificador", sa.String(length=64), primary_key=True),
        sa.Column("sistema_identificador", sa.String(length=255)),
        sa.Column("valor_identificador", sa.String(length=255)),
        sa.Column("instante", sa.DateTime(timezone=True)),
        sa.Column("recurso_json", postgresql.JSONB(), nullable=False),
        sa.Column("id_versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "entradas_pacote",
        sa.Column("identificador", sa.Integer(), primary_key=True),
        sa.Column("pacote_id", sa.String(length=64), nullable=False),
        sa.Column("indice_entrada", sa.Integer(), nullable=False),
        sa.Column("url_completa", sa.String(length=512), nullable=False),
        sa.Column("tipo_recurso", sa.String(length=64), nullable=False),
        sa.Column("recurso_id", sa.String(length=64)),
        sa.Column("recurso_json", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["pacote_id"], ["pacotes_fhir.identificador"]),
        sa.UniqueConstraint(
            "pacote_id",
            "indice_entrada",
            name="uq_entradas_pacote_indice",
        ),
        sa.UniqueConstraint(
            "pacote_id",
            "url_completa",
            name="uq_entradas_pacote_url",
        ),
    )
    op.create_index(
        "ix_entradas_pacote_pacote_id",
        "entradas_pacote",
        ["pacote_id"],
    )

    op.create_table(
        "imagens_clinicas",
        sa.Column("identificador", sa.String(length=64), primary_key=True),
        sa.Column("pacote_id", sa.String(length=64), nullable=False),
        sa.Column("url_completa", sa.String(length=512)),
        sa.Column("estado", sa.String(length=32), nullable=False),
        sa.Column("referencia_sujeito", sa.String(length=512), nullable=False),
        sa.Column("referencia_atendimento", sa.String(length=512)),
        sa.Column("criado_em", sa.DateTime(timezone=True)),
        sa.Column("tipo_conteudo", sa.String(length=255), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("recurso_json", postgresql.JSONB(), nullable=False),
        sa.Column("id_versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pacote_id"], ["pacotes_fhir.identificador"]),
    )
    op.create_index(
        "ix_imagens_clinicas_pacote_id",
        "imagens_clinicas",
        ["pacote_id"],
    )

    op.create_table(
        "codificacoes_tipo_imagem",
        sa.Column("identificador", sa.Integer(), primary_key=True),
        sa.Column("imagem_id", sa.String(length=64), nullable=False),
        sa.Column("sistema", sa.String(length=255)),
        sa.Column("codigo", sa.String(length=255)),
        sa.Column("exibicao", sa.String(length=255)),
        sa.ForeignKeyConstraint(["imagem_id"], ["imagens_clinicas.identificador"]),
    )
    op.create_index(
        "ix_codificacoes_tipo_imagem_imagem_id",
        "codificacoes_tipo_imagem",
        ["imagem_id"],
    )

    op.create_table(
        "tarefas_analise",
        sa.Column("identificador", sa.String(length=64), primary_key=True),
        sa.Column("pacote_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("estado", sa.String(length=32), nullable=False),
        sa.Column("referencia_sujeito", sa.String(length=512)),
        sa.Column("recurso_json", postgresql.JSONB(), nullable=False),
        sa.Column("id_versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pacote_id"], ["pacotes_fhir.identificador"]),
    )
    op.create_index("ix_tarefas_analise_estado", "tarefas_analise", ["estado"])


def downgrade() -> None:
    """Drop all persistence tables from this initial schema."""
    op.drop_index("ix_tarefas_analise_estado", table_name="tarefas_analise")
    op.drop_table("tarefas_analise")
    op.drop_index(
        "ix_codificacoes_tipo_imagem_imagem_id",
        table_name="codificacoes_tipo_imagem",
    )
    op.drop_table("codificacoes_tipo_imagem")
    op.drop_index("ix_imagens_clinicas_pacote_id", table_name="imagens_clinicas")
    op.drop_table("imagens_clinicas")
    op.drop_index("ix_entradas_pacote_pacote_id", table_name="entradas_pacote")
    op.drop_table("entradas_pacote")
    op.drop_table("pacotes_fhir")
