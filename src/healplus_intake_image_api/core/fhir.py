"""FHIR HTTP response, versioning, and content-negotiation helpers."""

from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from typing import Any

from fastapi import Header, Request
from fastapi.responses import JSONResponse, Response

from healplus_intake_image_api.schemas.image import operation_outcome
from healplus_intake_image_api.services.image import FHIRRequestError

FHIR_JSON_MEDIA_TYPE = "application/fhir+json"
JSON_MEDIA_TYPE = "application/json"


class FHIRJSONResponse(JSONResponse):
    """JSON response serialized with the FHIR JSON media type."""

    media_type = FHIR_JSON_MEDIA_TYPE


def _response_media_type(accept: str | None) -> str:
    """Select the JSON representation accepted by the client."""
    if accept is None:
        return FHIR_JSON_MEDIA_TYPE

    accepted = {
        value.split(";", maxsplit=1)[0].strip()
        for value in accept.split(",")
    }
    if FHIR_JSON_MEDIA_TYPE in accepted or "*/*" in accepted:
        return FHIR_JSON_MEDIA_TYPE
    if JSON_MEDIA_TYPE in accepted:
        return JSON_MEDIA_TYPE
    raise FHIRRequestError(
        406,
        "not-supported",
        "Accept must allow application/fhir+json or application/json",
    )


def _resource_headers(content: dict[str, Any]) -> dict[str, str]:
    """Map FHIR resource metadata to HTTP versioning headers."""
    meta = content.get("meta", {})
    headers: dict[str, str] = {}
    if version_id := meta.get("versionId"):
        headers["ETag"] = f'W/"{version_id}"'
    if last_updated := meta.get("lastUpdated"):
        last_updated_datetime = datetime.fromisoformat(
            last_updated.replace("Z", "+00:00")
        )
        headers["Last-Modified"] = format_datetime(
            last_updated_datetime.astimezone(UTC),
            usegmt=True,
        )
    return headers


def fhir_response(
    content: Any,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    media_type: str = FHIR_JSON_MEDIA_TYPE,
) -> FHIRJSONResponse:
    """Return serialized FHIR JSON content."""
    if hasattr(content, "model_dump"):
        content = content.model_dump(by_alias=True, exclude_none=True, mode="json")
    response_headers = _resource_headers(content) if isinstance(content, dict) else {}
    response_headers.update(headers or {})
    return FHIRJSONResponse(
        content=content,
        status_code=status_code,
        headers=response_headers,
        media_type=media_type,
    )


async def require_fhir_request_content_type(request: Request) -> None:
    """Require FHIR JSON for requests that carry a FHIR resource."""
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0]
    if content_type != FHIR_JSON_MEDIA_TYPE:
        raise FHIRRequestError(
            415,
            "not-supported",
            "Content-Type must be application/fhir+json",
        )


async def require_fhir_accept(
    accept: str | None = Header(default=None),
) -> str:
    """Negotiate the JSON representation used by a FHIR response."""
    return _response_media_type(accept)


async def require_async_preference(request: Request) -> None:
    """Require the FHIR preference that initiates asynchronous processing."""
    preferences = {
        value.strip()
        for value in request.headers.get("prefer", "").split(",")
    }
    if "respond-async" not in preferences:
        raise FHIRRequestError(
            400,
            "required",
            "Prefer must include respond-async for $submit-media",
        )


def fhir_conditional_response(
    content: Any,
    *,
    if_none_match: str | None,
    if_modified_since: str | None,
    media_type: str,
) -> Response:
    """Return a resource or 304 when its version has not changed."""
    if hasattr(content, "model_dump"):
        content = content.model_dump(by_alias=True, exclude_none=True, mode="json")
    headers = _resource_headers(content)
    etag = headers.get("ETag")
    if if_none_match and (
        if_none_match.strip() == "*"
        or etag in {value.strip() for value in if_none_match.split(",")}
    ):
        return Response(status_code=304, headers=headers)

    if if_modified_since and (last_modified := headers.get("Last-Modified")):
        try:
            since = parsedate_to_datetime(if_modified_since)
            modified = parsedate_to_datetime(last_modified)
        except (TypeError, ValueError):
            pass
        else:
            if modified <= since:
                return Response(status_code=304, headers=headers)

    return fhir_response(content, headers=headers, media_type=media_type)


def fhir_error_response(
    error: FHIRRequestError,
    *,
    accept: str | None = None,
) -> FHIRJSONResponse:
    """Render a domain error as a FHIR OperationOutcome."""
    try:
        media_type = _response_media_type(accept)
    except FHIRRequestError:
        media_type = FHIR_JSON_MEDIA_TYPE
    return fhir_response(
        operation_outcome(
            severity="error",
            code=error.issue_code,
            diagnostics=error.diagnostics,
            expression=error.expression,
        ),
        status_code=error.status_code,
        media_type=media_type,
    )
