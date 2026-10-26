"""Modelos de persistência SQLAlchemy para recursos FHIR do HealPlus."""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from healplus_intake_image_api.core.database import Base

FHIRJSON = JSON().with_variant(JSONB, "postgresql")


def utc_now() -> datetime:
    """Retorna o horário UTC atual."""
    return datetime.now(timezone.utc)


class PacoteFHIR(Base):
    """Bundle FHIR collection persistido e submetido para análise de imagens."""

    __tablename__ = "pacotes_fhir"

    identificador: Mapped[str] = mapped_column(String(64), primary_key=True)
    sistema_identificador: Mapped[str | None] = mapped_column(String(255))
    valor_identificador: Mapped[str | None] = mapped_column(String(255))
    instante: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recurso_json: Mapped[dict] = mapped_column(FHIRJSON, nullable=False)
    id_versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    imagens: Mapped[list["ImagemClinica"]] = relationship(
        back_populates="pacote",
        cascade="all, delete-orphan",
    )
    entradas: Mapped[list["EntradaPacote"]] = relationship(
        back_populates="pacote",
        cascade="all, delete-orphan",
        order_by="EntradaPacote.indice_entrada",
    )
    tarefa: Mapped["TarefaAnalise | None"] = relationship(
        back_populates="pacote",
        cascade="all, delete-orphan",
        uselist=False,
    )


class EntradaPacote(Base):
    """Representa uma entrada de Bundle persistida de forma estruturada."""

    __tablename__ = "entradas_pacote"

    identificador: Mapped[int] = mapped_column(primary_key=True)
    pacote_id: Mapped[str] = mapped_column(
        ForeignKey("pacotes_fhir.identificador"),
        nullable=False,
        index=True,
    )
    indice_entrada: Mapped[int] = mapped_column(Integer, nullable=False)
    url_completa: Mapped[str] = mapped_column(String(512), nullable=False)
    tipo_recurso: Mapped[str] = mapped_column(String(64), nullable=False)
    recurso_id: Mapped[str | None] = mapped_column(String(64))
    recurso_json: Mapped[dict] = mapped_column(FHIRJSON, nullable=False)

    pacote: Mapped[PacoteFHIR] = relationship(back_populates="entradas")


class ImagemClinica(Base):
    """Recurso FHIR Media contido em um Bundle de entrada."""

    __tablename__ = "imagens_clinicas"

    identificador: Mapped[str] = mapped_column(String(64), primary_key=True)
    pacote_id: Mapped[str] = mapped_column(
        ForeignKey("pacotes_fhir.identificador"),
        nullable=False,
        index=True,
    )
    url_completa: Mapped[str | None] = mapped_column(String(512))
    estado: Mapped[str] = mapped_column(String(32), nullable=False)
    referencia_sujeito: Mapped[str] = mapped_column(String(512), nullable=False)
    referencia_atendimento: Mapped[str | None] = mapped_column(String(512))
    criado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tipo_conteudo: Mapped[str] = mapped_column(String(255), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    recurso_json: Mapped[dict] = mapped_column(FHIRJSON, nullable=False)
    id_versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    pacote: Mapped[PacoteFHIR] = relationship(back_populates="imagens")
    codificacoes_tipo: Mapped[list["CodificacaoTipoImagem"]] = relationship(
        back_populates="imagem",
        cascade="all, delete-orphan",
    )


class CodificacaoTipoImagem(Base):
    """Valores de Coding de Media.type.coding."""

    __tablename__ = "codificacoes_tipo_imagem"

    identificador: Mapped[int] = mapped_column(primary_key=True)
    imagem_id: Mapped[str] = mapped_column(
        ForeignKey("imagens_clinicas.identificador"),
        nullable=False,
        index=True,
    )
    sistema: Mapped[str | None] = mapped_column(String(255))
    codigo: Mapped[str | None] = mapped_column(String(255))
    exibicao: Mapped[str | None] = mapped_column(String(255))
    imagem: Mapped[ImagemClinica] = relationship(back_populates="codificacoes_tipo")


class TarefaAnalise(Base):
    """Task FHIR que representa a análise assíncrona do HealPlus."""

    __tablename__ = "tarefas_analise"

    identificador: Mapped[str] = mapped_column(String(64), primary_key=True)
    pacote_id: Mapped[str] = mapped_column(
        ForeignKey("pacotes_fhir.identificador"),
        nullable=False,
        unique=True,
    )
    estado: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    referencia_sujeito: Mapped[str | None] = mapped_column(String(512))
    recurso_json: Mapped[dict] = mapped_column(FHIRJSON, nullable=False)
    id_versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    pacote: Mapped[PacoteFHIR] = relationship(back_populates="tarefa")
