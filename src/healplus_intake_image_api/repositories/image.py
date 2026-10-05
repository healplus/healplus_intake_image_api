"""Pure database operations for HealPlus FHIR image intake resources."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from healplus_intake_image_api.models.image import (
    AnalysisTask,
    FHIRBundle,
    Media,
    MediaTypeCoding,
)
from healplus_intake_image_api.schemas.image import (
    HEALPLUS_IMAGE_INTAKE_BUNDLE_PROFILE,
    HEALPLUS_MEDIA_PROFILE,
    FHIRBundleCreate,
    resource_json,
)
from healplus_intake_image_api.schemas.task import (
    HEALPLUS_ANALYSIS_TASK_PROFILE,
    TaskStatus,
)


def _with_server_meta(
    resource: dict,
    *,
    resource_id: str,
    profile: str,
    last_updated: datetime,
) -> dict:
    """Add server-managed FHIR identity and metadata to a resource dictionary."""
    result = {**resource, "id": resource_id}
    meta = {**result.get("meta", {})}
    profiles = list(meta.get("profile", []))
    if profile not in profiles:
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


def create_intake(
    db: Session,
    bundle: FHIRBundleCreate,
) -> AnalysisTask:
    """Persist a submitted Bundle, its Media resources, and its analysis Task.

    Args:
        db: Database session.
        bundle: Validated Bundle from the $submit-media operation.

    Returns:
        The persisted Task in the accepted state.
    """
    now = datetime.now(timezone.utc)
    bundle_id = bundle.id or str(uuid4())
    bundle_payload = _with_server_meta(
        resource_json(bundle),
        resource_id=bundle_id,
        profile=HEALPLUS_IMAGE_INTAKE_BUNDLE_PROFILE,
        last_updated=now,
    )
    db_bundle = FHIRBundle(
        id=bundle_id,
        identifier_system=bundle.identifier.system if bundle.identifier else None,
        identifier_value=bundle.identifier.value if bundle.identifier else None,
        timestamp=bundle.timestamp,
        resource_json=bundle_payload,
        last_updated=now,
    )

    for index, entry in enumerate(bundle.entry):
        resource = entry.resource
        media_id = resource.id or str(uuid4())
        media_payload = _with_server_meta(
            resource_json(resource),
            resource_id=media_id,
            profile=HEALPLUS_MEDIA_PROFILE,
            last_updated=now,
        )
        bundle_payload["entry"][index]["resource"] = media_payload
        db_bundle.media.append(
            Media(
                id=media_id,
                full_url=entry.full_url,
                status=resource.status,
                subject_reference=resource.subject.reference or "",
                encounter_reference=(
                    resource.encounter.reference if resource.encounter else None
                ),
                created_date_time=resource.created_date_time,
                content_type=resource.content.content_type,
                content_data=resource.content.data,
                resource_json=media_payload,
                last_updated=now,
                type_codings=[
                    MediaTypeCoding(
                        system=coding.system,
                        code=coding.code,
                        display=coding.display,
                    )
                    for coding in resource.type.coding
                ],
            )
        )

    task_id = str(uuid4())
    subject_reference = bundle.entry[0].resource.subject.reference
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

    db_task = AnalysisTask(
        id=task_id,
        status=TaskStatus.ACCEPTED.value,
        subject_reference=subject_reference,
        resource_json=task_payload,
        authored_on=now,
        last_modified=now,
    )
    db_bundle.task = db_task
    db.add(db_bundle)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_task(db: Session, task_id: str) -> AnalysisTask | None:
    """Return an analysis Task by its FHIR id."""
    return db.get(AnalysisTask, task_id)


def get_bundle(db: Session, bundle_id: str) -> FHIRBundle | None:
    """Return a submitted Bundle by its FHIR id."""
    return db.get(FHIRBundle, bundle_id)


def get_media(db: Session, media_id: str) -> Media | None:
    """Return a submitted Media resource by its FHIR id."""
    return db.get(Media, media_id)
