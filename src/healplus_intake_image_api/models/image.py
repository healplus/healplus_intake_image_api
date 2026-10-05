"""SQLAlchemy persistence models for the HealPlus FHIR resources."""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from healplus_intake_image_api.core.database import Base

FHIRJSON = JSON().with_variant(JSONB, "postgresql")


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


class FHIRBundle(Base):
    """Persisted FHIR collection Bundle submitted for image analysis."""

    __tablename__ = "fhir_bundles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identifier_system: Mapped[str | None] = mapped_column(String(255))
    identifier_value: Mapped[str | None] = mapped_column(String(255))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resource_json: Mapped[dict] = mapped_column(FHIRJSON, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    media: Mapped[list["Media"]] = relationship(
        back_populates="bundle",
        cascade="all, delete-orphan",
    )
    task: Mapped["AnalysisTask | None"] = relationship(
        back_populates="bundle",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Media(Base):
    """FHIR Media resource contained in an intake Bundle."""

    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(
        ForeignKey("fhir_bundles.id"),
        nullable=False,
        index=True,
    )
    full_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    encounter_reference: Mapped[str | None] = mapped_column(String(512))
    created_date_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    content_data: Mapped[str] = mapped_column(Text, nullable=False)
    resource_json: Mapped[dict] = mapped_column(FHIRJSON, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    bundle: Mapped[FHIRBundle] = relationship(back_populates="media")
    type_codings: Mapped[list["MediaTypeCoding"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )


class MediaTypeCoding(Base):
    """Coding values from Media.type.coding."""

    __tablename__ = "media_type_codings"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[str] = mapped_column(
        ForeignKey("media.id"),
        nullable=False,
        index=True,
    )
    system: Mapped[str | None] = mapped_column(String(255))
    code: Mapped[str | None] = mapped_column(String(255))
    display: Mapped[str | None] = mapped_column(String(255))
    media: Mapped[Media] = relationship(back_populates="type_codings")


class AnalysisTask(Base):
    """FHIR Task that represents the asynchronous HealPlus analysis."""

    __tablename__ = "analysis_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(
        ForeignKey("fhir_bundles.id"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subject_reference: Mapped[str | None] = mapped_column(String(512))
    resource_json: Mapped[dict] = mapped_column(FHIRJSON, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    authored_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    bundle: Mapped[FHIRBundle] = relationship(back_populates="task")
