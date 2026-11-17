"""Casos sintéticos para integridade, privacidade e metadados da imagem."""

import base64
import copy
import hashlib
import io

import pytest
from PIL import Image
from pydantic import ValidationError

from healplus_intake_image_api.core import image_validation
from healplus_intake_image_api.schemas.avaliacao_ferida import AvaliacaoFeridaParameters
from healplus_intake_image_api.schemas.fhir import Attachment
from test_fhir_avaliacao_ferida import intake_payload, jpeg_attachment


def _attachment(data: bytes) -> dict:
    return {
        "contentType": "image/jpeg",
        "data": base64.b64encode(data).decode(),
        "size": len(data),
        "hash": base64.b64encode(hashlib.sha1(data).digest()).decode(),
    }


def _media(payload: dict) -> dict:
    return next(
        item["resource"] for item in payload["parameter"][0]["resource"]["entry"]
        if item["resource"]["resourceType"] == "Media"
    )


def test_decodes_real_srgb_jpeg() -> None:
    attachment = jpeg_attachment()
    validated = Attachment.model_validate(attachment)
    assert validated.size == len(base64.b64decode(validated.data))


@pytest.mark.parametrize("field", ["size", "hash"])
def test_requires_size_and_sha1(field: str) -> None:
    attachment = jpeg_attachment()
    attachment.pop(field)
    with pytest.raises(ValidationError):
        Attachment.model_validate(attachment)


def test_rejects_size_mismatch() -> None:
    attachment = jpeg_attachment()
    attachment["size"] += 1
    with pytest.raises(ValidationError, match="diverge"):
        Attachment.model_validate(attachment)


def test_rejects_sha1_mismatch() -> None:
    attachment = jpeg_attachment()
    attachment["hash"] = base64.b64encode(b"0" * 20).decode()
    with pytest.raises(ValidationError, match="diverge"):
        Attachment.model_validate(attachment)


@pytest.mark.parametrize("data", [b"not a JPEG", b"\xff\xd8\xff\xe0\x00\x10", b"\xff\xd8\xff\xe0\x00\x10\xff\xd9"])
def test_rejects_arbitrary_or_truncated_bytes(data: bytes) -> None:
    with pytest.raises(ValidationError, match="JPEG"):
        Attachment.model_validate(_attachment(data))


def test_rejects_truncated_real_jpeg() -> None:
    attachment = jpeg_attachment()
    data = base64.b64decode(attachment["data"])
    with pytest.raises(ValidationError, match="JPEG"):
        Attachment.model_validate(_attachment(data[:-20]))


def test_rejects_png_mislabeled_as_jpeg() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16)).save(buffer, format="PNG")
    with pytest.raises(ValidationError, match="JPEG"):
        Attachment.model_validate(_attachment(buffer.getvalue()))


def test_requires_embedded_icc() -> None:
    with pytest.raises(ValidationError, match="ICC"):
        Attachment.model_validate(jpeg_attachment(icc=False))


def test_rejects_fake_icc_profile() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16)).save(buffer, format="JPEG", icc_profile=b"sRGB fake")
    with pytest.raises(ValidationError, match="ICC"):
        Attachment.model_validate(_attachment(buffer.getvalue()))


def test_rejects_non_normalized_orientation() -> None:
    exif = Image.Exif()
    exif[274] = 6
    with pytest.raises(ValidationError, match="orientação"):
        Attachment.model_validate(jpeg_attachment(exif=exif))


@pytest.mark.parametrize("tag,value", [(34853, {1: "N", 2: (1.0, 0.0, 0.0)}), (42032, "Nome pessoal"), (42033, "SERIAL-1"), (315, "Nome do fotógrafo")])
def test_rejects_sensitive_exif(tag: int, value) -> None:
    exif = Image.Exif()
    exif[tag] = value
    with pytest.raises(ValidationError, match="Remova GPS"):
        Attachment.model_validate(jpeg_attachment(exif=exif))


def test_rejects_sensitive_nested_exif() -> None:
    exif = Image.Exif()
    exif[34665] = {42037: "LENS-SERIAL"}
    with pytest.raises(ValidationError, match="Remova GPS"):
        Attachment.model_validate(jpeg_attachment(exif=exif))


def test_checks_pixel_limit_before_decode(monkeypatch) -> None:
    monkeypatch.setattr(image_validation, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ValidationError, match="megapixels"):
        Attachment.model_validate(jpeg_attachment())


