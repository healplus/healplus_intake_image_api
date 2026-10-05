"""Application services for FHIR image intake."""

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from healplus_intake_image_api.models.image import AnalysisTask
from healplus_intake_image_api.repositories.image import (
    create_intake as repo_create_intake,
    get_bundle as repo_get_bundle,
    get_media as repo_get_media,
    get_task as repo_get_task,
)
from healplus_intake_image_api.schemas.image import FHIRBundleCreate
from healplus_intake_image_api.schemas.task import TaskResponse

logger = logging.getLogger(__name__)


class FHIRRequestError(Exception):
    """Application error rendered as a FHIR OperationOutcome."""

    def __init__(
        self,
        status_code: int,
        issue_code: str,
        diagnostics: str,
        expression: list[str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.issue_code = issue_code
        self.diagnostics = diagnostics
        self.expression = expression or []
        super().__init__(diagnostics)


def _task_response(task: AnalysisTask) -> TaskResponse:
    """Deserialize the persisted Task resource."""
    return TaskResponse.model_validate(task.resource_json)


def submit_media(db: Session, bundle: FHIRBundleCreate) -> TaskResponse:
    """Persist an image Bundle and create its accepted analysis Task.

    Args:
        db: Database session.
        bundle: Validated HealPlus image intake Bundle.

    Returns:
        FHIR Task in the accepted status.

    Raises:
        FHIRRequestError: If the Bundle cannot be persisted.
    """
    try:
        task = repo_create_intake(db, bundle)
        logger.info(
            "FHIR image Bundle accepted",
            extra={"task_id": task.id, "media_count": len(bundle.entry)},
        )
        return _task_response(task)
    except IntegrityError as error:
        db.rollback()
        logger.exception("FHIR resource identity conflict while submitting image Bundle")
        raise FHIRRequestError(
            409,
            "duplicate",
            "A Bundle or Media resource with a supplied id already exists",
        ) from error
    except OperationalError as error:
        db.rollback()
        logger.exception("Database unavailable while submitting image Bundle")
        raise FHIRRequestError(503, "transient", "Database unavailable") from error
    except Exception as error:
        db.rollback()
        logger.exception("Unexpected error while submitting image Bundle")
        raise FHIRRequestError(
            500,
            "exception",
            "Unable to process the submitted FHIR Bundle",
        ) from error


def read_task(db: Session, task_id: str) -> TaskResponse:
    """Retrieve an analysis Task by FHIR id."""
    try:
        task = repo_get_task(db, task_id)
        if task is None:
            raise FHIRRequestError(404, "not-found", "Task not found")
        return _task_response(task)
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Database unavailable while reading Task %s", task_id)
        raise FHIRRequestError(503, "transient", "Database unavailable") from error
    except Exception as error:
        logger.exception("Unexpected error while reading Task %s", task_id)
        raise FHIRRequestError(500, "exception", "Unable to read Task") from error


def read_bundle(db: Session, bundle_id: str) -> dict[str, Any]:
    """Retrieve a submitted FHIR Bundle by id."""
    try:
        bundle = repo_get_bundle(db, bundle_id)
        if bundle is None:
            raise FHIRRequestError(404, "not-found", "Bundle not found")
        return bundle.resource_json
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Database unavailable while reading Bundle %s", bundle_id)
        raise FHIRRequestError(503, "transient", "Database unavailable") from error
    except Exception as error:
        logger.exception("Unexpected error while reading Bundle %s", bundle_id)
        raise FHIRRequestError(500, "exception", "Unable to read Bundle") from error


def read_media(db: Session, media_id: str) -> dict[str, Any]:
    """Retrieve a submitted FHIR Media resource by id."""
    try:
        media = repo_get_media(db, media_id)
        if media is None:
            raise FHIRRequestError(404, "not-found", "Media not found")
        return media.resource_json
    except FHIRRequestError:
        raise
    except OperationalError as error:
        logger.exception("Database unavailable while reading Media %s", media_id)
        raise FHIRRequestError(503, "transient", "Database unavailable") from error
    except Exception as error:
        logger.exception("Unexpected error while reading Media %s", media_id)
        raise FHIRRequestError(500, "exception", "Unable to read Media") from error