def test_checks_image_byte_limit(monkeypatch) -> None:
    monkeypatch.setattr(image_validation, "MAX_IMAGE_BYTES", 100)
    with pytest.raises(ValidationError, match="10 MiB"):
        Attachment.model_validate(jpeg_attachment())


def test_rejects_declared_dimensions_mismatch(intake_payload: dict) -> None:
    _media(intake_payload)["width"] += 1
    with pytest.raises(ValidationError, match="width/height"):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


@pytest.mark.parametrize("field,value", [("width", 0), ("height", -1), ("width", True), ("height", 1.5)])
def test_rejects_invalid_fhir_dimensions(intake_payload: dict, field: str, value) -> None:
    _media(intake_payload)[field] = value
    with pytest.raises(ValidationError):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_requires_bundle_identifier(intake_payload: dict) -> None:
    intake_payload["parameter"][0]["resource"].pop("identifier")
    with pytest.raises(ValidationError):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_requires_local_coding_version(intake_payload: dict) -> None:
    _media(intake_payload)["bodySite"]["coding"][0].pop("version")
    with pytest.raises(ValidationError, match="Coding.version"):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_requires_version_for_preserved_extra_codings(intake_payload: dict) -> None:
    _media(intake_payload)["reasonCode"] = [{"coding": [{
        "system": "https://healplus.com.br/fhir/CodeSystem/motivo",
        "code": "exemplo",
    }]}]
    with pytest.raises(ValidationError, match="Coding.version"):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_requires_versioned_declared_profile(intake_payload: dict) -> None:
    _media(intake_payload)["meta"] = {"profile": [
        "https://healplus.com.br/fhir/StructureDefinition/HealPlusImagemClinica"
    ]}
    with pytest.raises(ValidationError, match="canonical"):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_every_photo_requires_its_human_quality_assessment(intake_payload: dict) -> None:
    extra = copy.deepcopy(next(
        item for item in intake_payload["parameter"][0]["resource"]["entry"]
        if item["resource"]["resourceType"] == "Media"
    ))
    extra["fullUrl"] = "urn:uuid:50000000-0000-4000-8000-000000000002"
    extra["resource"]["id"] = "media-002"
    intake_payload["parameter"][0]["resource"]["entry"].append(extra)
    with pytest.raises(ValidationError, match="Cada Media"):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_rejects_unresolved_capture_device(intake_payload: dict) -> None:
    _media(intake_payload)["device"] = {"reference": "Device/missing"}
    with pytest.raises(ValidationError, match="Media.device"):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_accepts_native_r4_capture_device_versions(intake_payload: dict) -> None:
    bundle = intake_payload["parameter"][0]["resource"]
    device_url = "urn:uuid:80000000-0000-4000-8000-000000000001"
    bundle["entry"].append({
        "fullUrl": device_url,
        "resource": {
            "resourceType": "Device",
            "id": "capture-device",
            "status": "active",
            "manufacturer": "Fabricante sintético",
            "modelNumber": "DEMO",
            "deviceName": [{"name": "Câmera sintética", "type": "model-name"}],
            "version": [{"type": {"text": "app"}, "value": "1.0.0"}],
        },
    })
    _media(intake_payload)["device"] = {"reference": device_url}
    assert AvaliacaoFeridaParameters.model_validate(intake_payload).bundle


def test_mandatory_code_requires_its_declared_codesystem(intake_payload: dict) -> None:
    for item in intake_payload["parameter"][0]["resource"]["entry"]:
        resource = item["resource"]
        if resource["resourceType"] == "Observation" and resource["code"]["coding"][0]["code"] == "dimensoes-ferida":
            resource["code"]["coding"][0]["system"] = "https://example.org/unrelated"
    with pytest.raises(ValidationError, match="dimensoes-ferida"):
        AvaliacaoFeridaParameters.model_validate(intake_payload)


def test_patient_reference_uses_fullurl_without_local_id(intake_payload: dict) -> None:
    entries = intake_payload["parameter"][0]["resource"]["entry"]
    patient_entry = next(item for item in entries if item["resource"]["resourceType"] == "Patient")
    patient_entry["resource"].pop("id")
    validated = AvaliacaoFeridaParameters.model_validate(intake_payload)
    assert validated.bundle.patient_reference == patient_entry["fullUrl"]
